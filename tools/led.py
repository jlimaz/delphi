#!/usr/bin/env python3
"""Bluetooth LED strip control for Delphi (Happy Lighting / Triones strips, and ELK-BLEDOM look-alikes).

  led.py scan [--all]                  list nearby named BLE devices (name, identifier, protocol guess); --all: unnamed too
  led.py on | off
  led.py color <name | R G B | #RRGGBB>   e.g. color purple, color warm white, color 255 0 128
  led.py brightness <0-100>            rescales the last color
  led.py mode <name> [speed 1-100]     built-in effects; 100 = fastest. led.py mode --list
Exit 0 with a one-line confirmation on success; a one-line error and exit 1 otherwise (2: bad arguments).

On macOS, bleak identifies devices by CoreBluetooth UUID, not MAC address. The strip found first is cached
with its protocol and last color in ~/.config/delphi/led.json; a stale cache falls back to a fresh scan.
Other devices (a TV, ...) can follow the same pattern: one script per device in tools/.
"""
import asyncio
import json
import os
import sys

STATE = os.path.join(os.environ.get('DELPHI_DIR') or os.path.expanduser('~/.config/delphi'), 'led.json')
VENV_PYTHON = os.path.join(os.environ.get('DELPHI_DIR') or os.path.expanduser('~/.config/delphi'), 'tools-venv/bin/python')
SCAN_SECONDS, FIND_SECONDS, CONNECT_SECONDS = 5.0, 4.0, 8.0

PROTOCOLS = {
    # write characteristic, name prefixes, advertised service UUID prefixes (for strips that hide their name)
    'triones': ('0000ffd9-0000-1000-8000-00805f9b34fb', ('QHM', 'TRIONES', 'LEDBLE', 'BRGLIGHT', 'DREAM'), ('0000ffd5', '0000ffd0')),
    'elk': ('0000fff3-0000-1000-8000-00805f9b34fb', ('ELK',), ('0000fff0',)),
}

COLORS = {
    'red': (255, 0, 0), 'green': (0, 255, 0), 'blue': (0, 0, 255), 'white': (255, 255, 255),
    'warm white': (255, 160, 60), 'cool white': (200, 220, 255), 'soft white': (255, 200, 140),
    'yellow': (255, 200, 0), 'orange': (255, 90, 0), 'amber': (255, 120, 0), 'gold': (255, 170, 0),
    'purple': (128, 0, 255), 'violet': (150, 0, 255), 'magenta': (255, 0, 255), 'pink': (255, 40, 120),
    'hot pink': (255, 0, 90), 'cyan': (0, 255, 255), 'teal': (0, 160, 140), 'turquoise': (0, 230, 180),
    'lime': (120, 255, 0), 'indigo': (60, 0, 255), 'lavender': (170, 110, 255), 'coral': (255, 70, 40),
    'crimson': (220, 0, 30), 'sky blue': (60, 160, 255), 'mint': (60, 255, 140),
}

# Triones built-in effects (0x25-0x38)
MODES = {
    'fade': 0x25, 'red fade': 0x26, 'green fade': 0x27, 'blue fade': 0x28, 'yellow fade': 0x29, 'cyan fade': 0x2A,
    'purple fade': 0x2B, 'white fade': 0x2C, 'red green fade': 0x2D, 'red blue fade': 0x2E, 'green blue fade': 0x2F,
    'strobe': 0x30, 'red strobe': 0x31, 'green strobe': 0x32, 'blue strobe': 0x33, 'yellow strobe': 0x34,
    'cyan strobe': 0x35, 'purple strobe': 0x36, 'white strobe': 0x37, 'jump': 0x38,
}


class Fail(Exception):
    """A one-line error for the user."""


# ---- packets (pure, no Bluetooth) ----

def detect_protocol(name, service_uuids=()):
    """'triones', 'elk', or None, from the advertised name (or service UUIDs when the name is missing)."""
    upper = (name or '').strip().upper()
    for protocol, (_, prefixes, services) in PROTOCOLS.items():
        if upper.startswith(prefixes): return protocol
    for protocol, (_, _, services) in PROTOCOLS.items():
        if any(str(u).lower().startswith(services) for u in service_uuids or ()): return protocol
    return None


def scale(rgb, brightness):
    return tuple(round(c * max(0, min(100, brightness)) / 100) for c in rgb)


def power_packet(protocol, on):
    if protocol == 'elk':
        return bytes([0x7E, 0x00, 0x04, 0xF0 if on else 0x00, 0x00, 0x01 if on else 0x00, 0xFF, 0x00, 0xEF])
    return bytes([0xCC, 0x23 if on else 0x24, 0x33])


def color_packets(protocol, rgb, brightness):
    """Triones has no brightness command, so the color is scaled; ELK has one, so the color is sent as is."""
    if protocol == 'elk':
        r, g, b = rgb
        return [bytes([0x7E, 0x00, 0x05, 0x03, r, g, b, 0x00, 0xEF]),
                bytes([0x7E, 0x00, 0x01, max(0, min(100, brightness)), 0x00, 0x00, 0x00, 0x00, 0xEF])]
    r, g, b = scale(rgb, brightness)
    return [bytes([0x56, r, g, b, 0x00, 0xF0, 0xAA])]


def mode_packet(protocol, mode, speed):
    """speed 1-100 (100 = fastest) -> the Triones delay byte 31..1 (lower = faster)."""
    if protocol != 'triones':
        raise Fail('Built-in modes are only supported on Triones (Happy Lighting) strips so far.')
    speed = max(1, min(100, speed))
    delay = round(1 + (100 - speed) * 30 / 99)
    return bytes([0xBB, MODES[mode], delay, 0x44])


def parse_color(words):
    """'purple' | 'warm white' | '255 0 128' | '#ff0080' -> (r, g, b), else Fail."""
    text = ' '.join(words).strip().lower().replace('-', ' ').replace('_', ' ')
    if text in COLORS: return COLORS[text]
    if text.startswith('#') and len(text) == 7:
        try: return tuple(int(text[i:i + 2], 16) for i in (1, 3, 5))
        except ValueError: pass
    parts = text.replace(',', ' ').split()
    if len(parts) == 3 and all(p.isdigit() for p in parts) and all(0 <= int(p) <= 255 for p in parts):
        return tuple(int(p) for p in parts)
    raise Fail(f'Unknown color "{" ".join(words)}". Use R G B (0-255), #RRGGBB, or one of: {", ".join(sorted(COLORS))}.')


def describe(rgb):
    name = next((n for n, v in COLORS.items() if v == tuple(rgb)), None)
    return f'{name} ({rgb[0]}, {rgb[1]}, {rgb[2]})' if name else f'({rgb[0]}, {rgb[1]}, {rgb[2]})'


# ---- state ----

def load():
    try:
        with open(STATE) as f: state = json.load(f)
        return state if isinstance(state, dict) else {}
    except (OSError, ValueError):
        return {}


def save(state):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    tmp = STATE + '.tmp'
    with open(tmp, 'w') as f: json.dump(state, f, indent=1)
    os.replace(tmp, STATE)


# ---- Bluetooth ----

def bluetooth_error(e):
    """bleak/CoreBluetooth errors -> a one-line Fail."""
    text = str(e)
    low = text.lower()
    if 'not authorized' in low or 'unauthorized' in low or 'permission' in low:
        return Fail('Bluetooth permission denied: allow Delphi (or your terminal) in System Settings > Privacy & Security > Bluetooth.')
    if 'turned off' in low or 'powered off' in low:
        return Fail('Bluetooth is turned off on this Mac.')
    if 'unsupported' in low:
        return Fail('This Mac does not support Bluetooth LE.')
    return Fail(f'Bluetooth error: {text or type(e).__name__}')


async def discover(seconds=SCAN_SECONDS):
    """-> [(device, advertisement)] for everything nearby."""
    from bleak import BleakScanner
    from bleak.exc import BleakError
    try:
        found = await BleakScanner.discover(timeout=seconds, return_adv=True)
    except BleakError as e:
        raise bluetooth_error(e)
    return list(found.values())


async def find_strip(state):
    """The cached strip if it is advertising, else a fresh scan. Caches what it finds."""
    from bleak import BleakScanner
    from bleak.exc import BleakError
    if state.get('address'):
        try:
            device = await BleakScanner.find_device_by_address(state['address'], timeout=FIND_SECONDS)
        except BleakError as e:
            raise bluetooth_error(e)
        if device: return device, state['protocol']
    strips = sorted(((d, a, detect_protocol(d.name or a.local_name, a.service_uuids)) for d, a in await discover()),
                    key=lambda x: -(x[1].rssi or -999))
    strips = [s for s in strips if s[2]]
    if not strips:
        raise Fail('LED strip not found. Is it powered, and is the Happy Lighting app closed on your phone? (The strip takes one connection at a time.)')
    device, adv, protocol = strips[0]
    state.update(address=device.address, name=device.name or adv.local_name or '', protocol=protocol)
    save(state)
    return device, protocol


async def send(state, packets):
    from bleak import BleakClient
    from bleak.exc import BleakError
    device, protocol = await find_strip(state)
    packets = packets(protocol) if callable(packets) else packets
    try:
        async with BleakClient(device, timeout=CONNECT_SECONDS) as client:
            for p in packets:
                await client.write_gatt_char(PROTOCOLS[protocol][0], p, response=False)
                await asyncio.sleep(0.05)
    except (BleakError, asyncio.TimeoutError, TimeoutError, EOFError) as e:
        if isinstance(e, BleakError) and ('not authorized' in str(e).lower() or 'turned off' in str(e).lower()):
            raise bluetooth_error(e)
        if isinstance(e, BleakError) and 'characteristic' in str(e).lower():
            raise Fail(f'{state.get("name") or "The strip"} does not have the expected {protocol} write characteristic; it may use another protocol.')
        raise Fail('Could not connect to the LED strip (connection refused). Close the Happy Lighting app on your phone; the strip allows one connection.')
    return protocol


# ---- commands ----

async def run(args):
    state = load()
    if not args or args[0] in ('-h', '--help', 'help'):
        print(__doc__.strip()); return
    cmd, rest = args[0].lower(), args[1:]
    rgb = tuple(state.get('color') or (255, 255, 255))
    level = state.get('brightness', 100)

    if cmd == 'scan':
        rows = sorted(await discover(), key=lambda x: -(x[1].rssi or -999))
        if not rows: print('No Bluetooth LE devices found.'); return
        shown = rows if rest[:1] == ['--all'] else [(d, a) for d, a in rows if d.name or a.local_name or detect_protocol(None, a.service_uuids)]
        for d, a in shown:
            protocol = detect_protocol(d.name or a.local_name, a.service_uuids)
            print(f'{(d.name or a.local_name or "(no name)"):<24} {d.address}  rssi {a.rssi:>4}  {protocol or "-"}')
        if len(shown) < len(rows): print(f'(+{len(rows) - len(shown)} unnamed devices hidden; led.py scan --all lists them)')
        strips = [(d, a) for d, a in rows if detect_protocol(d.name or a.local_name, a.service_uuids)]
        if strips:
            d, a = strips[0]
            state.update(address=d.address, name=d.name or a.local_name or '', protocol=detect_protocol(d.name or a.local_name, a.service_uuids))
            save(state)
            print(f'Using {state["name"] or d.address} ({state["protocol"]}); saved to {STATE}.')
        else:
            print('No LED strip recognized among these.')
        return
    if cmd in ('on', 'off'):
        if rest: raise Fail(f'Usage: led.py {cmd}')
        await send(state, lambda p: [power_packet(p, cmd == 'on')])
        state['power'] = cmd; save(state)
        print(f'Lights {cmd}.'); return
    if cmd in ('color', 'colour'):
        if not rest: raise Fail('Usage: led.py color <name | R G B | #RRGGBB>')
        rgb = parse_color(rest)
        await send(state, lambda p: [power_packet(p, True), *color_packets(p, rgb, level)])
        state.update(color=list(rgb), power='on', mode=None); save(state)
        print(f'Lights set to {describe(rgb)}' + (f' at {level}% brightness.' if level != 100 else '.')); return
    if cmd == 'brightness':
        if len(rest) != 1 or not rest[0].rstrip('%').isdigit() or not 0 <= int(rest[0].rstrip('%')) <= 100:
            raise Fail('Usage: led.py brightness <0-100>')
        level = int(rest[0].rstrip('%'))
        await send(state, lambda p: [power_packet(p, True), *color_packets(p, rgb, level)])
        state.update(brightness=level, power='on', mode=None); save(state)
        print(f'Brightness {level}% ({describe(rgb)}).'); return
    if cmd == 'mode':
        if rest[:1] == ['--list']: print('Modes: ' + ', '.join(MODES)); return
        speed = 50
        if rest and rest[-1].isdigit(): speed = int(rest.pop())
        mode = ' '.join(rest).lower().replace('-', ' ')
        if mode not in MODES: raise Fail(f'Unknown mode "{mode}". Modes: {", ".join(MODES)}.')
        await send(state, lambda p: [power_packet(p, True), mode_packet(p, mode, speed)])
        state.update(mode=mode, power='on'); save(state)
        print(f'Mode {mode} at speed {max(1, min(100, speed))}.'); return
    raise Fail(f'Unknown command "{cmd}". Use: scan, on, off, color, brightness, mode.')


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    needs_bleak = bool(args) and args[0].lower() in ('scan', 'on', 'off', 'color', 'colour', 'brightness', 'mode') and args[1:2] != ['--list']
    if needs_bleak:
        try:
            import bleak  # noqa: F401
        except ImportError:
            if os.path.exists(VENV_PYTHON) and os.path.realpath(sys.executable) != os.path.realpath(VENV_PYTHON) and not os.environ.get('DELPHI_LED_REEXEC'):
                os.environ['DELPHI_LED_REEXEC'] = '1'
                os.execv(VENV_PYTHON, [VENV_PYTHON, os.path.abspath(__file__), *args])
            print(f'The bleak package is missing. Run ./build.sh (it installs it into {os.path.dirname(os.path.dirname(VENV_PYTHON))}).', file=sys.stderr)
            return 1
    try:
        asyncio.run(asyncio.wait_for(run(args), timeout=30))
    except Fail as e:
        print(e, file=sys.stderr)
        return 2 if str(e).startswith(('Usage:', 'Unknown')) else 1
    except (asyncio.TimeoutError, TimeoutError):
        print('Timed out talking to the LED strip.', file=sys.stderr); return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == '__main__':
    sys.exit(main())
