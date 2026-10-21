# Preset 4's other half: Live's Chord device on the tracks the pads play.
#
# A pad translation is one note to one note, so preset 4's pads play each
# chord's root and a Chord MIDI effect, counting in Live's scale, adds the
# rest. While preset 4 is up this switches on the Chord device of every track
# the pads reach, adding one where there is none; on any other preset it
# switches off the ones it switched on or added, so preset 3 plays single notes.
#
# Imports nothing from Live, so the self-test can load it like KeysLayout.
from .MIDI_Map import CHORDS_DEVICE, CHORDS_SHIFTS


class ChordDevices(object):

    def __init__(self, surface):
        self._surface = surface
        self._active = False
        self._switched_on = []  # Chord devices to switch off on leaving
        self.problem = None     # why a track may play no chords, for messages
        self._view = getattr(surface.song(), 'view', None)
        add = getattr(self._view, 'add_selected_track_listener', None)
        if add is not None:
            # Selecting a track arms it (Live's default), so the newly armed
            # track needs its Chord device too.
            add(self._on_selected_track)
        else:
            self._view = None

    def disconnect(self):
        if self._view is not None:
            try:
                self._view.remove_selected_track_listener(self._on_selected_track)
            except Exception:
                pass
            self._view = None

    def set_active(self, active):
        """Preset 4 up (True) or not."""
        active = bool(active)
        if active != self._active:
            self._active = active
            self.sync()

    def _on_selected_track(self):
        # A song listener must not change the song: deferred.
        self._surface.schedule_message(1, self._synced_for_new_track)

    def _synced_for_new_track(self, _=None):
        if self._active:
            self.sync()
            if self.problem:
                self._surface.show_message('SMC-PAD chords: ' + self.problem)

    def sync(self):
        self.problem = None
        if not self._active:
            for device in self._switched_on:
                try:
                    switch = _device_on(device)
                    if switch is not None:
                        switch.value = switch.min
                except Exception:
                    pass    # deleted since: nothing to switch off
            self._switched_on = []
            return
        if not CHORDS_DEVICE:
            return
        try:
            for track in self._playing_tracks():
                device = _chord_device(track)
                if device is None:
                    device = self._add(track)
                    if device is not None:
                        self._switched_on.append(device)
                    continue
                switch = _device_on(device)
                if switch is not None and switch.value == switch.min:
                    switch.value = switch.max
                    self._switched_on.append(device)
        except Exception:
            self._surface._log_exception('chords: Chord device')

    def _playing_tracks(self):
        # The tracks a pad reaches: MIDI tracks armed, or monitoring In (0).
        for track in getattr(self._surface.song(), 'tracks', ()):
            if not getattr(track, 'has_midi_input', False):
                continue
            armed = getattr(track, 'can_be_armed', False) and track.arm
            if armed or getattr(track, 'current_monitoring_state', 1) == 0:
                yield track

    def _add(self, track):
        insert = getattr(track, 'insert_device', None)
        if insert is None:
            # A Live without Track.insert_device: the user adds one.
            self.problem = "put Live's Chord device on the track to hear chords"
            return None
        try:
            insert(CHORDS_DEVICE, 0)    # in front of the instrument
        except Exception:
            self.problem = 'could not add a Chord device'
            self._surface._log_exception('chords: add Chord')
            return None
        device = _chord_device(track)
        if device is not None:
            self._set_up(device)
        return device

    def _set_up(self, device):
        # Count the shifts in Live's scale, then stack CHORDS_SHIFTS. Matched
        # on spelling because Live shows the names, not an API. Live 12.4's
        # Chord has two shifts per voice (Log.txt, 2026-10-20): ShiftN in
        # semitones, and ShiftN Scale Degrees, the one it plays while Use
        # Current Scale is on. Every parameter is logged, to check them.
        parameters = dict((parameter.name.replace(' ', '').lower(), parameter)
                          for parameter in device.parameters)
        scale = parameters.get('usecurrentscale')
        shifts = [parameters.get('shift%dscaledegrees' % (number + 1))
                  for number in range(len(CHORDS_SHIFTS))]
        if scale is None or None in shifts:
            # Steps of a scale mean nothing in semitones: leave it as it is.
            self.problem = 'this Chord has no Use Current Scale, so not in key'
        else:
            scale.value = scale.max
            for shift, steps in zip(shifts, CHORDS_SHIFTS):
                shift.value = max(shift.min, min(shift.max, steps))
        log = getattr(self._surface, 'log_message', None)
        if log is not None:
            log('SMC-PAD chords: added Chord, parameters %s' % ', '.join(
                '%s=%s' % (p.name, p.str_for_value(p.value)) for p in device.parameters))


def _chord_device(track):
    for device in track.devices:
        if getattr(device, 'class_name', '') == 'MidiChord':
            return device
    return None


def _device_on(device):
    for parameter in getattr(device, 'parameters', ()):
        if parameter.name == 'Device On':
            return parameter
    return None
