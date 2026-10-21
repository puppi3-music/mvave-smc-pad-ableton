# M-Vave SMC-PAD for Ableton Live

Ableton Live Remote Scripts that give an **M-Vave SMC-PAD** four jobs, one per
preset on the controller:

1. a Launchpad-style **clip launcher**, with a mixer one button press away;
2. a Push-style **step sequencer** that edits the selected MIDI clip, with
   velocity-sensitive drum pads one button press away;
3. a Launchpad-style **scale keyboard** for playing a synth;
4. a **chord keyboard**: every pad a chord of the key.

On every preset the encoders control the selected device.

Don't have one yet? The SMC-PAD is available on
[AliExpress](https://www.aliexpress.com/item/1005012967834750.html).

Also here: a **complete measured MIDI reference** for the SMC-PAD, and the tool
used to measure it. The manufacturer publishes no MIDI implementation (both its
manuals are marketing copy), so as far as we know that reference exists nowhere
else.

> **Here to make music?** Read the **[user guide online](https://puppi3-music.github.io/mvave-smc-pad-ableton/smc-pad-guide.html)**
> (or open `docs/smc-pad-guide.html` from a download in any browser). It has
> four step-by-step example sessions, an "I want to…" cheat sheet, every mode
> and the one-off setup. The rest of this
> README is for people installing, porting or changing the scripts.

---

## Where to read what

| You want to… | Read |
|---|---|
| Play: example sessions, every control, quick fixes | [the user guide](https://puppi3-music.github.io/mvave-smc-pad-ableton/smc-pad-guide.html) (`docs/smc-pad-guide.html`) |
| Install on Windows or macOS, check it worked, troubleshoot | [docs/INSTALL.md](docs/INSTALL.md) |
| Understand or change the step sequencer | [docs/STEPSEQ.md](docs/STEPSEQ.md) |
| Know exactly what the hardware sends and accepts, and the `.spc` file format | [docs/HARDWARE.md](docs/HARDWARE.md) |
| Change the scripts, or port them to another controller | [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) |
| Measure a controller yourself | [docs/PROBE.md](docs/PROBE.md) |
| Read how the device was reverse-engineered, and what went wrong | [docs/FINDINGS.md](docs/FINDINGS.md) |

---

## What you get

### The four presets

Hold **Shift** and press pad 1, 2, 3 or 4 (bottom row, from the left) to switch.
Nothing in Live changes when you do, because all the scripts stay loaded.
**PAD BANK** flips the pads to a second layout within the preset.

| Preset | Pads | PAD BANK | File to load |
|---|---|---|---|
| 1 | **Clip launcher**: a 4 × 4 session box, each pad lit by its clip's state | **Mixer** for the same four tracks: on/off, solo, arm, stop | `preset1-launcher-mixer.spc` |
| 2 | **Step sequencer**: 16 steps of one drum in the selected MIDI clip, or 4 drums × 4 steps | **Drum pads**: velocity-sensitive, unlit, laid out like a Drum Rack | `preset2-sequencer-drums.spc` |
| 3 | **Scale keyboard**: only notes in the current key, or chromatic | **Key, scale and octave** | `preset3-keys.spc` |
| 4 | **Chords**: each pad a chord of the current key, going up the scale | **Key, scale and octave** for the chords | `preset4-chords.spc` |

The files are in `presets/` and are loaded with MidiSuite, M-Vave's
editor. When Live opens, it puts the controller on preset 1 and plays a short
rainbow across the pads.

### Buttons and knobs

| Control | Presets 1, 3 and 4 | Preset 2 (sequencer) |
|---|---|---|
| Play | Live's play | Launch or stop the selected clip. Record + Play starts or stops Live |
| Stop | Stop Live, on release | Switch between 16 steps and the 4 × 4 overview, on release |
| Hold Stop + `<` `>` | Move the blue hand to the previous / next device on the track | The same. A Drum Rack's selected drum comes right after the rack |
| Record | Arrangement record | Held: the pads show the drums. Record + pad picks one. Record + `<` `>`: clip one bar shorter / longer |
| `<` `>` | Select the previous / next track | Page through the steps |
| Knob bank 1 | Macros 1–8 of the selected device (presets 3 and 4: Live's first parameter bank for it) | Macros 1–8 |
| Knob bank 2 | Encoders 1–2 move the session box, 3–8 are macros 9–14 (presets 3 and 4: Live's second parameter bank) | Macros 9–16 |

Launcher pad colours: green playing · orange stopped · red-pink recording ·
blue queued to play · light purple queued to record · off empty. On a MIDI
track, an empty pad makes an empty one-bar clip, as a double-click on the slot
does.

### Things worth knowing about each mode

**Step sequencer.** The clip is the only state it keeps, so Ctrl+Z undoes a
step, saving the set saves the pattern, and a note drawn with the mouse lights
up on the pads. The 16 pads follow the playhead, so a 32- or 64-step loop needs
no paging. Steps light in their drum's colour (kick red-pink, snare and clap
green, hats light blue, cymbals yellow, toms purple), taken from the Drum Rack
pad's name, or from the General MIDI note when there is no name. Live's status
bar names every edit and page. New steps are written at the velocity picked
with the controller's own setting (Shift + pad 9–12: 40, 70, 100 or 127), and
it starts at 127. While another preset is up, the sequencer keeps its clip
however the selection moves. Details: [docs/STEPSEQ.md](docs/STEPSEQ.md).

**Keyboard.** The layout is a Launchpad's Note mode: root at bottom-left, each
row three scale notes above the one below. Roots light blue, fifths purple and
other scale notes white. Press the lit root on PAD BANK to switch to the
chromatic layout. The key and scale are Live 12's own Scale setting, so changing
either side moves the other. Every note plays at full velocity, because pads
the host can light always send 127 ([HARDWARE.md 5.6](docs/HARDWARE.md)). Notes
reach whichever track is armed or set to Monitor In, with its input on **All
Ins**, on **MIDI channel 2**. A synth listening only on channel 1 won't hear
them.

**Chords.** Preset 4 is preset 3 with chords. Its pads go up the scale one
note at a time with no repeats (in C major: C, Dm, Em, F / G, Am, B°, C / ...),
lit like the keyboard. A translated pad can only send one note, so each pad
sends its chord's root and Live's **Chord** MIDI effect adds the rest. While
preset 4 is up, the script switches on the Chord device of each track the pads
play. Where there is none, it adds one in front of the instrument, with **Use
Current Scale** on and shifts of +2 and +4 scale steps. That gives each chord
the quality the key makes it. A Chord device already on the track keeps its own
shifts. On any other preset the ones it switched on go off again, so preset 3
plays single notes. Adding the device needs `Track.insert_device`, which Live
12.4 has; without it the status bar asks you to add one. PAD BANK is preset 4's
own key, scale and octave page. Key and scale are Live's, so presets 3 and 4
always share them, but each has its own octave. `CHORDS_SHIFTS` in
`MIDI_Map.py` sets the shape, and `(2, 4, 6)` gives sevenths. Its knobs and
buttons are preset 3's.

**Preset 3's knobs** (and preset 4's) play the device with Live's blue hand, using Live 12's own
parameter banks (the table Push uses), so built-in instruments work with no
mapping. Racks get macros 1–16. Plugins get the parameters their **Configure**
list holds, in order. The knobs are relative, so switching devices never makes
a parameter jump. `Log.txt` says at load whether Live's bank table was found.

---

## How the scripts fit together

A Remote Script reads exactly one MIDI input port, and the SMC-PAD sends its
lit pads and its encoders on different ports. So there are three scripts in
three Control Surface slots:

| Script | Port | Runs |
|---|---|---|
| `MVave_SMC_PAD` | 3 (the DAW port) | Presets 1, 3 and 4: pads, buttons and lights for the launcher, mixer, keyboard and chords, and preset 4's Chord devices |
| `MVave_SMC_STEPSEQ` | 3 | Preset 2: the step sequencer's pads, buttons and lights |
| `MVave_SMC_KNOBS` | 1 | The knobs on every preset. It also watches which preset and PAD BANK are up and tells the pad scripts to repaint (and the pad script which preset is up, for preset 4's Chord devices), puts the controller on preset 1 when Live loads, and passes preset 2's drum pads and note repeat to tracks |

Port 2 stays out of every slot, with **Remote** on (so Ctrl/Cmd+M mapping still
works) and **Track** off.

`MVave_SMC_PAD` and `MVave_SMC_STEPSEQ` share port 3 safely. Their presets use
different note and LED numbers, and lighting a number the active preset
doesn't use does nothing. Both stay loaded, and switching preset on the
controller is the mode switch.

**Plain MIDI goes through `MVave_SMC_KNOBS`.** The drum pads and the
controller's note repeat are plain MIDI on ports 1 and 2. Note repeat is
generated by the firmware and always sent as the pad's raw note on channel 10
([HARDWARE.md 5.7](docs/HARDWARE.md)). With Track on for port 2, note repeat on
the keyboard would play notes 85 and up whatever the key. So Track is off, and
`MVave_SMC_KNOBS` passes them on with Live's note translation, on MIDI channel 2:

| Input | Reaches the track as |
|---|---|
| Drum pads and their repeats (channel 10 or 1, notes 36–51) | The same notes |
| Note repeat on the keyboard (channel 10, notes 85–100) | The scale note that pad plays, kept in step with the keyboard |
| Note repeat on the chords (channel 10, notes 65–80) | That pad's chord root, which the Chord device fills out |

Repeats keep the controller's own velocity, which is low (10–15 measured). Note
repeat on the launcher, mixer or sequencer pads plays nothing.

---

## Install

In short:

1. Load the four files in `presets/` into presets 1–4 with
   MidiSuite.
2. Copy `MVave_SMC_PAD/`, `MVave_SMC_KNOBS/` and `MVave_SMC_STEPSEQ/` into
   Live's Remote Scripts folder.
3. Restart Live and fill three Control Surface slots.
4. Leave port 2 out of the slots, with Remote on and Track off.

Full steps, port names for Windows and macOS, verification and troubleshooting
are in **[docs/INSTALL.md](docs/INSTALL.md)**.

> **The presets matter as much as the scripts.** The scripts expect the note,
> CC and LED numbers those four files set up, with every encoder relative. A
> factory-configured unit sends different numbers and will appear to do
> nothing. If your pads launch the clip three pads along, the controller holds
> a preset built before 8 October 2026: import the current files again.

The presets are generated: `tools/make_presets.py` builds all four from the
launcher and sequencer sources in `reference/`.

## Layout

```
├── MVave_SMC_PAD/        presets 1, 3, 4: pads, buttons, LEDs, keyboards  (copy into Live)
├── MVave_SMC_KNOBS/      encoders, preset detection, MIDI pass-through    (copy into Live)
├── MVave_SMC_STEPSEQ/    preset 2: the step sequencer                     (copy into Live)
├── docs/
│   ├── smc-pad-guide.html  the user guide: example sessions, cheat sheet, every mode
│   ├── smc-pad.jpg         picture of the controller used in the guide (© M-Vave)
│   ├── index.html          forwards the GitHub Pages site root to the guide
│   ├── INSTALL.md          setup, verification, troubleshooting, customising
│   ├── STEPSEQ.md          the step sequencer: behaviour, design, what is unconfirmed
│   ├── HARDWARE.md         the measured MIDI reference: ports, notes, LED palette,
│   │                       encoders, the editor protocol and the .spc file format
│   ├── DEVELOPMENT.md      architecture, _Framework gotchas, porting to another controller
│   ├── PROBE.md            the measurement tool, mode by mode
│   └── FINDINGS.md         how the device was reverse-engineered, and what went wrong
├── presets/              what to load into the controller (see WHICH-PRESET.txt)
│   ├── preset1-launcher-mixer.spc
│   ├── preset2-sequencer-drums.spc
│   └── preset3-keys.spc
├── reference/            not for loading
│   ├── smc-pad-launcher-led33.spc   inputs to tools/make_presets.py
│   ├── smc-pad-sequencer-led69.spc
│   ├── launchpad.spc                the first two presets as MidiSuite exported
│   └── sequencer.spc                them (byte-scanned: no vendor text, branding
│                                    or serial); HARDWARE.md reads these
└── tools/
    ├── make_presets.py      builds presets/ from the two sources in reference/
    ├── mvave_probe.py       the MIDI probe
    ├── run_probe.bat        Windows launcher for the probe; builds its own virtualenv
    ├── requirements-midi.txt
    └── stepseq_selftest.py  runs all three scripts against a fake Live, no DAW needed
```

## The probe

`tools/mvave_probe.py` talks straight to the controller's MIDI ports. It needs no
Remote Script and never touches Ableton. It can list ports, log everything the
device sends, light pads, walk the LED palette one velocity at a time, and map
every encoder to its CC with a checkpoint at each knob.

It is included because this device is undocumented and every number in
[HARDWARE.md](docs/HARDWARE.md) had to be measured. If you own a different
controller it adapts easily: see [PROBE.md](docs/PROBE.md).

## Status

In daily use on macOS with Live 12.3. Built, and first verified, on Windows
with Live 11.3. The keyboards and the knobs on presets 3 and 4 are built on two
Live 12 features, the song's Scale setting and Live's parameter-bank table.
Without them the knobs fall back to plain parameter order and the keyboards to
their own key and scale. That fallback has not been tried on Live 11. Preset
4's chords also need Live 12's Chord device with Use Current Scale; the script
adds it itself on Live 12.4 (`Track.insert_device`).

**Not yet confirmed on hardware**, documented rather than hidden:

- In the sequencer, added 2026-10-20: changing the clip length with Record +
  `<` `>`, skipping empty banks of a Drum Rack, drum colours in the picker, and
  the Stop and arrow LEDs ([STEPSEQ.md](docs/STEPSEQ.md) §1).
- Several `_Framework` behaviours that could not be checked outside Live are
  marked as such in the code and in [DEVELOPMENT.md](docs/DEVELOPMENT.md).

**Known gaps:**

- **Sequencer steps can't take the strike velocity.** The pads that can light
  are the pads that cannot sense velocity, so steps use the controller's
  VELOCITY setting instead ([STEPSEQ.md](docs/STEPSEQ.md) §9).
- **Both knob banks are claimed on port 1.** Bank 1 uses CC 1–8, two of which
  (CC 1, CC 7) are the mod wheel and channel volume. That's harmless while the
  port belongs to a Control Surface, but a hazard if you ever hand the port back
  to Live's MIDI mapping.
- **Two latent bugs inherited from the template**: a `_do_uncombine()` guard
  that can never fire, and `TSB_X`/`TSB_Y` swapped in two places. Harmless with
  a square grid; both would bite anyone adapting this
  ([DEVELOPMENT.md](docs/DEVELOPMENT.md#known-rough-edges)).
- **The probe's launcher, `run_probe.bat`, is Windows-only.** On macOS and Linux
  you run the probe with Python directly ([PROBE.md](docs/PROBE.md#setup)).

**Quoting a version.** These scripts carry no version number in Live, and a
copied folder has no commit hash. For a bug report, quote `SCRIPT_REVISION` at
the top of `MVave_SMC_PAD/MIDI_Map.py`, `MVave_SMC_STEPSEQ/MIDI_Map.py` and
`MVave_SMC_KNOBS/MVave_SMC_KNOBS.py`. Whoever changes a script sets its
revision to that day's date.

## Why this exists

The SMC-PAD's factory DAW mode speaks Mackie Control. That gives you LED feedback
but **no clip launching**: MCU is a mixer and transport protocol with no concept
of a clip grid, and the factory layout spends all 16 pads on select/arm/solo/mute.
Live's stock `MackieControl` script will never fire a clip.

These scripts take over that Control Surface slot instead. The firmware still
sends pad notes and still lights pads from incoming MIDI; nothing requires Live
to interpret those notes as mute and solo. It is fully reversible: put
`Mackie Control` back in the slot and you are where you started.

## Attribution

`MVave_SMC_PAD/` descends from **Hanz Petrov's "Introduction to the Framework
Classes"** template, the long-standing starting point for custom Live Remote
Scripts. Its six `Special*Component.py` files — channel strip, mixer, session,
transport, view controller and zooming — are template code of **mixed and partly
unverified origin**: substantially Petrov's, but one is marked a partial
decompile of Ableton's own scripts and another credits an "OpenLabs" module for
its undo/redo block. See the Licence section below and the file-by-file table in
[DEVELOPMENT.md](docs/DEVELOPMENT.md). The clip-state colours, the modifier
button, the keyboard, the startup intro and every value in `MIDI_Map.py` are
this project's. `MVave_SMC_KNOBS/`, `MVave_SMC_STEPSEQ/`, `tools/` and `docs/`
are original — bar each package's three-line `__init__.py`, which is the
template's boilerplate with the names changed, footer included.
[DEVELOPMENT.md](docs/DEVELOPMENT.md) carries a file-by-file provenance table.

Not affiliated with or endorsed by Ableton, M-Vave/Cuvave, Novation or Focusrite.
Product names — including Live, Push, Launchpad and Mackie Control — belong to
their owners and are used here descriptively.

## Licence

**Not yet chosen.** `MVave_SMC_KNOBS/`, `MVave_SMC_STEPSEQ/`, `tools/` and
`docs/` are original work (bar the two `__init__.py` entry points, which are the
template's boilerplate with the names changed). `MVave_SMC_PAD/` is not, and what it inherits comes
from **three** upstreams, not one. All three ship, deliberately — the point of
listing them here is that a reader can see exactly what they are getting:

- **Hanz Petrov's "Introduction to the Framework Classes"** — the structural
  skeleton, the 128-element MIDI map and the `Special*` components. Published on
  [remotescripts.blogspot.com](http://remotescripts.blogspot.com/2010/03/introduction-to-framework-classes.html)
  from 12 March 2010, in four parts, with the example scripts on its
  [Support Files](http://remotescripts.blogspot.com/p/support-files.html) page.
  **Checked 2026-09-05: neither page states any licence, copyright notice or
  terms of use.** The material is presented as educational, with no permission
  granted or withheld in writing.
- **Ableton's own shipped scripts.** `SpecialViewControllerComponent.py:5` carries
  `# Partial --== Decompile ==-- with fixes`, which asserts on its face that the
  file was recovered from compiled bytecode rather than typed from a tutorial.
  The likely route is the template itself: Petrov's Support Files page also
  distributes **decompiled Live 8.2.2 `_Framework`, APC40 and APC20 scripts**, so
  this appears to arrive with the lineage rather than having been decompiled
  here. That identifies the path, not the permission.
- **An "OpenLabs" module.** `SpecialTransportComponent.py` credits it in seven
  places for the undo/redo block. Searched 2026-09-05 without finding
  an identifiable OpenLabs release: `SpecialTransportComponent.py` is described in
  the community as a re-usable module that circulated with APC40 scripts, which
  Petrov's blog also distributes, so it plausibly arrived by the same route —
  but that is inference, and the origin remains unestablished. The block is
  kept, and currently unwired (`UNDO = -1`, `REDO = -1`) — see
  [DEVELOPMENT.md](docs/DEVELOPMENT.md) for how to re-enable it.

There is no LICENSE, COPYING or NOTICE file in this repository yet. The one
upstream that *can* be identified states no terms of its own, so what
`MVave_SMC_PAD/` inherits is an absence rather than a permission. That is the
constraint on choosing a licence for the parts that are original, and it is why
this section exists in place of one: everything above is disclosed so that
anyone reusing this can make their own assessment of the parts that are not
mine to license.
