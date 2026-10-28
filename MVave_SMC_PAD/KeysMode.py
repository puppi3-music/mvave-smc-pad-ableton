# SPDX-FileCopyrightText: 2026 puppi3-music
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Preset 3's keyboard: Launchpad-style Note mode on the SMC-PAD's lit pads.
# Preset 4's chords are a second instance (chords=True) on their own notes and
# LEDs, playing each chord's root for ChordDevices' Chord device to fill out.
#
# Bank A's pads are translated, not handled: each pad's note is rewritten to a
# scale note on the way in (InputControlElement.set_identifier + a midi map
# rebuild, the mechanism Push uses for its pads), so Live hands the note to the
# armed track and the script never sees it. Bank B's pads are ordinary buttons
# that change root, scale, octave and layout and then re-translate bank A.
#
# Both banks are lit all the time, whatever preset is showing: their LED
# numbers (MIDI_Map.py) belong to no other layout, so painting them while
# another preset is up changes nothing you can see.
from .KeysLayout import (SCALES, NOTE_NAMES, BLACK_KEYS, pad_note, chord_note,
                         degree, note_name, scale_index)
from .MIDI_Map import *

OCTAVE_DOWN, OCTAVE_UP, SCALE_PREV, SCALE_NEXT = 12, 13, 14, 15


class KeysMode(object):

    def __init__(self, surface, note_map, chords=False):
        self._surface = surface
        self._chords = chords
        if chords:
            notes, settings = CHORDS_NOTES, CHORDS_SETTINGS_NOTES
            self._key_leds, self._settings_leds = CHORDS_LEDS, CHORDS_SETTINGS_LEDS
        else:
            notes, settings = KEYS_NOTES, SETTINGS_NOTES
            self._key_leds, self._settings_leds = KEYS_LEDS, SETTINGS_LEDS
        self._keys = [note_map[note] for note in notes]
        self._settings = [note_map[note] for note in settings]
        self._listeners = []
        self._song_listeners = []
        self._leds = {}
        self._root = KEYS_ROOT_NOTE
        self._octave = CHORDS_OCTAVE if chords else KEYS_OCTAVE
        self._chromatic = KEYS_CHROMATIC and not chords
        self._flash = None      # the scale pad flickering, if any
        self._flash_phase = 0   # even: white, odd: green
        self._flash_count = 0   # which flicker a scheduled tick belongs to
        index = scale_index(KEYS_SCALE, ())
        self._scale_name, self._intervals = SCALES[max(index, 0)]
        self._read_live_scale(root=True, scale=True)
        for index, button in enumerate(self._settings):
            if button is not None:
                listener = self._make_settings_listener(index)
                button.add_value_listener(listener)
                self._listeners.append((button, listener))
        for button in self._keys:
            if button is not None:
                # No value listener reaches the script: the note belongs to
                # the track.
                button.suppress_script_forwarding = True
        self._watch_live_scale()
        self._translate()

    def disconnect(self):
        self._flash_count += 1  # a flicker still running stops without painting
        for button, listener in self._listeners:
            button.remove_value_listener(listener)
        self._listeners = []
        song = self._song()
        for name, listener in self._song_listeners:
            try:
                getattr(song, 'remove_%s_listener' % name)(listener)
            except Exception:
                pass
        self._song_listeners = []

    # ------------------------------------------------------------- live scale

    def _song(self):
        return self._surface.song()

    def _watch_live_scale(self):
        if not KEYS_FOLLOW_LIVE_SCALE:
            return
        song = self._song()
        for name, listener in (('root_note', self._on_live_root),
                               ('scale_name', self._on_live_scale)):
            add = getattr(song, 'add_%s_listener' % name, None)
            if add is not None:
                add(listener)
                self._song_listeners.append((name, listener))

    def _read_live_scale(self, root=False, scale=False):
        # Live before 12 has no song scale; the defaults above stand in.
        if not KEYS_FOLLOW_LIVE_SCALE:
            return False
        song = self._song()
        changed = False
        if root and hasattr(song, 'root_note'):
            value = int(song.root_note) % 12
            changed = changed or value != self._root
            self._root = value
        if scale and hasattr(song, 'scale_intervals'):
            intervals = tuple(int(i) for i in song.scale_intervals)
            if intervals:
                changed = changed or intervals != tuple(self._intervals)
                self._intervals = intervals
                self._scale_name = str(getattr(song, 'scale_name', '') or 'Scale')
        return changed

    # Song listeners only read and schedule: a listener must not change the
    # song, and the midi map rebuild is deferred out of the notification.
    def _on_live_root(self):
        self._surface.schedule_message(1, self._adopt_live, (True, False))

    def _on_live_scale(self):
        self._surface.schedule_message(1, self._adopt_live, (False, True))

    def _adopt_live(self, which):
        try:
            if self._read_live_scale(root=which[0], scale=which[1]):
                self._translate()
        except Exception:
            self._surface._log_exception('keys: follow Live scale')

    def _write_live(self, root=None, scale_name=None):
        if not KEYS_FOLLOW_LIVE_SCALE:
            return
        song = self._song()
        try:
            if root is not None and hasattr(song, 'root_note'):
                song.root_note = root
            if scale_name is not None and hasattr(song, 'scale_name'):
                song.scale_name = scale_name
        except Exception:
            # A scale name this Live does not know: the pads still use it.
            self._surface._log_exception('keys: set Live scale')

    # --------------------------------------------------------------- settings

    def _make_settings_listener(self, index):
        def listener(value):
            if value:
                try:
                    self._settings_pressed(index)
                except Exception:
                    self._surface._log_exception('keys settings')
        return listener

    def _settings_pressed(self, index):
        if index < 12 and index == self._root:
            # The lit root again: switch between in key and chromatic. The
            # chords have the one layout.
            self._chromatic = not self._chromatic and not self._chords
        elif index < 12:
            self._root = index
            self._write_live(root=index)
        elif index in (OCTAVE_DOWN, OCTAVE_UP):
            delta = -1 if index == OCTAVE_DOWN else 1
            self._octave = max(KEYS_OCTAVE_MIN, min(KEYS_OCTAVE_MAX, self._octave + delta))
        else:
            current = scale_index(self._scale_name, self._intervals)
            if current < 0:
                current = -1 if index == SCALE_NEXT else 0
            current = (current + (1 if index == SCALE_NEXT else -1)) % len(SCALES)
            self._scale_name, self._intervals = SCALES[current]
            self._write_live(scale_name=self._scale_name)
            if current == 0:
                self._start_flash(index)
            else:
                self._flash = None
        self._translate()
        self._surface.show_message(self.describe())

    def _start_flash(self, index):
        # Back round to Major: the pad just pressed flickers white
        # KEYS_SCALE_FLASH_TIMES times. The _translate after this paints the
        # first white; _flash_tick alternates green and white from there.
        self._flash = index
        self._flash_phase = 0
        self._flash_count += 1
        self._surface.schedule_message(KEYS_SCALE_FLASH_TICKS, self._flash_tick,
                                       self._flash_count)

    def _flash_tick(self, count):
        if count != self._flash_count:
            return  # a later press or a disconnect owns the pad now
        try:
            self._flash_phase += 1
            if self._flash_phase >= 2 * KEYS_SCALE_FLASH_TIMES - 1:
                self._flash = None
            else:
                self._surface.schedule_message(KEYS_SCALE_FLASH_TICKS, self._flash_tick, count)
            self.repaint(force=False)
        except Exception:
            self._surface._log_exception('keys: flash')

    def _note(self, index):
        if self._chords:
            return chord_note(index, self._root, self._octave, self._intervals)
        return pad_note(index, self._root, self._octave, self._intervals, self._chromatic)

    def describe(self):
        low, high = self._note(0), self._note(15)
        span = ''
        if low is not None and high is not None:
            span = ', %s to %s' % (note_name(low), note_name(high))
        if self._chords:
            return 'SMC-PAD chords: %s %s%s' % (NOTE_NAMES[self._root], self._scale_name, span)
        layout = 'chromatic' if self._chromatic else 'in key'
        return 'SMC-PAD keys: %s %s, %s%s' % (NOTE_NAMES[self._root], self._scale_name,
                                              layout, span)

    # ------------------------------------------------------------ translation

    def _translate(self):
        for index, button in enumerate(self._keys):
            if button is None:
                continue
            note = self._note(index)
            if note is None:
                # Off the end of the MIDI range: left untranslated, and with
                # forwarding suppressed the press goes nowhere.
                button.use_default_message()
                continue
            # Always onto KEYS_CHANNEL, never this script's own channel: a
            # translated note is looked up in this script's map, so on
            # BUTTONCHANNEL it would press whichever button owns that note.
            button.set_identifier(note)
            button.set_channel(KEYS_CHANNEL)
        self._surface.request_rebuild_midi_map()
        self._push_to_knobs()
        self.repaint(force=False)

    def targets(self):
        """The note each pad plays (preset 4: each chord's root), PAD1 first;
        None off the range."""
        return [self._note(index) for index in range(16)]

    def _push_to_knobs(self):
        # Note repeat bypasses this port: the firmware sends it as plain notes
        # on ports 1 and 2, where MVave_SMC_KNOBS translates it with this
        # table. Optional -- without the knobs script, repeats just do nothing.
        try:
            module = __import__('MVave_SMC_KNOBS.MVave_SMC_KNOBS', fromlist=['MVave_SMC_KNOBS'])
            instances = list(getattr(module.MVave_SMC_KNOBS, '_active_instances', None) or [])
        except Exception:
            return
        targets = self.targets()
        name = 'chords_changed' if self._chords else 'keys_changed'
        for knobs in instances:
            try:
                getattr(knobs, name)(targets)
            except Exception:
                self._surface._log_exception('keys: tell the knobs script')

    # ------------------------------------------------------------------- LEDs

    def _key_colour(self, index):
        note = self._note(index)
        if note is None:
            return 0
        return {'root': KEYS_ROOT, 'fifth': KEYS_FIFTH, 'scale': KEYS_IN_SCALE,
                None: KEYS_OUT_OF_SCALE}[degree(note, self._root, self._intervals)]

    def _settings_colour(self, index):
        if index < 12:
            if index == self._root:
                # Its colour shows the layout pressing it again leaves.
                if self._chords:
                    return KEYS_SETTINGS_CHORDS
                return KEYS_SETTINGS_CHROMATIC if self._chromatic else KEYS_SETTINGS_ROOT
            return KEYS_SETTINGS_BLACK if index in BLACK_KEYS else KEYS_SETTINGS_WHITE
        # Each octave pad shows the octave it moves to.
        if index == OCTAVE_DOWN:
            return self._octave_colour(self._octave - 1) if self._octave > KEYS_OCTAVE_MIN else 0
        if index == OCTAVE_UP:
            return self._octave_colour(self._octave + 1) if self._octave < KEYS_OCTAVE_MAX else 0
        if index == self._flash and self._flash_phase % 2 == 0:
            return KEYS_SCALE_FLASH
        return KEYS_SETTINGS_SCALE

    def _octave_colour(self, octave):
        step = octave - KEYS_OCTAVE_MIN
        return KEYS_OCTAVE_COLOURS[max(0, min(len(KEYS_OCTAVE_COLOURS) - 1, step))]

    def repaint(self, force=True):
        if force:
            self._leds = {}
        for index in range(16):
            for leds, colour in ((self._key_leds, self._key_colour(index)),
                                 (self._settings_leds, self._settings_colour(index))):
                led = leds[index]
                if self._leds.get(led) != colour:
                    self._leds[led] = colour
                    self._surface._send_midi((0x90 | BUTTONCHANNEL, led, colour))
