#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 puppi3-music
# SPDX-License-Identifier: AGPL-3.0-or-later
r"""
play_intro.py -- play the startup intro on the pads without Live.

It runs MVave_SMC_PAD/StartupIntro.py's own frame(), so what you see is what
Live will show, and settings can be tried from the command line before they
go into MIDI_Map.py:

  play_intro.py                          the flag, as MIDI_Map.py has it
  play_intro.py --style rainbow          the rainbow
  play_intro.py --flag 62,57,40,57,62    other stripe colours, bottom to top
  play_intro.py --wave 20                a slower wave (ticks per ripple)
  play_intro.py --loops 5                play it 5 times (default 3)
  play_intro.py --stripes                each flag colour on all 16 pads, 3 s each
  play_intro.py --still 12               hold one tick of the show for 10 s

The grid only shows on preset 1, bank A, so it first asks the controller
which layout is up and switches it there if not (--no-switch skips that).

On macOS, quit Live first or its clip colours may paint over the show. On
Windows, MIDI ports are exclusive: Live must be closed. Needs mido and
python-rtmidi, as the probe does (docs/PROBE.md, Setup):

  macOS:    ./venv-midi/bin/python tools/play_intro.py
  Windows:  tools\venv-midi\Scripts\python tools\play_intro.py
            (run_probe.bat makes that virtualenv on its first run)
"""

import argparse
import importlib
import os
import sys
import time
import types

try:
    import mido
except ImportError:                                 # pragma: no cover
    sys.exit("mido is not installed.\n"
             "Run this with the probe's virtualenv (docs/PROBE.md, Setup).")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load StartupIntro.py and MIDI_Map.py without the package's __init__, which
# needs Live.
_package = types.ModuleType('mvave_intro')
_package.__path__ = [os.path.join(ROOT, 'MVave_SMC_PAD')]
sys.modules['mvave_intro'] = _package
intro = importlib.import_module('mvave_intro.StartupIntro')

# Ports, macOS name first, then Windows (INSTALL.md).
PADS_PORTS = ('SINCO Port 3', 'MIDIOUT3 (SMC-PAD)')
STATE_PORTS = ('SINCO SMC-PAD-Private', 'SMC-PAD')

# The device drops the tail of a burst sent too fast (mvave_probe.py,
# SEND_GAP): 2 ms between messages.
SEND_GAP = 0.002
TICK = 0.1                  # Live's display tick, as the intro counts them


# The state read and write, as MVave_SMC_KNOBS.py sends them (its module needs
# Live, so they are repeated here). HARDWARE.md has the wire format.
STATE_PRESET_ADDRESS, STATE_BANK_ADDRESS = 0x0A, 0x0B
STATUS_PRESET, STATUS_BANK = 24, 25


def pack7(data):
    out, acc, bits = [], 0, 0
    for byte in data:
        acc |= byte << bits
        bits += 8
        while bits >= 7:
            out.append(acc & 0x7F)
            acc >>= 7
            bits -= 7
    if bits:
        out.append(acc & 0x7F)
    return out


def unpack7(data):
    out, acc, bits = [], 0, 0
    for byte in data:
        acc |= (byte & 0x7F) << bits
        bits += 7
        while bits >= 8:
            out.append(acc & 0xFF)
            acc >>= 8
            bits -= 8
    return out


def packet(command, payload):
    """A sysex message's data (mido adds F0 and F7)."""
    data = [0x00, 0x59, command, len(payload), 0x00, 0x00] + list(payload)
    data.append(~sum(payload) & 0xFF)
    return pack7(data)


def find_port(names, wanted, kind):
    """The first of `wanted` that is a port; a Windows name ends in an index,
    so a name or the name plus ' <n>' counts."""
    for want in wanted:
        for name in names:
            if name == want or (name.startswith(want + ' ')
                                and name[len(want) + 1:].isdigit()):
                return name
    sys.exit("Can't find the SMC-PAD's %s port (%s). Is it plugged in? Ports:\n  %s"
             % (kind, ' or '.join(wanted), '\n  '.join(names) or '(none)'))


def ask_layout(inp, out):
    """(preset, bank) counted from 0, or None if the controller didn't answer."""
    for _ in inp.iter_pending():
        pass
    out.send(mido.Message('sysex', data=packet(
        0x23, [0x04, 0x00, 0x00, 0x00, 0x00, 0x0C, 0x00, 0x00])))
    end = time.time() + 1.0
    while time.time() < end:
        for message in inp.iter_pending():
            if message.type == 'sysex' and len(message.data) == 31:
                data = unpack7(message.data)
                return data[STATUS_PRESET], data[STATUS_BANK]
        time.sleep(0.005)
    return None


def to_preset_1():
    names = mido.get_output_names()
    name = find_port(names, STATE_PORTS, 'state')
    in_name = find_port(mido.get_input_names(), STATE_PORTS, 'state')
    with mido.open_input(in_name) as inp, mido.open_output(name) as out:
        layout = ask_layout(inp, out)
        if layout is None:
            print("The controller didn't say which preset is up; trying anyway. "
                  "If the pads stay dark, press Shift + PAD1.")
            return
        if layout == (0, 0):
            return
        print("Switching from preset %d, bank %s to preset 1, bank A."
              % (layout[0] + 1, 'AB'[layout[1]] if layout[1] < 2 else layout[1]))
        for address in (STATE_PRESET_ADDRESS, STATE_BANK_ADDRESS):
            out.send(mido.Message('sysex', data=packet(
                0x22, [0x04, address, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0])))
            time.sleep(0.2)
        if ask_layout(inp, out) != (0, 0):
            print("It didn't switch. Press Shift + PAD1, then run this again.")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--style', choices=('flag', 'rainbow'),
                        default=intro.INTRO_STYLE)
    parser.add_argument('--flag', metavar='C,C,C,C,C',
                        help='flag stripe colours, bottom to top (palette 1-63)')
    parser.add_argument('--wave', type=int, metavar='TICKS',
                        help='ticks per ripple (default %d)' % intro.INTRO_WAVE_TICKS)
    parser.add_argument('--loops', type=int, default=3)
    parser.add_argument('--stripes', action='store_true',
                        help='each flag colour on all 16 pads, 3 s each')
    parser.add_argument('--still', type=int, metavar='TICK',
                        help='hold this tick of the show for 10 s')
    parser.add_argument('--no-switch', action='store_true',
                        help="don't switch the controller to preset 1, bank A")
    args = parser.parse_args()

    intro.INTRO_STYLE = args.style
    if args.flag:
        try:
            intro.INTRO_FLAG = tuple(int(c) for c in args.flag.split(','))
        except ValueError:
            parser.error('--flag takes palette numbers separated by commas')
        if not intro.INTRO_FLAG or not all(0 < c < 128 for c in intro.INTRO_FLAG):
            parser.error('--flag colours are 1-127')
    if args.wave:
        intro.INTRO_WAVE_TICKS = args.wave

    if not args.no_switch:
        to_preset_1()

    out = mido.open_output(find_port(mido.get_output_names(), PADS_PORTS, 'pad'))
    pads = intro.grid_leds()

    def show(leds):
        for led, colour in sorted(leds.items()):
            out.send(mido.Message('note_on', channel=intro.BUTTONCHANNEL,
                                  note=led, velocity=colour))
            time.sleep(SEND_GAP)

    try:
        if args.stripes:
            for colour in sorted(set(intro.INTRO_FLAG), key=intro.INTRO_FLAG.index):
                print('All pads: %d' % colour)
                show({led: colour for led, _, _ in pads})
                time.sleep(3)
        elif args.still is not None:
            show(intro.frame(args.still, pads))
            time.sleep(10)
        else:
            print('Playing the %s %d time(s).' % (args.style, args.loops))
            for _ in range(args.loops):
                for step in range(intro.INTRO_SHOW_TICKS + intro.INTRO_FLASH_TICKS):
                    started = time.time()
                    show(intro.frame(step, pads))
                    time.sleep(max(0, TICK - (time.time() - started)))
    except KeyboardInterrupt:
        pass
    finally:
        show({led: 0 for led, _, _ in pads})
        out.close()


if __name__ == '__main__':
    main()
