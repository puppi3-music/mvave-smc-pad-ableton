# Revision of these scripts, for bug reports: the install is "copy a
# folder", so a downloaded copy carries no commit and nothing else here
# names a version. Quote this line.
SCRIPT_REVISION = '2026-10-20b'

# Avoid using tabs for indentation, use spaces.
# Don't use floats, they might break things.


# Combination Mode offsets
# ------------------------

TRACK_OFFSET = -1  # offset from the left of linked session origin; set to -1 for auto-joining of multiple instances
SCENE_OFFSET = 0  # offset from the top of linked session origin (no auto-join)

# Buttons / Pads
# -------------
# Valid Note/CC assignments are 0 to 127, or -1 for NONE
# Duplicate assignments are permitted

BUTTONCHANNEL = 0  # Channel assignment for all mapped buttons/pads; valid range is 0 to 15 ; 0=1, 1=2 etc.
MESSAGETYPE = 0  # Message type for buttons/pads; set to 0 for MIDI Notes, 1 for CCs.
# When using CCs for buttons/pads, set BUTTONCHANNEL and SLIDERCHANNEL to different values.


# Track selection box (aka that coloured box for scene/track launching)
TSB_X = 4   # Controls the horizontal value for the track selection box. Default value is 8
TSB_Y = 4   # Controls the horizontal value for the track selection box. Default value is 8

# General
PLAY = 17   # Global play
STOP = 18   # Global stop
REC = 19    # Global record
TAPTEMPO = -1   # Tap tempo
NUDGEUP = -1    # Tempo Nudge Up
NUDGEDOWN = -1  # Tempo Nudge Down
UNDO = -1   # Undo
REDO = -1   # Redo
LOOP = -1   # Loop on/off
PUNCHIN = -1    # Punch in
PUNCHOUT = -1   # Punch out
OVERDUB = -1     # Overdub on/off
METRONOME = -1   # Metronome on/off
RECQUANT = -1   # Record quantization on/off
DETAILVIEW = -1   # Detail view switch
CLIPTRACKVIEW = -1  # Clip/Track view switch

# Modifier
# --------
# Currently DISABLED. The CC 17/18 encoders navigate both axes, so no modifier
# is needed and note 19 is free to be the record button.
#
# To re-enable it, four constants have to move together:
#     MODIFIER     = 19    (this line)
#     REC          = -1    so the transport component never claims note 19
#     SESSIONLEFT  = 20    _set_session_banking() reads the SESSION* constants,
#     SESSIONRIGHT = 21    not the TRACK* ones
#     TRACKLEFT/TRACKRIGHT = -1  so two components do not share one button
# Held down, the arrows then bank through scenes instead of across tracks.
MODIFIER = -1   # disabled: the CC 17/18 encoders navigate instead

# Device Control
DEVICELOCK = -1  # Device Lock (lock "blue hand")
DEVICEONOFF = -1  # Device on/off
DEVICENAVLEFT = -1  # Device nav left
DEVICENAVRIGHT = -1  # Device nav right
DEVICEBANKNAVLEFT = -1  # Device bank nav left
DEVICEBANKNAVRIGHT = -1  # Device bank nav right
DEVICEBANK = (-1,  # Bank 1 #All 8 banks must be assigned to positive values in order for bank selection to work
              -1,  # Bank 2
              -1,  # Bank 3
              -1,  # Bank 4
              -1,  # Bank 5
              -1,  # Bank 6
              -1,  # Bank 7
              -1,  # Bank 8
              )

# Arrangement View Controls
SEEKFWD = -1  # Seek forward
SEEKRWD = -1  # Seek rewind

# Session Navigation (aka "red box")
SESSIONLEFT = -1  # Session left  -- the CC 17 encoder banks tracks now
SESSIONRIGHT = -1  # Session right -- ditto, see MVave_SMC_KNOBS
SESSIONUP = -1  # Session up
SESSIONDOWN = -1  # Session down
ZOOMUP = -1  # Session Zoom up
ZOOMDOWN = -1  # Session Zoom down
ZOOMLEFT = -1  # Session Zoom left
ZOOMRIGHT = -1  # Session Zoom right

# Track Navigation
TRACKLEFT = 20  # Track left  -- selects the previous track
TRACKRIGHT = 21  # Track right -- selects the next track

# Scene Navigation
SCENEUP = -1  # Scene down
SCENEDN = -1  # Scene up

# Scene Launch
SELSCENELAUNCH = -1  # Selected scene launch
SCENELAUNCH = (-1,  # Scene 1 Launch
               -1,  # Scene 2
               -1,  # Scene 3
               -1,  # Scene 4
               -1,  # Scene 5
               -1,  # Scene 6
               -1,  # Scene 7
               -1,  # Scene 8
               )

# Clip Launch / Stop
SELCLIPLAUNCH = -1  # Selected clip launch
STOPALLCLIPS = -1  # Stop all clips

# 8x8 Matrix note assignments
# Track no.:     1   2   3   4   5   6   7   8
CLIPNOTEMAP = ((1, 2, 3, 4),  # Row 1
               (5, 6, 7, 8),  # Row 2
               (9, 10, 11, 12),  # Row 3
               (13, 14, 15, 16),  # Row 4
               )

# Pad LED colours
# ----------------
# The velocity of a note-on sent TO the SMC-PAD is a palette index, not a
# brightness. Measured 2026-08-02: the palette cycles hue roughly every 13-14
# steps, and everything above ~64 is the same flat blue, so all usable values
# are low. There is no saturated red -- 14 is as close as the palette gets.
#
#    5 green    14 red-pink    15 orange    21 bright blue
#   24 light purple    40 white    0 off
CLIP_PLAYING = 5           # clip is playing
CLIP_STOPPED = 15          # slot holds a clip, not playing
CLIP_RECORDING = 14        # clip is recording
CLIP_TRIGGERED_PLAY = 21   # queued, waiting for the quantise point
CLIP_TRIGGERED_REC = 24    # queued to record

# A pad pressed on an empty slot of a MIDI track makes an empty clip this many
# bars long, in the song's time signature, selected and open in the clip view --
# what double-clicking the slot does, armed or not. Audio tracks keep the old
# press: record if armed, else stop the track. 0 restores the old press on MIDI
# tracks too.
NEW_CLIP_BARS = 1

# Where the grid's LEDs are addressed, as an offset from each pad's note.
# Measured 2026-10-07: a pad whose editor LED number equals its own note shows
# white when sent velocity 0 -- it cannot be switched off. With the LED number
# moved off the note, velocity 0 is dark again. So the preset gives every grid
# pad LED number = note + PAD_LED_OFFSET (33-48), and the script lights that
# number instead of the note. 0 restores LED-on-the-note.
# 33-48 stays clear of the sequencer's 101-121, so neither preset lights the
# other's pads.
PAD_LED_OFFSET = 32

# Startup intro
# -------------
# When Live loads, the grid plays a show for ~3 s -- a waving trans flag, or a
# rainbow -- then PAD1 flashes for ~2 s to say preset 1 is loaded (Shift + PAD1
# is preset 1), then the clip colours come back. Ticks are Live's display
# ticks, about 100 ms each. StartupIntro.py has the details.
INTRO_ENABLED = True        # False skips it
INTRO_STYLE = 'flag'        # 'flag' or 'rainbow'
INTRO_SHOW_TICKS = 30       # ~3 s of flag or rainbow, before the flash
#
# The flag unfurls from the left column, a column a tick, then waves: a ripple
# runs left to right across the grid every INTRO_WAVE_TICKS, so the stripes
# rise and dip column by column. Its five stripes, bottom to top: light blue,
# pink, white, pink, light blue. Four rows can't show five stripes at once, so
# the white one shows where the wave lifts the middle rows onto it.
# 62 (sky blue), 56 (pink) and 40 (white) are from the palette survey
# (HARDWARE.md 3.2.1); pale pinks (28, 57) were passed over as they read as
# white on the pads. Approved on the pads on 2026-10-20 (played by a scratch
# script with Live closed).
INTRO_FLAG = (62, 56, 40, 56, 62)
INTRO_WAVE_TICKS = 10       # one ripple a second
#
# The rainbow runs diagonally across the grid from PAD1 to the top-right pad.
# The pads can't blend: each colour is a palette index (HARDWARE.md 3.2), so
# the rainbow is as smooth as its list is long. These 18 were picked on the
# device on 2026-10-20 from a survey of the whole palette (HARDWARE.md 3.2.1),
# by eye from photos, in hue order, round to red-pink again:
#   14 red-pink, 15 orange, 59 apricot, 46 yellow, 4 yellow-lime, 19 green,
#    5 mint, 6 cyan, 20 cyan-sky, 62 sky blue, 21 blue, 63 cornflower,
#    9 periwinkle, 24 lavender, 11 blue-violet, 26 violet, 12 orchid, 56 pink
# Pale entries were left out: in a moving rainbow they flash white. So were
# near-duplicates (7 looks like 20).
INTRO_RAINBOW = (14, 15, 59, 46, 4, 19, 5, 6, 20, 62, 21, 63, 9, 24, 11, 26, 12, 56)
# How many ticks each rainbow colour lasts on a pad; each diagonal is one
# colour behind the last. 1, the fastest that shows every colour, takes each pad round the
# 18 colours about 1.7 times in ~3 s. 2 is half the speed.
INTRO_COLOUR_TICKS = 1
INTRO_FLASH_TICKS = 20      # ~2 s
INTRO_FLASH_COLOUR = 40     # white
INTRO_FLASH_STEP = 2        # ticks on, then as many off: 5 flashes in 2 s
# Started by MVave_SMC_KNOBS once the controller shows preset 1; without that
# script, the intro starts on its own after this many ticks (~2 s).
INTRO_FALLBACK_TICKS = 20

# Mixer bank
# ----------
# PAD BANK flips the 16 pads to a second bank (presets/preset1-launcher-
# mixer.spc, built by tools/make_presets.py). Its pads send notes 49-64 and
# work on the four tracks in the session box, one column per track:
#
#   49 50 51 52   track on/off -- lit while the track is NOT muted
#   53 54 55 56   solo
#   57 58 59 60   arm
#   61 62 63 64   stop the track's clip -- lit while a clip plays there
#
# The notes live in TRACKMUTE/TRACKSOLO/TRACKREC/TRACKSTOP below. Their LEDs
# sit at note + MIXER_LED_OFFSET (85-100), clear of the clip grid (33-48)
# and the sequencer (69-84), for the same stuck-white reason as above.
MIXER_LED_OFFSET = 36
MIXER_TRACK_ON = 17         # yellow
MIXER_SOLO = 21             # bright blue
MIXER_ARM = 14              # red-pink
MIXER_STOP = 24             # light purple: a clip is playing, press to stop
MIXER_STOP_TRIGGERED = 40   # white: stop is queued for the quantise point

# Keyboard (preset 3)
# -------------------
# Preset 3's pads play notes in a scale, like a Launchpad's Note mode. Both of
# its pad banks are lit MCP pads on this port, built by tools/make_presets.py.
#
# Bank A plays. Its pads send KEYS_NOTES (PAD1 bottom-left first) and the script
# rewrites each one to the scale note that pad stands for, which Live passes to
# the armed track like a note from a keyboard (Live's note translation, the way
# Push plays notes). Lit pads always send velocity 127 (HARDWARE.md 5.6), so
# every note plays at full velocity.
#
# Bank B (PAD BANK) sets it up. Its pads send SETTINGS_NOTES, PAD1 bottom-left:
#
#   13 oct down   14 oct up   15 prev scale   16 next scale     <- top
#    9 G#         10 A        11 A#           12 B
#    5 E           6 F         7 F#            8 G
#    1 C           2 C#        3 D             4 D#             <- bottom
#
# Pads 1-12 pick the root note; pressing the root that is already selected
# switches the layout between in key (only scale notes, Launchpad's default)
# and chromatic (every semitone, notes outside the scale dark). The root and
# scale are Live's own (Live 12's Scale in the control bar), so changing them
# in Live moves the pads too.
#
# 85-100 and 22-37 are notes neither script on this port listens to or
# lights. Their LEDs, 1-16 and 49-64, are clear of the clip grid (33-48), the
# sequencer (69-84), the mixer (85-100) and the buttons (17-21, 117-121).
KEYS_NOTES = tuple(range(85, 101))
KEYS_LEDS = tuple(range(1, 17))
SETTINGS_NOTES = tuple(range(22, 38))
SETTINGS_LEDS = tuple(range(49, 65))
# The channel the keyboard's notes reach the track on (1 = MIDI channel 2).
# It must not be BUTTONCHANNEL: Live looks a translated note up in this
# script's own map, so on channel 1 a scale note of 55 pressed the mixer's
# solo button for track 3 instead of playing (measured 2026-10-17). Nothing
# on this port listens on MIDI channel 2.
KEYS_CHANNEL = 1
KEYS_ROOT_NOTE = 0          # C; used until Live's scale is read
KEYS_SCALE = 'Major'
KEYS_OCTAVE = 3             # bottom-left pad's octave in Live's naming (C3 = 60)
KEYS_OCTAVE_MIN = -1         # C-1 = MIDI 12
KEYS_OCTAVE_MAX = 8
KEYS_CHROMATIC = False      # start in the chromatic layout instead of in key
KEYS_FOLLOW_LIVE_SCALE = True   # read and write Live 12's song scale
KEYS_ROOT = 21              # bright blue: the root note, in every octave
KEYS_FIFTH = 24             # light purple: the fifth, for chord shapes; 40 to
                            # light it like any other scale note
KEYS_IN_SCALE = 40          # white: every other note of the scale
KEYS_OUT_OF_SCALE = 0       # chromatic layout: notes outside the scale
KEYS_SETTINGS_ROOT = 21     # bright blue: the selected root, in key
KEYS_SETTINGS_CHROMATIC = 8 # cold white-blue: the selected root, chromatic
KEYS_SETTINGS_WHITE = 40    # white: the other natural notes
KEYS_SETTINGS_BLACK = 24    # light purple: the other sharps
# Each octave pad lights in the colour of the octave it moves to, from a
# cold-to-hot ladder from KEYS_OCTAVE_MIN up: purple, blue, light blue,
# turquoise, yellow (octave 3, the default), orange, red-pink, pink, light
# pink, white. At octave 3, down is turquoise and up is orange. The
# palette has no ramp to compute (HARDWARE.md 3.2), so it is a list. Green is
# skipped: it is the scale pads' colour. Each pad goes dark at its end of the
# range. An octave past the end of the list takes the nearest end's colour.
KEYS_OCTAVE_COLOURS = (24, 21, 7, 6, 4, 15, 14, 12, 11, 13)
KEYS_SETTINGS_SCALE = 5     # green
# Stepping through the scales, the scale pad you pressed flickers white
# KEYS_SCALE_FLASH_TIMES times when it lands back on Major, the top of the
# list, so you can tell where the list starts without reading Live's status
# bar. Each white and each green between lasts KEYS_SCALE_FLASH_TICKS of
# Live's display ticks, about 100 ms each.
KEYS_SCALE_FLASH = 40       # white
KEYS_SCALE_FLASH_TIMES = 3
KEYS_SCALE_FLASH_TICKS = 1  # ~0.1 s, so three flickers take ~0.6 s

# Chords (preset 4)
# -----------------
# Preset 4 is preset 3 with chords: the same buttons and knobs, and the same
# KeysMode code, but each pad plays a whole chord of the key. Its pads go up
# the scale one note at a time with no repeats, so in C major:
#
#   Am   B°   C    Dm     <- top
#   Dm   Em   F    G
#   G    Am   B°   C
#   C    Dm   Em   F      <- bottom
#
# A translated pad can only become one note, so each pad plays its chord's
# root and Live's Chord MIDI effect on the track adds the rest, counting in
# steps of Live's scale (its Use Current Scale switch). That gives every pad
# the chord the key makes on it. While preset 4 is up, the script switches on
# the Chord device of each track the pads play (armed, or monitoring In), and
# adds one in front of the instrument where there is none (Track.insert_device,
# which Live 12.4 has; without it the status bar asks for one). On any other
# preset it switches off the ones it switched on, so preset 3 plays single
# notes again. MVave_SMC_KNOBS says which preset is up (set_preset).
#
# PAD BANK is preset 4's own key, scale and octave page, laid out like preset
# 3's. Key and scale are Live's, so the two presets always share them; the
# octave is each preset's own. Pressing the lit root changes nothing here:
# preset 4 has the one layout.
#
# Notes and LEDs are the last ones free on this port (preset 3's comment above
# lists the taken ones), so the settings page is in three runs.
CHORDS_NOTES = tuple(range(65, 81))
CHORDS_LEDS = tuple(range(101, 117))
CHORDS_SETTINGS_NOTES = tuple(range(38, 49)) + tuple(range(81, 85)) + (122,)
CHORDS_SETTINGS_LEDS = tuple(range(22, 33)) + tuple(range(65, 69)) + (123,)
CHORDS_PRESET = 3           # preset 4, counted from 0 as the controller does
CHORDS_OCTAVE = 3           # bottom-left chord's root octave, like KEYS_OCTAVE
KEYS_SETTINGS_CHORDS = 56   # pink: the selected root on preset 4's page
CHORDS_DEVICE = 'Chord'     # the device preset 4 adds; '' never adds or
                            # switches devices (bring your own)
# What a Chord device the script adds stacks on each root, in scale steps
# (Shift1 Scale Degrees, Shift2 Scale Degrees, ...: in scale mode Live plays
# these, not the semitone Shift1, Shift2): 2 and 4 are the third and fifth, a
# triad. (2, 4, 6)
# makes sevenths. A Chord device already on the track keeps its own shifts.
CHORDS_SHIFTS = (2, 4)

# Track Control
MASTERSEL = -1      # Master track select
SELTRACKREC = -1    # Arm Selected Track
SELTRACKSOLO = -1   # Solo Selected Track
SELTRACKMUTE = -1   # Mute Selected Track

TRACKSTOP = (61,  # Track 1 Clip Stop
             62,  # Track 2
             63,  # Track 3
             64,  # Track 4
             -1,  # Track 5
             -1,  # Track 6
             -1,  # Track 7
             -1,  # Track 8
             )

TRACKSEL = (-1,  # Track 1 Select
            -1,  # Track 2
            -1,  # Track 3
            -1,  # Track 4
            -1,  # Track 5
            -1,  # Track 6
            -1,  # Track 7
            -1,  # Track 8
            )

TRACKMUTE = (49,  # Track 1 On/Off
             50,  # Track 2
             51,  # Track 3
             52,  # Track 4
             -1,  # Track 5
             -1,  # Track 6
             -1,  # Track 7
             -1,  # Track 8
             )

TRACKSOLO = (53,  # Track 1 Solo
             54,  # Track 2
             55,  # Track 3
             56,  # Track 4
             -1,  # Track 5
             -1,  # Track 6
             -1,  # Track 7
             -1,  # Track 8
             )

TRACKREC = (57,  # Track 1 Record
            58,  # Track 2
            59,  # Track 3
            60,  # Track 4
            -1,  # Track 5
            -1,  # Track 6
            -1,  # Track 7
            -1,  # Track 8
            )


# Pad Translations for Drum Rack
PADCHANNEL = 0  # MIDI channel for Drum Rack notes
DRUM_PADS = (-1, -1, -1, -1,  # MIDI note numbers for 4 x 4 Drum Rack
             -1, -1, -1, -1,  # Mapping will be disabled if any notes are set to -1
             -1, -1, -1, -1,  # Notes will be "swallowed" if already mapped elsewhere
             -1, -1, -1, -1,
             )


# Sliders / Knobs
# ---------------
# Valid CC assignments are 0 to 127, or -1 for NONE
# Duplicate assignments will be ignored
SLIDERCHANNEL = 0  # Channel assignment for all mapped CCs; valid range is 0 to 15
TEMPO_TOP = 180.0  # Upper limit of tempo control in BPM (max is 999)
TEMPO_BOTTOM = 100.0  # Lower limit of tempo control in BPM (min is 0)

TEMPOCONTROL = -1  # Tempo control CC assignment; control range is set above
MASTERVOLUME = -1  # Master track volume
CUELEVEL = -1  # Cue level control
CROSSFADER = -1  # Crossfader control

TRACKVOL = (-1,  # Track 1 Volume
            -1,  # Track 2
            -1,  # Track 3
            -1,  # Track 4
            -1,  # Track 5
            -1,  # Track 6
            -1,  # Track 7
            -1,  # Track 8
            )

TRACKPAN = (-1,  # Track 1 Pan
            -1,  # Track 2
            -1,  # Track 3
            -1,  # Track 4
            -1,  # Track 5
            -1,  # Track 6
            -1,  # Track 7
            -1,  # Track 8
            )

TRACKSENDA = (-1,  # Track 1 Send A
              -1,  # Track 2
              -1,  # Track 3
              -1,  # Track 4
              -1,  # Track 5
              -1,  # Track 6
              -1,  # Track 7
              -1,  # Track 8
              )

TRACKSENDB = (-1,  # Track 1 Send B
              -1,  # Track 2
              -1,  # Track 3
              -1,  # Track 4
              -1,  # Track 5
              -1,  # Track 6
              -1,  # Track 7
              -1,  # Track 8
              )

TRACKSENDC = (-1,  # Track 1 Send C
              -1,  # Track 2
              -1,  # Track 3
              -1,  # Track 4
              -1,  # Track 5
              -1,  # Track 6
              -1,  # Track 7
              -1,  # Track 8
              )

PARAMCONTROL = (1,  # Param 1 #All 8 params must be assigned to positive values in order for param control to work
                2,  # Param 2
                3,  # Param 3
                4,  # Param 4
                5,  # Param 5
                6,  # Param 6
                7,  # Param 7
                8,  # Param 8
                )


