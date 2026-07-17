"""JSON persistence: atomic autosave, rotating backups, CSV export/import.

Runs on CPython and MicroPython. Two features keep RAM bounded on the
PicoCalc's microcontroller:

  * records cache — per-exercise bests, lifetime tonnage and weekly-best
    tonnage are folded into `data["records"]` as sessions complete, so PR
    detection never needs the full history in memory.
  * history archive — the live DB holds only the most recent
    `archive_keep` sessions; older ones are appended to an append-only
    JSONL file on disk (streamed, never loaded whole).
"""
import json
import os

from . import compat, programs
from .compat import (csv_row, csv_split, exists, listdir_sorted, makedirs,
                     pjoin, replace, today, week_key)


def default_data():
    return {
        "version": 2,
        "athlete": {
            "name": "Athlete", "age": 30, "sex": "M", "height_in": 70.0,
            "bodyweight": 180.0, "goal_weight": 185.0,
            "experience": "intermediate",  # beginner/intermediate/advanced
            "injuries": "",
            "equipment": ["barbell", "dumbbell", "machine", "cable",
                          "bodyweight"],
        },
        "settings": {
            "units": "lb", "theme": "phosphor", "charset": "unicode",
            "graph_detail": "high",  # high/low -> sparkline width
            "coach_verbosity": "normal",  # terse/normal/verbose
            "rest_target": 120,
        },
        "goals": {
            "type": "hypertrophy",  # strength/hypertrophy/weight loss/recomp/custom
            "note": "",
        },
        "program": programs.make_program("Upper Lower"),
        "meso": {"number": 1, "week": 1, "weeks": 6, "day_index": 0,
                 "started": today()},
        # exercise -> {"weight": float, "sets": int} — the coach's current
        # working prescription, updated by auto-regulation after sessions.
        "prescriptions": {},
        # TUNE-01: self-calibration of the recovery model. `bias` shifts
        # predicted recovery (clamped ±0.15) and drifts slowly whenever the
        # athlete's own post-session answers contradict the prediction.
        "coach_cal": {"bias": 0.0, "n": 0},
        "records": empty_records(),
        "history": [],         # recent completed sessions (older -> archive)
        "bodyweight_log": [],  # {"date", "weight"}
        "swaps": [],           # {"date", "from", "to", "reason"}
    }


def empty_records():
    return {"ex": {}, "lifetime": 0.0, "best_week": 0.0,
            "cur_week_key": "", "cur_week": 0.0, "n_sessions": 0}


class DB:
    """Persistence with multiple named athlete profiles. Each profile is a
    self-contained folder under <data_dir>/profiles/<name>/ (same files as a
    single-athlete DB); <data_dir>/active.txt names the current one. `data`
    always holds the flat document for the active profile, so the rest of
    the app is unaware profiles exist."""

    def __init__(self, data_dir, archive_keep=200, bw_keep=400):
        self.root = data_dir
        self.archive_keep = archive_keep
        self.bw_keep = bw_keep  # bodyweight-log entries kept in RAM
        self.active = self._read_active()
        self._set_paths()
        self.data = default_data()

    # -- profile plumbing -------------------------------------------------
    def _profiles_root(self):
        return pjoin(self.root, "profiles")

    def _set_paths(self):
        self.dir = pjoin(self._profiles_root(), self.active)
        self.path = pjoin(self.dir, "rpts_data.json")
        self.archive_path = pjoin(self.dir, "history_archive.jsonl")
        self.backup_dir = pjoin(self.dir, "backups")

    def _read_active(self):
        p = pjoin(self.root, "active.txt")
        if exists(p):
            try:
                with open(p, "r") as f:
                    name = f.read().strip()
                if name:
                    return name
            except OSError:
                pass
        return "Athlete"

    def _write_active(self, name):
        makedirs(self.root)
        with open(pjoin(self.root, "active.txt"), "w") as f:
            f.write(name)

    def _migrate_legacy(self):
        """v1/v2 kept a single athlete flat at the data-dir root. Move it
        into profiles/Athlete/ once. Keyed on the Athlete profile not yet
        existing (not on the profiles/ folder), so a pre-placed Demo
        profile doesn't stop the real data from migrating."""
        legacy = pjoin(self.root, "rpts_data.json")
        if not exists(legacy):
            return
        dst = pjoin(self._profiles_root(), "Athlete")
        if exists(pjoin(dst, "rpts_data.json")):
            return  # already migrated
        makedirs(dst)
        try:
            compat.copyfile(legacy, pjoin(dst, "rpts_data.json"))
            la = pjoin(self.root, "history_archive.jsonl")
            if exists(la):
                compat.copyfile(la, pjoin(dst, "history_archive.jsonl"))
        except OSError:
            pass

    def list_profiles(self):
        names = listdir_sorted(self._profiles_root())
        if self.active not in names:
            names = sorted(names + [self.active])
        return names or [self.active]

    def _drop_data(self):
        """Release the current profile's objects BEFORE building the next
        one — holding both at once OOMed the RP2040 (crash in clone() while
        the outgoing profile was still referenced)."""
        self.data = None
        try:
            import gc
            gc.collect()
        except ImportError:
            pass

    def switch_profile(self, name):
        if name == self.active:
            return
        self.save()
        self.active = name
        self._write_active(name)
        self._set_paths()
        self._drop_data()
        self.data = default_data()
        self.load()

    def create_profile(self, name, inherit_settings=True):
        settings = compat.clone(self.data["settings"]) \
            if inherit_settings else None
        self.save()                       # persist the profile we're leaving
        self.active = name
        self._write_active(name)
        self._set_paths()
        self._drop_data()
        self.data = default_data()
        if settings:                      # carry theme/units/pico-tuning over
            self.data["settings"] = settings
        makedirs(self.dir)
        self.save()

    def delete_profile(self, name):
        if name == self.active:
            return False                  # can't delete the active profile
        d = pjoin(self._profiles_root(), name)
        bk = pjoin(d, "backups")
        for f in listdir_sorted(bk):
            compat.remove_quiet(pjoin(bk, f))
        try:
            os.rmdir(bk)
        except OSError:
            pass
        for f in listdir_sorted(d):
            compat.remove_quiet(pjoin(d, f))
        try:
            os.rmdir(d)
        except OSError:
            pass
        return True

    # -- load / save ------------------------------------------------------
    def load(self):
        self._migrate_legacy()
        if exists(self.path):
            try:  # a defragmented heap matters for the parse (RP2040)
                import gc
                gc.collect()
            except ImportError:
                pass
            with open(self.path, "r") as f:
                loaded = json.load(f)
            base = default_data()
            base.update(loaded)  # forward-compatible: new keys get defaults
            self.data = base
            self.migrate_history_to_summaries()  # pre-summary profiles
            if not self.data.get("records", {}).get("n_sessions") and \
                    self.data["history"]:
                self.rebuild_records()
        else:
            makedirs(self.dir)
            self.save()
        return self

    def save(self):
        makedirs(self.dir)
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            compat.json_dump(self.data, f)
        replace(tmp, self.path)

    def backup(self):
        makedirs(self.backup_dir)
        dest = pjoin(self.backup_dir, "rpts_%s.json" % compat.stamp())
        self.save()
        compat.copyfile(self.path, dest)
        backups = listdir_sorted(self.backup_dir)
        for old in backups[:-20]:  # keep the 20 most recent
            compat.remove_quiet(pjoin(self.backup_dir, old))
        return dest

    def restore_latest_backup(self):
        backups = listdir_sorted(self.backup_dir)
        if not backups:
            return None
        src = pjoin(self.backup_dir, backups[-1])
        with open(src, "r") as f:
            self.data = json.load(f)
        self.save()
        return src

    # -- records cache -----------------------------------------------------
    def update_records(self, session):
        """Fold a completed session into the incremental records cache.
        Must be called AFTER PR detection (which compares against the
        cache as it stood before this session)."""
        rec = self.data["records"]
        ton_session = 0.0
        for e in session.get("entries", []):
            sets = e.get("sets", [])
            if not sets:
                continue
            name = e["exercise"]
            r = rec["ex"].setdefault(name, {
                "e1rm": 0.0, "e1rm_date": "", "reps": 0,
                "reps_weight": 0.0, "tonnage": 0.0})
            ton = 0.0
            for st in sets:
                w = st.get("weight", 0)
                n = st.get("reps", 0)
                ton += w * n
                total = n + max(0.0, st.get("rir", 0))
                e1 = w * (1 + total / 30.0) if total > 1 else float(w)
                if n > 0 and e1 > r["e1rm"]:
                    r["e1rm"] = e1
                    r["e1rm_date"] = session["date"]
                if (w, n) > (r["reps_weight"], r["reps"]):
                    r["reps_weight"], r["reps"] = w, n
            if ton > r["tonnage"]:
                r["tonnage"] = ton
            ton_session += ton
        rec["lifetime"] += ton_session
        wk = week_key(session["date"])
        if wk != rec["cur_week_key"]:
            if rec["cur_week"] > rec["best_week"]:
                rec["best_week"] = rec["cur_week"]
            rec["cur_week_key"] = wk
            rec["cur_week"] = 0.0
        rec["cur_week"] += ton_session
        rec["n_sessions"] += 1

    def rebuild_records(self):
        """Replay all full sessions (archive streamed + any non-summary
        live sessions) into a fresh cache. Summary sessions are skipped —
        their full twins are in the archive."""
        self.data["records"] = empty_records()
        for s in self.iter_all_sessions():
            self.update_records(s)

    # -- history archive ------------------------------------------------------
    def commit_session(self, session):
        """Persist a finished session: the FULL set-by-set record goes to
        the on-disk archive immediately; the live window keeps only a
        compact summary. A full session is ~4 KB of parsed objects — 24 of
        them OOMed the RP2040 on profile load; summaries are ~25x smaller,
        so the device can hold a longer trend window in less RAM."""
        from . import analytics
        makedirs(self.dir)
        with open(self.archive_path, "a") as f:
            f.write(json.dumps(session))
            f.write("\n")
        self.data["history"].append(analytics.summarize_session(session))
        self.archive_old()

    def archive_old(self):
        """Trim the live window and the bodyweight log. Summaries being
        dropped are already in the archive; any legacy FULL session being
        dropped is archived first so no data is ever lost."""
        hist = self.data["history"]
        if len(hist) > self.archive_keep:
            full_drops = [s for s in hist[: len(hist) - self.archive_keep]
                          if not s.get("summary")]
            if full_drops:
                makedirs(self.dir)
                with open(self.archive_path, "a") as f:
                    for s in full_drops:
                        f.write(json.dumps(s))
                        f.write("\n")
            del hist[: len(hist) - self.archive_keep]
        bw = self.data["bodyweight_log"]
        if len(bw) > self.bw_keep:
            del bw[: len(bw) - self.bw_keep]

    def migrate_history_to_summaries(self):
        """One-time upgrade of a pre-summary profile: archive every full
        live session and replace it with its summary. Returns count."""
        from . import analytics
        hist = self.data["history"]
        full = [s for s in hist if not s.get("summary")]
        if not full:
            return 0
        makedirs(self.dir)
        with open(self.archive_path, "a") as f:
            for s in full:
                f.write(json.dumps(s))
                f.write("\n")
        for i in range(len(hist)):
            if not hist[i].get("summary"):
                hist[i] = analytics.summarize_session(hist[i])
        self.save()
        return len(full)

    def iter_all_sessions(self):
        """Every FULL session ever, oldest first, archive streamed from
        disk. Live summaries are skipped (their full versions are in the
        archive); legacy full sessions still in the live window are
        included."""
        if exists(self.archive_path):
            with open(self.archive_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        yield json.loads(line)
        for s in self.data["history"]:
            if not s.get("summary"):
                yield s

    # -- CSV --------------------------------------------------------------
    CSV_FIELDS = ["date", "week", "day", "exercise", "set", "weight",
                  "reps", "rir", "pain", "difficulty", "notes"]

    def export_csv(self, path=None):
        path = path or pjoin(self.dir, "rpts_export.csv")
        with open(path, "w") as f:
            f.write(csv_row(self.CSV_FIELDS) + "\n")
            for s in self.iter_all_sessions():
                for entry in s.get("entries", []):
                    i = 0
                    for st in entry.get("sets", []):
                        i += 1
                        f.write(csv_row([
                            s["date"], s.get("week", ""), s.get("day", ""),
                            entry["exercise"], i, st.get("weight", ""),
                            st.get("reps", ""), st.get("rir", ""),
                            st.get("pain", ""), st.get("difficulty", ""),
                            st.get("notes", ""),
                        ]) + "\n")
        return path

    def import_csv(self, path):
        """Merge externally logged sets into history as imported sessions."""
        sessions = {}
        with open(path, "r") as f:
            header = None
            for line in f:
                line = line.rstrip("\r\n")
                if not line:
                    continue
                cells = csv_split(line)
                if header is None:
                    header = [c.strip().lower() for c in cells]
                    continue
                row = {}
                for i, name in enumerate(header):
                    row[name] = cells[i] if i < len(cells) else ""
                date = (row.get("date") or "").strip()
                ex = (row.get("exercise") or "").strip()
                if not date or not ex:
                    continue
                s = sessions.setdefault(date, {
                    "date": date, "week": 0, "day": "Imported",
                    "entries": [], "checkin": {}, "post": {},
                    "completed": True, "imported": True,
                })
                entry = None
                for e in s["entries"]:
                    if e["exercise"] == ex:
                        entry = e
                        break
                if entry is None:
                    entry = {"exercise": ex, "target_sets": 0,
                             "target_reps": [0, 0], "target_rir": 2,
                             "sets": []}
                    s["entries"].append(entry)
                try:
                    entry["sets"].append({
                        "weight": float(row.get("weight") or 0),
                        "reps": int(float(row.get("reps") or 0)),
                        "rir": float(row.get("rir") or 2),
                        "pain": float(row.get("pain") or 0),
                        "difficulty": float(row.get("difficulty") or 5),
                        "notes": row.get("notes") or "",
                    })
                except ValueError:
                    continue
        existing = set()
        for s in self.data["history"]:
            if s.get("imported"):
                existing.add(s["date"])
        added = 0
        for date in sorted(sessions):
            if date not in existing:
                s = sessions[date]
                self.data["history"].append(s)
                self.update_records(s)
                added += 1
        self.data["history"].sort(key=lambda s: s["date"])
        # archives the imported full sessions and keeps summaries live
        self.migrate_history_to_summaries()
        self.archive_old()
        self.save()
        return added

    # -- unit conversion --------------------------------------------------
    def convert_units(self, new_units):
        """Convert every stored load when the units setting flips.
        (Archived history keeps its original units; the archive stores
        raw logs and the units they were logged in matter only for the
        live analytics window.)"""
        old = self.data["settings"]["units"]
        if new_units == old:
            return
        k = 0.45359237 if new_units == "kg" else 1 / 0.45359237

        def rnd(v):
            return round(v * k, 1)

        a = self.data["athlete"]
        a["bodyweight"] = rnd(a["bodyweight"])
        a["goal_weight"] = rnd(a["goal_weight"])
        for p in self.data["prescriptions"].values():
            if p.get("weight"):
                p["weight"] = rnd(p["weight"])
        for s in self.data["history"]:
            for e in s.get("entries", []):
                for st in e.get("sets", []):
                    st["weight"] = rnd(st.get("weight", 0))
        for bw in self.data["bodyweight_log"]:
            bw["weight"] = rnd(bw["weight"])
        rec = self.data["records"]
        rec["lifetime"] = rnd(rec["lifetime"])
        rec["best_week"] = rnd(rec["best_week"])
        rec["cur_week"] = rnd(rec["cur_week"])
        for r in rec["ex"].values():
            r["e1rm"] = rnd(r["e1rm"])
            r["reps_weight"] = rnd(r["reps_weight"])
            r["tonnage"] = rnd(r["tonnage"])
        self.data["settings"]["units"] = new_units
        self.save()
