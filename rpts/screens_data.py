"""Dashboard screens: recovery, trends, calendar, records, mesocycle.

Editors live in rpts.screens_edit — the two families are separate modules
so the RP2040 only pays the RAM for the one actually opened (the app
unloads them again on returning to the home screen)."""
from . import analytics, coach, compat, widgets
from .app import Screen
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
        # TUNE-01: show what the coach has learned about this athlete
        cal = app.db.data.get("coach_cal") or {}
        if cal.get("n") and abs(cal.get("bias", 0)) >= 0.005:
            b = cal["bias"]
            word = "faster" if b > 0 else "slower"
            cv.put(3, y, widgets.clip(
                "calibration %+d%% - you recover %s than modeled (n=%d)"
                % (round(b * 100), word, cal["n"]), cv.w - 6), "dim")
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

    _CAP = 40  # sparklines are <=32 chars wide; longer series is wasted RAM

    def _series(self, pairs):
        return [v for _, v in pairs][-self._CAP:]

    def _build(self):
        db = self.app.db
        rows = []  # (label, values, unit)
        rows.append(("Sleep", self._series(
            analytics.checkin_series(db, "sleep")), "h"))
        rows.append(("Stress", self._series(
            analytics.checkin_series(db, "stress")), ""))
        rows.append(("Energy", self._series(
            analytics.checkin_series(db, "energy")), ""))
        rows.append(("Bodyweight",
                     [r["weight"] for r in
                      db.data["bodyweight_log"][-self._CAP:]],
                     self.app.units))
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
                if analytics.entry_nsets(e):
                    nm = analytics.entry_exercise(e)
                    counts[nm] = counts.get(nm, 0) + 1
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


