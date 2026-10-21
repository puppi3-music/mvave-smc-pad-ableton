# M-Vave SMC-PAD — measured MIDI reference

Everything the SMC-PAD sends, everything it accepts, and the format of its
configuration file. All of it measured on real hardware, because there is no
usable public documentation for this device — the manufacturer's manuals name
the controls and stop there.

**How this was measured.** With `tools/mvave_probe.py`, run on the Windows PC the
controller is plugged into, talking straight to the MIDI ports with no Remote
Script and no DAW involved. Pads, LEDs and the velocity settings were measured
2026-08-02; the encoder map 2026-08-03. `tools/mvave_probe.py` is in this repo,
so any of it can be re-run.

**How to read the claims.** Anything stated flatly here was observed directly.
Anything that was inferred but never tested is marked **Hypothesis** and says so.
That distinction is load-bearing: several early wrong turns in this project came
from treating a plausible inference as a fact, and they are recorded below rather
than quietly fixed.

**Scope.** Measured on Windows up to 2026-10-07, and on macOS since (3.6 and
5.7 were measured on macOS). On macOS the three ports are `SINCO SMC-PAD-Private`
(port 1), `SINCO SMC-PAD-Master` (port 2) and `SINCO Port 3`. Linux is
unchecked.

---

## 1. MIDI ports

### 1.1 Three port pairs

The SMC-PAD enumerates as three independent in/out pairs:

| # | Windows name | macOS name | Sends (device → host) | Accepts (host → device) |
|---|---|---|---|---|
| 1 | `SMC-PAD` | `SINCO SMC-PAD-Private` | encoder CCs, **and MIDI-typed pad notes**; the editor protocol (3.6) | the editor protocol only — LEDs do not respond |
| 2 | `MIDIIN2` / `MIDIOUT2` | `SINCO SMC-PAD-Master` | identical to port 1, bar the editor protocol | nothing — LEDs do not respond |
| 3 | `MIDIIN3` / `MIDIOUT3` | `SINCO Port 3` | **MCP-typed** pad and button notes | pad and button LED colours |

> **Corrected 2026-08-31.** This table previously said the pads appear only on
> port 3. They appear on ports 1 and 2 as well, as velocity-sensitive MIDI notes,
> when the pad is assigned a plain-MIDI type instead of an MCP one. Which port a
> control uses is not a setting — see the note at the end of 5.6.

"Port 1/2/3" throughout this document means the Windows enumeration above, in
that order. The manufacturer's material refers to a *generic* port and a
*Mackie/DAW* port without matching them to those names; port 3 is the DAW one.

All LED work here was done through `MIDIOUT3`. No lighting has ever been obtained
on ports 1 or 2 in any attempt so far, but what was actually tried was *plain-MIDI
banks* — not an MCP-typed bank addressed through those outputs, which is a
different experiment. The single-variable test in 5.6 has not been run, so treat
"only port 3 lights" as the leading explanation rather than a measurement. Mackie mode was the
interesting one to begin with precisely because it was the only mode on this
device that sends anything *back* for lighting.

The split matters more than it looks. **The pads you can light are on port 3, the
encoders are on ports 1 and 2, and no port carries both.** (Plain-MIDI pad banks
do reach ports 1 and 2 — see the correction above — but those cannot be lit, so
they are no use to a clip grid.) An Ableton Remote Script gets exactly one input
port, so a single script physically cannot see the whole controller. That is why
this repo has a separate script for the encoders (`MVave_SMC_KNOBS`).

Two further measured details:

- The encoders appear on ports 1 and 2 **identically** — same CC numbers, same
  message counts. Port 2 is a mirror, not a second layer.
- Encoders never appear on port 3, and with the pads on block 3 (PAD BANK off) they never
  appear on port 1. (Port 1 was watched during the velocity-curve test and
  received nothing at all while pads were being struck.)

### 1.2 Windows MIDI ports are exclusive

Only one process may hold a given port. If Live has a port open, nothing else
can open it — you get an access-denied style error. Before running any probe,
either close Live or untick that port in **Preferences → Link, Tempo & MIDI**.
This is the single most common reason a probe run comes back empty.

`mvave_probe.py --listen` deliberately opens what it can and skips what it
cannot, so one port held by Live does not abort a run across the other two.

### 1.3 Port names collide — disambiguate with the index

`SMC-PAD` is a substring of all three Windows port names, so tools that resolve
port names by substring will match all of them. `mvave_probe.py` refuses rather
than guessing; pass the trailing index, e.g. `"SMC-PAD 0"`.

### 1.4 A Live Control Surface takes its port away from Ctrl+M

Assigning a port to a Control Surface slot in Live **disables Track, Sync and
Remote for that port**. Any MIDI mappings you had made through Ctrl+M on that
port stop working silently — nothing is reported, the knobs just go dead.

This was found the hard way: putting the encoder script on port 1 killed a set of
existing macro mappings that had been arriving there.

**Ports 1 and 2 being identical is what makes this survivable.** A script claims
one of them, and Live's Remote stays enabled on the other, so the same physical
encoders remain available to Ctrl+M. In this repo's layout, port 1 goes to the
script and port 2 is left unassigned with Remote on.

---

## 2. Pads and buttons (port 3)

### 2.1 Note map

Sixteen pads, MIDI channel 1, **notes 1–16 in reading order** — top-left is 1,
bottom-right is 16. These are the *clip-launcher* preset's numbers; the note map
is per-preset, not a device property (see 2.4):

```
 1   2   3   4
 5   6   7   8
 9  10  11  12
13  14  15  16

buttons = 17 - 21
```

### 2.2 Press and release encoding

- Press: note-on, **velocity 127**, every time.
- Release: **note-on with velocity 0** — not a note-off (`0x80`).

The pads are not velocity-sensitive on this port. Every strike reports 127
regardless of how hard you hit it, so on port 3 the pads are buttons, which is
what a clip grid wants. (Section 5.4 explains why the velocity is fixed, and
section 6 covers the VELOCITY settings that do not change it.)

The note-on/velocity-0 idiom matters in both directions. The device uses it for
its own releases, and it is also the only thing it accepts for turning an LED
off — see section 3.3.

### 2.3 This is *not* Mackie/MCU numbering

Port 3 is the "DAW"/Mackie port, and that name tells you nothing about the
protocol on it. Real MCU would be arm 0–7, solo 8–15, mute 16–23, select 24–31,
transport 91–95. The SMC-PAD sends 1–16 and 17–21 on the preset measured here (see 2.4 — another
preset sends 101–116 and 117–121).

Assuming MCU numbering because of the port's name was one of the first wrong
calls in this project and cost real time. Measure the port; do not read its
label.

### 2.4 The five transport/function buttons

The five buttons above the grid send **notes 17–21** on port 3 *on the clip-launcher
preset*, with the same press/release encoding as the pads. The step-sequencer
preset sends 117–121 from the same five keys — see below.

The session log records that these buttons had already been configured on the
device to line up with the script's map before they were measured. It does not
establish whether 17–21 is a factory default or the result of that
configuration. **If you own one of these, measure your own buttons before
trusting 17–21.**

**These notes are per-preset, not a property of the device.** Section 5.2
establishes that byte 2 of each button record *is* the note the button transmits:
the launcher preset's five records read 20, 21, 17, 18, 19 and the sequencer
preset's read 120, 121, 117, 118, 119. The MMC/SysEx payload those records also
carry is byte-identical in both files while the notes differ, so it is vestigial
rather than what the device sends.

---

## 3. Pad LEDs

### 3.1 Velocity is a palette index, not a brightness

Send a note-on on port 3 to a pad's **LED number** and that pad lights. The LED
number is its own byte in the preset (5.2). In the editor's exports it equals
the note the pad sends, so it looks as if you light a pad by its note; this
repo's presets move it, because a pad lit at its own note can't be switched off
(5.2). The velocity byte selects a **colour from a fixed palette**. It is not brightness, and it is not a
modifier on the pad's configured colour: a pad configured pure green
(`#00ff00`) in the `.spc` still displays pink, blue and orange when driven with
the right velocities. **The palette is absolute.**

> The green pad was in `reference/Ableton.spc`, replaced by commit `32d8012`.
> The two editor exports configure block 3 **magenta** (`#f000f0`), so this
> observation cannot be re-run against `reference/` as it stands — see 5.2. The
> conclusion is unaffected: the point is that the *configured* colour, whatever
> it is, does not survive a host-driven note-on.

The hue cycles roughly every 13–14 steps, with the wash/pastel-ness varying
between cycles.

### 3.2 The measured palette

Built with `mvave_probe.py --colours`, which lights one pad at one velocity, waits
for you to type what you see, and moves on. Colour names are therefore one
observer's description by eye, not measured chromaticity — treat them as
identification, not specification.

| Velocity | Colour |
|---|---|
| 0 | off |
| 1–2 | pastel orange |
| 3 | yellow-white |
| 4 | yellow |
| 5 | green |
| 6 | turquoise |
| 7 | light blue |
| 8 | cold white-blue |
| 9 | light blue |
| 10 | white-blue |
| 11 | light pink |
| 12 | pink |
| 13 | white |
| 14 | red-pink |
| 15 | orange |
| 16 | pastel pink-orange |
| 17 | yellow |
| 18 | pastel green |
| 19 | absinth green |
| 20 | turquoise |
| 21–23 | bright blue |
| 24 | light purple |
| 32 | yellow-white |
| 40 | white |
| 48 | blue-white |
| 60 | light yellow |
| 64–112 | blue (flat — no variation across the whole range) |
| 127 | green |

Values between the sampled points above 24 were not walked exhaustively.

#### 3.2.1 The rest of the palette, surveyed 2026-10-20

On macOS, preset 1 bank A, the grid's LEDs (33-48) were lit 16 at a time
straight from a script, and each batch was photographed with a phone. From the
second batch on, the bottom row was a reference (14, 5, 21, 24) to correct for
the camera, which showed everything paler and bluer: 14 came out pink and 40
(white) lavender. **These are names from photos and one person's eye, so they
are for ordering colours, not measurements.**

| Velocity | Colour |
|---|---|
| 25 | lavender-white |
| 26 | violet (strong) |
| 27 | blue-white |
| 28 | pale pink |
| 29-30 | pinkish white |
| 31-32 | pale blue |
| 33 | white |
| 34 | pale cyan |
| 35-39 | periwinkle to blue-violet, pale (38 pale lavender) |
| 41 | pale blue |
| 42, 44 | lavender |
| 43 | pale pink-lavender |
| 45 | warm white |
| 46 | yellow |
| 47 | pale mint-aqua |
| 48 | pale sky blue |
| 49, 51 | periwinkle |
| 50 | light blue |
| 52 | lavender-violet |
| 53 | pale periwinkle |
| 54 | pale lilac |
| 55 | pale blue |
| 56 | pink (nearly as deep as 14) |
| 57 | pale pink |
| 58 | pale lilac |
| 59 | apricot |
| 60 | pale yellow-green |
| 61 | pale mint |
| 62 | sky blue (as strong as 21) |
| 63 | cornflower |
| 113 | pale lavender |
| 114-125 | the same as 53-63 and 113, in that order (117 pink, 120 yellow, 123 sky blue, 124 cornflower) |

Seen side by side, some of the 1-24 names in the table above don't hold up:
**11 is a blue-violet, not light pink**; 4 is a yellow-lime and 46 the truer
yellow; 7 looks like 20 (cyan-sky); 9 is periwinkle; 1, 17 and 18 are pale. The
table above is left as first recorded, and `KEYS_OCTAVE_COLOURS` (MIDI_Map.py)
still uses its names.

Past 24 the palette keeps cycling through the hues, paler each time, and
114-125 repeat 53-63. So the vivid colours are almost all in 1-24, plus 26,
46, 56, 59, 62 and 63. The startup intro's `INTRO_RAINBOW` is 18 of these in
hue order: 14 15 59 46 4 19 5 6 20 62 21 63 9 24 11 26 12 56. That is close
to the most a smooth rainbow can use: the rest are pale, or duplicates. Its
trans flag, `INTRO_FLAG`, is 62 (sky blue), 56 (pink) and 40 (white): the
pale pinks 28 and 57 read as white, so the pink stripe uses the deeper 56.
The flag was approved on the pads on 2026-10-20.

**What this means in practice:**

- **Everything usable lives below ~64.** The entire top half of the velocity
  range is one flat blue. Half the byte is wasted.
- **There is no saturated red.** 14 (red-pink) is the closest the palette gets.
  Any design that needs a clear red/green distinction has to accept red-pink.
- Usable, well-separated anchors: **5 green · 14 red-pink · 15 orange ·
  21 bright blue · 24 light purple · 40 white · 0 off.**

If you are picking state colours, note that **14 and 15 are adjacent in the hue
cycle**, so red-pink and orange can be hard to tell apart under stage lighting.
Swapping one of them for 21 or 24 buys much more contrast.

#### 3.2.2 Which colours tell apart side by side, 2026-10-21

To choose the step sequencer's drum colours, test grids of 16 colours were
lit straight from a script on macOS (preset 1, bank A) and one person said
which pads they could not easily tell apart. By eye again, so for choosing
colours, not measurements.

- **Easy to tell apart, all at once:** red 14, green 5, yellow 46, blue 21,
  purple 24, absinth green 19, pale pink 28, violet 26, pale yellow-green 60,
  mint-aqua 47, pastel pink-orange 16 and pastel orange 1, with orange 15 and
  white 40 beside them. Those are the sequencer's twelve drum colours and its
  playhead's two (STEPSEQ.md §1).
- **Blurred:** turquoise 6 and teal 20 with blue 21, and sky blue 62 with all
  three: the palette has one usable blue. Pink 56 with red 14; pink 12 with
  violet 26, and with pale pink 28; lime 4 with yellow 46; apricot 59 with
  orange 15. Periwinkle 9, cornflower 63, pastel green 18, yellow-white 3 and
  pale lilac 54 each looked like one of the fourteen above.
- **Also apart:** pink 12 from red 14 and from purple 24; pale pink 28 from
  white 40; absinth 19 from green 5 and lime 4; purple 24 from violet 26 and
  blue 21.

So fourteen colours can share the grid at once, the last four of them pale.
A design that needs more has to reuse one.

Three ways to more colours were tried the same day and led nowhere:

- **The MIDI channel.** Green 5 sent to each pad on its own channel, 1 to 16,
  lit all sixteen the same green. Unlike some controllers, the channel sets
  no brightness or blinking.
- **Velocity 127 as the pad's own colour.** Each pad record in a preset holds
  an RGB colour (5.2), and section 3.2's 127 was green when the pads were
  configured green, so 127 might have shown that colour. With every pad
  configured magenta (`f0 00 f0`, preset 1 as `make_presets.py` writes it),
  126 and 127 both lit nothing, on their own and beside a lit pad. Sent to
  the pads' own notes (1-16) instead of their LED numbers, since the first
  test had the two equal, 127 lit nothing either.
- **A command for the RGB or the palette.** MidiSuite 1.x's controller code
  (`CUSBConnect`) has only flash read, write, erase and checksum commands,
  and its `SmcPad` view uses two flash types: 4, the 12-byte state (3.6), and
  5, the presets. There is no LED command and no stored palette, so the
  palette is in the firmware and a pad's RGB changes only by rewriting its
  preset, which a host-lit pad doesn't show anyway.

### 3.3 Turning a pad off requires note-on velocity 0

Send note-on with velocity 0. **A real note-off (`0x80`) appears to be ignored
entirely.** Clear a grid with note-offs and every pad stays lit, with no error
and no clue as to why.

This is worth knowing before you write any LED code, because the failure mode is
"my clear function does nothing" and the obvious explanation (wrong note
numbers, wrong channel, wrong port) is the wrong one.

Convenient consequence for Ableton work: `_Framework` lights note-type buttons
through `send_value()`, which emits a note-on carrying the value as velocity. The
stock framework already speaks this dialect, including for value 0, so no
custom LED transport is needed.

`mvave_probe.py --clear` sends note-on/velocity-0 across notes 0–127 if you need
to recover a grid left lit by an aborted run.

### 3.4 The host owns the grid — measured, not assumed

Three separate things had to be true for a host to be able to drive the LEDs as a
state display, and each was tested on its own:

1. **Pads do not recolour themselves as you play.** Four rounds, roughly 78
   strikes, with no LED movement at all.
2. **A colour the host has set survives being struck.** A pad lit green stays
   green under your fingers. This is a genuinely different claim from (1) and
   needed its own test.
3. **The VELOCITY 1–4 setting does not affect colour.** Velocity 5 produced
   green on every setting tried.

Together these mean no re-assert-after-press logic is needed: set a pad's colour
once and it stays until you change it.

A caution that came out of this: **"all pads lit" is not the same as "the host
can set colours."** The first `--light` test lit the whole grid in the colour
each pad was already configured with in the `.spc`, which proves only on/off
feedback. Distinguishing that from a real colour grid needed the velocity sweep.

### 3.5 Do not blast 128 note-ons back to back

Sending note-on to all 128 notes in a tight loop **overruns the device's MIDI
input buffer** and some pads never light. In the original test this presented as
pad 16 being dead; addressed on its own, pad 16 lights fine.

If you are lighting the whole grid, pace it, or at minimum do not conclude a pad
is broken from a bulk write.

### 3.6 Pads keep their colour across a preset or PAD BANK switch

Measured 2026-10-08 on macOS. The device does not clear or redraw the pads when
you switch preset (Shift + pad) or press PAD BANK: each pad keeps the colour it
last showed. Because lighting a note the active preset does not use does nothing,
the sequencer came up showing the launcher's clip colours, and a script that only
sends changes never corrected them.

Nothing arrives on port 3 when you switch. On port 1 the device sends a 33-byte
status sysex once a second, on a fixed beat. A switch shows up in the next one,
not when the button is pressed, so it can take up to a second to see:

```
F0 00 32 0D 21 01 00 00 02 00 00 00 00 40 01 00 00 78 00 48 21 00 00 00 01 00 02 04 [b28] [b29] [b30] [b31] F7
```

| State | b28 b29 b30 b31 |
|---|---|
| preset 1, bank A (launcher) | `00 00 20 0F` |
| preset 1, bank B (mixer) | `00 10 00 0F` |
| preset 2, bank A (sequencer) | `08 00 00 0F` |
| preset 2, bank B (drums) | `08 10 60 0E` |
| preset 3, bank A (keys) | `10 00 40 0E` |

Byte 28 bit `0x08` is preset 2, bit `0x10` is preset 3 (measured 2026-10-20),
and byte 29 bit `0x10` is PAD BANK's second bank. Bytes 30-31 change too, but
not only with the state: on 2026-10-20 preset 1 bank A read `00 00 00 0F` and
preset 2 bank A `08 00 60 0E`, so they are not a pure function of b28-b29.
A preset switch also sends the whole preset as 28 sysex messages of 1173
bytes and one of 88 (`... 21 04 ...`), over ~150 ms. The status keeps coming
with MidiSuite closed, so nothing on the computer is asking for it.

**Unexplained, 2026-10-20 (later):** in a capture with Live and MidiSuite
quitting partway, the one-second status continued for ~5 s after Live's polling
stopped, then everything on all three ports stopped. Preset switches, PAD BANK
and a velocity change after that produced nothing, not even the dump. Either
the beat depends on something the host does, or the controller stopped talking
(a USB drop?). Not repeated. Later the same day, with Live running the
once-a-second poll and the controller idle for 15 s, exactly one status a
second arrived, spaced ~1.007 s apart and drifting against the wall clock like
Live's display ticks. So there was no separate beat from the device then.

**What the device sends by itself waits for the beat.** Measured 2026-10-20
over three preset switches and two PAD BANK presses: the changed status arrives
on the next one-second beat, and the preset dump starts 0-5 ms *after* that
status, never at the moment of the switch. PAD BANK sends no dump at all.
Nothing on any of the three ports arrives earlier: 0-1 s of lag, about 0.5 s on
average.

**But the device answers when asked.** The status is a reply to a state read
from M-Vave's editor protocol, read out of MidiSuite 1.x (`CUSBConnect`,
`CMIDITranfer`; its `SmcPad::timerEvent` sends this read on a timer):

- On the wire: `F0`, the packet's 8-bit bytes packed 7 bits at a time, low
  bits first, then `F7`. Every message starts `00 32 0D` because that unpacks
  to the packet head `00 59`. (So `00 32 0D` is not a manufacturer ID.)
- A packet is the head `00 59`, a command (`23` = flash read, in both the
  request and the reply), a 3-byte little-endian length, the payload, and a
  checksum: the byte sum of the payload, inverted.
- The state read is type `04`, address 0, 12 bytes. Sent as
  `F0 00 32 0D 41 00 00 00 02 00 00 00 00 40 01 00 00 6F 01 F7` on
  `SMC-PAD-Private` only (the other two ports don't answer).
- The reply is the 33-byte status above. Unpacked: bytes 0-5 are
  `00 59 23 14 00 00`, 6-13 echo the type, address and count, 14-25 are the
  12 state bytes, 26 the checksum. **Byte 24 is the preset (0-2 for presets
  1-3; 3 for preset 4, reached with Shift + pad 4: seen in Live 2026-10-20, when
  the script acting on 3 ran on preset 4), byte 25 the
  PAD BANK bank (0-1). Byte 22 is the VELOCITY setting (0-3 for Shift + Pad
  9-12)** (measured 2026-10-20: it stepped 00, 01, 02, 03 as the four were
  selected, the moment each was pressed). That is why it read `01` on 2026-10-08
  and `02` earlier on 2026-10-20, and why the raw b30-b31 changed.

Measured 2026-10-20: replies came 0.1-1.4 ms after the request, and polling
every 50 ms saw all five switches (three presets, two PAD BANK) at moments
unrelated to the beat. The reply shows a switch the moment it happens.

`MVave_SMC_KNOBS` is the script on port 1, so it watches this message and sends
the read, which needs its Output set to `SMC-PAD-Private`. Every request and
reply flashes Live's MIDI indicators, so since 2026-10-20 it asks every ~0.2 s
(`POLL_TICKS` = 2 display ticks; about 0.35 KB/s on the wire), plus at once when a pad or knob sends something the current
layout doesn't have. Every layout has its own notes and CCs
(`LAYOUTS_BY_NOTE` / `LAYOUTS_BY_CC`), so the first touch after a switch gives
it away; SHIFT and PAD BANK send nothing (6.1), so nothing earlier can. A switch
repaints the moment you touch a pad or knob, or within ~0.2 s if you don't. For
~4 s after a switch it asks every tick (`SWITCH_FAST_TICKS`), so quick PAD BANK
flips show at once.
Only the transport and arrow buttons (notes 17–21) can't tell presets 1, 3 and 4 apart. When the preset or bank changes, it schedules
`refresh_state()` on `MVave_SMC_PAD` and `MVave_SMC_STEPSEQ`, a few ticks apart,
and tells `MVave_SMC_PAD` the preset, which switches preset 4's Chord devices.
The script that owns the new layout goes last. It also stops these messages
being logged as "unknown sysex". Without the output there is no read, so it
depends on the controller sending the status unprompted, which the captures
above disagree about.

**Writing the state.** Captured 2026-10-20 with MIDI Monitor's spy on
`SMC-PAD-Private` while MidiSuite changed the preset and PAD BANK. MidiSuite
writes one byte of the same type-4 block with command `22` (flash write).
The payload is type `04`, a 4-byte address, a 3-byte count of 1, then the value:

| Change | Address | Sent |
|---|---|---|
| preset 2 | `0A` = 1 | `F0 00 32 09 49 00 00 00 02 0A 00 00 00 10 00 00 00 01 5E 03 F7` |
| preset 1 | `0A` = 0 | `F0 00 32 09 49 00 00 00 02 0A 00 00 00 10 00 00 00 00 60 03 F7` |
| PAD BANK on (B) | `0B` = 1 | `F0 00 32 09 49 00 00 00 02 0B 00 00 00 10 00 00 00 01 5C 03 F7` |
| PAD BANK off (A) | `0B` = 0 | `F0 00 32 09 49 00 00 00 02 0B 00 00 00 10 00 00 00 00 5E 03 F7` |

Address `0A` is the reply's byte 24 and `0B` its byte 25, so byte 22 (the
VELOCITY setting) would be address `08`. That one has not been written. The
device answers each write within ~1.3 ms with an OK, `F0 00 32 01 08 00 00 00
00 7F 01 F7` (unpacked: command `00`, one payload byte `00`), and switches at
once. The same bytes sent from a script did the same (2026-10-20). A Program
Change on any port or channel switches nothing.

`MVave_SMC_KNOBS` uses this to put the controller on preset 1, PAD BANK off,
when Live loads (`STARTUP_PRESET` and `STARTUP_BANK`, `None` to turn it off).
It writes only a byte the first reply shows wrong, one write per reply, at most
four in all. The first reply after that tells `MVave_SMC_PAD` whether to play
its startup intro (a waving trans flag or a rainbow, then a PAD1 flash on
LEDs 33-48). The intro only
shows while preset 1, bank A is up, so it is skipped on any other layout.

---

## 4. Encoders

### 4.1 Layout

Eight physical encoders, arriving on ports 1 and 2 only (never port 3). A
**KNOB BANK** button switches all eight at once between two banks, each bank with
its own CC set.

Measured with `mvave_probe.py --knobs`, which walks one encoder at a time and
reports after each, so a silent knob or a CC clash shows up while your hand is
still on it.

**Current — measured 2026-08-31. Every encoder is relative.**

| Encoder | Bank 1 CC | Bank 2 CC (launcher) | Bank 2 CC (sequencer) |
|---|---|---|---|
| 1 | 7 | 17 | 15 |
| 2 | 8 | 18 | 16 |
| 3 | 5 | 13 | 13 |
| 4 | 6 | 14 | 14 |
| 5 | 3 | 11 | 11 |
| 6 | 4 | 12 | 12 |
| 7 | 1 | 9 | 9 |
| 8 | 2 | 10 | 10 |

Bank 2's bottom pair is the only thing that differs between the two presets: the
launcher spends it on session navigation (CC 17/18), the sequencer on macros 15
and 16. Every CC above is confirmed against `reference/launchpad.spc` and `reference/sequencer.spc`, whose sixteen
encoder records carry the CC in byte 4 and `63 65` in bytes 5–6 — the relative
centre-64 encoding, on all sixteen.

**Preset 3 (`preset3-keys.spc`) has its own CCs:** relative like the rest, but
CC 21–36 (bank 1, encoders 1–8: 27, 28, 25, 26, 23, 24, 21, 22; bank 2 the same
+ 8), so `MVave_SMC_KNOBS` can tell them apart and play the selected device's
parameter banks with them (README, keyboard preset). Before 2026-10-20 they were
absolute standard synth CCs (74, 71…) passed to the track. That did nothing on
Live's built-in instruments, which ignore CCs. The first build of it also kept
type 3 and only changed bytes 5–6 to `00 7f`, guessing they were a range;
measured, every knob then sent **0 one way and 127 the other**, because under
type 3 those bytes are the values sent per left/right click. With type 0
(section 5) the same knobs swept smoothly through 0–127.

**None of this is a property of the hardware.** The same unit measured 2026-08-03
read bank 1 as CC 1–8 ascending and bank 2 as CC 44, 45, 42, 43, 40, 41, 38, 39 —
with only the last two relative and everything else absolute. Both banks were
renumbered and every encoder switched to relative in the M-Vave editor between the
two readings. Treat the table above as *this unit, on that date*.

### 4.2 One bank's CC numbers will not follow the printed encoder numbers

In the 2026-08-03 measurement exactly one bank ran ascending with the printed
labels while the other descended in pairs. After the renumbering, **both** banks
descend in pairs — encoders 1 and 2 carry the highest pair and encoder 7 the
lowest CC overall, while within each pair the CCs ascend left to right:

```
bank 1, encoders 1..8  ->  CC  7,  8,  5,  6,  3,  4,  1,  2
bank 2, encoders 1..8  ->  CC 17, 18, 13, 14, 11, 12,  9, 10   (launcher preset)
bank 2, encoders 1..8  ->  CC 15, 16, 13, 14, 11, 12,  9, 10   (sequencer preset)
```

The consequence is the same whichever bank it lands on: wire a row of controls in
numeric CC order and they scatter across the panel in a pattern that looks random
under your hands. **Map in encoder order, and re-measure after any editor change.**
This is configuration rather than hardware, and it has already moved once.

### 4.3 A knob that seems dead is usually on the other bank

KNOB BANK switches all eight encoders together. Mappings made on bank 1 are
completely inert while bank 2 is selected, and vice versa. Check the bank before
debugging anything about an encoder.

### 4.4 Relative encoding

The encoders ship **absolute**: the firmware accumulates a position internally and
reports it, confirmed by walking a knob and watching the value climb (6 → 31).

Relative is a per-encoder setting made in the M-Vave editor, not a fixed property
of any encoder. As of 2026-08-31 **all sixteen assignments on this unit are
relative**; an earlier reading had only two. The encoding is binary-offset around
a centre of 64:

| Value | Meaning |
|---|---|
| 63 | one step counter-clockwise (−1) |
| 64 | centre / no movement |
| 65 | one step clockwise (+1) |

**Why the mode matters.** An absolute CC carries a *value*, which maps cleanly
onto a continuous range like volume or filter cutoff, where nothing else moves the
target. A relative CC carries a *step*. If the thing you are driving is an integer
index that other inputs also move — Ableton's session box, moved by the arrow keys
and the mouse as well — an absolute encoder's internal counter desyncs immediately
and the target teleports the next time you touch the knob. A relative encoder has
no position to desync.

**If you are writing a `_Framework` script, the mode decides your whole approach.**
`SliderElement` reads absolute only; feed it 63/65 and the target parks near half
and jitters, which is a *silent* failure rather than an obvious one.
`EncoderElement` plus a `Live.MidiMap.MapMode` handles relative. The script in this
repo does neither — it decodes 63/65 itself in `receive_midi` and writes
`device.parameters[n]` directly, because fourteen simultaneous macros do not fit
`DeviceComponent`'s one-bank-of-eight parameter model, and hand-decoding avoids
depending on a `MapMode` constant whose name varies by host version.

---

## 5. The `.spc` configuration file

> **One file is one preset.** Confirmed 2026-09-01 by decoding the two exported
> presets in `reference/` (`launchpad.spc`, `sequencer.spc`) side by side: both are 3539 bytes and
> **41 bytes differ** — five button notes plus two of their mirrored tails, two
> encoder CCs, and sixteen pad notes plus all sixteen of their tails
> (7 + 2 + 32 = 41). The tail mirroring is described in 5.2; nothing else
> moves. A preset holds 5 buttons, 2 knob banks of 8 encoders, and 128 pad
> records, which read naturally as 8 blocks of 16. **PAD BANK uses only two of
> those blocks** (measured 2026-10-07, see 5.2). **Shift+Pad** loads a
> different file.
>
> Both files agree with every **note** constant the scripts use — `CLIPNOTEMAP`
> 1–16, `PLAY`/`STOP`/`REC` 17–19, `TRACKLEFT`/`RIGHT` 20–21, `PAD_NOTES`
> 101–116 and `BTN_*` 117–121 — so they double as a regression fixture for those.
> The sequencer's `CC_LANE`–`CC_SPARE` (20–23, channel 16) are deliberately
> unbacked: they describe controls the presets do not assign, and a 6-byte
> encoder record has no channel field at all.
>
> **On reading `git`'s rename detection.** Git paired the older single dump with
> `launchpad.spc` and reported it as a rename — but rename detection matches on
> *similarity*, not identity, and `Bin 3539 -> 3539` says nothing about whether
> the content moved. It had moved: 108 bytes, including the bank-2 encoder
> renumbering and a whole pad bank reverting to factory. Diff the bytes; do not
> read `R` as "unchanged".
>
> That diff also explains an earlier confusion. The sequencer's 101–116 layout
> once lived in **pad bank 8 of the launcher preset**, so both note ranges came
> out of one preset and were reachable by PAD BANK rather than Shift+Pad.
> Splitting them into two preset files is what made them independent.

A `.spc` file is what the M-Vave editor writes out, one per preset. Binary, **no magic bytes, no
header, no version field**. It is three fixed-size record sections back to back.

### 5.1 How the segmentation was confirmed

The record sizes multiply out to exactly the file length:

```
5 x 23  +  16 x 6  +  128 x 26  =  115 + 96 + 3328  =  3539 bytes
```

3539 is the file size. Three independently guessed record sizes summing exactly
to the total, with no header and no slack, is strong enough evidence to work
from. **This is the technique worth stealing for the next undocumented binary
format**: guess record boundaries from repeating byte patterns, then check
whether the arithmetic closes.

### 5.2 Section layout

| Offset | Records | Size | Contents |
|---|---|---|---|
| `@0` | 5 | 23 B | the five buttons |
| `@115` | 16 | 6 B | continuous controls (encoders) |
| `@211` | 128 | 26 B | pads — 8 blocks x 16, of which PAD BANK uses two |

**Section 1 — the five buttons, `@0`, 5 x 23 B**

```
[type=05] [00] [note] [00] [7f] [len] [sysex, 16 B] [tail]
```

**Byte 2 is the note the button transmits.** Corrected 2026-09-01 by diffing two
exported presets whose buttons measure 17–21 and 117–121: those five bytes differ
by +100, along with the mirrored `tail` byte of the two records that carry one —
seven bytes in this section, at 1-based offsets 3, 26, 49, 69, 72, 95 and 115.

This section previously read the records as SysEx buttons carrying MMC commands
(Deferred Play, Fast Forward, Rewind, Stop, Play). The MMC payload is really
there — `f0 7f 7f 06 0n f7` — but it is **byte-identical in both presets** while
the notes differ, so it is not what the device sends. Treat it as vestigial until
something demonstrates otherwise.

The `tail` byte mirrors the note on some records and is `0xff` on others. In
both shipped sources it is the note on play and record and `0xff` on stop and
the two arrows. **Working hypothesis (2026-10-20): it is the button's LED
number**, the way byte 8 is a pad's, with `0xff` meaning "not host-lit" — the
sequencer lit stop in its overview and the arrows when a page was available,
and those stayed dark. `tools/make_presets.py` now writes each preset-2 button's
own note there (`light_buttons`). Not yet confirmed: re-import preset 2 and see
whether stop lights in the overview.

**Section 2 — the encoders, `@115`, 16 x 6 B — two knob banks of 8**

```
[type] [02] [00] [cc] [data1] [data2]
```

Read from MidiSuite's `SmcPad::setKnobData`, which loads the six bytes into six
widgets in this order, and `SmcPad::knobTypeChange` (2026-10-20). **Type**
(byte 1) is a combo box: 0 = CC, with data1/data2 labelled *Min*/*Max*
(absolute); 3 = CC, with data1/data2 relabelled *Left*/*Right*, the values sent
per counter-clockwise/clockwise click (relative, `3f 41` = 63/65 in every
shipped record). Types 1 and 2 disable the CC field. Bytes 2 and 3 load into the
editor's other two fields (speed and channel, by the widget names, though which
is which wasn't traced); every record has `02 00` there.

Sixteen records for eight physical encoders — two banks of eight. In
`launchpad.spc` the CC bytes read `7, 8, 5, 6, 3, 4, 1, 2` then
`17, 18, 13, 14, 11, 12, 9, 10`; `sequencer.spc` differs only in the bottom pair
of bank 2, `15, 16`.

> **Two records measured, the rest inferred.** Nothing in a six-byte record names
> an encoder, so the record → encoder correspondence cannot be read from one file.
> But the two editor exports in `reference/` *are* the single-variable test, already run:
> they differ in exactly two encoder bytes — the CC fields of **records 9 and 10**,
> 1-based file offsets 167 and 173, where `17→15` and `18→16`. Section 4.1
> measured those same two CCs as bank 2's encoders 1 and 2, so records 9 and 10
> **are** encoders 1 and 2, read off the bytes rather than assumed. That also
> refutes the ordering this section once proposed — `(enc 7, 8, 5, 6, 3, 4, 1, 2)`
> — under which encoders 1 and 2 would sit at records 15 and 16, whose bytes are
> identical in both files.
>
> The other six positions in each bank remain inferred from 4.1's table, on the
> assumption that one ordering governs the whole section. Changing one more
> encoder's CC and re-exporting would close them the same way.

**Section 3 — pads, `@211`, 128 x 26 B**

```
[flag] [type] [note] [chan?] [vel] [r] [g] [b] [led] [zeros...]
```

Three field notes:

- **Byte 8 is the pad's LED number**: the number the host sends a note-on to
  in order to light that pad (measured 2026-10-07). It is `0xff` on plain-MIDI
  records, which the host can't light. In both editor exports it mirrors
  `note` on every record whose `flag` is `0x04` (128/128 in both files), which
  is why it was first read as a mirrored tail.
- **A pad whose LED number equals its own note shows white at velocity 0**, so
  it can never be switched off (measured 2026-10-07). This repo's presets
  therefore move every lit pad's LED number off its note. `tools/make_presets.py`
  and the scripts' `MIDI_Map.py` files must agree on these:

  | Layout | Notes | LED numbers |
  |---|---|---|
  | preset 1, clips | 1–16 | 33–48 |
  | preset 1, mixer | 49–64 | 85–100 |
  | preset 2, steps | 101–116 | 69–84 |
  | preset 3, keyboard | 85–100 | 1–16 |
  | preset 3, key and scale | 22–37 | 49–64 |
  | preset 4, chords | 65–80 | 101–116 |
  | preset 4, key and scale | 38–48, 81–84, 122 | 22–32, 65–68, 123 |

- **`chan?` is a Hypothesis, not an observation.** Byte 3 is `0x00` in all
  256 records, so these files cannot distinguish "channel, 0-based" from
  "unused padding"; the name comes from section 2.1's measured channel 1.

128 records read as **8 blocks of 16 pads**. The note ranges below are those
of the editor exports:

| Block | Records | Notes | Used by |
|---|---|---|---|
| 1 | 0–15 | 4–19 | — |
| 2 | 16–31 | 20–35 | — |
| 3 | 32–47 | **1–16** | **PAD BANK off** (bank A) |
| 4 | 48–63 | 52–67 | **PAD BANK on** (bank B) |
| 5 | 64–79 | 68–83 | — |
| 6 | 80–95 | 84–99 | — |
| 7 | 96–111 | 100–115 | — |
| 8 | 112–127 | 52–67 | unclear: same notes as block 4 |

**PAD BANK has two positions, not eight** (measured 2026-10-07). It flips
between block 3 and block 4. Blocks 4 and 8 hold the same factory notes and
one measurement can't tell them apart, so `tools/make_presets.py` writes the
second layout to both. Shift+Pad loads a different *file*, as the note at the
head of this section says.

This section once assumed eight PAD BANK positions, one per block. A first
measurement also put bank A at records 29–44. Presets built that way played
every pad's neighbour three along once imported, with the last three pads stuck
white. The sources were moved to 32–47 on 2026-10-08, where M-Vave's own export
keeps it. The old 29–44 sources are no longer kept.

In the two editor exports, block 3's pads are configured **`#f000f0` magenta**
(bytes 5–7 = `f0 00 f0` on all 16 records of both files), with notes 1–16 in
`launchpad.spc` and 101–116 in `sequencer.spc`.

> **Historical note.** Section 3.1's argument uses a pad configured `#00ff00`
> pure green that still displayed pink. That observation was made on
> `reference/Ableton.spc`, the single dump this repo carried before commit
> `32d8012` replaced it with the two presets above. No shipped file reproduces
> it — checking 3.1 against `reference/` today finds the pad configured magenta.
> The editor's own palette maxes at `0xf0` (bank 5 green is `00 f0 00`), so
> `#00ff00` was a hand-typed value.

### 5.3 The device numbers its pads bottom-up

**PAD1 is bottom-left. PAD13 is top-left.** Read block 3's records in that
bottom-up order and they yield notes 1–16 in *reading* order from the top-left —
which is precisely what the probe measured on port 3, inversion and all,
sixteen out of sixteen.

This matters whenever you edit a bank in the M-Vave editor: the pad the editor
calls PAD1 is not the pad in the top-left corner.

### 5.4 Why the pads always transmit velocity 127

Every record in block 3 carries `vel = 0x7f`. It is a **fixed velocity byte, not a
curve**, which is why every strike reports 127 and why the VELOCITY settings do
nothing to it (section 6.2).

### 5.5 Two traps in reading this format

**A `0x00` in the `type` byte does not mean "pad disabled."** In the pre-`32d8012`
`reference/Ableton.spc`, two block-3 records carried `0x00` there where the rest
had `0x09` (0-based offsets 1278 and 1356 — PAD10 → note 6 and PAD13 → note 1).
That was read as "these two pads transmit nothing" and produced a confident,
wrong prediction. Both fired normally. Whatever the byte means, it is not an
enable flag — do not infer silence from it.

**In the two shipped presets the field has no variance at all: `0x09` on all 128
records of both files.** So the trap is real but no longer inspectable here; it
survives only in git history at the offsets above.

**The `.spc` and a Remote Script must be reasoned about as a pair.** An apparent
collision between the script's `PLAY=17 STOP=18 REC=19` and the pad note range
was called a bug; it was not, because the device had been configured to match the
map. Reading either artifact in isolation produces nonsense.

### 5.6 The flag byte

Block 3's `flag` byte is `0x04`. All seven factory blocks have `0x00`.

> **Superseded 2026-08-31.** This section previously proposed the flag byte as an
> **output-port selector**, on two consistent observations and no experiment. That
> was one observation dressed as a mechanism, and it explained only the port.
>
> The better model, from the device's owner: **the port follows the assignment
> TYPE.** MCP/Mackie assignments come out of port 3; plain MIDI assignments come
> out of ports 1 and 2. That accounts for all four measured properties at once:
>
> | Type | Port | Velocity | LEDs |
> |---|---|---|---|
> | MCP / Mackie | 3 | fixed 127 | **yes** |
> | plain MIDI note | 1 & 2 | **sensitive** | no |
>
> So the LED/velocity trade in section 3 is not a device quirk — it is the two
> protocols being what they are. MCU is a control protocol with on/off buttons and
> host-driven lights; MIDI notes are performance data with velocity and no
> feedback path. The `0x04` flag is most likely just the MCP marker.
>
> **Still untested, and the experiment is designed:** change *one* pad's type from
> MCP to plain MIDI, keep its note number identical, and capture. If that note
> alone moves to ports 1/2, becomes velocity-sensitive and stops lighting while
> its fifteen neighbours do not, the type is the mechanism. Until that is run,
> treat this as the leading explanation rather than a measured fact.

---

### 5.7 Note repeat bypasses the pad's port

Measured 2026-10-17 on preset 3, PAD1 (MCP, note 85, port 3), with all three
ports watched. A normal tap arrives on port 3 as note 85, channel 1, velocity
127, as configured. With note repeat on, holding the pad sends **nothing on
port 3**: the firmware sends the repeats on **ports 1 and 2** as plain MIDI,
**channel 10**, the pad's own note (85), at about 8 per second, note-on velocity
10–15 and note-off velocity 64. So repeats ignore the pad's type, port and
channel, and anything a host script does to port 3's notes. This repo turns
Track off on port 2 and has `MVave_SMC_KNOBS` translate them (README, "Plain
MIDI goes through MVave_SMC_KNOBS"). Whether the VELOCITY 1–4 settings change
the repeat velocity was not measured.

## 6. SHIFT and the Shift+Pad settings

### 6.1 SHIFT transmits nothing

Confirmed by listening on all three ports simultaneously. The SHIFT button is
consumed entirely by the firmware for its Shift+Pad combinations (preset select,
velocity, transpose, octave).

It has no LED the host can reach either: SHIFT has no record in the preset
file (section 5.2 lists five buttons, and SHIFT is not one of them), so it has no
LED number. The startup intro flashes PAD1 alone for that reason. Not
measured: whether some fixed note lights it. A paced 0-127 sweep on port 3
while you watch the key would settle it.

**There is no spare modifier button on this device.** Any host-side "hold X to
change what the other controls do" scheme has to spend one of the five
transport/function buttons on it.

### 6.2 VELOCITY 1–4 (Shift + Pad 9–12)

Undocumented — the manual names the setting and says nothing else. Measured with
`mvave_probe.py --curves`, which walks all four settings while watching two ports
at once.

**What was established:**

- All four settings transmit **velocity 127 on port 3**, every strike, no
  variation. The fixed `0x7f` velocity byte in the pad bank (section 5.4)
  overrides whatever the setting would otherwise do.
- None of the four settings changes LED colour.

**Readable by the host (2026-10-20).** The setting is byte 22 of the state
read's reply (section 3.6), 0-3 for VELOCITY 1-4, updated the moment it is
selected. `MVave_SMC_KNOBS` passes each change to `MVave_SMC_STEPSEQ`, which
writes new steps at 40, 70, 100 or 127 (STEPSEQ.md section 9).

On VELOCITY 4, the plain-MIDI drum pads (preset 2, bank B, ports 1 and 2,
channel 10) sent velocity 127 on every strike, soft or hard, so 4 is
probably a fixed full velocity. VELOCITY 1-3 have not been measured on those
pads.

**What was not established: what the settings actually do.** A velocity curve
would shape the *playing* port's output, and port 1 transmitted nothing at all
during the test. Measuring these properly means first working out why port 1 is
silent in this configuration — probably by switching to a different pad preset
bank, which ties back to the flag-byte hypothesis in 5.6.

For clip-launching purposes the setting is simply irrelevant.

---

## 7. Factory DAW mode, and why it cannot launch clips

In its factory DAW (Mackie) mode, the SMC-PAD spends the entire 4x4 grid on mixer
duties:

| Pads | Function |
|---|---|
| 1–4 | select track |
| 5–8 | arm |
| 9–12 | solo |
| 13–16 | mute |

with **PAD BANK** toggling between tracks 1–4 and tracks 5–8.

Mackie Control is a mixer and transport protocol. **It has no concept of a clip
grid at all**, so no amount of configuration on the device or in Live's stock
`MackieControl` script will get a pad to launch a clip. The limitation is in the
protocol, not the hardware.

What makes a clip launcher possible anyway: the firmware keeps sending pad notes
and keeps lighting pads from incoming MIDI regardless of what the host does with
them. Put a custom Remote Script in that Control Surface slot instead of
`MackieControl` and the same note stream means whatever you decide it means. The
device is unchanged and the change is fully reversible — switch the Control
Surface dropdown back and the factory behaviour returns.

---

## 8. Reproducing any of this

`tools/mvave_probe.py` runs on the machine the controller is plugged into. It
needs `mido` and `python-rtmidi` (see `tools/requirements-midi.txt`); on Windows,
`tools/run_probe.bat` builds a venv and runs it. It never touches the DAW.
Full usage is in [PROBE.md](PROBE.md); the modes exist as follows.

| Mode | What it does |
|---|---|
| `--list` | enumerate MIDI in/out ports |
| `--listen --port MIDIIN3` | log everything the device sends, with a per-control summary |
| `--light --port MIDIOUT3` | blunt test — light everything at once |
| `--sweep` | narrow down which notes address pads, a block at a time |
| `--colours --note 1` | step a pad through velocities, typing the colour you see; prints a grouped velocity→colour table |
| `--clear` | extinguish every pad |
| `--curves --port "SMC-PAD 0" --port2 "MIDIIN3"` | walk VELOCITY 1–4, capturing transmitted velocities on two ports at once |
| `--knobs --port "SMC-PAD 0"` | map every encoder to its CC, one knob at a time, reporting mode and flagging silent knobs and CC clashes |

Both `--colours` and `--knobs` are interactive and checkpoint every single step,
which is deliberate. A timed sweep asks a human to remember a sequence of colours
or to turn sixteen knobs in the right order and only reveals a mistake at the end.
The first attempt at the encoder map was one flat 180-second `--listen` run; it
came back 14 of 16, with two CCs missing and one wrongly classified, and no way to
tell which step had gone wrong. Step-by-step, it produced a clean 16 of 16.

---

## 9. Known unknowns

Collected so nobody re-derives them as facts:

1. **What VELOCITY 1–3 do** to the velocity-sensitive drum pads. VELOCITY 4
   sends a fixed 127 there; the setting itself is readable (6.2).
2. **Whether the assignment type is what sets port, velocity and lighting
   together.** The leading explanation, with the experiment designed and not
   run (5.6).
3. **Whether notes 17–21 for the five buttons are a factory default** or the
   result of prior configuration on the device (2.4).
4. **The full velocity→colour mapping above 24.** Sampled, not walked
   exhaustively (3.2).
5. **The meaning of the pad record's `type` byte** (`0x09` vs `0x00`). Known not
   to be an enable flag; nothing more (5.5).
6. **Any of this on Linux.** Not tested. On macOS, the scripts and the
   later measurements run; the Windows-era measurements were not repeated there.
7. **Whether a button record's last byte is its LED number**, and whether the
   button LEDs take the palette or are only on/off (5.2).
8. **Whether the controller sends its status unprompted.** One capture saw a
   once-a-second status with nothing asking; a later one saw none (3.6).
