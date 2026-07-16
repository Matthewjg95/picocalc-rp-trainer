"""The RP auto-regulation engine.

Responsibilities:
  * mesocycle RIR schedule (3 -> 0-1 -> deload)
  * fatigue / recovery / readiness model from check-ins + training load
  * per-exercise load progression (RIR-accuracy driven)
  * per-muscle set progression between MEV and MRV
  * deload detection
  * pain-driven exercise swap suggestions
  * end-of-session written analysis (every recommendation is explained)
"""
from . import analytics, exercise_db
from .compat import date_add, gmax, now_iso, today

EXPERIENCE_SCALE = {"beginner": 0.75, "intermediate": 1.0, "advanced": 1.15}


def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


# -- mesocycle schedule ------------------------------------------------------

def target_rir(week, weeks):
    """(numeric_rir, label). Last week of a meso is always the deload."""
    if week >= weeks:
        return 4.0, "DELOAD"
    acc = max(1, weeks - 1)
    f = 0.0 if acc == 1 else (week - 1) / (acc - 1)
    if f < 0.34:
        return 3.0, "3 RIR"
    if f < 0.6:
        return 2.0, "2 RIR"
    if f < 0.9:
        return 1.0, "1 RIR"
    return 0.5, "0-1 RIR"


def is_deload_week(meso):
    return meso["week"] >= meso["weeks"]


def landmarks(db, muscle):
    """(MV, MEV, MAV, MRV) scaled for experience level."""
    k = EXPERIENCE_SCALE.get(db.data["athlete"].get("experience"), 1.0)
    return tuple(round(v * k) for v in exercise_db.LANDMARKS[muscle])


# -- fatigue / recovery model ---------------------------------------------

def _recent_checkins(db, days=7):
    cutoff = date_add(today(), -days)
    return [s.get("checkin", {}) for s in db.data["history"]
            if s["date"] >= cutoff and s.get("checkin")]


def _avg(checks, field, default):
    vals = [c[field] for c in checks if c.get(field) is not None]
    return sum(vals) / len(vals) if vals else default


def recovery_scores(db):
    """All values 0..100.  recovery/readiness: higher = better;
    muscular/joint/systemic: higher = more fatigued."""
    if not db.data["history"]:
        # a brand-new athlete has accumulated nothing: fatigue starts at
        # zero and recovery at full, instead of the model's baseline for
        # someone mid-training
        return {"recovery": 100, "muscular": 0, "joint": 0, "systemic": 0,
                "readiness": 100, "sleep_h": 8.0, "perf_trend": 0.0,
                "vol_load": 0}
    checks = _recent_checkins(db)
    meso = db.data["meso"]

    sleep = clamp(_avg(checks, "sleep", 7.5) / 8.0)          # 1.0 = 8h
    stress = clamp(_avg(checks, "stress", 4) / 10.0)         # 1.0 = maxed
    energy = clamp(_avg(checks, "energy", 6) / 10.0)
    motivation = clamp(_avg(checks, "motivation", 6) / 10.0)
    joint_rep = clamp(_avg(checks, "joint_pain", 1) / 10.0)

    # training load: how deep into per-muscle MRVs is this week?
    weekly = analytics.weekly_muscle_sets(db)
    ratios = []
    for m, sets in weekly.items():
        mrv = landmarks(db, m)[3]
        if sets > 0 and mrv > 0:
            ratios.append(sets / mrv)
    vol_load = clamp(max(ratios) * 0.5 + (sum(ratios) / len(ratios)) * 0.5) \
        if ratios else 0.0

    # accumulated exercise pain over the last week (per-entry max pain —
    # works for both full and summarized history entries)
    cutoff = date_add(today(), -7)
    pains = [analytics.entry_stats(e)["max_pain"]
             for s in db.data["history"] if s["date"] >= cutoff
             for e in s.get("entries", [])]
    set_pain = clamp((sum(pains) / len(pains)) / 10.0) if pains else 0.0

    week_pos = clamp((meso["week"] - 1) / max(1, meso["weeks"] - 1))
    perf = analytics.strength_trend(db)  # ~ fraction/session

    muscular = clamp(0.15 + 0.50 * vol_load + 0.30 * week_pos
                     - 0.15 * (sleep - 0.8))
    joint = clamp(0.6 * joint_rep + 0.5 * set_pain)
    systemic = clamp(0.30 * muscular + 0.25 * stress + 0.25 * (1 - sleep)
                     + 0.20 * week_pos - clamp(perf * 4, -0.1, 0.1))
    recovery = clamp(1.0 - (0.45 * muscular + 0.25 * systemic
                            + 0.15 * joint) + 0.15 * (sleep - 0.75))
    readiness = clamp(0.55 * recovery + 0.20 * energy + 0.15 * motivation
                      + 0.10 * (1 - stress))
    return {
        "recovery": round(recovery * 100),
        "muscular": round(muscular * 100),
        "joint": round(joint * 100),
        "systemic": round(systemic * 100),
        "readiness": round(readiness * 100),
        "sleep_h": round(_avg(checks, "sleep", 7.5), 1),
        "perf_trend": perf,
        "vol_load": round(vol_load * 100),
    }


# -- deloads -----------------------------------------------------------

def deload_recommendation(db):
    """None, or a human-readable reason a deload is (or is nearly) due."""
    meso = db.data["meso"]
    if is_deload_week(meso):
        return "Deload week — reduced sets and load this week."
    sc = recovery_scores(db)
    if sc["systemic"] >= 85:
        return "Systemic fatigue critical (%d%%) — begin deload early." \
            % sc["systemic"]
    if sc["perf_trend"] < -0.015 and sc["recovery"] < 40:
        return "Strength trending down with poor recovery — deload advised."
    if meso["week"] == meso["weeks"] - 1:
        return "Final accumulation week — deload begins next week."
    return None


# -- load progression --------------------------------------------------

def suggest_weight(db, exercise, target):
    """(weight or None, delta, reason) for the next session of `exercise`.

    Driven by RIR accuracy of the most recent performance:
      actual RIR well above target  -> too light, add load
      on target and reps at ceiling -> progress load
      well below target / misses    -> hold or back off
    """
    units = db.data["settings"]["units"]
    presc = db.data["prescriptions"].get(exercise, {})
    hist = analytics.exercise_sessions(db, exercise)
    if not hist:
        w = presc.get("weight")
        return w, 0.0, "First exposure — establish a baseline."
    last = hist[-1]
    base = presc.get("weight") or last["top_weight"]
    inc = exercise_db.increment(exercise, units)
    diff = last["avg_rir"] - last["target_rir"]  # + = easier than planned

    if last["max_pain"] >= 5:
        return base, 0.0, "Pain reported last session — hold the load."
    if diff >= 1.0:
        return base + inc, inc, \
            "RIR undershoot (easier than planned) — add %g %s." % (inc, units)
    if diff <= -1.5:
        return max(0.0, base - inc), -inc, \
            "Repeated RIR overshoot — reduce %g %s." % (inc, units)
    if diff <= -0.5:
        return base, 0.0, "Slight RIR overshoot — keep weight identical."
    # on target: progress if the rep ceiling was reached
    if len(hist) >= 2 and hist[-1]["best_e1rm"] > hist[-2]["best_e1rm"]:
        return base + inc, inc, \
            "Performance increasing — add %g %s next session." % (inc, units)
    return base, 0.0, "On target — repeat and push reps."


# -- set (volume) progression -------------------------------------------

def program_volume(db):
    """PROJECTED weekly sets per muscle from the saved program (each day
    assumed to run once per week; secondary muscles count 0.5), alongside
    the landmarks and this week's ACTUAL logged sets. This is the
    'does my program design stack up against MEV/MAV/MRV?' view."""
    projected = {}
    for m in exercise_db.MUSCLES:
        projected[m] = 0.0
    for day in db.data["program"]["days"]:
        for slot in day["exercises"]:
            inf = exercise_db.info(slot["exercise"])
            n = slot.get("sets", 0)
            for m in inf["primary"]:
                projected[m] = projected.get(m, 0) + n
            for m in inf["secondary"]:
                projected[m] = projected.get(m, 0) + 0.5 * n
    actual = analytics.weekly_muscle_sets(db)
    out = {}
    for m in exercise_db.MUSCLES:
        mv, mev, mav, mrv = landmarks(db, m)
        p = projected.get(m, 0.0)
        if p <= 0:
            status = "-"
        elif p < mev:
            status = "<MEV"
        elif p < mav:
            status = "OK"
        elif p < mrv:
            status = "MAV"
        else:
            status = "MRV!"
        out[m] = {"projected": p, "actual": actual.get(m, 0.0),
                  "mv": mv, "mev": mev, "mav": mav, "mrv": mrv,
                  "status": status}
    return out


def volume_status(db):
    """Per-muscle weekly sets vs landmarks, with a status word."""
    weekly = analytics.weekly_muscle_sets(db)
    out = {}
    for m in exercise_db.MUSCLES:
        mv, mev, mav, mrv = landmarks(db, m)
        sets = weekly.get(m, 0.0)
        if sets <= 0:
            status = "-"
        elif sets < mev:
            status = "< MEV"
        elif sets < mav:
            status = "OK"
        elif sets < mrv:
            status = "MAV"
        else:
            status = "MRV!"
        out[m] = {"sets": sets, "mv": mv, "mev": mev, "mav": mav,
                  "mrv": mrv, "status": status}
    return out


def _sets_delta(db, entry, session, scores):
    """(delta, reason or None) for next-session set count of one exercise."""
    post = session.get("post", {})
    name = entry["exercise"]
    prim = exercise_db.info(name)["primary"]
    weekly = analytics.weekly_muscle_sets(db, ref_date=session["date"],
                                          extra_session=session)
    worst = gmax((weekly.get(m, 0) / max(1, landmarks(db, m)[3])
                  for m in prim))
    max_pain = gmax((s.get("pain", 0) for s in entry.get("sets", [])))
    missed = any(s.get("reps", 0) < entry.get("target_reps", [0, 0])[0]
                 for s in entry.get("sets", []))

    if max_pain >= 5:
        return -1, "Joint pain %d/10 — drop a set and reassess." % max_pain
    if missed and scores["recovery"] < 50:
        return -1, "Missed reps with low recovery — reduce a set."
    if post.get("volume_down") or name in str(post.get("too_hard", "")):
        return -1, "You flagged this as too much — reduce a set."
    if worst >= 1.0:
        return 0, "Reached MRV for %s — maintain, deload soon." % \
            "/".join(prim)
    if worst >= 0.85:
        return 0, "Approaching MRV — maintain current volume."
    add_ok = (scores["recovery"] >= 60 and scores["readiness"] >= 55
              and max_pain < 3 and not missed)
    if add_ok and (post.get("volume_up")
                   or name in str(post.get("too_easy", ""))):
        return 1, "Recovering well and it felt easy — add a set."
    if add_ok and scores["perf_trend"] > 0.005 and worst < 0.7:
        return 1, "Recovery high, performance rising — add a set."
    return 0, None


# -- session planning ------------------------------------------------------

def plan_workout(db):
    """Build a session skeleton from the program day + current prescriptions."""
    meso = db.data["meso"]
    days = db.data["program"]["days"]
    day = days[meso["day_index"] % len(days)]
    rir, rir_label = target_rir(meso["week"], meso["weeks"])
    deload = is_deload_week(meso)
    entries = []
    for slot in day["exercises"]:
        name = slot["exercise"]
        presc = db.data["prescriptions"].get(name, {})
        sets = presc.get("sets", slot["sets"])
        weight, delta, reason = suggest_weight(db, name, rir)
        if deload:
            sets = max(1, (sets + 1) // 2)
            if weight:
                weight = round(weight * 0.9 / 2.5) * 2.5
            reason = "Deload: half sets, ~90% load, stay far from failure."
        entries.append({
            "exercise": name,
            "target_sets": sets,
            "target_reps": list(slot["reps"]),
            "target_rir": rir,
            "tempo": slot.get("tempo", ""),
            "notes": slot.get("notes", ""),
            "suggested_weight": weight,
            "suggested_delta": delta,
            "suggestion_reason": reason,
            "sets": [],
        })
    return {
        "date": today(),
        "ts": now_iso(),
        "week": meso["week"], "meso": meso["number"],
        "day": day["name"], "rir_label": rir_label,
        "checkin": {}, "post": {}, "entries": entries,
        "completed": False,
    }


def advance_calendar(db):
    """Move the meso pointer after a completed session."""
    meso = db.data["meso"]
    days = db.data["program"]["days"]
    meso["day_index"] = (meso["day_index"] + 1) % max(1, len(days))
    if meso["day_index"] == 0:
        meso["week"] += 1
        if meso["week"] > meso["weeks"]:
            meso["number"] += 1
            meso["week"] = 1
            meso["started"] = today()


# -- swaps ------------------------------------------------------------------

def pain_streak(db, exercise, threshold=4):
    """Consecutive most-recent sessions of `exercise` with pain >= threshold."""
    hist = analytics.exercise_sessions(db, exercise)
    streak = 0
    for h in reversed(hist):
        if h["max_pain"] >= threshold:
            streak += 1
        else:
            break
    return streak


def swap_suggestion(db, exercise):
    """A lower-joint-stress alternative if pain keeps recurring."""
    if pain_streak(db, exercise) < 2:
        return None
    equip = set(db.data["athlete"].get("equipment", []))
    for alt in exercise_db.swap_chain(exercise, equip or None):
        if pain_streak(db, alt) == 0:
            return alt
    return None


# -- end-of-session analysis --------------------------------------------------

def analyze_session(db, session):
    """Written verdict per exercise plus overall guidance, and the
    prescription updates to apply.  Returns (blocks, overall, updates)."""
    scores = recovery_scores(db)
    verbose = db.data["settings"].get("coach_verbosity", "normal")
    deload = session.get("rir_label") == "DELOAD"
    blocks, updates = [], {}

    for entry in session.get("entries", []):
        if not entry.get("sets"):
            continue
        name = entry["exercise"]
        lines = []
        hist = analytics.exercise_sessions(db, name)
        prev = hist[-1] if hist else None
        cur_e1 = analytics.best_set_e1rm(entry)
        if prev and prev["best_e1rm"] > 0 and cur_e1 > 0:
            d = (cur_e1 / prev["best_e1rm"] - 1) * 100
            if d > 1:
                lines.append(("Performance increasing (+%.1f%% e1RM)." % d,
                              "good"))
            elif d < -2:
                lines.append(("Performance down %.1f%% — watch fatigue."
                              % -d, "bad"))
            elif verbose != "terse":
                lines.append(("Performance steady.", ""))

        rirs = [s.get("rir", 0) for s in entry["sets"]]
        avg_rir = sum(rirs) / len(rirs) if rirs else 0
        diff = avg_rir - entry.get("target_rir", 2)
        if diff >= 1.0:
            lines.append(("Sets came in easier than planned "
                          "(avg RIR %.1f vs %.1f)." %
                          (avg_rir, entry["target_rir"]), "warn"))
        elif diff <= -1.0:
            lines.append(("Repeated RIR overshoot — closer to failure "
                          "than planned.", "warn"))

        max_pain = gmax((s.get("pain", 0) for s in entry["sets"]))
        if max_pain >= 4:
            lines.append(("Pain %d/10 reported." % max_pain, "bad"))
            alt = swap_suggestion(db, name)
            if alt:
                lines.append(("Recurring pain — consider swapping to %s."
                              % alt, "bad"))

        # next-session prescription (frozen during a deload week — light
        # deload numbers must not overwrite the working prescription)
        if deload:
            lines.append(("Deload logged — prescriptions unchanged.",
                          "accent"))
        else:
            w, wd, wreason = _suggest_after(db, entry, session)
            sd, sreason = _sets_delta(db, entry, session, scores)
            presc = db.data["prescriptions"].get(name, {})
            new_sets = max(1, min(entry["target_sets"] + 3,
                                  (presc.get("sets", entry["target_sets"]))
                                  + sd))
            updates[name] = {"weight": w, "sets": new_sets}
            lines.append((wreason, "accent"))
            if sreason:
                lines.append((sreason, "accent"))
        blocks.append({"exercise": name, "lines": lines})

    overall = []
    if scores["recovery"] >= 70:
        overall.append(("Recovery excellent (%d%%). Continue progression."
                        % scores["recovery"], "good"))
    elif scores["recovery"] >= 45:
        overall.append(("Recovery moderate (%d%%). Progress with care."
                        % scores["recovery"], "warn"))
    else:
        overall.append(("Recovery poor (%d%%). Prioritize sleep and food."
                        % scores["recovery"], "bad"))
    dl = deload_recommendation(db)
    if dl:
        overall.append((dl, "warn"))
    if scores["perf_trend"] > 0.005:
        overall.append(("Strength trend positive across recent sessions.",
                        "good"))
    elif scores["perf_trend"] < -0.01:
        overall.append(("Strength trend negative — volume or recovery "
                        "needs attention.", "bad"))
    return blocks, overall, updates


def _suggest_after(db, entry, session):
    """Weight suggestion for next time, judged on *this* session's sets."""
    name = entry["exercise"]
    units = db.data["settings"]["units"]
    inc = exercise_db.increment(name, units)
    sets = entry["sets"]
    top = gmax((s.get("weight", 0) for s in sets))
    rirs = [s.get("rir", 0) for s in sets]
    avg_rir = sum(rirs) / len(rirs) if rirs else 0
    diff = avg_rir - entry.get("target_rir", 2)
    max_pain = gmax((s.get("pain", 0) for s in sets))
    missed = any(s.get("reps", 0) < entry.get("target_reps", [0, 0])[0]
                 for s in sets)
    hit_ceiling = all(s.get("reps", 0) >= entry.get("target_reps",
                                                    [0, 99])[1]
                      for s in sets if s.get("reps", 0) > 0)
    if max_pain >= 5:
        return top, 0, "Keep weight identical until pain resolves."
    if missed and diff <= -1:
        return max(0, top - inc), -inc, \
            "Missed reps near failure — reduce %g %s." % (inc, units)
    if diff <= -1:
        return top, 0, "Keep weight identical; regain the RIR target."
    if hit_ceiling or diff >= 1:
        return top + inc, inc, "Add %g %s next session." % (inc, units)
    return top, 0, "Hold %g %s and add reps." % (top, units)


def apply_updates(db, updates):
    for name, u in updates.items():
        p = db.data["prescriptions"].setdefault(name, {})
        if u.get("weight"):
            p["weight"] = u["weight"]
        if u.get("sets"):
            p["sets"] = u["sets"]


def perform_swap(db, old, new, reason="pain"):
    """Replace an exercise in the program and log the swap for tracking."""
    for day in db.data["program"]["days"]:
        for slot in day["exercises"]:
            if slot["exercise"] == old:
                slot["exercise"] = new
    db.data["swaps"].append({"date": today(),
                             "from": old, "to": new, "reason": reason})
