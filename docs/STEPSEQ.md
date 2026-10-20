# `MVave_SMC_STEPSEQ` — the step sequencer

The Remote Script behind preset 2. The 16 pads become 16 steps of one drum
lane in the selected MIDI clip, with LED feedback and a playhead that chases
Live's own playback. A second view turns the grid into four lanes by four steps,
so a kick/clap/hat/open-hat groove is readable at a glance.

For how to *use* it, the user guide ([smc-pad-guide.html](smc-pad-guide.html),
"Step sequencer") is the place to start. This file is for changing it: what
every control does, why it is built the way it is, and what is still
unconfirmed.

| Section | |
|---|---|
| [1. What it does](#1-what-it-does) | every control, and the behaviour behind it |
| [2. The three properties](#2-the-three-properties-everything-else-hangs-off) | the design in three rules |
| [3. How it renders](#3-how-it-renders) | LED diffing, step bucketing |
| [4. Where the brief met the hardware](#4-where-the-brief-met-the-measured-hardware) | what the original brief got wrong, and why |
| [5. Phase 0](#5-phase-0--closed) | the measured hardware facts it depends on |
| [6. Installing](#6-installing) | the preset and the Control Surface slot |
| [7. The self-test](#7-the-self-test) | running it with no Live and no controller |
| [8. Deliberately not built](#8-deliberately-not-built) | |
| [9. To do](#9-to-do) | step velocity, unreachable knobs, the open experiment |

This is the design record the original build brief asked for. The brief
itself is no longer kept: this file is what got built, and section 4 says where
the brief and the hardware disagreed.

> **Status: running in Live on real hardware** (2026-08-31). Every value in
> `MIDI_Map.py` is measured rather than assumed — section 5 has the table and
> [HARDWARE.md](HARDWARE.md) has the method. The logic is also exercised by
> `tools/stepseq_selftest.py` (no controller and no DAW required),
> which is what makes a change safe to attempt without a Live restart.
>
> Two things the first real session changed: the visible window now follows the
> playhead, and the lane picker banks past its first sixteen pitches. Both were
> found in minutes of use and neither was visible from the self-test — a
> reminder of what running it actually buys you.

---

## 1. What it does

| Control | Focus view | Overview |
|---|---|---|
| Pads | toggle a 16th note in the current lane | toggle a step at (lane row, beat column); lowest lane on the **bottom** row |
| MOD held | **the pads show the lane picker** (below) instead of steps, and the status bar names the lane | same |
| MOD + pad | select the lane, drum-rack layout, and select that drum's pad in the track's Drum Rack | same, and scrolls the lane window so it is the bottom row |
| `<` `>` | page through the steps by 16; lit when there is a page that way | page four steps at a time |
| MOD + `<` `>` | **clip one bar shorter / longer** (16 steps, snapped to whole bars, 1 bar to `STEPS_MAX`) | same |
| MOD + stop + `<` `>` | **bank the lane picker by 16 pitches**, skipping banks of an empty Drum Rack | same |
| stop button | switch view, **on release** | switch view, on release |
| stop held + `<` `>` | **move the blue hand** to the previous/next device | same |
| play button | **launch the selected clip**; press again to stop it (a queued launch is cancelled). With no clip, or an Arrangement clip, starts/stops Live's transport | same |
| MOD + play | start/stop Live's transport — the way to stop everything | same |
| Shift + pad 9–12 | **velocity of new steps**: 40, 70, 100 or 127, the controller's own VELOCITY setting (section 9) | same |
| knobs | macros of the selected device, through `MVave_SMC_KNOBS` (the sequencer's own knob handlers are unreachable — see below) | same |

**All five buttons show state on their own LEDs** — play lit while the
selected clip plays or is queued (the transport, with no clip), the view button lit while you are in overview, the modifier lit
while held, and each arrow lit when pressing it would move somewhere: another
step page, or with MOD held another bank of drums (the same scan the move uses,
so a lit arrow always moves). `ARROW_LEDS = False` leaves the arrows dark.

This needs the buttons' **feedback option turned ON in the M-Vave editor**. With
it off the button lights from its own press and ignores the host, so the script's
writes do nothing; with it on the button is dark unless something lights it, which
is what this is for. `BUTTON_LEDS = False` in `MIDI_Map.py` turns it off again.

It also needs each button to **have an LED number** in the preset. The last
byte of a button record appears to be it (HARDWARE.md 5.2): the shipped source
had one on play and record only, so stop and the arrows stayed dark whatever
the script sent. Since 2026-10-20 `preset2-sequencer-drums.spc` gives all five
buttons their own note as LED number — re-import it to light stop in the
overview and the arrows. Inferred, not yet seen working.

Whether the button LEDs take the pad palette or are simply on/off is unmeasured —
`BTN_LED_ON` is a velocity either way, so pick from the palette in
[HARDWARE.md](HARDWARE.md) 3.2 if they turn out to be colour capable.

**The clip is pinned while you're away.** `MVave_SMC_KNOBS` reads the preset
from the controller's status message (HARDWARE.md 3.6) and calls
`set_on_screen()`. While another preset is up, selection changes are ignored and
the sequencer keeps its clip, so playing preset 3 on another track doesn't lose
the pattern. Back on preset 2, it keeps that clip until the selection next
changes; a clip deleted while away is replaced by the selected one. Without the
knobs script it always follows the selection.

**The window follows the playhead.** The sixteen pads show the sixteen steps
being played, so a 16, 32 or 64-step loop needs no paging at all.

Paging by hand stops the chase for a moment, because otherwise the next audio
buffer yanks the view straight back and the arrow looks broken. It comes back on
its own — **paging away is a peek at the current cycle, not a mode**:

| What you do | What happens |
|---|---|
| press `<` or `>` while playing | the view stays where you put it |
| the loop comes round again | the chase resumes and the view snaps to the playhead |
| page back onto the playing page | resumes immediately, without waiting |
| stop the clip or the transport | resumes |

So you can page away to edit steps 17–32 while 1–16 play, and at the top of the
next loop the view returns to the music by itself. You never have to remember to
re-arm it, and the wait is bounded by one cycle.

`FOLLOW_RESUMES_ON_WRAP = False` makes a manual page stick until you page back or
stop; `FOLLOW_PLAYHEAD = False` turns the whole thing off.

**The status bar says what the pads cannot.** Page 1 and page 3 of a 64-step
loop look alike, so every page move — by hand, by following the playhead, or a
view switch — names the window: `Steps 17-32 of 64  -  page 2/4  -  Kick (C1)`,
or `Overview  -  steps 5-8 of 64  -  lanes C1-D#1`. Every pad edit names itself:
`Kick (C1) step 5/16 on` (the drum's name comes from the Drum Rack; without one
it is just the pitch). `SHOW_PAGE_MESSAGES` and `SHOW_STEP_MESSAGES` in
`MIDI_Map.py` switch either off.

**PAD BANK: a lit drum bank was tried and taken out (2026-10-20).** The idea:
preset 2's second bank as sixteen lit pads in drum colours that play the rack
and pick the lane on a hit, like Push. The preset sent notes 65–80 on port 3 as
built, and the script translated them in Live's MIDI map onto the rack's
pitches on channel 2 (`c_instance.set_note_translation`) and forwarded the
translated note non-consuming (`Live.MidiMap.forward_midi_note(…, False)`, the
call ableton.v2's `ScriptForwarding.non_consuming` makes). No drum played and
the log showed nothing. Unchecked when it was removed: whether **Track** was on
for the `SINCO (Port 3)` input — Live only hands a port's notes, translated or
not, to tracks when it is, so this is the first thing to check before trying
again (preset 3's keyboard rides on the same translation) — and whether the hit
reached the script (the white pad would have moved). PAD BANK went back to the
velocity-sensitive drums on 36–51 below.

**MOD is the record button** (`BTN_MOD`, note 119), held down. It is deliberately
not called SHIFT: the device has a key physically labelled SHIFT which does
something else entirely and transmits nothing at all
([HARDWARE.md](HARDWARE.md) 6.1), so using that word for this button would put
two unrelated things under one name in a codebase about this exact device.

**The lane picker banks.** MOD + pad reaches sixteen pitches starting at
`LANE_SELECT_BASE`, which is one bank of a drum rack. MOD + stop + an arrow moves that
base by 16, so all 128 pitches are reachable. The two end stops land on 0 and
112 rather than on the `LANE_SELECT_BASE + 16k` series, and stepping back off a
stop returns to the series — the picker tracks a bank index, not the base, so a
trip to either end does not strand it.

**MOD + an arrow sets the clip length.** One bar (16 steps) per press, snapped
to whole bars, so a 20-step loop goes to 16 or 32. It stops at one bar and at
`STEPS_MAX` (16 bars), and the status bar says `Clip length 2 bars (32 steps)`,
or `Clip is 1 bar, the shortest` at a stop. The arrows light when there is a
length that way. Growing adds empty steps; nothing is copied, and notes past a
shortened loop stay in the clip, dark and out of reach, until it grows again.
Stop held as well turns the arrows back into the lane-bank control, and a stop
used this way does not switch the view on release. Added 2026-10-20, **not yet
tried on hardware.**

**With a Drum Rack, the picker stays on the kit.** A bank of 16 that holds no
sound, no note in the loop and not the current lane is skipped, and past the
last one MOD + stop + an arrow does nothing but say `No more drums above D#2` (or
below) in the status bar. A 16-pad kit therefore never banks at all. This came
from use: the bank above a 16-pad kit was sixteen dark pads, which looked like
a fault, and a lane picked there plays nothing. Without a Drum Rack on the
track every pitch stays reachable, as above. Added 2026-10-20, **not yet tried
on hardware.**

**Holding MOD shows the picker.** Otherwise nothing on the controller says
which lane the pads are editing. While MOD is held the pads show the sixteen
pitches MOD + pad can pick, in the same drum-rack layout: **white** the current
lane, and every other drum that holds a sound or has notes in the loop in **its
drum's colour** (below), the same colour as its steps; off the rest. The
playhead is not drawn over it; instead, while the clip plays, **each drum's pad
flashes white on every 16th it plays** (the current lane's white pad flashes
its drum colour), so the kit pulses with the pattern like a Push drum rack —
and that is how the picker shows which drums are in the pattern. A flash lasts
one step, so a drum on consecutive steps stays lit through them.

The flash follows the clip's playback only: hits on the PAD BANK drum pads go
straight to the track and never reach this script. `PICKER_FLASH = False` turns
it off. Releasing MOD brings the steps back.

Pressing MOD, picking a lane and banking with MOD + stop + an arrow also put the
lane in Live's status bar — `Lane C1 (36) Kick  -  MOD + pad picks C1-D#2` —
which answers the question when the current lane is outside the picker's
sixteen and no pad is white.

The current lane is `COLOR_PICK_SELECTED` (white). With `DRUM_COLORS = False`
the other drums show the older scheme instead: **teal** (`COLOR_PICK_NOTES`) for
a drum with notes in the loop and **blue** (`COLOR_PICK_LOADED`) for a loaded
drum with none. That scheme was the default until a drum turning from blue to
teal the moment it joined the pattern read as a fault on the device. Added
2026-10-20; **not yet tried on hardware.** The drum's name comes from the Drum
Rack pad's `name`, and whether that reads as the sample's name in Live is
unconfirmed.

**The overview stacks like Live's piano roll.** The lane window's lowest pitch is
the bottom row and the three above it climb upward, so a kick at C1 sits at the
bottom on both the pads and the screen. Picking a lane in overview puts it on the
bottom row.

**Stop is also a modifier.** Held, the arrows step Live's blue hand through the
selected track's devices, which is what the macro knobs (`MVave_SMC_KNOBS`)
follow. The list is the track's devices in order, with the devices of the Drum
Rack's selected pad inserted right after the rack; MOD + pad selects that pad,
so picking the Hi Tom and pressing stop + `>` lands on the Hi Tom's own device.
It stops at both ends rather than wrapping. To let the same button do both jobs,
the view now switches on release, and only if no arrow was pressed while it was
held.

**The encoder CCs are not wired**, and freeing a knob bank would not change that.
Encoder assignments are per preset, so this preset could carry its own CCs at no
cost to the launcher ([HARDWARE.md 4.1](HARDWARE.md)) — but the encoders transmit
on ports 1 and 2 and a Remote Script gets one input port, so those CCs would
still never reach this script. Paint velocity comes from the controller's
VELOCITY setting (Shift + pad 9–12, section 9), and pattern length from MOD + an arrow. The handlers remain, and they work the moment a
sibling script forwards to `handle_encoder_cc()`.

Pad colours, from the measured palette ([HARDWARE.md 3.2](HARDWARE.md)):
a step that holds a note lights in **its drum's colour** · amber the playhead ·
white the playhead sitting on an active step · off everything else. Beat markers
on empty steps exist (`COLOR_STEP_DOWNBEAT`, focus view only, never past the
loop end) but ship off — see "There is no dim" below.

**Drum colours** (`DRUM_COLORS`, `DRUM_KINDS` in `MIDI_Map.py`), in both views:

| Kind | Colour | Name contains | General MIDI pitches |
|---|---|---|---|
| kick | red-pink 14 | kick, bd, bassdrum | 35, 36 |
| snare / clap | green 5 | snare, sd, clap, snap, rim, stick | 37–40 |
| hats | light blue 7 | hat, hh, hihat | 42, 44, 46 |
| cymbals | yellow 4 | crash, ride, cymbal, cym, china, splash | 49, 51–53, 55, 57, 59 |
| toms | light purple 24 | tom | 41, 43, 45, 47, 48, 50 |
| anything else | teal 20 | | |

The kind comes from the Drum Rack pad's name, which Live usually takes from the
sample. A loaded pad's name decides on its own — "Bongo" on C1 is teal, not a
kick — and only an empty pad or a track with no Drum Rack falls back to the
General MIDI pitch. Words of three letters or more match anywhere in the name,
shorter ones only as a whole word; the first kind that matches wins. Two
caveats: light blue (hats) sits near the picker's blue (`COLOR_PICK_LOADED`),
and yellow 4 and light blue 7 were only named by eye in the palette sweep —
neither has been seen in the sequencer on hardware yet. `DRUM_COLORS = False` brings back teal
steps and the fixed overview rows (green, red-pink, blue, purple, bottom up),
and the picker's teal/blue scheme above.

## 2. The three properties everything else hangs off

**The clip is the only state.** The script stores no pattern. Steps are read
from and written to the bound MIDI clip through the Live API. Ctrl+Z undoes a
step edit, saving the set saves the pattern, a note drawn with the mouse lights
up on the pads, and Live's own playback provides sample-accurate timing — the
script never plays a note. None of that is implemented; all of it falls out of
not keeping a copy.

**One write path.** Both views funnel into `toggle_step(pitch, step_index)`. A
view is a coordinate mapping and a render function, nothing more.

**Listeners drive rendering, not the input handler.** Pressing a pad writes to
the clip and returns. The clip's notes listener fires and redraws. That is why a
pad press, a mouse edit and a Ctrl+Z produce identical LED updates, and it is
why nothing writes to the clip during a render — the listener would feed itself.

Three listeners: clip notes (redraw), clip playing position and status
(playhead), song view selected-track and detail-clip (re-bind).

## 3. How it renders

`_refresh()` reads the clip into a 16-slot grid, once per change. `_paint()`
overlays the playhead, diffs against a cache of what the device was last told,
and sends only the pads that changed. The playhead listener fires per audio
buffer and calls `_paint()` alone — no clip read, and no MIDI at all unless the
step index actually changed. At 140 BPM that is about nine repaints a second,
each one or two bytes triples.

The diff is not just tidiness. Sending all 128 notes back to back overruns this
device's MIDI input buffer and some pads silently never light
([HARDWARE.md 3.5](HARDWARE.md)) — the bug that first presented as a dead pad.

Two smaller decisions worth knowing:

- **Note times are floored into steps, not rounded.** `remove_notes_extended()`
  clears the half-open window `[t, t + STEP)`, so flooring is what makes "this
  pad is lit" and "pressing this pad clears it" agree about a note that sits
  slightly off the grid. Rounding to nearest would light a step whose window
  does not contain the note, and pressing it would appear to do nothing.
- **LEDs are always note-on.** This device ignores a real note-off entirely and
  silently, so velocity 0 is the only "off" it understands
  ([HARDWARE.md 3.3](HARDWARE.md)).

## 4. Where the brief met the measured hardware

The brief was written before [HARDWARE.md](HARDWARE.md) was consulted, and four
of its Phase 0 assumptions are already contradicted by measurements in this
repo. The architecture survived all four; the hardware constants did not.

**The knobs are probably unreachable, and it is not a software problem.** The
pads this preset uses are MCP-typed and so appear only on port 3, while the
encoders appear only on ports 1 and 2 ([HARDWARE.md 1.1](HARDWARE.md)); no port
carries both. A Remote Script gets exactly one input port.
Encoder assignments *are* per preset — the two files in `reference/` differ at
exactly encoder records 9 and 10, bank 2's first two ([HARDWARE.md 5.2](HARDWARE.md)) — so this preset
could carry its own CC 20–23 without costing the launcher anything. What it
cannot do is get them to this script: the encoders never appear on port 3, and a
Remote Script gets one input port. The way in is a forward from the encoder
script, not a different assignment.

The sequencer works without any knob. Paint velocity is the controller's
VELOCITY setting (section 9); pattern length is MOD + an arrow. If the knobs turn
out to be worth having, `MVave_SMC_STEPSEQ.handle_encoder_cc()` is the way in: a
sibling script on the encoder port can find the instance through the class-level
`_active_instances` list and forward, which is exactly what `MVave_SMC_KNOBS`
already does in the other direction to move the session box. That is a ten-line
addition to the encoder script, not a redesign of this one.

**There is no spare button to make SHIFT out of.** The device's own SHIFT key
transmits nothing at all — it is consumed by the firmware for its Shift+Pad
combinations ([HARDWARE.md 6.1](HARDWARE.md)). The five buttons above the grid
are **per-preset**, and on this preset they send notes **117–121** on channel 1.
Decoding the two exported presets settles it: the five button records read
20, 21, 17, 18, 19 in `launchpad.spc` and 120, 121, 117, 118, 119 in
`sequencer.spc`. The brief's "spare button as SHIFT, CC 104 on channel 16"
became the record button — note **119**, channel 1.

That in turn is why the script owns the play button. Claiming a port with a
Control Surface disables Track, Sync and Remote on it
([HARDWARE.md 1.4](HARDWARE.md)), so a button the script does not handle is a
dead button while this preset is live. Five buttons, five jobs.

**There is no dim.** The velocity byte sent to a pad is a palette index, not a
brightness, and the palette is absolute — it overrides the colour the pad is
configured with in the editor ([HARDWARE.md 3.1](HARDWARE.md)). "Step off = dim"
is not available; off is off. `COLOR_STEP_EMPTY` marks every in-loop empty step
and defaults to 0, because every colour on this device is full brightness and a
lit empty grid is loud. `COLOR_STEP_DOWNBEAT` marks only the four beats. It was
switched on (21, blue) on 2026-10-20 and off again the same day after a look on
the device: a lit left-hand column of empty steps read as notes, and its blue
was the picker's "loaded" blue. Set it to a palette colour to try it again.

**Relative encoders here are centre-64, not two's complement.** The brief
specified `delta = v if v < 64 else v - 128`. The two encoders switched to
relative in the M-Vave editor were measured as 63 = one step back, 65 = one step
forward ([HARDWARE.md 4.4](HARDWARE.md)). The two schemes are mutually
ambiguous — 63 means +63 under one and −1 under the other — so this is a setting
(`KNOB_MODE`) rather than something that can be detected. It defaults to the
measured scheme.

**One more, not a contradiction but a trap: numbering.** The brief calls the
sequencer "preset 3". In this repo it is **preset 2**; preset 3 is the scale
keyboard. Separately, inside a `.spc` file the pad records are counted in
blocks of 16, and the block PAD BANK's first position plays is the third one,
records 32–47 ([HARDWARE.md 5.2](HARDWARE.md)). Neither number is the preset
number. Confirm which slot and which records you are editing before you
program anything.

## 5. Phase 0 — closed

Everything the script assumed about the hardware has now been measured. Dates and
method are in [HARDWARE.md](HARDWARE.md); this is what the sequencer depends on.

| Question | Answer |
|---|---|
| Which port does the sequencer preset use? | **Port 3.** MCP-typed banks come out of port 3 — see [HARDWARE.md 5.6](HARDWARE.md), where the flag-byte-as-port-selector explanation is superseded and the confirming experiment is still unrun. |
| What do the pads send? | **Notes 101–116, channel 1, fixed velocity 127.** A purpose-built port-3 bank. |
| How are the LEDs addressed? | **By the pad's LED number**, a separate byte in the preset, sent as a note-on out of port 3. The shipped preset puts them at **69–84** (`LED_NOTES` = note − 32). They started equal to the notes, but a pad whose LED number is its own note shows white at velocity 0 and cannot be switched off. |
| Can the two scripts share port 3? | **Yes.** Note range is the only separator — the clip launcher is 1–16, this is 101–116. Channel cannot separate them; both are channel 1. |
| Do the five buttons work in this preset? | **Yes** — notes **117–121**, channel 1. They are per-preset, not global: the launcher's bank sends 17–21, this one sends 117–121. |
| Do pads self-light on press? | **No.** Four rounds, ~78 strikes, no LED movement, and a host-set colour survives being struck. |
| Does velocity select the LED colour? | **Yes**, an absolute palette index. Everything usable is below 64; 64–112 is one flat blue. |
| How does a pad turn off? | **Note-on velocity 0.** A real note-off is ignored, silently. |
| Do the encoders reach this script? | **No** — not directly. The encoders never appear on port 3, and this script owns port 3. Assignments are per preset, so the CCs are free; the port is the obstacle, and a forward from `MVave_SMC_KNOBS` is the way in. |

**The one trade you cannot configure around**, and *why* — corrected 2026-08-31:
this is not a device quirk but a consequence of the assignment type. **MCP
assignments go to port 3, are fixed-velocity, and light. Plain MIDI assignments go
to ports 1/2, are velocity-sensitive, and do not light.** MCU is a control
protocol — on/off buttons, host-driven LEDs; MIDI notes are performance data —
velocity, and no feedback path in the protocol at all. See
[HARDWARE.md](HARDWARE.md) 5.6, where the confirming experiment is written up but
not yet run.

Concretely: only port-3 banks light their
pads, and only port-3 banks are fixed-velocity. Banks on ports 1 and 2 are
velocity-sensitive but could not be lit on any port, note range or channel tried.
So a lit grid and per-step strike velocity are mutually exclusive on this device.
`USE_STRIKE_VELOCITY` stays on and inert, correct the moment a device can do both.
The controller's VELOCITY setting takes its place (section 9).

**PAD BANK, settled 2026-10-08:** it has only two positions, records 32–47
and 48–63 ([HARDWARE.md 5.2](HARDWARE.md)). `tools/make_presets.py` writes the
second as plain drum notes 36–51, which go to ports 1/2 and can't collide with
`PAD_NOTES`. (A lit bank on notes 65–80 was tried and removed on 2026-10-20, §1.)

Still genuinely unknown, and it blocks nothing:

| Question | Status |
|---|---|
| Which velocities are actually teal and amber? | 20 and 15, named by eye by one observer. Swap them for whatever reads best on your unit. |

The measurement tool is here if you need to redo any of it:
`tools/mvave_probe.py --listen --port "SMC-PAD"` (`"SINCO"` on macOS) shows what every control sends
with its port and channel, `--knobs` maps the encoders one at a time, and
`--colours --note 1` walks the palette. [PROBE.md](PROBE.md) has the modes. Live
must not be holding the port — Windows MIDI ports are exclusive.

## 6. Installing

Copy `MVave_SMC_STEPSEQ/` into Live's Remote Scripts directory alongside the other two
(see [INSTALL.md](INSTALL.md) for the path), restart Live, and add a Control
Surface slot for `MVave_SMC_STEPSEQ`. Live 11 or newer: the clip API this uses
(`get_notes_extended`, `add_new_notes`, `remove_notes_extended`) does not exist
before that, and the script says so in `Log.txt` rather than rendering an empty
grid forever.

**First, load the preset.** Import `presets/preset2-sequencer-drums.spc`
into preset 2 with MidiSuite ([INSTALL.md](INSTALL.md) step 1). That is the
whole job; the rest of this paragraph is for building one by hand.

The sequencer needs its own preset, because the note range is the only thing
that separates it from the clip launcher. It must be a **separate preset** — a
Shift+Pad slot, not the second PAD BANK of your launcher preset. The five
buttons are one set per preset file, so a PAD BANK position renumbers the pads
and leaves the buttons on 17–21: the pads would work while MOD, the view toggle
and both arrows stayed dead and drove the launcher's transport instead. Give
the preset:

- **the same assignment *type* the clip-launcher bank uses: MCP / Mackie, not
  plain MIDI.** The type is what puts a bank on port 3 and what makes its pads
  light from the host; a bank assigned as plain MIDI notes comes out of ports
  1/2, is velocity-sensitive, and does not light (HARDWARE.md 5.6). In the
  `.spc` this shows up as the flag byte `0x04`, which is most likely just the
  MCP marker — an earlier revision of this document called it a port or routing
  option, which is the reading HARDWARE.md 5.6 superseded on 2026-08-31.
- **notes 101–116**, channel 1, in screen reading order, with **LED numbers
  69–84** (note − 32)
- **buttons 117–121**, each with its own note as LED number, so the script can
  light them

The editor numbers pads **bottom-up** — its PAD1 is the bottom-left pad — so its
PAD13–16 carry the first four notes. Confirm with
`run_probe.bat --listen --port "SMC-PAD"` before going further: you want notes
101–116 on `MIDIIN3`, channel 1, and buttons 117–121 alongside them.

**Then the Control Surface slot:**

| | macOS | Windows |
|---|---|---|
| Control Surface | `MVave_SMC_STEPSEQ` | `MVave_SMC_STEPSEQ` |
| Input | `SINCO Port 3` | `MIDIIN3 (SMC-PAD)` |
| Output | `SINCO Port 3` | `MIDIOUT3 (SMC-PAD)` |

Both scripts sit on the same port and coexist because their note ranges do not
overlap: 1–16 for the clip launcher, 101–116 here. Switching the pad preset on
the device switches which one you are driving, with nothing to change in Live.

**Both scripts can stay loaded.** They render LEDs on Live-side events whichever
preset is active, but they write to disjoint LED numbers, and lighting a number
the active preset does not use does nothing (measured; see `LED_NOTES` in
`MIDI_Map.py`). Neither can overwrite the other's pads, so the
preset switch really is the mode switch, with nothing to change in Live. The one
resource they share is the device's MIDI input buffer, and neither sends in
bulk.

The pads keep their last colour across a switch, so on its own the sequencer
would come up showing the launcher's colours. `MVave_SMC_KNOBS` sees the switch
in the device's status message on port 1 and makes this script repaint all
sixteen pads (HARDWARE.md 3.6). Without the knobs script loaded on that port, the
pads stay stale until each one's colour changes for another reason.

On the port's MIDI Ports row set **Track = Off** if Live still lets you — a
Control Surface disables Track/Sync/Remote on the port it claims (INSTALL.md §4,
HARDWARE.md 1.4), so the switch may already be greyed out, in which case there is
nothing to do and nothing is wrong. Notes 101–116 are real pitches
near the top of the keyboard, and with Track on and a track armed, every step you
toggle also plays a note through that instrument. Leave Track off on
`SMC-PAD-Master` too: the drum pads on PAD BANK reach the track through
`MVave_SMC_KNOBS`, on MIDI channel 2 (README).

Live's `Log.txt` is the only debugger inside Live. On load the script prints
what it is listening for, verbatim:

```
MVave_SMC_STEPSEQ: loaded. pads ch 1 notes 101-116, buttons ch 1 notes 117-121.
```

It also logs anything it receives that `MIDI_Map.py` does not describe, once per
signature — but **do not use that to find out what your unit sends.**
`build_midi_map` forwards exactly the set `_dispatch` claims, and under Live's
forward-only routing nothing else is ever delivered, so a preset sending the
wrong notes produces no `unmapped:` line at all: the pads simply do nothing.
`docs/DEVELOPMENT.md` records the same conclusion from a hardware session. For
"what is this thing actually sending?", use `tools/mvave_probe.py --listen`,
which reads the port directly.

## 7. The self-test

```
python3 tools/stepseq_selftest.py -v
```

Runs the script against a fake Live on any machine, no controller and no DAW.
It exists because Live has no hot reload: every change costs a full restart, and
an exception inside a MIDI callback disables the script silently — the
controller just stops responding and the only evidence is a traceback in
`Log.txt`. Grid arithmetic is a punishing thing to debug through that loop.

It covers the coordinate maps, the step bucketing, the write path, LED bytes and
diffing, playhead gating, page clamping, re-binding, clip deletion, and the
map file's own sanity. It cannot cover the hardware — note numbers, channels,
the palette. That is section 5, on the device.

## 8. Deliberately not built

From the brief's own out-of-scope list: per-step velocity editing, aftertouch
ratchets, swing and nudge, auto-creating a clip when none is selected, note
repeat, melodic and scale modes. (Preset 1 can make an empty clip, and preset 3
is a scale keyboard, but neither is part of the sequencer.)

**Reading drum-rack pad names was built after all** (2026-10-20): it gives the
status bar its drum names and the steps their drum colours (section 1).

**Auto-following the playhead was built after all** (2026-08-31). The brief had
it as a nice-to-have defaulting to off, and this section previously argued that a
feature off by default is a feature nobody has tried. Running the sequencer in
Live for the first time settled it immediately: with a 32-step loop and a 16-pad
grid, manual paging is the whole interaction, and following makes loop length
stop mattering. It defaults to **on**.

Per-step velocity is also implemented (`USE_STRIKE_VELOCITY`) but **inert on this
hardware**: only port-3 banks light their pads, and only they are fixed-velocity.
See [HARDWARE.md](HARDWARE.md) — the trade is a property of the device. Once the
controller's VELOCITY setting changes, it replaces the strike (section 9).

---

## 9. To do

### Step velocity: the controller's VELOCITY setting (done 2026-10-20)

The pads send a fixed 127. MCP-typed banks are the only ones that light, and
they are not velocity-sensitive (section 5). With `USE_STRIKE_VELOCITY` on, that
127 won and `PAINT_VELOCITY` was never reached, so a whole pattern came out at
full scale: no ghost notes, no dynamics.

The way in is the controller's own VELOCITY setting, **Shift + pad 9–12**. It
transmits nothing, but it is byte 22 of the state reply that `MVave_SMC_KNOBS`
already polls for the preset ([HARDWARE.md](HARDWARE.md) 3.6 and 6.2). Each
change goes to `set_velocity_setting()`, which sets the paint velocity from
`VELOCITY_LEVELS` (40, 70, 100, 127 for VELOCITY 1–4) and shows it in the
status bar while preset 2 is up. From the first change on, the setting wins
over the strike. Steps already written keep their velocity.

- **It starts at VELOCITY 4 (127).** The setting the controller reports when
  Live starts is not passed on, because the controller remembers whatever it
  was left on. `PAINT_VELOCITY` is VELOCITY 4's level, so the sequencer starts
  where it always did.
- **It needs `MVave_SMC_KNOBS`, with its Output set.** The setting arrives in
  the reply to the knobs script's state read. Without the output there is no
  read, and a change arrives only if the controller sends its status
  unprompted, which HARDWARE.md 3.6 has seen both happen and not. With no knobs
  script loaded, steps stay at 127.
- **The drum pads read the same setting.** On preset 2's PAD BANK the
  controller applies it to the velocity-sensitive drum pads itself. VELOCITY 4
  sent 127 on every hit there. 1–3 are unmeasured on those pads (HARDWARE.md 6.2).

Still possible, for a continuous control rather than four levels: spend two
macros on `CC_VELOCITY`. Doing that takes four changes. Assign CC 20/21 on the
sequencer preset, add them to the forwarded set in
`MVave_SMC_KNOBS.build_midi_map`, and have that script's `receive_midi` call
`handle_encoder_cc(cc, value)` with the **raw** byte, before it subtracts
`CENTRE`. The knob then adjusts from the current level until the next VELOCITY
change.

### Constants describing controls that cannot exist

`CC_LANE` (20), `CC_VELOCITY` (21), `CC_LENGTH` (22) and `CC_SPARE` (23) are
unreachable for the same reason. Three of them are covered otherwise — lane
selection by holding the modifier and pressing a pad, paging by the window
following the playhead, length by MOD + an arrow — and velocity by the
controller's VELOCITY setting, in four steps.

### Confirm the MCP-vs-MIDI experiment

[HARDWARE.md](HARDWARE.md) 5.6 carries the leading explanation for why port,
velocity and LEDs move together, with the single-variable experiment written out
and not yet run.
