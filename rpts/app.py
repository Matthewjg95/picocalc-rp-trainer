"""Application shell: screen stack, frame chrome, event loop, modal input.

Platform-neutral: runs against any driver exposing size()/draw()/read_key()/
theme() — the desktop ANSI Term or the PicoCalc LCD PicoTerm.
"""
from . import APP_NAME, VERSION, compat, widgets
from .canvas import ByteCanvas, Canvas


class Screen:
    """Base class. Screens draw inside the chrome frame (margin of 1)."""

    title = ""
    hints = "[ESC] Back"
    tick = None  # seconds between on_tick() calls, or None for blocking

    def __init__(self, app):
        self.app = app

    def render(self, cv):
        pass

    def on_key(self, k):
        if k == "ESC":
            self.app.pop()

    def on_tick(self):
        pass


class App:
    def __init__(self, terminal, db):
        self.term = terminal
        self.db = db
        self.stack = []
        self.running = True
        self._cv = None
        self.on_first_draw = None  # optional one-shot hook (boot diagnostics)

    # -- style / theme (cheap to rebuild; settings can change any time) ----
    @property
    def settings(self):
        return self.db.data["settings"]

    @property
    def style(self):
        return widgets.Style(self.settings)

    @property
    def theme(self):
        return self.term.theme(self.settings.get("theme", "phosphor"))

    @property
    def units(self):
        return self.settings.get("units", "lb")

    def spark_width(self):
        return 32 if self.settings.get("graph_detail") == "high" else 16

    # -- stack -----------------------------------------------------------
    def push(self, screen):
        self.stack.append(screen)

    def pop(self):
        if self.stack:
            self.stack.pop()
        if not self.stack:
            self.running = False
        elif len(self.stack) == 1:
            self._unload_ui_modules()

    def pop_to_root(self):
        del self.stack[1:]
        self._unload_ui_modules()

    def _unload_ui_modules(self, force=False):
        """Back at the home screen: drop the on-demand screen modules from
        the module cache so their bytecode is reclaimed. On the RP2040
        each family costs ~10-20 KB of heap; re-importing from the SD card
        on next open is fast. Desktop keeps the cache (no RAM pressure,
        and tests rely on quick navigation)."""
        if not (compat.MICROPYTHON or force):
            return
        import sys as _sys
        for name in ("rpts.screens_data", "rpts.screens_edit",
                     "rpts.screens_workout"):
            if name in _sys.modules:
                del _sys.modules[name]
        if compat.MICROPYTHON:
            import gc
            gc.collect()

    def replace(self, screen):
        if self.stack:
            self.stack.pop()
        self.stack.append(screen)

    # -- chrome ------------------------------------------------------------
    def build_frame(self):
        w, h = self.term.size()
        # reuse one canvas across frames; only reallocate if the terminal
        # is resized (never, on the fixed-size PicoCalc LCD)
        cv = self._cv
        if cv is None or cv.w != w or cv.h != h:
            # ByteCanvas: ~10x lighter, ascii-only (device runs ascii mode).
            # Canvas: Unicode-capable, used on the desktop.
            cv = self._cv = ByteCanvas(w, h) if compat.MICROPYTHON \
                else Canvas(w, h)
        else:
            cv.clear()
        st = self.style
        scr = self.stack[-1] if self.stack else None
        widgets.frame(cv, 0, 0, w, h, st)
        meso = self.db.data["meso"]
        right = " MESO %d  WK %d/%d " % (meso["number"], meso["week"],
                                         meso["weeks"])
        head = " %s " % scr.title if (scr and scr.title) else \
            " %s v%s " % (APP_NAME, VERSION)
        cv.put(2, 0, widgets.clip(head, w - len(right) - 6), "title")
        cv.put(w - len(right) - 2, 0, right, "accent")
        if scr:
            hint = " %s " % widgets.clip(scr.hints, w - 6)
            cv.put(2, h - 1, hint, "dim")
            scr.render(cv)
        # desktop ascii mode: transliterate stray Unicode in the list-based
        # Canvas. (ByteCanvas already stores ascii bytes, so it's skipped.)
        if not compat.MICROPYTHON and \
                self.settings.get("charset") == "ascii":
            tr = widgets.ASCII_TRANSLATE
            for row in cv.chars:
                for i, ch in enumerate(row):
                    if ord(ch) > 127:
                        row[i] = tr.get(ch, "?")
        return cv

    # -- main loop -------------------------------------------------------------
    def run(self):
        gc = None
        if compat.MICROPYTHON:
            import gc
        while self.running and self.stack:
            scr = self.stack[-1]
            # only collect when the heap is getting tight — collecting on
            # every keypress made input feel laggy. The lightweight
            # ByteCanvas keeps per-frame allocation small, so free memory
            # stays high during normal navigation.
            if gc is not None and gc.mem_free() < 48000:
                gc.collect()
            self.term.draw(self.build_frame(), self.theme)
            if self.on_first_draw is not None:
                cb, self.on_first_draw = self.on_first_draw, None
                cb()
            k = self.term.read_key(scr.tick)
            if k is None:
                scr.on_tick()
            else:
                scr.on_key(k)

    # -- modal input ---------------------------------------------------------
    def prompt(self, label, initial=""):
        """Blocking one-line text input overlay. Returns str or None (ESC)."""
        buf = str(initial)
        while True:
            cv = self.build_frame()
            w, h = cv.w, cv.h
            bw = min(w - 6, max(30, len(label) + 8))
            x, y = (w - bw) // 2, h - 5
            cv.fill(x, y, bw, 3, " ")
            widgets.frame(cv, x, y, bw, 3, self.style, title=label)
            cv.put(x + 2, y + 1, widgets.clip(buf, bw - 5) + "_", "hi")
            self.term.draw(cv, self.theme)
            k = self.term.read_key()
            if k == "ENTER":
                return buf
            if k == "ESC":
                return None
            if k == "BS":
                buf = buf[:-1]
            elif k == "SPACE":
                buf += " "
            elif k and len(k) == 1:
                buf += k

    def confirm(self, question):
        """Yes/No modal. Enter or Y confirms; Esc or N cancels."""
        lines = widgets.wrap(question, min(self.term.size()[0] - 10, 40))
        while True:
            cv = self.build_frame()
            w, h = cv.w, cv.h
            bw = min(w - 6, max(34, max(len(s) for s in lines) + 6))
            bh = len(lines) + 3
            x, y = (w - bw) // 2, h - bh - 2
            cv.fill(x, y, bw, bh, " ")
            widgets.frame(cv, x, y, bw, bh, self.style, title="CONFIRM")
            for i, s in enumerate(lines):
                cv.put(x + 2, y + 1 + i, s, "warn")
            cv.put(x + 2, y + bh - 2, "[Enter] Yes    [Esc] No", "dim")
            self.term.draw(cv, self.theme)
            k = self.term.read_key()
            if k in ("ENTER", "SPACE") or (k and k.lower() == "y"):
                return True
            if k == "ESC" or (k and k.lower() == "n"):
                return False

    def today(self):
        return compat.today()


# -- generic form ----------------------------------------------------------

class Field:
    def __init__(self, key, label, ftype="float", value=None, choices=None,
                 lo=None, hi=None, step=1, suffix="", cycle=None):
        self.key, self.label, self.ftype = key, label, ftype
        self.choices = choices
        # `cycle`: a browse list for a free-text field — LEFT/RIGHT steps
        # through it while typing still works (e.g. the exercise library)
        self.cycle = cycle
        self.lo, self.hi, self.step, self.suffix = lo, hi, step, suffix
        if value is None:
            value = choices[0] if choices else (0 if ftype != "text" else "")
        self.value = value
        self.buf = None  # live inline-edit string, or None when not editing

    def _num_str(self):
        v = self.value
        return ("%g" % v) if isinstance(v, float) else str(v)

    def display(self, selected=False):
        if self.buf is not None:               # actively typing into it
            body = self.buf + "_"
        elif self.ftype == "text":
            body = str(self.value) or ("_" if selected else "-")
        elif self.choices:
            body = str(self.value)
        else:
            body = self._num_str()
        if self.suffix and not (self.buf is not None):
            body += " " + self.suffix
        return body

    # -- LEFT/RIGHT nudge (also commits any in-progress typing) ----------
    def adjust(self, direction):
        self.commit()
        opts = self.choices or self.cycle
        if opts:
            i = opts.index(self.value) if self.value in opts else -direction
            self.value = opts[(i + direction) % len(opts)]
        elif self.ftype in ("int", "float"):
            v = self.value + direction * self.step
            if self.lo is not None:
                v = max(self.lo, v)
            if self.hi is not None:
                v = min(self.hi, v)
            self.value = int(v) if self.ftype == "int" else round(v, 2)

    def _jump(self, c):
        """On a choice/browse field, jump to the next option starting with
        the typed letter (fast browsing of a long list)."""
        opts = self.choices or self.cycle
        start = (opts.index(self.value) + 1) if self.value in opts else 0
        cl = c.lower()
        for off in range(len(opts)):
            o = opts[(start + off) % len(opts)]
            if str(o).lower().startswith(cl):
                self.value = o
                return

    # -- inline typing ---------------------------------------------------
    def type_char(self, c):
        if self.choices:                       # choices: type to jump
            self._jump(c)
            return
        if self.buf is None:
            self.buf = ""                       # first keystroke clears field
        if self.ftype == "text":
            self.buf += c
        elif c.isdigit():
            self.buf += c
        elif c == "." and self.ftype == "float" and "." not in self.buf:
            self.buf += c
        elif c == "-" and self.buf == "":
            self.buf += c
        self._apply_live()

    def backspace(self):
        if self.choices:
            return
        if self.buf is None:
            self.buf = "" if self.ftype == "text" else self._num_str()
        self.buf = self.buf[:-1]
        self._apply_live()

    def _apply_live(self):
        """Reflect the edit buffer into value as you type (no clamping —
        clamping mid-number would fight the typing, e.g. min 10 vs '1')."""
        if self.ftype == "text":
            self.value = self.buf
            return
        if self.buf in ("", "-", ".", "-."):
            return
        try:
            v = float(self.buf)
        except ValueError:
            return
        self.value = int(v) if self.ftype == "int" else v

    def commit(self):
        """Finalize typing: parse, clamp, and leave edit mode."""
        if self.buf is None:
            return
        if self.ftype == "text":
            self.value = self.buf
        else:
            try:
                v = float(self.buf) if self.buf not in ("", "-", ".", "-.") \
                    else self.value
            except ValueError:
                v = self.value
            if self.lo is not None:
                v = max(self.lo, v)
            if self.hi is not None:
                v = min(self.hi, v)
            self.value = int(v) if self.ftype == "int" else round(v, 2)
        self.buf = None


class FormScreen(Screen):
    """Keyboard form with INLINE editing: UP/DOWN pick a field, just type
    to change it (digits/letters go straight in, Backspace deletes),
    LEFT/RIGHT nudge numbers or cycle choices, ENTER moves on / saves."""

    hints = "[Up/Dn]Field [Type]Edit [L/R]+- [Ent]Save [ESC]"

    def __init__(self, app, title, fields, on_submit=None, intro=None):
        super().__init__(app)
        self.title = title
        self.fields = fields
        self.on_submit = on_submit
        self.intro = intro or []
        self.sel = 0  # index into fields; len(fields) == SAVE row

    def values(self):
        # finalize any field still being typed into, so every submit path
        # (base or subclass-overridden) gets clamped, committed values
        for f in self.fields:
            f.commit()
        return {f.key: f.value for f in self.fields}

    def render(self, cv):
        st = self.app.style
        y = 2
        for line in self.intro:
            for wl in widgets.wrap(line, cv.w - 6):   # wrap, don't clip
                cv.put(3, y, wl, "dim")
                y += 1
        if self.intro:
            y += 1
        label_w = compat.gmax((len(f.label) for f in self.fields),
                              default=10) + 2
        for i, f in enumerate(self.fields):
            sel = (i == self.sel)
            marker = (st.bullet + " ") if sel else "  "
            cv.put(3, y, marker + widgets.lj(f.label, label_w),
                   "hi" if sel else "")
            val = widgets.clip(f.display(selected=sel), cv.w - label_w - 12)
            cv.put(6 + label_w, y, val, "inv" if sel else "hi")
            if (f.choices or f.cycle) and sel:
                cv.put(6 + label_w + len(val) + 1, y, "<>", "dim")
            y += 1
        y += 1
        sel = (self.sel == len(self.fields))
        cv.put(3, y, (st.bullet + " " if sel else "  ") + "[ SAVE ]",
               "inv" if sel else "good")
        self.save_y = y

    def _commit_current(self):
        if self.sel < len(self.fields):
            self.fields[self.sel].commit()

    def on_key(self, k):
        n = len(self.fields)
        if k == "UP":
            self._commit_current()
            self.sel = (self.sel - 1) % (n + 1)
        elif k in ("DOWN", "TAB"):
            self._commit_current()
            self.sel = (self.sel + 1) % (n + 1)
        elif k == "ESC":
            self.cancel()
        elif self.sel == n:                    # on the SAVE row
            if k == "ENTER":
                self.submit()
        elif k == "ENTER":                     # commit field, advance
            self._commit_current()
            self.sel += 1
        elif k in ("LEFT", "RIGHT"):
            self.fields[self.sel].adjust(1 if k == "RIGHT" else -1)
        elif k == "BS":
            self.fields[self.sel].backspace()
        elif k == "SPACE":
            f = self.fields[self.sel]
            if f.ftype == "text":
                f.type_char(" ")
        elif k and len(k) == 1:
            self.fields[self.sel].type_char(k)

    def submit(self):
        vals = self.values()                   # values() commits all fields
        self.app.pop()
        if self.on_submit:
            self.on_submit(vals)

    def cancel(self):
        self.app.pop()


class InfoScreen(Screen):
    """Static message panel; any key dismisses."""

    hints = "[Any key] Continue"

    def __init__(self, app, title, lines):
        super().__init__(app)
        self.title = title
        self.lines = lines  # list of (text, attr) or str

    def render(self, cv):
        y = 3
        for line in self.lines:
            text, attr = line if isinstance(line, tuple) else (line, "")
            cv.put(4, y, widgets.clip(text, cv.w - 8), attr)
            y += 1

    def on_key(self, k):
        self.app.pop()
