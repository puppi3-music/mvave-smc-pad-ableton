# emacs-mode: -*- python-*-
# -*- coding: utf-8 -*-

import Live
from _Framework.SessionComponent import SessionComponent
from _Framework.SceneComponent import SceneComponent
from _Framework.ClipSlotComponent import ClipSlotComponent
from _Framework.ButtonElement import ButtonElement
from .MIDI_Map import NEW_CLIP_BARS


class NewClipSlotComponent(ClipSlotComponent):
    " A slot whose pad, on an empty slot of a MIDI track, makes an empty clip "

    def __init__(self, *a, **k):
        ClipSlotComponent.__init__(self, *a, **k)
        self._release_swallowed = False

    def _do_launch_clip(self, value):
        # The press makes the clip, so its release must not reach it: the
        # framework would hand the release to the new clip's fire button.
        if not value and self._release_swallowed:
            self._release_swallowed = False
            return
        if value and self._create_clip():
            self._release_swallowed = True
            return
        ClipSlotComponent._do_launch_clip(self, value)

    def _create_clip(self):
        # Mirrors a double-click on the slot: an empty clip, selected, with
        # the clip view open, armed or not -- so no open-ended recording that
        # keeps growing under the step sequencer. Audio tracks are left to the
        # framework (record if armed, else stop). Any failure falls back to
        # the framework's own press rather than eating the pad.
        slot = self._clip_slot
        if NEW_CLIP_BARS <= 0 or slot is None or slot.has_clip:
            return False
        try:
            track = slot.canonical_parent
            if not track.has_midi_input:
                return False
            song = self.song()
            beats_per_bar = song.signature_numerator * 4.0 / song.signature_denominator
            slot.create_clip(NEW_CLIP_BARS * beats_per_bar)
            song.view.highlighted_clip_slot = slot
            self.application().view.show_view('Detail/Clip')
        except Exception:
            return slot.has_clip
        return True


class NewClipSceneComponent(SceneComponent):
    clip_slot_component_type = NewClipSlotComponent


class SpecialSessionComponent(SessionComponent):
    " Special SessionComponent for APC combination mode and button to fire selected clip slot "
    __module__ = __name__
    scene_component_type = NewClipSceneComponent

    def __init__(self, num_tracks, num_scenes):
        SessionComponent.__init__(self, num_tracks, num_scenes)
        self._slot_launch_button = None

    def disconnect(self):
        SessionComponent.disconnect(self)
        if (self._slot_launch_button != None):
            self._slot_launch_button.remove_value_listener(self._slot_launch_value)
            self._slot_launch_button = None

    def link_with_track_offset(self, track_offset, scene_offset):
        assert (track_offset >= 0)
        assert (scene_offset >= 0)
        if self._is_linked():
            self._unlink()
        self.set_offsets(track_offset, scene_offset)
        self._link()

    def unlink(self):
        if self._is_linked():
            self._unlink()

    def set_slot_launch_button(self, button):
        assert ((button == None) or isinstance(button, ButtonElement))
        if (self._slot_launch_button != button):
            if (self._slot_launch_button != None):
                self._slot_launch_button.remove_value_listener(self._slot_launch_value)
            self._slot_launch_button = button
            if (self._slot_launch_button != None):
                self._slot_launch_button.add_value_listener(self._slot_launch_value)

            self.update()

    def _slot_launch_value(self, value):
        assert (value in range(128))
        assert (self._slot_launch_button != None)
        if self.is_enabled():
            if ((value != 0) or (not self._slot_launch_button.is_momentary())):
                if (self.song().view.highlighted_clip_slot != None):
                    self.song().view.highlighted_clip_slot.fire()



# local variables:
# tab-width: 4
