# SPDX-FileCopyrightText: 2026 puppi3-music
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# The light show when Live loads: for INTRO_SHOW_TICKS the clip grid shows
# INTRO_STYLE -- a trans flag that unfurls from the left column and waves, or
# a rainbow that runs diagonally from PAD1 (bottom-left) to the top-right
# corner -- then PAD1 alone flashes for INTRO_FLASH_TICKS -- PAD1 is the pad
# that selects preset 1 with Shift, so it says "preset 1 is loaded". Then the
# grid goes back to the clip colours.
#
# MVave_SMC_KNOBS starts it once the controller's first status shows preset 1,
# bank A, after its own startup write has landed: the grid's LEDs (33-48) show
# only while that layout is up, so started any earlier the show would play to
# the wrong preset. play(False) -- the controller is on another layout -- skips
# it. Without the knobs script nothing calls it, so the surface starts it after
# INTRO_FALLBACK_TICKS anyway.
#
# The SHIFT key is not lit: it has no record and no LED number in the preset,
# and sends nothing (HARDWARE.md 6.1), so there is nothing to address.
import math

from .MIDI_Map import *

WAITING, PLAYING, DONE = 0, 1, 2

# How far the wave lifts or drops a column, as a share of the flag's height:
# an eighth is half a row, enough to bring the white stripe onto the middle
# rows without losing the blue ones at the edges.
WAVE_HEIGHT = 0.12


def grid_leds():
    """(LED, row, column) per clip-grid pad, row 0 the bottom and column 0 the
    left. CLIPNOTEMAP's first row is the TOP one, like Live's scenes: PAD1,
    bottom-left, sends note 13 (preset 1, record 32; seen 2026-10-20 when the
    flash landed on PAD13). So rows are counted from the last."""
    pads = []
    bottom = len(CLIPNOTEMAP) - 1
    for row, notes in enumerate(CLIPNOTEMAP):
        for col, note in enumerate(notes):
            if note >= 0:
                pads.append((note + PAD_LED_OFFSET, bottom - row, col))
    return pads


def rainbow_colour(step, row, col):
    """The pads light one diagonal per tick outwards from PAD1, then the
    colours flow the same way, each pad each colour lasting
    INTRO_COLOUR_TICKS."""
    diagonal = row + col
    if diagonal > step:
        return 0
    phase = step // max(1, INTRO_COLOUR_TICKS)
    return INTRO_RAINBOW[(phase - diagonal) % len(INTRO_RAINBOW)]


def flag_colour(step, row, col):
    """The flag unfurls a column per tick from the left. Each pad shows the
    stripe at its row's height, lifted or dropped by a sine wave that runs
    left to right, one ripple every INTRO_WAVE_TICKS and one wavelength
    across the grid."""
    if col > step:
        return 0
    rows, cols = len(CLIPNOTEMAP), len(CLIPNOTEMAP[0])
    wave = WAVE_HEIGHT * math.sin(2 * math.pi * (
        step / float(max(1, INTRO_WAVE_TICKS)) - col / float(cols)))
    height = (row + 0.5) / rows + wave
    stripes = len(INTRO_FLAG)
    return INTRO_FLAG[min(stripes - 1, max(0, int(height * stripes)))]


def frame(step, pads):
    """LED -> colour for one tick of the show."""
    leds = {}
    if step < INTRO_SHOW_TICKS:
        colour = flag_colour if INTRO_STYLE == 'flag' else rainbow_colour
        for led, row, col in pads:
            leds[led] = colour(step, row, col)
    else:
        lit = ((step - INTRO_SHOW_TICKS) // INTRO_FLASH_STEP) % 2 == 0
        for led, row, col in pads:
            first = row == 0 and col == 0
            leds[led] = INTRO_FLASH_COLOUR if first and lit else 0
    return leds


class StartupIntro(object):

    def __init__(self, surface):
        self._surface = surface
        self._pads = grid_leds()
        self._state = WAITING if INTRO_ENABLED and self._pads else DONE
        self._step = 0
        self._count = 0         # which show a scheduled tick belongs to
        self._leds = {}

    def disconnect(self):
        self._count += 1        # a tick still scheduled paints nothing
        self._state = DONE

    @property
    def playing(self):
        return self._state == PLAYING

    def play(self, show=True):
        """Start the show, once. Later calls, and the fallback after a call
        from the knobs script, do nothing."""
        if self._state != WAITING:
            return
        if not show:
            self._state = DONE
            return
        self._state = PLAYING
        self._step = 0
        self._count += 1
        self.repaint()
        self._surface.schedule_message(1, self._tick, self._count)

    def _tick(self, count):
        if count != self._count or self._state != PLAYING:
            return
        try:
            self._step += 1
            if self._step >= INTRO_SHOW_TICKS + INTRO_FLASH_TICKS:
                self._state = DONE
                # Back to the clip colours. refresh_state clears the send
                # cache, so the framework resends every pad.
                self._surface.refresh_state()
                return
            self._surface.schedule_message(1, self._tick, count)
            self.repaint(force=False)
        except Exception:
            self._state = DONE
            self._surface._log_exception('startup intro')

    def repaint(self, force=True):
        # Also called from the surface's refresh_state, which repaints the
        # clip colours under the show: force resends the whole frame.
        if self._state != PLAYING:
            return
        if force:
            self._leds = {}
        for led, colour in sorted(frame(self._step, self._pads).items()):
            if self._leds.get(led) != colour:
                self._leds[led] = colour
                self._surface._send_midi((0x90 | BUTTONCHANNEL, led, colour))
