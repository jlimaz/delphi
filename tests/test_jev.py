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


def answers(action='open', app='Spotify', where='none', screen='current', sure=1.0, one=.97, site='none', amount='1', pt=.02):
    choice = lambda c: {'type': 'choice', 'choice': c, 'confidence': sure, 'probabilities': {c: sure}}
    return {'model': 'jev-1.13.0', 'answers': {'action': choice(action), 'app': choice(app), 'where': choice(where),
                                               'screen': choice(screen), 'site': choice(site), 'amount': choice(amount),
                                               'one': {'type': 'noul', 'noul': one}, 'portuguese': {'type': 'noul', 'noul': pt}}}


class JevTests(unittest.TestCase):
    def ask(self, text, reply=None, prefs=None, error=None, env=None, key='ts-fixture'):
        prefs = prefs or {}
        sent = []
        def urlopen(request, timeout):
            sent.append((request, timeout))
            if error: raise error
            return io.BytesIO(json.dumps(reply or answers()).encode())
        with patch.object(delphi, 'TYPESAFE_KEY', key), patch.object(delphi, 'pref', side_effect=lambda k, d: prefs.get(k, d)), \
             patch.object(delphi, 'jev_apps', return_value=['Brave Browser', 'Google Chrome', 'Slack', 'Spotify']), \
             patch.object(delphi, 'jev_sites', return_value={'amazon.com': 'Amazon', 'mail.google.com': 'Gmail'}), \
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
        self.assertEqual(set(body['questions']['app']['criteria']), {'Brave Browser', 'Google Chrome', 'Slack', 'Spotify', 'none'})
        self.assertEqual(timeout, 1)

    def test_move_says_only_the_place_and_screen_it_heard(self):
        _, fast, _ = self.ask('throw the browser on my big screen, left side',
                              answers('move', 'Google Chrome', 'left', 'monitor'))
        fast.assert_called_once_with('move Google Chrome left monitor')
        _, fast, _ = self.ask('make slack big', answers('move', 'Slack', 'full', 'current'))
        fast.assert_called_once_with('move Slack full')
        _, fast, _ = self.ask('move slack', answers('move', 'Slack', 'none', 'current'))
        fast.assert_not_called()

    def test_music_volume_tabs_and_screen_use_the_instant_commands(self):
        for action, amount, said in (('pause', '1', 'pause'), ('next', '1', 'next'), ('volume_up', '2', 'turn volume up by 2'),
                                     ('volume_down', '1', 'turn volume down by 1'), ('mute', '1', 'mute'), ('new_tab', '1', 'new tab'),
                                     ('reload', '1', 'reload'), ('screen_saver', '1', 'screen saver'), ('display_off', '1', 'turn off the display')):
            with self.subTest(action=action):
                _, fast, _ = self.ask('baixe um pouquinho', answers(action, 'none', amount=amount))
                fast.assert_called_once_with(said)

    def test_an_undoable_action_jev_is_sure_of_allows_a_less_sure_one_step(self):
        _, fast, _ = self.ask('baixe um pouquinho', answers('volume_down', 'none', one=.74))
        fast.assert_called_once_with('turn volume down by 1')
        for reply in (answers('volume_down', 'none', one=.74, sure=.9), answers('quit', 'Slack', one=.74)):
            _, fast, _ = self.ask('baixe um pouquinho', reply)
            fast.assert_not_called()

    def test_closing_a_tab_needs_more_certainty_and_the_named_app_in_front(self):
        _, fast, _ = self.ask('get rid of this tab', answers('close_tab', 'none', sure=.85))
        fast.assert_not_called()
        _, fast, _ = self.ask('feche a aba do brave', answers('close_tab', 'Brave Browser'), env={'DELPHI_FRONT': 'Slack'})
        fast.assert_not_called()
        _, fast, _ = self.ask('feche a aba do brave', answers('close_tab', 'Brave Browser'), env={'DELPHI_FRONT': 'Brave Browser'})
        fast.assert_called_once_with('close tab')

    def test_a_site_opens_by_its_host_or_in_the_named_browser(self):
        _, fast, _ = self.ask('abra amazon pra mim', answers('site', 'none', site='amazon.com'))
        fast.assert_called_once_with('open amazon.com')
        ok = delphi.subprocess.CompletedProcess([], 0)
        with patch.object(delphi.subprocess, 'run', return_value=ok) as run:
            result, fast, _ = self.ask('abre meu e-mail no brave', answers('site', 'Brave Browser', site='mail.google.com', pt=.97))
        run.assert_called_once_with(['open', '-a', 'Brave Browser', 'https://mail.google.com'])
        fast.assert_not_called(); self.assertTrue(delphi.jev.hit)
        self.assertEqual(result, 'Abri Gmail no Brave Browser.')
        for reply in (answers('site', 'none', site='none'), answers('site', 'Slack', site='amazon.com')):   # no site, or "in Slack"
            _, fast, _ = self.ask('open amazon', reply)
            fast.assert_not_called()

    def test_portuguese_requests_get_portuguese_replies(self):
        with patch.object(delphi, 'TYPESAFE_KEY', 'ts-fixture'):
            result, _, _ = self.ask('bota pra tocar', answers('open', 'Spotify', pt=.95))
        self.assertEqual(result, 'Done.')   # an unknown reply stays as it is
        with patch.object(delphi, 'portuguese', return_value='Abri Spotify.') as pt:
            result, _, _ = self.ask('bota o spotify', answers('open', 'Spotify', pt=.95))
        self.assertEqual(result, 'Abri Spotify.'); pt.assert_called_once_with('Done.')

    def test_site_list_adds_hosts_earlier_asks_opened(self):
        rows = [{'ran': ['/x/delphi.py --show --bg "https://www.amazon.com.br/s?k=a"', 'open -a "Brave Browser" "https://resultados.tse.jus.br/"',
                         'curl "https://api.example.com/x"']}]
        with patch.object(delphi, 'read_rows', return_value=rows):
            sites = delphi.jev_sites()
        self.assertIn('amazon.com.br', sites); self.assertIn('resultados.tse.jus.br', sites); self.assertNotIn('api.example.com', sites)
        self.assertEqual(sites['amazon.com'], 'Amazon')

    def test_a_reworded_or_misheard_saved_task_replays_it(self):
        learned = {'ligue o sidecar com meu ipad': {'cmds': ['x'], 'reply': 'On.', 'at': '2026-10-28'},
                   'pesquisar {q} na amazon': {'cmds': ['x'], 'reply': '', 'slot': 'plus'}}   # needs a value: never a Jev pick
        reply = answers('other', 'none')
        reply['answers']['shortcut'] = {'type': 'choice', 'choice': 'ligue o sidecar com meu ipad', 'confidence': .93}
        with patch.object(delphi, 'skills', return_value=learned), patch.object(delphi, 'run_shortcut', return_value='Sidecar is on.') as run:
            result, fast, sent = self.ask('ligar sicore com meu ipad', reply)
        self.assertEqual(result, 'Sidecar is on.')
        run.assert_called_once_with('ligue o sidecar com meu ipad'); fast.assert_not_called()
        self.assertTrue(delphi.jev.hit and delphi.jev.known)   # already learned: main saves no second copy
        self.assertEqual(set(json.loads(sent[0][0].data)['questions']['shortcut']['criteria']), {'ligue o sidecar com meu ipad', 'none'})
        reply['answers']['shortcut']['confidence'] = .7
        with patch.object(delphi, 'skills', return_value=learned), patch.object(delphi, 'run_shortcut') as run:
            result, _, _ = self.ask('ligar sicore com meu ipad', reply)
        self.assertIsNone(result); run.assert_not_called()

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
