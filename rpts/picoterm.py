"""PicoCalc terminal driver for the PicoCalc MicroPython firmware
(zenodante's build — the `MicroPython_*.bin` shipped on the stock SD card).

That firmware boots with:
  * `picocalc.terminal` — a 53x40 VT100 emulator on the 320x320 LCD,
    attached to the REPL via os.dupterm; it parses standard ANSI escape
    sequences in C, so we render exactly like the desktop driver: diffed
    rows written to sys.stdout.
  * `picocalc.keyboard` — the I2C keyboard (STM32 @ 0x1F), whose
    readinto() yields VT100 byte sequences: arrows ESC[A-D, Enter '\r',
    Backspace 0x7F, Esc as ESC ESC, Del ESC[3~, Home ESC[H, End ESC[F.

This module is only imported on the device; on desktop, rpts.term is used.
"""
import sys
import time

from .compat import now_iso
from .themes import THEMES

# time.ticks_ms is MicroPython-only; shim so the module stays testable
_ticks_ms = getattr(time, "ticks_ms", None) or (lambda: int(time.time() * 1000))
_ticks_add = getattr(time, "ticks_add", None) or (lambda t, d: t + d)
_ticks_diff = getattr(time, "ticks_diff", None) or (lambda a, b: a - b)

_CSI_FINAL = {
    "A": "UP", "B": "DOWN", "C": "RIGHT", "D": "LEFT",
    "H": "HOME", "F": "END",
}
_CSI_TILDE = {"1": "HOME", "3": "DEL", "4": "END", "5": "PGUP", "6": "PGDN"}


class PicoVtTerm:
    """Drives picocalc.terminal (output) + picocalc.keyboard (input).
    Same interface as rpts.term.Term: size/theme/enter/exit/draw/read_key.
    """

    def __init__(self, keyboard=None, terminal=None, clock_file=None):
        if keyboard is None or terminal is None:
            import picocalc  # frozen module in the PicoCalc firmware
            keyboard = keyboard or picocalc.keyboard
            terminal = terminal or getattr(picocalc, "terminal", None)
        if keyboard is None:
            raise RuntimeError("picocalc.keyboard missing - boot.py failed?")
        self.kbd = keyboard
        self.terminal = terminal
        self.clock_file = clock_file
        self._last = []
        # key buffer is a list of int byte values, NOT a bytearray:
        # MicroPython bytearray does not support `del buf[i]` / slice
        # deletion, which _decode() relies on (CPython bytearray does,
        # which is why desktop tests didn't catch it).
        self._kbuf = []
        self._tmp = bytearray(16)
        self._clock_at = _ticks_ms()

    # -- interface -------------------------------------------------------
    def size(self):
        if self.terminal:
            try:
                rows, cols = self.terminal.get_screen_size()
                return cols, rows
            except Exception:
                pass
        return 53, 40

    def theme(self, name):
        return THEMES.get(name, THEMES["phosphor"])

    def enter(self):
        # \x1b[?7l disables auto-wrap: without it, drawing the last cell of
        # the bottom row wraps the cursor and SCROLLS the whole screen up,
        # which caused the "everything doubles / options copy upward" bug.
        sys.stdout.write("\x1b[0m\x1b[?7l\x1b[2J\x1b[?25l\x1b[1;1H")
        self._last = []

    def exit(self):
        sys.stdout.write("\x1b[0m\x1b[?7h\x1b[2J\x1b[?25h\x1b[1;1H")

    def draw(self, canvas, theme):
        lines = canvas.render(theme)
        w = sys.stdout.write
        last = self._last
        nlast = len(last)
        for y in range(len(lines)):
            line = lines[y]
            if y >= nlast or last[y] != line:
                # write each changed row on its own — never build a single
                # whole-frame string (that big contiguous alloc is what
                # exhausted the RP2040 heap)
                w("\x1b[")
                w(str(y + 1))
                w(";1H")
                w(line)
                w("\x1b[0m")
        self._last = lines

    def read_key(self, timeout=None):
        deadline = None if timeout is None else \
            _ticks_add(_ticks_ms(), int(timeout * 1000))
        idle = 0  # consecutive pumps that yielded no new bytes
        while True:
            # once input has gone quiet, flush any partial escape sequence
            # (e.g. a lone ESC) rather than waiting forever for its tail —
            # not doing this can lock up all further input.
            k = self._decode(flush=(idle >= 2))
            if k is not None:
                self._persist_clock()
                return k
            before = len(self._kbuf)
            self._pump()
            if len(self._kbuf) > before:
                idle = 0
            else:
                idle += 1
            timed_out = deadline is not None and \
                _ticks_diff(deadline, _ticks_ms()) <= 0
            if not self._kbuf:
                if timed_out:
                    return None
                time.sleep(0.01)
            else:
                # bytes pending but not yet a full key: brief wait for the
                # rest, and flush on the next pass if we hit the timeout
                if timed_out:
                    idle = 99
                time.sleep(0.005)

    # -- input plumbing --------------------------------------------------
    def _pump(self):
        try:
            n = self.kbd.readinto(self._tmp)
        except OSError:  # transient I2C hiccup
            return
        if n:
            self._kbuf.extend(self._tmp[:n])

    def _decode(self, flush=False):
        """Consume one key from the byte buffer. Returns a key name, or None
        if the buffer holds only an incomplete escape sequence. When `flush`
        is set, an incomplete sequence is resolved to ESC instead of waiting
        (prevents a stuck partial sequence from freezing input)."""
        buf = self._kbuf
        while buf:
            b0 = buf[0]
            if b0 != 0x1B:
                del buf[0]
                k = self._plain(b0)
                if k is not None:
                    return k
                continue  # unmapped control byte: drop and keep scanning
            # escape sequence: need at least one more byte
            if len(buf) < 2:
                if flush:
                    del buf[0]
                    return "ESC"
                return None  # wait for the rest
            b1 = buf[1]
            if b1 == 0x1B:  # keyboard sends Esc as ESC ESC
                del buf[0:2]
                return "ESC"
            if b1 != 0x5B:  # lone ESC + other char: emit ESC, keep the char
                del buf[0]
                return "ESC"
            # CSI: ESC [ params final(0x40-0x7E)
            i = 2
            n = len(buf)
            while i < n and not (0x40 <= buf[i] <= 0x7E):
                i += 1
            if i >= n:
                if flush:
                    del buf[0:n]  # give up on the incomplete CSI
                    return "ESC"
                return None
            final = chr(buf[i])
            params = bytes(buf[2:i]).decode() if i > 2 else ""
            del buf[0: i + 1]
            if final == "~":
                key = _CSI_TILDE.get(params.split(";")[0] if params else "")
            else:
                key = _CSI_FINAL.get(final)
            if key:
                return key
            # unknown sequence: swallow and keep scanning
        return None

    @staticmethod
    def _plain(b):
        if b in (0x0D, 0x0A):
            return "ENTER"
        if b in (0x08, 0x7F):
            return "BS"
        if b == 0x09:
            return "TAB"
        if b == 0x20:
            return "SPACE"
        if 0x21 <= b <= 0x7E:
            return chr(b)
        return None

    # -- clock persistence -------------------------------------------------
    def _persist_clock(self):
        """The Pico has no battery RTC; remember the current time on disk
        (at most every 2 minutes) so the next boot can restore a sane
        clock and the date-confirm screen starts close to reality."""
        if not self.clock_file:
            return
        now = _ticks_ms()
        if _ticks_diff(now, self._clock_at) < 120000:
            return
        self._clock_at = now
        try:
            with open(self.clock_file, "w") as f:
                f.write(now_iso())
        except OSError:
            pass
