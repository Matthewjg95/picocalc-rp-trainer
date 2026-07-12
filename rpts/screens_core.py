"""Home dashboard — the instrument panel you see on boot.

The dashboard and workout screen modules are imported lazily (only when
the user opens them) so booting into the home screen keeps the largest UI
modules off the RP2040 heap until they're actually needed."""

from . import analytics, coach, compat, widgets
from .widgets import lj
from .app import Screen


class HomeScreen(Screen):
    hints = "[S]tart  [B] Bodyweight  [Q]uit"

    def render(self, cv):
        app, st = self.app, self.app.style
        db = app.db
        w, h = cv.w, cv.h
        iw = w - 4                      # inner content width of a full panel
        sc = coach.recovery_scores(db)
        bar_w = max(8, min(24, iw - 20))

        # -- STATUS (full width) ------------------------------------------
        widgets.frame(cv, 1, 1, w - 2, 7, st, title="STATUS")
        y = 2
        for label, val, hb in (("Recovery", sc["recovery"], True),
                               ("Fatigue", sc["muscular"], False),
                               ("Readiness", sc["readiness"], True),
                               ("MRV Used", sc["vol_load"], False)):
            pct = val / 100.0
            attr = widgets.health_attr(pct) if hb else widgets.load_attr(pct)
            widgets.gauge(cv, 3, y, label, pct, st, label_w=11, bar_w=bar_w,
                          attr=attr)
            y += 1
        a = db.data["athlete"]
        arrow, aattr = widgets.trend_arrow(sc["perf_trend"], st)
        cv.put(3, y, "Wt %.1f %s" % (a.get("bodyweight", 0), app.units), "")
        cv.put(19, y, "Sleep %.1f h" % sc["sleep_h"], "")
        cv.put(34, y, "Str " + arrow + " %+.1f%%" %
               (sc["perf_trend"] * 100), aattr)

        # -- NEXT SESSION (full width) ------------------------------------
        ny, nh = 8, 14
        widgets.frame(cv, 1, ny, w - 2, nh, st, title="NEXT SESSION")
        active = db.data.get("_active")
        if active:
            cv.put(3, ny + 1, "WORKOUT IN PROGRESS", "warn")
            cv.put(3, ny + 2, "%s  ·  %d sets logged" %
                   (active["day"], analytics.session_sets(active)), "hi")
            cv.put(3, ny + 4, "Press [S] to resume where you left off",
                   "dim")
        else:
            plan = coach.plan_workout(db)
            cv.put(3, ny + 1, "%s   ·   %s" %
                   (plan["day"], plan["rir_label"]), "hi")
            yy = ny + 3
            for e in plan["entries"]:
                if yy >= ny + nh - 1:
                    break
                cv.put(3, yy, widgets.clip(e["exercise"], 22), "")
                cv.put(26, yy, "%dx%d-%d" % (
                    e["target_sets"], e["target_reps"][0],
                    e["target_reps"][1]), "dim")
                sug = e.get("suggested_weight")
                if sug:
                    cv.put(w - 13, yy, "%6g" % sug, "hi")
                    d = e.get("suggested_delta") or 0
                    if d:
                        cv.put(w - 6, yy, "%s%+g" %
                               (st.arrow_up if d > 0 else st.arrow_dn, d),
                               "good" if d > 0 else "bad")
                yy += 1

        # -- COACH (full width, wrapped) ----------------------------------
        cy = ny + nh
        msg = coach.deload_recommendation(db)
        if not msg:
            if sc["recovery"] >= 70:
                msg = "Recovery is strong - a productive session awaits."
            elif sc["recovery"] >= 45:
                msg = "Recovery is middling. Train, but check the ego."
            else:
                msg = "Recovery poor - prioritize sleep and food today."
        mlines = widgets.wrap(st.bullet + " " + msg, iw)[:2]
        widgets.frame(cv, 1, cy, w - 2, len(mlines) + 2, st, title="COACH")
        for i, ml in enumerate(mlines):
            cv.put(3, cy + 1 + i, ml, "warn" if "eload" in msg else "good")

        # -- this week + menu --------------------------------------------
        my = cy + len(mlines) + 2
        today = compat.today()
        monday = compat.monday_of(today)
        trained = set()
        for s in db.data["history"]:
            trained.add(s["date"])
        # day-of-week letters on one row, the status markers on the row
        # BELOW them (previously the markers overwrote the letters)
        cv.put(3, my, "THIS WEEK", "dim")
        cv.put(14, my, "M  T  W  T  F  S  S", "dim")
        for d in range(7):
            iso = compat.date_add(monday, d)
            if iso in trained:
                ch, attr = st.blk_done, "good"
            elif iso == today:
                ch, attr = st.blk_miss, "inv"
            else:
                ch, attr = st.blk_rest, "dim"
            cv.put(14 + d * 3, my + 1, ch, attr)
        my += 3
        for line in ("[S]tart Workout      [B] Log Bodyweight",
                     "[R]ecovery [T]rends [C]alendar [K] PRs [M]eso",
                     "[G]oals [O]Program [A]thlete [X]Settings [Q]uit"):
            if my < h - 1:
                cv.put(3, my, line, "accent")
                my += 1

    # dashboard/editor hotkey -> class name in rpts.screens_data
    _DASH = {"r": "RecoveryScreen", "t": "TrendsScreen",
             "c": "CalendarScreen", "k": "RecordsScreen",
             "m": "MesoScreen", "g": "GoalsScreen",
             "o": "ProgramScreen", "a": "ProfileScreen",
             "x": "SettingsScreen"}

    def _open(self, cls_name):
        # import the dashboard module only on first use, to keep it off
        # the heap while the user is on the home screen
        from . import screens_data
        self.app.push(getattr(screens_data, cls_name)(self.app))

    def on_key(self, k):
        app = self.app
        kl = (k or "").lower()
        if kl == "s" or k == "ENTER":
            self.start_workout()
        elif kl in self._DASH:
            self._open(self._DASH[kl])
        elif kl == "b":
            t = app.prompt("Bodyweight (%s)" % app.units,
                           "%g" % app.db.data["athlete"].get("bodyweight",
                                                             0))
            if t:
                try:
                    v = float(t)
                except ValueError:
                    return
                db = app.db
                db.data["athlete"]["bodyweight"] = v
                log = db.data["bodyweight_log"]
                today = app.today()
                log[:] = [r for r in log if r["date"] != today]
                log.append({"date": today, "weight": v})
                db.save()
        elif kl == "q" or k == "ESC":
            app.running = False

    def start_workout(self):
        from .screens_workout import CheckinScreen, WorkoutScreen
        app = self.app
        active = app.db.data.get("_active")
        if active:
            app.push(WorkoutScreen(app, active))
        else:
            session = coach.plan_workout(app.db)
            app.push(CheckinScreen(app, session))
