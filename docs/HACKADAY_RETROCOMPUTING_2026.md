# 2026 Hackaday Retrocomputing Challenge Plan

Status: **Deferred / documented only**  
Target category: **Modern Retro**  
Submission deadline: **October 27, 2026 at 10:00 PM PDT**  
Resume work: late September or early October 2026  
Contest: https://hackaday.io/contest/206399-retrocomputing-contest

## Scope lock

The current RP2040 application is already a valid, working contest build. Do not
start a rewrite or add major training features for this challenge.

The contest pass is limited to:

1. A small retro-identity UI pass.
2. Optional Pico 2 hardware evaluation behind a decision gate.
3. Device validation, photography, a short demo video, and the Hackaday.io
   write-up.

The stock RP2040 build remains the submission baseline. Its constraints are an
asset to the story: a complete offline training computer, including coaching,
history, dashboards, persistence, and recovery, running in 264 KB of SRAM.

## Contest positioning

### Recommended title

**PicoCalc RP Trainer: An Offline Gym Computer**

### One-line description

A keyboard-driven strength-training computer that turns the RP2040-powered
PicoCalc into a self-contained, 1980s-style coaching terminal.

### Core story

This is not merely a fitness application displayed on retro-looking hardware.
It asks whether the focused personal-computer experience of the 1980s is better
for a modern task than another phone app.

The PicoCalc provides the physical keyboard, compact display, removable storage,
limited memory, instant ownership of local data, and deliberate single-purpose
interaction. RP Trainer uses those qualities to make a durable gym instrument:
no account, network, subscription, notifications, or cloud dependency.

### Category fit

Primary: **Modern Retro** — modern RP2040/RP2350 electronics recreating the
focused interface and ownership model of an earlier personal computer.

Secondary themes:

- New software designed around severe embedded constraints.
- A portable terminal used as practical lab equipment.
- Local-first data and user-serviceable hardware.
- Information-dense text interfaces used because they are efficient, not only
  decorative.

Avoid leading with “fitness app.” Lead with the retrocomputer design experiment
and demonstrate the real training use case.

## Retro UI backlog

These changes are ordered by contest value divided by implementation risk.

### P0 — skippable boot/POST sequence

Add a brief boot sequence, ideally less than two seconds and skippable by key:

```text
RP TRAINING COMPUTER / MODEL 2040
CHECKING SD...........OK
LOADING ATHLETE.......OK
COACH MEMORY..........OK
READY.
```

Acceptance criteria:

- Does not materially slow normal startup.
- Reports a real failure when practical; avoid purely decorative false checks.
- Fits the 53x40 terminal without scrolling or wrapping.
- Can identify RP2040 versus RP2350 if both are supported.

### P0 — phosphor theme set

Retain the current lab-equipment theme and add:

- Amber terminal.
- Green phosphor.
- Monochrome/high-contrast fallback.

Acceptance criteria:

- Themes use the existing terminal/theme architecture.
- All states remain readable under gym lighting.
- User selection persists.
- No simulated scanlines or effects that reduce legibility.

### P0 — static ASCII exercise art

Add small static figures for the major movement families:

- Squat.
- Press/bench.
- Hinge.
- Pull/row.
- Generic fallback.

Reuse art by exercise mode/family rather than drawing every exercise.

Acceptance criteria:

- Approximately 12x10 characters or smaller.
- Fits the live workout screen at 53x40.
- No full-screen periodic redraw.
- No loss of workout information or input responsiveness.
- Static art ships first; animation remains optional.

### P1 — retro storage language

Use restrained computer terminology where it clarifies the mental model:

- Mesocycle/program: **PROGRAM**
- Athlete data: **ATHLETE ARCHIVE**
- Loading transition: **LOADING PROGRAM 03...**

Do not rename established training concepts when it would confuse users. This is
presentation polish, not a wholesale vocabulary change.

### P2 — minimal sound design

Optional, only if the active PicoCalc firmware exposes audio cleanly:

- One startup chirp.
- Short error/confirmation tones.
- PR celebration sound.
- Persistent mute setting.

Sound is not a contest blocker and must not trigger a firmware rewrite.

### Explicitly out of scope

- Fake CRT scanlines.
- Long typing animations.
- Animated exercise art unless static art is already stable.
- Networking, accounts, or cloud services.
- New training modes.
- A new UI framework.
- Full firmware replacement solely for contest aesthetics.

## Pico 2 decision gate

### Baseline

Keep the working Pico/RP2040 configuration as the primary supported and
photographed build.

### Candidate upgrade

Evaluate a headered **Raspberry Pi Pico 2** first. Prefer the non-wireless Pico 2
for the contest build unless a real synchronization experiment justifies Pico 2
W.

Nominal comparison:

| Core | SRAM | Flash | Contest role |
| --- | ---: | ---: | --- |
| Pico / RP2040 | 264 KB | 2 MB | Proven baseline and constraint story |
| Pico 2 / RP2350 | 520 KB | 4 MB | Optional enhanced edition |
| Pico 2 W / RP2350 | 520 KB | 4 MB | Future synchronization work |

The upgrade can provide more history in memory, more artwork, larger caches, and
less aggressive compaction. It is not required to complete the submission.

### Upgrade only if all gates pass

- A PicoCalc-compatible RP2350 MicroPython firmware is available and stable.
- Display, keyboard, SD access, boot flow, and terminal behavior are verified.
- Existing athlete data loads without migration loss.
- A full workout can be started, paused, resumed, and completed.
- Memory behavior is measured rather than assumed.
- The RP2040 payload and instructions remain preserved and reproducible.

If any gate fails, revert to RP2040 and document the investigation as a project
log. Do not let the hardware upgrade delay contest media or submission.

### Useful comparison log

If Pico 2 succeeds, publish a Hackaday project log comparing:

- Free heap after boot and after loading the demo athlete.
- Screen responsiveness.
- Maximum useful live-history window.
- Build/firmware differences.
- Which RP2040 optimizations remain valuable.

The strongest story may be that one codebase spans both generations: RP2040
demonstrates deliberate constraint while RP2350 enables the enhanced interface.

## Submission package

### Required media

- One hero photo of the complete PicoCalc in a gym or beside weights, with the
  dashboard readable.
- Close photos of workout logging, trends/recovery, and session analysis.
- A 45–90 second continuous demo:
  1. Power or wake the PicoCalc.
  2. Launch RP Trainer.
  3. Start a workout.
  4. Log a set.
  5. Show the resulting coaching recommendation.
- Optional screen captures for details that are difficult to photograph.

### Recommended Hackaday.io structure

1. **Why a pocket computer belongs in the gym**
2. **The retrocomputer design constraints**
3. **How the coaching engine works**
4. **Making history survive limited RAM and power loss**
5. **Running natively on the PicoCalc**
6. **RP2040 versus RP2350**, if completed
7. **Build/install instructions and source**

### Recommended project logs

1. **Shrinking a desktop training system onto the RP2040**
2. **Making workout data survive dead batteries and power loss**
3. **Designing a 53x40 gym interface**
4. **What changed on Pico 2**, only if tested

### Final validation

- Fresh SD-card installation following only the published instructions.
- Launch from a cold boot.
- Complete one representative workout.
- Power-interrupt during a paused workout and verify recovery.
- Load the demo athlete and inspect dashboards.
- Confirm CSV export, backups, and unit settings.
- Run the smoke test suite.
- Check public links, license, captions, and image readability.
- Enter the project in the contest before October 27, 2026 at 10:00 PM PDT.

## Readiness assessment

At the time this plan was written:

- Core build: complete and running on the stock PicoCalc.
- Contest eligibility/category fit: strong.
- Documentation and installation path: established.
- UI contest polish: deferred.
- Pico 2 port: optional and unvalidated.
- Submission media and Hackaday.io page: outstanding.

Estimated status: **85% technically complete**. Remaining work is mostly visual
identity, validation, media, and storytelling.

## Recommended restart sequence

When this project leaves backlog:

1. Reconfirm the contest page and deadline.
2. Run the existing RP2040 build and smoke tests without changing anything.
3. Capture a current baseline video.
4. Implement POST, themes, and static ASCII art in that order.
5. Capture final media.
6. Create and enter the Hackaday.io project.
7. Evaluate Pico 2 only if schedule margin remains.

This order ensures there is always a submit-ready RP2040 version.
