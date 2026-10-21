#!/usr/bin/env python3
"""Build the mixer, drum and keyboard presets from the working source presets.

    python3 tools/make_presets.py

Reads two sources from reference/ and writes four files to presets/:

  preset1-launcher-mixer.spc    preset 1: PAD BANK flips clips <-> mixer
  preset2-sequencer-drums.spc   preset 2: PAD BANK flips steps <-> drum pads
  preset3-keys.spc              preset 3: keyboard + device knobs, PAD BANK -> key/scale
  preset4-chords.spc            preset 4: chords + device knobs, PAD BANK -> key/scale

Presets 1 and 3 start from smc-pad-launcher-led33.spc, so buttons are the
launcher's (transport, track select) and MVave_SMC_PAD keeps working on
preset 3 without a second script; it also plays preset 3's lit keyboard
(KEYS_NOTES) and reads its key/scale bank (SETTINGS_NOTES). Preset 3's encoders are rewritten to send
CCs 21-36 (PARAM_CCS_BANK_*), which MVave_SMC_KNOBS plays onto the selected
device's parameter banks, instead of the launcher's macro CCs. Preset 4 is
built the same way as preset 3, on its own notes and LEDs (CHORDS_NOTES and
CHORDS_SETTINGS_NOTES), with the same knobs. Preset 2
starts from smc-pad-sequencer-led69.spc and only its bank B changes, so the
sequencer's buttons and encoders stay put while the pads play drums. Its
buttons also get LED numbers (see light_buttons), so the sequencer can light
Stop in the overview and the arrows when there is a page to go to.

Where the records are, measured on this unit rather than taken from
docs/HARDWARE.md 5.2 (which assumes 8 banks at records 16k):

  * PAD BANK has TWO positions, not eight: bank A is records 32-47 (MCP type,
    port 3, lit by the host) and bank B is records 48-63 (factory: notes
    52-67 on channel 10, ports 1 and 2, velocity-sensitive). Records 112-127
    hold the same 52-67 and nothing distinguishes the two from one
    measurement, so bank B is written to both.
  * 2026-10-08: bank A is 32-47, the same place M-Vave's own export
    (reference/launchpad.spc) keeps it. An earlier reading put
    it at 29-44; presets built that way played every pad's neighbour three
    along (bottom-left sent 16, not 13) once imported, with the last three
    pads stuck white. The old sources are no longer kept.
  * PAD n is the device's numbering: PAD1 bottom-left, PAD13 top-left.
  * Pad record: [flag] [type] [note] [00] [vel] [r] [g] [b] [led] [zeros].
    flag 0x04 = MCP (port 3, lit, always 127); 0x00 = plain MIDI (ports 1/2,
    velocity-sensitive, unlit). Byte 8 is the LED number the host lights,
    0xff on plain records. LED == own note leaves the pad stuck white at
    velocity 0, which is why every lit pad here has its LED moved off its note.
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE_DIR = os.path.join(HERE, '..', 'reference')
OUT_DIR = os.path.join(HERE, '..', 'presets')
LAUNCHER = 'smc-pad-launcher-led33.spc'
SEQUENCER = 'smc-pad-sequencer-led69.spc'

ENCODER_SECTION = 115
ENCODER_RECORD = 6
PAD_SECTION = 211
RECORD = 26
FILE_SIZE = 3539

BANK_A = [32]           # first record of PAD1, bank A
BANK_B = [48, 112]      # first record of PAD1, bank B (see docstring)

# Mixer: must match TRACKMUTE/TRACKSOLO/TRACKREC/TRACKSTOP and
# MIXER_LED_OFFSET in MVave_SMC_PAD/MIDI_Map.py. Notes 49-64 in reading
# order, top-left first; LEDs 85-100 stay clear of the clip grid (33-48) and
# the sequencer (69-84, 101-116).
MIXER_TOP_LEFT = 49
MIXER_LED_OFFSET = 36

# Drums: Live's Drum Rack puts C1 (36) on its bottom-left pad and counts up
# left to right, bottom to top -- the same order as the device's PAD numbers.
DRUM_BOTTOM_LEFT = 36

# Keyboard: must match KEYS_NOTES/KEYS_LED_OFFSET and SETTINGS_NOTES/
# SETTINGS_LED_OFFSET in MVave_SMC_PAD/MIDI_Map.py. Both banks are lit MCP
# pads, PAD1 first; the script turns the keyboard's notes into scale notes.
KEYS_PAD1 = 85                  # notes 85-100, LEDs 1-16
KEYS_LED_OFFSET = -84
SETTINGS_PAD1 = 22              # notes 22-37, LEDs 49-64
SETTINGS_LED_OFFSET = 27

# Chords: must match CHORDS_NOTES/CHORDS_LEDS and CHORDS_SETTINGS_NOTES/
# CHORDS_SETTINGS_LEDS in MVave_SMC_PAD/MIDI_Map.py, PAD1 first. The last notes
# and LEDs free on port 3, so the settings page is in three runs.
CHORDS_NOTES = tuple(range(65, 81))
CHORDS_LEDS = tuple(range(101, 117))
CHORDS_SETTINGS_NOTES = tuple(range(38, 49)) + tuple(range(81, 85)) + (122,)
CHORDS_SETTINGS_LEDS = tuple(range(22, 33)) + tuple(range(65, 69)) + (123,)

# Preset 3's encoders: relative, like every other preset's, on their own CCs
# 21-36, which MVave_SMC_KNOBS turns into the selected device's parameter banks
# (PARAM_BY_CC there: CC 21 + slot, slots in panel reading order, top-left
# first). Keyed by the device's encoder number (1 = bottom-left, 7 = top-left,
# HARDWARE.md 4.2).
PARAM_CCS_BANK_1 = {
    7: 21, 8: 22,   # top row       -> Live's bank 1, parameters 1-2
    5: 23, 6: 24,
    3: 25, 4: 26,
    1: 27, 2: 28,   # bottom row    -> parameters 7-8
}
PARAM_CCS_BANK_2 = dict((encoder, cc + 8) for encoder, cc in PARAM_CCS_BANK_1.items())

MAGENTA = (0xf0, 0x00, 0xf0)    # what the shipped lit banks use
AMBER = (0xf0, 0x50, 0x00)


def mixer_note(pad):
    row_from_bottom, col = divmod(pad - 1, 4)
    return MIXER_TOP_LEFT + (3 - row_from_bottom) * 4 + col


def mcp_record(note, led, rgb=MAGENTA):
    return bytes([0x04, 0x09, note, 0x00, 0x7f]) + bytes(rgb) + bytes([led]) + bytes(RECORD - 9)


def plain_record(note, rgb=AMBER):
    return bytes([0x00, 0x09, note, 0x00, 0x7f]) + bytes(rgb) + bytes([0xff]) + bytes(RECORD - 9)


def relative_encoder(cc):
    # Encoder record: [type] [speed] [channel] [cc] [data1] [data2], read from
    # MidiSuite's SmcPad::setKnobData / knobTypeChange (2026-10-20). Type 3 is
    # relative, data1/data2 = the values sent per click left/right; 3f 41 is
    # the 63/65 every shipped record uses. (Type 0 would be absolute, with
    # data1/data2 = min/max.)
    return bytes([0x03, 0x02, 0x00, cc, 0x3f, 0x41])


def write_encoders(data, banks):
    # Record r of bank b is encoder r+1 (HARDWARE.md 5.2).
    for b, ccs in enumerate(banks):
        for encoder, cc in ccs.items():
            offset = ENCODER_SECTION + (b * 8 + encoder - 1) * ENCODER_RECORD
            data[offset:offset + ENCODER_RECORD] = relative_encoder(cc)


# The five button records at the top of the file, 23 bytes each:
#   [05] [00] [note] [00] [7f] [06] [f0 7f 7f 06 0n f7, padded] ... [tail]
# The tail is the button's LED number, by analogy with byte 8 of a pad record:
# Play and Record carry their own note there and Stop and the arrows carry
# 0xff, and only Stop and the arrows stayed dark when the sequencer lit them
# (2026-10-20). INFERRED, not measured -- see docs/HARDWARE.md 5.2.
BUTTON_SECTION = 0
BUTTON_RECORD = 23
BUTTON_TAIL = 22


def light_buttons(data):
    """Give every button an LED number: its own note, as Play and Record have."""
    for i in range(5):
        offset = BUTTON_SECTION + i * BUTTON_RECORD
        assert data[offset] == 0x05, 'button record %d: not a button' % i
        data[offset + BUTTON_TAIL] = data[offset + 2]


def write_bank(data, starts, record_for_pad):
    for start in starts:
        for pad in range(1, 17):
            offset = PAD_SECTION + (start + pad - 1) * RECORD
            data[offset:offset + RECORD] = record_for_pad(pad)


def mixer_pad(pad):
    note = mixer_note(pad)
    return mcp_record(note, note + MIXER_LED_OFFSET)


def drum_pad(pad):
    return plain_record(DRUM_BOTTOM_LEFT + pad - 1)


def key_pad(pad):
    note = KEYS_PAD1 + pad - 1
    return mcp_record(note, note + KEYS_LED_OFFSET)


def settings_pad(pad):
    note = SETTINGS_PAD1 + pad - 1
    return mcp_record(note, note + SETTINGS_LED_OFFSET)


def chord_pad(pad):
    return mcp_record(CHORDS_NOTES[pad - 1], CHORDS_LEDS[pad - 1])


def chord_settings_pad(pad):
    return mcp_record(CHORDS_SETTINGS_NOTES[pad - 1], CHORDS_SETTINGS_LEDS[pad - 1])


def check(data):
    # Only the two reachable banks.
    assert len(data) == FILE_SIZE
    for i in [s + p for s in BANK_A + BANK_B for p in range(16)]:
        r = data[PAD_SECTION + i * RECORD:PAD_SECTION + (i + 1) * RECORD]
        if r[0] == 0x04:
            assert r[8] != r[2], 'record %d: LED == note, pad would stick white' % i


def build(name, source, bank_a, bank_b, encoders=None, button_leds=False):
    data = bytearray(open(os.path.join(SOURCE_DIR, source), 'rb').read())
    if button_leds:
        light_buttons(data)
    if encoders is not None:
        write_encoders(data, encoders)
    if bank_a is not None:
        write_bank(data, BANK_A, bank_a)
    write_bank(data, BANK_B, bank_b)
    check(data)
    path = os.path.join(OUT_DIR, name)
    with open(path, 'wb') as f:
        f.write(data)
    print('wrote', os.path.normpath(path))


if __name__ == '__main__':
    build('preset1-launcher-mixer.spc', LAUNCHER, None, mixer_pad)
    build('preset2-sequencer-drums.spc', SEQUENCER, None, drum_pad,
          button_leds=True)
    build('preset3-keys.spc', LAUNCHER, key_pad, settings_pad,
          (PARAM_CCS_BANK_1, PARAM_CCS_BANK_2))
    build('preset4-chords.spc', LAUNCHER, chord_pad, chord_settings_pad,
          (PARAM_CCS_BANK_1, PARAM_CCS_BANK_2))
