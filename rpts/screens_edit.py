"""Editor screens: athletes (profile switcher), athlete profile, program
editor, goals, settings.

Split from the dashboards module so the RP2040 only pays the RAM for the
family of screens actually opened (the app unloads these modules again on
returning to the home screen)."""
from . import analytics, coach, compat, exercise_db, programs, widgets
from .app import Field, FormScreen, InfoScreen, Screen
from .compat import group_thousands
from .widgets import lj, rj

# -- athletes (profile switcher) -----------------------------------------

class AthletesScreen(Screen):
    title = "ATHLETES"
    hints = "[Up/Dn] [Ent]Switch/Edit [N]ew [E]dit [D]el [ESC]"

    def __init__(self, app):
        super().__init__(app)
        self.names = app.db.list_profiles()
        self.sel = self.names.index(app.db.active) \
            if app.db.active in self.names else 0

    def _refresh(self):
        self.names = self.app.db.list_profiles()
        self.sel = self.names.index(self.app.db.active) \
            if self.app.db.active in self.names else 0

    def render(self, cv):
        st, db = self.app.style, self.app.db
        cv.put(3, 2, "Each athlete keeps its own program, history,", "dim")
        cv.put(3, 3, "records and settings.", "dim")
        y = 5
        for i, n in enumerate(self.names):
            sel = i == self.sel
            active = n == db.active
            cv.put(3, y, (st.bullet + " " if sel else "  ") +
                   widgets.clip(n, cv.w - 18) + ("  (current)" if active
                                                 else ""),
                   "inv" if sel else ("good" if active else ""))
            y += 1
        y += 1
        cv.put(3, y, "Enter = switch to it (or edit, if it's current)",
               "dim")
        cv.put(3, y + 1, "N = new athlete   E = edit current   D = delete",
               "dim")

    def on_key(self, k):
        app, db = self.app, self.app.db
        kl = (k or "").lower()
        n = len(self.names)
        if k == "DOWN":
            self.sel = (self.sel + 1) % n
        elif k == "UP":
            self.sel = (self.sel - 1) % n
        elif k == "ENTER":
            name = self.names[self.sel]
            if name == db.active:
                app.push(ProfileScreen(app))
            else:
                try:
                    db.switch_profile(name)
                except MemoryError:
                    # profile too large for the current heap: fall back to
                    # the previous athlete and tell the user what to do
                    db.switch_profile(db.active)
                    app.push(InfoScreen(app, "OUT OF MEMORY", [
                        ("Not enough free RAM to load '%s'." % name,
                         "bad"),
                        ("Power-cycle and switch to it first thing",
                         "dim"),
                        ("after boot (before opening dashboards).",
                         "dim")]))
                    return
                app.pop_to_root()          # reflect the new athlete at home
        elif kl == "e":
            app.push(ProfileScreen(app))
        elif kl == "n":
            nm = app.prompt("New athlete name")
            nm = (nm or "").strip()
            if nm and nm not in self.names and "/" not in nm:
                db.create_profile(nm)
                app.pop_to_root()
        elif kl == "d":
            name = self.names[self.sel]
            if name == db.active:
                app.push(InfoScreen(app, "DELETE", [
                    ("Can't delete the athlete you're using.", "warn"),
                    ("Switch to another one first.", "dim")]))
            elif app.confirm("Delete '%s' and ALL its data?" % name):
                db.delete_profile(name)
                self._refresh()
        elif k == "ESC":
            app.pop()


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
