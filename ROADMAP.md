# RP Training System — Roadmap & Change Log

Running list of what's done and what's planned, so nothing gets lost.
Newest changes at the top of "Done".

## Done (on the SD card)
- **Summary-based live history** — fixed the MemoryError when switching to
  a data-heavy athlete: the live window now holds compact per-session
  summaries (~25x smaller); full set-by-set records stream from the
  on-disk archive. Window grew 24 -> 48 sessions (richer trends) while the
  loaded document shrank 170 KB -> 33 KB. Old profiles migrate on load.
- **Multiple athlete profiles** — `[A]` is now an athlete manager
  (switch / new / edit / delete); each athlete keeps its own program,
  history, records and settings. Old single-athlete data auto-migrates.
- **Demo athlete** with ~8 months of realistic generated training
  (`tools/gen_demo.py`) — multiple mesocycles, load progression, a
  pain-driven squat->hack-squat swap, bodyweight trend, ~5M lb lifetime
  tonnage — for exploring long-term coaching/charts. Switch to it via `[A]`.
- Home calendar fixed (day letters were being overwritten by the markers)
- Workout "UP NEXT" now lists **all** remaining exercises with a count,
  not just 3
- **Home screen (and all screens) redesigned for the real 53-column
  display** — was laid out for a wider screen, so text truncated with `~`
  everywhere; panels now stack full-width, long text wraps, hints shortened
- **Add an exercise mid-workout** (`A`) — pick from the library, inserted
  into today's session only (program unchanged)
- **Skip / remove the current exercise** mid-workout (`X`, confirms if it
  has logged sets)
- Confirm dialogs now accept **Enter = Yes** (was Y-only; that's why the
  template didn't apply after `T` then Enter)
- Form intro text **word-wraps** instead of getting cut off with `~`
- Exercise field is **browsable with Left/Right** (steps through the whole
  library) and still typeable; choice fields **jump on typing** a letter
- Native MicroPython app runs 100% on the stock PicoCalc (no PC at runtime)
- Boots from the bootloader menu as its own entry (`RP_Training_System`);
  launch with `import rpts_boot`
- Full RP engine: mesocycles, RIR schedule, MEV/MAV/MRV volume, deloads,
  per-exercise load progression, fatigue/recovery model, coach analysis
- Dashboards: recovery, trends (sparklines), calendar, PR board, mesocycle
- Program editor: build/edit days & exercises, apply UL/PPL/FB templates,
  swap exercises
- Workout logging with autosave after every set; pause/resume across reboot
- CSV export/import; lb/kg conversion; rotating backups
- **Screen no longer doubles/scrolls** (disabled terminal auto-wrap)
- **Inline field editing** — type straight into a field, no pop-up dialog
- Clock simplified to date + hour (no minutes)
- Removed the rest timer (was causing per-second redraw churn)
- Snappier keyboard input (no GC on every keystroke)
- Lightweight screen buffer (ByteCanvas) — ~10x less RAM per frame

## Planned / backlog
### Workout flexibility
- [x] Add an exercise mid-workout (pick from the library, insert into today)
- [x] Skip / remove an exercise from today's session without editing the
      program
- [ ] Reorder exercises within a session
- [ ] Explicit per-exercise "done" checkmark in the UP NEXT list

### Program / workout creation
- [ ] Quick "new blank program" flow on-device (editor exists; make the
      empty-start path smoother)
- [ ] Duplicate a day / a program as a starting point
- [ ] (Maybe, later) PC companion app that builds a program and writes it
      to the SD card — deferred; the on-device editor covers this for now

### UX polish
- [ ] Clearer indication that the home screen is hotkey-driven (letters,
      not arrows)
- [ ] Confirmation/feedback flashes after logging a set
- [ ] Faster number entry (hold-to-repeat on Left/Right?)

### ASCII art of the exercise being performed
- [ ] Show ASCII art of the current lift on the workout screen — ideally a
      short 2-4 frame animation of the movement (e.g. bench: rack -> lower
      -> press) that cycles while you rest. Static art as a first pass.
  - Store frames per exercise keyed to the exercise-DB `mode` (a squat
    frame set can be reused for many squat variants) so ~10-15 art sets
    cover the whole library; fall back to a generic figure for unknowns.
  - Draw into a fixed region of the workout panel; keep it ASCII (device
    is 7-bit) and small (~12x10 chars) so it fits at 53x40 and stays cheap.
  - Animation needs a screen tick again (removed for the rest timer) —
    re-add a slow, scoped redraw ONLY for the art cell to avoid the old
    full-screen scroll/flicker; or a manual "next frame" key.
  - Great motivation hook; also doubles as a form reminder. Pairs well with
    the skill mode (show the target skill position).

### Multi-modal training (big, high-interest)
Current model is strength only: (weight, reps, RIR). To add calisthenics,
running, swimming, HIIT, skills (handstands), and speed work, give each
exercise a `mode` and adapt logging + coaching per mode:
- [ ] `strength`   — weight x reps x RIR (today's model), full RP logic
- [ ] `bodyweight` — reps (+ optional added weight) x RIR; progress by reps
      then added load (some exist: Push-Up, Pull-Up, Dips, Plank)
- [ ] `cardio`     — duration / distance / avg pace or HR; track trend, not
      RP volume (running, swimming, rowing)
- [ ] `interval`  — HIIT: rounds x work/rest, intensity; simple load index
- [ ] `speed`     — sprints/plyo: reps x distance x quality, low volume,
      long rest, freshness-gated (don't do fatigued)
- [ ] `skill`     — handstands etc.: log practice time + a 1-5 quality/hold
      metric and a level ladder (e.g. wall -> tuck -> freestanding). Coach
      tracks consistency and gates progression on quality, not volume.
      *(User flagged skills as especially interesting.)*
Design: an exercise's `mode` picks its log form and its analytics; the RP
engine stays for `strength`/`bodyweight`, others get lighter tracking.
Storage/history already generic enough to hold per-mode fields.

### Connectivity (needs Pico W / Pico 2 W hardware)
- [ ] Wi-Fi sync to a computer or web page (export/import already exists as
      the offline fallback; add a sync module that pushes the JSON when a
      network is available). Architecture is offline-first with sync hooks,
      so this slots in without disturbing on-device operation.
- [ ] Investigate whether the PicoCalc's always-on keyboard MCU exposes a
      battery-backed RTC (would remove the boot date-confirm entirely)

### Future modules (hooks already in the architecture)
- [ ] Plate calculator
- [ ] Rest timer (re-add as an optional, non-intrusive feature)
- [ ] Wearable / HRV import, Bluetooth scale
- [ ] Macro / calorie tracking
- [ ] True one-tap boot (needs a custom MicroPython firmware build with the
      app frozen in — bigger project)

## Known constraints (hardware/firmware)
- No battery clock → date-confirm on each boot
- Writing internal flash hangs this firmware → app lives on SD, launched
  by typing `import rpts_boot`
- SD card has shown intermittent corruption on this unit → consider a
  known-good card if odd issues recur
