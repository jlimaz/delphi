"""Sidecar and volume levels as instant commands: no Control Center clicks, no AI, no real Mac actions."""
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import delphi
from tests import scratch_dir


def helper(out, code=0):
    return patch.object(delphi.subprocess, 'run', return_value=subprocess.CompletedProcess([], code, out + '\n', ''))


class SidecarTests(unittest.TestCase):
    def setUp(self):
        self.root = scratch_dir(self)
        for p in (patch.object(delphi, 'skills', return_value={}), patch.object(delphi, 'fast_hands', return_value=None),
                  patch.object(delphi, 'free_focus'), patch.object(delphi, 'LAST', str(self.root / 'last_app'))):
            p.start(); self.addCleanup(p.stop)

    def test_ways_to_say_it_in_english_and_portuguese(self):
        for said, want in [('turn on sidecar', ('on', '')), ('turn sidecar on', ('on', '')), ('turn on sidecar with my ipad', ('on', 'ipad')),
                           ('sidecar off', ('off', '')), ('turn off the sidecar', ('off', '')), ('connect sidecar to my ipad', ('on', 'ipad')),
                           ('ligue o sidecar com meu ipad', ('on', 'ipad')), ('liga o sidecar', ('on', '')), ('desliga o sidecar', ('off', '')),
                           ('turn on sidecar with my ipad and open notes', None), ('open safari', None)]:
            t = delphi.plain(said)
            self.assertEqual(delphi.sidecar_words(t) or delphi.sidecar_words(delphi.english(t)), want, said)

    def test_calls_the_helper_and_learns_the_direct_command(self):
        with helper('Sidecar is on with iPad.') as run:
            self.assertEqual(delphi.fast('Turn on Sidecar with my iPad.'), 'Sidecar is on with iPad.')
        self.assertEqual(run.call_args.args[0], [delphi.APP, '--sidecar', 'on', 'ipad'])
        self.assertEqual(delphi.fast.cmds, [f'{delphi.ME} --sidecar on ipad'])
        with helper('Sidecar is off.'):
            self.assertEqual(delphi.fast('desliga o sidecar'), 'Desliguei o Sidecar.')

    def test_a_learned_click_recording_never_replays_over_it(self):
        clicks = {'ligue o sidecar com meu ipad': {'cmds': [f'{delphi.ME} --hands click "Control Center"'], 'reply': 'Sidecar is on.'}}
        with patch.object(delphi, 'skills', return_value=clicks), patch.object(delphi, 'replay') as replay, helper('Sidecar is on with iPad.'):
            self.assertEqual(delphi.fast('ligue o sidecar com meu ipad'), 'Liguei o Sidecar com o iPad.')
        replay.assert_not_called()

    def test_failures_are_said_and_a_missing_api_goes_to_the_ai(self):
        with helper('No iPad is available for Sidecar. Check that it is nearby, unlocked and signed in to the same Apple Account.', 1):
            self.assertTrue(delphi.fast('turn on sidecar').startswith('No iPad is available'))
        self.assertEqual(delphi.fast.cmds, [])
        with helper('Sidecar is not available on this Mac.', 3):
            self.assertIsNone(delphi.fast('turn on sidecar'))

    def test_volume_to_a_level(self):
        for said, level in [('set volume to 30', 30), ('set the volume to 30%', 30), ('volume to max', 100), ('max volume', 100),
                            ('bota o volume na metade', 50), ('aumenta o volume no máximo', 100), ('bota o volume no mínimo', 0),
                            ('volume no 30', 30), ('baixa o volume pra 20', 20)]:
            with self.subTest(said=said), patch.object(delphi, 'osa', side_effect=lambda s, *a, **k: str(level) if s.startswith('output volume') else '') as osa:
                self.assertRegex(delphi.fast(said), rf'^Volume (em )?{level}%\.$')
                self.assertTrue(osa.call_args_list[0].args[0].startswith(f'set volume output volume {level}'))
        with patch.object(delphi, 'osa') as osa:
            self.assertIsNone(delphi.fast('set volume to 300'))
        osa.assert_not_called()
        self.assertEqual(delphi.english('aumenta o volume'), 'turn volume up by 1')   # steps still mean steps


if __name__ == '__main__':
    unittest.main()
