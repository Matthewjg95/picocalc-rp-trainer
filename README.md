# RP TRAINING SYSTEM

An offline, keyboard-first strength-training operating system with a
Renaissance Periodization (RP) auto-regulation coach, styled like a piece of
lab equipment. Pure Python 3 standard library — no dependencies, no network.

```
┌─ RP TRAINING SYSTEM v1.0 ─────────────────── MESO 1  WK 1/6 ─┐
│┌─ STATUS ───────────────────┐┌─ NEXT SESSION ───────────────┐│
││ Recovery  █████████░  90%  ││ Upper A   ·   3 RIR          ││
││ Fatigue   ██░░░░░░░░  20%  ││ Bench Press         195 ↑+5  ││
││ Readiness ████████░░  81%  ││ Barbell Row         175 ↑+5  ││
││ MRV Used  ██░░░░░░░░  15%  ││ Overhead Press               ││
││ Weight    180.0 lb         ││ Lat Pulldown                 ││
││ Strength  ↑ +1.3%/session  ││ Lateral Raise                ││
│└────────────────────────────┘└──────────────────────────────┘│
│┌─ COACH ────────────────────────────────────────────────────┐│
││ ▸ Recovery is strong — a productive session awaits.        ││
│└────────────────────────────────────────────────────────────┘│
└─ [S] Start Workout   [B] Log Bodyweight   [Q] Quit ──────────┘
```

## Run

```
python main.py
```

Requires Python 3.8+. Works on Windows 10+ (Windows Terminal or conhost),
Linux, macOS, and over SSH/serial.

### On a stock PicoCalc (100% standalone, no computer)

The same codebase runs under MicroPython on the stock Pico core, using the
PicoCalc MicroPython firmware's built-in 53x40 VT100 terminal for display
and its I2C keyboard driver for input. Build the SD payload and follow the
on-card instructions:

```
python tools/build_sd.py        # produces build/sd/ (py + precompiled mpy)
# copy build/sd/* to the SD card root, then read README_PICOCALC.txt
```

One-time, on the device: boot menu → `MicroPython_*.bin` → at the on-screen
`>>>` prompt type `
import sys; sys.path.insert(0,'/sd'); import boot_rpts
`.
After that the app auto-starts on every boot. The stock BASIC/NES/etc.
firmwares remain available in the boot menu. Since the Pico has no battery
clock, each boot shows a two-keypress date-confirm screen seeded from the
last saved timestamp. `tools/check_upy.py` statically verifies the shared
modules stay MicroPython-clean.

Environment (desktop):

| Var | Meaning |
|---|---|
| `RPTS_DATA` | data directory (default `./data`) |
| `RPTS_COLS` / `RPTS_ROWS` | force a fixed screen size |

## What it does

- **RP mesocycles** — 4-8 week blocks, RIR ramps 3 → 3 → 2 → 1 → 0-1 →
  deload (half sets, ~90% load) automatically.
- **Auto-regulation** — every muscle tracks weekly sets against MEV/MAV/MRV
  landmarks (scaled by experience level). Sets are added when recovery is
  high and performance rises; pulled back on pain, missed reps, poor sleep,
  or MRV breach. Deloads trigger early if systemic fatigue spikes.
- **Load progression** — per-exercise suggestions driven by RIR accuracy
  and e1RM trend, with per-equipment increments. Every recommendation comes
  with its reason.
- **Check-ins** — sleep / stress / energy / motivation / joint pain /
  calories / protein / bodyweight before each session; RIR-accuracy and
  volume feedback after. All of it feeds the fatigue model.
- **Pain-driven swaps** — repeated pain on a lift suggests the RP swap
  chain (Back Squat → Hack Squat → Leg Press → …), filtered by your
  equipment.
- **Dashboards** — recovery gauges, engineering-telemetry trend sparklines,
  training calendar, mesocycle manager, PR board with lifetime-tonnage
  milestones and a celebration screen.
- **Data safety** — one JSON database, atomically written after every set;
  a paused workout survives a power cut and resumes on next boot. Rotating
  backups after each session, CSV export/import, lb/kg conversion of the
  entire archive.

## Keys

Global: hotkeys shown in each screen's bottom border. `ESC` backs out of
anything. Forms: `↑/↓` field, `←/→` nudge value or cycle choice, `Enter`
edit/save, or just start typing digits.

## Architecture

```
main.py               launcher
rpts/term.py          ANSI terminal driver: canvas, themes, diffed frames,
                      cross-platform key input (no curses)
rpts/widgets.py       frames, bars, gauges, sparklines, ascii fallbacks
rpts/exercise_db.py   exercise library, muscle targets, RP volume landmarks
rpts/programs.py      Upper/Lower, PPL, Full Body templates (all editable)
rpts/storage.py       JSON persistence, backups, CSV, unit conversion
rpts/analytics.py     pure functions: e1RM, tonnage, trends, PR detection
rpts/coach.py         RP engine: RIR schedule, fatigue model, progression,
                      deloads, swap suggestions, session analysis
rpts/app.py           screen stack, chrome, event loop, form toolkit
rpts/screens_*.py     UI screens (home / workout flow / dashboards)
tests/smoke.py        engine checks + scripted full-UI runs (python tests/smoke.py)
```

The layering is strict: `coach`/`analytics` never import UI; screens never
touch JSON directly. Future modules (wearables, plate calculator, macro
tracking, sync) plug in as new analytics inputs or screens without touching
the core.
