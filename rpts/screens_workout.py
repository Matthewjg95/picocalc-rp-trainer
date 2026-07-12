"""Workout flow: pre-workout check-in, live set logging,
post-workout survey, coach analysis, PR celebration."""
from . import analytics, coach, compat, widgets
from .app import Field, FormScreen, Screen
from .widgets import lj


# -- pre-workout check-in ---------------------------------------------------

class CheckinScreen(FormScreen):
    def __init__(self, app, session):
        bw = app.db.data["athlete"].get("bodyweight", 0)
        fields = [
            Field("sleep", "Hours slept", "float", 7.5, lo=0, hi=14,
                  step=0.5, suffix="h"),
            Field("stress", "Stress (0-10)", "int", 4, lo=0, hi=10),
            Field("energy", "Energy (0-10)", "int", 6, lo=0, hi=10),
            Field("motivation", "Motivation (0-10)", "int", 6, lo=0, hi=10),
            Field("joint_pain", "Joint pain (0-10)", "int", 0, lo=0, hi=10),
            Field("calories", "Calories yesterday", "int", 0, lo=0,
                  hi=12000, step=100, suffix="kcal"),
            Field("protein", "Protein yesterday", "int", 0, lo=0, hi=500,
                  step=10, suffix="g"),
            Field("bodyweight", "Bodyweight", "float", bw, lo=0, hi=1000,
                  step=0.2, suffix=app.units),
        ]
        super().__init__(app, "PRE-WORKOUT CHECK-IN", fields,
                         intro=["These answers drive today's coaching "
                                "and future volume decisions."])
        self.session = session

    def submit(self):
        vals = self.values()
        app, db = self.app, self.app.db
        self.session["checkin"] = vals
        if vals.get("bodyweight"):
            db.data["athlete"]["bodyweight"] = vals["bodyweight"]
            log = db.data["bodyweight_log"]
            today = app.today()
            log[:] = [r for r in log if r["date"] != today]
            log.append({"date": today, "weight": vals["bodyweight"]})
        db.data["_active"] = self.session
        db.save()
        app.pop()
        app.push(WorkoutScreen(app, self.session))


# -- live workout ----------------------------------------------------------

class WorkoutScreen(Screen):
    hints = "[Ent]Log [U]ndo [N/P]Ex [A]dd [X]Skip [F]in"
    # no tick: redraw only on a keypress (the rest timer that needed a
    # per-second redraw was removed to keep the screen calm and stable)

    def __init__(self, app, session):
        super().__init__(app)
        self.session = session
        self.title = session["day"]
        self.ex_idx = 0
        for i, e in enumerate(session["entries"]):
            if len(e["sets"]) < e["target_sets"]:
                self.ex_idx = i
                break

    @property
    def entry(self):
        return self.session["entries"][self.ex_idx]

    def render(self, cv):
        st, app = self.app.style, self.app
        s = self.session
        n = len(s["entries"])
        cv.put(2, 1, "WEEK %d  ·  TARGET %s  ·  EXERCISE %d/%d" %
               (s["week"], s["rir_label"], self.ex_idx + 1, n), "accent")

        # current exercise panel
        e = self.entry
        ph = max(9, min(cv.h - 12, e["target_sets"] + 9))
        widgets.frame(cv, 1, 3, cv.w - 2, ph, st, title=e["exercise"])
        y = 4
        sug = e.get("suggested_weight")
        delta = e.get("suggested_delta") or 0
        parts = "TARGET  %d x %d-%d  @ RIR %g" % (
            e["target_sets"], e["target_reps"][0], e["target_reps"][1],
            e["target_rir"])
        cv.put(3, y, parts, "hi")
        if sug:
            tail = "%g %s" % (sug, app.units)
            if delta:
                tail += "  %s%+g" % (st.arrow_up if delta > 0
                                     else st.arrow_dn, delta)
            cv.put(cv.w - len(tail) - 4, y,
                   tail, "good" if delta > 0 else ("bad" if delta < 0
                                                   else "hi"))
        y += 1
        if e.get("tempo"):
            cv.put(3, y, "TEMPO %s" % e["tempo"], "dim")
            y += 1
        reason = e.get("suggestion_reason", "")
        if reason:
            # own full-width line(s) so the coach note is never cut off
            for rl in widgets.wrap(reason, cv.w - 6)[:2]:
                cv.put(3, y, rl, "dim")
                y += 1
        y += 1
        for i in range(max(e["target_sets"], len(e["sets"]))):
            if y >= 3 + ph - 1:
                break
            if i < len(e["sets"]):
                x = e["sets"][i]
                row = "%2d  %6g x %-2d   RIR %-3g" % (
                    i + 1, x.get("weight", 0), x.get("reps", 0),
                    x.get("rir", 0))
                cv.put(3, y, row, "")
                if x.get("pain", 0) >= 3:
                    cv.put(3 + len(row) + 2, y,
                           "PAIN %g" % x["pain"], "bad")
                cv.put(cv.w - 8, y, "DONE", "good")
            else:
                cv.put(3, y, "%2d  %s pending" % (i + 1, st.blk_rest), "dim")
            y += 1

        # session ticker + upcoming
        yb = 3 + ph + 1
        ton = analytics.session_tonnage(s)
        nsets = analytics.session_sets(s)
        cv.put(2, yb, "SESSION  TONNAGE %s %s   SETS %d" %
               (compat.group_thousands(ton), app.units, nsets), "accent")
        yb += 2
        remaining = n - 1 - self.ex_idx
        cv.put(2, yb, "UP NEXT" + (" (%d more)" % remaining
                                   if remaining > 0 else ""), "title")
        yb += 1
        # show every remaining exercise that fits (wrapping past the end of
        # the list back to the ones before the current, so the whole day is
        # visible), bounded by the bottom of the screen
        for off in range(1, n):
            if yb >= cv.h - 2:
                break
            nxt = s["entries"][(self.ex_idx + off) % n]
            done = len(nxt["sets"]) >= nxt["target_sets"]
            cv.put(4, yb, widgets.clip("%s %s  %dx%d-%d" % (
                st.blk_done if done else st.blk_miss, nxt["exercise"],
                nxt["target_sets"], nxt["target_reps"][0],
                nxt["target_reps"][1]), cv.w - 8),
                "dim" if done else "")
            yb += 1

    def on_key(self, k):
        kl = (k or "").lower()
        if k in ("ENTER", "SPACE"):
            self.log_set()
        elif kl == "u":
            if self.entry["sets"]:
                self.entry["sets"].pop()
                self.autosave()
        elif kl == "n" or k == "RIGHT":
            self.ex_idx = (self.ex_idx + 1) % len(self.session["entries"])
        elif kl == "p" or k == "LEFT":
            self.ex_idx = (self.ex_idx - 1) % len(self.session["entries"])
        elif kl == "a":
            self.add_exercise()
        elif kl == "x":
            self.skip_exercise()
        elif kl == "f":
            if analytics.session_sets(self.session) == 0:
                if self.app.confirm("No sets logged. Discard this workout?"):
                    self.app.db.data.pop("_active", None)
                    self.app.db.save()
                    self.app.pop()
                return
            self.app.push(PostScreen(self.app, self.session))
        elif k == "ESC":
            if self.app.confirm("Pause workout? Progress is saved."):
                self.app.pop()

    def add_exercise(self):
        """Insert an extra exercise into today's session (after the current
        one). Doesn't touch the saved program — it's a one-off for today."""
        from . import exercise_db
        app = self.app
        library = sorted(exercise_db.EXERCISES)
        fields = [
            Field("exercise", "Exercise", "text", library[0], cycle=library),
            Field("sets", "Sets", "int", 3, lo=1, hi=8),
            Field("lo", "Reps low", "int", 8, lo=1, hi=50),
            Field("hi", "Reps high", "int", 12, lo=1, hi=50),
        ]
        me = self

        def apply(vals):
            name = str(vals["exercise"]).strip()
            if not name:
                return
            meso = app.db.data["meso"]
            rir, _ = coach.target_rir(me.session["week"], meso["weeks"])
            w, d, reason = coach.suggest_weight(app.db, name, rir)
            lo, hi = min(vals["lo"], vals["hi"]), max(vals["lo"], vals["hi"])
            entry = {
                "exercise": name, "target_sets": vals["sets"],
                "target_reps": [lo, hi], "target_rir": rir,
                "tempo": "", "notes": "", "suggested_weight": w,
                "suggested_delta": d or 0, "suggestion_reason": reason,
                "sets": [], "added": True,
            }
            me.session["entries"].insert(me.ex_idx + 1, entry)
            me.ex_idx += 1
            me.autosave()

        app.push(FormScreen(app, "ADD EXERCISE", fields, on_submit=apply,
                            intro=["Added just for today's session (your "
                                   "program is unchanged). Left/Right "
                                   "browses the library, or type a name."]))

    def skip_exercise(self):
        """Drop the current exercise from today's session."""
        app = self.app
        entries = self.session["entries"]
        if len(entries) <= 1:
            return
        cur = entries[self.ex_idx]
        n = len(cur["sets"])
        if n and not app.confirm(
                "Remove %s? %d logged set%s will be discarded." %
                (cur["exercise"], n, "s" if n != 1 else "")):
            return
        entries.pop(self.ex_idx)
        if self.ex_idx >= len(entries):
            self.ex_idx = len(entries) - 1
        self.autosave()

    def log_set(self):
        e = self.entry
        last = e["sets"][-1] if e["sets"] else None
        weight = last["weight"] if last else (e.get("suggested_weight") or 0)
        reps = last["reps"] if last else \
            (e["target_reps"][0] + e["target_reps"][1]) // 2
        rir = e.get("target_rir", 2)
        fields = [
            Field("weight", "Weight", "float", weight, lo=0, hi=2000,
                  step=exercise_step(self.app, e["exercise"]),
                  suffix=self.app.units),
            Field("reps", "Reps", "int", reps, lo=0, hi=100),
            Field("rir", "RIR", "float", rir, lo=0, hi=6, step=0.5),
            Field("pain", "Pain (0-10)", "int", 0, lo=0, hi=10),
            Field("difficulty", "Difficulty (0-10)", "int", 5, lo=0, hi=10),
            Field("notes", "Notes", "text", ""),
        ]
        me = self

        class SetForm(FormScreen):
            def submit(self):
                vals = self.values()
                self.app.pop()
                me.entry["sets"].append(vals)
                me.autosave()
                if len(me.entry["sets"]) >= me.entry["target_sets"]:
                    me.next_unfinished()

        self.app.push(SetForm(self.app, "LOG SET %d — %s" %
                              (len(e["sets"]) + 1, e["exercise"]), fields))

    def next_unfinished(self):
        entries = self.session["entries"]
        for off in range(1, len(entries) + 1):
            j = (self.ex_idx + off) % len(entries)
            if len(entries[j]["sets"]) < entries[j]["target_sets"]:
                self.ex_idx = j
                return

    def autosave(self):
        self.app.db.data["_active"] = self.session
        self.app.db.save()


def exercise_step(app, exercise):
    from . import exercise_db
    return exercise_db.increment(exercise, app.units) / 2


# -- post-workout survey -----------------------------------------------------

class PostScreen(FormScreen):
    def __init__(self, app, session):
        fields = [
            Field("rir_accurate", "Was target RIR accurate?", "text",
                  choices=["yes", "mostly", "no"]),
            Field("too_easy", "Exercises too easy", "text", ""),
            Field("too_hard", "Exercises too difficult", "text", ""),
            Field("soreness", "Unexpected soreness", "text", ""),
            Field("volume_up", "Should volume increase?", "text",
                  choices=["no", "yes"]),
            Field("volume_down", "Should volume decrease?", "text",
                  choices=["no", "yes"]),
            Field("notes", "Session notes", "text", ""),
        ]
        super().__init__(app, "POST-WORKOUT REVIEW", fields,
                         intro=["Your feedback recalibrates the next "
                                "mesocycle decisions."])
        self.session = session

    def submit(self):
        vals = self.values()
        vals["volume_up"] = vals["volume_up"] == "yes"
        vals["volume_down"] = vals["volume_down"] == "yes"
        self.app.pop()
        finish_session(self.app, self.session, vals)


def finish_session(app, session, post):
    db = app.db
    session["post"] = post
    session["completed"] = True
    session["end_ts"] = compat.now_iso()
    prs = analytics.detect_prs(db, session)
    blocks, overall, updates = coach.analyze_session(db, session)
    session["analysis"] = {
        "blocks": [{"exercise": b["exercise"],
                    "lines": [t for t, _ in b["lines"]]} for b in blocks],
        "overall": [t for t, _ in overall],
        "prs": [p["text"] for p in prs],
    }
    db.data["history"].append(session)
    db.update_records(session)  # after detect_prs, which compares to cache
    db.archive_old()
    coach.apply_updates(db, updates)
    coach.advance_calendar(db)
    db.data.pop("_active", None)
    db.save()
    db.backup()
    app.pop_to_root()
    app.push(AnalysisScreen(app, blocks, overall, prs))


# -- coach analysis ------------------------------------------------------

class AnalysisScreen(Screen):
    title = "SESSION ANALYSIS"
    hints = "[Up/Dn] Scroll  [Enter] Continue"

    def __init__(self, app, blocks, overall, prs):
        super().__init__(app)
        self.prs = prs
        st = app.style
        rows = []
        for b in blocks:
            rows.append((b["exercise"], "title", 0))
            for text, attr in b["lines"]:
                rows.append((st.bullet + " " + text, attr, 2))
            rows.append(("", "", 0))
        rows.append(("OVERALL", "title", 0))
        for text, attr in overall:
            rows.append((st.bullet + " " + text, attr, 2))
        if prs:
            rows.append(("", "", 0))
            rows.append(("%d PERSONAL RECORD%s SET TODAY" %
                         (len(prs), "S" if len(prs) > 1 else ""),
                         "good", 0))
        self.rows = rows
        self.top = 0

    def render(self, cv):
        vis = cv.h - 4
        for i in range(vis):
            idx = self.top + i
            if idx >= len(self.rows):
                break
            text, attr, indent = self.rows[idx]
            cv.put(3 + indent, 2 + i, widgets.clip(text, cv.w - 7 - indent),
                   attr)
        if len(self.rows) > vis:
            pct = self.top / max(1, len(self.rows) - vis)
            cv.put(cv.w - 3, 2 + int(pct * (vis - 1)), self.app.style.full,
                   "accent")

    def on_key(self, k):
        vis = self.app.term.size()[1] - 4
        if k == "DOWN":
            self.top = min(max(0, len(self.rows) - vis), self.top + 1)
        elif k == "UP":
            self.top = max(0, self.top - 1)
        elif k in ("ENTER", "ESC", "SPACE"):
            if self.prs:
                self.app.replace(CelebrationScreen(self.app, self.prs))
            else:
                self.app.pop()


# -- PR celebration ---------------------------------------------------------

class CelebrationScreen(Screen):
    hints = "[Any key] Continue"
    tick = 0.15

    def __init__(self, app, prs):
        super().__init__(app)
        self.prs = prs
        self.frame_i = 0

    def on_tick(self):
        self.frame_i += 1

    def render(self, cv):
        st = self.app.style
        phases = [st.blk_rest, "+", st.star, "+"]
        w = cv.w
        deco = "".join(phases[(self.frame_i + i) % len(phases)]
                       for i in range(0, w - 8, 2))
        deco = " ".join(deco)[: w - 8]
        y = max(2, cv.h // 2 - len(self.prs) // 2 - 4)
        cv.put(4, y, deco, "warn")
        msg = "%s  NEW PERSONAL RECORD  %s" % (st.star, st.star)
        cv.put(max(2, (w - len(msg)) // 2), y + 2, msg,
               "hi" if self.frame_i % 2 else "good")
        yy = y + 4
        for p in self.prs:
            text = "%s  %s" % (lj(p["kind"].upper(), 10), p["text"])
            cv.put(max(2, (w - len(text)) // 2), yy,
                   widgets.clip(text, w - 6), "good")
            yy += 1
        cv.put(4, yy + 2, deco, "warn")

    def on_key(self, k):
        self.app.pop()
