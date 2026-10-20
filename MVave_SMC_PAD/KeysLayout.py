# Preset 3's keyboard: which note each pad plays, Launchpad-style.
#
# Pure functions with no imports, like DeviceNav, so the self-test can load
# this file by path without a fake _Framework.

# (name, semitones above the root). The names are Live 12's own, so choosing
# one on the controller can set Live's scale too. Playing every semitone is a
# layout (pad_note's chromatic flag), not a scale, so it works with any of them.
SCALES = (
    ('Major', (0, 2, 4, 5, 7, 9, 11)),
    ('Minor', (0, 2, 3, 5, 7, 8, 10)),
    ('Dorian', (0, 2, 3, 5, 7, 9, 10)),
    ('Mixolydian', (0, 2, 4, 5, 7, 9, 10)),
    ('Lydian', (0, 2, 4, 6, 7, 9, 11)),
    ('Phrygian', (0, 1, 3, 5, 7, 8, 10)),
    ('Locrian', (0, 1, 3, 5, 6, 8, 10)),
    ('Harmonic Minor', (0, 2, 3, 5, 7, 8, 11)),
    ('Melodic Minor', (0, 2, 3, 5, 7, 9, 11)),
    ('Major Pentatonic', (0, 2, 4, 7, 9)),
    ('Minor Pentatonic', (0, 3, 5, 7, 10)),
    ('Minor Blues', (0, 3, 5, 6, 7, 10)),
)

NOTE_NAMES = ('C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B')
BLACK_KEYS = (1, 3, 6, 8, 10)

# Each row starts this many scale notes above the row below. 3 is Launchpad's
# "in key" layout: on a 7-note scale every row is a fourth up, and the last
# pad of a row repeats the first pad of the next. The chromatic layout, and a
# 12-note scale in key, use 4 semitones: one unbroken run of 16, each note once.
# (A Launchpad's chromatic rows are a fourth apart, but on 4 columns that
# skips a semitone every row.)
ROW_STEP = 3
CHROMATIC_ROW_STEP = 4


def bottom_note(root, octave):
    """The bottom-left pad's MIDI note. Live calls MIDI 60 C3, so octave 3
    with root C is 60."""
    return 12 * (octave + 2) + root


def pad_note(index, root, octave, intervals, chromatic=False):
    """MIDI note for pad index 0-15 (0 = bottom-left, reading left to right
    then upward), or None when it falls outside 0-127. In key, every pad is a
    note of the scale; chromatic, the pads are 16 semitones up from the root."""
    row, col = divmod(index, 4)
    if chromatic:
        intervals = tuple(range(12))
    count = len(intervals)
    step = CHROMATIC_ROW_STEP if count >= 12 else ROW_STEP
    position = row * step + col
    note = bottom_note(root, octave) + 12 * (position // count) + intervals[position % count]
    return note if 0 <= note <= 127 else None


def degree(note, root, intervals):
    """'root', 'fifth' or 'scale' for a note of the scale, None for one
    outside it. The fifth is 7 semitones up, so a scale without a perfect
    fifth (Locrian) has none."""
    offset = (note - root) % 12
    if offset == 0:
        return 'root'
    if offset not in intervals:
        return None
    return 'fifth' if offset == 7 else 'scale'


def note_name(note):
    """Live's spelling: 60 -> 'C3'."""
    return '%s%d' % (NOTE_NAMES[note % 12], note // 12 - 2)


def scale_index(name, intervals):
    """Position of a scale in SCALES, by name first and then by shape, or -1
    for a scale of Live's that is not in the list."""
    for i, (scale_name, scale_intervals) in enumerate(SCALES):
        if scale_name == name:
            return i
    for i, (scale_name, scale_intervals) in enumerate(SCALES):
        if tuple(scale_intervals) == tuple(intervals):
            return i
    return -1
