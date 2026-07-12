"""Derived metrics: e1RM, tonnage, weekly series, trends, PR detection.

Pure functions of the database. Trend/series functions read only the live
history window; anything needing all-time knowledge (PRs, lifetime
tonnage) reads the incremental records cache maintained by storage.
"""
from . import exercise_db
from .compat import gmax, group_thousands, week_key


# -- per-set / per-session ------------------------------------------------

def e1rm(weight, reps, rir=0):
    """Epley estimate, RIR-adjusted: performance at RIR 2 counts as if the
    set had been taken to failure two reps later."""
    total = reps + max(0.0, rir)
    if total <= 1:
        return float(weight)
    return weight * (1 + total / 30.0)


def best_set_e1rm(entry):
    vals = [e1rm(s["weight"], s["reps"], s.get("rir", 0))
            for s in entry.get("sets", []) if s.get("reps", 0) > 0]
    return max(vals) if vals else 0.0


def entry_tonnage(entry):
    return sum(s.get("weight", 0) * s.get("reps", 0)
               for s in entry.get("sets", []))


def session_tonnage(session):
    return sum(entry_tonnage(e) for e in session.get("entries", []))


def session_sets(session):
    return sum(len(e.get("sets", [])) for e in session.get("entries", []))


# -- history queries --------------------------------------------------------

def exercise_sessions(db, name):
    """Chronological per-session stats for one exercise (live window)."""
    out = []
    for s in db.data["history"]:
        for e in s.get("entries", []):
            if e["exercise"] != name or not e.get("sets"):
                continue
            sets = e["sets"]
            reps_done = [x["reps"] for x in sets if x.get("reps", 0) > 0]
            rirs = [x.get("rir", 0) for x in sets]
            out.append({
                "date": s["date"],
                "target_rir": e.get("target_rir", 2),
                "best_e1rm": best_set_e1rm(e),
                "top_weight": gmax((x.get("weight", 0) for x in sets)),
                "total_reps": sum(reps_done),
                "tonnage": entry_tonnage(e),
                "avg_rir": sum(rirs) / len(rirs) if rirs else 0,
                "max_pain": gmax((x.get("pain", 0) for x in sets)),
                "n_sets": len(sets),
            })
    return out


def weekly_series(db, metric="tonnage"):
    """(labels, values) grouped by ISO week.  metric: tonnage|sets|sessions."""
    buckets = {}
    for s in db.data["history"]:
        k = week_key(s["date"])
        b = buckets.setdefault(k, [0.0, 0, 0])
        b[0] += session_tonnage(s)
        b[1] += session_sets(s)
        b[2] += 1
    keys = sorted(buckets)
    idx = {"tonnage": 0, "sets": 1, "sessions": 2}[metric]
    return keys, [buckets[k][idx] for k in keys]


def checkin_series(db, field):
    """Chronological values of one pre-workout check-in field."""
    out = []
    for s in db.data["history"]:
        v = s.get("checkin", {}).get(field)
        if v is not None:
            out.append((s["date"], float(v)))
    return out


def bodyweight_series(db):
    log = sorted(db.data["bodyweight_log"], key=lambda r: r["date"])
    return [(r["date"], r["weight"]) for r in log]


def weekly_muscle_sets(db, ref_date=None, extra_session=None):
    """Working sets per muscle this ISO week (secondary muscles count 0.5).
    `extra_session` lets an in-progress workout be included."""
    from .compat import today
    wk = week_key(ref_date or today())
    totals = {}
    for m in exercise_db.MUSCLES:
        totals[m] = 0.0
    sessions = list(db.data["history"])
    if extra_session is not None:
        sessions.append(extra_session)
    for s in sessions:
        if week_key(s["date"]) != wk:
            continue
        for e in s.get("entries", []):
            n = len(e.get("sets", []))
            if not n:
                continue
            inf = exercise_db.info(e["exercise"])
            for m in inf["primary"]:
                totals[m] = totals.get(m, 0) + n
            for m in inf["secondary"]:
                totals[m] = totals.get(m, 0) + 0.5 * n
    return totals


def strength_trend(db, sessions_back=8):
    """Normalized slope of mean session e1RM over recent sessions.
    ~ +0.01 means ~1%/session improvement."""
    means = []
    for s in db.data["history"][-sessions_back:]:
        vals = [best_set_e1rm(e) for e in s.get("entries", [])
                if e.get("sets")]
        vals = [v for v in vals if v > 0]
        if vals:
            means.append(sum(vals) / len(vals))
    return trend_slope(means)


def trend_slope(vals):
    """Least-squares slope normalized by the series mean."""
    n = len(vals)
    if n < 2:
        return 0.0
    mean = sum(vals) / n
    if abs(mean) < 1e-9:
        return 0.0
    xm = (n - 1) / 2.0
    num = sum((i - xm) * (v - mean) for i, v in enumerate(vals))
    den = sum((i - xm) ** 2 for i in range(n))
    return (num / den) / mean if den else 0.0


def lifetime_tonnage(db):
    return db.data["records"]["lifetime"]


# -- personal records ---------------------------------------------------

TONNAGE_MILESTONES_LB = [100_000, 250_000, 500_000, 1_000_000, 2_500_000,
                         5_000_000, 10_000_000]


def all_records(db):
    """[(exercise, record dict)] from the cache, best e1RM first."""
    ex = db.data["records"]["ex"]
    items = [(n, r) for n, r in ex.items() if r["e1rm"] > 0]
    items.sort(key=lambda kv: -kv[1]["e1rm"])
    return items


def detect_prs(db, session):
    """PRs set by `session` vs the records cache (which excludes it —
    storage.update_records() runs after this). Returns display dicts."""
    prs = []
    units = db.data["settings"]["units"]
    rec = db.data["records"]
    for e in session.get("entries", []):
        if not e.get("sets"):
            continue
        name = e["exercise"]
        prev = rec["ex"].get(name, {"e1rm": 0.0, "reps": 0,
                                    "reps_weight": 0.0, "tonnage": 0.0})
        v = best_set_e1rm(e)
        if v > prev["e1rm"] > 0:
            prs.append({"kind": "e1RM PR", "exercise": name,
                        "text": "%s e1RM %.0f %s (was %.0f)" %
                                (name, v, units, prev["e1rm"])})
        t = entry_tonnage(e)
        if t > prev["tonnage"] > 0:
            prs.append({"kind": "Volume PR", "exercise": name,
                        "text": "%s session volume %s %s" %
                                (name, group_thousands(t), units)})
        for st in e.get("sets", []):
            w, r = st.get("weight", 0), st.get("reps", 0)
            if w >= prev["reps_weight"] > 0 and r > prev["reps"]:
                prs.append({"kind": "Rep PR", "exercise": name,
                            "text": "%s %g x %d" % (name, w, r)})
                break
    # weekly tonnage PR
    wk = week_key(session["date"])
    cur = (rec["cur_week"] if rec["cur_week_key"] == wk else 0.0) \
        + session_tonnage(session)
    best_other = rec["best_week"]
    if rec["cur_week_key"] != wk and rec["cur_week"] > best_other:
        best_other = rec["cur_week"]
    if best_other > 0 and cur > best_other:
        prs.append({"kind": "Weekly PR", "exercise": "",
                    "text": "Weekly tonnage %s %s" %
                            (group_thousands(cur), units)})
    # lifetime milestone
    before = rec["lifetime"]
    after = before + session_tonnage(session)
    scale = 1.0 if units == "lb" else 0.5
    for m in TONNAGE_MILESTONES_LB:
        m2 = m * scale
        if before < m2 <= after:
            prs.append({"kind": "Milestone", "exercise": "",
                        "text": "Lifetime tonnage passed %s %s" %
                                (group_thousands(m2), units)})
    return prs
