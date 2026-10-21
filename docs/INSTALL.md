# Installing the M-Vave SMC-PAD Remote Scripts

Three Remote Scripts, one per job:

| Script | Runs |
|---|---|
| `MVave_SMC_PAD` | Presets 1, 3 and 4: the clip launcher, its mixer, the scale keyboard and the chords. Pads, buttons and pad lights |
| `MVave_SMC_STEPSEQ` | Preset 2: the step sequencer. Pads, buttons and pad lights |
| `MVave_SMC_KNOBS` | The knobs on every preset. It also tells the other two to repaint when you switch preset (and `MVave_SMC_PAD` which preset is up, for preset 4's Chord devices), puts the controller on preset 1 when Live loads, and passes preset 2's drum pads and note repeat to your tracks |

They are separate because a Remote Script gets exactly one MIDI input port,
and the controller sends its lit pads and its encoders on different ports.
`MVave_SMC_KNOBS` also reaches into `MVave_SMC_PAD` to move the session box, so
**install both of those**. `MVave_SMC_STEPSEQ` is needed only for preset 2.

Once it's installed, the user guide ([online](https://puppi3-music.github.io/mvave-smc-pad-ableton/smc-pad-guide.html), or
[smc-pad-guide.html](smc-pad-guide.html) in a download) shows how to use it.

---

## Contents

- [Before you start](#before-you-start)
- [1. Load the presets onto the controller](#1-load-the-presets-onto-the-controller)
- [2. Copy the scripts into Live](#2-copy-the-scripts-into-live)
- [3. Restart Live](#3-restart-live)
- [4. Fill the Control Surface slots](#4-fill-the-control-surface-slots)
- [5. Set up the remaining port](#5-set-up-the-remaining-port)
- [Checking it worked](#checking-it-worked)
- [Troubleshooting](#troubleshooting)
- [Customising](#customising)
- [Uninstalling](#uninstalling)

---

## Before you start

| | |
|---|---|
| Ableton Live | Live 11 or 12. In daily use on **Live 12.3 and 12.4 (macOS)**, preset 4 verified on 12.4.6; first verified on Live 11.3.43 (Windows), see DEVELOPMENT.md §"Verified on hardware". The step sequencer needs Live 11+ (`get_notes_extended`). The keyboard follows Live 12's Scale setting, and preset 3's knobs use Live 12's parameter banks. Preset 4 needs Live 12's Chord device with Use Current Scale, and adds it to the track itself on Live 12.4 (`Track.insert_device`). |
| Hardware | M-Vave SMC-PAD, connected by USB. |
| Editor | **MidiSuite**, M-Vave's editor, from [m-vave.com/appdownload](https://www.m-vave.com/appdownload) (Windows, macOS, iOS, Android). It is the only way to write presets to the controller. |
| OS | Windows or macOS. |
| Python | None. Live runs the scripts with its own interpreter. Only the optional probe tool needs Python (see [Finding out what your unit sends](#finding-out-what-your-unit-sends)). |

> **MidiSuite, not CubeSuite.** M-Vave ships a second editor called CubeSuite
> for other products (LooperPro, SMK25, VMK25…), and the SMC-PAD is not in its
> device list.

Nothing here ships, mirrors or depends on MidiSuite, and none of it has been
tested against a particular version of it.

---

## 1. Load the presets onto the controller

The scripts expect the note, CC and LED numbers these four files set up. **A
factory-configured unit sends different numbers, and the scripts will appear
to do nothing.**

In MidiSuite, import each file from `presets/` and write it to its
preset slot:

| File | Slot | Gives you |
|---|---|---|
| `preset1-launcher-mixer.spc` | Preset 1 | Clip launcher; PAD BANK → mixer |
| `preset2-sequencer-drums.spc` | Preset 2 | Step sequencer; PAD BANK → drum pads |
| `preset3-keys.spc` | Preset 3 | Scale keyboard and device knobs; PAD BANK → key and scale |
| `preset4-chords.spc` | Preset 4 | Chords and device knobs; PAD BANK → key and scale |

On the controller, **Shift + pad 1, 2, 3 or 4** (bottom row, from the left) loads
that preset. **PAD BANK** is a different thing: it flips between the two pad
layouts *within* a preset. The five buttons belong to the preset, not to the
pad layout, so they keep the same job when you press PAD BANK.

Load only from `presets/`. The files in `reference/` are the sources
`tools/make_presets.py` builds these from and the original editor exports.

**Check it took** before going near Live, if you have the probe set up: run
`--listen` (see [Finding out what your unit sends](#finding-out-what-your-unit-sends))
and press the pads. Preset 1 sends notes 1–16, preset 2 notes 101–116, preset 3
notes 85–100, preset 4 notes 65–80. A factory unit sends none of these.

### What the scripts expect the controller to send

All on MIDI channel 1, unless noted. The **LED** column is the number the host
sends to light that pad, which these presets set apart from the pad's own note.
A pad whose LED number equals its note shows white when it should be off
([HARDWARE.md](HARDWARE.md) §5.2).

| Preset · layout | Pads send | Pads light at | Buttons send |
|---|---|---|---|
| 1 · clips | notes 1–16, port 3 | LEDs 33–48 | notes 17–21 (play, stop, record, `<`, `>`) |
| 1 · mixer | notes 49–64, port 3 | LEDs 85–100 | |
| 2 · steps | notes 101–116, port 3 | LEDs 69–84 | notes 117–121 |
| 2 · drums | notes 36–51, plain MIDI on ports 1 and 2, velocity-sensitive | unlit | |
| 3 · keyboard | notes 85–100, port 3 | LEDs 1–16 | notes 17–21 |
| 3 · key and scale | notes 22–37, port 3 | LEDs 49–64 | |
| 4 · chords | notes 65–80, port 3 | LEDs 101–116 | notes 17–21 |
| 4 · key and scale | notes 38–48, 81–84 and 122, port 3 | LEDs 22–32, 65–68 and 123 | |

Pads read left to right, top to bottom: the top-left pad sends the first note
of the range. Press is note-on velocity 127, release is note-on velocity 0.

The encoders send CCs on ports 1 and 2 (never port 3), and **all sixteen are
relative**, centred on 64: 63 is one step back, 65 one step forward.

| Encoder | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| Presets 1, 2 · knob bank 1 | 7 | 8 | 5 | 6 | 3 | 4 | 1 | 2 |
| Preset 1 · knob bank 2 | 17 | 18 | 13 | 14 | 11 | 12 | 9 | 10 |
| Preset 2 · knob bank 2 | 15 | 16 | 13 | 14 | 11 | 12 | 9 | 10 |
| Presets 3, 4 · knob bank 1 | 27 | 28 | 25 | 26 | 23 | 24 | 21 | 22 |
| Presets 3, 4 · knob bank 2 | 35 | 36 | 33 | 34 | 31 | 32 | 29 | 30 |

The CC numbers don't follow the printed encoder numbers. That is how this unit
was configured, and it has moved once already, so re-measure with the probe's
`--knobs` mode rather than trusting the table.

**Why relative matters.** The knob script decodes every CC as a step. An
absolute encoder sends a position, which the script would read as a huge step,
slamming a macro to its limit on the first turn. The session box is worse: it
is an index the arrows and the mouse also move, so an absolute knob's position
is out of date the moment anything else moves the box, and the box jumps the
next time you touch it.

**If you can't load the files**, configure the controller by hand to match the
tables above. [HARDWARE.md](HARDWARE.md) §5 decodes the `.spc` format byte by
byte, so the files remain the authoritative answer. Two gotchas make it
silently wrong:

- **The editor numbers pads bottom-up.** Its PAD1 is the bottom-left pad, so
  PAD13–16 carry the first four notes (HARDWARE.md 5.3).
- **The five buttons are one set per preset**, not per pad layout
  (HARDWARE.md 2.4).

Or change the numbers in the scripts to match your controller instead: see
[Customising](#customising).

### Finding out what your unit sends

`tools/mvave_probe.py` logs everything the controller sends and can light
pads, without any Remote Script. On Windows, `tools/run_probe.bat` sets it up
on first run:

```
run_probe.bat --list                            # list the ports
run_probe.bat --listen --port "SMC-PAD"         # log notes and CCs on all three ports
run_probe.bat --knobs  --port "SMC-PAD 0"       # map every encoder to its CC, one at a time
run_probe.bat --clear  --port "MIDIOUT3"        # turn every pad off
```

**Windows MIDI ports are exclusive.** Close Live, or untick the port in
Live's preferences, before running the probe, or it cannot open the port.
`SMC-PAD` matches all three Windows port names, so modes other than `--listen`
need the trailing index: `"SMC-PAD 0"`.

On macOS and Linux there is no launcher. Set the probe up once, then call it
directly. CoreMIDI and ALSA ports can be shared, so Live can stay open:

```
python3 -m venv venv-midi
./venv-midi/bin/pip install -r tools/requirements-midi.txt
./venv-midi/bin/python tools/mvave_probe.py --list
./venv-midi/bin/python tools/mvave_probe.py --listen --port "SINCO"
```

Every mode is described in **[PROBE.md](PROBE.md)**. The probe was written and
tested on Windows; on macOS the commands are standard, but the probe itself
hasn't been run there.

---

## 2. Copy the scripts into Live

Copy the folders themselves (`MVave_SMC_PAD`, `MVave_SMC_KNOBS` and
`MVave_SMC_STEPSEQ`), not their contents, and don't nest them a level deeper.
Live scans only the direct subfolders of this directory, and each must keep
its `__init__.py`. The result should look like
`…/Remote Scripts/MVave_SMC_PAD/__init__.py`. Replace any older copies.

Prefer the user location. The application folder belongs to the installer, and
a Live update can overwrite it.

**macOS**

| | Path |
|---|---|
| User | `<User Library>/Remote Scripts/`. `<User Library>` is the folder set in Live's Settings → Library. The default is `~/Music/Ableton/User Library`; a shared install may use `/Users/Shared/Ableton/User Library` |
| Application | `/Applications/Ableton Live <version>.app/Contents/App-Resources/MIDI Remote Scripts/`. Right-click the app and choose Show Package Contents to get in |

**Windows**

| | Path |
|---|---|
| User | `%APPDATA%\Ableton\Live <version>\Preferences\User Remote Scripts\` |
| Application | `C:\ProgramData\Ableton\Live <version>\Resources\MIDI Remote Scripts\` |

`<version>` is the exact installed version and **varies per install** (`Live 12`,
`Live 12.1.5`, `Live 11.3.21`, …). Open the parent folder and use the version
folder that is actually there. If you already have another custom script
installed, put these next to it.

## 3. Restart Live

Live scans the Remote Scripts directory **only at startup**. Until you restart,
the scripts won't appear in the Control Surface menu. The same applies after
any later edit to a `.py` file.

## 4. Fill the Control Surface slots

Open Live's **Settings → Link, Tempo & MIDI** (called Preferences on Windows
and in Live 11). Fill three rows of the Control Surface table at the top. Order
doesn't matter.

| Control Surface | Input and output on macOS | Input and output on Windows |
|---|---|---|
| `MVave_SMC_PAD` | `SINCO Port 3` | `MIDIIN3 (SMC-PAD)` / `MIDIOUT3 (SMC-PAD)` |
| `MVave_SMC_KNOBS` | `SINCO SMC-PAD-Private` | `SMC-PAD` / `SMC-PAD` (the first port) |
| `MVave_SMC_STEPSEQ` | `SINCO Port 3` | `MIDIIN3 (SMC-PAD)` / `MIDIOUT3 (SMC-PAD)` |

If your port names differ, identify the ports by what they carry. The lit pads
and the buttons appear on the **third** port. The encoders appear
**identically on the first two** and never on the third.

**Set the outputs too.** They are not optional extras:

- `MVave_SMC_PAD`'s and `MVave_SMC_STEPSEQ`'s output lights the pads. With
  `None`, clips still launch and steps still toggle, but nothing lights.
- `MVave_SMC_KNOBS`'s output asks the controller which preset and PAD BANK are
  up, about five times a second, so the pads repaint as soon as you switch
  (HARDWARE.md 3.6). It also puts the controller on preset 1 when Live loads,
  and is how the step sequencer learns the VELOCITY setting. With `None` the
  script can't ask, the controller stays on whatever preset it was left on, and
  the lights repaint late or not at all. (Whether the controller ever reports a
  switch unprompted is unsettled; HARDWARE.md 3.6 has captures both ways.)

`MVave_SMC_PAD` and `MVave_SMC_STEPSEQ` share port 3 deliberately. Their
presets use different note and LED numbers, so both stay loaded and switching
preset on the controller is the mode switch. Skip `MVave_SMC_STEPSEQ` if you
don't use preset 2.

## 5. Set up the remaining port

In the **MIDI Ports** list further down the same page, find the second port
(`SINCO SMC-PAD-Master` on macOS, `MIDIIN2 (SMC-PAD)` on Windows). Leave it out
of every Control Surface slot, and:

- switch **Remote on**, so Ctrl+M (Cmd+M on macOS) mapping from the encoders
  still works;
- leave **Track off**. Preset 2's drum pads and note repeat reach your tracks
  through `MVave_SMC_KNOBS` instead. With Track on they would play twice, and
  note repeat on the keyboard or the chords would play the pads' raw notes,
  ignoring the key.

**Why this port matters.** A Control Surface takes its port away from Ctrl+M:
Live turns off Track, Sync and Remote for a port as soon as a script claims
it. Ports 1 and 2 carry identical encoder CCs, so the knob script claims port 1
and port 2 stays free for mapping. If you had Ctrl+M mappings arriving on
port 1 before, installing the knob script kills them silently. Remake them on
port 2.

> **Check which port the knob script actually holds.** The **last**
> `Midi Remote Scripts` block in `Log.txt` names the input each slot is on.
> Live appends one block per launch, so scroll to the *bottom* of the file. The
> block at the top is the first session ever recorded, and following it would
> send you to remake mappings on the port the script holds.

---

## Checking it worked

The quickest check is the controller itself. When Live opens, it should switch
to preset 1 and play a waving trans flag (or a rainbow, see `INTRO_STYLE`)
across the pads for about three seconds, then
flash pad 1 (bottom-left) white. That shows `MVave_SMC_PAD` and
`MVave_SMC_KNOBS` are both loaded with their outputs set. Then pads under the
coloured session box should light orange where a clip sits and green when one
plays.

For more detail, `Log.txt` is at:

- **macOS:** `~/Library/Preferences/Ableton/Live <version>/Log.txt`
- **Windows:** `%APPDATA%\Ableton\Live <version>\Preferences\Log.txt`

Look for these lines:

```
MVave_SMC_KNOBS: loaded. CC 17/18 navigate; 16 macro CCs 1,2,...,16; preset 3 CCs 21-36 play device banks (Live bank table, 69 devices).
MVave_SMC_STEPSEQ: loaded. pads ch 1 notes 101-116, buttons ch 1 notes 117-121.
MVave_SMC_KNOBS: device -> <device name>
MVave_SMC_STEPSEQ: clip -> "<clip name>" on track "<track name>"
MVave_SMC_STEPSEQ: preset 2 up, following the selection
MVave_SMC_STEPSEQ: drum rack -> "<kit name>" on track "<track name>"
MVave_SMC_KNOBS: first nav CC -- 17 value 65
MVave_SMC_KNOBS: first macro CC -- 1 value 65 -> macro 1
MVave_SMC_KNOBS: first preset 3 knob CC -- 21 value 65 -> slot 1
```

| Line | Shows | Appears when |
|---|---|---|
| `KNOBS: loaded.` | The knob script was found and built. The bracket says whether Live's parameter-bank table was found for preset 3 (`no Live bank table` means Live 11, or a Live without it) | At startup |
| `STEPSEQ: loaded.` | The sequencer was found and built, and which notes it listens for | At startup |
| `clip -> …` | The clip the sequencer is editing, or `no clip` | At startup, and whenever that changes |
| `made …` / `picked up …` | A step pad pressed with no clip made a new clip in the selected slot, or picked up the MIDI clip there | On that press |
| `drum rack -> …` | The Drum Rack the sequencer's colours and drum picker read, or `none` | When the sequencer first draws, and whenever that changes |
| `preset 2 up` / `preset 2 away, holding …` | Whether the sequencer follows clicks in Live (preset 2 up) or holds its clip (another preset up) | On each switch to or from preset 2 |
| `device -> …` | The macro knobs have a device to control | **Only once the selected track changes.** Click a track before deciding the macros are broken |
| `first nav CC` | MIDI is reaching the knob script | The first time you turn encoder 1 or 2 on preset 1's knob bank 2. Logged once only |
| `first macro CC` | A macro knob reaches the script and resolves to a macro | The first turn of any macro knob. Logged once only |
| `first preset 3 knob CC` | Preset 3's (or 4's) knobs reach the script | The first turn of a knob on preset 3 or 4. Logged once only |

`MVave_SMC_PAD` prints nothing on a clean load. Its only log lines are
warnings, so check it by behaviour, with one exception: the first time preset 4
adds a Chord device to a track, it logs `SMC-PAD chords: added Chord, parameters
…`, every parameter with its value. If preset 4's chords sound wrong, look
there: `Use Current Scale` should be on and `Shift1 Scale Degrees` and `Shift2
Scale Degrees` at 2 and 4. (The plain `Shift1`, `Shift2` are semitones, which
Live ignores while Use Current Scale is on.) A Chord device the script added
before 2026-10-20's fix has 0 there: delete it and switch to preset 4 again.

Lines that mean something went wrong:

- `MVave_SMC_KNOBS: cannot import MVave_SMC_PAD (…)` or
  `MVave_SMC_KNOBS: MVave_SMC_PAD is not loaded -- is it in a Control Surface slot?`:
  the knob script can't find the pad script. Macros still work; moving the
  session box doesn't.
- `MVave_SMC_KNOBS: could not read the session offsets`: the pad script was
  found, but this Live version exposes the session box in a way the knob script
  doesn't recognise.
- `MVave_SMC_PAD: ClipSlotComponent has no <setter>()`: this Live version lacks
  one of the clip-colour setters. Clips still launch; that one state just won't
  light.
- `exception in …`, or a Python traceback naming one of the scripts: see
  [The script fails to load](#the-script-fails-to-load-or-never-appears-in-the-menu).

---

## Troubleshooting

The user guide has quick fixes for everyday problems (wrong preset, pads dark
in the launcher, no sound). These are the setup problems.

### Nothing happens at all: no clips launch, no lights

- **Live wasn't restarted after copying.** Scripts are picked up at startup
  only. Restart and check the Control Surface menu lists the scripts.
- **Wrong port in the slot.** The pads are on the third port. On the first or
  second, the script sees encoder CCs and no notes.
- **The controller doesn't have this project's presets**, so it sends other
  notes. Check with the probe's `--listen` mode, then load the files
  ([step 1](#1-load-the-presets-onto-the-controller)).
- **The folders landed one level too deep**, e.g.
  `Remote Scripts/mvave-smc-pad-ableton/MVave_SMC_PAD/`. Live only scans direct
  children.

### Pads launch the wrong clips, or empty pads stay white

If every pad fires the clip three pads along and the last pads stay white, the
controller holds a preset built before 8 October 2026, which put the pads in
the wrong place in the file. Import all the files from `presets/`
again.

A pad that shows white when it should be off means its LED number equals its
note, which only happens with a preset that wasn't built by
`tools/make_presets.py`. Load the files from `presets/`.

### Pads keep the old preset's colours after a switch

The controller doesn't clear the pads when you switch preset or press PAD BANK.
`MVave_SMC_KNOBS` notices the switch and makes the scripts repaint. If they
don't:

- **`MVave_SMC_KNOBS`'s output is `None`.** It can't ask the controller which
  preset is up. Set the output to the same port as its input.
- **`MVave_SMC_KNOBS` isn't loaded, or its input isn't the first port.** Check
  for its `loaded.` line in `Log.txt`.

### Preset 4 plays single notes

The chords come from Live's Chord device on the track; the pads only send each
chord's root. While preset 4 is up there should be a Chord device in front of
the synth, switched on, with **Use Current Scale** on.

- **No Chord device appears.** Check the track is armed or set to Monitor In,
  and that `MVave_SMC_KNOBS` has its output set: it tells `MVave_SMC_PAD`
  which preset is up. On a Live without `Track.insert_device` the status bar
  asks you to add the device yourself.
- **It's there but adds nothing.** Check `Shift1 Scale Degrees` and `Shift2
  Scale Degrees` (2 and 4 for triads). In scale mode Live ignores the plain
  semitone `Shift1`, `Shift2`. The script leaves a Chord device it didn't add
  as it is, so delete it and switch to preset 4 again to get one set up.
- **Nothing changed after copying new scripts.** Live reads Remote Scripts only
  when it starts: quit and reopen it.

### The macro knobs do nothing, or move the wrong macro

- **You are on the other knob bank.** KNOB BANK switches all eight encoders at
  once and the two banks carry different macros, so a knob you expect to move
  macro 3 moves macro 11 instead.
- **No device is selected yet.** After a fresh start the knobs do nothing until
  the selected track changes. Click any track once. The `device -> …` line in
  `Log.txt` appears at that moment.
- **The selected track has no device**, or **the device has fewer macros than
  the knob you turned.** Bank 2's knobs reach macros 9–16, which an eight-macro
  rack doesn't have.
- **`MVave_SMC_KNOBS` is missing or on the wrong port.** It needs the *first*
  port as input. No `loaded.` line in `Log.txt` means it was never built.
- **One knob is dead on both banks.** Its CC may not match the map. Run the
  probe's `--knobs` mode, which reports each encoder separately and names
  silent knobs and CC clashes.

### The session box jumps to one end when you turn bank 2's encoder 1 or 2

- **The encoder is absolute.** It sends a position, not a step. Switch CC 17
  and 18 to relative in MidiSuite (63 one back, 65 one forward), or load
  `preset1-launcher-mixer.spc`, which already has them relative.
- **It is relative, but the other convention.** Some encoders send 127 for one
  step back and 1 for one forward, which this script would read as ±63. Set
  `ENCODER_MODE = 'twos'` in `MVave_SMC_KNOBS/MVave_SMC_KNOBS.py` and restart
  Live. The probe's `--knobs` mode names the convention your unit sends.

### Drum pads or note repeat play twice, or note repeat ignores the key

Track is on for the second port. Switch it off ([step 5](#5-set-up-the-remaining-port)).

### Pads stay lit after Live closes

The controller ignores real note-offs: a pad goes dark only on a note-on with
velocity 0. Live sends the right thing while a script runs, but the pads hold
their last colour if the script goes away (Live closed, the slot set to `None`,
or a crash).

Clear them with the probe's `--clear` mode on the third port. On Windows,
close Live first (`run_probe.bat --clear --port "MIDIOUT3"`). On macOS, Live
can stay open:
`./venv-midi/bin/python tools/mvave_probe.py --clear --port "Port 3"`.

### Ctrl+M mappings stopped working after installing this

A Control Surface turns off Track, Sync and Remote on the port it claims, and
your mappings were arriving on the port the knob script now owns. Remake them
on the second port, with Remote on there ([step 5](#5-set-up-the-remaining-port)).

### The script fails to load, or never appears in the menu

- Live wasn't restarted, or the scripts went into the folder of a **different
  Live version** than the one you launched. Check `<version>` in the path.
- A file is missing from the copy. Each folder needs every `.py` file,
  including `__init__.py`.
- A traceback in `Log.txt` naming the script shows which line failed. An
  exception while a script starts up takes the **whole script** down, not just
  the feature that raised it.
- After any fix, restart Live again.

### Clip colours are missing or wrong

If `Log.txt` has `ClipSlotComponent has no <setter>()`, that state is
unsupported in your Live version and nothing in `MIDI_Map.py` can fix it.
Otherwise, the colours are palette numbers, not RGB: see
[Pad LED colours](#pad-led-colours).

---

## Customising

Live must be restarted for any edit to take effect.

### `MVave_SMC_PAD/MIDI_Map.py`

Everything the pad script maps lives in this one file. `-1` means unassigned.

| Constant | Controls |
|---|---|
| `CLIPNOTEMAP` | The 4 × 4 grid of pad notes, row by row from the top. Change these to match what your pads send. |
| `TSB_X`, `TSB_Y` | Session box width and height. Must match `CLIPNOTEMAP`'s size. Keep them equal: see DEVELOPMENT.md, "Known rough edges". |
| `PAD_LED_OFFSET` | A pad lights at its note plus this (32, so notes 1–16 light LEDs 33–48). Must match the preset. `MIXER_LED_OFFSET`, `KEYS_LEDS`, `SETTINGS_LEDS` and the `CHORDS_*_LEDS` do the same for the mixer and the keyboards' layouts. |
| `PLAY`, `STOP`, `REC` | Transport button notes (17, 18, 19). `STOP` is handled by the script, so it can double as the device-navigation modifier, and stops Live on release. |
| `TRACKLEFT`, `TRACKRIGHT` | Arrow button notes (20, 21): previous / next track, or previous / next device while `STOP` is held (`DeviceNav.py`). |
| `TRACKMUTE`, `TRACKSOLO`, `TRACKREC`, `TRACKSTOP` | The mixer's four rows on PAD BANK (notes 49–64). |
| `KEYS_*`, `SETTINGS_*` | The keyboard: its notes, MIDI channel, colours and the key/scale pads. |
| `CHORDS_*` | Preset 4: its notes and LEDs, its octave, the Chord device it adds (`CHORDS_DEVICE`, `''` to manage none) and that device's shape (`CHORDS_SHIFTS`, scale steps above the root: `(2, 4)` triads, `(2, 4, 6)` sevenths). |
| `BUTTONCHANNEL`, `SLIDERCHANNEL` | MIDI channel, 0-based: `0` is channel 1. |
| `MESSAGETYPE` | `0` for notes, `1` for CCs. |
| `NEW_CLIP_BARS` | Length in bars of the empty clip a pad makes on an empty slot of a MIDI track, like double-clicking the slot (`1`). `0` restores the old press: record if armed, else stop the track. The step sequencer has its own `NEW_CLIP_BARS`, in `MVave_SMC_STEPSEQ/MIDI_Map.py`, for the clip its first pad press makes ([STEPSEQ.md](STEPSEQ.md) §1). |
| `INTRO_ENABLED` and the other `INTRO_*` | The startup intro. `INTRO_ENABLED = False` turns it off. `INTRO_STYLE` picks `'flag'` (a waving trans flag, the default) or `'rainbow'`. `INTRO_FLAG` holds the flag's five stripe colours, bottom to top, and `INTRO_WAVE_TICKS` how many ticks one ripple takes (10 is one a second). `INTRO_COLOUR_TICKS` sets the rainbow's speed (1 is the fastest that shows every colour; 2 is half speed). |
| `MODIFIER` | Disabled (`-1`). Set to a button note, the arrows bank the session box through scenes while it is held, at the cost of that button's normal job. |
| Everything else | Standard slots from the template this is built on: sends, scene launch, device banks. Nearly all `-1`. |

### Pad LED colours

Also in `MIDI_Map.py`:

```python
CLIP_PLAYING = 5           # clip is playing
CLIP_STOPPED = 15          # slot holds a clip, not playing
CLIP_RECORDING = 14        # clip is recording
CLIP_TRIGGERED_PLAY = 21   # queued, waiting for the quantise point
CLIP_TRIGGERED_REC = 24    # queued to record
```

The velocity of a note-on sent **to** the SMC-PAD picks a colour from a fixed
palette. It is not a brightness, and it overrides whatever colour the pad was
given in the editor. Most vivid colours are below 25, and everything from 64
to 112 is the same flat blue. There is no saturated red; 14 is as close as it
gets. The full table is in HARDWARE.md §3.2.

Reliable choices: **5** green · **14** red-pink · **15** orange · **21** bright
blue · **24** light purple · **40** white · **0** off.

14 and 15 sit next to each other in the palette. If red-pink and orange are
hard to tell apart under your lighting, move `CLIP_STOPPED` to 21 or 24.

### `MVave_SMC_KNOBS/MVave_SMC_KNOBS.py`

The settings are constants at the top of the file:

- `MACRO_BY_CC`: maps each macro CC to a macro number. Macro *N* is
  `device.parameters[N]`; index 0 is the device on/off switch, so there is no
  offset. Write it in **encoder order**, not numeric CC order, or the macros
  scatter across the panel.
- `PARAM_BY_CC`: the same for presets 3 and 4's CCs 21–36, mapped to slots in Live's
  parameter banks.
- `CC_TRACK = 17`, `CC_SCENE = 18`: the session-box encoders (preset 1, knob
  bank 2, encoders 1 and 2). They must differ.
- `ENCODER_MODE = 'centre'`: **which relative convention your encoders use.**
  `'centre'` is 63 back / 65 forward (this unit); `'twos'` is 127 back / 1
  forward. The two can't be told apart on the wire, so this is a setting. The
  probe's `--knobs` mode reports which one it saw, in those words.
- `STEPS_PER_SWEEP = 127.0`: one click moves this fraction of a parameter's
  range. A rack macro runs 0–127, so one click is one unit.
- `STARTUP_PRESET`, `STARTUP_BANK`: where the controller goes when Live loads
  (`0`, `0` = preset 1, PAD BANK off). `None` leaves it where it was.
- `POLL_TICKS`: how often it asks the controller for its preset (`2` display
  ticks, about 0.2 s). Each request flashes Live's MIDI indicators.

### Editing with shell tools

The template's files in `MVave_SMC_PAD/` (`Special*Component.py` and
`__init__.py`) have **CRLF line endings**; everything else is LF. `sed`
patterns anchored on `$` silently do nothing on CRLF lines.

---

## Uninstalling

1. In Live's Settings → Link, Tempo & MIDI, set every Control Surface slot
   showing `MVave_SMC_PAD`, `MVave_SMC_KNOBS` or `MVave_SMC_STEPSEQ` back to
   `None`.
2. Delete the three folders from the Remote Scripts directory you copied them
   to.
3. If you had **Mackie Control** in a slot before, put it back on the third
   port (input and output) to restore the factory DAW mode: pads 1–4 select a
   track, 5–8 arm, 9–12 solo, 13–16 mute, with PAD BANK toggling tracks 1–4 /
   5–8.
4. If pads were left lit, clear them with the probe's `--clear` mode
   ([Pads stay lit](#pads-stay-lit-after-live-closes)).
5. The presets live on the controller, not in these files, so none of the above
   changes them. Load a factory preset in MidiSuite if you want the controller
   back as it shipped.
