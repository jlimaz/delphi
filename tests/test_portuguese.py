"""Portuguese instant commands, media and volume: no AI, no real Mac actions."""
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import delphi
from tests import scratch_dir


class PortugueseTests(unittest.TestCase):
    def setUp(self):
        self.root = scratch_dir(self)
        for p in (patch.object(delphi, 'skills', return_value={}), patch.object(delphi, 'fast_hands', return_value=None),
                  patch.object(delphi, 'free_focus'), patch.object(delphi, 'LAST', str(self.root / 'last_app'))):
            p.start(); self.addCleanup(p.stop)

    def test_real_asks_from_the_log_become_english_commands(self):
        for said, english in [('abrir spotify', 'open spotify'), ('abre o vscode', 'open vscode'), ('abra amazon pra mim por favor', 'open amazon'),
                              ('abre o meu e-mail no brave por favor', 'open e-mail no brave'), ('fecha o spotify', 'close spotify'),
                              ('play no spotify', 'play'), ('pausa a música', 'pause'), ('próxima música', 'next'),
                              ('aumenta o volume em dois pontinhos por favor', 'turn volume up by 2'), ('abaixa o volume', 'turn volume down by 1'),
                              ('pesquisar quarters zip na amazon', 'search amazon for quarters zip'), ('pesquisa receita de bolo', 'search for receita de bolo'),
                              ('coloca o chrome na esquerda', 'put chrome left'), ('joga o brave pro monitor', 'put brave monitor'),
                              ('toca a playlist de estudo', 'play estudo'), ('não', 'no'), ('valeu', 'thanks'), ('muta', 'mute'),
                              ('lembra como mandar mensagem pra letícia', 'remember how to mandar mensagem pra letícia')]:
            self.assertEqual(delphi.english(said), english, said)

    def test_second_steps_pointing_words_and_questions_stay_with_the_ai(self):
        for said in ('abre a amazon e pesquisa pra mim sei lá livros', 'fecha isso', 'fecha aqui',
                     'pesquisa livros e abre o primeiro', 'me mostra na tela onde está a resposta final', 'baixe um pouquinho',
                     'como está a apuração das eleições no brasil', 'oi', 'mande um boa tarde para letícia pelo whatsapp'):
            self.assertEqual(delphi.english(said), said, said)

    def test_open_and_close_answer_in_portuguese(self):
        ok = subprocess.CompletedProcess([], 0)
        with patch.object(delphi, 'app_named', side_effect=lambda n: 'Visual Studio Code' if n == 'vscode' else None), \
             patch.object(delphi, 'app_heard', return_value=None), patch.object(delphi.subprocess, 'run', return_value=ok) as run:
            self.assertEqual(delphi.fast('Abre o VSCode.'), 'Abri Visual Studio Code.')
            self.assertEqual(run.call_args.args[0], ['open', '-a', 'Visual Studio Code'])
            self.assertIsNone(delphi.fast('Abre o Viascode.'))   # unknown app: the AI still finds it
        with patch.object(delphi, 'app_named', return_value='Spotify'), patch.object(delphi, 'app_id', return_value='com.spotify.client'), \
             patch.object(delphi, 'quit_app', return_value=True):
            self.assertEqual(delphi.fast('Fecha o Spotify.'), 'Fechei Spotify.')
        self.assertEqual(delphi.fast('Não.'), 'Ok.')

    def test_learned_portuguese_shortcuts_still_win(self):
        with patch.object(delphi, 'skills', return_value={'abrir spotify': {'cmds': ['open -a Spotify'], 'reply': 'Abri.'}}), \
             patch.object(delphi, 'run_shortcut', return_value='Abri.') as replayed:
            self.assertEqual(delphi.fast('Abrir Spotify.'), 'Abri.')
        self.assertEqual(replayed.call_args.args[0], 'abrir spotify')

    def test_media_checks_the_player_state(self):
        states = iter(['paused', 'playing'])
        def osa(script, *args, timeout=60):
            if 'player state' in script: return next(states)
            if 'name of current track' in script: return 'Boombap'
            return ''
        with patch.object(delphi, 'app_running', side_effect=lambda bid: bid == 'com.spotify.client'), patch.object(delphi, 'front', return_value=('Brave', '')), \
             patch.object(delphi, 'osa', side_effect=osa) as calls, patch.object(delphi.time, 'sleep'):
            self.assertEqual(delphi.fast('Play no Spotify.'), 'Tocando Boombap no Spotify.')
        self.assertIn('tell application id "com.spotify.client" to play', [c.args[0] for c in calls.call_args_list])
        with patch.object(delphi, 'app_running', side_effect=lambda bid: bid == 'com.spotify.client'), patch.object(delphi, 'front', return_value=('Brave', '')), \
             patch.object(delphi, 'osa', return_value='playing'), patch.object(delphi.time, 'sleep'):
            self.assertEqual(delphi.fast('Paus the music.'), 'Could not pause Spotify. Check its Automation permission and try again.')
        with patch.object(delphi, 'app_running', return_value=False):
            self.assertIsNone(delphi.fast('pause'))   # nothing playing: the AI works out what was meant

    def test_volume_steps_and_reads_back(self):
        with patch.object(delphi, 'osa', side_effect=lambda script, *a, **k: '62' if script.startswith('output volume') else '') as calls:
            self.assertEqual(delphi.fast('Aumenta o volume em dois pontinhos por favor.'), 'Volume em 62%.')
            self.assertIn('+ (12)', calls.call_args_list[0].args[0])
            self.assertEqual(delphi.fast('turn the volume down'), 'Volume 62%.')
            self.assertIn('+ (-6)', calls.call_args_list[2].args[0])
        with patch.object(delphi, 'osa', return_value='missing value'):
            self.assertIsNone(delphi.fast('volume up'))

    def test_messaging_rule_fits_the_prompt_budget(self):
        self.assertIn('whatsapp://send?phone=', delphi.SYSTEM)
        full = delphi.SYSTEM + delphi.ASK_ME + delphi.POINTER + delphi.LEARN_ME + delphi.ASK_FIRST + delphi.WORKFLOW
        self.assertLessEqual(len(full), 10000)


if __name__ == '__main__':
    unittest.main()
