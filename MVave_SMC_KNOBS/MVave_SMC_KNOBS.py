# Encoder half of the M-Vave SMC-PAD setup.
#
# The pads and the encoders arrive on DIFFERENT MIDI ports, and a Remote Script
# gets exactly one input port, so this is a second script in a second Control
# Surface slot:
#
#   slot 1   MVave_SMC_PAD     in MIDIIN3 / out MIDIOUT3   pads, buttons, LEDs
#   slot 2   MVave_SMC_KNOBS   in/out SMC-PAD (port 1)     the 8 encoders
#
# BOTH knob banks are used: on the launcher preset that is 14 macros plus two
# navigation encoders; on the sequencer preset, 16 macros and no navigation.
#
#   bank 1, knobs 7 8 5 6 3 4 1 2   ->  macros 1-8
#   bank 2, knobs 7 8 5 6 3 4       ->  macros 9-14
#   bank 2, knobs 1 2               ->  session box X and Y
#
# On the keyboard preset (3) the knobs send their own CCs, 21-36, and play the
# selected device's parameters the way Live's own controllers bank them: see
# PARAM_BY_CC.
#
# The macros follow the selection -- Live's "blue hand" -- rather than being
# statically MIDI-mapped. Click a different track and the same knobs control that
# device instead, which is the entire point of doing this in a script.
#
# Why the parameters are driven directly rather than through DeviceComponent's
# parameter controls: that mechanism addresses ONE BANK OF EIGHT at a time and
# pages between banks. Fourteen simultaneous macros do not fit it. Driving
# device.parameters directly also means decoding the relative encoders here,
# exactly as the navigation knobs already do, instead of depending on a
# Live.MidiMap.MapMode constant that cannot be verified off-machine.
#
# This script deliberately builds NO session box of its own. Live's red box
# belongs to whichever script called set_highlighting_session_component, so a
# second box would either fight the first or trigger the pad template's
# combination mode. Instead it reaches the pad script's session through the
# class-level _active_instances list and moves the real box.
from __future__ import with_statement

import traceback

# Revision of these scripts, for bug reports: the install is "copy a
# folder", so a downloaded copy carries no commit and nothing else here
# names a version. Quote this line.
SCRIPT_REVISION = '2026-10-20'

import Live
from _Framework.ControlSurface import ControlSurface
from _Framework.DeviceComponent import DeviceComponent
from _Framework.ButtonElement import ButtonElement
from _Framework.InputControlElement import MIDI_NOTE_TYPE, MIDI_CC_TYPE

# Measured 2026-08-31 with tools/mvave_probe.py --knobs, one encoder at a time.
# Every encoder on the device is RELATIVE, both banks, centred on 64:
# 65 is one click clockwise, 63 one click back.
CHANNEL = 0                                     # MIDI channel 1
CENTRE = 64

# How a relative encoder encodes one click. The same hardware fact lives in
# MVave_SMC_STEPSEQ/MIDI_Map.py as KNOB_MODE, and the two must agree -- a test
# in tools/stepseq_selftest.py asserts they do. It is duplicated rather than
# imported because the sequencer package is optional; a rig with only the
# launcher and the encoders must not depend on it being installed.
#
#   'centre'  63 = one step back, 64 = nothing, 65 = one step forward.
#   'twos'    127 = one step back, 1 = one step forward.
#
# The two are mutually ambiguous -- 63 is -1 under 'centre' and +63 under
# 'twos' -- so this is a setting, not something that can be detected. Feeding
# the wrong one to the session box moves it 63 tracks per click, silently.
ENCODER_MODE = 'centre'


def decode_relative(value, mode=None):
    """One encoder click -> a signed number of steps."""
    if (mode or ENCODER_MODE) == 'twos':
        return value if value < 64 else value - 128
    return value - CENTRE

# Navigation -- bank 2, knobs 1 and 2 (the BOTTOM pair; the device numbers its
# encoders bottom-up, so encoder 1 is bottom-left and encoder 7 is top-left).
CC_TRACK = 17                                   # box across tracks
CC_SCENE = 18                                   # box through scenes
NAV_CCS = (CC_TRACK, CC_SCENE)

# CC -> macro number, 1-based. Macro N is device.parameters[N]; index 0 is the
# device on/off switch, so the numbering lines up with no offset arithmetic.
#
# Re-measured 2026-08-31 after the device was renumbered: CC number now equals
# macro number for all fourteen, so this table is the identity function. That is
# by design, not luck -- the CCs were chosen to make it so. It survives only as
# long as the device keeps that numbering, which is why it stays an explicit map
# rather than becoming arithmetic: the next editor change can break the identity
# without breaking the file.
#
# The physical layout is 2 wide by 4 tall, numbered BOTTOM-UP. Reading the panel
# top-left to bottom-right is therefore encoders 7,8,5,6,3,4,1,2, which is why
# the macros run in that order rather than 1..8:
#
#     enc 7  enc 8        macro 1  macro 2     <- top
#     enc 5  enc 6        macro 3  macro 4
#     enc 3  enc 4        macro 5  macro 6
#     enc 1  enc 2        macro 7  macro 8     <- bottom   (bank 2: nav)
# Encoders are PER-PRESET, so the two presets send different CCs from the same
# knobs -- and they were numbered so that no CC means two things. That is what
# lets one flat table serve both presets with no mode detection:
#
#   CC 1-14   macros 1-14      both presets, identical
#   CC 15-16  macros 15-16     sequencer preset only (bank 2, bottom pair)
#   CC 17-18  session box X/Y  launcher preset only  (bank 2, bottom pair)
#
# The bottom pair is the only difference. The launcher needs grid navigation; the
# sequencer has no session box to move -- it pages with the arrow buttons -- so
# there those two knobs become the last two macros of a 16-macro rack instead.
MACRO_BY_CC = {
    # bank 1: encoders 7, 8, 5, 6, 3, 4, 1, 2  ->  macros 1-8
    1: 1,   2: 2,   3: 3,   4: 4,   5: 5,   6: 6,   7: 7,   8: 8,
    # bank 2: encoders 7, 8, 5, 6, 3, 4  ->  macros 9-14
    9: 9,   10: 10, 11: 11, 12: 12, 13: 13, 14: 14,
    # bank 2 bottom pair, sequencer preset only  ->  macros 15-16
    15: 15, 16: 16,
}

# One click moves this fraction of a parameter's range. A rack macro runs 0-127,
# so its range is 127 and this gives exactly one unit per click; a continuous
# parameter with a different range scales proportionally rather than jumping.
# (128 was the obvious-looking number and is off by one: it moves 0.992 per
# click, so macro values never land on integers and one click per sweep is
# invisible.)
STEPS_PER_SWEEP = 127.0

# Preset 3 (the keyboard): the knobs play the selected device's parameters in
# the banks Live's own controllers use, so a built-in instrument answers with
# no mapping. Live's built-in instruments ignore MIDI CCs, which is why the
# standard synth CCs these knobs used to send did nothing on them.
#
#   knob bank 1  ->  Live's first bank of eight for the device
#   knob bank 2  ->  its second bank
#
# The banks are Live 12's own table (ableton.v3 default_bank_definitions, the
# one Push uses), matched by parameter original_name exactly as Live does.
# A device the table doesn't list -- racks, plugins, Max devices -- gets
# parameters 1-16 in order: a rack's macros, or the list a plugin's Configure
# button builds. Relative, like every other knob here, so switching devices
# never makes a parameter jump.
#
# Slot = position on the panel, reading order (top-left first), bank 1 then
# bank 2; tools/make_presets.py PARAM_CCS_BANK_* gives each knob its CC.
PARAM_CC_FIRST = 21
BANK_SIZE = 8
PARAM_BANKS = 2
PARAM_BY_CC = dict((PARAM_CC_FIRST + slot, slot)
                   for slot in range(BANK_SIZE * PARAM_BANKS))

try:
    from ableton.v3.control_surface.default_bank_definitions import (
        BANK_DEFINITIONS, BANK_PARAMETERS_KEY)
except Exception:
    # Not Live 12, or the table moved: every device falls back to parameter
    # order. Said once in Log.txt at load.
    BANK_DEFINITIONS, BANK_PARAMETERS_KEY = {}, None


def device_parameter_slots(device):
    """The parameters preset 3's knobs play on this device, one per slot,
    None where a slot has nothing. Banks come from BANK_DEFINITIONS when the
    device is in it, otherwise parameters 1-16 in order."""
    size = BANK_SIZE * PARAM_BANKS
    params = device.parameters
    definition = BANK_DEFINITIONS.get(getattr(device, 'class_name', None))
    if definition:
        by_name = {}
        for param in params:
            by_name.setdefault(param.original_name, param)
        slots = []
        for index in range(min(PARAM_BANKS, len(definition))):
            bank = definition.value_by_index(index)
            names = tuple(bank.get(BANK_PARAMETERS_KEY) or ())[:BANK_SIZE]
            names += (None,) * (BANK_SIZE - len(names))
            # str(): a slot can be a dynamic rule object; Live compares its
            # str() against original_name too.
            slots.extend(None if name is None else by_name.get(str(name))
                         for name in names)
    else:
        # Index 0 is Device On.
        slots = [params[i] for i in range(1, min(len(params), size + 1))]
    return slots + [None] * (size - len(slots))

# Preset and PAD BANK changes. The device remembers the colour each pad last
# showed and keeps it across a switch, while the pad and sequencer scripts only
# send what changed, so after Shift + pad or PAD BANK the pads kept the other
# layout's colours. Nothing reaches port 3 on a switch, but the device sends a
# 33-byte status sysex on port 1 (this script's input) once a second. A change
# in it makes both lit scripts repaint. The script that owns what is now on
# the pads repaints last, so it wins if the other's LEDs land too.
#
# Waiting for that beat costs up to a second, so this script also ASKS. The
# status is the device's reply to MidiSuite's state read, and the device
# answers the same read from us within ~1 ms, already showing a switch the
# moment it happens (measured 2026-10-20: five switches, each seen within one
# 50 ms poll, off the beat). So it sends STATE_REQUEST on display ticks
# (~100 ms). That needs this script's Output set to SINCO (SMC-PAD-Private):
# the device answers only there. With no output the request goes nowhere and
# the beat still repaints, a second late.
#
# Every request and reply flashes Live's MIDI indicators, so it asks only
# every POLL_TICKS (~0.2 s; ~0.25 s was asked for, ticks are ~0.1 s), plus at
# once whenever a pad or knob sends something
# the current layout doesn't have (LAYOUTS_BY_NOTE / LAYOUTS_BY_CC): the first
# touch after a switch gives it away. SHIFT and PAD BANK transmit nothing
# (HARDWARE.md 6.1), so there is no earlier sign. A switch therefore repaints
# the moment you touch a pad or knob, or within ~0.2 s if you don't.
# After a switch it asks on every tick for SWITCH_FAST_TICKS, since switches
# come in runs (PAD BANK flipped back and forth, a preset then PAD BANK): the
# first takes up to ~0.2 s to show, the ones after it show at once.
#
# The wire format, read from MidiSuite 1.x (CUSBConnect, CMIDITranfer): F0, the
# packet's 8-bit bytes packed 7 bits at a time, low bits first, then F7. That
# is why every message starts 00 32 0D: it unpacks to the head, 00 59. A packet
# is head, command (0x23 = flash read, request and reply), a 3-byte length,
# the payload and a checksum (the inverted byte sum of the payload). The read
# is type 4, address 0, 12 bytes; in the reply's unpacked packet, byte 24 is
# the preset (0-2) and byte 25 the PAD BANK bank (0-1). Measured for presets
# 1-3, both banks of preset 1 and 2 (2026-10-08 and 2026-10-20).
#
# Byte 22 is the VELOCITY setting, 0-3 for Shift + pad 9-12 (measured
# 2026-10-20). A change is passed to the sequencer, which writes its steps at
# that level; it repaints nothing. The setting found at startup is not passed
# on: the controller remembers whatever it was left on, and the sequencer
# starts at VELOCITY 4 (full) until you choose otherwise.
STATUS_PREFIX = (0xF0, 0x00, 0x32, 0x0D, 0x21, 0x01)
STATUS_LENGTH = 33
STATUS_VELOCITY = 22
STATUS_PRESET = 24
STATUS_BANK = 25
LAUNCHER_PRESET = 0                     # preset 1
SEQUENCER_PRESET = 1                    # preset 2
# Every packet from the device starts F0 00 32: the head 00 59, packed. The
# byte after it carries command bits, so the status (0D) and the OK a write
# gets back (01, "00 59 00 01 00 00 00 FF") differ there.
M_VAVE_SYSEX = (0xF0, 0x00, 0x32)

# Where Live puts the controller when it loads: preset 1, PAD BANK off (bank
# A). Set either to None to leave the controller where it was. Written with
# the command MidiSuite sends when you change them (captured 2026-10-20 with
# MIDI Monitor's spy): 0x22, flash write, to the same type-4 state block the
# read returns, one byte at a time. The preset is address 0x0A (byte 24 of the
# reply), the bank 0x0B (byte 25). The device switches at once and answers OK.
# A byte is only written if the first reply shows it wrong, at most
# STARTUP_TRIES times in all, so a device that ignores it is left alone.
STARTUP_PRESET = 0
STARTUP_BANK = 0
STATE_PRESET_ADDRESS = 0x0A
STATE_BANK_ADDRESS = 0x0B
STARTUP_TRIES = 4

POLL_TICKS = 2                  # one request per ~0.2 s
SWITCH_FAST_TICKS = 40          # then every tick for ~4 s after a switch


def _layout_table(ranges):
    table = {}
    for first, last, layouts in ranges:
        for number in range(first, last + 1):
            table[number] = layouts
    return table

# The layouts, (preset, bank) counted from 0 with bank None for either, that
# send each message: a press from none of them means the controller has
# switched. Port 3 notes (the pad and sequencer scripts hand each message to
# port3_message) must match MVave_SMC_PAD/MIDI_Map.py and
# MVave_SMC_STEPSEQ/MIDI_Map.py; tools/stepseq_selftest.py checks they do.
LAYOUTS_BY_NOTE = _layout_table((
    (1, 16, ((0, 0),)),                 # launcher clip pads
    (49, 64, ((0, 1),)),                # mixer
    (101, 116, ((1, 0),)),              # sequencer steps
    (117, 121, ((1, None),)),           # sequencer buttons, both banks
    (85, 100, ((2, 0),)),               # keyboard
    (22, 37, ((2, 1),)),                # key / scale bank
    (17, 21, ((0, None), (2, None))),   # launcher buttons, presets 1 and 3
))
LAYOUTS_BY_CC = _layout_table((
    (1, 14, ((0, None), (1, None))),    # macros
    (15, 16, ((1, None),)),             # the sequencer's last two macros
    (17, 18, ((0, None),)),             # session box
    (PARAM_CC_FIRST, PARAM_CC_FIRST + BANK_SIZE * PARAM_BANKS - 1, ((2, None),)),
))



def pack7(data):
    """8-bit bytes -> the device's 7-bit sysex payload, low bits first."""
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
    """The device's 7-bit sysex payload -> its 8-bit packet."""
    out, acc, bits = [], 0, 0
    for byte in data:
        acc |= (byte & 0x7F) << bits
        bits += 7
        while bits >= 8:
            out.append(acc & 0xFF)
            acc >>= 8
            bits -= 8
    return out


def _packet(command, payload):
    packet = [0x00, 0x59, command, len(payload), 0x00, 0x00] + list(payload)
    packet.append(~sum(payload) & 0xFF)
    return tuple([0xF0] + pack7(packet) + [0xF7])


def _state_request():
    # Type 4, address 0 (4 bytes), 12 bytes (3 bytes).
    return _packet(0x23, [0x04, 0x00, 0x00, 0x00, 0x00, 0x0C, 0x00, 0x00])


def state_write(address, value):
    """Write one byte of the state block, as MidiSuite does."""
    return _packet(0x22, [0x04, address, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, value])


STATE_REQUEST = _state_request()


def decode_status(status):
    """(preset, bank) from a 33-byte status, both counted from 0."""
    packet = unpack7(status[1:-1])
    return packet[STATUS_PRESET], packet[STATUS_BANK]


def decode_velocity(status):
    """The VELOCITY setting from a 33-byte status, 0-3."""
    return unpack7(status[1:-1])[STATUS_VELOCITY]


# Ticks (~100 ms) before each repaint, kept as short as possible. The two are
# spaced so they don't reach the device as one burst (HARDWARE.md 3.5). Was
# (3, 5), to clear the ~150 ms preset dump that follows a switch; that wait
# was cut on 2026-10-08 because the lag was noticeable.
REPAINT_DELAYS = (1, 2)

# Plain MIDI to the armed track. Ports 1 (this script's) and 2 carry the same
# plain-MIDI notes and CCs; SMC-PAD-Master (port 2) used to have Track on to
# pass them to the track. That also passed the controller's note repeat, which
# the firmware sends as each pad's raw note on channel 10, ports 1 and 2 only
# (measured 2026-10-17): on preset 3 that is note 85-100, so repeats played
# C#5 and up whatever the keyboard's key, scale and octave. So Track is now off
# on port 2 and this script passes the plain MIDI through itself, with Live's
# note/CC translation, onto PASS_CHANNEL:
#
#   preset 3 note repeat   ch 10, KEYS_REPEAT_NOTES -> the scale note that pad
#                          plays (MVave_SMC_PAD's KeysMode pushes the table)
#   preset 2 drum pads     ch 10 (and ch 1), DRUM_NOTES -> same notes
#
# (Preset 3's knobs used to pass through here as synth CCs; they now play the
# selected device instead, PARAM_BY_CC.)
#
# Anything else -- note repeat on a lit launcher, mixer or sequencer pad --
# reaches no track at all, which is better than the raw note it used to play.
# Translation keeps velocity, so repeats keep the device's own (quiet) one.
PASS_CHANNEL = 1                        # MIDI channel 2, as MVave_SMC_PAD's KEYS_CHANNEL
REPEAT_CHANNEL = 9                      # MIDI channel 10
KEYS_REPEAT_NOTES = tuple(range(85, 101))   # == MVave_SMC_PAD KEYS_NOTES
DRUM_NOTES = tuple(range(36, 52))           # tools/make_presets.py drum_pad
DRUM_CHANNELS = (REPEAT_CHANNEL, 0)


def _clamp(value, ceiling):
    return max(0, min(value, max(0, ceiling)))


class MVave_SMC_KNOBS(ControlSurface):
    __doc__ = " Encoder half of the M-Vave SMC-PAD: session box + up to 16 device macros "

    # So MVave_SMC_PAD's keyboard can push its note table here.
    _active_instances = []

    def __init__(self, c_instance):
        ControlSurface.__init__(self, c_instance)
        self._logged = set()
        self._exceptions_logged = set()
        self._first_nav_logged = False
        self._first_macro_logged = False
        self._first_param_logged = False
        self._slots_device = None
        self._slots = None
        self._device_logged = False
        self._last_status = None
        self._last_velocity = None
        self._startup_pending = True
        self._startup_tries = STARTUP_TRIES
        self._poll_ticks = 0
        self._fast_ticks = 0
        self._asked_this_tick = False
        self._device = None
        self._target_device = None
        self._repeat_buttons = []
        with self.component_guard():
            self._setup_device_control()
            self._setup_pass_through()
        MVave_SMC_KNOBS._active_instances.append(self)
        self._pull_keys()
        self.log_message('MVave_SMC_KNOBS: loaded. CC %d/%d navigate; %d macro CCs %s; '
                         'preset 3 CCs %d-%d play device banks (%s).'
                         % (CC_TRACK, CC_SCENE, len(MACRO_BY_CC),
                            ','.join(str(c) for c in sorted(MACRO_BY_CC)),
                            min(PARAM_BY_CC), max(PARAM_BY_CC),
                            'Live bank table, %d devices' % len(BANK_DEFINITIONS)
                            if BANK_DEFINITIONS else
                            'no Live bank table -- parameter order only'))

    def disconnect(self):
        if self in MVave_SMC_KNOBS._active_instances:
            MVave_SMC_KNOBS._active_instances.remove(self)
        self._repeat_buttons = []
        ControlSurface.disconnect(self)

    # ----------------------------------------------------------- pass-through

    def _setup_pass_through(self):
        # Elements built inside component_guard are registered, so
        # build_midi_map installs their translations -- the same mechanism
        # MVave_SMC_PAD's keyboard uses. Forwarding is suppressed: these
        # belong to the track, not to receive_midi.
        def passed(element):
            element.set_channel(PASS_CHANNEL)
            element.suppress_script_forwarding = True
            return element
        for channel in DRUM_CHANNELS:
            for note in DRUM_NOTES:
                passed(ButtonElement(True, MIDI_NOTE_TYPE, channel, note))
        for note in KEYS_REPEAT_NOTES:
            button = ButtonElement(True, MIDI_NOTE_TYPE, REPEAT_CHANNEL, note)
            # Untranslated until the keyboard says what each pad plays, and
            # forwarding suppressed, so until then a repeat goes nowhere.
            button.suppress_script_forwarding = True
            self._repeat_buttons.append(button)

    def _pull_keys(self):
        # The pad script may have loaded first; if not, it pushes when it does.
        # Its absence is _pad_session's to report, not this.
        for pad in self._instances('MVave_SMC_PAD'):
            keys = getattr(pad, '_keys_mode', None)
            if keys is None:
                continue
            try:
                self.keys_changed(keys.targets())
            except Exception:
                self._log_exception('read keyboard notes')

    def keys_changed(self, targets):
        """The note each of preset 3's 16 keyboard pads plays (None = none),
        PAD1 first. Called by MVave_SMC_PAD whenever key, scale, octave or
        layout changes, so note repeat plays what the pad plays."""
        for button, note in zip(self._repeat_buttons, targets):
            if note is None:
                button.use_default_message()
            else:
                button.set_identifier(note)
                button.set_channel(PASS_CHANNEL)
        self.request_rebuild_midi_map()

    # ----------------------------------------------------------------- device

    def _setup_device_control(self):
        # The component exists only to keep Live's blue hand pointed at the same
        # device these knobs write to. set_parameter_controls is deliberately
        # NOT called: it addresses one bank of eight, and some _Framework
        # versions assert on the count, which would take the script down in
        # __init__ rather than merely disabling a feature.
        self._device = DeviceComponent()
        self._device.name = 'Device_Component'
        self.set_device_component(self._device)

    def _on_selected_track_changed(self):
        try:
            self._follow_selected_track()
        except Exception:
            # Live calls this on every track click. Letting it raise would take
            # the script down for the rest of the session.
            self._log_exception('selected track changed')

    def _follow_selected_track(self):
        # Follow the selection: the same knobs, whatever track you click on.
        #
        # The superclass call gets its OWN guard, because everything below it is
        # this script's rebinding and a framework failure must not cancel it --
        # otherwise one raise pins the write target to the previous track for
        # the rest of the session, logged once and never revisited.
        try:
            ControlSurface._on_selected_track_changed(self)
        except Exception:
            self._log_exception('ControlSurface._on_selected_track_changed')
        track = self.song().view.selected_track
        device_to_select = track.view.selected_device
        if device_to_select is None and len(track.devices) > 0:
            device_to_select = track.devices[0]
        if device_to_select is not None:
            self.song().view.select_device(device_to_select)
        self._target_device = device_to_select
        if self._device is not None:
            self._device.set_device(device_to_select)
        if not self._device_logged:
            # Once only. If the macros are dead, this line separates "no device
            # was ever assigned" from a fault further down.
            self._device_logged = True
            self.log_message('MVave_SMC_KNOBS: device -> %s'
                             % (device_to_select.name if device_to_select else 'None'))

    def _current_device(self):
        """The device to write to, resolved at write time rather than cached.

        _on_selected_track_changed is the only hook this script has, and it
        fires on a TRACK change only. A cached target therefore goes stale the
        moment you click a different device on the same track: Live's blue hand
        moves, because DeviceComponent has its own appointed-device listener,
        while the cache does not -- so the knobs quietly edit the device you
        just navigated away from, with nothing to show for it. Delete the
        cached device and the reference dangles, and the next click raises
        inside a MIDI callback, which takes the whole script down.

        DeviceComponent already follows the appointed device, so ask it. The
        cached value survives only as a fallback for a _Framework version whose
        DeviceComponent has no device() getter.
        """
        component = self._device
        if component is not None:
            # A SENTINEL, not None, because getattr's default cannot tell an
            # absent attribute from a getter legitimately answering None. That
            # distinction is the whole game here: "no device is selected" is a
            # real answer and must be returned, while falling through to the
            # cache on it hands back a device the component has already let go
            # -- which is the dangling reference this method exists to avoid,
            # and it happens on every fresh start before the first track click.
            missing = object()
            getter = getattr(component, 'device', missing)
            if getter is not missing:
                # Method on most versions, property on others. Calling a
                # property's value would raise TypeError in a MIDI callback.
                return getter() if callable(getter) else getter
            private = getattr(component, '_device', missing)
            if private is not missing:
                # Reached only when the public name is absent entirely. An
                # explicit None is still an answer; anything else has to look
                # like a device before the macros write to it, since this is
                # private state whose shape no version guarantees.
                if private is None or hasattr(private, 'parameters'):
                    return private
        # Nothing on the component exposes its device, so fall back to whatever
        # the last TRACK change cached. That is the pre-fix behaviour, with the
        # pre-fix bugs -- the knobs will write to a device that goes stale the
        # moment you pick another one on the same track. Say so once: without
        # this line Log.txt cannot tell you which of the two worlds you are in,
        # and the whole point of resolving at write time is silently lost.
        self._log_once('DeviceComponent exposes no device getter -- the macros '
                       'fall back to the device cached at the last track change, '
                       'which goes stale if you select another device on the '
                       'same track')
        return self._target_device

    def _adjust_macro(self, macro, delta):
        device = self._current_device()
        if device is None:
            self._log_once('no device selected yet -- click a track to bind one')
            return
        params = device.parameters
        if macro >= len(params):
            # Not an error: a device with fewer macros than knobs is normal.
            # Logged once per device+macro so a small rack cannot flood the log.
            self._log_once('"%s" exposes %d macro(s); the macro-%d knob does nothing'
                           % (device.name, max(0, len(params) - 1), macro),
                           key=(id(device), macro))
            return
        self._adjust_parameter(params[macro], delta)

    def _adjust_slot(self, slot, delta):
        device = self._current_device()
        if device is None:
            self._log_once('no device selected yet -- click a track to bind one')
            return
        if (self._slots is None or self._slots_device is None
                or self._slots_device != device
                or not BANK_DEFINITIONS.get(getattr(device, 'class_name', None))):
            # Cached only for devices in Live's table, where resolving reads
            # every parameter's name; a plugin's list changes under Configure
            # and its slots are cheap to read anyway.
            self._slots = device_parameter_slots(device)
            self._slots_device = device
        param = self._slots[slot]
        if param is None:
            self._log_once('"%s" has nothing on preset 3 knob slot %d'
                           % (device.name, slot + 1),
                           key=(getattr(device, 'class_name', None), slot))
            return
        self._adjust_parameter(param, delta)

    def _adjust_parameter(self, param, delta):
        if not param.is_enabled:
            return
        # Each read is a call into Live, once per click of every turn.
        low, high = param.min, param.max
        if param.is_quantized:
            new_value = param.value + delta
        else:
            new_value = param.value + delta * (high - low) / STEPS_PER_SWEEP
        # Clamped here: writing outside a parameter's range raises, and an
        # exception inside a MIDI callback disables the whole script silently.
        param.value = max(low, min(high, new_value))

    # ------------------------------------------------------------------- midi

    def port3_message(self, midi_bytes):
        if (len(midi_bytes) == 3 and (midi_bytes[0] & 0xF0) == 0x90
                and midi_bytes[2]):
            self._layout_hint(LAYOUTS_BY_NOTE.get(midi_bytes[1]))

    def _layout_hint(self, layouts):
        """Ask now if a message came from a layout other than the last one
        the controller reported. At most once a tick: a chord of presses
        after a switch needs one answer, not sixteen."""
        if not layouts or self._last_status is None or self._asked_this_tick:
            return
        preset, bank = self._last_status
        for p, b in layouts:
            if p == preset and (b is None or b == bank):
                return
        self._ask_state()

    def _ask_state(self):
        self._asked_this_tick = True
        self._poll_ticks = 0
        try:
            # Ask for the preset, bank and velocity; the reply is a status.
            self._send_midi(STATE_REQUEST)
        except Exception:
            self._log_exception('ask the device for its state')

    def update_display(self):
        ControlSurface.update_display(self)
        self._asked_this_tick = False
        self._poll_ticks += 1
        if self._fast_ticks > 0:
            self._fast_ticks -= 1
        # Every tick until the startup preset is in place, so it's seen at once.
        if (self._startup_pending or self._fast_ticks > 0
                or self._poll_ticks >= POLL_TICKS):
            self._ask_state()
            self._asked_this_tick = False

    def build_midi_map(self, midi_map_handle):
        ControlSurface.build_midi_map(self, midi_map_handle)
        script_handle = self._c_instance.handle()
        for cc in tuple(NAV_CCS) + tuple(sorted(MACRO_BY_CC)) + tuple(sorted(PARAM_BY_CC)):
            Live.MidiMap.forward_midi_cc(script_handle, midi_map_handle, CHANNEL, cc)

    def receive_midi(self, midi_bytes):
        try:
            if tuple(midi_bytes[:len(M_VAVE_SYSEX)]) == M_VAVE_SYSEX:
                # The status every second and the preset dump after a switch.
                # Handed to the framework, each one is an "unknown sysex" line
                # in Log.txt.
                if (len(midi_bytes) == STATUS_LENGTH
                        and tuple(midi_bytes[:6]) == STATUS_PREFIX):
                    status = decode_status(midi_bytes)
                    if not self._move_to_startup(status):
                        self._on_device_status(status)
                    self._on_velocity_setting(decode_velocity(midi_bytes))
                return
            if len(midi_bytes) == 3 and (midi_bytes[0] & 0xF0) == 0xB0:
                cc, value = midi_bytes[1], midi_bytes[2]
                self._layout_hint(LAYOUTS_BY_CC.get(cc))
                if cc in NAV_CCS:
                    self._navigate(cc, value)
                    return
                if cc in MACRO_BY_CC:
                    self._macro(cc, value)
                    return
                if cc in PARAM_BY_CC:
                    self._param(cc, value)
                    return
        except Exception:
            # An uncaught exception here disables the entire script until Live
            # restarts -- all fourteen macros AND both navigation encoders --
            # with nothing in the UI to say so. Clamping alone was the previous
            # defence, which only covers the failures we thought of.
            self._log_exception('receive_midi')
            return
        # Anything unclaimed belongs to the framework. Swallowing it here is the
        # classic silent failure in this codebase, so it is forwarded explicitly.
        ControlSurface.receive_midi(self, midi_bytes)

    def _navigate(self, cc, value):
        if not self._first_nav_logged:
            # One line proving the pipe works, then silence -- a knob produces
            # hundreds of messages and Log.txt is not the place for them.
            self._first_nav_logged = True
            self.log_message('MVave_SMC_KNOBS: first nav CC -- %d value %d' % (cc, value))
        delta = decode_relative(value)
        if delta == 0:
            return
        if cc == CC_TRACK:
            self._bank(delta, 0)
        elif cc == CC_SCENE:
            self._bank(0, delta)

    def _macro(self, cc, value):
        if not self._first_macro_logged:
            self._first_macro_logged = True
            self.log_message('MVave_SMC_KNOBS: first macro CC -- %d value %d -> macro %d'
                             % (cc, value, MACRO_BY_CC[cc]))
        delta = decode_relative(value)
        if delta:
            self._adjust_macro(MACRO_BY_CC[cc], delta)

    def _param(self, cc, value):
        if not self._first_param_logged:
            self._first_param_logged = True
            self.log_message('MVave_SMC_KNOBS: first preset 3 knob CC -- %d value %d -> slot %d'
                             % (cc, value, PARAM_BY_CC[cc] + 1))
        delta = decode_relative(value)
        if delta:
            self._adjust_slot(PARAM_BY_CC[cc], delta)

    # ------------------------------------------------------------ pad lights

    def _move_to_startup(self, status):
        """Until the controller is on STARTUP_PRESET / STARTUP_BANK, write the
        first byte that is wrong. True while a write is on its way, so this
        status repaints nothing: the next one shows the switch."""
        if not self._startup_pending:
            return False
        preset, bank = status
        for address, wanted, actual in ((STATE_PRESET_ADDRESS, STARTUP_PRESET, preset),
                                        (STATE_BANK_ADDRESS, STARTUP_BANK, bank)):
            if wanted is None or wanted == actual:
                continue
            if self._startup_tries <= 0:
                self._log_once('the controller did not take the startup preset '
                               'or bank; leaving it where it is')
                break
            self._startup_tries -= 1
            self._send_midi(state_write(address, wanted))
            return True
        self._startup_pending = False
        return False

    def _on_device_status(self, status):
        if status == self._last_status:
            return
        first = self._last_status is None
        if not first:
            self._fast_ticks = SWITCH_FAST_TICKS
        self._last_status = status
        preset, bank = status
        on_sequencer = preset == SEQUENCER_PRESET and not bank
        pad = self._instances('MVave_SMC_PAD')
        seq = self._instances('MVave_SMC_STEPSEQ')
        if first:
            # The startup light show (MVave_SMC_PAD/StartupIntro.py) plays
            # on the clip grid, so only if that is what the pads show now.
            # Scheduled, like the repaints below, to run in the pad script's
            # own context. The flag is never None, so it is passed on.
            for script in pad:
                play_intro = getattr(script, 'play_intro', None)
                if play_intro is not None:
                    script.schedule_message(1, play_intro,
                                            preset == LAUNCHER_PRESET and not bank)
        # The sequencer keeps its clip while another preset is up, so the
        # selection can move around on preset 3 without losing the pattern.
        for script in seq:
            set_on_screen = getattr(script, 'set_on_screen', None)
            if set_on_screen is not None:
                set_on_screen(preset == SEQUENCER_PRESET)
        order = pad + seq if on_sequencer else seq + pad
        for delay, script in zip(REPAINT_DELAYS, order):
            # Scheduled on the other script, so the repaint runs in its own
            # context, as Live's own refresh_state call would.
            script.schedule_message(delay, script.refresh_state)

    def _on_velocity_setting(self, setting):
        if setting == self._last_velocity:
            return
        first = self._last_velocity is None
        self._last_velocity = setting
        if first:
            return
        for script in self._instances('MVave_SMC_STEPSEQ'):
            set_velocity_setting = getattr(script, 'set_velocity_setting', None)
            if set_velocity_setting is not None:
                set_velocity_setting(setting)

    def _instances(self, name):
        # Resolved per call for the same reason as _pad_session. The
        # sequencer is optional, so its absence is not worth a log line.
        try:
            module = __import__('%s.%s' % (name, name), fromlist=[name])
            return list(getattr(getattr(module, name), '_active_instances', None) or [])[:1]
        except Exception:
            return []

    # ---------------------------------------------------------------- session

    def _pad_session(self):
        # Resolved on every turn rather than cached at load: the two Control
        # Surface slots load in an order we do not control, so the pad script
        # may not exist yet when this one starts. After the first import this
        # is just a sys.modules lookup, so the cost is nil.
        try:
            from MVave_SMC_PAD.MVave_SMC_PAD import MVave_SMC_PAD
        except Exception as exc:
            self._log_once('cannot import MVave_SMC_PAD (%s)' % type(exc).__name__)
            return None
        instances = getattr(MVave_SMC_PAD, '_active_instances', None) or []
        if not instances:
            self._log_once('MVave_SMC_PAD is not loaded -- is it in a Control Surface slot?')
            return None
        return getattr(instances[0], '_session', None)

    def _log_once(self, message, key=None):
        # Keyed on the message rather than a single flag, so a later distinct
        # problem is not hidden by an earlier one -- or on an explicit key when
        # the message interpolates text that repeats across genuinely different
        # causes. Two racks both called "Audio Effect Rack" (Live's default) are
        # two devices and one string, so without a key the second one's dead
        # knobs are never reported and the troubleshooting step reads
        # "no line, so not this cause", which is wrong.
        #
        # Capped like _log_exception: a caller that interpolates a message
        # varying per occurrence must not be able to grow this set without
        # bound. _pad_session() runs on every navigation click.
        signature = message if key is None else key
        if signature in self._logged or len(self._logged) >= 32:
            return
        self._logged.add(signature)
        self.log_message('MVave_SMC_KNOBS: ' + message)

    def _log_exception(self, where):
        # Keyed on the last traceback line -- the exception type and message --
        # and capped, exactly as MVave_SMC_STEPSEQ does. Routing the whole
        # traceback through _log_once keys on text that varies with the
        # exception's own message, so a fault whose text changes per occurrence
        # defeats the latch entirely: a traceback per MIDI message, hundreds
        # per knob turn, and an unbounded set entry for each one.
        text = traceback.format_exc()
        # Keyed on the deepest frame as well as the exception line. `where` is
        # coarse -- receive_midi covers both the session-box path and the device
        # path -- and the likeliest fault in either is the same message, so a
        # key without the frame silently discards whichever failed second.
        lines = text.strip().split('\n')
        frame = next((l.strip() for l in reversed(lines)
                      if l.strip().startswith('File "')), '')
        signature = (where, frame, lines[-1])
        if signature in self._exceptions_logged or len(self._exceptions_logged) >= 32:
            return
        self._exceptions_logged.add(signature)
        self.log_message('MVave_SMC_KNOBS: exception in %s\n%s' % (where, text))

    def _bank(self, d_track, d_scene):
        session = self._pad_session()
        if session is None:
            return
        song = self.song()
        try:
            track_count = len(song.visible_tracks)
        except AttributeError:
            track_count = len(song.tracks)
        scene_count = len(song.scenes)

        track_offset = self._probe_value(session, 'track_offset', '_track_offset')
        scene_offset = self._probe_value(session, 'scene_offset', '_scene_offset')
        if track_offset is None or scene_offset is None:
            self._log_once('could not read the session offsets')
            return

        # Clamped here rather than left to set_offsets, which asserts on a
        # negative offset -- an assert inside a MIDI callback takes the script
        # down mid-jam.
        # Probed like the offsets above: this SessionComponent's getters are
        # methods on most _Framework versions and plain attributes on others,
        # and hardening only half of them left width()/height() raising
        # TypeError -- which receive_midi's guard would now swallow, killing
        # both navigation encoders quietly instead of loudly.
        width = self._probe_value(session, 'width', '_num_tracks')
        height = self._probe_value(session, 'height', '_num_scenes')
        if width is None or height is None:
            self._log_once('could not read the session box size')
            return
        new_track = _clamp(track_offset + d_track, track_count - width)
        new_scene = _clamp(scene_offset + d_scene, scene_count - height)
        if (new_track, new_scene) != (track_offset, scene_offset):
            session.set_offsets(new_track, new_scene)

    def _probe_value(self, session, method_name, attr_name):
        # _Framework exposes these as methods in most versions and as bare
        # attributes in others, and it is not on the machine this was written
        # on, so try both rather than guess.
        method = getattr(session, method_name, None)
        if callable(method):
            return method()
        if method is not None:
            # This version spells it as a plain attribute under the same name.
            # Calling it would raise TypeError inside a MIDI callback, which is
            # the exact failure the two-spellings dance exists to avoid.
            return method
        return getattr(session, attr_name, None)
