# How the coaching works

Everything below runs on the PicoCalc itself, in [`rpts/coach.py`](../rpts/coach.py)
and [`rpts/analytics.py`](../rpts/analytics.py). No black boxes: every
recommendation the coach prints traces to one of these rules.

## 1. Strength estimate — e1RM

Every set is scored with an RIR-adjusted Epley estimate:

```
e1RM = weight x (1 + (reps + RIR) / 30)
```

Leaving 2 reps in reserve counts as if the set had gone 2 reps further, so
submaximal training still produces a comparable strength number. The best
set of each exercise per session becomes its e1RM history — that's what
the trend sparklines and PR detection use.

## 2. Volume landmarks — MV / MEV / MAV / MRV

Each muscle has weekly working-set landmarks (RP's published hypertrophy
guidelines, in `rpts/exercise_db.py`), scaled by experience level
(beginner x0.75, intermediate x1.0, advanced x1.15):

- **MV** — maintenance volume
- **MEV** — minimum effective volume (below this: not enough to grow)
- **MAV** — maximum adaptive volume (the productive band's upper middle)
- **MRV** — maximum recoverable volume (above this: digging a hole)

Weekly sets are counted per muscle: a set counts 1.0 for each primary
muscle and 0.5 for each secondary. The Program editor's **[V] Volume**
view compares your program's *projected* weekly sets against these
landmarks (and against what you've actually logged this week).

## 3. Mesocycle RIR schedule

A mesocycle is 4-8 weeks; the last week is always a deload. Target RIR
(reps in reserve) ramps intensity across the accumulation weeks by
position: first ~third at 3 RIR, then 2, then 1, final week 0-1. Deload
week: half the sets, ~90% load, RIR 4.

## 4. Fatigue / recovery model

A brand-new athlete starts pristine: fatigue 0, recovery 100. Once
training exists, five 0-100 gauges are computed from the last 7 days of
check-ins plus training load:

- **muscular fatigue** = base + 0.50 x (weekly sets / MRV, worst muscle
  weighted) + 0.30 x position-in-mesocycle − sleep bonus
- **joint stress** = reported joint pain + per-set pain logged this week
- **systemic fatigue** = blend of muscular, stress, short sleep, week
  position, minus the performance trend
- **recovery** = 1 − weighted(muscular, systemic, joint) + sleep bonus
- **readiness** = 0.55 x recovery + energy + motivation + calm

These drive volume decisions and the coach's tone ("recovery excellent —
continue progression" vs "prioritize sleep and food").

## 5. Load progression (per exercise)

Judged on RIR accuracy of the most recent performance of that exercise:

| observation | action |
|---|---|
| pain >= 5 reported | hold the load |
| avg RIR >= target + 1 (too easy) | **add** one increment |
| every set hit the rep ceiling | **add** one increment |
| avg RIR <= target − 1.5 (much too hard) | **reduce** one increment |
| slight overshoot | hold, regain the target |
| on target, e1RM rising | add one increment |
| otherwise | hold and add reps |

Increments are per-equipment: lower-body compounds 10 lb / 5 kg, upper
compounds 5 lb / 2.5 kg, isolations 2.5 lb / 1.25 kg.

## 6. Set (volume) auto-regulation

After each session, per exercise:

- pain >= 5, or missed reps with recovery < 50 → **−1 set**
- athlete flagged "too much" in the post-workout survey → **−1 set**
- at or near MRV for its muscle → hold (deload soon)
- recovery >= 60, readiness >= 55, no pain, reps made, and either the
  athlete flagged "too easy" or performance is trending up with room
  under MRV → **+1 set**

## 7. Deload triggers

- final week of the mesocycle (always), or early if:
- systemic fatigue >= 85%, or
- strength trending down while recovery < 40%

## 8. Pain-driven exercise swaps

If an exercise logs pain >= 4 in two consecutive sessions, the coach
suggests the next exercise in its swap chain (ordered by decreasing joint
stress, filtered by your equipment) that has no pain history — e.g.
Back Squat → Hack Squat → Leg Press → Safety Bar Squat.

## 9. Session analysis

After every workout the coach prints, per exercise: performance vs last
time (e1RM delta), RIR accuracy, pain flags with swap suggestions, and
the exact load/set change queued for next session — plus an overall
recovery verdict and any deload warning. Every line comes from the rules
above, so the "why" is always inspectable.
