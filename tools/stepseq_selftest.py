#!/usr/bin/env python3
"""Run MVave_SMC_STEPSEQ against a fake Live, on any machine.

    python3 tools/stepseq_selftest.py [-v]

Why this exists: Live has no hot reload. Every change to a Remote Script costs a
full Live restart, and a mistake inside a MIDI callback disables the script
silently -- the controller just stops responding and the only evidence is a
traceback in Log.txt. That is a punishing loop to debug grid arithmetic in.

Everything in the sequencer that is arithmetic rather than I/O -- which
coordinate maps to which step, which note bucket a time falls in, which LED
bytes go out and in what order, what happens when the bound clip is deleted --
can be checked here in a second, with no controller and no DAW. What this cannot
check is the hardware itself: the note numbers, the channel, the palette. Those
are Phase 0, on the device, and they live in MVave_SMC_STEPSEQ/MIDI_Map.py.

The stubs below implement only the slice of the Live API the sequencer touches,
and they deliberately model the half-open [t, t + span) window semantics that
the script's floor-bucketing assumes.

Live behaviours these fakes *assert* rather than check. A green run inherits
whichever of these is wrong, so they are listed rather than buried:

  * get_notes_extended/remove_notes_extended use the half-open window
    [from_time, from_time + span) -- CONFIRMED on Live 11.3.43, 2026-09-03, by
    hand: a note on step 5, then pressing the empty step 4, adds to step 4 and
    leaves step 5 alone. A closed window would have deleted the neighbour. The
    "a lit step is a step pressing clears" guarantee rests on this one.
  * add_new_notes fires the notes listener exactly once, synchronously -- still
    assumed; the suite would not notice a second fire.
  * MidiNoteSpecification accepts these keyword arguments -- de facto confirmed,
    since steps are written on real hardware.
  * a deleted LOM object raises on EVERY attribute access, methods included --
    STILL ASSUMED. FakeClip.__getattribute__ models it, and both the
    deleted-clip test and _detach_clip's block-level guard rest on it. No
    session has yet deleted a clip while the sequencer held it.
"""

import ast
import contextlib
import os
import sys
import unittest


# --------------------------------------------------------------------- stubs

class FakeNote(object):
    def __init__(self, pitch, start_time, duration, velocity, mute=False):
        self.pitch = pitch
        self.start_time = start_time
        self.duration = duration
        self.velocity = velocity
        self.mute = mute

    def __repr__(self):
        return 'Note(%d @ %.3f)' % (self.pitch, self.start_time)


class FakeListenable(object):
    """Live's add_x_listener / remove_x_listener / x_has_listener triple."""

    def __init__(self):
        self._listeners = {}

    def _bucket(self, name):
        return self._listeners.setdefault(name, [])

    def _add(self, name, callback):
        if callback not in self._bucket(name):
            self._bucket(name).append(callback)

    def _remove(self, name, callback):
        # Live raises on a double remove; so does this, so the script's guards
        # are actually exercised rather than merely present.
        self._bucket(name).remove(callback)

    def _has(self, name, callback):
        return callback in self._bucket(name)

    def _fire(self, name):
        for callback in list(self._bucket(name)):
            callback()


class FakeClip(FakeListenable):
    # Class-level so __getattribute__ below can read it before __init__ runs.
    dead = False

    def __init__(self, loop_start=0.0, loop_end=4.0, is_midi=True):
        FakeListenable.__init__(self)
        self.is_midi_clip = is_midi
        self.loop_start = loop_start
        self.loop_end = loop_end
        self.end_marker = loop_end
        self.is_playing = False
        self.is_triggered = False
        self.playing_position = 0.0
        self.notes = []
        self.fired = 0
        self.dead = False

    def __getattribute__(self, name):
        # A deleted Live object raises on ANY attribute access, not only on the
        # three note methods -- and that is precisely what _detach_clip's guards
        # and _rebind's try/except exist to survive. Modelling only the note
        # methods meant the deleted-clip test never reached a single dead
        # access: _detach_clip nulls _clip and then asks *_has_listener, which
        # answered normally, so the test passed without exercising anything.
        if name != 'dead' and not name.startswith('__'):
            if object.__getattribute__(self, 'dead'):
                raise RuntimeError('clip has been deleted')
        return object.__getattribute__(self, name)

    def _check(self):
        if self.dead:
            raise RuntimeError('clip has been deleted')

    def set_loop_start(self, value):
        """Drag the FRONT of the brace. Fires loop_start and nothing else."""
        self.loop_start = value
        self._fire('loop_start')

    def set_loop_end(self, value):
        """Drag the loop brace the way the mouse does: no note changes at all.

        Live fires the loop listeners here and nothing else; the notes listener
        stays silent, which is why the script needs its own loop listener.
        """
        self.loop_end = value
        self._fire('loop_end')

    def get_notes_extended(self, from_pitch, pitch_span, from_time, time_span):
        self._check()
        return tuple(n for n in self.notes
                     if from_pitch <= n.pitch < from_pitch + pitch_span
                     and from_time <= n.start_time < from_time + time_span)

    def add_new_notes(self, specs):
        self._check()
        for spec in specs:
            self.notes.append(FakeNote(spec.pitch, spec.start_time,
                                       spec.duration, spec.velocity, spec.mute))
        self._fire('notes')

    def remove_notes_extended(self, from_pitch, pitch_span, from_time, time_span):
        self._check()
        doomed = self.get_notes_extended(from_pitch, pitch_span, from_time, time_span)
        self.notes = [n for n in self.notes if n not in doomed]
        self._fire('notes')

    def add_notes_listener(self, cb):
        self._add('notes', cb)

    def remove_notes_listener(self, cb):
        self._remove('notes', cb)

    def notes_has_listener(self, cb):
        return self._has('notes', cb)

    def add_playing_position_listener(self, cb):
        self._add('position', cb)

    def remove_playing_position_listener(self, cb):
        self._remove('position', cb)

    def playing_position_has_listener(self, cb):
        return self._has('position', cb)

    def add_playing_status_listener(self, cb):
        self._add('status', cb)

    def remove_playing_status_listener(self, cb):
        self._remove('status', cb)

    def playing_status_has_listener(self, cb):
        return self._has('status', cb)

    def add_loop_start_listener(self, cb):
        self._add('loop_start', cb)

    def remove_loop_start_listener(self, cb):
        self._remove('loop_start', cb)

    def loop_start_has_listener(self, cb):
        return self._has('loop_start', cb)

    def add_loop_end_listener(self, cb):
        self._add('loop_end', cb)

    def remove_loop_end_listener(self, cb):
        self._remove('loop_end', cb)

    def loop_end_has_listener(self, cb):
        return self._has('loop_end', cb)

    def play(self, position):
        self.is_playing = True
        self.is_triggered = False
        self.playing_position = position
        self._fire('position')

    def fire(self):
        # Live queues the launch until the quantise point: triggered, not yet
        # playing, and the status listener hears it.
        self.fired += 1
        self.is_triggered = True
        self._fire('status')

    def stop(self):
        self.is_playing = False
        self.is_triggered = False
        self._fire('status')


class PreLive11Clip(FakeClip):
    """A Live 10 clip. The extended note API arrived in Live 11."""

    @property
    def get_notes_extended(self):
        raise AttributeError('get_notes_extended')


class FakeView(FakeListenable):
    def __init__(self):
        FakeListenable.__init__(self)
        self.detail_clip = None
        self.selected_track = FakeTrack()
        self.selected_device = None

    def select_device(self, device):
        self.selected_device = device
        self.selected_track.view.selected_device = device

    def select(self, clip):
        self.detail_clip = clip
        self._fire('detail_clip')

    def add_detail_clip_listener(self, cb):
        self._add('detail_clip', cb)

    def remove_detail_clip_listener(self, cb):
        self._remove('detail_clip', cb)

    def detail_clip_has_listener(self, cb):
        return self._has('detail_clip', cb)

    def add_selected_track_listener(self, cb):
        self._add('track', cb)

    def remove_selected_track_listener(self, cb):
        self._remove('track', cb)

    def selected_track_has_listener(self, cb):
        return self._has('track', cb)


class FakeChain(object):
    def __init__(self, devices):
        self.devices = list(devices)


class FakeDrumPad(object):
    def __init__(self, note, devices=()):
        self.note = note
        self.chains = [FakeChain(devices)] if devices else []


class FakeDrumRack(object):
    can_have_drum_pads = True

    def __init__(self, pads):
        self.name = 'Kit'
        self.drum_pads = [pads.get(n, FakeDrumPad(n)) for n in range(128)]
        self.view = type('RackView', (), {'selected_drum_pad': None})()


class FakeTrack(object):
    """Enough of a track for _follow_selected_track to walk it."""

    def __init__(self, devices=()):
        self.devices = list(devices)
        self.view = FakeTrackView(self.devices[0] if self.devices else None)


class FakeTrackView(object):
    def __init__(self, selected_device=None):
        self.selected_device = selected_device


class FakeSession(object):
    """The launcher's session box, as MVave_SMC_KNOBS._bank() reads it.

    Method-spelled, which is the spelling verified on Live 11.3.43; the
    attribute spelling is exercised separately through _fake_component.
    """

    def __init__(self, width=4, height=4):
        self._width, self._height = width, height
        self._track_offset = self._scene_offset = 0
        self.offsets = []

    def width(self):
        return self._width

    def height(self):
        return self._height

    def track_offset(self):
        return self._track_offset

    def scene_offset(self):
        return self._scene_offset

    def set_offsets(self, track_offset, scene_offset):
        # Live's own setter asserts on a negative offset, and an assert inside
        # a MIDI callback takes the script down mid-jam. Mirror that.
        assert track_offset >= 0, 'negative track offset %r' % track_offset
        assert scene_offset >= 0, 'negative scene offset %r' % scene_offset
        self._track_offset, self._scene_offset = track_offset, scene_offset
        self.offsets.append((track_offset, scene_offset))


class FakeSong(object):
    def __init__(self):
        self.view = FakeView()
        self.is_playing = False
        self.tracks = [FakeTrack() for _ in range(8)]
        self.visible_tracks = self.tracks
        self.scenes = [object() for _ in range(8)]

    def start_playing(self):
        self.is_playing = True

    def stop_playing(self):
        self.is_playing = False


class FakeCInstance(object):
    def __init__(self):
        self.log = []

    def handle(self):
        return 'handle'

    def log_message(self, message):
        self.log.append(message)


def install_stubs():
    """Put fake Live and _Framework modules in sys.modules, before import."""
    import types

    live = types.ModuleType('Live')

    class MidiNoteSpecification(object):
        def __init__(self, pitch=0, start_time=0.0, duration=0.0,
                     velocity=100, mute=False):
            self.pitch = pitch
            self.start_time = start_time
            self.duration = duration
            self.velocity = velocity
            self.mute = mute

    clip_module = types.ModuleType('Live.Clip')
    clip_module.MidiNoteSpecification = MidiNoteSpecification

    midi_map = types.ModuleType('Live.MidiMap')
    midi_map.forwarded = []
    midi_map.forward_midi_note = lambda h, m, ch, n: midi_map.forwarded.append(('note', ch, n))
    midi_map.forward_midi_cc = lambda h, m, ch, c: midi_map.forwarded.append(('cc', ch, c))

    live.Clip = clip_module
    live.MidiMap = midi_map

    class ControlSurface(object):
        def __init__(self, c_instance):
            self._c_instance = c_instance
            self.sent = []
            self.forwarded_to_framework = []
            self._song = FakeSong()

        def song(self):
            return self._song

        def log_message(self, message):
            self._c_instance.log_message(message)

        def show_message(self, message):
            # Live's status bar, at the bottom of the window.
            self.messages = getattr(self, 'messages', []) + [message]

        def _send_midi(self, midi_bytes):
            self.sent.append(tuple(midi_bytes))

        @contextlib.contextmanager
        def component_guard(self):
            yield

        def build_midi_map(self, midi_map_handle):
            pass

        def receive_midi(self, midi_bytes):
            self.forwarded_to_framework.append(tuple(midi_bytes))

        def refresh_state(self):
            pass

        def _on_selected_track_changed(self):
            pass

        def set_device_component(self, component):
            self._device_component = component

        def request_rebuild_midi_map(self):
            self.rebuilds = getattr(self, 'rebuilds', 0) + 1

        def schedule_message(self, delay, callback, parameter=None):
            pass

        def update_display(self):
            pass

        def disconnect(self):
            pass

    class InputControlElement(object):
        """What the pass-through elements touch: identifier, channel,
        suppress_script_forwarding, use_default_message."""
        created = []

        def __init__(self, msg_type, channel, identifier):
            self.msg_type = msg_type
            self.original = (identifier, channel)
            self.identifier, self.channel = identifier, channel
            self.suppress_script_forwarding = False
            InputControlElement.created.append(self)

        def set_identifier(self, value):
            self.identifier = value

        def set_channel(self, value):
            self.channel = value

        def use_default_message(self):
            self.identifier, self.channel = self.original

    class ButtonElement(InputControlElement):
        def __init__(self, is_momentary, msg_type, channel, identifier):
            InputControlElement.__init__(self, msg_type, channel, identifier)

    class SliderElement(InputControlElement):
        pass

    ice_module = types.ModuleType('_Framework.InputControlElement')
    ice_module.InputControlElement = InputControlElement
    ice_module.MIDI_NOTE_TYPE, ice_module.MIDI_CC_TYPE = 0, 1
    button_module = types.ModuleType('_Framework.ButtonElement')
    button_module.ButtonElement = ButtonElement
    slider_module = types.ModuleType('_Framework.SliderElement')
    slider_module.SliderElement = SliderElement
    sys.modules['_Framework.InputControlElement'] = ice_module
    sys.modules['_Framework.ButtonElement'] = button_module
    sys.modules['_Framework.SliderElement'] = slider_module

    cs_module = types.ModuleType('_Framework.ControlSurface')
    cs_module.ControlSurface = ControlSurface
    framework = types.ModuleType('_Framework')
    framework.ControlSurface = cs_module

    dc_module = types.ModuleType('_Framework.DeviceComponent')

    class DeviceComponent(object):
        """Only what MVave_SMC_KNOBS touches: a name, set_device, device()."""

        def __init__(self):
            self.name = None
            self._device = None

        def set_device(self, device):
            self._device = device

        def device(self):
            return self._device

    dc_module.DeviceComponent = DeviceComponent
    sys.modules['_Framework.DeviceComponent'] = dc_module

    sys.modules['Live'] = live
    sys.modules['Live.Clip'] = clip_module
    sys.modules['Live.MidiMap'] = midi_map
    sys.modules['_Framework'] = framework
    sys.modules['_Framework.ControlSurface'] = cs_module
    return midi_map


MIDI_MAP = install_stubs()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from MVave_SMC_STEPSEQ import MIDI_Map as C                                  # noqa: E402
from MVave_SMC_STEPSEQ.MVave_SMC_STEPSEQ import (MVave_SMC_STEPSEQ, decode_relative,    # noqa: E402
                                     lane_for_pad, step_at,
                                     VIEW_FOCUS, VIEW_OVERVIEW)

# The package, the module and the class all share one name -- the convention the
# other two scripts follow too -- and __init__.py binds the CLASS over the module
# in the package namespace. So `import MVave_SMC_STEPSEQ.MVave_SMC_STEPSEQ as m`
# hands back the class, not the module, and patching a flag on it silently misses.
# sys.modules is not shadowed, so it is the reliable handle.
SEQ_MODULE = sys.modules['MVave_SMC_STEPSEQ.MVave_SMC_STEPSEQ']

from MVave_SMC_KNOBS import MVave_SMC_KNOBS as _knobs_pkg                  # noqa: E402
KNOBS_MODULE = sys.modules['MVave_SMC_KNOBS.MVave_SMC_KNOBS']


# ------------------------------------------------- knob-script fixtures

class FakeParameter(object):
    """A device parameter that rejects an out-of-range write, as Live's does.

    Stored as a plain attribute this accepted writes the real
    Live.DeviceParameter setter raises on, so _adjust_macro's clamp could be
    deleted with the suite green -- and the exception that clamp exists to
    prevent disables the whole script from inside a MIDI callback.
    """

    def __init__(self, minimum, maximum, value=0.0, quantized=False):
        self.min, self.max = minimum, maximum
        self.is_quantized, self.is_enabled = quantized, True
        self._value = value

    def _get_value(self):
        return self._value

    def _set_value(self, new):
        if not (self.min <= new <= self.max):
            raise RuntimeError('value %r outside [%r, %r]' % (new, self.min, self.max))
        self._value = new

    value = property(_get_value, _set_value)


class FakeDevice(object):
    def __init__(self, parameters, name='Fake Rack'):
        self.parameters, self.name = parameters, name


def _fake_component(spelling, held):
    """A DeviceComponent that exposes its device in one of four ways.

    'method' and 'property' are the two _Framework spellings the script has to
    survive; 'private' is the fallback for a component with no public getter;
    'nothing' exposes none of them and must take the logged fallback.
    """
    if spelling == 'method':
        return type('M', (), {'device': lambda self: held})()
    if spelling == 'property':
        return type('P', (), {'device': property(lambda self: held)})()
    if spelling == 'private':
        obj = type('V', (), {})()
        obj._device = held
        return obj
    return type('N', (), {})()


# --------------------------------------------------------------------- helper

def note_on(channel, note, velocity=127):
    return (0x90 | channel, note, velocity)


def cc(channel, number, value):
    return (0xB0 | channel, number, value)


class SeqTest(unittest.TestCase):
    """Base: a loaded script with a bound four-beat clip."""

    # Most tests here are about geometry, not palette: they are written against
    # one teal note colour and the fixed LANE_COLORS rows. DrumColours turns it
    # back on to test the drum kinds themselves.
    DRUM_COLORS = False

    def setUp(self):
        self._drum_colors = SEQ_MODULE.DRUM_COLORS
        SEQ_MODULE.DRUM_COLORS = self.DRUM_COLORS
        self.addCleanup(setattr, SEQ_MODULE, 'DRUM_COLORS', self._drum_colors)
        MVave_SMC_STEPSEQ._active_instances = []
        self.c_instance = FakeCInstance()
        self.seq = MVave_SMC_STEPSEQ(self.c_instance)
        self.song = self.seq.song()
        self.clip = FakeClip(loop_start=0.0, loop_end=4.0)
        self.song.view.select(self.clip)
        self.seq.sent = []
        self.expect_logged_exception = False

    def tearDown(self):
        # _guarded logs and swallows, so without this an exception in any
        # callback is indistinguishable from success across the whole suite --
        # a test could "pass" purely because the code under it raised early and
        # the assertion it would have failed was never reached.
        if self.expect_logged_exception:
            return
        raised = [line for line in self.c_instance.log if 'exception in' in line]
        self.assertEqual(raised, [], 'a guarded callback raised: %s' % raised)

    def press(self, pad_index, velocity=127):
        self.seq.receive_midi(note_on(C.PAD_CHANNEL, C.PAD_NOTES[pad_index], velocity))
        self.seq.receive_midi(note_on(C.PAD_CHANNEL, C.PAD_NOTES[pad_index], 0))

    def button(self, number, down=None):
        """Press and release by default; down=True/False sends just one edge."""
        if down is None:
            self.button(number, True)
            self.button(number, False)
            return
        self.seq.receive_midi(note_on(C.BUTTON_CHANNEL, number, 127 if down else 0))

    def leds(self):
        """The colour last sent to each of the 16 pads, in reading order."""
        state = dict((note, None) for note in C.LED_NOTES)
        for status, note, velocity in self.seq.sent:
            if note in state:
                state[note] = velocity
        return [state[note] for note in C.LED_NOTES]

    def btn_led(self, note):
        """The velocity last sent to one button, or None if never written."""
        last = None
        for status, sent_note, velocity in self.seq.sent:
            if sent_note == note:
                last = velocity
        return last

    def btn_writes(self, note):
        return [v for _, n, v in self.seq.sent if n == note]


# ------------------------------------------------------------- pure functions

class PureFunctions(unittest.TestCase):

    def test_step_at_floors_rather_than_rounds(self):
        # A note nudged off the grid must light the step whose half-open window
        # contains it -- the same window remove_notes_extended() will clear.
        self.assertEqual(step_at(0.0, 0.0), 0)
        self.assertEqual(step_at(0.24, 0.0), 0)
        self.assertEqual(step_at(0.25, 0.0), 1)
        self.assertEqual(step_at(0.49, 0.0), 1)
        self.assertEqual(step_at(3.75, 0.0), 15)

    def test_step_at_is_relative_to_loop_start(self):
        self.assertEqual(step_at(4.0, 4.0), 0)
        self.assertEqual(step_at(4.5, 4.0), 2)

    def test_step_at_survives_float_error(self):
        # 0.25 * 3 is 0.7500000000000001 in binary floating point.
        self.assertEqual(step_at(0.25 * 3, 0.0), 3)
        for step in range(64):
            self.assertEqual(step_at(step * 0.25, 0.0), step)

    def test_lane_for_pad_is_drum_rack_oriented(self):
        # Bottom-left is the lowest note, ascending left to right then upward,
        # so the controller matches the rack on screen.
        self.assertEqual(lane_for_pad(12), 36)      # bottom-left
        self.assertEqual(lane_for_pad(15), 39)      # bottom-right
        self.assertEqual(lane_for_pad(0), 48)       # top-left
        self.assertEqual(lane_for_pad(3), 51)       # top-right

    def test_decode_relative_centre(self):
        self.assertEqual(decode_relative(65, 'centre'), 1)
        self.assertEqual(decode_relative(63, 'centre'), -1)
        self.assertEqual(decode_relative(64, 'centre'), 0)

    def test_decode_relative_twos_complement(self):
        self.assertEqual(decode_relative(1, 'twos'), 1)
        self.assertEqual(decode_relative(127, 'twos'), -1)
        self.assertEqual(decode_relative(0, 'twos'), 0)


# -------------------------------------------------------------------- writing

class Writing(SeqTest):

    def test_pad_writes_a_sixteenth_at_the_right_time(self):
        self.press(5)
        self.assertEqual(len(self.clip.notes), 1)
        note = self.clip.notes[0]
        self.assertEqual(note.pitch, C.DEFAULT_LANE)
        self.assertAlmostEqual(note.start_time, 5 * C.STEP)
        self.assertAlmostEqual(note.duration, C.STEP)
        # Velocity-sensitive pads: the strike sets it, not the default.
        self.assertEqual(note.velocity, 127)

    def test_pressing_twice_removes_the_note(self):
        self.press(5)
        self.press(5)
        self.assertEqual(self.clip.notes, [])

    def test_pad_release_writes_nothing(self):
        self.seq.receive_midi(note_on(C.PAD_CHANNEL, C.PAD_NOTES[5], 0))
        self.assertEqual(self.clip.notes, [])

    def test_a_step_past_the_loop_end_is_refused(self):
        self.clip.loop_end = 1.0        # four steps; pad 5 is past the end
        self.press(5)
        self.assertEqual(self.clip.notes, [])

    def test_toggle_clears_an_off_grid_note_in_the_same_window(self):
        self.clip.notes.append(FakeNote(C.DEFAULT_LANE, 5 * C.STEP + 0.05,
                                        C.STEP, 100))
        self.press(5)
        self.assertEqual(self.clip.notes, [])

    def test_strike_velocity_paints_the_step(self):
        # How hard you hit the pad is the velocity the step gets, Push-style.
        for pad, hit in ((0, 40), (1, 90), (2, 127)):
            self.press(pad, hit)
        self.assertEqual([n.velocity for n in self.clip.notes], [40, 90, 127])

    def test_the_knob_still_applies_when_there_is_no_strike(self):
        # USE_STRIKE_VELOCITY off, or a caller with no velocity to offer, falls
        # back to the painted default the knob adjusts.
        self.seq.receive_midi(cc(C.KNOB_CHANNEL, C.CC_VELOCITY, 63))
        self.seq.toggle_step(C.DEFAULT_LANE, 0)          # no velocity argument
        self.assertEqual(self.clip.notes[0].velocity, C.PAINT_VELOCITY - 1)

    def test_steps_default_to_velocity_4(self):
        # Before the controller reports its setting: 127, as VELOCITY 4 gives.
        self.assertEqual(C.PAINT_VELOCITY, C.VELOCITY_LEVELS[3])
        self.assertEqual(C.VELOCITY_LEVELS[3], 127)
        self.seq.toggle_step(C.DEFAULT_LANE, 0)
        self.assertEqual(self.clip.notes[0].velocity, 127)

    def test_the_velocity_setting_sets_the_step_velocity(self):
        # The lit pads strike 127 whatever the setting, so the setting wins.
        for setting, pad in ((0, 0), (1, 1), (2, 2), (3, 3)):
            self.seq.set_velocity_setting(setting)
            self.press(pad, 127)
        self.assertEqual([n.velocity for n in self.clip.notes],
                         list(C.VELOCITY_LEVELS))
        self.assertEqual(sorted(C.VELOCITY_LEVELS), list(C.VELOCITY_LEVELS))

    def test_the_velocity_setting_leaves_written_steps_alone(self):
        self.press(0)
        self.seq.set_velocity_setting(0)
        self.assertEqual(self.clip.notes[0].velocity, 127)

    def test_a_velocity_change_shows_in_the_status_bar(self):
        self.seq.set_velocity_setting(1)
        self.assertIn('velocity 70 (VELOCITY 2)', self.seq.messages[-1])

    def test_a_velocity_change_off_the_sequencer_is_quiet(self):
        self.seq.set_on_screen(False)
        self.seq.set_velocity_setting(0)
        self.assertEqual(getattr(self.seq, 'messages', []), [])
        self.press(0)
        self.assertEqual(self.clip.notes[0].velocity, C.VELOCITY_LEVELS[0])

    def test_strike_velocity_can_be_turned_off(self):
        # Patch the SEQUENCER module, not MIDI_Map. The script does
        # `from .MIDI_Map import *`, which copies the flag into its own namespace
        # at import time -- rebinding it on MIDI_Map afterwards reaches nothing.
        seqmod = SEQ_MODULE
        original = seqmod.USE_STRIKE_VELOCITY
        try:
            seqmod.USE_STRIKE_VELOCITY = False
            self.press(0, 40)
            self.assertEqual(self.clip.notes[0].velocity, C.PAINT_VELOCITY)
        finally:
            seqmod.USE_STRIKE_VELOCITY = original

    def test_writing_with_no_clip_bound_is_a_no_op(self):
        self.song.view.select(None)
        self.press(0)       # must not raise

    def test_a_mouse_edit_lights_the_pads(self):
        # The notes listener is the whole reason Ctrl+Z and mouse edits work.
        self.seq.sent = []
        self.clip.notes.append(FakeNote(C.DEFAULT_LANE, 2 * C.STEP, C.STEP, 100))
        self.clip._fire('notes')
        self.assertEqual(self.leds()[2], C.COLOR_STEP_ON)


# ------------------------------------------------------------------ rendering

class Rendering(SeqTest):

    def test_focus_view_lights_the_lane(self):
        self.press(0)
        self.press(4)
        self.press(8)
        self.seq.sent = []
        self.seq.refresh_state()
        lit = [i for i, colour in enumerate(self.leds())
               if colour == C.COLOR_STEP_ON]
        self.assertEqual(lit, [0, 4, 8])

    def test_notes_in_another_lane_are_not_shown(self):
        self.clip.notes.append(FakeNote(C.DEFAULT_LANE + 1, 0.0, C.STEP, 100))
        self.seq.sent = []
        self.seq.refresh_state()
        self.assertNotIn(C.COLOR_STEP_ON, self.leds())

    def test_only_changed_pads_are_sent(self):
        self.press(0)
        self.seq.sent = []
        self.press(1)
        # Pad 0 was already teal and pad 1 was already off, so exactly one pad
        # changes. The diff is what keeps this off the device's input buffer.
        self.assertEqual(len(self.seq.sent), 1)
        self.assertEqual(self.seq.sent[0][1], C.LED_NOTES[1])

    def test_leds_are_note_on_never_note_off(self):
        # A real note-off is ignored by this device, silently.
        self.press(0)
        self.press(0)
        for status, _note, _velocity in self.seq.sent:
            self.assertEqual(status & 0xF0, 0x90)

    def test_steps_beyond_the_loop_are_dark(self):
        self.clip.loop_end = 1.0        # four steps
        self.seq.sent = []
        self.seq.refresh_state()
        self.assertEqual(self.leds()[4:], [C.COLOR_STEP_OFF] * 12)

    def test_a_note_past_the_loop_end_is_not_lit(self):
        # Live keeps notes that sit outside the loop brace -- shortening a
        # pattern is enough to leave some -- and the 16-step read window
        # reaches them. Lighting one would promise a step that toggle_step
        # refuses: a lit pad that does nothing when pressed, which is exactly
        # what the floor-not-round rule exists to prevent.
        self.clip.loop_end = 1.0                    # four steps
        self.clip.notes.append(FakeNote(C.DEFAULT_LANE, 5 * C.STEP, C.STEP, 100))
        self.seq.sent = []
        self.seq.refresh_state()
        self.assertEqual(self.leds()[5], C.COLOR_STEP_OFF)

    def test_the_render_and_the_write_path_agree_on_the_last_step(self):
        # A loop length that is not a whole number of steps. [0, 4.3) contains
        # 18 steps, 0..17: step 17 starts at 4.25, inside the loop, so it must
        # both light AND accept a press. Step 18 starts at 4.5 and must do
        # neither. _step_count() rounding instead of ceiling made step 17 dark
        # and unwritable -- and half of all loop lengths lose their last step
        # that way, so this is the boundary the two gates have to share.
        self.clip.loop_end = 4.3
        self.button(C.BTN_RIGHT)                    # bank 1 -> steps 16-31
        self.press(1)                               # step 17, the last in loop
        self.assertEqual(len(self.clip.notes), 1)
        self.assertAlmostEqual(self.clip.notes[0].start_time, 17 * C.STEP)
        self.assertEqual(self.leds()[1], C.COLOR_STEP_ON)   # and it lights
        self.seq.toggle_step(C.DEFAULT_LANE, 18)    # starts at 4.5, outside
        self.assertEqual(len(self.clip.notes), 1)   # refused, nothing written

    def test_a_note_past_the_loop_end_is_not_lit_in_overview(self):
        # The same gate exists on both refresh paths and only the focus one was
        # covered, so the lit-pad-that-ignores-you defect was fully
        # reintroducible in overview with the suite green.
        self.clip.loop_end = 1.5                    # six steps: 0..5
        self.clip.notes.append(FakeNote(C.DEFAULT_LANE, 6 * C.STEP, C.STEP, 100))
        self.clip.notes.append(FakeNote(C.DEFAULT_LANE, 5 * C.STEP, C.STEP, 100))
        self.button(C.BTN_VIEW)                     # overview
        self.button(C.BTN_RIGHT)                    # page 1 -> steps 4-7
        self.button(C.BTN_RIGHT)                    # and again: page 1 is the last
        self.seq.sent = []
        self.seq.refresh_state()
        self.assertEqual(self.seq._page, 1)                 # _clamp_pages held it
        # Both directions. Gating on `total` renders step 5 and hides step 6;
        # gating on `total - 1` hides both, which is the off-by-one the focus
        # companion test is named for and could not see over here.
        # Lane 0 is the bottom row in overview: pads 12-15.
        self.assertEqual(self.leds()[13], C.LANE_COLORS[0])  # step 5, last in loop
        self.assertEqual(self.leds()[14], C.COLOR_STEP_OFF)  # step 6, past the loop

    def test_the_in_loop_gate_holds_when_empty_steps_are_marked(self):
        # COLOR_STEP_EMPTY ships as 0, the same byte as COLOR_STEP_OFF, so the
        # in-loop gate on the *empty* pass is unobservable under the default
        # palette -- deleting it is green. MIDI_Map.py explicitly invites
        # turning these markers on, at which point the gate starts mattering.
        seqmod = SEQ_MODULE
        original = seqmod.COLOR_STEP_EMPTY
        try:
            seqmod.COLOR_STEP_EMPTY = 40
            self.clip.loop_end = 1.0                # four steps: 0..3
            self.seq.sent = []
            self.seq.refresh_state()
            # Pad 1, not 0: step 0 is a beat and the beat marker overrides.
            self.assertEqual(self.leds()[1], 40)                # in loop, marked
            self.assertEqual(self.leds()[4], C.COLOR_STEP_OFF)  # out of loop, dark
        finally:
            seqmod.COLOR_STEP_EMPTY = original

    def test_a_note_on_the_last_step_of_a_whole_loop_lights(self):
        # The ordinary case the off-by-one would break: one bar, note on the
        # final 16th. Gating the render on `total - 1` renders it dark while
        # toggle_step still erases it.
        self.clip.notes.append(FakeNote(C.DEFAULT_LANE, 15 * C.STEP, C.STEP, 100))
        self.seq.sent = []
        self.seq.refresh_state()
        self.assertEqual(self.leds()[15], C.COLOR_STEP_ON)

    def test_disconnect_extinguishes_the_grid(self):
        self.press(0)
        self.seq.sent = []
        self.seq.disconnect()
        self.assertEqual(self.leds(), [0] * 16)


# ------------------------------------------------------------------- playhead

class Playhead(SeqTest):

    def test_a_sliver_of_a_final_step_does_not_bank_the_view(self):
        # A loop brace dragged off the grid leaves a last step holding a
        # fraction of a step's worth of in-loop time. Chasing it banks the view
        # there and back twice per cycle, tens of milliseconds apart, at
        # roughly double the LED traffic -- the burst this device's MIDI input
        # buffer does not survive (HARDWARE.md 3.5).
        self.clip.loop_end = self.clip.loop_start + 16 * C.STEP + C.STEP / 4.0
        self.seq.refresh_state()
        self.clip.play(16 * C.STEP)
        self.assertEqual(self.seq._bank, 0)

    def test_a_final_step_worth_following_is_followed(self):
        # The companion: a full step past the page boundary must still scroll,
        # or the gate has simply broken the follower.
        self.clip.loop_end = self.clip.loop_start + 18 * C.STEP
        self.seq.refresh_state()
        self.clip.play(16 * C.STEP)
        self.assertEqual(self.seq._bank, 1)

    def test_playhead_marks_the_current_step(self):
        self.seq.sent = []
        self.clip.play(2 * C.STEP)
        self.assertEqual(self.leds()[2], C.COLOR_PLAYHEAD)

    def test_playhead_over_an_active_step_is_highlighted(self):
        self.press(2)
        self.seq.sent = []
        self.clip.play(2 * C.STEP)
        self.assertEqual(self.leds()[2], C.COLOR_PLAYHEAD_ON)

    def test_playhead_within_one_step_sends_nothing(self):
        self.clip.play(2 * C.STEP)
        self.seq.sent = []
        self.clip.play(2 * C.STEP + 0.05)
        self.clip.play(2 * C.STEP + 0.15)
        # This listener fires per audio buffer; only a step change is work.
        self.assertEqual(self.seq.sent, [])

    def test_the_window_follows_the_playhead(self):
        # A 64-step loop needs no manual paging: the visible 16 are the ones
        # playing. This is the whole reason STEPS_MAX is no longer 32.
        self.clip.loop_end = self.clip.loop_start + 64 * C.STEP
        self.clip.notes.append(FakeNote(C.DEFAULT_LANE, 20 * C.STEP, C.STEP, 100))
        self.clip._fire('notes')
        self.assertEqual(self.seq._bank, 0)
        self.seq.sent = []
        self.clip.play(20 * C.STEP)
        self.assertEqual(self.seq._bank, 1)
        # Assert the PADS, not just _bank. _bank is set inside _scroll_to before
        # anything is drawn, so a follow that moved the window and then skipped
        # the clip read -- _paint() instead of _render() -- would satisfy the
        # bank assertion while the device showed bank 0's notes under bank 1's
        # playhead. That is the shape of the bug this test exists for.
        self.assertEqual(self.leds()[4], C.COLOR_PLAYHEAD_ON)
        self.clip.play(50 * C.STEP)
        self.assertEqual(self.seq._bank, 3)
        self.assertEqual(self.leds()[2], C.COLOR_PLAYHEAD)

    def test_the_window_follows_the_playhead_in_overview(self):
        # The overview half of _scroll_to had no test at all: the only overview
        # playhead test played step 1 on page 0, so the branch never ran.
        self.clip.loop_end = self.clip.loop_start + 64 * C.STEP
        self.clip.notes.append(FakeNote(C.DEFAULT_LANE, 6 * C.STEP, C.STEP, 100))
        self.button(C.BTN_VIEW)                 # overview
        self.seq.sent = []
        self.clip.play(6 * C.STEP)
        self.assertEqual(self.seq._page, 1)
        # The note matters: with an empty clip _paint() alone reproduces this
        # result, so the test could not tell a moved window from a re-read one.
        # COLOR_PLAYHEAD_ON is only reachable if the new page was read.
        self.assertEqual(self.leds()[14], C.COLOR_PLAYHEAD_ON)   # lane 0: bottom row
        self.assertEqual([self.leds()[i] for i in (2, 6, 10)],
                         [C.COLOR_PLAYHEAD] * 3)

    def test_paging_by_hand_stops_the_chase(self):
        self.clip.loop_end = self.clip.loop_start + 64 * C.STEP
        self.clip.play(20 * C.STEP)           # follows to bank 1
        self.button(C.BTN_LEFT)               # manual page -> stop following
        self.assertFalse(self.seq._follow)
        self.clip.play(50 * C.STEP)
        self.assertEqual(self.seq._bank, 0)   # stayed put

    def test_paging_back_onto_the_playhead_resumes_the_chase(self):
        # Otherwise the only way to re-arm while playing is to stop the
        # transport, which makes paging away a mode you cannot leave mid-jam.
        self.clip.loop_end = self.clip.loop_start + 64 * C.STEP
        self.clip.play(20 * C.STEP)               # follows to bank 1
        self.button(C.BTN_RIGHT)                  # page away -> stops following
        self.assertFalse(self.seq._follow)
        self.assertEqual(self.seq._bank, 2)
        self.button(C.BTN_LEFT)                   # back onto the playing page
        self.assertEqual(self.seq._bank, 1)
        self.assertTrue(self.seq._follow)
        self.clip.play(50 * C.STEP)               # and it chases again
        self.assertEqual(self.seq._bank, 3)

    def test_paging_away_holds_until_the_loop_comes_round(self):
        self.clip.loop_end = self.clip.loop_start + 64 * C.STEP
        self.clip.play(20 * C.STEP)
        self.button(C.BTN_RIGHT)
        self.button(C.BTN_RIGHT)                  # two pages from the playhead
        self.assertFalse(self.seq._follow)
        self.clip.play(50 * C.STEP)               # still playing forwards
        self.assertFalse(self.seq._follow)
        self.assertEqual(self.seq._bank, 3)       # stayed where you put it

    def test_the_loop_wrapping_resumes_the_chase(self):
        self.clip.loop_end = self.clip.loop_start + 64 * C.STEP
        self.clip.play(20 * C.STEP)
        self.button(C.BTN_RIGHT)
        self.assertFalse(self.seq._follow)
        self.clip.play(50 * C.STEP)
        self.assertFalse(self.seq._follow)
        self.clip.play(2 * C.STEP)                # wrapped: step went backwards
        self.assertTrue(self.seq._follow)
        self.assertEqual(self.seq._bank, 0)       # and snapped to the playhead

    def test_wrap_resume_can_be_switched_off(self):
        seqmod = SEQ_MODULE
        original = seqmod.FOLLOW_RESUMES_ON_WRAP
        try:
            seqmod.FOLLOW_RESUMES_ON_WRAP = False
            self.clip.loop_end = self.clip.loop_start + 64 * C.STEP
            self.clip.play(20 * C.STEP)
            self.button(C.BTN_RIGHT)
            self.clip.play(2 * C.STEP)            # wraps, but must not resume
            self.assertFalse(self.seq._follow)
        finally:
            seqmod.FOLLOW_RESUMES_ON_WRAP = original

    def test_paging_with_the_transport_stopped_leaves_follow_alone(self):
        # _playhead is None when stopped, so there is nothing to catch up to.
        self.assertIsNone(self.seq._playhead)
        self.button(C.BTN_RIGHT)
        self.assertFalse(self.seq._follow)

    def test_stopping_restores_the_chase(self):
        self.clip.loop_end = self.clip.loop_start + 64 * C.STEP
        self.clip.play(20 * C.STEP)
        self.button(C.BTN_LEFT)
        self.assertFalse(self.seq._follow)
        self.clip.stop()
        self.assertTrue(self.seq._follow)

    def test_playhead_clears_on_stop(self):
        self.clip.play(2 * C.STEP)
        self.seq.sent = []
        self.clip.stop()
        self.assertEqual(self.leds()[2], C.COLOR_STEP_OFF)

    def test_playhead_on_another_bank_is_not_drawn(self):
        self.clip.loop_end = 8.0        # 32 steps, so bank 1 exists
        self.button(C.BTN_RIGHT)
        self.seq.sent = []
        self.clip.play(2 * C.STEP)      # step 2 lives on bank 0
        self.assertNotIn(C.COLOR_PLAYHEAD, self.leds())


# ----------------------------------------------------------------- navigation

class Navigation(SeqTest):

    def setUp(self):
        SeqTest.setUp(self)
        self.clip.loop_end = 8.0        # 32 steps: two full banks

    def test_right_moves_to_steps_17_to_32(self):
        self.button(C.BTN_RIGHT)
        self.press(0)
        self.assertAlmostEqual(self.clip.notes[0].start_time, 16 * C.STEP)

    def test_banking_is_clamped_to_the_clip(self):
        self.clip.loop_end = 4.0        # one bank only
        self.button(C.BTN_RIGHT)
        self.press(0)
        self.assertAlmostEqual(self.clip.notes[0].start_time, 0.0)

    def test_left_cannot_go_below_the_first_bank(self):
        self.button(C.BTN_LEFT)
        self.press(0)
        self.assertAlmostEqual(self.clip.notes[0].start_time, 0.0)

    def test_mod_pad_selects_a_lane(self):
        self.button(C.BTN_MOD, down=True)
        self.press(15)                  # bottom-right -> 39
        self.button(C.BTN_MOD, down=False)
        self.press(0)
        self.assertEqual(self.clip.notes[0].pitch, 39)

    def test_mod_pad_does_not_write_a_step(self):
        self.button(C.BTN_MOD, down=True)
        self.press(0)
        self.assertEqual(self.clip.notes, [])

    def test_holding_mod_shows_the_lane_picker(self):
        # The lane you are editing is white; drums with notes are teal, the
        # rest dark. Pad 12 is bottom-left, 36: the default lane.
        self.clip.notes.append(FakeNote(38, 0.0, C.STEP, 100))     # pad 14
        self.clip.notes.append(FakeNote(C.DEFAULT_LANE, 0.0, C.STEP, 100))
        self.clip._fire('notes')
        self.button(C.BTN_MOD, True)
        leds = self.leds()
        self.assertEqual(leds[12], C.COLOR_PICK_SELECTED)
        self.assertEqual(leds[14], C.COLOR_PICK_NOTES)
        self.assertEqual(leds[0], C.COLOR_STEP_OFF)
        # Releasing brings the steps back: step 0 of lane 36 is lit.
        self.button(C.BTN_MOD, False)
        self.assertEqual(self.leds()[0], C.COLOR_STEP_ON)
        self.assertEqual(self.leds()[12], self.seq._empty_color(12))
        self.assertEqual(self.seq._led[13], C.COLOR_STEP_OFF)  # never lit

    def test_picking_a_lane_moves_the_white_pad(self):
        self.button(C.BTN_MOD, True)
        self.press(15)                                  # -> 39
        leds = self.leds()
        self.assertEqual(leds[15], C.COLOR_PICK_SELECTED)
        self.assertNotEqual(leds[12], C.COLOR_PICK_SELECTED)
        self.button(C.BTN_MOD, False)

    def test_the_picker_shows_loaded_rack_pads(self):
        rack = FakeDrumRack({37: FakeDrumPad(37, [FakeDevice([], 'Snare')])})
        self.song.view.selected_track = FakeTrack([rack])
        self.button(C.BTN_MOD, True)
        self.assertEqual(self.leds()[13], C.COLOR_PICK_LOADED)
        self.button(C.BTN_MOD, False)

    def test_the_picker_finds_a_kit_inside_another_rack(self):
        rack = FakeDrumRack({37: FakeDrumPad(37, [FakeDevice([], 'Snare')])})
        outer = type('Rack', (), {'can_have_chains': True, 'name': 'Rack',
                                  'chains': [FakeChain([rack])]})()
        self.song.view.selected_track = FakeTrack([outer])
        self.button(C.BTN_MOD, True)
        self.assertEqual(self.leds()[13], C.COLOR_PICK_LOADED)
        self.button(C.BTN_MOD, False)

    def test_the_picker_reads_the_clips_track_not_the_selected_one(self):
        # The clip plays on in the background while another track is selected.
        rack = FakeDrumRack({37: FakeDrumPad(37, [FakeDevice([], 'Snare')])})
        kit = FakeTrack([rack])
        self.clip.canonical_parent = type('Slot', (), {
            'has_clip': True, 'canonical_parent': kit})()
        self.song.view.selected_track = FakeTrack([])
        self.button(C.BTN_MOD, True)
        self.assertEqual(self.leds()[13], C.COLOR_PICK_LOADED)
        self.button(C.BTN_MOD, False)

    def test_the_picker_hides_the_playhead(self):
        self.clip.play(12 * C.STEP)
        self.button(C.BTN_MOD, True)
        self.assertEqual(self.leds()[12], C.COLOR_PICK_SELECTED)
        self.clip.play(13 * C.STEP)
        self.assertNotIn(C.COLOR_PLAYHEAD, self.leds())
        self.button(C.BTN_MOD, False)
        self.assertEqual(self.leds()[13], C.COLOR_PLAYHEAD)

    def _kit(self, *pitches):
        pads = dict((p, FakeDrumPad(p, [FakeDevice([], 'Drum')])) for p in pitches)
        self.song.view.selected_track = FakeTrack([FakeDrumRack(pads)])

    def test_the_picker_stops_at_the_edge_of_the_kit(self):
        # A 16-pad kit on 36-51: the next bank up would be all dark.
        self._kit(*range(36, 52))
        self.button(C.BTN_MOD, True)
        self.button(C.BTN_VIEW, True)             # Record + Stop: lane bank
        self.button(C.BTN_RIGHT)
        self.assertEqual(self.seq._lane_base, 36)
        self.assertIn('No more drums above D#2', self.seq.messages[-1])
        self.button(C.BTN_LEFT)
        self.assertEqual(self.seq._lane_base, 36)
        self.assertIn('No more drums below C1', self.seq.messages[-1])
        self.button(C.BTN_VIEW, False)
        self.button(C.BTN_MOD, False)

    def test_the_picker_skips_an_empty_bank(self):
        self._kit(36, 70)                       # 52-67 empty, 68-83 has a sound
        self.button(C.BTN_MOD, True)
        self.button(C.BTN_VIEW, True)             # Record + Stop: lane bank
        self.button(C.BTN_RIGHT)
        self.assertEqual(self.seq._lane_base, 68)
        self.button(C.BTN_LEFT)
        self.assertEqual(self.seq._lane_base, 36)
        self.button(C.BTN_VIEW, False)
        self.button(C.BTN_MOD, False)

    def test_notes_or_the_lane_keep_a_bank_reachable(self):
        self._kit(*range(36, 52))
        self.clip.notes.append(FakeNote(60, 0.0, C.STEP, 100))   # bank 52-67
        self.button(C.BTN_MOD, True)
        self.button(C.BTN_VIEW, True)             # Record + Stop: lane bank
        self.button(C.BTN_RIGHT)
        self.assertEqual(self.seq._lane_base, 52)
        self.seq._lane = 90                     # e.g. picked before the kit changed
        self.button(C.BTN_RIGHT)
        self.assertEqual(self.seq._lane_base, 84)
        self.button(C.BTN_VIEW, False)
        self.button(C.BTN_MOD, False)

    def test_mod_arrows_change_the_clip_length_by_a_bar(self):
        # Navigation's clip is 32 steps.
        self.button(C.BTN_MOD, True)
        self.button(C.BTN_RIGHT)
        self.assertAlmostEqual(self.clip.loop_end, 48 * C.STEP)
        self.assertIn('Clip length 3 bars (48 steps)', self.seq.messages[-1])
        self.button(C.BTN_LEFT)
        self.button(C.BTN_LEFT)
        self.assertAlmostEqual(self.clip.loop_end, 16 * C.STEP)
        self.assertEqual(self.seq._lane_base, C.LANE_SELECT_BASE)  # untouched
        self.button(C.BTN_MOD, False)

    def test_the_clip_length_snaps_to_whole_bars(self):
        self.clip.loop_end = 20 * C.STEP
        self.button(C.BTN_MOD, True)
        self.button(C.BTN_LEFT)
        self.assertAlmostEqual(self.clip.loop_end, 16 * C.STEP)
        self.clip.loop_end = 20 * C.STEP
        self.button(C.BTN_RIGHT)
        self.assertAlmostEqual(self.clip.loop_end, 32 * C.STEP)
        self.button(C.BTN_MOD, False)

    def test_the_clip_length_stops_at_one_bar_and_at_steps_max(self):
        self.clip.loop_end = 16 * C.STEP
        self.button(C.BTN_MOD, True)
        self.button(C.BTN_LEFT)
        self.assertAlmostEqual(self.clip.loop_end, 16 * C.STEP)
        self.assertIn('the shortest', self.seq.messages[-1])
        self.assertNotEqual(self.btn_led(C.BTN_LEFT), C.BTN_LED_ON)
        self.assertEqual(self.btn_led(C.BTN_RIGHT), C.BTN_LED_ON)
        self.clip.loop_end = C.STEPS_MAX * C.STEP
        self.clip.end_marker = self.clip.loop_end
        self.button(C.BTN_RIGHT)
        self.assertAlmostEqual(self.clip.loop_end, C.STEPS_MAX * C.STEP)
        self.assertIn('the longest', self.seq.messages[-1])
        self.button(C.BTN_MOD, False)

    def test_mod_stop_arrows_do_not_switch_the_view(self):
        self.button(C.BTN_MOD, True)
        self.button(C.BTN_VIEW, True)
        self.button(C.BTN_RIGHT)
        self.button(C.BTN_VIEW, False)
        self.button(C.BTN_MOD, False)
        self.assertEqual(self.seq._view, VIEW_FOCUS)
        self.assertAlmostEqual(self.clip.loop_end, 8.0)            # length kept

    def test_without_a_drum_rack_every_bank_is_reachable(self):
        self.button(C.BTN_MOD, True)
        self.button(C.BTN_VIEW, True)             # Record + Stop: lane bank
        self.button(C.BTN_RIGHT)
        self.assertEqual(self.seq._lane_base, 52)
        self.button(C.BTN_VIEW, False)
        self.button(C.BTN_MOD, False)

    def test_the_status_bar_names_the_lane(self):
        self.button(C.BTN_MOD, True)
        self.button(C.BTN_VIEW, True)             # Record + Stop: lane bank
        self.assertIn('Lane C1 (36)', self.seq.messages[-1])
        self.assertIn('C1-D#2', self.seq.messages[-1])
        self.press(13)                                  # -> 37
        self.assertIn('Lane C#1 (37)', self.seq.messages[-1])
        self.button(C.BTN_RIGHT)                        # picker bank up
        self.assertIn('E2-G3', self.seq.messages[-1])
        self.button(C.BTN_VIEW, False)
        self.button(C.BTN_MOD, False)

    def test_lane_knob_scrolls(self):
        self.seq.receive_midi(cc(C.KNOB_CHANNEL, C.CC_LANE, 65))
        self.press(0)
        self.assertEqual(self.clip.notes[0].pitch, C.DEFAULT_LANE + 1)

    def test_length_knob_sets_the_loop(self):
        self.seq.receive_midi(cc(C.KNOB_CHANNEL, C.CC_LENGTH, 63))
        self.assertAlmostEqual(self.clip.loop_end, 8.0 - C.STEP)

    def test_length_knob_repaints_the_grid(self):
        # The fake does not fire loop listeners on a programmatic write, and a
        # real Live may not either -- so _set_length's own render is what covers
        # the knob path, separately from the mouse-drag listener.
        self.clip.loop_end = 4.0                # 16 steps (Navigation gives 32)
        self.clip.notes.append(FakeNote(C.DEFAULT_LANE, 12 * C.STEP, C.STEP, 100))
        self.clip._fire('notes')
        self.assertEqual(self.leds()[12], C.COLOR_STEP_ON)
        self.seq.sent = []
        for _ in range(8):
            self.seq.receive_midi(cc(C.KNOB_CHANNEL, C.CC_LENGTH, 63))  # -> 8 steps
        self.assertEqual(self.leds()[12], C.COLOR_STEP_OFF)

    def test_length_knob_will_not_shrink_below_one_step(self):
        for _ in range(64):
            self.seq.receive_midi(cc(C.KNOB_CHANNEL, C.CC_LENGTH, 63))
        self.assertAlmostEqual(self.clip.loop_end, C.STEP)

    def test_length_knob_keeps_the_end_marker_ahead_of_the_loop(self):
        self.clip.loop_end = 1.0
        self.clip.end_marker = 1.0
        self.seq.receive_midi(cc(C.KNOB_CHANNEL, C.CC_LENGTH, 65))
        self.assertGreaterEqual(self.clip.end_marker, self.clip.loop_end)

    def test_encoder_cc_arrives_the_same_way_from_a_sibling_script(self):
        self.seq.handle_encoder_cc(C.CC_LANE, 65)
        self.press(0)
        self.assertEqual(self.clip.notes[0].pitch, C.DEFAULT_LANE + 1)


# ---------------------------------------------------------------------- views

class Views(SeqTest):

    def setUp(self):
        SeqTest.setUp(self)
        self.clip.loop_end = 8.0
        self.button(C.BTN_VIEW)

    def test_overview_maps_rows_to_lanes_and_columns_to_steps(self):
        self.press(4 + 2)               # row 1 from the top, col 2
        note = self.clip.notes[0]
        self.assertEqual(note.pitch, C.DEFAULT_LANE + 2)
        self.assertAlmostEqual(note.start_time, 2 * C.STEP)

    def test_overview_colours_rows_by_lane(self):
        self.press(12)                  # bottom row: the lowest lane
        self.press(8)                   # the row above it
        self.seq.sent = []
        self.seq.refresh_state()
        leds = self.leds()
        self.assertEqual(leds[12], C.LANE_COLORS[0])
        self.assertEqual(leds[8], C.LANE_COLORS[1])

    def test_overview_puts_the_lowest_lane_on_the_bottom_row(self):
        # Matches Live's piano roll, where the kick sits at the bottom.
        self.press(12)
        self.assertEqual(self.clip.notes[0].pitch, C.DEFAULT_LANE)
        self.press(1)
        self.assertEqual(self.clip.notes[1].pitch, C.DEFAULT_LANE + 3)

    def test_overview_pages_four_steps_at_a_time(self):
        self.button(C.BTN_RIGHT)
        self.press(0)
        self.assertAlmostEqual(self.clip.notes[0].start_time, 4 * C.STEP)

    def test_overview_playhead_lights_the_whole_column(self):
        self.seq.sent = []
        self.clip.play(1 * C.STEP)
        leds = self.leds()
        self.assertEqual([leds[1], leds[5], leds[9], leds[13]],
                         [C.COLOR_PLAYHEAD] * 4)

    def test_view_toggle_keeps_the_musical_position(self):
        # Focus bank 1 covers steps 16-31; overview page 4 starts at step 16.
        self.button(C.BTN_VIEW)         # back to focus
        self.button(C.BTN_RIGHT)        # bank 1
        self.button(C.BTN_VIEW)         # overview again
        self.press(0)
        self.assertAlmostEqual(self.clip.notes[0].start_time, 16 * C.STEP)

    def test_mod_arrows_move_the_lane_picker_bank(self):
        # MOD + pad only reaches 16 pitches from _lane_base, and a drum rack
        # has more rows than that, so the arrows bank the picker while held.
        base = self.seq._lane_base
        self.button(C.BTN_MOD, True)
        self.button(C.BTN_VIEW, True)             # Record + Stop: lane bank
        self.button(C.BTN_RIGHT)
        self.assertEqual(self.seq._lane_base, base + 16)
        self.button(C.BTN_LEFT)
        self.button(C.BTN_LEFT)
        self.assertEqual(self.seq._lane_base, base - 16)
        self.button(C.BTN_VIEW, False)
        self.button(C.BTN_MOD, False)

    def test_the_lane_base_starts_inside_the_range_the_picker_derives(self):
        # _lane_base is a DERIVED value -- every later write is
        # _clamp(LANE_SELECT_BASE + 16 * bank, 0, 112) -- so the constructor has
        # to apply the same clamp. Writing the raw constant left any
        # LANE_SELECT_BASE above 112 starting out of range, and MOD + pad then
        # selected pitches past 127, which toggle_step refuses in silence.
        seqmod = SEQ_MODULE
        original = seqmod.LANE_SELECT_BASE
        try:
            seqmod.LANE_SELECT_BASE = 120
            fresh = MVave_SMC_STEPSEQ(FakeCInstance())
            self.assertLessEqual(fresh._lane_base, 112)
            self.assertLessEqual(lane_for_pad(0, fresh._lane_base), 127)
        finally:
            seqmod.LANE_SELECT_BASE = original

    def test_the_lane_picker_reaches_every_pitch_and_keeps_its_series(self):
        # Two properties at once, because the two obvious implementations each
        # give up one of them. The end stops must reach pitch 0 and 112, since
        # MOD + pad is the only lane control this hardware can offer; and
        # stepping back off a stop must return to the original 16-pitch series
        # rather than stranding the picker on 0+16k with 36 unreachable.
        self.button(C.BTN_MOD, True)
        self.button(C.BTN_VIEW, True)             # Record + Stop: lane bank
        for _ in range(8):
            self.button(C.BTN_LEFT)             # walk into the bottom stop
        self.assertEqual(self.seq._lane_base, 0)            # pitches 0-15
        for _ in range(3):
            self.button(C.BTN_RIGHT)
        self.assertEqual(self.seq._lane_base, C.LANE_SELECT_BASE)   # back on series
        for _ in range(5):
            self.button(C.BTN_RIGHT)            # walk into the top stop
        self.assertEqual(self.seq._lane_base, 112)          # pitches 112-127
        self.button(C.BTN_VIEW, False)
        self.button(C.BTN_MOD, False)

    def test_mod_arrows_do_not_page_steps(self):
        self.seq._bank = 0
        self.button(C.BTN_MOD, True)
        self.button(C.BTN_RIGHT)
        self.assertEqual(self.seq._bank, 0)
        self.button(C.BTN_MOD, False)

    def test_lane_picker_follows_its_bank(self):
        self.button(C.BTN_MOD, True)
        self.button(C.BTN_VIEW, True)             # Record + Stop: lane bank
        self.button(C.BTN_RIGHT)              # base += 16
        self.press(0)                         # MOD + pad 0
        self.button(C.BTN_VIEW, False)
        self.button(C.BTN_MOD, False)
        self.assertEqual(self.seq._lane,
                         lane_for_pad(0, C.LANE_SELECT_BASE + 16))

    def test_mod_pad_scrolls_the_lane_window_into_view(self):
        self.button(C.BTN_MOD, down=True)
        self.press(12)                  # bottom-left -> 36, bottom row of window
        self.button(C.BTN_MOD, down=False)
        self.press(12)
        self.assertEqual(self.clip.notes[0].pitch, lane_for_pad(12))


class DeviceNavigation(SeqTest):
    """VIEW + arrows move the blue hand; a plain VIEW tap still flips the grid."""

    def setUp(self):
        SeqTest.setUp(self)
        self.tom = FakeDevice([], 'Hi Tom')
        self.kick = FakeDevice([], 'Kick')
        self.rack = FakeDrumRack({50: FakeDrumPad(50, [self.tom]),
                                  36: FakeDrumPad(36, [self.kick])})
        self.after = FakeDevice([], 'Reverb')
        track = FakeTrack([self.rack, self.after])
        self.song.view.selected_track = track
        self.view = self.song.view

    def pick(self, pad_index):
        self.button(C.BTN_MOD, down=True)
        self.press(pad_index)
        self.button(C.BTN_MOD, down=False)

    def view_arrow(self, arrow):
        self.button(C.BTN_VIEW, down=True)
        self.button(arrow)
        self.button(C.BTN_VIEW, down=False)

    def test_picking_a_lane_selects_its_drum_pad(self):
        self.pick(2)                        # top row, third pad -> 50
        self.assertIs(self.rack.view.selected_drum_pad, self.rack.drum_pads[50])

    def test_view_right_steps_into_the_picked_drum_then_on(self):
        self.pick(2)
        self.view_arrow(C.BTN_RIGHT)
        self.assertIs(self.view.selected_device, self.tom)
        self.view_arrow(C.BTN_RIGHT)
        self.assertIs(self.view.selected_device, self.after)
        self.view_arrow(C.BTN_RIGHT)        # stops at the end, no wrap
        self.assertIs(self.view.selected_device, self.after)
        self.view_arrow(C.BTN_LEFT)
        self.view_arrow(C.BTN_LEFT)
        self.assertIs(self.view.selected_device, self.rack)

    def test_view_arrow_neither_flips_the_view_nor_pages(self):
        self.clip.loop_end = 8.0            # two banks, so paging could move
        self.view_arrow(C.BTN_RIGHT)
        self.assertEqual(self.seq._view, VIEW_FOCUS)
        self.assertEqual(self.seq._bank, 0)

    def test_a_view_tap_still_flips_the_view(self):
        self.button(C.BTN_VIEW, down=True)
        self.assertEqual(self.seq._view, VIEW_FOCUS)    # not until release
        self.button(C.BTN_VIEW, down=False)
        self.assertEqual(self.seq._view, VIEW_OVERVIEW)


class OffsetLoop(SeqTest):
    """Every core guarantee again, on a clip whose loop does not start at zero.

    Every other clip in this file is built `loop_start=0.0`, which made six of
    the seven places the script reads `loop_start` invisible: dropping it from
    `toggle_step`, `_step_count`, `_on_playhead`, `_set_length` or either read
    window left the suite green while the pads wrote and drew at the wrong beat.
    Dragging the front of the brace in is an entirely ordinary thing to do.
    """

    def setUp(self):
        SeqTest.setUp(self)
        self.clip = FakeClip(loop_start=1.0, loop_end=5.0)      # 16 steps
        self.song.view.select(self.clip)
        self.seq.sent = []

    def test_a_pad_writes_relative_to_the_loop_start(self):
        self.press(3)
        self.assertAlmostEqual(self.clip.notes[0].start_time, 1.0 + 3 * C.STEP)

    def test_the_step_count_is_relative_to_the_loop_start(self):
        self.assertEqual(self.seq._step_count(), 16)

    def test_a_note_lights_the_pad_its_own_offset_names(self):
        # Step 14 sits at beat 4.5 -- inside [1.0, 5.0) but OUTSIDE the [0, 4.0)
        # window a loop_start-blind read would use. A note near the start of the
        # loop falls in both windows and so cannot see that mutation at all.
        self.clip.notes.append(FakeNote(C.DEFAULT_LANE, 1.0 + 14 * C.STEP, C.STEP, 100))
        self.seq.sent = []
        self.seq.refresh_state()
        self.assertEqual(self.leds()[14], C.COLOR_STEP_ON)

    def test_the_overview_read_window_is_relative_to_the_loop_start(self):
        # The overview read window has its own copy of the offset, and the
        # focus tests above cannot see it.
        self.clip.notes.append(FakeNote(C.DEFAULT_LANE, 1.0 + 2 * C.STEP, C.STEP, 100))
        self.button(C.BTN_VIEW)                 # overview
        self.seq.sent = []
        self.seq.refresh_state()
        self.assertEqual(self.leds()[14], C.LANE_COLORS[0])     # lane 0: bottom row

    def test_the_playhead_is_relative_to_the_loop_start(self):
        self.clip.play(1.0 + 2 * C.STEP)
        self.assertEqual(self.leds()[2], C.COLOR_PLAYHEAD)

    def test_the_length_knob_measures_from_the_loop_start(self):
        self.seq.receive_midi(cc(C.KNOB_CHANNEL, C.CC_LENGTH, 63))      # 16 -> 15
        self.assertAlmostEqual(self.clip.loop_end, 1.0 + 15 * C.STEP)


# ------------------------------------------------------------------ lifecycle

class Lifecycle(SeqTest):

    def test_selecting_another_clip_rebinds(self):
        other = FakeClip(loop_start=0.0, loop_end=4.0)
        self.song.view.select(other)
        self.press(3)
        self.assertEqual(len(other.notes), 1)
        self.assertEqual(self.clip.notes, [])

    def test_the_old_clip_keeps_no_listeners(self):
        self.song.view.select(FakeClip())
        self.assertFalse(self.clip.notes_has_listener(self.seq._on_notes_changed))
        self.assertFalse(self.clip.playing_position_has_listener(self.seq._on_playhead))

    def test_a_deleted_clip_does_not_take_the_script_down(self):
        # Live goes on calling our listeners for a moment after the clip dies,
        # and a dead LOM object raises on any attribute access. Every entry
        # point has to survive that, log it, and carry on.
        self.expect_logged_exception = True
        self.clip.dead = True
        self.seq._on_playhead()             # guarded listener
        self.seq._on_notes_changed()        # guarded listener
        self.seq.refresh_state()            # the entry point the guard is for
        self.press(0)                       # receive_midi -> toggle_step
        self.song.view.select(None)         # rebind away from the corpse
        self.assertIsNone(self.seq._clip)
        self.assertTrue(any('exception in' in line
                            for line in self.c_instance.log))

    def test_dragging_the_loop_brace_clamps_the_visible_page(self):
        # The brace moves with no note change, so the notes listener stays
        # silent and only a loop listener sees it. Without one the grid keeps
        # showing a page the loop no longer has, and every pad on it is
        # refused without writing -- so nothing repaints it either.
        self.clip.loop_end = self.clip.loop_start + 32 * C.STEP
        self.clip.notes.append(FakeNote(C.DEFAULT_LANE, 20 * C.STEP, C.STEP, 100))
        self.clip._fire('notes')
        self.button(C.BTN_RIGHT)                        # look at steps 17-32
        self.assertEqual(self.seq._bank, 1)
        self.assertEqual(self.leds()[4], C.COLOR_STEP_ON)   # step 20 is lit
        self.seq.sent = []
        self.clip.set_loop_end(self.clip.loop_start + 16 * C.STEP)
        self.assertEqual(self.seq._bank, 0)
        # Asserting _bank alone was the exact flaw this suite calls out in the
        # old playhead test: _clamp_pages moves it before anything is drawn, so
        # dropping the _render() from _on_loop_changed stayed green while the
        # device kept showing a page the loop no longer has.
        # Step 4 of bank 0 is empty: a beat marker, not bank 1's note.
        self.assertEqual(self.leds()[4], self.seq._empty_color(4))

    def test_shortening_the_loop_under_the_playhead_drops_it(self):
        # _on_playhead range-checks a step only when it moves, so a brace
        # dragged in under a playing step is the loop listener's to clear --
        # or the playhead stays painted on a pad past the loop end until the
        # next step change, and following stays off if paging had stopped it.
        self.clip.play(10 * C.STEP)
        self.assertEqual(self.leds()[10], C.COLOR_PLAYHEAD)
        self.seq._follow = False
        self.clip.set_loop_end(self.clip.loop_start + 8 * C.STEP)
        self.assertIsNone(self.seq._playhead)
        self.assertEqual(self.leds()[10], C.COLOR_STEP_OFF)
        self.assertEqual(self.seq._follow, C.FOLLOW_PLAYHEAD)
        self.clip.play(10 * C.STEP + 0.01)              # Live not yet wrapped
        self.assertIsNone(self.seq._playhead)

    def test_dragging_the_front_of_the_loop_redraws(self):
        # loop_start moves both the step count and the absolute time every index
        # maps to, and it fires only the loop_start listener -- so dropping that
        # half of LOOP_PROPERTIES has to fail something.
        self.clip.notes.append(FakeNote(C.DEFAULT_LANE, 2 * C.STEP, C.STEP, 100))
        self.clip._fire('notes')
        self.assertEqual(self.leds()[2], C.COLOR_STEP_ON)
        self.seq.sent = []
        self.clip.set_loop_start(2 * C.STEP)            # loop is now [0.5, 4.0)
        self.assertEqual(self.leds()[0], C.COLOR_STEP_ON)   # the note is step 0 now

    def test_the_loop_listeners_are_released_with_the_clip(self):
        # assertTrue first: assertFalse alone is trivially satisfied by a
        # listener that was never attached, which is how half of
        # LOOP_PROPERTIES could be dropped with this test still green.
        self.assertTrue(self.clip.loop_end_has_listener(self.seq._on_loop_changed))
        self.assertTrue(self.clip.loop_start_has_listener(self.seq._on_loop_changed))
        self.song.view.select(FakeClip())
        self.assertFalse(self.clip.loop_end_has_listener(self.seq._on_loop_changed))
        self.assertFalse(self.clip.loop_start_has_listener(self.seq._on_loop_changed))

    def test_an_audio_clip_is_not_bound(self):
        self.song.view.select(FakeClip(is_midi=False))
        self.assertIsNone(self.seq._clip)

    def test_a_pre_live_11_clip_is_refused_loudly(self):
        self.song.view.select(PreLive11Clip())
        self.assertIsNone(self.seq._clip)
        self.assertTrue(any('get_notes_extended' in line
                            for line in self.c_instance.log))

    def test_disconnect_releases_the_song_listeners(self):
        self.seq.disconnect()
        view = self.song.view
        self.assertFalse(view.detail_clip_has_listener(self.seq._on_selection_changed))
        self.assertFalse(view.selected_track_has_listener(self.seq._on_selection_changed))

    def test_disconnect_twice_does_not_raise(self):
        self.seq.disconnect()
        self.seq.disconnect()


# ----------------------------------------------------------------------- midi

class MidiPlumbing(SeqTest):

    def test_every_control_is_forwarded(self):
        MIDI_MAP.forwarded = []
        self.seq.build_midi_map('map')
        forwarded = set(MIDI_MAP.forwarded)
        for note in C.PAD_NOTES:
            self.assertIn(('note', C.PAD_CHANNEL, note), forwarded)
        for number in (C.BTN_LEFT, C.BTN_RIGHT, C.BTN_MOD, C.BTN_VIEW):
            self.assertIn(('note', C.BUTTON_CHANNEL, number), forwarded)
        self.assertIn(('cc', C.KNOB_CHANNEL, C.CC_LANE), forwarded)

    def test_unowned_midi_goes_back_to_the_framework(self):
        # Swallowing it is a documented silent failure in this repo.
        stray = (0x90, 60, 100)
        self.seq.receive_midi(stray)
        self.assertIn(stray, self.seq.forwarded_to_framework)

    def test_unmapped_midi_is_named_once(self):
        for _ in range(5):
            self.seq.receive_midi((0x90, 60, 100))
        lines = [line for line in self.c_instance.log if 'unmapped' in line]
        self.assertEqual(len(lines), 1)
        self.assertIn('60', lines[0])

    def test_a_broken_callback_is_logged_not_fatal(self):
        # An uncaught exception in a listener disables the whole script until
        # Live restarts, so every callback is wrapped.
        self.expect_logged_exception = True
        self.clip.get_notes_extended = lambda *a: 1 / 0
        self.clip._fire('notes')        # must not raise
        self.assertTrue(any('exception in notes listener' in line
                            for line in self.c_instance.log))

    def test_the_exception_log_is_latched_but_still_hears_a_new_fault(self):
        # The latch is what stops a per-audio-buffer fault writing ~90
        # tracebacks a second and burying the first. Keyed too coarsely it
        # would silently swallow a second, different fault -- and since the
        # suite's whole backstop is tearDown reading 'exception in' lines,
        # that would blind the suite as well as Log.txt.
        self.expect_logged_exception = True
        self.clip.get_notes_extended = lambda *a: 1 / 0
        self.clip._fire('notes')
        self.clip._fire('notes')
        lines = [l for l in self.c_instance.log if 'exception in notes listener' in l]
        self.assertEqual(len(lines), 1)         # the repeat is latched

        def different(*a):
            raise RuntimeError('a different fault entirely')
        self.clip.get_notes_extended = different
        self.clip._fire('notes')
        lines = [l for l in self.c_instance.log if 'exception in notes listener' in l]
        self.assertEqual(len(lines), 2)         # but a new one is still heard

    def test_play_launches_the_bound_clip(self):
        self.button(C.BTN_PLAY)
        self.assertEqual(self.clip.fired, 1)
        self.assertTrue(self.clip.is_triggered)

    def test_play_on_a_playing_clip_stops_it(self):
        self.clip.play(0.0)
        self.button(C.BTN_PLAY)
        self.assertFalse(self.clip.is_playing)
        self.assertEqual(self.clip.fired, 0)

    def test_play_on_a_queued_clip_cancels_the_launch(self):
        self.button(C.BTN_PLAY)
        self.button(C.BTN_PLAY)
        self.assertEqual(self.clip.fired, 1)
        self.assertFalse(self.clip.is_triggered)

    def test_mod_play_toggles_the_transport_and_leaves_the_clip(self):
        self.button(C.BTN_MOD, True)
        self.button(C.BTN_PLAY)
        self.assertTrue(self.song.is_playing)
        self.button(C.BTN_PLAY)
        self.assertFalse(self.song.is_playing)
        self.button(C.BTN_MOD, False)
        self.assertEqual(self.clip.fired, 0)

    def test_play_with_no_clip_toggles_the_transport(self):
        self.song.view.select(None)
        self.button(C.BTN_PLAY)
        self.assertTrue(self.song.is_playing)
        self.button(C.BTN_PLAY)
        self.assertFalse(self.song.is_playing)

    def test_play_on_an_arrangement_clip_toggles_the_transport(self):
        clip = FakeClip()
        clip.is_arrangement_clip = True
        self.song.view.select(clip)
        self.button(C.BTN_PLAY)
        self.assertEqual(clip.fired, 0)
        self.assertTrue(self.song.is_playing)


# --------------------------------------------------------------------- config

class LengthKnob(SeqTest):
    """The pattern-length encoder, on a loop longer than the grid can show."""

    def test_the_length_knob_never_truncates_a_loop_it_cannot_show(self):
        # _step_count() is the VIEW ceiling and stops at STEPS_MAX. Feeding it
        # back as if it were the CURRENT length turned one click into a
        # truncation on any longer loop -- 128 beats became 64, in either
        # direction, silently, dragging the clip's end marker in with it.
        self.clip.loop_start = 0.0
        self.clip.loop_end = 4.0 * C.STEPS_MAX * C.STEP      # four screens
        long_end = self.clip.loop_end
        self.seq.handle_encoder_cc(C.CC_LENGTH, 65)          # one click up
        self.assertGreaterEqual(self.clip.loop_end, long_end,
                                'the knob shortened a loop it cannot address')
        self.seq.handle_encoder_cc(C.CC_LENGTH, 63)          # one click down
        self.assertAlmostEqual(self.clip.loop_end, long_end - C.STEP)

    def test_the_length_knob_still_resizes_an_ordinary_loop(self):
        self.clip.loop_start = 0.0
        self.clip.loop_end = 4 * C.STEP
        self.seq.handle_encoder_cc(C.CC_LENGTH, 65)
        self.assertAlmostEqual(self.clip.loop_end, 5 * C.STEP)
        self.seq.handle_encoder_cc(C.CC_LENGTH, 63)
        self.assertAlmostEqual(self.clip.loop_end, 4 * C.STEP)


class LogFlooding(SeqTest):
    """The latches were pinned; the caps beside them were not.

    The existing tests fire the SAME signature repeatedly, which pins the
    latch. The cap exists for the opposite case, named in the code: "a fault
    whose message varies every time cannot fill Log.txt either." A per-audio-
    buffer fault with a varying message writes ~90 tracebacks a second and
    grows an unbounded set, burying the first copy -- which is also the only
    thing tearDown and the "no exception in any session" claim can read.
    """

    def test_the_exception_log_stops_at_the_cap(self):
        self.expect_logged_exception = True
        for index in range(40):
            try:
                raise RuntimeError('a fault whose message varies %d' % index)
            except RuntimeError:
                self.seq._log_exception('receive_midi')
        lines = [l for l in self.c_instance.log if 'exception in' in l]
        self.assertEqual(len(lines), 32, 'wrote %d lines' % len(lines))

    def test_the_unmapped_log_stops_at_the_cap(self):
        for status in range(0x90, 0x90 + 60):
            self.seq._log_unhandled(status, 1, 1)
        lines = [l for l in self.c_instance.log if 'unmapped' in l]
        self.assertEqual(len(lines), 48, 'wrote %d lines' % len(lines))

    def test_a_second_distinct_fault_in_one_place_is_still_heard(self):
        # The reason the signature carries the frame as well as `where`:
        # receive_midi covers pads, buttons and knobs, and the likeliest fault
        # in each is the same message.
        self.expect_logged_exception = True

        def one():
            raise RuntimeError('same message')

        def two():
            raise RuntimeError('same message')

        for raiser in (one, two):
            try:
                raiser()
            except RuntimeError:
                self.seq._log_exception('receive_midi')
        lines = [l for l in self.c_instance.log if 'exception in' in l]
        self.assertEqual(len(lines), 2, 'the second subsystem was dropped')


class RetiredClaims(unittest.TestCase):
    """Facts that were corrected once and must not come back anywhere else.

    Five review rounds found the same shape of defect over and over: a claim
    fixed in one file and left standing in another -- CC 38 corrected in a
    block and surviving in a table eight lines away; the flag-byte-as-port
    model retired in HARDWARE.md and still instructing in STEPSEQ.md; a
    pre-fix function body quoted in DEVELOPMENT.md as the pattern to copy.
    Six separate instances in the fifth round alone.

    Every one of them is a literal string that outlived its correction, so
    this is a grep, not a judgement. Add a row whenever a claim is retired;
    the cost is one line and it never rots the way prose does.
    """

    # (phrase, why it was retired). Case-insensitive, substring.
    RETIRED = (
        ('eight Shift+Pad presets',
         'those eight note ranges are PAD BANK positions of ONE preset file'),
        ('REC is -1 above',
         'never existed in MIDI_Map.py in any revision'),
        ('satisfied by padding',
         'the setter is not called at all, so nothing is padded'),
        ('All three scripts now call this body',
         'MVave_SMC_STEPSEQ has no such body -- it uses a guarded listener'),
        ('Dependency install failed',
         'run_probe.bat prints DOWNLOAD or IMPORTED, two separate labels'),
        ('set_scene_bank_buttons(None, None)',
         'commit 204acbe replaced it; quoting it reinstates a permanent unbind'),
        ('CC 118 and 119 are chosen',
         'present tense: the padding that used them is gone'),
        ('draw over each other',
         'the two port-3 scripts write disjoint note ranges (measured)'),
        ('load one at a time',
         'same -- both scripts stay loaded, the preset switch is the mode switch'),
        ('CC 38',
         'the encoders send CC 1-18; 38-45 was never measured on this unit'),
        ('take a bank you do not use',
         'the sequencer needs its own PRESET, not a spare bank'),
        ('one bank per Shift+Pad',
         'one bank per PAD BANK position; Shift+Pad loads a different file'),
        ('only the two navigation encoders',
         'all sixteen must be relative -- the macros are decoded as deltas too'),
        ('All five `Special*Component.py`',
         'there are six'),
    )

    def test_no_retired_claim_survives_anywhere_in_the_docs(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        documents = []
        for directory in (root, os.path.join(root, 'docs')):
            for name in sorted(os.listdir(directory)):
                if name.endswith('.md'):
                    documents.append(os.path.join(directory, name))
        self.assertTrue(documents, 'found no documents to check')

        survivors = []
        for path in documents:
            with open(path, encoding='utf-8') as handle:
                lines = handle.read().split('\n')
            for number, line in enumerate(lines, 1):
                for phrase, why in self.RETIRED:
                    if phrase.lower() in line.lower():
                        survivors.append('%s:%d  %r\n      retired because: %s'
                                         % (os.path.relpath(path, root),
                                            number, phrase, why))
        self.assertEqual(survivors, [],
                         'retired claims are back:\n    ' + '\n    '.join(survivors))


class LauncherDeviceNav(unittest.TestCase):
    """MVave_SMC_PAD/DeviceNav.py, by path: Stop + arrows on presets 1 and 3."""

    @classmethod
    def setUpClass(cls):
        import importlib.util
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        spec = importlib.util.spec_from_file_location(
            'pad_device_nav', os.path.join(root, 'MVave_SMC_PAD', 'DeviceNav.py'))
        cls.nav = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.nav)

    def setUp(self):
        self.tom = FakeDevice([], 'Hi Tom')
        self.rack = FakeDrumRack({50: FakeDrumPad(50, [self.tom])})
        self.after = FakeDevice([], 'Reverb')
        self.track = FakeTrack([self.rack, self.after])

    def test_the_selected_drum_comes_right_after_its_rack(self):
        self.rack.view.selected_drum_pad = self.rack.drum_pads[50]
        self.assertEqual(self.nav.device_list(self.track),
                         [self.rack, self.tom, self.after])

    def test_no_selected_pad_lists_just_the_track(self):
        self.assertEqual(self.nav.device_list(self.track), [self.rack, self.after])

    def test_step_stops_at_both_ends(self):
        items = ['a', 'b', 'c']
        self.assertEqual(self.nav.step(items, 'b', 1), 'c')
        self.assertEqual(self.nav.step(items, 'c', 1), 'c')
        self.assertEqual(self.nav.step(items, 'a', -1), 'a')

    def test_step_from_an_unknown_item_lands_on_the_first(self):
        self.assertEqual(self.nav.step(['a', 'b'], 'zzz', 1), 'a')
        self.assertIsNone(self.nav.step([], 'a', 1))

    def test_tracks_then_returns_then_master(self):
        song = type('S', (), {'visible_tracks': ['t1', 't2'],
                              'return_tracks': ['r'], 'master_track': 'm'})()
        self.assertEqual(self.nav.track_list(song), ['t1', 't2', 'r', 'm'])


class SourceFiles(unittest.TestCase):
    """Every shipped .py must parse, at the floor the docs claim.

    The suite imports MVave_SMC_STEPSEQ and MVave_SMC_KNOBS and loads
    MVave_SMC_PAD/MIDI_Map.py by path -- and touches nothing else in
    MVave_SMC_PAD/. A syntax error in MVave_SMC_PAD.py or any Special*
    component was a green run here and a silently dead control surface in
    Live. Four review rounds ran this by hand; nothing ran it on demand.
    """

    def test_every_shipped_python_file_parses_at_the_stated_floor(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        checked = []
        for package in ('MVave_SMC_PAD', 'MVave_SMC_KNOBS',
                        'MVave_SMC_STEPSEQ', 'tools'):
            directory = os.path.join(root, package)
            for name in sorted(os.listdir(directory)):
                if not name.endswith('.py'):
                    continue
                path = os.path.join(directory, name)
                checked.append(path)
                with open(path, 'rb') as handle:
                    source = handle.read()
                try:
                    # Live 11 embeds Python 3.7. Syntax newer than that parses
                    # fine under the interpreter running this suite and fails
                    # only on the target, which is the whole point.
                    ast.parse(source, path, feature_version=(3, 7))
                except SyntaxError as exc:
                    self.fail('%s does not parse at Python 3.7: %s' % (path, exc))
        self.assertGreaterEqual(len(checked), 16,
                                'expected all four directories scanned, saw %d files'
                                % len(checked))


class Configuration(unittest.TestCase):
    """Cheap guards on MIDI_Map.py, since a typo there is a Live restart."""

    def test_sixteen_pads(self):
        self.assertEqual(len(C.PAD_NOTES), 16)
        self.assertEqual(len(C.LED_NOTES), 16)
        self.assertEqual(len(set(C.PAD_NOTES)), 16)

    def test_four_lane_colours(self):
        self.assertEqual(len(C.LANE_COLORS), 4)

    def test_the_two_port_3_scripts_cannot_collide(self):
        # Both scripts sit on port 3 and both use channel 1, so the NOTE RANGE
        # is the only thing keeping them apart -- which is what the +100 offset
        # in MIDI_Map.py exists for. The check below this one compares the
        # sequencer only with itself, so it would happily pass with
        # PAD_NOTES = 1..16, a state this map file records having been in once,
        # in which every clip launch would also toggle a step.
        import importlib.util
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        spec = importlib.util.spec_from_file_location(
            'pad_midi_map', os.path.join(root, 'MVave_SMC_PAD', 'MIDI_Map.py'))
        pad = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pad)

        # Sweep every note constant the launcher defines, not a hand-picked
        # six: enabling any of the ~42 currently at -1 is the realistic way a
        # collision gets introduced, and naming six left that path uncovered.
        not_notes = {'BUTTONCHANNEL', 'SLIDERCHANNEL', 'MESSAGETYPE', 'PADCHANNEL',
                     'TSB_X', 'TSB_Y', 'TRACK_OFFSET', 'SCENE_OFFSET',
                     'TEMPO_TOP', 'TEMPO_BOTTOM',
                     # CC assignments, on SLIDERCHANNEL -- they share a number
                     # space with notes but never a message type, so a CC of 101
                     # is not a collision and must not fail this test.
                     'TEMPOCONTROL', 'MASTERVOLUME', 'CUELEVEL', 'CROSSFADER',
                     'TRACKVOL', 'TRACKPAN', 'TRACKSENDA', 'TRACKSENDB',
                     'TRACKSENDC', 'PARAMCONTROL',
                     # Drum-rack pitches Live translates TO; never transmitted.
                     'DRUM_PADS'}
        # Constants named *_LEDS are LED numbers the launcher sends, the rest
        # notes it receives (or colours, which collide with nothing). The two
        # directions are separate on the wire: preset 4's pads send 65-80,
        # which the sequencer only ever sends as LEDs (69-84), and that is no
        # collision.
        launcher, launcher_leds = set(), set()
        for name in dir(pad):
            if not name.isupper() or name in not_notes or name.startswith('CLIP_'):
                continue
            into = launcher_leds if name.endswith('_LEDS') else launcher
            value = getattr(pad, name)
            if isinstance(value, int):
                into.add(value)
            elif isinstance(value, tuple):
                for item in value:
                    if isinstance(item, int):
                        into.add(item)
                    elif isinstance(item, tuple):
                        into.update(i for i in item if isinstance(i, int))
        launcher.discard(-1)

        # LED_NOTES too: it decides where _send_led writes on the MIDIOUT3 both
        # scripts share, and the map file records having held a fixed 1-16 LED
        # map once already. Without it, one constant makes the sequencer paint
        # its step colours onto the launcher's clip slots, suite still green.
        buttons = set(n for n in (C.BTN_PLAY, C.BTN_VIEW, C.BTN_MOD,
                                  C.BTN_LEFT, C.BTN_RIGHT) if n is not None)
        mine = set(C.PAD_NOTES) | set(C.PAD_NOTES_B) | buttons
        mine_leds = set(C.LED_NOTES) | buttons   # buttons light at their note
        # The clip grid and mixer light at note + offset, not a constant.
        clips = [n for row in pad.CLIPNOTEMAP for n in row if n >= 0]
        mixer = [n for n in pad.TRACKMUTE + pad.TRACKSOLO + pad.TRACKREC + pad.TRACKSTOP
                 if n >= 0]
        launcher_leds.update(n + pad.PAD_LED_OFFSET for n in clips)
        launcher_leds.update(n + pad.MIXER_LED_OFFSET for n in mixer)

        if C.PAD_CHANNEL == pad.BUTTONCHANNEL:
            self.assertEqual(mine & launcher, set(),
                             'sequencer and clip launcher share notes on one port')
            self.assertEqual(mine_leds & launcher_leds, set(),
                             'sequencer and clip launcher share LEDs on one port')

    def test_pads_and_buttons_do_not_collide(self):
        buttons = set(n for n in (C.BTN_PLAY, C.BTN_VIEW, C.BTN_MOD,
                                  C.BTN_LEFT, C.BTN_RIGHT) if n is not None)
        if C.BUTTON_CHANNEL == C.PAD_CHANNEL and not C.BUTTON_IS_CC:
            self.assertFalse((buttons & set(C.PAD_NOTES))
                             | (buttons & set(C.PAD_NOTES_B)))

    def test_every_value_is_a_legal_midi_byte(self):
        for name in ('COLOR_STEP_ON', 'COLOR_STEP_OFF', 'COLOR_PLAYHEAD',
                     'COLOR_PLAYHEAD_ON', 'COLOR_STEP_EMPTY',
                     'COLOR_STEP_DOWNBEAT', 'COLOR_NO_CLIP'):
            self.assertTrue(0 <= getattr(C, name) <= 127, name)
        for colour in C.LANE_COLORS:
            self.assertTrue(0 <= colour <= 127)
        for note in tuple(C.PAD_NOTES) + tuple(C.LED_NOTES):
            self.assertTrue(0 <= note <= 127)
        self.assertTrue(0 <= C.PAD_CHANNEL <= 15)
        self.assertTrue(0 <= C.LED_CHANNEL <= 15)
        # The buttons and knob CCs go straight to Live.MidiMap in
        # build_midi_map, which is unguarded -- an illegal number there takes
        # the surface down at load. None is the documented "unassigned" value;
        # a negative is not, and the adapting guide used to hand out -1.
        for name in ('BTN_PLAY', 'BTN_VIEW', 'BTN_MOD', 'BTN_LEFT', 'BTN_RIGHT'):
            value = getattr(C, name)
            self.assertTrue(value is None or 0 <= value <= 127,
                            '%s = %r -- use None, not a negative' % (name, value))
        for cc in SEQ_MODULE.KNOB_CCS:
            self.assertTrue(0 <= cc <= 127, 'CC %r' % (cc,))
        self.assertTrue(0 <= C.BUTTON_CHANNEL <= 15)
        self.assertTrue(0 <= C.KNOB_CHANNEL <= 15)

    def test_a_negative_button_never_reaches_the_midi_map(self):
        # -1 is the sentinel MVave_SMC_PAD/MIDI_Map.py uses and the adapting
        # guide once recommended here too. The LED path always skipped it; the
        # forwarding path did not, so it arrived as note -1.
        seqmod = SEQ_MODULE
        original = seqmod.BTN_PLAY
        try:
            seqmod.BTN_PLAY = -1
            seq = seqmod.MVave_SMC_STEPSEQ(FakeCInstance())
            MIDI_MAP.forwarded = []
            seq.build_midi_map('map')
            numbers = [n for kind, ch, n in MIDI_MAP.forwarded if kind == 'note']
            self.assertTrue(all(0 <= n <= 127 for n in numbers), numbers)
        finally:
            seqmod.BTN_PLAY = original

    def test_the_palette_only_uses_measured_colours(self):
        # Everything from 64 to 112 is one flat blue on this device, so a
        # colour up there is almost certainly a mistake (HARDWARE.md 3.2).
        for colour in ((C.COLOR_STEP_ON, C.COLOR_PLAYHEAD, C.COLOR_PLAYHEAD_ON)
                       + tuple(C.LANE_COLORS)):
            self.assertLessEqual(colour, 63, 'velocity %d is in the flat blue '
                                             'range' % colour)

    def test_knob_mode_is_one_of_the_two_schemes(self):
        self.assertIn(C.KNOB_MODE, ('centre', 'twos'))



class ButtonLeds(SeqTest):
    """The five buttons show state, when the device is set to accept feedback."""

    def test_play_button_lights_with_the_clip(self):
        self.seq.sent = []
        self.button(C.BTN_PLAY)                      # queues the clip
        self.assertEqual(self.btn_led(C.BTN_PLAY), C.BTN_LED_ON)
        self.clip.play(0.0)
        self.seq.sent = []
        self.button(C.BTN_PLAY)                      # stops it again
        self.assertEqual(self.btn_led(C.BTN_PLAY), C.BTN_LED_OFF)

    def test_play_button_follows_a_launch_from_the_mouse(self):
        # The status listener repaints the buttons, so a clip launched in Live
        # lights play even though no step moved.
        self.seq.sent = []
        self.clip.fire()
        self.assertEqual(self.btn_led(C.BTN_PLAY), C.BTN_LED_ON)
        self.clip.stop()
        self.assertEqual(self.btn_led(C.BTN_PLAY), C.BTN_LED_OFF)

    def test_play_button_lights_with_the_transport_without_a_clip(self):
        self.song.view.select(None)
        self.seq.sent = []
        self.button(C.BTN_PLAY)                      # starts the transport
        self.assertTrue(self.song.is_playing)
        self.assertEqual(self.btn_led(C.BTN_PLAY), C.BTN_LED_ON)
        self.seq.sent = []
        self.button(C.BTN_PLAY)                      # stops it again
        self.assertEqual(self.btn_led(C.BTN_PLAY), C.BTN_LED_OFF)

    def test_view_button_lights_in_overview(self):
        self.seq.sent = []
        self.button(C.BTN_VIEW)
        self.assertEqual(self.seq._view, VIEW_OVERVIEW)
        self.assertEqual(self.btn_led(C.BTN_VIEW), C.BTN_LED_ON)
        self.seq.sent = []
        self.button(C.BTN_VIEW)
        self.assertEqual(self.btn_led(C.BTN_VIEW), C.BTN_LED_OFF)

    def test_modifier_lights_while_held(self):
        self.seq.sent = []
        self.button(C.BTN_MOD, True)
        self.assertEqual(self.btn_led(C.BTN_MOD), C.BTN_LED_ON)
        self.seq.sent = []
        self.button(C.BTN_MOD, False)
        self.assertEqual(self.btn_led(C.BTN_MOD), C.BTN_LED_OFF)

    def test_refresh_state_repaints_the_button_leds(self):
        # refresh_state exists because the device may have been repowered or
        # switched presets, which leaves every LED dark. Dropping only the pad
        # cache left the button diff believing the play and view lights were
        # still lit, so they stayed dark until their state next changed.
        self.button(C.BTN_VIEW)                 # overview: the view LED is on
        self.seq.sent = []
        self.seq.refresh_state()
        self.assertEqual(self.btn_led(C.BTN_VIEW), C.BTN_LED_ON)

    def test_button_leds_are_diffed_not_resent(self):
        # _paint() runs on every playhead step. Without the cache each step would
        # rewrite all three buttons, which is the bulk-write the device's input
        # buffer does not survive.
        self.clip.play(0 * C.STEP)
        self.seq.sent = []
        for step in range(1, 8):
            self.clip.play(step * C.STEP)
        self.assertEqual(self.btn_writes(C.BTN_PLAY), [])
        self.assertEqual(self.btn_writes(C.BTN_VIEW), [])

    def arrow(self, note):
        """What the device holds for an arrow LED. The writes are diffed, so
        an arrow already dark is never re-sent and btn_led() cannot see it."""
        return self.seq._btn_led.get(note)

    def test_the_arrows_are_dark_on_a_one_page_loop(self):
        # A four-beat loop is one focus page: neither arrow goes anywhere.
        self.seq.refresh_state()
        self.assertEqual(self.arrow(C.BTN_LEFT), C.BTN_LED_OFF)
        self.assertEqual(self.arrow(C.BTN_RIGHT), C.BTN_LED_OFF)

    def test_the_arrows_light_towards_the_other_pages(self):
        self.clip.set_loop_end(self.clip.loop_start + 48 * C.STEP)   # 3 pages
        self.assertEqual(self.arrow(C.BTN_LEFT), C.BTN_LED_OFF)
        self.assertEqual(self.arrow(C.BTN_RIGHT), C.BTN_LED_ON)
        self.button(C.BTN_RIGHT)                                     # page 2
        self.assertEqual(self.arrow(C.BTN_LEFT), C.BTN_LED_ON)
        self.assertEqual(self.arrow(C.BTN_RIGHT), C.BTN_LED_ON)
        self.button(C.BTN_RIGHT)                                     # page 3
        self.assertEqual(self.arrow(C.BTN_LEFT), C.BTN_LED_ON)
        self.assertEqual(self.arrow(C.BTN_RIGHT), C.BTN_LED_OFF)

    def test_the_arrows_count_overview_pages(self):
        # Overview pages are 4 steps, so the same 16-step loop has 4 of them.
        self.button(C.BTN_VIEW)
        self.assertEqual(self.arrow(C.BTN_RIGHT), C.BTN_LED_ON)
        self.assertEqual(self.arrow(C.BTN_LEFT), C.BTN_LED_OFF)

    def test_with_mod_held_the_arrows_show_the_drum_banks(self):
        # A 16-pad kit: no bank either side, though the loop has pages.
        pads = dict((p, FakeDrumPad(p, [FakeDevice([], 'Drum')]))
                    for p in range(36, 52))
        self.song.view.selected_track = FakeTrack([FakeDrumRack(pads)])
        self.clip.set_loop_end(self.clip.loop_start + 32 * C.STEP)
        self.assertEqual(self.arrow(C.BTN_RIGHT), C.BTN_LED_ON)
        self.button(C.BTN_MOD, True)
        self.button(C.BTN_VIEW, True)             # Record + Stop: lane bank
        self.assertEqual(self.arrow(C.BTN_LEFT), C.BTN_LED_OFF)
        self.assertEqual(self.arrow(C.BTN_RIGHT), C.BTN_LED_OFF)
        self.button(C.BTN_VIEW, False)
        self.button(C.BTN_MOD, False)
        self.assertEqual(self.arrow(C.BTN_RIGHT), C.BTN_LED_ON)

    def test_arrow_leds_can_be_switched_off(self):
        seqmod = SEQ_MODULE
        original = seqmod.ARROW_LEDS
        try:
            seqmod.ARROW_LEDS = False
            self.seq.sent = []
            self.clip.set_loop_end(self.clip.loop_start + 32 * C.STEP)
            self.button(C.BTN_RIGHT)
            self.assertEqual(self.btn_writes(C.BTN_LEFT), [])
            self.assertEqual(self.btn_writes(C.BTN_RIGHT), [])
        finally:
            seqmod.ARROW_LEDS = original

    def test_every_button_the_script_lights_has_an_led_in_the_preset(self):
        # A button record's last byte is its LED number (inferred); 0xff left
        # Stop and the arrows dark however often the script lit them.
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data = open(os.path.join(root, 'presets',
                                 'preset2-sequencer-drums.spc'), 'rb').read()
        leds = dict((data[i * 23 + 2], data[i * 23 + 22]) for i in range(5))
        for note in (C.BTN_PLAY, C.BTN_VIEW, C.BTN_MOD, C.BTN_LEFT, C.BTN_RIGHT):
            self.assertEqual(leds[note], note)

    def test_all_leds_off_clears_the_buttons(self):
        self.button(C.BTN_VIEW)                      # light one
        self.seq.sent = []
        self.seq._all_leds_off()
        self.assertEqual(self.btn_led(C.BTN_VIEW), C.BTN_LED_OFF)

    def test_button_leds_can_be_switched_off(self):
        seqmod = SEQ_MODULE
        original = seqmod.BUTTON_LEDS
        try:
            seqmod.BUTTON_LEDS = False
            self.seq.sent = []
            self.button(C.BTN_VIEW)
            self.assertEqual(self.btn_writes(C.BTN_VIEW), [])
        finally:
            seqmod.BUTTON_LEDS = original


# ------------------------------------------------- the other two scripts

def _load_launcher_map():
    """MVave_SMC_PAD/MIDI_Map.py, by path -- its package __init__ imports Live."""
    import importlib.util
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    spec = importlib.util.spec_from_file_location(
        'pad_midi_map', os.path.join(root, 'MVave_SMC_PAD', 'MIDI_Map.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


NOT_NOTES = frozenset((
    'BUTTONCHANNEL', 'SLIDERCHANNEL', 'MESSAGETYPE', 'PADCHANNEL',
    'TSB_X', 'TSB_Y', 'TRACK_OFFSET', 'SCENE_OFFSET', 'TEMPO_TOP', 'TEMPO_BOTTOM',
    # CC assignments, on SLIDERCHANNEL -- same number space, different message
    # type, so they can never collide with a note.
    'TEMPOCONTROL', 'MASTERVOLUME', 'CUELEVEL', 'CROSSFADER', 'TRACKVOL',
    'TRACKPAN', 'TRACKSENDA', 'TRACKSENDB', 'TRACKSENDC', 'PARAMCONTROL',
    # Drum-rack pitches Live translates TO; never transmitted.
    'DRUM_PADS',
    # Preset 3's keyboard settings: channels, octaves, a flag and colours.
    'KEYS_CHANNEL', 'KEYS_ROOT_NOTE', 'KEYS_OCTAVE', 'KEYS_OCTAVE_MIN',
    'KEYS_OCTAVE_MAX', 'KEYS_FOLLOW_LIVE_SCALE', 'KEYS_SCALE',
))


# NOT_NOTES exempts these from the COLLISION test, correctly -- a CC and a note
# live in different message spaces. They are still list indexes, so the RANGE
# test must cover them: MASTERVOLUME = 200 is an IndexError inside __init__,
# where Live disables the whole surface silently.
NOT_INDEXES = frozenset((
    'BUTTONCHANNEL', 'SLIDERCHANNEL', 'MESSAGETYPE', 'PADCHANNEL',
    'TSB_X', 'TSB_Y', 'TEMPO_TOP', 'TEMPO_BOTTOM',
    # Preset 3's keyboard settings: channels, octaves, a flag and colours.
    'KEYS_CHANNEL', 'KEYS_ROOT_NOTE', 'KEYS_OCTAVE', 'KEYS_OCTAVE_MIN',
    'KEYS_OCTAVE_MAX', 'KEYS_FOLLOW_LIVE_SCALE', 'KEYS_SCALE',
))


def _launcher_indexes(pad):
    """Every constant the launcher uses to index _note_map or _ctrl_map."""
    out = []
    for name in dir(pad):
        if not name.isupper() or name in NOT_INDEXES or name.startswith('CLIP_'):
            continue
        value = getattr(pad, name)
        if isinstance(value, int):
            out.append((name, value))
        elif isinstance(value, tuple):
            for item in value:
                if isinstance(item, int):
                    out.append((name, item))
                elif isinstance(item, tuple):
                    out.extend((name, i) for i in item if isinstance(i, int))
    return out


def _launcher_notes(pad):
    """Every note constant the launcher declares, as (name, value) pairs."""
    out = []
    for name in dir(pad):
        if not name.isupper() or name in NOT_NOTES or name.startswith('CLIP_'):
            continue
        value = getattr(pad, name)
        if isinstance(value, int):
            out.append((name, value))
        elif isinstance(value, tuple):
            for item in value:
                if isinstance(item, int):
                    out.append((name, item))
                elif isinstance(item, tuple):
                    out.extend((name, i) for i in item if isinstance(i, int))
    return out


class LauncherMap(unittest.TestCase):
    """MVave_SMC_PAD/MIDI_Map.py -- the file INSTALL.md tells users to edit.

    Six single-constant edits to it used to pass the only check that read this
    file and then raise inside MVave_SMC_PAD.__init__, where Live disables the
    whole control surface silently and the only evidence is a Log.txt traceback
    after a full restart. These assertions are the half of that a machine can
    catch in a second.
    """

    def setUp(self):
        self.pad = _load_launcher_map()

    def test_every_indexing_constant_is_a_legal_index(self):
        # Wider than the note test below: the CC constants are indexes too.
        for name, value in _launcher_indexes(self.pad):
            self.assertTrue(-1 <= value <= 127, '%s = %r' % (name, value))
        # The session offsets are asserted >= 0 by SpecialSessionComponent.
        for name in ('TRACK_OFFSET', 'SCENE_OFFSET'):
            self.assertGreaterEqual(getattr(self.pad, name), -1, name)

    def test_every_note_constant_is_a_legal_index(self):
        # -1 is the "unassigned" sentinel; 128+ is an IndexError at load and a
        # value below -1 silently binds the wrong note from the end of the list.
        for name, value in _launcher_notes(self.pad):
            self.assertTrue(-1 <= value <= 127, '%s = %r' % (name, value))

    def test_the_grid_dimensions_are_whole_numbers(self):
        # A float here is a TypeError inside range() at load.
        for name in ('TSB_X', 'TSB_Y'):
            self.assertIsInstance(getattr(self.pad, name), int, name)

    def test_clipnotemap_covers_the_declared_grid(self):
        p = self.pad
        self.assertGreaterEqual(len(p.CLIPNOTEMAP), p.TSB_Y)
        for row in p.CLIPNOTEMAP[:p.TSB_Y]:
            self.assertGreaterEqual(len(row), p.TSB_X)

    def test_the_indexed_tuples_are_long_enough(self):
        # _setup_session_control indexes SCENELAUNCH by range(TSB_X) and
        # TRACKSTOP by range(TSB_Y) -- the documented swap. Pinned as the code
        # is, not as it reads, so a non-square grid fails here and not in Live.
        p = self.pad
        self.assertGreaterEqual(len(p.SCENELAUNCH), p.TSB_X)
        self.assertGreaterEqual(len(p.TRACKSTOP), p.TSB_Y)
        # _scene_launch_buttons is built with range(TSB_X) and then indexed by
        # range(TSB_Y), so TSB_X < TSB_Y is an IndexError at load that the two
        # assertions above cannot see. The grid is square by assumption
        # (DEVELOPMENT.md) -- pin the assumption rather than the symptom.
        self.assertEqual(p.TSB_X, p.TSB_Y,
                         'a non-square grid raises IndexError in '
                         '_setup_session_control')
        for name in ('TRACKREC', 'TRACKSOLO', 'TRACKMUTE', 'TRACKSEL',
                     'TRACKVOL', 'TRACKPAN', 'TRACKSENDA', 'TRACKSENDB',
                     'TRACKSENDC', 'PARAMCONTROL', 'DEVICEBANK'):
            self.assertGreaterEqual(len(getattr(p, name)), 8, name)

    def test_the_clip_palette_stays_in_the_measured_range(self):
        # Same hardware palette as the sequencer's: everything above ~64 is one
        # flat blue, and above 127 is not a legal MIDI byte at all.
        for name in ('CLIP_PLAYING', 'CLIP_STOPPED', 'CLIP_RECORDING',
                     'CLIP_TRIGGERED_PLAY', 'CLIP_TRIGGERED_REC'):
            value = getattr(self.pad, name)
            self.assertTrue(0 <= value <= 63, '%s = %d' % (name, value))


class KnobScript(unittest.TestCase):
    """MVave_SMC_KNOBS had no test of any kind before this class."""

    def setUp(self):
        self.knobs = KNOBS_MODULE.MVave_SMC_KNOBS(FakeCInstance())
        self.expect_logged_exception = False

    def tearDown(self):
        # The same backstop SeqTest has, and for the same reason: receive_midi
        # swallows and logs, so a test that drives the script the way real MIDI
        # arrives can be green while every write raised and was discarded.
        if self.expect_logged_exception:
            return
        raised = [l for l in self.knobs._c_instance.log if 'exception in' in l]
        self.assertEqual(raised, [], 'a guarded callback raised: %s' % raised)

    def _with_session(self, width=4, height=4):
        session = FakeSession(width, height)
        self.knobs._pad_session = lambda: session
        return session

    def _turn(self, cc, value):
        self.knobs.receive_midi((0xB0 | KNOBS_MODULE.CHANNEL, cc, value))

    # ------------------------------------------------------- the MIDI path

    def test_a_navigation_click_moves_the_session_box(self):
        session = self._with_session()
        self._turn(KNOBS_MODULE.CC_TRACK, 65)
        self.assertEqual(session.offsets[-1], (1, 0))
        self._turn(KNOBS_MODULE.CC_SCENE, 65)
        self.assertEqual(session.offsets[-1], (1, 1))

    def test_the_session_box_never_banks_below_zero(self):
        # set_offsets asserts on a negative offset, and an assert inside a MIDI
        # callback takes the whole script down mid-jam.
        session = self._with_session()
        for _ in range(4):
            self._turn(KNOBS_MODULE.CC_TRACK, 63)
        self.assertEqual(session.track_offset(), 0)

    def test_every_cc_the_script_handles_is_forwarded(self):
        # Dropping this loop leaves Live forwarding nothing: all sixteen macros
        # and both navigation encoders go dead, with no UI evidence at all.
        MIDI_MAP.forwarded = []
        self.knobs.build_midi_map('map')
        forwarded = set(MIDI_MAP.forwarded)
        for cc in (tuple(KNOBS_MODULE.NAV_CCS)
                   + tuple(sorted(KNOBS_MODULE.MACRO_BY_CC))
                   + tuple(sorted(KNOBS_MODULE.PARAM_BY_CC))):
            self.assertIn(('cc', KNOBS_MODULE.CHANNEL, cc), forwarded)

    def test_unowned_midi_goes_back_to_the_framework(self):
        # Swallowing it is the documented silent failure in this codebase.
        stray = (0x90, 60, 100)
        self.knobs.receive_midi(stray)
        self.assertIn(stray, self.knobs.forwarded_to_framework)

    def test_a_macro_cc_reaches_the_device(self):
        param = FakeParameter(0.0, 127.0)
        self.knobs._device.set_device(FakeDevice([FakeParameter(0.0, 1.0), param]))
        self._turn(sorted(KNOBS_MODULE.MACRO_BY_CC)[0], 65)
        self.assertEqual(param.value, 1.0)

    def test_a_raising_device_is_logged_not_propagated(self):
        # And tearDown must SEE it -- the point of the opt-out.
        self.expect_logged_exception = True

        class Exploding(object):
            name = 'Exploding Rack'

            @property
            def parameters(self):
                raise RuntimeError('device went away')

        self.knobs._device.set_device(Exploding())
        self._turn(sorted(KNOBS_MODULE.MACRO_BY_CC)[0], 65)
        self.assertTrue(any('exception in receive_midi' in l
                            for l in self.knobs._c_instance.log))

    # ------------------------------------------------------- the guards

    def test_a_macro_never_writes_outside_the_parameter_range(self):
        # Live's setter raises on an out-of-range write, and an exception in a
        # MIDI callback disables the script silently.
        param = FakeParameter(0.0, 127.0, value=127.0)
        self.knobs._device.set_device(FakeDevice([FakeParameter(0.0, 1.0), param]))
        self.knobs._adjust_macro(1, 1)
        self.assertEqual(param.value, 127.0)

    def test_a_disabled_parameter_is_left_alone(self):
        param = FakeParameter(0.0, 127.0)
        param.is_enabled = False
        self.knobs._device.set_device(FakeDevice([FakeParameter(0.0, 1.0), param]))
        self.knobs._adjust_macro(1, 1)
        self.assertEqual(param.value, 0.0)

    def test_a_rack_with_fewer_macros_than_knobs_is_not_an_error(self):
        self.knobs._device.set_device(FakeDevice([FakeParameter(0.0, 1.0)]))
        self.knobs._adjust_macro(9, 1)
        self.assertTrue(any('does nothing' in l
                            for l in self.knobs._c_instance.log))

    def test_two_identically_named_devices_are_both_reported(self):
        # Live names every rack "Audio Effect Rack", so a latch keyed on the
        # finished message reported the first and silently dropped the second
        # -- while the troubleshooting step reads "no line, so not this cause".
        devices = [FakeDevice([FakeParameter(0.0, 1.0)], name='Audio Effect Rack')
                   for _ in range(2)]
        for device in devices:
            self.knobs._device.set_device(device)
            self.knobs._adjust_macro(9, 1)
        lines = [l for l in self.knobs._c_instance.log if 'does nothing' in l]
        self.assertEqual(len(lines), 2, lines)

    def test_the_once_latch_is_capped(self):
        for index in range(40):
            self.knobs._log_once('a message that varies %d' % index)
        lines = [l for l in self.knobs._c_instance.log if 'that varies' in l]
        self.assertEqual(len(lines), 32, 'wrote %d lines' % len(lines))

    def test_the_two_navigation_ccs_are_distinct(self):
        # NAV_CCS is a tuple and set() collapses a duplicate silently; then
        # _navigate's "if cc == CC_TRACK" claims both, the scene encoder banks
        # tracks, and the box's Y axis becomes unreachable. No log line.
        self.assertNotEqual(KNOBS_MODULE.CC_TRACK, KNOBS_MODULE.CC_SCENE)

    def test_the_macro_map_is_self_consistent(self):
        K = KNOBS_MODULE
        self.assertFalse(set(K.MACRO_BY_CC) & set(K.NAV_CCS),
                         'a macro CC collides with a navigation CC')
        for cc, macro in K.MACRO_BY_CC.items():
            self.assertTrue(0 <= cc <= 127, 'CC %r' % (cc,))
            self.assertTrue(1 <= macro <= 127,
                            'macro %r -- index 0 is the device on/off switch' % (macro,))
        values = list(K.MACRO_BY_CC.values())
        self.assertEqual(len(set(values)), len(values), 'two CCs drive one macro')

    def test_one_click_moves_a_rack_macro_by_exactly_one(self):
        # The documented guarantee (INSTALL.md): a rack macro runs 0-127, a
        # range of 127, so one click is one unit. STEPS_PER_SWEEP = 128.0 was
        # shipped once and moves 0.992, which never lands on an integer.
        param = FakeParameter(0.0, 127.0)
        # Bound through the component, not the cache: _adjust_macro resolves the
        # device at write time, which is the whole point of _current_device().
        self.knobs._device.set_device(
            FakeDevice([FakeParameter(0.0, 1.0), param]))
        self.knobs._adjust_macro(1, 1)
        self.assertEqual(param.value, 1.0)

    def test_the_device_lookup_engages_on_every_spelling(self):
        # getattr(component, 'device', None) cannot tell an absent attribute
        # from a getter answering None, which made this fall back to the stale
        # cache on a fresh start. A sentinel distinguishes them.
        live_device, stale = FakeDevice([]), FakeDevice([])
        for spelling in ('method', 'property', 'private'):
            for held in (live_device, None):
                self.knobs._device = _fake_component(spelling, held)
                self.knobs._target_device = stale
                self.assertIs(self.knobs._current_device(), held,
                              '%s spelling, held=%r' % (spelling, held))

    def test_an_absent_getter_falls_back_and_says_so(self):
        self.knobs._device = _fake_component('nothing', None)
        stale = FakeDevice([])
        self.knobs._target_device = stale
        self.assertIs(self.knobs._current_device(), stale)
        self.assertTrue(any('no device getter' in line
                            for line in self.knobs._c_instance.log))

    def test_both_scripts_decode_a_click_the_same_way(self):
        # One measured hardware fact, two copies -- KNOBS hard-codes CENTRE and
        # the sequencer exposes KNOB_MODE. If they ever disagree, the same byte
        # moves the session box and the step lane in opposite directions.
        #
        # BOTH modes, not just the shipped one: comparing the two scripts under
        # 'centre' alone never executed the 'twos' branch at all, so the whole
        # convention a stranger with a 1/127 encoder depends on -- added by the
        # previous review round -- shipped untested.
        self.assertEqual(KNOBS_MODULE.ENCODER_MODE, C.KNOB_MODE)
        for mode in ('centre', 'twos'):
            for value in (0, 1, 2, 63, 64, 65, 126, 127):
                self.assertEqual(KNOBS_MODULE.decode_relative(value, mode),
                                 decode_relative(value, mode),
                                 'mode %s, value %d' % (mode, value))
        # And the two conventions must not be silently interchangeable.
        self.assertNotEqual(KNOBS_MODULE.decode_relative(127, 'centre'),
                            KNOBS_MODULE.decode_relative(127, 'twos'))


class PresetSwitchRepaint(unittest.TestCase):
    """MVave_SMC_KNOBS repaints the pad lights when the device changes layout.

    The status bytes are the four states captured from the device on
    2026-10-08 (preset 1 bank A/B and preset 2 bank A/B) and preset 3 bank A,
    captured on 2026-10-20.
    """

    BASE = (0xF0, 0x00, 0x32, 0x0D, 0x21, 0x01, 0x00, 0x00, 0x02, 0x00, 0x00,
            0x00, 0x00, 0x40, 0x01, 0x00, 0x00, 0x78, 0x00, 0x48, 0x21, 0x00,
            0x00, 0x00, 0x01, 0x00, 0x02, 0x04)
    LAUNCHER = BASE + (0x00, 0x00, 0x20, 0x0F, 0xF7)
    MIXER = BASE + (0x00, 0x10, 0x00, 0x0F, 0xF7)
    SEQUENCER = BASE + (0x08, 0x00, 0x00, 0x0F, 0xF7)
    DRUMS = BASE + (0x08, 0x10, 0x60, 0x0E, 0xF7)
    KEYS = BASE + (0x10, 0x00, 0x40, 0x0E, 0xF7)

    class Script(object):
        def __init__(self, name, log):
            self.name, self.log = name, log

        def refresh_state(self):
            pass

        def schedule_message(self, delay, callback):
            self.log.append((delay, self.name))

    def setUp(self):
        self.knobs = KNOBS_MODULE.MVave_SMC_KNOBS(FakeCInstance())
        self.scheduled = []
        scripts = {'MVave_SMC_PAD': [self.Script('pad', self.scheduled)],
                   'MVave_SMC_STEPSEQ': [self.Script('seq', self.scheduled)]}
        self.knobs._instances = lambda name: scripts[name]
        # Already on the startup preset: StartupPreset tests the move itself.
        self.knobs._startup_pending = False

    def _last_repainted(self, status):
        del self.scheduled[:]
        self.knobs.receive_midi(status)
        return max(self.scheduled)[1]

    def test_the_status_is_33_bytes(self):
        for status in (self.LAUNCHER, self.MIXER, self.SEQUENCER, self.DRUMS,
                       self.KEYS):
            self.assertEqual(len(status), KNOBS_MODULE.STATUS_LENGTH)

    def test_the_status_decodes_to_preset_and_bank(self):
        decode = KNOBS_MODULE.decode_status
        self.assertEqual(decode(self.LAUNCHER), (0, 0))
        self.assertEqual(decode(self.MIXER), (0, 1))
        self.assertEqual(decode(self.SEQUENCER), (1, 0))
        self.assertEqual(decode(self.DRUMS), (1, 1))
        self.assertEqual(decode(self.KEYS), (2, 0))

    def test_the_state_request_is_the_one_the_device_answered(self):
        # Sent from the computer on 2026-10-20; the device replied in ~1 ms.
        self.assertEqual(KNOBS_MODULE.STATE_REQUEST, (
            0xF0, 0x00, 0x32, 0x0D, 0x41, 0x00, 0x00, 0x00, 0x02, 0x00, 0x00,
            0x00, 0x00, 0x40, 0x01, 0x00, 0x00, 0x6F, 0x01, 0xF7))

    def test_the_status_unpacks_to_a_checksummed_flash_read(self):
        packet = KNOBS_MODULE.unpack7(self.KEYS[1:-1])
        self.assertEqual(packet[:3], [0x00, 0x59, 0x23])
        self.assertEqual(KNOBS_MODULE.unpack7(KNOBS_MODULE.pack7(packet)), packet)
        for status in (self.LAUNCHER, self.MIXER, self.SEQUENCER, self.DRUMS):
            packet = KNOBS_MODULE.unpack7(status[1:-1])
            self.assertEqual(packet[26], ~sum(packet[6:26]) & 0xFF)

    def _requests(self, ticks=0):
        sent = self.knobs.sent
        for _ in range(ticks):
            self.knobs.update_display()
        return sent.count(KNOBS_MODULE.STATE_REQUEST)

    def _settled(self, status):
        # On a known layout, startup done, poll counter just reset.
        self.knobs.receive_midi(status)
        self.knobs._poll_ticks = 0
        self.knobs._asked_this_tick = False
        self.knobs.sent = []

    def test_it_asks_every_poll_ticks_not_every_tick(self):
        # Every request and reply flashes Live's MIDI indicators.
        self._settled(self.LAUNCHER)
        self.assertEqual(self._requests(KNOBS_MODULE.POLL_TICKS * 3), 3)

    def test_after_a_switch_it_asks_every_tick_for_a_while(self):
        # Switches come in runs; the second one should show at once.
        self._settled(self.LAUNCHER)
        self.knobs.receive_midi(self.MIXER)
        fast = KNOBS_MODULE.SWITCH_FAST_TICKS
        self.assertEqual(self._requests(fast - 1), fast - 1)
        self.knobs.sent = []
        self.knobs._poll_ticks = 0
        self.assertEqual(self._requests(KNOBS_MODULE.POLL_TICKS * 2), 2)

    def test_the_first_status_is_not_a_switch(self):
        self.knobs._last_status = None
        self._settled(self.LAUNCHER)
        self.assertEqual(self._requests(KNOBS_MODULE.POLL_TICKS), 1)

    def test_until_the_startup_preset_is_in_it_asks_every_tick(self):
        self.knobs._startup_pending = True
        self.knobs.sent = []
        self.assertEqual(self._requests(3), 3)

    def test_a_press_from_the_current_layout_asks_nothing(self):
        self._settled(self.LAUNCHER)
        for note in (1, 16, 17, 21):
            self.knobs.port3_message((0x90, note, 127))
        self.knobs.receive_midi((0xB0 | KNOBS_MODULE.CHANNEL, 17, 65))
        self.assertEqual(self._requests(), 0)

    def test_a_press_from_another_layout_asks_at_once(self):
        cases = ((self.LAUNCHER, (0x90, 101, 127)),     # sequencer step
                 (self.LAUNCHER, (0x90, 49, 127)),      # mixer, other bank
                 (self.SEQUENCER, (0x90, 85, 127)),     # keyboard
                 (self.KEYS, (0x90, 117, 127)),         # sequencer button
                 (self.KEYS, (0xB0, 1, 65)),            # a macro knob
                 (self.LAUNCHER, (0xB0, 21, 65)))       # a preset 3 knob
        for status, message in cases:
            self._settled(status)
            if message[0] == 0x90:
                self.knobs.port3_message(message)
            else:
                self.knobs.receive_midi(message)
            self.assertEqual(self._requests(), 1, (status[28:30], message))

    def test_a_chord_after_a_switch_asks_once(self):
        self._settled(self.LAUNCHER)
        for note in range(101, 117):
            self.knobs.port3_message((0x90, note, 127))
        self.assertEqual(self._requests(), 1)
        self.knobs.update_display()
        self.knobs.port3_message((0x90, 101, 127))
        self.assertEqual(self._requests(), 2)

    def test_releases_and_ambiguous_buttons_ask_nothing(self):
        self._settled(self.SEQUENCER)
        self.knobs.port3_message((0x90, 1, 0))          # a release
        self.knobs.port3_message((0x90, 120, 127))      # its own arrow
        self._settled(self.KEYS)
        self.knobs.port3_message((0x90, 17, 127))       # shared with preset 1
        self.assertEqual(self._requests(), 0)

    def test_the_pad_and_sequencer_scripts_hand_it_their_messages(self):
        saved = list(KNOBS_MODULE.MVave_SMC_KNOBS._active_instances)
        KNOBS_MODULE.MVave_SMC_KNOBS._active_instances[:] = [self.knobs]
        try:
            self._settled(self.LAUNCHER)
            SEQ_MODULE._tell_knobs((0x90, 101, 127))
            self.assertEqual(self._requests(), 1)
        finally:
            KNOBS_MODULE.MVave_SMC_KNOBS._active_instances[:] = saved

    def test_the_layout_table_agrees_with_the_pad_and_sequencer_maps(self):
        M = _load_launcher_map()
        notes = KNOBS_MODULE.LAYOUTS_BY_NOTE
        clip_notes = [n for row in M.CLIPNOTEMAP for n in row]
        mixer = M.TRACKMUTE + M.TRACKSOLO + M.TRACKREC + M.TRACKSTOP
        for group, layouts in ((clip_notes, ((0, 0),)), (mixer, ((0, 1),)),
                               (M.KEYS_NOTES, ((2, 0),)),
                               (M.SETTINGS_NOTES, ((2, 1),)),
                               (C.PAD_NOTES, ((1, 0),))):
            for note in group:
                if note >= 0:       # -1 = an unused slot in the map
                    self.assertEqual(notes[note], layouts, note)
        for group, layouts in ((M.CHORDS_NOTES, ((3, 0),)),
                               (M.CHORDS_SETTINGS_NOTES, ((3, 1),))):
            for note in group:
                self.assertEqual(notes[note], layouts, note)
        for note in (M.PLAY, M.STOP, M.REC, M.TRACKLEFT, M.TRACKRIGHT):
            self.assertEqual(notes[note], ((0, None), (2, None), (3, None)))
        for note in (C.BTN_PLAY, C.BTN_VIEW, C.BTN_MOD, C.BTN_LEFT, C.BTN_RIGHT):
            self.assertEqual(notes[note], ((1, None),))

    def _with_velocity(self, status, setting):
        packet = KNOBS_MODULE.unpack7(status[1:-1])
        packet[KNOBS_MODULE.STATUS_VELOCITY] = setting
        packet[26] = ~sum(packet[6:26]) & 0xFF
        return (0xF0,) + tuple(KNOBS_MODULE.pack7(packet)) + (0xF7,)

    def test_the_status_decodes_to_the_velocity_setting(self):
        # The 2026-10-08 captures were taken on VELOCITY 2.
        self.assertEqual(KNOBS_MODULE.decode_velocity(self.LAUNCHER), 1)
        for setting in range(4):
            status = self._with_velocity(self.SEQUENCER, setting)
            self.assertEqual(len(status), KNOBS_MODULE.STATUS_LENGTH)
            self.assertEqual(KNOBS_MODULE.decode_velocity(status), setting)
            self.assertEqual(KNOBS_MODULE.decode_status(status), (1, 0))

    def _velocity_calls(self):
        got = []
        seq = self.Script('seq', self.scheduled)
        seq.set_velocity_setting = got.append
        self.knobs._instances = lambda name: (
            [seq] if name == 'MVave_SMC_STEPSEQ' else [])
        return got

    def test_a_velocity_change_reaches_the_sequencer_once(self):
        got = self._velocity_calls()
        self.knobs.receive_midi(self._with_velocity(self.SEQUENCER, 3))
        del self.scheduled[:]
        for setting in (1, 1, 0):
            self.knobs.receive_midi(self._with_velocity(self.SEQUENCER, setting))
        self.assertEqual(got, [1, 0])
        self.assertEqual(self.scheduled, [])        # and repaints nothing

    def test_the_velocity_the_controller_starts_on_is_not_passed_on(self):
        # Whatever it was left on, the sequencer starts at VELOCITY 4.
        got = self._velocity_calls()
        self.knobs.receive_midi(self._with_velocity(self.SEQUENCER, 0))
        self.knobs.receive_midi(self._with_velocity(self.SEQUENCER, 0))
        self.assertEqual(got, [])

    def test_a_status_differing_outside_preset_and_bank_repaints_nothing(self):
        # Byte 22 is the VELOCITY setting (01 on 2026-10-08, 02 and 03 on
        # 2026-10-20); only preset and bank repaint.
        packet = KNOBS_MODULE.unpack7(self.LAUNCHER[1:-1])
        packet[22] ^= 0x03
        packet[26] = ~sum(packet[6:26]) & 0xFF
        other = (0xF0,) + tuple(KNOBS_MODULE.pack7(packet)) + (0xF7,)
        self.assertNotEqual(other, self.LAUNCHER)
        self.assertEqual(len(other), KNOBS_MODULE.STATUS_LENGTH)
        self.knobs.receive_midi(self.LAUNCHER)
        del self.scheduled[:]
        self.knobs.receive_midi(other)
        self.assertEqual(self.scheduled, [])

    def test_preset_3_is_not_the_sequencer(self):
        self.assertEqual(self._last_repainted(self.KEYS), 'pad')

    def test_the_owner_of_the_new_layout_repaints_last(self):
        self.assertEqual(self._last_repainted(self.SEQUENCER), 'seq')
        self.assertEqual(self._last_repainted(self.DRUMS), 'pad')
        self.assertEqual(self._last_repainted(self.LAUNCHER), 'pad')
        self.assertEqual(self._last_repainted(self.MIXER), 'pad')
        self.assertEqual(self._last_repainted(self.SEQUENCER), 'seq')

    def test_both_scripts_repaint_at_different_times(self):
        self.knobs.receive_midi(self.LAUNCHER)
        self.assertEqual(sorted(s for _, s in self.scheduled), ['pad', 'seq'])
        self.assertEqual(len(set(d for d, _ in self.scheduled)), 2)

    def test_the_once_a_second_repeat_repaints_nothing(self):
        self.knobs.receive_midi(self.LAUNCHER)
        del self.scheduled[:]
        self.knobs.receive_midi(self.LAUNCHER)
        self.assertEqual(self.scheduled, [])

    def test_device_sysex_is_not_logged_as_unknown(self):
        self.knobs.receive_midi(self.LAUNCHER)
        self.knobs.receive_midi((0xF0, 0x00, 0x32, 0x0D, 0x49, 0x3F, 0xF7))
        self.assertEqual(self.knobs.forwarded_to_framework, [])

    def test_a_missing_sequencer_still_repaints_the_launcher(self):
        self.knobs._instances = lambda name: (
            [self.Script('pad', self.scheduled)] if name == 'MVave_SMC_PAD' else [])
        self.knobs.receive_midi(self.SEQUENCER)
        self.assertEqual([s for _, s in self.scheduled], ['pad'])

    def test_instances_finds_the_loaded_sequencer(self):
        seq_class = SEQ_MODULE.MVave_SMC_STEPSEQ
        saved = list(seq_class._active_instances)
        marker = object()
        seq_class._active_instances[:] = [marker]
        try:
            self.assertEqual(KNOBS_MODULE.MVave_SMC_KNOBS._instances(
                self.knobs, 'MVave_SMC_STEPSEQ'), [marker])
        finally:
            seq_class._active_instances[:] = saved



class StartupPreset(unittest.TestCase):
    """MVave_SMC_KNOBS puts the controller on preset 1, bank A when Live loads."""

    S = PresetSwitchRepaint
    # MidiSuite's own commands, captured with MIDI Monitor's spy on 2026-10-20.
    MIDISUITE = {
        (0x0A, 1): (0xF0, 0x00, 0x32, 0x09, 0x49, 0x00, 0x00, 0x00, 0x02, 0x0A,
                    0x00, 0x00, 0x00, 0x10, 0x00, 0x00, 0x00, 0x01, 0x5E, 0x03, 0xF7),
        (0x0A, 0): (0xF0, 0x00, 0x32, 0x09, 0x49, 0x00, 0x00, 0x00, 0x02, 0x0A,
                    0x00, 0x00, 0x00, 0x10, 0x00, 0x00, 0x00, 0x00, 0x60, 0x03, 0xF7),
        (0x0B, 1): (0xF0, 0x00, 0x32, 0x09, 0x49, 0x00, 0x00, 0x00, 0x02, 0x0B,
                    0x00, 0x00, 0x00, 0x10, 0x00, 0x00, 0x00, 0x01, 0x5C, 0x03, 0xF7),
        (0x0B, 0): (0xF0, 0x00, 0x32, 0x09, 0x49, 0x00, 0x00, 0x00, 0x02, 0x0B,
                    0x00, 0x00, 0x00, 0x10, 0x00, 0x00, 0x00, 0x00, 0x5E, 0x03, 0xF7),
    }
    OK = (0xF0, 0x00, 0x32, 0x01, 0x08, 0x00, 0x00, 0x00, 0x00, 0x7F, 0x01, 0xF7)
    PRESET, BANK = 0x0A, 0x0B

    def setUp(self):
        self.knobs = KNOBS_MODULE.MVave_SMC_KNOBS(FakeCInstance())
        self.scheduled = []
        scripts = {'MVave_SMC_PAD': [self.S.Script('pad', self.scheduled)],
                   'MVave_SMC_STEPSEQ': [self.S.Script('seq', self.scheduled)]}
        self.knobs._instances = lambda name: scripts[name]
        self.knobs.sent = []

    def writes(self):
        return [m for m in self.knobs.sent if m != KNOBS_MODULE.STATE_REQUEST]

    def test_the_writes_are_the_ones_midisuite_sends(self):
        self.assertEqual(KNOBS_MODULE.STATE_PRESET_ADDRESS, self.PRESET)
        self.assertEqual(KNOBS_MODULE.STATE_BANK_ADDRESS, self.BANK)
        for (address, value), captured in self.MIDISUITE.items():
            self.assertEqual(KNOBS_MODULE.state_write(address, value), captured)

    def test_the_default_is_preset_1_bank_a(self):
        self.assertEqual((KNOBS_MODULE.STARTUP_PRESET, KNOBS_MODULE.STARTUP_BANK), (0, 0))

    def test_already_there_writes_nothing(self):
        self.knobs.receive_midi(self.S.LAUNCHER)
        self.assertEqual(self.writes(), [])
        self.assertTrue(self.scheduled)             # and repaints as usual

    def test_another_preset_is_moved_to_preset_1(self):
        self.knobs.receive_midi(self.S.KEYS)
        self.assertEqual(self.writes(), [self.MIDISUITE[(self.PRESET, 0)]])
        self.assertEqual(self.scheduled, [])        # the next status repaints
        self.knobs.receive_midi(self.S.LAUNCHER)
        self.assertEqual(len(self.writes()), 1)
        self.assertEqual(max(self.scheduled)[1], 'pad')

    def test_bank_b_is_moved_to_bank_a(self):
        self.knobs.receive_midi(self.S.MIXER)
        self.assertEqual(self.writes(), [self.MIDISUITE[(self.BANK, 0)]])

    def test_preset_then_bank_one_write_per_status(self):
        self.knobs.receive_midi(self.S.DRUMS)                   # preset 2, bank B
        self.knobs.receive_midi(self.S.MIXER)                   # preset 1, bank B
        self.knobs.receive_midi(self.S.LAUNCHER)
        self.assertEqual(self.writes(), [self.MIDISUITE[(self.PRESET, 0)],
                                         self.MIDISUITE[(self.BANK, 0)]])

    def test_switching_later_is_left_alone(self):
        self.knobs.receive_midi(self.S.LAUNCHER)
        self.knobs.receive_midi(self.S.SEQUENCER)
        self.assertEqual(self.writes(), [])
        self.assertEqual(max(self.scheduled)[1], 'seq')

    def test_a_device_that_ignores_the_write_is_given_up_on(self):
        for _ in range(KNOBS_MODULE.STARTUP_TRIES + 3):
            self.knobs.receive_midi(self.S.SEQUENCER)
        self.assertEqual(len(self.writes()), KNOBS_MODULE.STARTUP_TRIES)
        self.assertEqual(max(self.scheduled)[1], 'seq')         # repaints after all
        self.assertTrue(any('did not take' in line for line in self.knobs._c_instance.log))

    def test_none_leaves_the_controller_where_it_is(self):
        saved = KNOBS_MODULE.STARTUP_PRESET, KNOBS_MODULE.STARTUP_BANK
        KNOBS_MODULE.STARTUP_PRESET = KNOBS_MODULE.STARTUP_BANK = None
        try:
            self.knobs.receive_midi(self.S.DRUMS)
            self.assertEqual(self.writes(), [])
        finally:
            KNOBS_MODULE.STARTUP_PRESET, KNOBS_MODULE.STARTUP_BANK = saved

    def test_the_ok_reply_is_not_logged_as_unknown(self):
        self.knobs.receive_midi(self.OK)
        self.assertEqual(self.knobs.forwarded_to_framework, [])


def _load_keys_mode():
    """MVave_SMC_PAD/KeysMode.py and its pure siblings, without the package
    __init__ (which imports Live): a stand-in package points at the folder."""
    import importlib
    import types
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if 'pad_keys_pkg' not in sys.modules:
        pkg = types.ModuleType('pad_keys_pkg')
        pkg.__path__ = [os.path.join(root, 'MVave_SMC_PAD')]
        sys.modules['pad_keys_pkg'] = pkg
    return importlib.import_module('pad_keys_pkg.KeysMode')


class FakeKeyButton(object):
    def __init__(self, note):
        self.original = note
        self.identifier, self.channel = note, 0
        self.suppress_script_forwarding = False
        self.listeners = []

    def set_identifier(self, value):
        self.identifier = value

    def set_channel(self, value):
        self.channel = value

    def use_default_message(self):
        self.identifier, self.channel = self.original, 0

    def add_value_listener(self, listener):
        self.listeners.append(listener)

    def remove_value_listener(self, listener):
        self.listeners.remove(listener)

    def press(self):
        for listener in list(self.listeners):
            listener(127)
        for listener in list(self.listeners):
            listener(0)


class FakeScaleSong(object):
    """Live 12's song scale: root_note, scale_name, scale_intervals."""
    NAMES = {'Major': (0, 2, 4, 5, 7, 9, 11), 'Minor': (0, 2, 3, 5, 7, 8, 10),
             'Dorian': (0, 2, 3, 5, 7, 9, 10)}

    def __init__(self):
        self._root, self._name = 0, 'Major'
        self.listeners = {'root_note': [], 'scale_name': []}

    def _notify(self, name):
        for listener in list(self.listeners[name]):
            listener()

    @property
    def root_note(self):
        return self._root

    @root_note.setter
    def root_note(self, value):
        self._root = value
        self._notify('root_note')

    @property
    def scale_name(self):
        return self._name

    @scale_name.setter
    def scale_name(self, value):
        if value not in self.NAMES:
            raise RuntimeError('unknown scale %r' % value)
        self._name = value
        self._notify('scale_name')

    @property
    def scale_intervals(self):
        return list(self.NAMES[self._name])

    def add_root_note_listener(self, listener):
        self.listeners['root_note'].append(listener)

    def remove_root_note_listener(self, listener):
        self.listeners['root_note'].remove(listener)

    def add_scale_name_listener(self, listener):
        self.listeners['scale_name'].append(listener)

    def remove_scale_name_listener(self, listener):
        self.listeners['scale_name'].remove(listener)


class FakeKeysSurface(object):
    def __init__(self, song):
        self._song = song
        self.sent, self.messages, self.rebuilds, self.logged = [], [], 0, []
        # Scheduled calls run at once, unless a test holds them to look at
        # the pads mid-flash; run_pending then plays the ticks out.
        self.hold, self.pending = False, []

    def song(self):
        return self._song

    def schedule_message(self, delay, callback, parameter=None):
        if self.hold:
            self.pending.append((delay, callback, parameter))
        else:
            callback(parameter)

    def run_pending(self):
        pending, self.pending = self.pending, []
        for delay, callback, parameter in pending:
            callback(parameter)

    def request_rebuild_midi_map(self):
        self.rebuilds += 1

    def show_message(self, text):
        self.messages.append(text)

    def _send_midi(self, message):
        self.sent.append(tuple(message))

    def _log_exception(self, where):
        self.logged.append(where)


class Keyboard(unittest.TestCase):
    """Preset 3's Launchpad-style keyboard: MVave_SMC_PAD/KeysMode.py."""

    def setUp(self):
        self.mod = _load_keys_mode()
        self.M = _load_launcher_map()
        self.song = FakeScaleSong()
        self.surface = FakeKeysSurface(self.song)
        self.note_map = [FakeKeyButton(n) for n in range(128)]
        self.keys = self.mod.KeysMode(self.surface, self.note_map)

    def tearDown(self):
        # The only fault allowed is Live refusing a scale name it lacks.
        self.assertEqual([w for w in self.surface.logged if w != 'keys: set Live scale'], [])

    def played(self):
        return [self.note_map[n].identifier for n in self.M.KEYS_NOTES]

    def led(self, number):
        return [m[2] for m in self.surface.sent if m[1] == number][-1]

    def settings(self, index):
        self.note_map[self.M.SETTINGS_NOTES[index]].press()

    def test_c_major_rows_go_up_a_fourth(self):
        self.assertEqual(self.played(), [60, 62, 64, 65, 65, 67, 69, 71,
                                         71, 72, 74, 76, 76, 77, 79, 81])

    def test_keyboard_pads_never_reach_the_script(self):
        for note in self.M.KEYS_NOTES:
            self.assertTrue(self.note_map[note].suppress_script_forwarding)

    def test_roots_are_blue_fifths_purple_and_scale_notes_white(self):
        self.assertEqual(self.led(self.M.KEYS_LEDS[0]), self.M.KEYS_ROOT)       # C3
        self.assertEqual(self.led(self.M.KEYS_LEDS[9]), self.M.KEYS_ROOT)       # C4
        self.assertEqual(self.led(self.M.KEYS_LEDS[5]), self.M.KEYS_FIFTH)      # G3
        self.assertEqual(self.led(self.M.KEYS_LEDS[1]), self.M.KEYS_IN_SCALE)   # D3

    def test_the_fifth_colour_is_one_the_palette_tells_apart(self):
        # HARDWARE.md 3.2: 21 and 22-23 are one blue; 24 is the nearest
        # well-separated anchor.
        colours = {self.M.KEYS_ROOT, self.M.KEYS_FIFTH, self.M.KEYS_IN_SCALE,
                   self.M.KEYS_OUT_OF_SCALE}
        self.assertEqual(len(colours), 4)

    def test_pressing_the_lit_root_switches_to_chromatic_and_back(self):
        self.settings(0)    # C is already the root
        self.assertEqual(self.played(), list(range(60, 76)))
        self.assertEqual(self.song.root_note, 0)
        self.assertIn('chromatic', self.surface.messages[-1])
        # C# is outside C major: dark. C, G light as root and fifth.
        self.assertEqual(self.led(self.M.KEYS_LEDS[1]), self.M.KEYS_OUT_OF_SCALE)
        self.assertEqual(self.led(self.M.KEYS_LEDS[7]), self.M.KEYS_FIFTH)
        self.assertEqual(self.led(self.M.KEYS_LEDS[12]), self.M.KEYS_ROOT)
        # The key's own settings pad shows the layout: white-blue, then blue.
        self.assertEqual(self.led(self.M.SETTINGS_LEDS[0]), self.M.KEYS_SETTINGS_CHROMATIC)
        self.settings(0)
        self.assertEqual(self.played()[:4], [60, 62, 64, 65])
        self.assertEqual(self.led(self.M.SETTINGS_LEDS[0]), self.M.KEYS_SETTINGS_ROOT)

    def test_the_chromatic_key_colour_is_its_own(self):
        self.assertNotIn(self.M.KEYS_SETTINGS_CHROMATIC,
                         (self.M.KEYS_SETTINGS_ROOT, self.M.KEYS_SETTINGS_WHITE,
                          self.M.KEYS_SETTINGS_BLACK, self.M.KEYS_SETTINGS_SCALE, 0))

    def test_changing_key_in_chromatic_keeps_the_white_blue(self):
        self.settings(0)    # chromatic
        self.settings(9)    # A, still chromatic
        self.assertEqual(self.led(self.M.SETTINGS_LEDS[9]), self.M.KEYS_SETTINGS_CHROMATIC)
        self.assertEqual(self.led(self.M.SETTINGS_LEDS[0]), self.M.KEYS_SETTINGS_WHITE)

    def test_chromatic_follows_the_scale_and_key(self):
        self.settings(0)
        self.song.scale_name = 'Minor'
        self.settings(2)    # D minor: starts on D, E is in, D# and F# are out
        self.assertEqual(self.played()[:4], [62, 63, 64, 65])
        self.assertEqual([self.led(self.M.KEYS_LEDS[i]) for i in range(5)],
                         [self.M.KEYS_ROOT, self.M.KEYS_OUT_OF_SCALE,
                          self.M.KEYS_IN_SCALE, self.M.KEYS_IN_SCALE,
                          self.M.KEYS_OUT_OF_SCALE])

    def test_locrian_has_no_fifth_to_light(self):
        layout = self.mod.degree
        self.assertIsNone(layout(67, 60, (0, 1, 3, 5, 6, 8, 10)))
        self.assertEqual(layout(66, 60, (0, 1, 3, 5, 6, 8, 10)), 'scale')

    def test_a_root_pad_sets_the_key_in_live_and_on_the_pads(self):
        self.settings(2)    # D
        self.assertEqual(self.song.root_note, 2)
        self.assertEqual(self.played()[0], 62)
        self.assertEqual(self.led(self.M.SETTINGS_LEDS[2]), self.M.KEYS_SETTINGS_ROOT)
        self.assertIn('D Major', self.surface.messages[-1])

    def test_next_scale_writes_live_and_relays_the_pads(self):
        self.settings(self.mod.SCALE_NEXT)
        self.assertEqual(self.song.scale_name, 'Minor')
        self.assertEqual(self.played()[:4], [60, 62, 63, 65])

    def test_previous_scale_wraps_to_the_last_scale(self):
        self.settings(self.mod.SCALE_PREV)
        self.assertIn('Minor Blues', self.surface.messages[-1])
        self.assertEqual(self.played()[:4], [60, 63, 65, 66])

    def scale_led(self, index):
        return self.led(self.M.SETTINGS_LEDS[index])

    def flicker_ticks(self):
        return [p for p in self.surface.pending if p[1] == self.keys._flash_tick]

    def flicker(self, index):
        """The pad's colour now and after each flicker tick, to the end."""
        seen = [self.scale_led(index)]
        for _ in range(20):
            if not self.flicker_ticks():
                return seen
            self.assertEqual({p[0] for p in self.flicker_ticks()},
                             {self.M.KEYS_SCALE_FLASH_TICKS})
            self.surface.run_pending()
            seen.append(self.scale_led(index))
        self.fail('the flicker never ended')

    def expected_flicker(self):
        white, green = self.M.KEYS_SCALE_FLASH, self.M.KEYS_SETTINGS_SCALE
        return [white, green] * self.M.KEYS_SCALE_FLASH_TIMES

    def test_next_scale_flickers_white_when_it_wraps_to_major(self):
        self.settings(self.mod.SCALE_PREV)      # Major -> Minor Blues
        self.surface.hold = True
        self.settings(self.mod.SCALE_NEXT)      # back round to Major
        self.assertIn('C Major', self.surface.messages[-1])
        self.assertEqual(self.scale_led(self.mod.SCALE_PREV), self.M.KEYS_SETTINGS_SCALE)
        self.assertEqual(self.flicker(self.mod.SCALE_NEXT), self.expected_flicker())

    def test_previous_scale_flickers_white_when_it_lands_on_major(self):
        self.settings(self.mod.SCALE_NEXT)      # Major -> Minor
        self.surface.hold = True
        self.settings(self.mod.SCALE_PREV)      # Minor -> Major
        self.assertEqual(self.flicker(self.mod.SCALE_PREV), self.expected_flicker())

    def test_the_flicker_is_three_whites(self):
        self.assertEqual(self.M.KEYS_SCALE_FLASH_TIMES, 3)
        self.settings(self.mod.SCALE_NEXT)
        self.surface.hold = True
        self.settings(self.mod.SCALE_PREV)
        self.assertEqual(self.flicker(self.mod.SCALE_PREV).count(self.M.KEYS_SCALE_FLASH), 3)

    def test_other_scales_do_not_flicker(self):
        self.surface.hold = True
        for _ in range(len(self.mod.SCALES) - 1):   # Minor ... Minor Blues
            self.settings(self.mod.SCALE_NEXT)
            self.assertEqual(self.scale_led(self.mod.SCALE_NEXT), self.M.KEYS_SETTINGS_SCALE)
            self.assertEqual(self.flicker_ticks(), [])

    def test_the_flicker_is_a_colour_the_scale_pads_never_show(self):
        self.assertNotEqual(self.M.KEYS_SCALE_FLASH, self.M.KEYS_SETTINGS_SCALE)
        self.assertNotEqual(self.M.KEYS_SCALE_FLASH, 0)
        self.assertGreater(self.M.KEYS_SCALE_FLASH_TICKS, 0)

    def test_moving_off_major_mid_flicker_ends_it_and_old_ticks_are_ignored(self):
        self.settings(self.mod.SCALE_NEXT)      # Minor
        self.surface.hold = True
        self.settings(self.mod.SCALE_PREV)      # Major: SCALE_PREV flickers
        old_tick = self.flicker_ticks()[0]
        self.settings(self.mod.SCALE_NEXT)      # Minor: the flicker is over
        self.assertEqual(self.scale_led(self.mod.SCALE_PREV), self.M.KEYS_SETTINGS_SCALE)
        self.settings(self.mod.SCALE_PREV)      # Major again: a new flicker
        self.surface.pending.remove(old_tick)
        sent = len(self.surface.sent)
        old_tick[1](old_tick[2])                # the first flicker's tick, late
        self.assertEqual(len(self.surface.sent), sent)
        self.assertEqual(self.flicker(self.mod.SCALE_PREV), self.expected_flicker())

    def test_a_flicker_after_disconnect_paints_nothing(self):
        self.settings(self.mod.SCALE_NEXT)
        self.surface.hold = True
        self.settings(self.mod.SCALE_PREV)
        self.keys.disconnect()
        sent = len(self.surface.sent)
        self.surface.run_pending()
        self.assertEqual(len(self.surface.sent), sent)
        self.assertEqual(self.flicker_ticks(), [])

    def test_a_scale_live_does_not_know_still_plays(self):
        for _ in range(3):  # Major -> Minor -> Dorian -> Mixolydian
            self.settings(self.mod.SCALE_NEXT)
        self.assertEqual(self.played()[:7], [60, 62, 64, 65, 65, 67, 69])
        self.assertEqual(self.played()[6:8], [69, 70])
        self.assertEqual(self.surface.logged, ['keys: set Live scale'])

    def test_the_pads_follow_a_scale_changed_in_live(self):
        self.song.scale_name = 'Dorian'
        self.song.root_note = 9
        self.assertEqual(self.played()[:4], [69, 71, 72, 74])

    def test_octave_buttons_move_and_stop_at_the_ends(self):
        self.settings(self.mod.OCTAVE_UP)
        self.assertEqual(self.played()[0], 72)
        for _ in range(20):
            self.settings(self.mod.OCTAVE_UP)
        self.assertEqual(self.led(self.M.SETTINGS_LEDS[self.mod.OCTAVE_UP]), 0)
        # Pads past MIDI 127 are dark and untranslated.
        self.assertEqual(self.led(self.M.KEYS_LEDS[15]), 0)
        self.assertEqual(self.note_map[self.M.KEYS_NOTES[15]].identifier,
                         self.M.KEYS_NOTES[15])

    def test_octave_pads_light_in_the_octave_colour(self):
        self.assertEqual(len(self.M.KEYS_OCTAVE_COLOURS),
                         self.M.KEYS_OCTAVE_MAX - self.M.KEYS_OCTAVE_MIN + 1)
        down = self.M.SETTINGS_LEDS[self.mod.OCTAVE_DOWN]
        up = self.M.SETTINGS_LEDS[self.mod.OCTAVE_UP]
        for _ in range(20):
            self.settings(self.mod.OCTAVE_DOWN)
        colours = self.M.KEYS_OCTAVE_COLOURS
        lowest, highest = self.M.KEYS_OCTAVE_MIN, self.M.KEYS_OCTAVE_MAX
        for octave in range(lowest, highest + 1):
            # Each pad shows the octave it moves to; dark at its end.
            step = octave - lowest
            self.assertEqual(self.led(down), colours[step - 1] if octave > lowest else 0)
            self.assertEqual(self.led(up), colours[step + 1] if octave < highest else 0)
            self.settings(self.mod.OCTAVE_UP)
        self.assertEqual(len(set(colours)), len(colours))
        self.assertNotIn(self.M.KEYS_SETTINGS_SCALE, colours)
        self.assertNotIn(0, colours)

    def test_octave_pads_preview_their_octave_from_the_start(self):
        colours = self.M.KEYS_OCTAVE_COLOURS
        step = self.M.KEYS_OCTAVE - self.M.KEYS_OCTAVE_MIN
        self.assertEqual(self.led(self.M.SETTINGS_LEDS[self.mod.OCTAVE_DOWN]), colours[step - 1])
        self.assertEqual(self.led(self.M.SETTINGS_LEDS[self.mod.OCTAVE_UP]), colours[step + 1])

    def test_no_scale_note_can_press_another_button_on_this_port(self):
        # Live looks a translated note up in the script's own map. On channel
        # 1, a scale note of 55 soloed track 3 (seen on hardware 2026-10-17).
        seq_channels = {C.PAD_CHANNEL, C.BUTTON_CHANNEL}
        for octave in range(self.M.KEYS_OCTAVE_MIN, self.M.KEYS_OCTAVE_MAX + 1):
            self.keys._octave = octave
            self.keys._translate()
            for i, note in enumerate(self.M.KEYS_NOTES):
                button = self.note_map[note]
                if (button.identifier, button.channel) == (note, 0):
                    continue    # off the MIDI range, untranslated
                self.assertNotEqual(button.channel, self.M.BUTTONCHANNEL)
                self.assertNotIn(button.channel, seq_channels)

    def test_disconnect_removes_every_listener(self):
        self.keys.disconnect()
        self.assertEqual(self.song.listeners, {'root_note': [], 'scale_name': []})
        for note in self.M.SETTINGS_NOTES:
            self.assertEqual(self.note_map[note].listeners, [])

    def test_the_preset_file_matches_the_script(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data = open(os.path.join(root, 'presets', 'preset3-keys.spc'), 'rb').read()
        for first, notes, leds in ((32, self.M.KEYS_NOTES, self.M.KEYS_LEDS),
                                   (48, self.M.SETTINGS_NOTES, self.M.SETTINGS_LEDS)):
            for pad in range(16):
                record = data[211 + (first + pad) * 26:][:26]
                self.assertEqual((record[0], record[2], record[8]),
                                 (0x04, notes[pad], leds[pad]))



class Chords(unittest.TestCase):
    """Preset 4: KeysMode(chords=True), beside preset 3's keyboard."""

    def setUp(self):
        self.mod = _load_keys_mode()
        self.M = _load_launcher_map()
        self.song = FakeScaleSong()
        self.surface = FakeKeysSurface(self.song)
        self.note_map = [FakeKeyButton(n) for n in range(128)]
        self.keys = self.mod.KeysMode(self.surface, self.note_map)
        self.chords = self.mod.KeysMode(self.surface, self.note_map, chords=True)

    def tearDown(self):
        self.assertEqual([w for w in self.surface.logged if w != 'keys: set Live scale'], [])

    def played(self, notes=None):
        return [self.note_map[n].identifier for n in notes or self.M.CHORDS_NOTES]

    def led(self, number):
        return [m[2] for m in self.surface.sent if m[1] == number][-1]

    def settings(self, index):
        self.note_map[self.M.CHORDS_SETTINGS_NOTES[index]].press()

    def test_c_major_chords_go_up_the_scale_one_pad_at_a_time(self):
        # I ii iii IV / V vi vii I / ii ... with no repeats.
        self.assertEqual(self.played(), [60, 62, 64, 65, 67, 69, 71, 72,
                                         74, 76, 77, 79, 81, 83, 84, 86])
        self.assertEqual(self.chords.targets(), self.played())

    def test_root_chords_are_blue_and_the_fifths_purple(self):
        leds = self.M.CHORDS_LEDS
        self.assertEqual(self.led(leds[0]), self.M.KEYS_ROOT)     # I
        self.assertEqual(self.led(leds[7]), self.M.KEYS_ROOT)     # I, up an octave
        self.assertEqual(self.led(leds[4]), self.M.KEYS_FIFTH)    # V
        self.assertEqual(self.led(leds[1]), self.M.KEYS_IN_SCALE)

    def test_preset_3_is_untouched(self):
        self.assertEqual(self.played(self.M.KEYS_NOTES),
                         [60, 62, 64, 65, 65, 67, 69, 71, 71, 72, 74, 76, 76, 77, 79, 81])
        self.assertIn('keys', self.keys.describe())
        self.assertIn('chords', self.chords.describe())

    def test_the_lit_root_changes_nothing_and_shows_pink(self):
        before = self.played()
        self.settings(0)
        self.assertEqual(self.played(), before)
        self.assertEqual(self.led(self.M.CHORDS_SETTINGS_LEDS[0]), self.M.KEYS_SETTINGS_CHORDS)
        self.assertNotIn(self.M.KEYS_SETTINGS_CHORDS,
                         (self.M.KEYS_SETTINGS_ROOT, self.M.KEYS_SETTINGS_CHROMATIC,
                          self.M.KEYS_SETTINGS_WHITE, self.M.KEYS_SETTINGS_BLACK,
                          self.M.KEYS_SETTINGS_SCALE, 0))

    def test_key_and_scale_are_shared_with_preset_3_and_the_octave_is_not(self):
        self.settings(9)                        # A, on preset 4's page
        self.settings(self.mod.SCALE_NEXT)      # Minor
        self.settings(self.mod.OCTAVE_DOWN)
        self.assertEqual(self.played()[:8], [57, 59, 60, 62, 64, 65, 67, 69])
        # Preset 3 follows the key and scale through Live, not the octave.
        self.assertEqual(self.played(self.M.KEYS_NOTES)[:4], [69, 71, 72, 74])

    def test_a_scale_changed_in_live_moves_the_chords(self):
        self.song.scale_name = 'Dorian'
        self.song.root_note = 2
        self.assertEqual(self.played()[:4], [62, 64, 65, 67])

    def test_chord_pads_never_reach_the_script_or_another_button(self):
        for note in self.M.CHORDS_NOTES:
            button = self.note_map[note]
            self.assertTrue(button.suppress_script_forwarding)
            self.assertEqual(button.channel, self.M.KEYS_CHANNEL)

    def test_the_notes_and_leds_are_free(self):
        M = self.M
        notes = (set(M.CHORDS_NOTES) | set(M.CHORDS_SETTINGS_NOTES))
        leds = (set(M.CHORDS_LEDS) | set(M.CHORDS_SETTINGS_LEDS))
        self.assertEqual(len(notes), 32)
        self.assertEqual(len(leds), 32)
        clips = [n for row in M.CLIPNOTEMAP for n in row]
        mixer = M.TRACKMUTE + M.TRACKSOLO + M.TRACKREC + M.TRACKSTOP
        taken_notes = (set(clips) | set(mixer) | set(M.KEYS_NOTES) | set(M.SETTINGS_NOTES)
                       | {M.PLAY, M.STOP, M.REC, M.TRACKLEFT, M.TRACKRIGHT}
                       | set(C.PAD_NOTES) | {C.BTN_PLAY, C.BTN_VIEW, C.BTN_MOD,
                                            C.BTN_LEFT, C.BTN_RIGHT})
        taken_leds = ({n + M.PAD_LED_OFFSET for n in clips}
                      | {n + M.MIXER_LED_OFFSET for n in mixer}
                      | set(M.KEYS_LEDS) | set(M.SETTINGS_LEDS) | set(C.LED_NOTES)
                      | {M.PLAY, M.STOP, M.REC, M.TRACKLEFT, M.TRACKRIGHT}
                      | {C.BTN_PLAY, C.BTN_VIEW, C.BTN_MOD, C.BTN_LEFT, C.BTN_RIGHT})
        self.assertEqual(notes & taken_notes, set())
        self.assertEqual(leds & taken_leds, set())
        for pad in range(16):
            # LED == own note leaves a pad stuck white (make_presets.check).
            self.assertNotEqual(M.CHORDS_NOTES[pad], M.CHORDS_LEDS[pad])
            self.assertNotEqual(M.CHORDS_SETTINGS_NOTES[pad], M.CHORDS_SETTINGS_LEDS[pad])

    def test_the_preset_file_matches_the_script(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, 'presets', 'preset4-chords.spc'), 'rb') as f:
            data = f.read()
        for first, notes, leds in ((32, self.M.CHORDS_NOTES, self.M.CHORDS_LEDS),
                                   (48, self.M.CHORDS_SETTINGS_NOTES,
                                    self.M.CHORDS_SETTINGS_LEDS),
                                   (112, self.M.CHORDS_SETTINGS_NOTES,
                                    self.M.CHORDS_SETTINGS_LEDS)):
            for pad in range(16):
                record = data[211 + (first + pad) * 26:][:26]
                self.assertEqual((record[0], record[2], record[8]),
                                 (0x04, notes[pad], leds[pad]))

    def test_preset_4_has_preset_3s_buttons_and_knobs(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        read = lambda name: open(os.path.join(root, 'presets', name), 'rb').read()
        keys, chords = read('preset3-keys.spc'), read('preset4-chords.spc')
        self.assertEqual(keys[:211], chords[:211])      # buttons and encoders


class FakeChordParameter(object):
    def __init__(self, name, value=0.0, minimum=0.0, maximum=1.0):
        self.name, self.value, self.min, self.max = name, value, minimum, maximum

    def str_for_value(self, value):
        return str(value)


class FakeChordDevice(object):
    def __init__(self, class_name='MidiChord', on=True):
        self.class_name = class_name
        self.parameters = [FakeChordParameter('Device On', 1.0 if on else 0.0)]
        if class_name == 'MidiChord':
            # Live 12.4's names, as Log.txt listed them on 2026-10-20.
            for n in range(1, 7):
                self.parameters += [FakeChordParameter('Shift%d' % n, 0.0, -36.0, 36.0),
                                    FakeChordParameter('Shift%d Scale Degrees' % n,
                                                       0.0, -21.0, 21.0),
                                    FakeChordParameter('Velocity%d' % n),
                                    FakeChordParameter('Chance%d' % n)]
            self.parameters.append(FakeChordParameter('Use Current Scale'))

    def value(self, name):
        return [p.value for p in self.parameters if p.name == name][0]


class FakeChordTrack(object):
    def __init__(self, arm=True, midi=True):
        self.arm, self.can_be_armed, self.has_midi_input = arm, True, midi
        self.current_monitoring_state = 1   # Auto
        self.devices = [FakeChordDevice('InstrumentVector')]
        self.inserted = []

    def insert_device(self, name, index):
        self.inserted.append((name, index))
        self.devices.insert(index, FakeChordDevice())


class FakeSongView(object):
    def __init__(self):
        self.listeners = []

    def add_selected_track_listener(self, listener):
        self.listeners.append(listener)

    def remove_selected_track_listener(self, listener):
        self.listeners.remove(listener)


def _load_chord_devices():
    import importlib
    _load_keys_mode()   # sets up the stand-in package
    return importlib.import_module('pad_keys_pkg.ChordDevices')


class ChordDevices(unittest.TestCase):
    """Preset 4's Chord device on the tracks the pads play: MVave_SMC_PAD/ChordDevices.py."""

    def setUp(self):
        self.mod = _load_chord_devices()
        self.M = _load_launcher_map()
        self.song = FakeScaleSong()
        self.song.view = FakeSongView()
        self.armed = FakeChordTrack()
        self.idle = FakeChordTrack(arm=False)
        self.audio = FakeChordTrack(midi=False)
        self.song.tracks = [self.armed, self.idle, self.audio]
        self.surface = FakeKeysSurface(self.song)
        self.surface.log_message = lambda text: None
        self.chords = self.mod.ChordDevices(self.surface)

    def tearDown(self):
        self.assertEqual(self.surface.logged, [])

    def test_nothing_happens_until_preset_4_is_up(self):
        self.song.view.listeners[0]()
        self.assertEqual(self.armed.inserted, [])

    def test_preset_4_adds_a_chord_device_in_key_in_front_of_the_instrument(self):
        self.chords.set_active(True)
        self.assertEqual(self.armed.inserted, [(self.M.CHORDS_DEVICE, 0)])
        chord = self.armed.devices[0]
        self.assertEqual(chord.value('Use Current Scale'), 1.0)
        # In scale mode Live plays the Scale Degrees shifts, not the semitones.
        self.assertEqual([chord.value('Shift%d Scale Degrees' % n) for n in (1, 2, 3)],
                         [2, 4, 0])
        self.assertEqual([chord.value('Shift%d' % n) for n in (1, 2)], [0, 0])
        self.assertEqual(self.idle.inserted, [])
        self.assertEqual(self.audio.inserted, [])

    def test_another_preset_switches_it_off_and_preset_4_back_on(self):
        self.chords.set_active(True)
        chord = self.armed.devices[0]
        self.chords.set_active(False)
        self.assertEqual(chord.value('Device On'), 0.0)
        self.chords.set_active(True)
        self.assertEqual(len(self.armed.inserted), 1)   # the same one, again
        self.assertEqual(chord.value('Device On'), 1.0)

    def test_a_chord_device_already_there_keeps_its_shape_and_switch(self):
        mine = FakeChordDevice()
        [p for p in mine.parameters if p.name == 'Shift1'][0].value = 3.0   # the user's
        self.armed.devices.insert(0, mine)
        self.chords.set_active(True)
        self.chords.set_active(False)
        self.assertEqual(self.armed.inserted, [])
        self.assertEqual(mine.value('Shift1'), 3.0)
        self.assertEqual(mine.value('Device On'), 1.0)  # it was on: left on

    def test_a_chord_device_that_was_off_is_switched_back_off(self):
        mine = FakeChordDevice(on=False)
        self.armed.devices.insert(0, mine)
        self.chords.set_active(True)
        self.assertEqual(mine.value('Device On'), 1.0)
        self.chords.set_active(False)
        self.assertEqual(mine.value('Device On'), 0.0)

    def test_a_track_armed_later_gets_its_chord_device(self):
        self.chords.set_active(True)
        self.idle.arm = True
        self.song.view.listeners[0]()
        self.assertEqual(len(self.idle.inserted), 1)
        self.chords.set_active(False)
        self.assertEqual(self.idle.devices[0].value('Device On'), 0.0)

    def test_a_chord_without_scale_degrees_is_left_alone(self):
        def older(name, index):
            device = FakeChordDevice()
            device.parameters = [p for p in device.parameters
                                 if 'Scale' not in p.name]
            self.armed.devices.insert(index, device)
        self.armed.insert_device = older
        self.chords.set_active(True)
        self.assertIn('Use Current Scale', self.chords.problem)
        self.assertEqual(self.armed.devices[0].value('Shift1'), 0.0)

    def test_without_insert_device_it_says_to_add_one(self):
        self.armed.insert_device = None
        self.chords.set_active(True)
        self.assertIn('Chord device', self.chords.problem)

    def test_disconnect_removes_the_selected_track_listener(self):
        self.chords.disconnect()
        self.assertEqual(self.song.view.listeners, [])


class PresetTellsThePadScript(unittest.TestCase):

    class Pad(object):
        def __init__(self):
            self.presets = []

        def set_preset(self, preset):
            self.presets.append(preset)

        def refresh_state(self):
            pass

        def schedule_message(self, delay, callback, parameter=None):
            # Live's ControlSurface drops a falsy parameter: model that, so a
            # preset 0 passed as one fails here as it did in Live.
            if parameter:
                callback(parameter)
            else:
                callback()

    @staticmethod
    def with_preset(status, preset):
        packet = KNOBS_MODULE.unpack7(status[1:-1])
        packet[KNOBS_MODULE.STATUS_PRESET] = preset
        packet[26] = ~sum(packet[6:26]) & 0xFF
        return (0xF0,) + tuple(KNOBS_MODULE.pack7(packet)) + (0xF7,)

    def test_every_switch_says_which_preset_is_up(self):
        knobs = KNOBS_MODULE.MVave_SMC_KNOBS(FakeCInstance())
        knobs._startup_pending = False
        pad = self.Pad()
        knobs._instances = lambda name: [pad] if name == 'MVave_SMC_PAD' else []
        P = PresetSwitchRepaint
        for status in (P.LAUNCHER, P.KEYS, self.with_preset(P.KEYS, 3), P.LAUNCHER):
            knobs.receive_midi(status)
        self.assertEqual(pad.presets, [0, 2, 3, 0])
        self.assertEqual(KNOBS_MODULE.CHORDS_PRESET, _load_launcher_map().CHORDS_PRESET)

    def test_chord_repeats_follow_the_chord_pads(self):
        knobs = KNOBS_MODULE.MVave_SMC_KNOBS(FakeCInstance())
        targets = list(range(60, 76))
        knobs.chords_changed(targets)
        buttons = knobs._chord_repeat_buttons
        self.assertEqual([b.original[0] for b in buttons],
                         list(_load_launcher_map().CHORDS_NOTES))
        self.assertEqual((buttons[0].identifier, buttons[0].channel), (60, 1))
        self.assertEqual([b.identifier for b in knobs._repeat_buttons],
                         list(KNOBS_MODULE.KEYS_REPEAT_NOTES))   # preset 3's untouched

class PassThrough(unittest.TestCase):
    """MVave_SMC_KNOBS passing plain MIDI to the track now that Track is off on
    SMC-PAD-Master: drum pads, preset 3's knobs and note repeat."""

    def setUp(self):
        self.saved = list(KNOBS_MODULE.MVave_SMC_KNOBS._active_instances)
        KNOBS_MODULE.MVave_SMC_KNOBS._active_instances[:] = []
        ice = sys.modules['_Framework.InputControlElement'].InputControlElement
        ice.created[:] = []
        self.knobs = KNOBS_MODULE.MVave_SMC_KNOBS(FakeCInstance())
        self.elements = list(ice.created)

    def tearDown(self):
        KNOBS_MODULE.MVave_SMC_KNOBS._active_instances[:] = self.saved

    def find(self, msg_type, channel, identifier):
        return [e for e in self.elements
                if (e.msg_type, e.original) == (msg_type, (identifier, channel))]

    def test_drum_pads_and_their_repeats_reach_the_track_unchanged_but_on_channel_2(self):
        for channel in (9, 0):
            for note in range(36, 52):
                element, = self.find(0, channel, note)
                self.assertEqual((element.identifier, element.channel), (note, 1))
                self.assertTrue(element.suppress_script_forwarding)

    def test_preset_3_knobs_are_the_scripts_not_the_tracks(self):
        # They play the selected device now; passed through as well, a synth
        # that answers CCs would move twice.
        for cc in KNOBS_MODULE.PARAM_BY_CC:
            self.assertEqual(self.find(1, 0, cc), [])
        self.assertFalse(set(KNOBS_MODULE.PARAM_BY_CC)
                         & (set(KNOBS_MODULE.MACRO_BY_CC) | set(KNOBS_MODULE.NAV_CCS)))

    def test_repeats_go_nowhere_until_the_keyboard_says_what_to_play(self):
        for note in range(85, 101):
            element, = self.find(0, 9, note)
            self.assertEqual((element.identifier, element.channel), (note, 9))
            self.assertTrue(element.suppress_script_forwarding)

    def test_the_keyboard_table_retargets_the_repeats(self):
        targets = list(range(60, 76))
        targets[15] = None
        self.knobs.keys_changed(targets)
        buttons = self.knobs._repeat_buttons
        self.assertEqual((buttons[0].identifier, buttons[0].channel), (60, 1))
        self.assertEqual((buttons[15].identifier, buttons[15].channel), (100, 9))

    def test_a_key_change_on_the_controller_reaches_the_repeats(self):
        mod = _load_keys_mode()
        M = _load_launcher_map()
        surface = FakeKeysSurface(FakeScaleSong())
        note_map = [FakeKeyButton(n) for n in range(128)]
        keys = mod.KeysMode(surface, note_map)
        note_map[M.SETTINGS_NOTES[2]].press()   # D
        self.assertEqual([b.identifier for b in self.knobs._repeat_buttons], keys.targets())
        self.assertEqual(self.knobs._repeat_buttons[0].identifier, 62)

    def test_the_tables_agree_with_the_pad_script_and_the_presets(self):
        import importlib.util
        M = _load_launcher_map()
        self.assertEqual(KNOBS_MODULE.KEYS_REPEAT_NOTES, M.KEYS_NOTES)
        self.assertEqual(KNOBS_MODULE.PASS_CHANNEL, M.KEYS_CHANNEL)
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        spec = importlib.util.spec_from_file_location(
            'make_presets', os.path.join(root, 'tools', 'make_presets.py'))
        presets = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(presets)
        # Slots in panel reading order, top-left first: encoders 7 8 5 6 3 4 1 2.
        reading_order = (7, 8, 5, 6, 3, 4, 1, 2)
        ccs = ([presets.PARAM_CCS_BANK_1[e] for e in reading_order]
               + [presets.PARAM_CCS_BANK_2[e] for e in reading_order])
        self.assertEqual([KNOBS_MODULE.PARAM_BY_CC[cc] for cc in ccs], list(range(16)))
        self.assertEqual(KNOBS_MODULE.DRUM_NOTES,
                         tuple(presets.DRUM_BOTTOM_LEFT + i for i in range(16)))



class FakeBanks(object):
    """The slice of Live's IndexedDict the bank table is: bank name -> dict."""

    def __init__(self, *banks):
        self._banks = banks

    def __len__(self):
        return len(self._banks)

    def value_by_index(self, index):
        return {'Parameters': self._banks[index]}


def named(name, minimum=0.0, maximum=127.0):
    param = FakeParameter(minimum, maximum)
    param.original_name = name
    return param


class DeviceBanks(KnobScript):
    """Preset 3's knobs play the selected device in Live's own banks."""

    def setUp(self):
        KnobScript.setUp(self)
        self.saved = (KNOBS_MODULE.BANK_DEFINITIONS, KNOBS_MODULE.BANK_PARAMETERS_KEY)
        KNOBS_MODULE.BANK_PARAMETERS_KEY = 'Parameters'
        KNOBS_MODULE.BANK_DEFINITIONS = {
            'InstrumentVector': FakeBanks(
                ('Filter 1 Freq', 'Filter 1 Res', 'Amp Attack', 'Amp Release'),
                ('LFO 1 Rate', 'Missing Param'),
                ('Never Reached',)),
        }

    def tearDown(self):
        KNOBS_MODULE.BANK_DEFINITIONS, KNOBS_MODULE.BANK_PARAMETERS_KEY = self.saved
        KnobScript.tearDown(self)

    def _wavetable(self):
        names = ['Device On', 'Amp Release', 'LFO 1 Rate', 'Filter 1 Res',
                 'Filter 1 Freq', 'Amp Attack', 'Never Reached']
        device = FakeDevice([named(n) for n in names], name='Wavetable')
        device.class_name = 'InstrumentVector'
        self.knobs._device.set_device(device)
        return dict((p.original_name, p) for p in device.parameters)

    def _cc(self, slot):
        return KNOBS_MODULE.PARAM_CC_FIRST + slot

    def test_bank_1_follows_live_s_table_by_name_not_position(self):
        p = self._wavetable()
        self._turn(self._cc(0), 65)
        self._turn(self._cc(1), 65)
        self._turn(self._cc(1), 65)
        self.assertEqual((p['Filter 1 Freq'].value, p['Filter 1 Res'].value), (1.0, 2.0))
        self.assertEqual(p['Amp Release'].value, 0.0)

    def test_knob_bank_2_is_live_s_second_bank(self):
        p = self._wavetable()
        self._turn(self._cc(8), 65)
        self.assertEqual(p['LFO 1 Rate'].value, 1.0)

    def test_an_empty_or_unknown_slot_does_nothing_and_says_so_once(self):
        p = self._wavetable()
        for slot in (4, 9, 15):             # short bank, unknown name, no bank
            self._turn(self._cc(slot), 65)
            self._turn(self._cc(slot), 65)
        self.assertTrue(all(param.value == 0.0 for param in p.values()))
        said = [l for l in self.knobs._c_instance.log if 'knob slot' in l]
        self.assertEqual(len(said), 3)

    def test_a_device_live_has_no_bank_for_plays_parameters_in_order(self):
        # A plugin: whatever its Configure button put in the list, in order.
        params = [named('p%d' % i) for i in range(20)]
        device = FakeDevice(params, name='Some VST')
        device.class_name = 'PluginDevice'
        self.knobs._device.set_device(device)
        self._turn(self._cc(0), 65)
        self._turn(self._cc(15), 65)
        self.assertEqual([p.value for p in params[:18]],
                         [0.0, 1.0] + [0.0] * 14 + [1.0, 0.0])

    def test_switching_devices_rebinds_the_knobs(self):
        self._wavetable()
        self._turn(self._cc(0), 65)
        params = [named('Device On'), named('Macro 1')]
        rack = FakeDevice(params, name='Rack')
        rack.class_name = 'InstrumentGroupDevice'
        self.knobs._device.set_device(rack)
        self._turn(self._cc(0), 65)
        self.assertEqual(params[1].value, 1.0)

    def test_without_live_s_table_everything_plays_in_order(self):
        KNOBS_MODULE.BANK_DEFINITIONS = {}
        names = ['Device On', 'Amp Release', 'LFO 1 Rate']
        device = FakeDevice([named(n) for n in names], name='Wavetable')
        device.class_name = 'InstrumentVector'
        self.knobs._device.set_device(device)
        self._turn(self._cc(0), 65)
        self.assertEqual(device.parameters[1].value, 1.0)


class PinnedClip(SeqTest):
    """Away from preset 2 the sequencer keeps its clip (MVave_SMC_KNOBS says
    which preset is up), so playing preset 3 on another track loses nothing."""

    def test_selection_moves_are_ignored_while_away(self):
        self.seq.set_on_screen(False)
        self.song.view.select(FakeClip(loop_start=0.0, loop_end=4.0))
        self.assertIs(self.seq._clip, self.clip)

    def test_back_on_preset_2_it_keeps_the_clip_then_follows_again(self):
        self.seq.set_on_screen(False)
        other = FakeClip(loop_start=0.0, loop_end=4.0)
        self.song.view.select(other)
        self.seq.set_on_screen(True)
        self.assertIs(self.seq._clip, self.clip)
        self.song.view.select(other)
        self.assertIs(self.seq._clip, other)

    def test_a_clip_deleted_while_away_is_replaced_by_the_selection(self):
        self.seq.set_on_screen(False)
        other = FakeClip(loop_start=0.0, loop_end=4.0)
        self.song.view.select(other)
        self.clip.dead = True
        self.seq.set_on_screen(True)
        self.assertIs(self.seq._clip, other)

    def test_a_clip_deleted_while_away_does_not_wedge_the_selection(self):
        self.seq.set_on_screen(False)
        self.clip.dead = True
        other = FakeClip(loop_start=0.0, loop_end=4.0)
        self.song.view.select(other)
        self.assertIs(self.seq._clip, other)


class PresetTellsTheSequencer(unittest.TestCase):

    class Seq(object):
        def __init__(self):
            self.calls = []

        def set_on_screen(self, value):
            self.calls.append(value)

        def refresh_state(self):
            pass

        def schedule_message(self, delay, callback):
            pass

    def test_only_preset_2_counts_as_on_screen(self):
        knobs = KNOBS_MODULE.MVave_SMC_KNOBS(FakeCInstance())
        seq = self.Seq()
        knobs._instances = lambda name: [seq] if name == 'MVave_SMC_STEPSEQ' else []
        P = PresetSwitchRepaint
        for status in (P.LAUNCHER, P.SEQUENCER, P.DRUMS, P.MIXER):
            knobs.receive_midi(status)
        self.assertEqual(seq.calls, [False, True, True, False])



class Feedback(SeqTest):
    """Beat markers and the status-bar messages."""

    def setUp(self):
        # Shipped off since 2026-10-20; tested lit so the gating still shows.
        # Both: the script copied the constant in with `import *`, and the
        # assertions below read it from C.
        self.addCleanup(setattr, C, 'COLOR_STEP_DOWNBEAT', C.COLOR_STEP_DOWNBEAT)
        self.addCleanup(setattr, SEQ_MODULE, 'COLOR_STEP_DOWNBEAT',
                        SEQ_MODULE.COLOR_STEP_DOWNBEAT)
        C.COLOR_STEP_DOWNBEAT = SEQ_MODULE.COLOR_STEP_DOWNBEAT = 21
        SeqTest.setUp(self)

    def test_beat_markers_light_empty_beats_in_focus(self):
        self.seq.refresh_state()
        leds = self.leds()
        for index in (0, 4, 8, 12):
            self.assertEqual(leds[index], C.COLOR_STEP_DOWNBEAT)
        for index in (1, 2, 3, 5, 15):
            self.assertEqual(leds[index], C.COLOR_STEP_EMPTY)

    def test_a_note_on_a_beat_beats_the_marker(self):
        self.press(4)
        self.assertEqual(self.leds()[4], C.COLOR_STEP_ON)
        self.press(4)
        self.assertEqual(self.leds()[4], C.COLOR_STEP_DOWNBEAT)

    def test_no_beat_markers_past_the_loop_end(self):
        self.clip.set_loop_end(self.clip.loop_start + 6 * C.STEP)
        self.assertEqual(self.seq._led[4], C.COLOR_STEP_DOWNBEAT)
        self.assertEqual(self.seq._led[8], C.COLOR_STEP_OFF)

    def test_no_beat_markers_in_the_overview(self):
        # Its left column is always a beat, and blue is a lane colour there.
        self.button(C.BTN_VIEW)
        self.assertEqual(self.leds()[0], C.COLOR_STEP_EMPTY)
        self.assertEqual(self.leds()[12], C.COLOR_STEP_EMPTY)

    def test_a_pad_edit_names_the_step(self):
        self.press(4)
        self.assertEqual(self.seq.messages[-1], 'C1 step 5/16 on')
        self.press(4)
        self.assertEqual(self.seq.messages[-1], 'C1 step 5/16 off')

    def test_a_pad_edit_names_the_drum(self):
        pads = {36: FakeDrumPad(36, [FakeDevice([], 'Drum')])}
        pads[36].name = 'Kick'
        self.song.view.selected_track = FakeTrack([FakeDrumRack(pads)])
        self.press(0)
        self.assertEqual(self.seq.messages[-1], 'Kick (C1) step 1/16 on')

    def test_paging_names_the_steps(self):
        self.clip.set_loop_end(self.clip.loop_start + 64 * C.STEP)
        self.button(C.BTN_RIGHT)
        self.assertIn('Steps 17-32 of 64', self.seq.messages[-1])
        self.assertIn('page 2/4', self.seq.messages[-1])

    def test_following_the_playhead_names_the_steps(self):
        self.clip.set_loop_end(self.clip.loop_start + 32 * C.STEP)
        self.clip.play(17 * C.STEP)
        self.assertEqual(self.seq._bank, 1)
        self.assertIn('Steps 17-32 of 32', self.seq.messages[-1])

    def test_switching_view_names_the_overview(self):
        self.button(C.BTN_VIEW)
        self.assertIn('Overview', self.seq.messages[-1])
        self.assertIn('steps 1-4 of 16', self.seq.messages[-1])

    def test_messages_can_be_switched_off(self):
        seqmod = SEQ_MODULE
        originals = seqmod.SHOW_PAGE_MESSAGES, seqmod.SHOW_STEP_MESSAGES
        try:
            seqmod.SHOW_PAGE_MESSAGES = seqmod.SHOW_STEP_MESSAGES = False
            self.seq.messages = []
            self.press(0)
            self.button(C.BTN_VIEW)
            self.assertEqual(self.seq.messages, [])
        finally:
            seqmod.SHOW_PAGE_MESSAGES, seqmod.SHOW_STEP_MESSAGES = originals


class DrumColours(SeqTest):
    """Each drum's steps light in its kind's colour."""

    DRUM_COLORS = True

    def colour(self, kind):
        return dict((k, c) for k, c, _, _ in C.DRUM_KINDS)[kind]

    def named_kit(self, names):
        pads = {}
        for pitch, name in names.items():
            pads[pitch] = FakeDrumPad(pitch, [FakeDevice([], 'Drum')])
            pads[pitch].name = name
        self.song.view.selected_track = FakeTrack([FakeDrumRack(pads)])

    def test_names_decide_the_kind(self):
        drum_color = SEQ_MODULE.drum_color
        self.assertEqual(drum_color(60, 'Kick 808'), self.colour('kick'))
        self.assertEqual(drum_color(60, 'BD 909'), self.colour('kick'))
        self.assertEqual(drum_color(60, 'Clap Wide'), self.colour('snare'))
        self.assertEqual(drum_color(60, 'Closed HiHat'), self.colour('hat'))
        self.assertEqual(drum_color(60, 'HH open'), self.colour('hat'))
        self.assertEqual(drum_color(60, 'Crash 2'), self.colour('cymbal'))
        self.assertEqual(drum_color(60, 'Low Tom'), self.colour('tom'))
        self.assertEqual(drum_color(60, 'Kick Snare Layer'), self.colour('kick'))

    def test_short_words_match_only_whole(self):
        # 'sd' must not make "Bassdrive" a snare, nor 'hh' anything with hh in it.
        self.assertEqual(SEQ_MODULE.drum_color(60, 'Bassdrive'), C.COLOR_DRUM_OTHER)

    def test_a_name_beats_the_general_midi_map(self):
        self.assertEqual(SEQ_MODULE.drum_color(36, 'Bongo'), C.COLOR_DRUM_OTHER)

    def test_no_name_falls_back_to_general_midi(self):
        drum_color = SEQ_MODULE.drum_color
        self.assertEqual(drum_color(36), self.colour('kick'))
        self.assertEqual(drum_color(42), self.colour('hat'))
        self.assertEqual(drum_color(49), self.colour('cymbal'))
        self.assertEqual(drum_color(60), C.COLOR_DRUM_OTHER)

    def test_kind_colours_avoid_the_playhead(self):
        for kind, colour, words, pitches in C.DRUM_KINDS:
            self.assertNotIn(colour, (C.COLOR_PLAYHEAD, C.COLOR_PLAYHEAD_ON), kind)
            self.assertTrue(0 < colour <= 127, kind)

    def test_focus_notes_light_in_the_drums_colour(self):
        self.named_kit({36: 'Crash 1'})
        self.press(1)
        self.assertEqual(self.leds()[1], self.colour('cymbal'))

    def test_focus_without_a_rack_uses_general_midi(self):
        self.press(1)                                   # lane 36: a kick
        self.assertEqual(self.leds()[1], self.colour('kick'))

    def test_the_playhead_still_whitens_a_coloured_step(self):
        self.press(1)
        self.clip.play(1 * C.STEP)
        self.assertEqual(self.leds()[1], C.COLOR_PLAYHEAD_ON)

    def test_the_picker_shows_every_drum_in_its_colour(self):
        self.named_kit({36: 'Kick', 38: 'Snare', 39: 'Clap', 40: 'Zap'})
        self.clip.notes.append(FakeNote(39, 0.0, C.STEP, 100))
        self.clip.notes.append(FakeNote(41, 0.0, C.STEP, 100))   # no sound
        self.clip._fire('notes')
        self.button(C.BTN_MOD, True)
        leds = self.leds()
        kinds = dict((k, c) for k, c, _, _ in C.DRUM_KINDS)
        self.assertEqual(leds[12], C.COLOR_PICK_SELECTED)   # 36, the lane
        self.assertEqual(leds[14], kinds['snare'])          # 38: no notes
        self.assertEqual(leds[15], kinds['snare'])          # 39: notes, same
        self.assertEqual(leds[8], C.COLOR_DRUM_OTHER)       # 40 'Zap'
        self.assertEqual(leds[9], kinds['tom'])             # 41: notes, GM
        self.assertNotEqual(leds[13], C.COLOR_PICK_LOADED)  # 37: no sound

    def test_holding_mod_flashes_each_drum_as_it_plays(self):
        self.named_kit({36: 'Kick', 38: 'Snare'})
        self.clip.notes.append(FakeNote(36, 0.0, C.STEP, 100))
        self.clip.notes.append(FakeNote(38, 4 * C.STEP, C.STEP, 100))
        self.clip._fire('notes')
        kinds = dict((k, c) for k, c, _, _ in C.DRUM_KINDS)
        self.button(C.BTN_MOD, True)
        self.clip.play(0.0)                     # step 1: the kick
        self.assertEqual(self.leds()[12], kinds['kick'])    # the white lane
        self.assertEqual(self.leds()[14], kinds['snare'])
        self.clip.play(4 * C.STEP)              # step 5: the snare
        self.assertEqual(self.leds()[12], C.COLOR_PICK_SELECTED)
        self.assertEqual(self.leds()[14], C.COLOR_PLAYHEAD_ON)
        self.clip.play(5 * C.STEP)              # step 6: nothing
        self.assertEqual(self.leds()[14], kinds['snare'])

    def test_the_flash_can_be_switched_off(self):
        original = SEQ_MODULE.PICKER_FLASH
        try:
            SEQ_MODULE.PICKER_FLASH = False
            self.clip.notes.append(FakeNote(36, 0.0, C.STEP, 100))
            self.clip._fire('notes')
            self.button(C.BTN_MOD, True)
            self.clip.play(0.0)
            self.assertEqual(self.leds()[12], C.COLOR_PICK_SELECTED)
        finally:
            SEQ_MODULE.PICKER_FLASH = original

    def test_overview_rows_light_in_their_drums_colours(self):
        # Bottom row is 36 (kick), then 37, 38 (snare), 39 (clap -> snare).
        self.clip.notes.append(FakeNote(36, 0.0, C.STEP, 100))
        self.clip.notes.append(FakeNote(38, 0.0, C.STEP, 100))
        self.clip._fire('notes')
        self.button(C.BTN_VIEW)
        self.assertEqual(self.leds()[12], self.colour('kick'))
        self.assertEqual(self.leds()[4], self.colour('snare'))



class FakeIntroSurface(FakeKeysSurface):
    def __init__(self):
        FakeKeysSurface.__init__(self, None)
        self.hold, self.refreshed = True, 0

    def refresh_state(self):
        self.refreshed += 1

    def run_ticks(self, ticks):
        for _ in range(ticks):
            self.run_pending()


class StartupIntro(unittest.TestCase):
    """MVave_SMC_PAD/StartupIntro.py: the rainbow and the PAD1 flash at load."""

    def setUp(self):
        _load_keys_mode()
        import importlib
        self.mod = importlib.import_module('pad_keys_pkg.StartupIntro')
        self.surface = FakeIntroSurface()
        self.intro = self.mod.StartupIntro(self.surface)
        self.pads = self.mod.grid_leds()
        # PAD1, bottom-left, sends note 13: the grid's first row is the top.
        self.pad1 = self.mod.PAD_LED_OFFSET + 13

    def lit(self):
        leds = {}
        for status, led, colour in self.surface.sent:
            leds[led] = colour
        return leds

    def test_the_grid_is_the_clip_grids_leds(self):
        self.assertEqual(sorted(led for led, _ in self.pads), list(range(33, 49)))
        self.assertEqual(dict(self.pads)[self.pad1], 0)         # PAD1 first
        self.assertEqual(dict(self.pads)[36], 6)                # top-right (note 4) last
        self.assertEqual(dict(self.pads)[33], 3)                # PAD13 (note 1) top-left

    def test_pad1_is_the_bottom_left_pad_in_preset_1(self):
        # Record 32 is PAD1, bank A (tools/make_presets.py BANK_A).
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data = open(os.path.join(root, 'presets',
                                 'preset1-launcher-mixer.spc'), 'rb').read()
        record = 211 + 32 * 26
        self.assertEqual(data[record + 8], self.pad1)           # its LED number

    def test_the_rainbow_starts_at_pad1_and_spreads_diagonally(self):
        first = self.mod.frame(0, self.pads)
        self.assertEqual(first[self.pad1], self.mod.INTRO_RAINBOW[0])
        self.assertEqual([led for led, c in first.items() if c], [self.pad1])
        later = self.mod.frame(6, self.pads)
        self.assertTrue(all(later.values()))                    # all 16 lit
        # Pads on one diagonal share a colour; the next one is a step behind.
        pad2, pad5, pad6 = 46, 41, 42                           # notes 14, 9, 10
        self.assertEqual(later[pad2], later[pad5])
        rainbow = list(self.mod.INTRO_RAINBOW)
        self.assertEqual((rainbow.index(later[pad2]) - rainbow.index(later[pad6])) % len(rainbow), 1)

    def test_pad1_steps_through_every_colour_in_order(self):
        rainbow = self.mod.INTRO_RAINBOW
        seen = [self.mod.frame(step, self.pads)[self.pad1]
                for step in range(self.mod.INTRO_RAINBOW_TICKS)]
        ticks = self.mod.INTRO_COLOUR_TICKS
        self.assertEqual(seen, [rainbow[(s // ticks) % len(rainbow)] for s in range(len(seen))])
        self.assertEqual(set(seen), set(rainbow))               # none skipped

    def test_the_rainbow_has_no_repeats(self):
        self.assertEqual(len(set(self.mod.INTRO_RAINBOW)), len(self.mod.INTRO_RAINBOW))

    def test_every_rainbow_colour_is_in_the_palette(self):
        for colour in self.mod.INTRO_RAINBOW:
            self.assertTrue(0 < colour < 64)

    def test_it_lasts_about_three_plus_two_seconds(self):
        self.assertEqual(self.mod.INTRO_RAINBOW_TICKS, 30)
        self.assertEqual(self.mod.INTRO_FLASH_TICKS, 20)

    def test_then_only_pad1_flashes(self):
        start = self.mod.INTRO_RAINBOW_TICKS
        on, off = self.mod.frame(start, self.pads), self.mod.frame(
            start + self.mod.INTRO_FLASH_STEP, self.pads)
        self.assertEqual({l: c for l, c in on.items() if c},
                         {self.pad1: self.mod.INTRO_FLASH_COLOUR})
        self.assertFalse(any(off.values()))

    def test_play_runs_to_the_end_then_hands_the_grid_back(self):
        self.intro.play()
        self.assertTrue(self.intro.playing)
        self.assertEqual(self.lit()[self.pad1], self.mod.INTRO_RAINBOW[0])
        self.surface.run_ticks(self.mod.INTRO_RAINBOW_TICKS + self.mod.INTRO_FLASH_TICKS - 1)
        self.assertTrue(self.intro.playing)
        self.assertEqual(self.surface.refreshed, 0)
        self.surface.run_ticks(1)
        self.assertFalse(self.intro.playing)
        self.assertEqual(self.surface.refreshed, 1)
        self.assertEqual(self.surface.pending, [])

    def test_only_changes_are_sent_between_ticks(self):
        self.intro.play()
        self.surface.run_ticks(self.mod.INTRO_RAINBOW_TICKS)  # first flash tick
        del self.surface.sent[:]
        self.surface.run_ticks(1)                               # PAD1 still on
        self.assertEqual(self.surface.sent, [])

    def test_it_plays_once(self):
        self.intro.play()
        self.surface.run_ticks(60)
        del self.surface.sent[:]
        self.intro.play()                                       # the fallback
        self.assertEqual(self.surface.sent, [])

    def test_another_layout_skips_it_and_the_fallback_too(self):
        self.intro.play(False)
        self.intro.play()
        self.assertEqual(self.surface.sent, [])
        self.assertFalse(self.intro.playing)

    def test_repaint_puts_the_frame_back_over_a_refresh(self):
        self.intro.play()
        self.surface.run_ticks(10)
        del self.surface.sent[:]
        self.intro.repaint()
        self.assertEqual(len(self.surface.sent), 16)

    def test_disconnect_stops_a_tick_still_scheduled(self):
        self.intro.play()
        self.intro.disconnect()
        del self.surface.sent[:]
        self.surface.run_ticks(60)
        self.assertEqual(self.surface.sent, [])
        self.assertEqual(self.surface.refreshed, 0)

    def test_disabled_never_plays(self):
        saved = self.mod.INTRO_ENABLED
        self.mod.INTRO_ENABLED = False
        try:
            intro = self.mod.StartupIntro(self.surface)
            intro.play()
            self.assertEqual(self.surface.sent, [])
        finally:
            self.mod.INTRO_ENABLED = saved


class KnobsStartTheIntro(unittest.TestCase):
    """The first status tells MVave_SMC_PAD whether the grid is showing."""

    S = PresetSwitchRepaint

    class Pad(object):
        def __init__(self):
            self.scheduled = []

        def play_intro(self, show=True):
            pass

        def refresh_state(self):
            pass

        def schedule_message(self, delay, callback, parameter=None):
            self.scheduled.append((callback, parameter))

    def setUp(self):
        self.knobs = KNOBS_MODULE.MVave_SMC_KNOBS(FakeCInstance())
        self.pad = self.Pad()
        self.knobs._instances = lambda name: [self.pad] if name == 'MVave_SMC_PAD' else []
        self.knobs._startup_pending = False

    def intros(self):
        # Bound with functools.partial and no parameter: Live's
        # schedule_message drops a falsy parameter, so False must not be one.
        return [c.args[0] for c, p in self.pad.scheduled
                if getattr(c, 'func', None) == self.pad.play_intro and p is None]

    def test_preset_1_bank_a_plays_it(self):
        self.knobs.receive_midi(self.S.LAUNCHER)
        self.assertEqual(self.intros(), [True])

    def test_another_layout_skips_it(self):
        for status in (self.S.MIXER, self.S.SEQUENCER, self.S.KEYS):
            self.setUp()
            self.knobs.receive_midi(status)
            self.assertEqual(self.intros(), [False])

    def test_only_the_first_status_counts(self):
        self.knobs.receive_midi(self.S.SEQUENCER)
        self.knobs.receive_midi(self.S.LAUNCHER)
        self.assertEqual(self.intros(), [False])

    def test_not_before_the_startup_write_has_landed(self):
        self.knobs._startup_pending = True
        self.knobs.sent = []
        self.knobs.receive_midi(self.S.KEYS)                    # writes preset 1
        self.assertEqual(self.intros(), [])
        self.knobs.receive_midi(self.S.LAUNCHER)
        self.assertEqual(self.intros(), [True])


if __name__ == '__main__':
    unittest.main(verbosity=2 if '-v' in sys.argv else 1)
