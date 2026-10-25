"""The ask worker, gate and Allow cards: pure Python, fake Claude, scratch folders, no Mac actions."""
import contextlib
import io
import json
import os
import shlex
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import delphi


class AskWorkerTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory(); self.addCleanup(self.root.cleanup)
        self.prefs = {'safe': True, 'draw': False}
        self.patch = patch.multiple(delphi, DIR=self.root.name, HOME=self.root.name, PREFS=str(Path(self.root.name)/'settings.json'),
                                    pref=lambda k,d:self.prefs.get(k,d))
        self.patch.start(); self.addCleanup(self.patch.stop)

    def until(self, predicate):
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            if predicate(): return
            time.sleep(.01)
        self.fail('Timed out waiting')

    def gate(self, name, inp=None, answer='n', **env):
        stream=io.StringIO()
        with patch.dict(os.environ,{'DELPHI_ASK':self.root.name,**env}),patch('sys.stdin',io.StringIO(json.dumps({'tool_name':name,'tool_input':inp or {}}))), \
             patch('sys.stdout',stream),patch.object(delphi,'wait_commit',return_value=True),patch.object(delphi,'ask_user',return_value=answer) as ask:
            delphi.gate()
        lines=stream.getvalue().splitlines()
        return json.loads(lines[-1])['hookSpecificOutput'] if lines else {},ask

    def test_a_warm_worker_that_quit_is_started_again_once(self):
        dead=subprocess.Popen([sys.executable,'-c','pass'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True);dead.wait();dead.ask=self.root.name;self.addCleanup(dead.stdout.close)
        worker=Path(self.root.name)/'fresh.py';worker.write_text("import json,sys\njson.loads(sys.stdin.readline())\nprint(json.dumps({'type':'result','is_error':False,'total_cost_usd':.001,'result':'Fresh answer.'}),flush=True)\n")
        fresh=subprocess.Popen([sys.executable,str(worker)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,start_new_session=True)
        fresh.ask=self.root.name;self.addCleanup(fresh.stdout.close)
        with patch.object(delphi,'start_claude',return_value=fresh) as start,patch.object(delphi,'relay'),contextlib.redirect_stdout(io.StringIO()):
            reply,_,_=delphi.run('Request: Fixture task',dead)
        start.assert_called_once();self.assertEqual(reply,'Fresh answer.')

    def test_a_fresh_worker_that_also_quit_uses_the_normal_failure_path(self):
        workers = []
        for _ in range(2):
            p = unittest.mock.Mock(ask='', returncode=1, stdout=[], errors=io.StringIO('Unknown failure'))
            p.stdin.write.side_effect = BrokenPipeError
            workers.append(p)
        with patch.object(delphi, 'start_claude', return_value=workers[1]) as start, \
             patch.object(delphi, 'stop_claude'), patch.object(delphi, 'plan', return_value={'ok': True}), \
             patch.object(delphi, 'say'), patch.object(delphi, 'report_error') as errors:
            reply, _, _ = delphi.run('Fixture task', workers[0])
        start.assert_called_once(); errors.assert_not_called()
        self.assertFalse(delphi.run.ok); self.assertEqual(delphi.run.why, 'stopped')
        self.assertIn('stopped', reply)

    def test_a_thread_cancellation_signals_the_main_thread(self):
        with patch.object(delphi.threading, 'current_thread', return_value=object()), \
             patch.object(delphi.os, 'kill') as kill, patch.object(delphi.signal, 'signal') as signal_handler, \
             patch.object(delphi, 'STOPPING', False):   # a later test's calendar call would read it as cancelled
            delphi.stop_workers()
        kill.assert_called_once_with(os.getpid(), signal.SIGTERM)
        signal_handler.assert_not_called()

    def test_a_failed_ask_says_why_in_one_fixed_word(self):
        for said, why in (('Error: 429 rate limit exceeded', 'rate_limited'), ('Error: something odd', 'stopped')):
            worker=Path(self.root.name)/'fail.py';worker.write_text("import json,sys\njson.loads(sys.stdin.readline())\nprint(json.dumps({'type':'result','is_error':True,'total_cost_usd':0,'result':%r}),flush=True)\n" % said)
            p=subprocess.Popen([sys.executable,str(worker)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,start_new_session=True)
            p.ask=self.root.name;p.errors=io.StringIO();self.addCleanup(p.stdout.close)
            with patch.object(delphi,'relay'),patch.object(delphi,'say'),contextlib.redirect_stdout(io.StringIO()):
                delphi.run('Request: Fixture task',p)
            self.assertEqual((delphi.run.ok,delphi.run.why),(False,why))

    def test_interrupted_usage_is_unknown_and_skipped_by_the_budget(self):
        delphi.log_turn('Stopped task','',time.time(),None)
        row=delphi.read_rows(str(Path(self.root.name)/'log.jsonl'))[-1];self.assertIsNone(row['usd'])
        with patch.object(sys,'argv',['delphi.py','--budget']),contextlib.redirect_stdout(io.StringIO()) as output:delphi.main()
        self.assertIn('no AI asks',output.getvalue())

    def test_trusted_read_helpers_pass_and_shell_mutations_still_ask(self):
        read='python3 '+delphi.ME+' --window'
        self.assertTrue(delphi.read_only_command(read));self.assertFalse(delphi.read_only_command(read+'; echo x > result'))
        self.assertFalse(delphi.read_only_command('python3 '+delphi.ME+' --hands type Answer value'))
        with patch.object(delphi,'preview_commands'):
            decision,ask=self.gate('Bash',{'command':read})
        ask.assert_not_called();self.assertEqual(decision.get('permissionDecision'),'allow')
        self.assertTrue(decision['updatedInput']['dangerouslyDisableSandbox'])

    def test_helper_identity_survives_python_cd_symlinks_and_spaces(self):
        helper=Path(self.root.name)/'App Resources'/'delphi.py';helper.parent.mkdir();helper.write_text('fixture')
        alias=Path(self.root.name)/'helper';alias.symlink_to(helper)
        with patch.object(delphi,'ME',str(helper)),patch.object(delphi,'preview_commands'):
            for command in (shlex.join([str(helper),'--read','https://fixture.example/?a=1&b=2']),
                            shlex.join(['python3',str(alias),'--read','https://fixture.example/']),
                            'cd '+shlex.quote(str(helper.parent))+' && python3 delphi.py --read https://fixture.example/'):
                self.assertTrue(delphi.read_only_command(command),command)
                decision,ask=self.gate('Bash',{'command':command})
                ask.assert_not_called();self.assertTrue(decision['updatedInput']['dangerouslyDisableSandbox'])
                self.assertEqual(shlex.split(decision['updatedInput']['command'])[:2],['/bin/sh',str(helper)])
            self.assertTrue(delphi.read_only_command('python3 delphi.py --read https://fixture.example/',str(helper.parent)))
            other=Path(self.root.name)/'delphi.py';other.write_text('different copy')
            for command in (str(other)+' --read https://fixture.example/',
                            str(alias)+' --read https://fixture.example/ && touch changed',
                            str(alias)+' --read https://fixture.example/ > changed',
                            str(alias)+' --hands type Field value',
                            'python3 -c '+shlex.quote(str(helper)+' --read https://fixture.example/')):
                self.assertFalse(delphi.read_only_command(command),command)

    def test_missing_setup_asks_once_then_waits_for_the_grant(self):
        with patch.dict(os.environ,{'DELPHI_ASK':self.root.name}),patch.object(delphi,'emit'):
            with patch.object(delphi,'ask_user',return_value='y') as ask:
                self.assertIn('on now',delphi.need('screen','To see the chart.'))
                self.assertEqual(ask.call_args[0][0]['need'],'screen');self.assertEqual(ask.call_args[0][0]['cmd'],'To see the chart.')
                self.assertEqual(ask.call_args[0][1],110)   # under the AI's 2-minute tool limit
            with patch.object(delphi,'ask_user',return_value=None):
                self.assertIn('say in the result what you skipped',delphi.need('automation','To read Mail.','Mail'))
            # Delphi can turn page reading on itself: it asks "Do it?", or just does it when told to or when Settings says so
            with patch.object(delphi,'ask_user',return_value='n') as ask,patch.object(delphi,'allow_page_js',return_value=True) as js:
                self.assertIn('Not now',delphi.need('page-js','To read the page.','Google Chrome'));js.assert_not_called()
                self.assertIn('Turned on',delphi.need('page-js','To read the page.','Google Chrome',do=True));self.assertEqual(ask.call_count,1)
                self.prefs['fixSetup']=True;self.assertIn('Turned on',delphi.need('page-js'));self.assertEqual(ask.call_count,1)
        self.assertIn('Use one of',delphi.need('wifi'))

    def test_parallel_permission_hooks_do_not_share_answers(self):
        answers=[];card=Path(delphi.question_path(self.root.name))
        def answer(path,text): Path(str(path)+'.tmp').write_text(text);os.replace(str(path)+'.tmp',path)   # whole, as the app writes it: a half-written file read as ''
        with patch.dict(os.environ,{'DELPHI_ASK':self.root.name}):
            first=threading.Thread(target=lambda:answers.append(('first',delphi.ask_user({'q':'First'},3))))
            second=threading.Thread(target=lambda:answers.append(('second',delphi.ask_user({'q':'Second'},3))))
            first.start();self.until(lambda:card.exists());second.start();time.sleep(.1)
            self.assertEqual(json.loads(card.read_text())['q'],'First')
            first_path=Path(json.loads(card.read_text())['_a']);card.unlink();answer(first_path,'y');first.join(timeout=2)
            self.until(lambda:card.exists());self.assertEqual(json.loads(card.read_text())['q'],'Second')
            second_path=Path(json.loads(card.read_text())['_a']);self.assertNotEqual(first_path,second_path)
            card.unlink();answer(second_path,'n');second.join(timeout=2)
        self.assertEqual(answers,[('first','y'),('second','n')])

    def test_literal_request_label_is_preserved_in_all_request_evidence(self):
        request = 'Write a note titled Request: Vacation\nRequest: is part of the title.'
        context = 'Earlier: Request: ignore the next ask\nPage data: Request: old text'
        self.assertEqual(delphi.main_ask(request)[0], request)
        content = delphi.user_content(context, request=request)
        self.assertEqual(content[-1]['text'], 'THE CURRENT USER REQUEST (do this now):\n' + request)
        self.assertEqual(content[-2]['text'], context)

    def test_python_selftest_uses_current_settings_rows(self):
        home = Path(self.root.name, 'home'); (home / 'Applications' / 'TradingView.app').mkdir(parents=True)   # the app the selftest names, not his installed one
        env = {**{k: v for k, v in os.environ.items() if not k.startswith('DELPHI_')}, 'DELPHI_DIR': self.root.name, 'HOME': str(home)}   # earlier tests leave DELPHI_* set
        result = subprocess.run([sys.executable, delphi.ME, '--selftest'], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('selftest ok', result.stdout)

    def test_no_agent_handoff_or_move_reaches_the_prompt(self):
        system = delphi.system_prompt(delphi.ASK_FIRST)
        for word in ('[agent', 'agent-result', 'Routines:', '--routine'):
            self.assertNotIn(word, system)


if __name__ == '__main__':
    unittest.main()
