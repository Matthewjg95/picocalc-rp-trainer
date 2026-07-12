"""Desktop terminal driver: ANSI themes, cross-platform keyboard input.

Works on Windows 10+ (VT mode enabled via kernel32), Linux/macOS, and any
serial/SSH terminal. No curses. (The PicoCalc runs pico/picoterm.py against
the LCD instead — this module is never imported on MicroPython.)
"""
import os
import sys
import time

from .canvas import Canvas  # noqa: F401  (re-export; shared with drivers)
from .themes import THEMES

IS_WIN = os.name == "nt"
if IS_WIN:
    import ctypes
    import msvcrt
else:
    import select
    import termios
    import tty

_WIN_KEYMAP = {
    "H": "UP", "P": "DOWN", "K": "LEFT", "M": "RIGHT",
    "G": "HOME", "O": "END", "S": "DEL", "I": "PGUP", "Q": "PGDN",
}
_ANSI_KEYMAP = {
    "[A": "UP", "[B": "DOWN", "[D": "LEFT", "[C": "RIGHT",
    "[H": "HOME", "[F": "END", "[3~": "DEL", "[5~": "PGUP", "[6~": "PGDN",
    "OA": "UP", "OB": "DOWN", "OD": "LEFT", "OC": "RIGHT",
}


class Term:
    """Owns the real terminal: raw mode, alt screen, diffed frame output."""

    def __init__(self):
        self._last = []
        self._last_size = None
        self._posix_saved = None

    def theme(self, name):
        """Resolve a theme name to this driver's attr map."""
        return THEMES.get(name, THEMES["phosphor"])

    # -- size ------------------------------------------------------------
    def size(self):
        cols = os.environ.get("RPTS_COLS")
        rows = os.environ.get("RPTS_ROWS")
        if cols and rows:
            return int(cols), int(rows)
        try:
            s = os.get_terminal_size()
            w, h = s.columns, s.lines
        except OSError:
            w, h = 80, 30
        return max(46, min(w, 96)), max(22, min(h, 42))

    # -- lifecycle ---------------------------------------------------------
    def enter(self):
        if IS_WIN:
            k32 = ctypes.windll.kernel32
            for handle in (-11,):  # STD_OUTPUT_HANDLE
                h = k32.GetStdHandle(handle)
                mode = ctypes.c_uint32()
                if k32.GetConsoleMode(h, ctypes.byref(mode)):
                    k32.SetConsoleMode(h, mode.value | 0x0004)  # VT processing
        else:
            fd = sys.stdin.fileno()
            self._posix_saved = termios.tcgetattr(fd)
            tty.setcbreak(fd)
        sys.stdout.write("\x1b[?1049h\x1b[?25l\x1b[2J")
        sys.stdout.flush()

    def exit(self):
        sys.stdout.write("\x1b[?25h\x1b[?1049l\x1b[0m")
        sys.stdout.flush()
        if not IS_WIN and self._posix_saved is not None:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN,
                              self._posix_saved)

    # -- output --------------------------------------------------------------
    def draw(self, canvas, theme):
        lines = canvas.render(theme)
        size = (canvas.w, canvas.h)
        if size != self._last_size:
            sys.stdout.write("\x1b[2J")
            self._last = []
            self._last_size = size
        out = []
        for y, line in enumerate(lines):
            if y >= len(self._last) or self._last[y] != line:
                out.append("\x1b[%d;1H%s\x1b[0m\x1b[K" % (y + 1, line))
        if out:
            sys.stdout.write("".join(out))
            sys.stdout.flush()
        self._last = lines

    # -- input ----------------------------------------------------------------
    def read_key(self, timeout=None):
        """Return a key name ("a", "ENTER", "UP", ...) or None on timeout."""
        if IS_WIN:
            return self._read_key_win(timeout)
        return self._read_key_posix(timeout)

    def _read_key_win(self, timeout):
        end = None if timeout is None else time.time() + timeout
        while True:
            if msvcrt.kbhit():
                ch = msvcrt.getwch()
                if ch in ("\x00", "\xe0"):
                    return _WIN_KEYMAP.get(msvcrt.getwch())
                return self._map_char(ch)
            if end is not None and time.time() >= end:
                return None
            time.sleep(0.01)

    def _read_key_posix(self, timeout):
        fd = sys.stdin.fileno()
        r, _, _ = select.select([sys.stdin], [], [], timeout)
        if not r:
            return None
        ch = os.read(fd, 1).decode("utf-8", "ignore")
        if ch != "\x1b":
            return self._map_char(ch)
        seq = ""
        while len(seq) < 4:
            r, _, _ = select.select([sys.stdin], [], [], 0.02)
            if not r:
                break
            seq += os.read(fd, 1).decode("utf-8", "ignore")
            if seq in _ANSI_KEYMAP:
                return _ANSI_KEYMAP[seq]
        return _ANSI_KEYMAP.get(seq, "ESC")

    @staticmethod
    def _map_char(ch):
        if ch in ("\r", "\n"):
            return "ENTER"
        if ch in ("\x08", "\x7f"):
            return "BS"
        if ch == "\x1b":
            return "ESC"
        if ch == "\t":
            return "TAB"
        if ch == " ":
            return "SPACE"
        if ch == "\x03":
            raise KeyboardInterrupt
        if ch and ch.isprintable():
            return ch
        return None
