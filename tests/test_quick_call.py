"""The tool-free Claude call dictation cleanup uses: offline, fake Claude only."""
import json
import os
import signal
import sys
import time
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import delphi


class QuickCallTests(unittest.TestCase):
    def test_claude_is_tool_free_and_receives_no_personal_settings(self):
        class Worker:
            pid = 12345
            returncode = 0
            def communicate(self, payload, timeout):
                self.payload = json.loads(payload)
                return json.dumps({'type': 'result', 'result': 'November 12.', 'total_cost_usd': .001}), ''
        worker = Worker()
        with patch.object(delphi.subprocess, 'Popen', return_value=worker) as start, patch.object(delphi, 'stop_claude'), patch.object(delphi.signal, 'signal'), patch.object(delphi.atexit, 'register'), patch.object(delphi, 'log_turn') as log:
            answer, metrics = delphi.quick_call('Stable prefix', 'A question', label='Dictation cleanup')
        args = start.call_args.args[0]
        self.assertEqual(args[args.index('--tools') + 1], '')
        self.assertIn('--no-session-persistence', args)
        self.assertEqual(args[args.index('--setting-sources') + 1], '')
        self.assertEqual(json.loads(args[args.index('--settings') + 1]), {'disableAllHooks': True})
        self.assertEqual(worker.payload['message']['content'], [{'type': 'text', 'text': 'A question'}])
        self.assertEqual(log.call_args.args[:2], ('Dictation cleanup', ''))
        self.assertEqual(answer, 'November 12.')
        self.assertEqual(metrics['usd'], .001)
        self.assertTrue(start.call_args.kwargs['start_new_session'])

    def test_other_clients_never_start_claude(self):
        for selected in ('devin', 'pi'):
            with self.subTest(client=selected), patch.object(delphi, 'client', return_value=selected), \
                 patch.object(delphi.subprocess, 'Popen') as start:
                with self.assertRaisesRegex(RuntimeError, 'needs Claude'):
                    delphi.quick_call('Stable prefix', 'A question')
                start.assert_not_called()

    def test_stop_cancels_claude_group(self):
        class Worker:
            pid = 12345
            def communicate(self, *args, **kwargs):
                raise subprocess.TimeoutExpired('claude', 45)
        worker = Worker()
        with patch.object(delphi.subprocess, 'Popen', return_value=worker), patch.object(delphi, 'stop_claude') as stop, patch.object(delphi.signal, 'signal'), patch.object(delphi.atexit, 'register'):
            with self.assertRaises(subprocess.TimeoutExpired):
                delphi.quick_call('prefix', 'question')
            stop.assert_called_once_with(worker)

    def test_sigterm_stops_actual_fake_worker(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            child = root / 'fake_claude.py'
            child.write_text("import sys,time\nfrom pathlib import Path\nPath(sys.argv[1]).write_text('ready')\ntime.sleep(1)\nPath(sys.argv[2]).write_text('survived')\n")
            runner = root / 'run.py'
            runner.write_text("import delphi,subprocess,sys\nreal=delphi.subprocess.Popen\ndelphi.subprocess.Popen=lambda args,**kwargs: real([sys.executable,sys.argv[1],sys.argv[2],sys.argv[3]],**kwargs)\ndelphi.quick_call('prefix','question')\n")
            ready, survived = root / 'ready', root / 'survived'
            p = subprocess.Popen([sys.executable, str(runner), str(child), str(ready), str(survived)],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 env={**os.environ, 'DELPHI_DIR': str(root), 'PYTHONPATH': str(Path(delphi.ME).parent)})
            self.addCleanup(lambda: p.poll() is None and p.kill())
            deadline = time.monotonic() + 15
            while not ready.exists() and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertTrue(ready.exists(), 'fake Claude never started')
            p.send_signal(signal.SIGTERM)
            p.wait(timeout=3)
            time.sleep(1.1)
            self.assertFalse(survived.exists(), 'Claude child survived Stop')


if __name__ == '__main__':
    unittest.main()
