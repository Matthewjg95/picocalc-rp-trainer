"""Dashboards and editors: recovery, trends, calendar, records, mesocycle,
athlete profile, program editor, goals, settings."""
from . import analytics, coach, compat, exercise_db, programs, widgets
from .app import Field, FormScreen, InfoScreen, Screen
from .compat import group_thousands
from .widgets import lj, rj


# -- recovery dashboard ------------------------------------------------------

class RecoveryScreen(Screen):
    title = "RECOVERY"
    hints = "[ESC] Back"

    def render(self, cv):
        app, st = self.app, self.app.style
        sc = coach.recovery_scores(app.db)
        bw = max(10, min(24, cv.w - 34))
        y = 2
        rows = [
            ("Recovery", sc["recovery"], True),
            ("Readiness", sc["readiness"], True),
            ("Musc Fatigue", sc["muscular"], False),
            ("Joint Stress", sc["joint"], False),
            ("Sys Fatigue", sc["systemic"], False),
        ]
        for label, val, higher_better in rows:
            pct = val / 100.0
            attr = widgets.health_attr(pct) if higher_better \
                else widgets.load_attr(pct)
            widgets.gauge(cv, 3, y, label, pct, st, label_w=13, bar_w=bw,
                          attr=attr)
            y += 2
        dl = coach.deload_recommendation(app.db)
        if dl:
            cv.put(3, y, widgets.clip(st.bullet + " " + dl, cv.w - 6),
                   "warn")
            y += 2

        # weekly volume vs landmarks
        widgets.frame(cv, 1, y, cv.w - 2, cv.h - y - 1, st,
                      title="WEEKLY SETS vs MEV/MAV/MRV")
        vy = y + 1
        vs = coach.volume_status(app.db)
        cols = 2 if cv.w >= 76 else 1
        colw = (cv.w - 4) // cols
        items = [(m, d) for m, d in vs.items()]
        half = (len(items) + cols - 1) // cols
        for c in range(cols):
            for r, (m, d) in enumerate(items[c * half:(c + 1) * half]):
                yy = vy + r
                if yy >= cv.h - 2:
                    break
                x = 3 + c * colw
                pct = d["sets"] / d["mrv"] if d["mrv"] else 0
                attr = widgets.load_attr(pct) if d["sets"] else "dim"
                cv.put(x, yy, lj(m[:10], 11), "")
                cv.put(x + 11, yy, widgets.bar(pct, 10, st), attr)
                cv.put(x + 22, yy, "%4.1f/%d %s" %
                       (d["sets"], d["mrv"], d["status"]), attr)


# -- trends -----------------------------------------------------------------

class TrendsScreen(Screen):
    title = "TRENDS"
    hints = "[Up/Dn] Scroll  [ESC] Back"

    def __init__(self, app):
        super().__init__(app)
        self.top = 0
        self.rows = self._build()

    def _series(self, pairs):
        return [v for _, v in pairs]

    def _build(self):
        db = self.app.db
        rows = []  # (label, values, unit)
        rows.append(("Sleep", self._series(
            analytics.checkin_series(db, "sleep")), "h"))
        rows.append(("Stress", self._series(
            analytics.checkin_series(db, "stress")), ""))
        rows.append(("Energy", self._series(
            analytics.checkin_series(db, "energy")), ""))
        rows.append(("Bodyweight", [w for _, w in
                     analytics.bodyweight_series(db)], self.app.units))
        _, ton = analytics.weekly_series(db, "tonnage")
        rows.append(("Wk Tonnage", ton, self.app.units))
        _, sets = analytics.weekly_series(db, "sets")
        rows.append(("Wk Sets", sets, ""))
        _, sess = analytics.weekly_series(db, "sessions")
        rows.append(("Wk Sessions", sess, ""))
        if sess:
            rows.append(("Density", [s / max(1, n) for s, n in
                                     zip(sets, sess)], "sets/wo"))
        # most-trained exercises' e1RM
        counts = {}
        for s in db.data["history"]:
            for e in s.get("entries", []):
                if e.get("sets"):
                    counts[e["exercise"]] = counts.get(e["exercise"], 0) + 1
        for name, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:5]:
            hist = analytics.exercise_sessions(db, name)
            rows.append(("e1RM " + name[:14],
                         [h["best_e1rm"] for h in hist], self.app.units))
        return [(l, v, u) for l, v, u in rows if v]

    def render(self, cv):
        app, st = self.app, self.app.style
        if not self.rows:
            cv.put(3, 3, "No telemetry yet — complete a workout first.",
                   "dim")
            return
        sw = min(app.spark_width(), cv.w - 42)
        y = 2
        for label, vals, unit in self.rows[self.top:]:
            if y >= cv.h - 2:
                break
            arrow, aattr = widgets.trend_arrow(
                analytics.trend_slope(vals[-8:]), st)
            cv.put(3, y, lj(label[:18], 19), "")
            cv.put(22, y, widgets.spark(vals, st, sw), "accent")
            last = vals[-1]
            txt = ("%s %s" % (group_thousands(last) if last >= 100
                              else "%.1f" % last, unit)).strip()
            cv.put(24 + sw, y, lj(txt, 12), "hi")
            cv.put(24 + sw + 13, y, arrow, aattr)
            y += 2

    def on_key(self, k):
        if k == "DOWN":
            self.top = min(max(0, len(self.rows) - 3), self.top + 1)
        elif k == "UP":
            self.top = max(0, self.top - 1)
        elif k == "ESC":
            self.app.pop()


# -- calendar -----------------------------------------------------------

class CalendarScreen(Screen):
    title = "CALENDAR"
    hints = "[ESC] Back"

    def render(self, cv):
        app, st = self.app, self.app.style
        db = app.db
        today = compat.today()
        trained = set()
        for s in db.data["history"]:
            trained.add(s["date"])
        monday = compat.monday_of(today)
        start = compat.date_add(monday, -7 * 7)
        cv.put(3, 2, "WEEK", "title")
        cv.put(10, 2, "M  T  W  T  F  S  S", "title")
        cv.put(33, 2, "SESSIONS", "title")
        y = 3
        for wk in range(8):
            wstart = compat.date_add(start, wk * 7)
            _, isow = compat.iso_week(wstart)
            cv.put(3, y, "W%02d" % isow,
                   "hi" if wstart == monday else "dim")
            count = 0
            for d in range(7):
                iso = compat.date_add(wstart, d)
                if iso in trained:
                    ch, attr = st.blk_done, "good"
                    count += 1
                elif iso > today:
                    ch, attr = " ", ""
                elif iso == today:
                    ch, attr = st.blk_miss, "inv"
                else:
                    ch, attr = st.blk_rest, "dim"
                cv.put(10 + d * 3, y, ch, attr)
            if count:
                cv.put(33, y, str(count), "good")
            y += 1

        y += 1
        meso = db.data["meso"]
        widgets.frame(cv, 1, y, cv.w - 2, 6, st, title="MESOCYCLE")
        pct = ((meso["week"] - 1) * len(db.data["program"]["days"])
               + meso["day_index"]) / max(
            1, meso["weeks"] * len(db.data["program"]["days"]))
        cv.put(3, y + 1, "MESO %d PROGRESS" % meso["number"], "")
        cv.put(22, y + 1, widgets.bar(pct, min(30, cv.w - 30), st),
               "accent")
        rir, label = coach.target_rir(meso["week"], meso["weeks"])
        cv.put(3, y + 2, "CURRENT   Week %d — %s" % (meso["week"], label),
               "hi")
        to_deload = meso["weeks"] - meso["week"]
        cv.put(3, y + 3, "DELOAD    %s" %
               ("THIS WEEK" if to_deload <= 0 else
                "in %d week%s" % (to_deload, "s" if to_deload > 1 else "")),
               "warn" if to_deload <= 1 else "dim")
        cv.put(3, y + 4, "NEXT UP   %s" % db.data["program"]["days"][
            meso["day_index"] % len(db.data["program"]["days"])]["name"],
            "accent")


# -- records ------------------------------------------------------------

class RecordsScreen(Screen):
    title = "PERSONAL RECORDS"
    hints = "[Up/Dn] Scroll  [ESC] Back"

    def __init__(self, app):
        super().__init__(app)
        self.top = 0
        self.recs = analytics.all_records(app.db)

    def render(self, cv):
        app, st = self.app, self.app.style
        u = app.units
        cv.put(3, 2, "EXERCISE", "title")
        cv.put(25, 2, rj("e1RM", 5), "title")
        cv.put(32, 2, "BEST SET", "title")
        cv.put(45, 2, rj("SESS VOL", 9), "title")
        y = 3
        for name, r in self.recs[self.top:]:
            if y >= cv.h - 6:
                break
            cv.put(3, y, lj(widgets.clip(name, 21), 22), "")
            cv.put(25, y, "%5.0f" % r["e1rm"], "hi")
            cv.put(32, y, "%g x %d" % (r["reps_weight"], r["reps"]), "")
            cv.put(45, y, rj(group_thousands(r["tonnage"]), 9), "dim")
            y += 1
        if not self.recs:
            cv.put(3, 4, "No records yet — go lift something.", "dim")

        # lifetime tonnage milestone bar
        total = analytics.lifetime_tonnage(app.db)
        scale = 1.0 if u == "lb" else 0.5
        nxt = analytics.TONNAGE_MILESTONES_LB[-1] * scale
        for m in analytics.TONNAGE_MILESTONES_LB:
            if m * scale > total:
                nxt = m * scale
                break
        yb = cv.h - 4
        widgets.frame(cv, 1, yb - 1, cv.w - 2, 4, st,
                      title="LIFETIME TONNAGE")
        cv.put(3, yb, "%s %s lifted" % (group_thousands(total), u), "hi")
        cv.put(3, yb + 1, widgets.bar(total / nxt if nxt else 0,
                                      min(34, cv.w - 30), st), "accent")
        cv.put(min(38, cv.w - 26) + 2, yb + 1,
               "next: %s" % group_thousands(nxt), "dim")

    def on_key(self, k):
        if k == "DOWN":
            self.top = min(max(0, len(self.recs) - 3), self.top + 1)
        elif k == "UP":
            self.top = max(0, self.top - 1)
        elif k == "ESC":
            self.app.pop()


# -- mesocycle manager --------------------------------------------------------

class MesoScreen(Screen):
    title = "MESOCYCLE"
    hints = "[W]Len [S]kip [N]ew Meso [ESC] Back"

    def render(self, cv):
        app, st = self.app, self.app.style
        meso = app.db.data["meso"]
        prog = app.db.data["program"]
        cv.put(3, 2, "MESO %d  ·  started %s  ·  program: %s" %
               (meso["number"], meso.get("started", "?"),
                prog.get("name", "custom")), "accent")
        y = 4
        cv.put(3, y, "WEEK   TARGET     STATUS", "title")
        y += 1
        for wk in range(1, meso["weeks"] + 1):
            _, label = coach.target_rir(wk, meso["weeks"])
            cur = wk == meso["week"]
            mark = st.bullet + " CURRENT" if cur else (
                "done" if wk < meso["week"] else "")
            attr = "inv" if cur else ("dim" if wk < meso["week"] else "")
            cv.put(3, y, lj(" WK %d   %-9s  %s" % (wk, label, mark),
                            min(40, cv.w - 6)), attr)
            y += 1
        y += 1
        days = prog["days"]
        cv.put(3, y, "NEXT SESSION  %s (day %d/%d of week)" %
               (days[meso["day_index"] % len(days)]["name"],
                meso["day_index"] + 1, len(days)), "hi")
        y += 2
        dl = coach.deload_recommendation(app.db)
        if dl:
            cv.put(3, y, widgets.clip(st.bullet + " " + dl, cv.w - 6),
                   "warn")

    def on_key(self, k):
        app = self.app
        kl = (k or "").lower()
        meso = app.db.data["meso"]
        if kl == "w":
            t = app.prompt("Mesocycle length in weeks (4-8)",
                           str(meso["weeks"]))
            if t and t.isdigit() and 4 <= int(t) <= 8:
                meso["weeks"] = int(t)
                app.db.save()
        elif kl == "s":
            if app.confirm("Skip ahead one training day?"):
                coach.advance_calendar(app.db)
                app.db.save()
        elif kl == "n":
            if app.confirm("Start a fresh mesocycle now?"):
                meso["number"] += 1
                meso["week"] = 1
                meso["day_index"] = 0
                meso["started"] = app.today()
                app.db.save()
        elif k == "ESC":
            app.pop()


# -- athlete profile -------------------------------------------------------

class ProfileScreen(FormScreen):
    def __init__(self, app):
        a = app.db.data["athlete"]
        fields = [
            Field("name", "Name", "text", a.get("name", "")),
            Field("age", "Age", "int", a.get("age", 30), lo=10, hi=100),
            Field("sex", "Sex", "text", a.get("sex", "M"),
                  choices=["M", "F"]),
            Field("height_in", "Height (in)", "float",
                  a.get("height_in", 70), lo=36, hi=96, step=0.5),
            Field("bodyweight", "Bodyweight", "float",
                  a.get("bodyweight", 180), lo=0, hi=1000, step=0.2,
                  suffix=app.units),
            Field("goal_weight", "Goal weight", "float",
                  a.get("goal_weight", 180), lo=0, hi=1000, step=0.5,
                  suffix=app.units),
            Field("experience", "Experience", "text",
                  a.get("experience", "intermediate"),
                  choices=["beginner", "intermediate", "advanced"]),
            Field("injuries", "Injuries", "text", a.get("injuries", "")),
            Field("equipment", "Equipment (csv)", "text",
                  ",".join(a.get("equipment", []))),
        ]
        super().__init__(app, "ATHLETE PROFILE", fields,
                         intro=["Experience level scales your MEV/MAV/MRV "
                                "landmarks."])

    def submit(self):
        vals = self.values()
        vals["equipment"] = [e.strip() for e in
                             str(vals["equipment"]).split(",") if e.strip()]
        self.app.db.data["athlete"].update(vals)
        self.app.db.save()
        self.app.pop()


# -- program editor ------------------------------------------------------

class ProgramScreen(Screen):
    title = "PROGRAM"
    hints = "[Enter] Edit Day  [T] Template  [ESC] Back"

    def __init__(self, app):
        super().__init__(app)
        self.sel = 0

    def render(self, cv):
        app, st = self.app, self.app.style
        prog = app.db.data["program"]
        cv.put(3, 2, "SPLIT: %s   (%d days/cycle)" %
               (prog.get("name", "custom"), len(prog["days"])), "accent")
        y = 4
        for i, day in enumerate(prog["days"]):
            sel = i == self.sel
            n_ex = len(day["exercises"])
            n_sets = sum(s["sets"] for s in day["exercises"])
            row = "%s %-14s %2d exercises  %2d sets" % (
                st.bullet if sel else " ", day["name"], n_ex, n_sets)
            cv.put(3, y, widgets.clip(row, cv.w - 6), "inv" if sel else "")
            y += 1
            if sel:
                for slot in day["exercises"][:6]:
                    cv.put(6, y, widgets.clip(
                        "%s  %dx%d-%d" % (slot["exercise"], slot["sets"],
                                          slot["reps"][0], slot["reps"][1]),
                        cv.w - 10), "dim")
                    y += 1

    def on_key(self, k):
        app = self.app
        days = app.db.data["program"]["days"]
        kl = (k or "").lower()
        if k == "DOWN":
            self.sel = (self.sel + 1) % len(days)
        elif k == "UP":
            self.sel = (self.sel - 1) % len(days)
        elif k == "ENTER":
            app.push(DayScreen(app, self.sel))
        elif kl == "t":
            names = list(programs.TEMPLATES) + ["Custom"]
            cur = app.db.data["program"].get("name", "Custom")
            i = (names.index(cur) + 1) if cur in names else 0
            nxt = names[i % len(names)]
            if app.confirm("Replace program with '%s' template?" % nxt):
                app.db.data["program"] = programs.make_program(nxt)
                app.db.data["meso"]["day_index"] = 0
                app.db.save()
                self.sel = 0
        elif k == "ESC":
            app.pop()


class DayScreen(Screen):
    hints = "[Ent]Edit [A]dd [D]el [W]Swap [R]ename [ESC]"

    def __init__(self, app, day_idx):
        super().__init__(app)
        self.day_idx = day_idx
        self.sel = 0

    @property
    def day(self):
        return self.app.db.data["program"]["days"][self.day_idx]

    def render(self, cv):
        st = self.app.style
        self.title = self.day["name"].upper()
        cv.put(2, 0, "", "")  # title drawn by chrome
        y = 2
        cv.put(3, y, lj("EXERCISE", 26) + "SETS  REPS    TEMPO", "title")
        y += 1
        for i, slot in enumerate(self.day["exercises"]):
            sel = i == self.sel
            row = "%s %-25s %2d   %2d-%-3d  %s" % (
                st.bullet if sel else " ", widgets.clip(slot["exercise"], 24),
                slot["sets"], slot["reps"][0], slot["reps"][1],
                slot.get("tempo", ""))
            cv.put(3, y, widgets.clip(row, cv.w - 6), "inv" if sel else "")
            y += 1
        if not self.day["exercises"]:
            cv.put(3, y, "Empty day — press A to add an exercise.", "dim")
        else:
            slot = self.day["exercises"][self.sel]
            info = exercise_db.info(slot["exercise"])
            y += 1
            cv.put(3, y, widgets.clip(
                "targets: %s   joint stress %.0f%%   alts: %s" % (
                    "+".join(info["primary"]), info["joint"] * 100,
                    ", ".join(info["alts"][:3]) or "none"),
                cv.w - 6), "dim")

    def on_key(self, k):
        app, day = self.app, self.day
        kl = (k or "").lower()
        n = len(day["exercises"])
        if k == "DOWN" and n:
            self.sel = (self.sel + 1) % n
        elif k == "UP" and n:
            self.sel = (self.sel - 1) % n
        elif k == "ENTER" and n:
            app.push(SlotForm(app, day, self.sel))
        elif kl == "a":
            day["exercises"].append(programs.slot("Bench Press"))
            self.sel = n
            app.push(SlotForm(app, day, self.sel))
        elif kl == "d" and n:
            if app.confirm("Remove %s from this day?" %
                           day["exercises"][self.sel]["exercise"]):
                day["exercises"].pop(self.sel)
                self.sel = max(0, self.sel - 1)
                app.db.save()
        elif kl == "w" and n:
            self.swap_current()
        elif kl == "r":
            t = app.prompt("Day name", day["name"])
            if t:
                day["name"] = t
                app.db.save()
        elif k == "ESC":
            app.pop()

    def swap_current(self):
        app, day, sel = self.app, self.day, self.sel
        old = day["exercises"][sel]["exercise"]
        chain = exercise_db.swap_chain(
            old, set(app.db.data["athlete"].get("equipment", [])) or None)
        if not chain:
            app.push(InfoScreen(app, "SWAP", [
                ("No catalogued alternatives for %s." % old, "warn"),
                ("Use [Enter] Edit to type any exercise name.", "dim")]))
            return
        f = Field("alt", "Swap to", "text", chain[0], choices=chain)

        def apply(vals):
            day["exercises"][sel]["exercise"] = vals["alt"]
            app.db.data["swaps"].append({
                "date": app.today(), "from": old, "to": vals["alt"],
                "reason": "manual"})
            app.db.save()

        app.push(FormScreen(app, "SWAP %s" % old.upper(), [f],
                            on_submit=apply,
                            intro=["Ordered by RP swap chain (lower joint "
                                   "stress first)."]))


class SlotForm(FormScreen):
    def __init__(self, app, day, idx):
        self.day, self.idx = day, idx
        slot = day["exercises"][idx]
        library = sorted(exercise_db.EXERCISES)
        fields = [
            Field("exercise", "Exercise", "text", slot["exercise"],
                  cycle=library),
            Field("sets", "Sets", "int", slot["sets"], lo=1, hi=8),
            Field("lo", "Reps low", "int", slot["reps"][0], lo=1, hi=50),
            Field("hi", "Reps high", "int", slot["reps"][1], lo=1, hi=50),
            Field("tempo", "Tempo", "text", slot.get("tempo", "2-0-1")),
            Field("notes", "Notes", "text", slot.get("notes", "")),
        ]
        super().__init__(app, "EDIT EXERCISE", fields,
                         intro=["Exercise: Left/Right browses the library, "
                                "or type any name."])

    def submit(self):
        vals = self.values()
        name = str(vals["exercise"]).strip()
        match = None
        for n in exercise_db.EXERCISES:
            if n.lower() == name.lower():
                match = n
                break
        if not match:
            subs = [n for n in exercise_db.EXERCISES
                    if name.lower() in n.lower()]
            match = subs[0] if len(subs) == 1 else None
        slot = self.day["exercises"][self.idx]
        slot["exercise"] = match or name
        slot["sets"] = vals["sets"]
        slot["reps"] = [min(vals["lo"], vals["hi"]),
                        max(vals["lo"], vals["hi"])]
        slot["tempo"] = vals["tempo"]
        slot["notes"] = vals["notes"]
        self.app.db.save()
        self.app.pop()


# -- goals ------------------------------------------------------------------

class GoalsScreen(Screen):
    title = "GOALS"
    hints = "[E] Edit  [ESC] Back"

    def render(self, cv):
        app, st = self.app, self.app.style
        db = app.db
        goals = db.data["goals"]
        a = db.data["athlete"]
        u = app.units
        cv.put(3, 2, "GOAL TYPE   %s" % goals.get("type", "-").upper(),
               "hi")
        if goals.get("note"):
            cv.put(3, 3, widgets.clip("NOTE        " + goals["note"],
                                      cv.w - 6), "dim")
        y = 5
        # bodyweight vs goal
        bws = analytics.bodyweight_series(db)
        cur = bws[-1][1] if bws else a.get("bodyweight", 0)
        start = bws[0][1] if bws else cur
        goal = a.get("goal_weight", cur)
        widgets.frame(cv, 1, y, cv.w - 2, 5, st, title="BODYWEIGHT")
        span = goal - start
        pct = (cur - start) / span if abs(span) > 0.01 else 1.0
        cv.put(3, y + 1, "%.1f %s  ->  goal %.1f %s   (started %.1f)" %
               (cur, u, goal, u, start), "")
        cv.put(3, y + 2, widgets.bar(max(0, min(1, pct)),
                                     min(36, cv.w - 20), st),
               widgets.health_attr(max(0.0, min(1.0, pct))))
        cv.put(3, y + 3, "%d%% of the way there" %
               round(max(0, min(1, pct)) * 100), "dim")
        y += 6
        # strength trend vs goal expectations
        slope = analytics.strength_trend(db)
        verdicts = []
        gtype = goals.get("type", "hypertrophy")
        if slope > 0.004:
            verdicts.append(("Strength rising %.1f%%/session, on track "
                             "for %s." % (slope * 100, gtype), "good"))
        elif slope < -0.004:
            verdicts.append(("Strength falling — recovery or volume needs "
                             "attention.", "bad"))
        else:
            verdicts.append(("Strength flat — normal mid-meso, watch the "
                             "trend.", "warn"))
        if gtype in ("weight loss", "recomp") and len(bws) >= 2:
            rate = (bws[-1][1] - bws[0][1])
            verdicts.append(("Bodyweight change since start: %+.1f %s." %
                             (rate, u), "" ))
        vs = coach.volume_status(db)
        low = [m for m, d in vs.items() if d["sets"] and d["status"] == "< MEV"]
        if low:
            verdicts.append(("Below MEV: %s — too little volume to grow." %
                             ", ".join(low[:4]), "warn"))
        # wrap each verdict so nothing gets cut off, then size the frame
        disp = []
        for t, attr in verdicts[:4]:
            wl = widgets.wrap(st.bullet + " " + t, cv.w - 6)
            for j, line in enumerate(wl):
                disp.append(((line if j == 0 else "  " + line), attr))
        fh = min(len(disp) + 2, cv.h - y - 1)
        widgets.frame(cv, 1, y, cv.w - 2, fh, st, title="PROGRESS CHECK")
        for i, (line, attr) in enumerate(disp):
            if i >= fh - 2:
                break
            cv.put(3, y + 1 + i, line, attr)

    def on_key(self, k):
        app = self.app
        if (k or "").lower() == "e":
            goals = app.db.data["goals"]
            fields = [
                Field("type", "Goal type", "text",
                      goals.get("type", "hypertrophy"),
                      choices=["strength", "hypertrophy", "weight loss",
                               "recomp", "custom"]),
                Field("goal_weight", "Goal bodyweight", "float",
                      app.db.data["athlete"].get("goal_weight", 180),
                      lo=0, hi=1000, step=0.5, suffix=app.units),
                Field("note", "Note", "text", goals.get("note", "")),
            ]

            def apply(vals):
                goals["type"] = vals["type"]
                goals["note"] = vals["note"]
                app.db.data["athlete"]["goal_weight"] = vals["goal_weight"]
                app.db.save()

            app.push(FormScreen(app, "EDIT GOALS", fields, on_submit=apply))
        elif k == "ESC":
            app.pop()


# -- settings ---------------------------------------------------------------

class SettingsScreen(FormScreen):
    hints = "[B]ackup [R]estore [E]xport [I]mport [Ent]Save"

    def __init__(self, app):
        s = app.db.data["settings"]
        fields = [
            Field("units", "Units", "text", s.get("units", "lb"),
                  choices=["lb", "kg"]),
            Field("theme", "Theme", "text", s.get("theme", "phosphor"),
                  choices=["phosphor", "amber", "cyan", "white", "mono"]),
            Field("charset", "ASCII density", "text",
                  s.get("charset", "unicode"),
                  choices=["unicode", "ascii"]),
            Field("graph_detail", "Graph detail", "text",
                  s.get("graph_detail", "high"), choices=["high", "low"]),
            Field("coach_verbosity", "Coach verbosity", "text",
                  s.get("coach_verbosity", "normal"),
                  choices=["terse", "normal", "verbose"]),
        ]
        super().__init__(app, "SETTINGS", fields,
                         intro=["Theme and charset apply instantly on "
                                "save. Unit change converts all data."])

    def submit(self):
        vals = self.values()
        db = self.app.db
        new_units = vals.pop("units")
        db.data["settings"].update(vals)
        if new_units != db.data["settings"]["units"]:
            db.convert_units(new_units)
        db.save()
        self.app.pop()

    def on_key(self, k):
        app = self.app
        kl = (k or "").lower()
        if kl == "b":
            path = app.db.backup()
            app.push(InfoScreen(app, "BACKUP", [
                ("Backup written:", "good"), (path, "dim")]))
        elif kl == "r":
            if app.confirm("Restore the most recent backup?"):
                src = app.db.restore_latest_backup()
                app.push(InfoScreen(app, "RESTORE", [
                    ("Restored from:" if src else "No backups found.",
                     "good" if src else "warn"), (src or "", "dim")]))
        elif kl == "e":
            path = app.db.export_csv()
            app.push(InfoScreen(app, "EXPORT", [
                ("CSV exported:", "good"), (path, "dim")]))
        elif kl == "i":
            path = app.prompt("CSV path to import")
            if path:
                try:
                    n = app.db.import_csv(path)
                    app.push(InfoScreen(app, "IMPORT", [
                        ("Imported %d session(s)." % n, "good")]))
                except OSError as ex:
                    app.push(InfoScreen(app, "IMPORT", [
                        ("Import failed: %s" % ex, "bad")]))
        else:
            super().on_key(k)
