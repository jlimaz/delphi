"""Jev routing of loose phrasings to instant commands: offline, a fake TypeSafe API only."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import delphi


def answers(action='open', app='Spotify', where='none', screen='current', sure=1.0, one=.97):
    choice = lambda c: {'type': 'choice', 'choice': c, 'confidence': sure, 'probabilities': {c: sure}}
    return {'model': 'jev-1.13.0', 'answers': {'action': choice(action), 'app': choice(app), 'where': choice(where),
                                               'screen': choice(screen), 'one': {'type': 'noul', 'noul': one}}}


class JevTests(unittest.TestCase):
    def ask(self, text, reply=None, prefs=None, error=None, env=None, key='ts-fixture'):
        prefs = prefs or {}
        sent = []
        def urlopen(request, timeout):
            sent.append((request, timeout))
            if error: raise error
            return io.BytesIO(json.dumps(reply or answers()).encode())
        with patch.object(delphi, 'TYPESAFE_KEY', key), patch.object(delphi, 'pref', side_effect=lambda k, d: prefs.get(k, d)), \
             patch.object(delphi, 'jev_apps', return_value=['Google Chrome', 'Slack', 'Spotify']), \
             patch.object(delphi.urllib.request, 'urlopen', side_effect=urlopen), \
             patch.object(delphi, 'fast', return_value='Done.') as fast, \
             patch.dict(os.environ, env or {}):
            if not env: os.environ.pop('DELPHI_LIVE', None)
            result = delphi.jev(text)
        return result, fast, sent

    def test_confident_open_runs_the_existing_instant_command(self):
        result, fast, sent = self.ask('could you fire up my music app')
        self.assertEqual(result, 'Done.')
        fast.assert_called_once_with('open Spotify')
        self.assertTrue(delphi.jev.hit)
        request, timeout = sent[0]
        body = json.loads(request.data)
        self.assertEqual(request.full_url, 'https://api.typesafe.ai/v1/systemone')
        self.assertEqual(request.get_header('Authorization'), 'Bearer ts-fixture')
        self.assertEqual(body['state'], 'could you fire up my music app')
        self.assertEqual(body['model'], 'jev-latest')
        self.assertEqual(set(body['questions']['app']['criteria']), {'Google Chrome', 'Slack', 'Spotify', 'none'})
        self.assertEqual(timeout, 1)

    def test_move_says_only_the_place_and_screen_it_heard(self):
        _, fast, _ = self.ask('throw the browser on my big screen, left side',
                              answers('move', 'Google Chrome', 'left', 'monitor'))
        fast.assert_called_once_with('move Google Chrome left monitor')
        _, fast, _ = self.ask('make slack big', answers('move', 'Slack', 'full', 'current'))
        fast.assert_called_once_with('move Slack full')
        _, fast, _ = self.ask('move slack', answers('move', 'Slack', 'none', 'current'))
        fast.assert_not_called()

    def test_unsure_answers_go_to_the_ai(self):
        for reply in (answers(sure=.6), answers(one=.5), answers(app='none'), answers(action='other'),
                      answers('quit', 'Slack', sure=.85)):   # quitting needs more certainty than opening
            with self.subTest(reply=reply):
                result, fast, _ = self.ask('get rid of slack', reply)
                self.assertIsNone(result); fast.assert_not_called(); self.assertFalse(delphi.jev.hit)
        _, fast, _ = self.ask('get rid of slack', answers('quit', 'Slack', sure=.95))
        fast.assert_called_once_with('quit Slack')

    def test_slow_or_broken_api_goes_to_the_ai(self):
        for error in (TimeoutError('slow'), OSError('offline')):
            with self.subTest(error=error):
                result, fast, _ = self.ask('fire up spotify', error=error)
                self.assertIsNone(result); fast.assert_not_called()
        result, fast, _ = self.ask('fire up spotify', {'detail': 'Invalid API key'})
        self.assertIsNone(result); fast.assert_not_called()

    def test_no_call_without_a_key_or_for_requests_it_cannot_route(self):
        for text, key, env in (('fire up spotify', '', None),
                               ('fire up spotify', 'ts-fixture', {'DELPHI_LIVE': '1'}),   # waits for confirmed words
                               ('close this', 'ts-fixture', None),
                               ('fire up spotify and then play jazz', 'ts-fixture', None),
                               ('please could you go ahead and find the thing I was working on yesterday afternoon', 'ts-fixture', None)):
            with self.subTest(text=text):
                result, fast, sent = self.ask(text, env=env, key=key)
                self.assertIsNone(result); self.assertEqual(sent, []); fast.assert_not_called()

    def test_key_comes_from_the_env_file_beside_delphi(self):
        self.assertEqual(delphi.TYPESAFE_KEY, '')   # tests/__init__.py: the repo's real key never reaches a test
        with tempfile.TemporaryDirectory() as root:
            Path(root, '.env').write_text('# TypeSafe\nOTHER=1\nexport TYPESAFE_API_KEY="ts-from-file"\n')
            with patch.object(delphi, 'ME', str(Path(root, 'delphi.py'))):
                self.assertEqual(delphi.dotenv('TYPESAFE_API_KEY'), 'ts-from-file')
                self.assertEqual(delphi.dotenv('MISSING'), '')
            with patch.object(delphi, 'ME', str(Path(root, 'none', 'delphi.py'))):
                self.assertEqual(delphi.dotenv('TYPESAFE_API_KEY'), '')

    def test_app_list_fits_one_choice(self):
        with patch.object(delphi.os, 'listdir', return_value=[f'App {i}.app' for i in range(400)]), \
             patch.object(delphi.os.path, 'isdir', return_value=True):
            self.assertEqual(len(delphi.jev_apps()), 254)


if __name__ == '__main__':
    unittest.main()
