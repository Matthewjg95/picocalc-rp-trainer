"""Smoke test: engine math, coach logic, and a scripted full-UI run.

Run:  python tests/smoke.py
No real terminal is touched — a FakeTerm captures frames and feeds keys.
"""
import copy
import datetime as dt
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rpts import analytics, coach
from rpts.app import App
from rpts.screens_core import HomeScreen
from rpts.storage import DB

PASS = 0


def check(cond, msg):
    global PASS
    assert cond, "FAIL: " + msg
    PASS += 1
    print("  ok  " + msg)


class FakeTerm:
    def __init__(self, keys, w=64, h=32):
        self.keys = list(keys)
        self.w, self.h = w, h
        self.frames = []

    def size(self):
        return self.w, self.h

    def theme(self, name):
        from rpts.term import THEMES
        return THEMES.get(name, THEMES["phosphor"])

    def enter(self):
        pass

    def exit(self):
        pass

    def draw(self, canvas, theme):
        canvas.render(theme)  # exercise the ANSI path too
        self.frames.append("\n".join("".join(r) for r in canvas.chars))

    def read_key(self, timeout=None):
        if not self.keys:
            raise RuntimeError("key script exhausted — UI did not exit")
        return self.keys.pop(0)


def seeded_db(tmp):
    """A DB with ~3 weeks of plausible history."""
    db = DB(tmp).load()
    today = dt.date.today()
    weight = {"Bench Press": 175.0, "Barbell Row": 155.0,
              "Back Squat": 225.0}
    day = 20
    while day > 0:
        date = (today - dt.timedelta(days=day)).isoformat()
        entries = []
        for name in weight:
            sets = [{"weight": weight[name], "reps": 8, "rir": 2.0,
                     "pain": 0, "difficulty": 6, "notes": ""}
                    for _ in range(3)]
            entries.append({"exercise": name, "target_sets": 3,
                            "target_reps": [6, 10], "target_rir": 2,
                            "sets": sets})
        db.data["history"].append({
            "date": date, "week": 1, "meso": 1, "day": "Test Day",
            "rir_label": "2 RIR", "completed": True,
            "checkin": {"sleep": 7.5, "stress": 3, "energy": 7,
                        "motivation": 7, "joint_pain": 1,
                        "calories": 2800, "protein": 180,
                        "bodyweight": 180.0},
            "post": {}, "entries": entries,
        })
        db.data["bodyweight_log"].append({"date": date, "weight": 180.0})
        for name in weight:
            weight[name] += 2.5
        day -= 3
    db.rebuild_records()
    db.save()
    return db


def test_compat():
    """Validate the pure-Python calendar math against CPython datetime."""
    print("[compat]")
    from rpts import compat
    d = dt.date(2020, 1, 1)
    ok = True
    for i in range(0, 3000, 7):  # ~8 years of weekly samples
        day = d + dt.timedelta(days=i)
        iso = day.isoformat()
        y, w, _ = day.isocalendar()
        if compat.iso_week(iso) != (y, w) or \
                compat.weekday(iso) != day.weekday() or \
                compat.date_add(iso, 13) != \
                (day + dt.timedelta(days=13)).isoformat():
            ok = False
            break
    check(ok, "date math matches datetime across 8 years")
    check(compat.week_key("2026-01-01") == "2026-W01", "ISO week edge")
    check(compat.week_key("2027-01-01") == "2026-W53", "ISO week-53 edge")
    check(compat.group_thousands(1234567.4) == "1,234,567",
          "thousands grouping")
    row = compat.csv_row(["a", 'he said "hi"', "x,y", 5])
    check(compat.csv_split(row) == ["a", 'he said "hi"', "x,y", "5"],
          "csv quoting round-trip")


def test_engine(tmp):
    print("[engine]")
    db = seeded_db(tmp)

    v = analytics.e1rm(185, 8, 2)
    check(abs(v - 185 * (1 + 10 / 30)) < 0.01, "e1RM Epley+RIR math")

    keys, vals = analytics.weekly_series(db, "tonnage")
    check(len(keys) >= 2 and all(v > 0 for v in vals),
          "weekly tonnage series")

    sc = coach.recovery_scores(db)
    check(all(0 <= sc[k] <= 100 for k in
              ("recovery", "muscular", "joint", "systemic", "readiness")),
          "recovery scores in range")

    slope = analytics.strength_trend(db)
    check(slope > 0, "rising weights detected as positive strength trend")

    plan = coach.plan_workout(db)
    check(plan["entries"], "plan has entries")
    bench = next(e for e in plan["entries"]
                 if e["exercise"] == "Bench Press")
    check(bench["suggested_weight"] is not None,
          "bench weight suggested from history")
    check(bench["target_rir"] == 3.0 and plan["rir_label"] == "3 RIR",
          "week 1 targets 3 RIR")

    rir, label = coach.target_rir(6, 6)
    check(label == "DELOAD", "week 6 of 6 is deload")
    labels = [coach.target_rir(w, 6)[1] for w in range(1, 6)]
    check(labels == ["3 RIR", "3 RIR", "2 RIR", "1 RIR", "0-1 RIR"],
          "RIR schedule 3/3/2/1/0-1: %s" % labels)

    # a PR session: heavier than anything before
    session = copy.deepcopy(db.data["history"][-1])
    session["date"] = dt.date.today().isoformat()
    for e in session["entries"]:
        for s in e["sets"]:
            s["weight"] += 20
    prs = analytics.detect_prs(db, session)
    check(any(p["kind"] == "e1RM PR" for p in prs), "e1RM PR detected")

    blocks, overall, updates = coach.analyze_session(db, session)
    check(blocks and overall and updates, "session analysis produced")
    check(any("Bench Press" == b["exercise"] for b in blocks),
          "analysis covers bench")

    # pain-driven swap
    for s2 in db.data["history"][-2:]:
        for e in s2["entries"]:
            if e["exercise"] == "Back Squat":
                for st in e["sets"]:
                    st["pain"] = 6
    alt = coach.swap_suggestion(db, "Back Squat")
    check(alt in ("Hack Squat", "Leg Press", "Safety Bar Squat",
                  "Goblet Squat"),
          "pain swap suggests alternative: %s" % alt)

    vs = coach.volume_status(db)
    check("chest" in vs and vs["chest"]["mrv"] > 0, "volume landmarks")

    path = db.export_csv()
    check(os.path.getsize(path) > 200, "CSV export written")
    n_before = len(db.data["history"])
    db.data["history"] = []
    db.import_csv(path)
    check(len(db.data["history"]) > 0, "CSV import round-trips")
    db.data["history"] = db.data["history"][:0]  # reset for cleanliness

    db2 = seeded_db(os.path.join(tmp, "kg"))
    b = db2.data["history"][0]["entries"][0]["sets"][0]["weight"]
    db2.convert_units("kg")
    b2 = db2.data["history"][0]["entries"][0]["sets"][0]["weight"]
    check(abs(b2 - b * 0.45359237) < 0.1, "unit conversion lb->kg")


def run_ui(db, keys, w=64, h=32):
    term = FakeTerm(keys, w, h)
    app = App(term, db)
    app.push(HomeScreen(app))
    app.run()
    return term.frames


def test_profiles(tmp):
    print("[profiles]")
    d = os.path.join(tmp, "prof")
    db = DB(d).load()
    check(db.active == "Athlete", "default profile is Athlete")
    check(db.list_profiles() == ["Athlete"], "lists the default profile")
    db.data["athlete"]["name"] = "Real"
    db.data["bodyweight_log"].append({"date": "2026-01-01", "weight": 200})
    db.data["settings"]["theme"] = "amber"
    db.save()

    db.create_profile("Demo")
    check(db.active == "Demo", "switched to the new Demo profile")
    check(db.data["settings"]["theme"] == "amber",
          "new profile inherits settings (theme)")
    check(db.data["athlete"]["name"] == "Athlete",
          "new profile has a fresh athlete")
    check(len(db.data["bodyweight_log"]) == 0, "new profile has no history")
    check(db.list_profiles() == ["Athlete", "Demo"], "both profiles listed")
    db.data["athlete"]["name"] = "Demo Person"
    db.save()

    db.switch_profile("Athlete")
    check(db.data["athlete"]["name"] == "Real", "Athlete data preserved")
    check(db.data["bodyweight_log"][0]["weight"] == 200,
          "Athlete history preserved after round-trip")

    db2 = DB(d).load()
    check(db2.active == "Athlete", "active profile persists across reload")
    check(db2.data["athlete"]["name"] == "Real", "reload restores active data")

    check(db.delete_profile("Demo") is True, "deleted Demo profile")
    check("Demo" not in db.list_profiles(), "Demo gone from the list")
    check(db.delete_profile("Athlete") is False,
          "cannot delete the active profile")

    # legacy migration: a flat root file becomes the Athlete profile, even
    # with another profile already present on the card
    import json as _json
    md = os.path.join(tmp, "migrate")
    os.makedirs(os.path.join(md, "profiles", "Demo"))
    with open(os.path.join(md, "profiles", "Demo", "rpts_data.json"),
              "w") as f:
        _json.dump({"athlete": {"name": "Demo"}}, f)
    with open(os.path.join(md, "rpts_data.json"), "w") as f:
        _json.dump({"athlete": {"name": "Legacy Me"}, "history": []}, f)
    mdb = DB(md).load()
    check(mdb.active == "Athlete", "post-migration active is Athlete")
    check(mdb.data["athlete"]["name"] == "Legacy Me",
          "legacy root data migrated into the Athlete profile")
    check("Demo" in mdb.list_profiles(),
          "pre-existing Demo profile survived migration")


def test_ui_navigation(tmp):
    print("[ui navigation]")
    db = seeded_db(os.path.join(tmp, "nav"))
    keys = []
    for hot in "rtckmgoax":
        keys += [hot, "ESC"]
    keys += ["q"]
    frames = run_ui(db, keys)
    text = "\n".join(frames)
    check("RP TRAINING SYSTEM" in text, "chrome title rendered")
    check("RECOVERY" in text, "recovery screen visited")
    check("TRENDS" in text, "trends screen visited")
    check("CALENDAR" in text, "calendar screen visited")
    check("PERSONAL RECORDS" in text, "records screen visited")
    check("MESOCYCLE" in text, "meso screen visited")
    check("GOALS" in text, "goals screen visited")
    check("PROGRAM" in text, "program editor visited")
    check("ATHLETES" in text, "athletes manager visited")
    check("SETTINGS" in text, "settings visited")

    # [A]thletes -> [E]dit opens the profile form
    frames = run_ui(db, ["a", "e", "ESC", "ESC", "q"])
    check("ATHLETE PROFILE" in "\n".join(frames),
          "edit-current opens the profile form")

    # create a new athlete through the UI: a -> n -> type name -> Enter
    db_c = seeded_db(os.path.join(tmp, "nav2"))
    run_ui(db_c, ["a", "n"] + list("Beta") + ["ENTER", "q"])
    check(db_c.active == "Beta", "UI created and switched to new athlete")
    check("Athlete" in db_c.list_profiles(),
          "original athlete still exists after UI create")

    # on-device the screen-family modules are unloaded when returning
    # home; force that path here and verify every screen still opens
    db_u = seeded_db(os.path.join(tmp, "nav3"))
    term = FakeTerm([], 53, 40)
    app = App(term, db_u)
    app.push(HomeScreen(app))
    home = app.stack[0]
    ok = True
    for hot, (fam, cls) in sorted(home._DASH.items()):
        home._open(fam, cls)
        app.build_frame()
        app.pop()                       # back home -> normally unloads
        app._unload_ui_modules(force=True)
        try:
            home._open(fam, cls)        # must re-import cleanly
            app.build_frame()
            app.pop()
            app._unload_ui_modules(force=True)
        except Exception:
            ok = False
            break
    check(ok, "every screen reopens after module unload (%s)" % cls)

    # graceful degradation: ascii + mono at PicoCalc-ish size
    db.data["settings"]["theme"] = "mono"
    db.data["settings"]["charset"] = "ascii"
    frames = run_ui(db, ["r", "ESC", "q"], w=53, h=24)
    check(all(ord(c) < 128 for c in frames[-1]),
          "ascii charset frame is 7-bit clean")


def test_ui_workout_flow(tmp):
    print("[ui workout flow]")
    db = DB(os.path.join(tmp, "flow")).load()
    keys = [
        "s",                    # start -> check-in
        "UP", "ENTER",          # check-in: jump to SAVE, submit
        "ENTER",                # workout: open set form
        "UP", "ENTER",          # set form: SAVE (defaults)
        "ENTER", "UP", "ENTER",  # second set
        "f",                    # finish -> post survey
        "UP", "ENTER",          # post: SAVE
        "ENTER",                # analysis -> continue
        "q",
    ]
    frames = run_ui(db, keys)
    text = "\n".join(frames)
    check("PRE-WORKOUT CHECK-IN" in text, "check-in shown")
    check("LOG SET" in text, "set form shown")
    check("SESSION ANALYSIS" in text, "analysis shown")
    check(len(db.data["history"]) == 1, "session persisted to history")
    check(analytics.session_sets(db.data["history"][0]) == 2,
          "both sets recorded")
    check(db.data.get("_active") is None, "active session cleared")
    check(db.data["meso"]["day_index"] == 1, "calendar advanced")
    check(db.data["prescriptions"], "prescriptions updated by coach")

    # resume path: pause mid-workout, then resume
    db2 = DB(os.path.join(tmp, "flow2")).load()
    keys = ["s", "UP", "ENTER",      # start, submit check-in
            "ENTER", "UP", "ENTER",  # one set
            "ESC", "y",              # pause (confirm)
            "q"]
    run_ui(db2, keys)
    check(db2.data.get("_active") is not None, "paused session persisted")
    db3 = DB(os.path.join(tmp, "flow2")).load()
    check(db3.data.get("_active") is not None,
          "paused session survives reload")


def test_workout_add_skip(tmp):
    print("[workout add/skip]")
    dba = DB(os.path.join(tmp, "add")).load()
    orig = len(coach.plan_workout(dba)["entries"])
    # start, submit check-in, ADD an exercise (SAVE with defaults), pause out
    frames = run_ui(dba, ["s", "UP", "ENTER",
                          "a", "UP", "ENTER",   # add-exercise form -> SAVE
                          "ESC", "y", "q"])
    check("ADD EXERCISE" in "\n".join(frames), "add-exercise form shown")
    active = dba.data.get("_active")
    check(active and len(active["entries"]) == orig + 1,
          "added exercise inserted into today's session")
    check(any(e.get("added") for e in active["entries"]),
          "added exercise is flagged as a one-off")

    dbs = DB(os.path.join(tmp, "skip")).load()
    orig2 = len(coach.plan_workout(dbs)["entries"])
    # add then skip the added one (0 sets -> no confirm), pause out
    run_ui(dbs, ["s", "UP", "ENTER",
                 "a", "UP", "ENTER",   # add
                 "x",                  # skip current (the added exercise)
                 "ESC", "y", "q"])
    active2 = dbs.data.get("_active")
    check(active2 and len(active2["entries"]) == orig2,
          "skip removed the added exercise from the session")


def test_inline_form():
    """Inline field editing: type straight into fields, no modal dialog."""
    print("[inline form]")
    from rpts.app import Field

    # numeric: typing replaces, clamps on commit
    f = Field("w", "Weight", "float", 180.0, lo=0, hi=2000)
    for c in "225":
        f.type_char(c)
    check(f.value == 225.0, "typing 225 sets value live (%s)" % f.value)
    f.type_char(".")
    f.type_char("5")
    f.commit()
    check(f.value == 225.5, "decimal typing -> 225.5 (%s)" % f.value)

    # int field: non-digits ignored, clamps to range on commit
    fi = Field("reps", "Reps", "int", 8, lo=1, hi=50)
    for c in "9a9":  # 'a' ignored
        fi.type_char(c)
    fi.commit()
    check(fi.value == 50, "int 99 clamps to hi=50 (%s)" % fi.value)

    # backspace edits the buffer
    fb = Field("x", "X", "int", 0, lo=0, hi=999)
    for c in "123":
        fb.type_char(c)
    fb.backspace()
    fb.commit()
    check(fb.value == 12, "backspace removes last digit -> 12 (%s)" %
          fb.value)

    # LEFT/RIGHT still nudges, and commits any pending typing first
    fn = Field("s", "Sets", "int", 3, lo=1, hi=8)
    fn.type_char("5")
    fn.adjust(1)   # commits 5, then +1
    check(fn.value == 6, "adjust after typing -> 6 (%s)" % fn.value)

    # choices: adjust cycles, typing jumps to a matching option
    fc = Field("u", "Units", "text", "lb", choices=["lb", "kg"])
    fc.adjust(1)
    check(fc.value == "kg", "adjust cycles choice")
    fc.type_char("l")
    check(fc.value == "lb", "typing 'l' jumps to lb")

    # cycle: a free-text field browsable with Left/Right, still typeable
    lib = ["Bench Press", "Deadlift", "Squat"]
    fy = Field("ex", "Exercise", "text", "Bench Press", cycle=lib)
    fy.adjust(1)
    check(fy.value == "Deadlift", "cycle steps forward through library")
    fy.adjust(-1)
    check(fy.value == "Bench Press", "cycle steps back")
    fy.type_char("Z")
    fy.commit()
    check(fy.value == "Z", "cycle field still accepts typed custom text")

    # word-wrap splits long intro text instead of clipping it
    from rpts.widgets import wrap
    ws = wrap("ordered by rp swap chain lower joint stress first", 20)
    check(all(len(s) <= 20 for s in ws) and len(ws) > 1,
          "wrap breaks long text into width-bounded lines")

    # text field: characters append
    ft = Field("note", "Note", "text", "")
    for c in "hi":
        ft.type_char(c)
    ft.type_char(" ")
    ft.commit()
    check(ft.value == "hi ", "text field appends chars (%r)" % ft.value)


def test_bytecanvas():
    """ByteCanvas (device) must render identically to Canvas (desktop)."""
    print("[bytecanvas]")
    from rpts.canvas import ByteCanvas, Canvas
    from rpts.themes import THEMES
    theme = THEMES["phosphor"]

    def draw(cv):
        cv.put(0, 0, "Header", "title")
        cv.put(2, 1, "value 183 lb", "hi")
        cv.fill(0, 2, 10, 1, "#", "good")
        cv.put(5, 2, "MID", "bad")
        cv.put(-2, 3, "clipL", "")      # clip left
        cv.put(46, 3, "clipRight", "")  # clip right

    a, b = Canvas(50, 5), ByteCanvas(50, 5)
    draw(a)
    draw(b)
    check(a.render(theme) == b.render(theme),
          "ByteCanvas render matches Canvas byte-for-byte")

    # clear() must fully reset (reused-buffer fast path)
    b.clear()
    b.put(0, 0, "X", "hi")
    b.clear()
    blank = ByteCanvas(50, 5)
    check(b.render(theme) == blank.render(theme),
          "ByteCanvas.clear resets every cell")

    # non-ascii glyphs fall back to ascii bytes (device is 7-bit)
    b.clear()
    b.put(0, 0, "█│★", "")  # block, vbar, star
    line = b.render(theme)[0]
    check(all(ord(c) < 128 for c in line), "ByteCanvas output is 7-bit")


def test_picoterm():
    """PicoCalc driver: key decoding + ANSI diff output, no hardware."""
    print("[picoterm]")
    import io
    from rpts.canvas import Canvas
    from rpts.picoterm import PicoVtTerm
    from rpts.themes import THEMES

    class FakeKbd:
        def __init__(self, chunks):
            self.chunks = list(chunks)

        def readinto(self, buf):
            if not self.chunks:
                return 0
            data = self.chunks.pop(0)
            buf[: len(data)] = data
            return len(data)

    class FakeVt:
        def get_screen_size(self):
            return [40, 53]

    kbd = FakeKbd([b"a", b"\r", b"\x1b[A", b"\x1b\x1b", b"\x1b[3~",
                   b"\x7f", b"\x1b[", b"C", b" "])
    t = PicoVtTerm(keyboard=kbd, terminal=FakeVt())
    # the key buffer must be a list, not a bytearray: MicroPython bytearray
    # has no item/slice deletion, which _decode relies on
    check(type(t._kbuf) is list, "key buffer is a list (del-able on upy)")
    check(t.size() == (53, 40), "reports 53x40 from vt emulator")
    got = [t.read_key(0.2) for _ in range(7)]
    check(got == ["a", "ENTER", "UP", "ESC", "DEL", "BS", "RIGHT"],
          "vt key decoding incl. split escape sequence: %s" % got)
    check(t.read_key(0.2) == "SPACE", "space maps to SPACE")

    # a lone ESC with nothing following must NOT freeze input: it should
    # time out to ESC rather than busy-loop forever waiting for a tail
    import time as _time
    t2 = PicoVtTerm(keyboard=FakeKbd([b"\x1b"]), terminal=FakeVt())
    start = _time.time()
    k = t2.read_key(0.3)
    check(k == "ESC", "stuck lone ESC flushes to ESC (was %r)" % k)
    check(_time.time() - start < 2.0, "stuck ESC returns promptly, no freeze")

    # an incomplete CSI ('ESC [ 1') that never completes also flushes
    t3 = PicoVtTerm(keyboard=FakeKbd([b"\x1b[1"]), terminal=FakeVt())
    check(t3.read_key(0.3) == "ESC", "incomplete CSI flushes to ESC")

    # a truly empty keyboard returns None on timeout (no hang)
    t4 = PicoVtTerm(keyboard=FakeKbd([]), terminal=FakeVt())
    check(t4.read_key(0.15) is None, "empty keyboard times out to None")

    out = io.StringIO()
    real, sys.stdout = sys.stdout, out
    try:
        cv = Canvas(53, 40)
        cv.put(2, 1, "HELLO", "hi")
        t.draw(cv, THEMES["mono"])
        first = out.getvalue()
        t.draw(cv, THEMES["mono"])  # identical frame -> no output
        second = out.getvalue()[len(first):]
    finally:
        sys.stdout = real
    check("\x1b[2;1H" in first and "HELLO" in first,
          "draw emits cursor-addressed rows")
    check(second == "", "unchanged frame emits nothing (diffed)")


def test_full_meso(tmp):
    """Simulate a complete 6-week mesocycle end to end (engine only)."""
    print("[full mesocycle]")

    def analytics_full_session(i):
        """A minimal FULL (set-level) session for migration tests."""
        return {
            "date": "2026-06-%02d" % (i + 1), "week": 1, "meso": 1,
            "day": "Legacy", "checkin": {}, "post": {}, "completed": True,
            "entries": [{"exercise": "Bench Press", "target_sets": 2,
                         "target_reps": [6, 10], "target_rir": 2,
                         "sets": [{"weight": 150, "reps": 8, "rir": 2,
                                   "pain": 0, "difficulty": 6, "notes": ""}
                                  for _ in range(2)]}],
        }
    db = DB(os.path.join(tmp, "meso")).load()
    start = dt.date.today() - dt.timedelta(days=6 * 7)
    day_n = 0
    deload_plans = []
    while db.data["meso"]["number"] == 1:
        plan = coach.plan_workout(db)
        plan["date"] = (start + dt.timedelta(days=day_n * 2)).isoformat()
        if plan["rir_label"] == "DELOAD":
            deload_plans.append(plan)
        for e in plan["entries"]:
            w = e.get("suggested_weight") or 100.0
            reps = (e["target_reps"][0] + e["target_reps"][1]) // 2
            e["sets"] = [{"weight": w, "reps": reps,
                          "rir": max(0.5, e["target_rir"]), "pain": 0,
                          "difficulty": 6, "notes": ""}
                         for _ in range(e["target_sets"])]
        plan["checkin"] = {"sleep": 7.5, "stress": 3, "energy": 7,
                           "motivation": 7, "joint_pain": 0}
        plan["post"] = {}
        analytics.detect_prs(db, plan)
        _, _, updates = coach.analyze_session(db, plan)
        plan["completed"] = True
        db.update_records(plan)
        db.commit_session(plan)
        coach.apply_updates(db, updates)
        coach.advance_calendar(db)
        day_n += 1
        assert day_n < 100, "meso never completed"
    check(day_n == 24, "6 weeks x 4 days completed (%d sessions)" % day_n)
    check(len(deload_plans) == 4, "week 6 sessions planned as deload")
    dl = deload_plans[0]["entries"][0]
    check(dl["target_sets"] <= 2, "deload halves set count")
    check(db.data["meso"]["number"] == 2 and db.data["meso"]["week"] == 1,
          "new mesocycle started after deload")
    bench = db.data["prescriptions"].get("Bench Press", {})
    check(bench.get("weight", 0) >= 100,
          "bench prescription progressed to %g" % bench.get("weight", 0))
    db.save()

    # live window is compact summaries; full sessions live in the archive
    check(all(s.get("summary") for s in db.data["history"]),
          "live window holds only summaries")
    check(sum(1 for _ in db.iter_all_sessions()) == day_n,
          "every full session is in the archive (%d)" % day_n)
    doc_bytes = len(json.dumps(db.data))
    check(doc_bytes < 40000,
          "live document stays small (%d bytes for %d sessions)" %
          (doc_bytes, day_n))
    # summarized history still feeds analytics identically
    hist = analytics.exercise_sessions(db, "Bench Press")
    check(len(hist) >= 5 and hist[-1]["best_e1rm"] > 0,
          "exercise history readable from summaries (%d found)" % len(hist))
    _, tons = analytics.weekly_series(db, "tonnage")
    check(len(tons) >= 5 and all(t > 0 for t in tons),
          "weekly tonnage series from summaries")

    # trimming the window drops summaries without losing archived data
    lifetime_before = db.data["records"]["lifetime"]
    db.archive_keep = 8
    db.archive_old()
    db.save()
    check(len(db.data["history"]) == 8, "history windowed to 8 in RAM")
    check(sum(1 for _ in db.iter_all_sessions()) == day_n,
          "archive still holds every session after trim")
    check(db.data["records"]["lifetime"] == lifetime_before,
          "records cache unaffected by trimming")
    db.rebuild_records()
    check(abs(db.data["records"]["lifetime"] - lifetime_before) < 0.01,
          "cache rebuild from archive matches")

    # legacy pre-summary profile migrates on load without losing sessions
    raw = DB(os.path.join(tmp, "legacy"))
    raw.load()
    for s in [analytics_full_session(d) for d in range(3)]:
        raw.data["history"].append(s)
    raw.save()
    mig = DB(os.path.join(tmp, "legacy")).load()
    check(all(s.get("summary") for s in mig.data["history"]),
          "legacy full history summarized on load")
    check(sum(1 for _ in mig.iter_all_sessions()) == 3,
          "migrated sessions preserved in archive")


def test_demo_gen(tmp):
    print("[demo generator]")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, os.path.join(root, "tools"))
    import gen_demo
    db = gen_demo.generate(os.path.join(tmp, "demo"), months=3, seed=1)
    check(db.active == "Demo", "generator leaves the Demo profile active")
    check(db.data["program"]["name"] == "Push Pull Legs", "demo uses PPL")
    total = sum(1 for _ in db.iter_all_sessions())
    check(total > 40, "demo has many sessions (%d)" % total)
    check(len(db.data["history"]) == 14, "demo live window matches device")
    check(all(s.get("summary") for s in db.data["history"]),
          "demo live window is summaries only")
    ck = db.data["history"][-1]["checkin"]
    check("calories" not in ck and "sleep" in ck,
          "summary check-ins slimmed to analytics fields")
    check(db.data["records"]["lifetime"] > 300000,
          "demo has a large lifetime tonnage")
    check(db.data["meso"]["number"] >= 2, "demo spans multiple mesocycles")
    check(len(db.data["bodyweight_log"]) > 20, "demo has a bodyweight log")
    check(len(db.data["swaps"]) >= 1, "demo logged an exercise swap")
    recs = analytics.all_records(db)
    dl = dict(recs).get("Deadlift", {}).get("e1rm", 0)
    rdl = dict(recs).get("Romanian Deadlift", {}).get("e1rm", 0)
    check(dl > rdl > 0, "demo loads are sane (deadlift e1RM > RDL)")
    db2 = DB(os.path.join(tmp, "demo")).load()
    check(db2.active == "Demo" and db2.data["history"],
          "demo profile reloads from disk")


def main():
    tmp = tempfile.mkdtemp(prefix="rpts_test_")
    try:
        test_compat()
        test_engine(os.path.join(tmp, "eng"))
        test_profiles(tmp)
        test_ui_navigation(tmp)
        test_ui_workout_flow(tmp)
        test_workout_add_skip(tmp)
        test_inline_form()
        test_bytecanvas()
        test_picoterm()
        test_full_meso(tmp)
        test_demo_gen(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\nALL %d CHECKS PASSED" % PASS)


if __name__ == "__main__":
    main()
