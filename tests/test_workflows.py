"""Product memory regressions: fake model results, scratch storage, no Mac actions."""
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import delphi
from tests import scratch_dir


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        p = patch.object(delphi, 'SKILLS', str(scratch_dir(self) / 'skills.json'))
        p.start()
        self.addCleanup(p.stop)

    def test_automatically_saves_and_retrieves_verified_browser_procedure(self):
        p = unittest.mock.Mock()
        p.stdin = io.StringIO(); p.ask = ''; p.returncode = 0
        p.stdout = map(json.dumps, [
            {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'name': 'Bash',
             'input': {'command': delphi.WEB + ' read'}}]}},
            {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'content': 'Saved successfully.'}]}},
            {'type': 'result', 'result': 'Created your calendar event. [workflow create calendar event | Read the calendar form, fill today\'s requested values, save, then check the event appears.]'}])
        with patch.object(delphi, 'say'):
            reply, _, _ = delphi.run('make a calendar event', p)
        reply, saved = delphi.remember_workflow('make a calendar event', reply, delphi.run.ok, delphi.run.cmds)
        self.assertTrue(saved)
        self.assertEqual(reply, 'Created your calendar event.')
        method = delphi.workflows('Can you make a new calendar event tomorrow?')
        self.assertIn('Read the calendar form', method)
        self.assertNotIn('workflow', reply)
        self.assertEqual(delphi.workflows('open calendar'), '')
        with patch.object(delphi.subprocess, 'run') as action:
            self.assertIn('saved', delphi.fast('And remember how to make a calendar event for the future'))
            action.assert_not_called()

    def test_never_saves_failed_incomplete_or_disabled_tasks(self):
        for reply, ok, cmds in [
                ('Done. [workflow start meeting | Use the menu; check meeting controls.]', False, ['open x']),
                ('Could not complete it. [workflow start meeting | Use the menu.]', True, ['open x']),
                ('Done. [workflow start meeting | Use the menu.]', True, []),
                ('[workflow start meeting | Use the menu.]', True, ['open x'])]:
            clean, saved = delphi.remember_workflow('start meeting', reply, ok, cmds)
            self.assertFalse(saved)
            self.assertNotIn('[workflow', clean)
        with patch.object(delphi, 'pref', return_value=False):
            _, saved = delphi.remember_workflow('start meeting', 'Done. [workflow start meeting | Check meeting controls.]', True, ['open x'])
        self.assertFalse(saved)
        self.assertFalse((Path(delphi.DIR) / 'workflows.json').exists())

    def test_unverified_history_cannot_be_claimed_as_remembered(self):
        with patch.object(delphi.subprocess, 'run') as action:
            reply = delphi.fast('remember how to create a meeting')
        self.assertIn('do not have a verified procedure', reply)
        action.assert_not_called()

    def test_learns_the_way_that_worked_without_the_ai_writing_a_tag(self):
        menu = delphi.HANDS + ' click "Zoom Workplace > Start meeting"'
        tool = lambda i, c: {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'id': i, 'name': 'Bash', 'input': {'command': c}}]}}
        result = lambda i, err, content='': {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': i, 'is_error': err, 'content': content}]}}
        p = unittest.mock.Mock()
        p.stdin = io.StringIO(); p.ask = ''; p.returncode = 0
        p.stdout = map(json.dumps, [tool('a', delphi.HANDS + ' see zoom.us'), result('a', False),
                                    tool('b', 'osascript -e "click New meeting"'), result('b', True),   # tried, failed, dropped
                                    tool('c', menu), result('c', False, 'Meeting controls are visible.'),
                                    {'type': 'result', 'result': 'Your Zoom meeting started.'}])
        with patch.object(delphi, 'say'):
            reply, _, _ = delphi.run('Um, make a new Zoom meeting', p)
        delphi.learn('Um, make a new Zoom meeting', delphi.run.cmds, reply)
        self.assertEqual(delphi.skills()['make a new zoom meeting']['cmds'], [delphi.HANDS+' menu zoom.us \'Zoom Workplace > Start meeting\''])
        with patch.object(delphi, 'hands', return_value=('Clicked Start meeting', True)):
            self.assertEqual(delphi.fast('start a zoom meeting'), 'Your Zoom meeting started.')
        delphi.learn('click new meeting', [delphi.HANDS + ' click 245,340'], 'Done.')   # a screen spot moves: never learned
        self.assertNotIn('click new meeting', delphi.skills())

    def test_learns_only_the_successful_retry_when_a_tool_reports_failure(self):
        first, retry = (f'{delphi.PLACE} Fixture fullscreen {screen}' for screen in ('monitor', 'laptop'))
        tool = lambda i, command: {'type': 'assistant', 'message': {'content': [
            {'type': 'tool_use', 'id': i, 'name': 'Bash', 'input': {'command': command}}]}}
        receipt = lambda i, output, error=False: {'type': 'user', 'message': {'content': [
            {'type': 'tool_result', 'tool_use_id': i, 'is_error': error, 'content': output}]}}
        p = unittest.mock.Mock(stdin=io.StringIO(), ask='', returncode=0)
        p.stdout = map(json.dumps, [tool('first', first), receipt('first', 'NOT DONE: wrong display.', True),
                                    tool('retry', retry), receipt('retry', 'Fixture window -> fullscreen.'),
                                    {'type': 'result', 'is_error': False, 'result': 'Done.'}])
        with patch.object(delphi, 'say'):
            reply, _, _ = delphi.run('Arrange workspace', p)
        self.assertTrue(delphi.run.ok)
        self.assertEqual(delphi.run.cmds, [retry])
        with patch.object(delphi, 'cached_hands', return_value=None):
            self.assertTrue(delphi.learn('Arrange workspace', delphi.run.cmds, reply))
        self.assertEqual(delphi.skills()['arrange workspace']['cmds'], [retry])

    def test_failure_words_in_ordinary_read_output_are_untrusted_text(self):
        p = unittest.mock.Mock(stdin=io.StringIO(), ask='', returncode=0)
        p.stdout = map(json.dumps, [
            {'type': 'assistant', 'message': {'content': [
                {'type': 'tool_use', 'id': 'read', 'name': 'Read', 'input': {'file_path': 'fixture.txt'}}]}},
            {'type': 'user', 'message': {'content': [
                {'type': 'tool_result', 'tool_use_id': 'read', 'is_error': False,
                 'content': 'The page says the previous attempt failed and cannot continue.'}]}},
            {'type': 'result', 'is_error': False, 'result': 'I read the page.'}])
        with patch.object(delphi, 'say'):
            delphi.run('Read the fixture', p)
        self.assertTrue(delphi.run.ok)
        self.assertFalse(delphi.run.observed[0]['error'])

    def test_failed_or_unsafe_receipts_are_not_learned(self):
        tool = lambda command: {'type': 'assistant', 'message': {'content': [
            {'type': 'tool_use', 'id': 'action', 'name': 'Bash', 'input': {'command': command}}]}}
        receipt = lambda output, error: {'type': 'user', 'message': {'content': [
            {'type': 'tool_result', 'tool_use_id': 'action', 'is_error': error, 'content': output}]}}
        for command, output, error, ok in [(f'{delphi.PLACE} Fixture fullscreen laptop', 'NOT DONE: no window found.', True, False),
                                           ('rm -rf /tmp/example', 'Done.', False, True)]:
            with self.subTest(command=command):
                p = unittest.mock.Mock(stdin=io.StringIO(), ask='', returncode=0)
                p.stdout = map(json.dumps, [tool(command), receipt(output, error),
                                            {'type': 'result', 'is_error': False, 'result': 'Done.'}])
                with patch.object(delphi, 'say'):
                    reply, _, _ = delphi.run('Arrange workspace', p)
                self.assertEqual(delphi.run.ok, ok)
                with patch.object(delphi, 'cached_hands', return_value=None):
                    self.assertIsNone(delphi.learn('Arrange workspace', delphi.run.cmds, reply))
        self.assertEqual(delphi.skills(), {})

    def test_replay_runs_instantly_for_any_wording_and_rejects_unsafe_commands(self):
        cmd = delphi.HANDS + ' menu us.zoom.xos "Zoom Workplace > Start meeting"'
        reply, saved = delphi.remember_workflow('Um, can you make a new Zoom meeting?',
            f'Your meeting started. [workflow start zoom meeting | Use the Zoom menu; check the meeting window.] [replay {cmd}]', True, [cmd])
        self.assertTrue(saved)
        self.assertEqual(reply, 'Your meeting started.')
        with patch.object(delphi, 'hands', return_value=('Clicked Start meeting', True)) as action:
            self.assertEqual(delphi.fast('Make a zoom meeting.'), 'Your meeting started.')
            self.assertIsNone(delphi.fast('make a zoom call'))   # different words that matter: the AI decides
        self.assertEqual(action.call_args_list[0].args, ('menu', 'us.zoom.xos', 'Zoom Workplace > Start meeting'))
        for bad in [delphi.HANDS + ' click 1,2', 'rm -rf ~/x', delphi.HANDS + ' see x']:
            delphi.remember_workflow('do thing', f'Done. [workflow do thing | a] [replay {bad}]', True, ['open x'])
            self.assertNotIn('do thing', delphi.skills())

    def test_method_can_contain_shell_brackets_but_malformed_metadata_is_not_saved(self):
        reply, saved = delphi.remember_workflow('check report ready',
            'Ready. [workflow check report ready | Run [ -f report.txt ] and inspect its contents.]', True, ['test -f report.txt'])
        self.assertTrue(saved)
        self.assertEqual(reply, 'Ready.')
        self.assertIn('[ -f report.txt ]', delphi.workflows('check report ready'))
        for tag in ['[workflow invalid]', '[workflow | missing task]', '[workflow missing method | ]']:
            _, saved = delphi.remember_workflow('bad task', 'Done. ' + tag, True, ['open x'])
            self.assertFalse(saved)

    def test_model_recipe_cannot_save_commands_that_were_not_run(self):
        actual=f'{delphi.PLACE} Editor full monitor'
        invented=f'{delphi.PLACE} Browser full laptop'
        _,saved=delphi.remember_workflow('arrange desk',f'Done. [workflow arrange desk | Move and check the windows.] [replay {invented}]',True,[actual])
        self.assertTrue(saved)   # historical guidance may be kept, but it is not an executable shortcut
        self.assertNotIn('arrange desk',delphi.skills())

    def test_ai_shortcut_helper_defers_saving_until_verification(self):
        command=f'{delphi.SHOW} Editor'
        with patch.dict(os.environ,{'DELPHI_ASK':str(Path(delphi.DIR)/'agent')}), \
             patch.object(sys,'argv',['delphi.py','--shortcut','focus time',command]),patch('sys.stdout',new_callable=io.StringIO) as output:
            delphi.main()
        self.assertEqual(delphi.skills(),{})
        self.assertIn('successful tool results',output.getvalue())
        # A user's direct CLI definition remains available without running its actions.
        with patch.dict(os.environ,{k:v for k,v in os.environ.items() if k!='DELPHI_ASK'},clear=True), \
             patch.object(sys,'argv',['delphi.py','--shortcut','focus time',command]),patch('sys.stdout',new_callable=io.StringIO):
            delphi.main()
        self.assertEqual(delphi.skills()['focus time']['cmds'],[command])

    def test_correction_removes_procedure_even_with_different_wording(self):
        delphi.workflows('create calendar event', 'Use calendar form; verify event exists.')
        delphi.unlearn('make a new calendar event')
        self.assertEqual(delphi.workflows('create calendar event'), '')

    def test_settings_can_inspect_and_delete_saved_procedure(self):
        delphi.workflows('create calendar event', 'Fill calendar form; verify event exists.')
        with patch('sys.argv', ['delphi.py', '--state']), patch.object(delphi, 'plan', return_value={}), \
             patch.object(delphi, 'me', return_value={}), patch.object(delphi, 'MEMORY', str(Path(delphi.DIR) / 'memory.md')), \
             patch('sys.stdout', new_callable=io.StringIO) as out:
            delphi.main()
        row = json.loads(out.getvalue())['skills'][0]
        self.assertEqual(row['say'], 'create calendar event')
        self.assertIn('verify event', row['reply'])
        with patch('sys.argv', ['delphi.py', '--unlearn', row['say']]):
            delphi.main()
        self.assertEqual(delphi.workflows(), {})

    def test_full_request_saves_then_reuses_procedure_without_extra_model_call(self):
        brain = unittest.mock.Mock(return_value=(
            'Created it. [workflow create calendar event | Read calendar, fill current values, save; verify event exists.]', .001, []))
        brain.ok = True
        brain.cmds = brain.ran = [delphi.WEB + ' read', delphi.WEB + ' fill 2 title']
        brain.observed = []
        with patch.multiple(delphi, licensed=lambda: True, ping=lambda: None, fast=lambda _: None,
                            front=lambda: ('Notes', ''), osa=lambda *a: '', screens=lambda: [],
                            describe=lambda *a: '', me_line=lambda: '', selection_context=lambda: '',
                            relevant_rules=lambda _: '', recent=lambda: [], screen_for=lambda *a: None,
                            wait_commit=lambda: True, run=brain, remember_turn=lambda *a: None,
                            log_turn=lambda *a, **k: None, restore_focus=lambda *a: None), \
             patch.object(delphi.threading, 'Thread'), patch('sys.stdout', io.StringIO()):
            with patch('sys.argv', ['delphi.py', 'make a calendar event']):
                delphi.main()
            self.assertEqual(brain.call_count, 1)
            brain.return_value = ('Created it.', .001, [])
            with patch('sys.argv', ['delphi.py', 'create a new calendar event tomorrow']):
                delphi.main()
        self.assertEqual(brain.call_count, 2)
        self.assertIn('Saved workflow (historical guidance)', brain.call_args.args[0])
        self.assertIn('verify event exists', brain.call_args.args[0])

    def test_only_matching_procedure_enters_prompt_and_remember_waits_for_confirmation(self):
        delphi.workflows('create calendar event', 'a' * 2000)
        delphi.workflows('play jazz playlist', 'Read playlists; choose jazz; verify playing.')
        self.assertEqual(len(delphi.workflows('create calendar event').split('Procedure: ')[1]), 800)
        self.assertNotIn('jazz', delphi.workflows('create calendar event'))
        with patch.dict(os.environ, {'DELPHI_LIVE': '1'}):
            self.assertIsNone(delphi.fast('remember how to create calendar event'))
        full = delphi.SYSTEM + delphi.ASK_ME + delphi.POINTER + delphi.LEARN_ME + delphi.TEACH + delphi.ASK_FIRST + delphi.WORKFLOW
        self.assertLessEqual(len(full), 10000)
        installed = os.path.expanduser("~/Applications/Delphi.app/Contents/Resources/delphi.py")
        self.assertLessEqual(len(full.replace(delphi.ME, installed)), 10000)

    def test_interrupted_shortcut_save_preserves_private_previous_file(self):
        saved={'original':{'mine':True,'cmds':['echo ok'],'reply':'Done.'}}
        Path(delphi.SKILLS).write_text(json.dumps(saved))
        with patch.object(delphi.json,'dump',side_effect=OSError('disk full')):
            with self.assertRaises(OSError): delphi.save_skills({'new':{'mine':True}})
        self.assertEqual(delphi.skills(),saved)
        self.assertEqual(list(Path(delphi.DIR).iterdir()),[Path(delphi.SKILLS)])
        delphi.save_skills(saved)
        self.assertEqual(Path(delphi.SKILLS).stat().st_mode & 0o777,0o600)


if __name__ == '__main__':
    unittest.main()
