"""Generate a realistic long-term "Demo" athlete for exploring how the app
feels after months of use.

It drives the real coach engine (plan -> simulated performance -> log ->
analyze -> progress), so the data is internally consistent: the same load
progression, deloads, PRs, and volume the app would actually produce. The
result is a Demo profile with several mesocycles of Push/Pull/Legs-style
training, a bodyweight trend, PRs, a pain-driven exercise swap, and a full
records cache.

Usage:
    python tools/gen_demo.py [output_data_dir] [--months N] [--seed N]

Default output is build/sd/rpts_data (so it lands in the SD payload). The
Demo profile is written to <data_dir>/profiles/Demo/. Existing profiles in
that data dir are left untouched; the active athlete is NOT changed.
"""
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from rpts import analytics, coach, compat, programs  # noqa: E402
from rpts.storage import DB  # noqa: E402

# device keeps only this many session SUMMARIES live; generate to match so
# the Demo looks the same on the PicoCalc (full sessions stream from the
# archive, lifetime records/tonnage come from the cache)
ARCHIVE_KEEP = 24
TRAIN_WEEKDAYS = (0, 1, 3, 4, 6)  # Mon Tue Thu Fri Sun (~5/week)

# realistic intermediate starting loads (lb) so progression begins from
# sane, differentiated numbers instead of everything at 100
STARTING_WEIGHTS = {
    "Bench Press": 155, "Incline Press": 135, "DB Bench Press": 60,
    "Incline DB Press": 55, "Cable Fly": 30, "Overhead Press": 95,
    "DB Shoulder Press": 45, "Lateral Raise": 15, "Cable Pushdown": 40,
    "Overhead Extension": 40, "Skullcrusher": 65, "Barbell Row": 135,
    "Chest-Supported Row": 90, "Cable Row": 110, "Lat Pulldown": 120,
    "Pull-Up": 25, "Face Pull": 30, "Rear Delt Fly": 20,
    "Barbell Curl": 65, "DB Curl": 30, "Hammer Curl": 30,
    "Barbell Shrug": 185, "Back Squat": 205, "Hack Squat": 200,
    "Front Squat": 155, "Leg Press": 320, "Romanian Deadlift": 165,
    "Deadlift": 275, "Leg Curl": 90, "Leg Extension": 110,
    "Walking Lunge": 40, "Standing Calf Raise": 150,
    "Seated Calf Raise": 90, "Hip Thrust": 185,
}


def _checkin(rnd, bodyweight, week_pos):
    # sleep/stress drift a little worse late in a mesocycle
    return {
        "sleep": round(rnd.uniform(6.2, 8.4) - 0.4 * week_pos, 1),
        "stress": min(9, rnd.randint(2, 5) + int(2 * week_pos)),
        "energy": max(2, rnd.randint(6, 9) - int(2 * week_pos)),
        "motivation": rnd.randint(6, 9),
        "joint_pain": rnd.choice([0, 0, 0, 1, 1, 2]),
        "calories": rnd.randint(2600, 3400),
        "protein": rnd.randint(150, 220),
        "bodyweight": round(bodyweight, 1),
    }


def _run_session(db, iso, rnd, squat_pain):
    session = coach.plan_workout(db)
    session["date"] = iso
    session["ts"] = iso + "T18:00:00"
    meso = db.data["meso"]
    week_pos = (meso["week"] - 1) / max(1, meso["weeks"] - 1)
    deload = session["rir_label"] == "DELOAD"
    session["checkin"] = _checkin(rnd, db.data["athlete"]["bodyweight"],
                                  week_pos)

    for e in session["entries"]:
        w = e.get("suggested_weight") or 100.0
        lo, hi = e["target_reps"]
        target_rir = e["target_rir"]
        n_sets = e["target_sets"]
        sets = []
        for s in range(n_sets):
            # aim near the top of the rep range early in the meso, drop a
            # little as sets accumulate and as the week gets deeper
            base = hi if week_pos < 0.5 else (lo + hi) // 2
            reps = base - (s // 2) - (1 if week_pos > 0.75 else 0)
            reps = max(lo - 1, min(hi + 1, reps + rnd.choice([-1, 0, 0])))
            rir = max(0, int(round(target_rir + rnd.choice([-1, 0, 0, 1]))))
            pain = 0
            if squat_pain and e["exercise"] in ("Back Squat", "Hack Squat"):
                pain = rnd.choice([4, 5, 5, 6])
            sets.append({"weight": w, "reps": reps, "rir": rir,
                         "pain": pain, "difficulty": rnd.randint(5, 8),
                         "notes": ""})
        e["sets"] = sets

    # occasional post-workout feedback that nudges volume
    post = {}
    if not deload and rnd.random() < 0.15:
        post["volume_up" if rnd.random() < 0.6 else "volume_down"] = True
    session["post"] = post
    session["completed"] = True

    # process exactly like a real finished session
    analytics.detect_prs(db, session)
    _blocks, _overall, updates = coach.analyze_session(db, session)
    db.update_records(session)
    db.commit_session(session)  # full -> archive, summary -> live window
    coach.apply_updates(db, updates)
    coach.advance_calendar(db)


def generate(data_dir, months=8, seed=7):
    rnd = random.Random(seed)
    db = DB(data_dir, archive_keep=ARCHIVE_KEEP)
    # start fresh Demo profile (inherits nothing; we set it up explicitly)
    db.load()
    if "Demo" in db.list_profiles():
        db.delete_profile("Demo") if db.active != "Demo" else None
    db.create_profile("Demo", inherit_settings=False)

    db.data["athlete"].update({
        "name": "Demo Athlete", "age": 28, "sex": "M", "height_in": 70.0,
        "bodyweight": 176.0, "goal_weight": 190.0,
        "experience": "intermediate",
    })
    db.data["goals"]["type"] = "hypertrophy"
    db.data["program"] = programs.make_program("Push Pull Legs")
    db.data["settings"]["charset"] = "ascii"      # so it renders on device
    db.data["settings"]["graph_detail"] = "low"
    db.data["settings"]["pico_tuned"] = True

    # seed realistic starting loads so the first exposure to each lift uses
    # a sane weight (progression continues from there)
    presc = db.data["prescriptions"]
    for name, w in STARTING_WEIGHTS.items():
        presc[name] = {"weight": float(w)}

    total_days = int(months * 30)
    end = compat.to_ord(compat.today())
    cur = end - total_days
    bw = 176.0
    bw_per_day = (188.0 - 176.0) / total_days     # slow lean gain
    swapped = False

    while cur <= end:
        iso = compat.from_ord(cur)
        # bodyweight log a few times a week, trending up with noise
        if rnd.random() < 0.45:
            bw += bw_per_day * 2 + rnd.uniform(-0.5, 0.5)
            db.data["athlete"]["bodyweight"] = round(bw, 1)
            db.data["bodyweight_log"].append({"date": iso,
                                              "weight": round(bw, 1)})
        if compat.weekday(iso) in TRAIN_WEEKDAYS:
            # a stretch of knee pain on squats in the middle third, then a
            # swap to hack squat (shows the swap system + coach reaction)
            frac = (cur - (end - total_days)) / total_days
            squat_pain = 0.42 < frac < 0.5 and not swapped
            _run_session(db, iso, rnd, squat_pain)
            if 0.5 <= frac and not swapped:
                coach.perform_swap(db, "Back Squat", "Hack Squat", "knee")
                swapped = True
        cur += 1

    db.archive_old()
    db.save()
    return db


def main():
    args = [a for a in sys.argv[1:]]
    out = os.path.join(ROOT, "build", "sd", "rpts_data")
    months, seed = 8, 7
    i = 0
    while i < len(args):
        if args[i] == "--months":
            months = int(args[i + 1]); i += 2
        elif args[i] == "--seed":
            seed = int(args[i + 1]); i += 2
        else:
            out = args[i]; i += 1

    db = generate(out, months=months, seed=seed)
    total = sum(1 for _ in db.iter_all_sessions())
    rec = db.data["records"]
    units = db.data["settings"]["units"]
    top = analytics.all_records(db)[:5]
    print("Demo athlete written to: %s/profiles/Demo" % out)
    print("  sessions total   : %d (%d live, rest archived)" %
          (total, len(db.data["history"])))
    print("  lifetime tonnage : %s %s" %
          (compat.group_thousands(rec["lifetime"]), units))
    print("  bodyweight log   : %d entries" % len(db.data["bodyweight_log"]))
    print("  mesocycle reached: meso %d, week %d" %
          (db.data["meso"]["number"], db.data["meso"]["week"]))
    print("  top e1RMs:")
    for name, r in top:
        print("    %-18s %.0f %s" % (name, r["e1rm"], units))


if __name__ == "__main__":
    main()
