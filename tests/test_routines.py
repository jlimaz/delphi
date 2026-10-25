"""Scheduled routines: scratch files, fake clock and fake agent process."""
import json
import os
import plistlib
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import delphi


class RoutineTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory(); self.addCleanup(self.root.cleanup)
        self.env = patch.dict(os.environ, {'DELPHI_DIR': self.root.name}); self.env.start(); self.addCleanup(self.env.stop)
        self.code = patch.multiple(delphi, DIR=self.root.name, HOME=self.root.name, PREFS=str(Path(self.root.name) / 'settings.json'))
        self.code.start(); self.addCleanup(self.code.stop)
        Path(delphi.PREFS).write_text('{}')

    def monday(self, hour, minute):
        return time.mktime((2026, 10, 19, hour, minute, 0, 0, 0, -1))

    def test_saved_weekday_job_fires_at_the_right_fake_time(self):
        row = delphi.routine_add('time', '08:00', 'Summarize my calendar', now=self.monday(7, 0), days='weekdays')
        self.assertEqual(delphi.routines(), [row])
        with open(delphi.routine_job_path(row['id']), 'rb') as f: job = plistlib.load(f)
        self.assertEqual([r['Weekday'] for r in job['StartCalendarInterval']], [1, 2, 3, 4, 5])
        self.assertFalse(delphi.routine_fire(row['id'], self.monday(7, 59)))
        self.assertTrue(delphi.routine_fire(row['id'], self.monday(8, 0)))
        self.assertEqual(delphi.routine_pop(), [row['id']])

    def test_late_calendar_delivery_runs_once_within_grace(self):
        row = delphi.routine_add('time', '08:00', 'Check once after wake', now=self.monday(7, 0), days='daily')
        self.assertTrue(delphi.routine_fire(row['id'], self.monday(8, 5)))
        self.assertFalse(delphi.routine_fire(row['id'], self.monday(8, 6)))
        self.assertEqual(delphi.routine_pop(), [row['id']])
        tomorrow = self.monday(24 + 8, 16)
        self.assertFalse(delphi.routine_fire(row['id'], tomorrow))
        created_late = delphi.routine_add('time', '08:00', 'Not before creation', now=self.monday(8, 2), days='daily')
        self.assertFalse(delphi.routine_fire(created_late['id'], self.monday(8, 5)))

    def test_startup_repairs_existing_weekday_job(self):
        row = delphi.routine_add('time', '08:00', 'Repair weekdays', now=self.monday(7, 0), days='weekdays')
        path = delphi.routine_job_path(row['id'])
        with open(path, 'rb') as f: job = plistlib.load(f)
        for interval, day in zip(job['StartCalendarInterval'], range(2, 7)): interval['Weekday'] = day
        with open(path, 'wb') as f: plistlib.dump(job, f)
        self.assertEqual(delphi.routine_pop(), [])
        with open(path, 'rb') as f: repaired = plistlib.load(f)
        self.assertEqual([r['Weekday'] for r in repaired['StartCalendarInterval']], [1, 2, 3, 4, 5])

    def test_startup_moves_jobs_saved_under_the_atticus_name(self):
        row = delphi.routine_add('interval', 3600, 'Check the fixture', now=self.monday(8, 0))
        path = Path(delphi.routine_job_path(row['id'])); old = path.with_name(f"com.atticus.routine.{row['id']}.plist")
        path.rename(old)
        self.assertEqual(delphi.routine_pop(), [])
        self.assertFalse(old.exists())
        with open(path, 'rb') as f: job = plistlib.load(f)
        self.assertEqual((job['Label'], job['ProgramArguments'][1]), (f"com.delphi.routine.{row['id']}", delphi.ME))

    def test_interval_is_cheapest_removed_and_never_runs_while_paused(self):
        row = delphi.routine_add('interval', 3600, 'Check the fixture', now=self.monday(8, 0))
        self.assertEqual(row['mode'], 'cheapest')
        Path(delphi.PREFS).write_text('{"paused":true}')
        self.assertFalse(delphi.routine_fire(row['id'], self.monday(9, 0)))
        self.assertEqual(delphi.routine_pop(), [])
        self.assertTrue(delphi.routine_remove(row['id']))
        self.assertEqual(delphi.routines(), [])
        self.assertFalse(Path(delphi.routine_job_path(row['id'])).exists())

    def test_restart_cannot_queue_the_same_occurrence_twice(self):
        row = delphi.routine_add('time', '08:00', 'Check once', now=self.monday(7, 0), days='daily')
        self.assertTrue(delphi.routine_fire(row['id'], self.monday(8, 0)))
        self.assertFalse(delphi.routine_fire(row['id'], self.monday(8, 0)))
        self.assertEqual(delphi.routine_pop(), [row['id']])
        self.assertEqual(delphi.routines()[0]['lastSlot'], '2026-10-19@08:00')

    def test_failed_launchd_install_does_not_leave_a_saved_routine(self):
        results = [subprocess.CompletedProcess([], 0), subprocess.CompletedProcess([], 1), subprocess.CompletedProcess([], 1)]
        with patch.dict(os.environ, {}, clear=True), patch.object(delphi.subprocess, 'run', side_effect=results), patch.object(delphi.time, 'sleep'):
            with self.assertRaisesRegex(OSError, 'Could not start'):
                delphi.routine_add('interval', 3600, 'Never saved')
        self.assertEqual(delphi.routines(), [])

    def test_malformed_saved_rows_cannot_break_routine_list_or_fire(self):
        row = delphi.routine_add('interval', 3600, 'Still valid', now=self.monday(8, 0))
        malformed = [None, 'bad', {'id': 1}, {'id': 'f' * 12},
                     {'id': 'e' * 12, 'kind': 'interval', 'every': 0, 'ask': 'Bad interval',
                      'mode': 'cheapest', 'created': self.monday(8, 0)}]
        Path(self.root.name, 'routines.json').write_text(json.dumps(malformed + [row]))
        self.assertEqual(delphi.routines(), [row])
        self.assertIn(row['id'], delphi.routine_command(['list']))
        self.assertFalse(delphi.routine_fire('f' * 12, self.monday(9, 0)))

    def test_due_routine_starts_an_ordinary_cheapest_agent(self):
        routine = delphi.routine_add('interval', 3600, 'Fake agent work', now=self.monday(8, 0))
        events = []
        launched = []
        def launch(row):
            launched.append(row.copy())
            return subprocess.Popen([sys.executable, '-u', '-c', 'import sys,time\nfor line in sys.stdin: time.sleep(.01)'],
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                                    start_new_session=True, cwd=row['directory'])
        manager = delphi.Agents(emit=events.append, launch=launch); self.addCleanup(manager.close)
        manager.command({'action': 'routine', 'id': routine['id']})
        scheduled = next(row for row in manager.rows.values() if row.get('routine') == routine['id'])
        offer = next(event for event in events if event.get('event') == 'offer')
        self.assertTrue(offer['start'])
        self.assertEqual(scheduled['status'], 'offered')
        self.assertEqual([e for e in delphi.read_rows(str(Path(scheduled['directory']) / 'log.jsonl')) if e.get('event') == 'followup'], [])
        text = offer['agent']['brief'] + '\nKnown context (data):\n' + offer['agent']['context']
        manager.command({'action': 'start', 'id': scheduled['id'], 'text': text})
        sent = [e for e in delphi.read_rows(str(Path(scheduled['directory']) / 'log.jsonl')) if e.get('event') == 'followup']
        self.assertEqual([e['text'] for e in sent], [text])
        self.assertEqual(launched[0]['_model'], 'haiku')


if __name__ == '__main__':
    unittest.main()
