"""Static MicroPython-compatibility checker for the shared rpts package.

Fails if any module that must run on the PicoCalc uses CPython-only
constructs. rpts/term.py is exempt (desktop-only driver).

Run:  python tools/check_upy.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "rpts")
EXEMPT = {"term.py"}

RULES = [
    (r"^\s*(import|from)\s+datetime\b", "datetime module (use rpts.compat)"),
    (r"\bos\.path\b", "os.path (use compat.pjoin/exists)"),
    (r"^\s*(import|from)\s+shutil\b", "shutil (use compat.copyfile)"),
    (r"^\s*(import|from)\s+csv\b", "csv module (use compat.csv_row/split)"),
    (r"^\s*(import|from)\s+copy\b", "copy module (use compat.clone)"),
    (r"^\s*(import|from)\s+(termios|msvcrt|ctypes|select|tty)\b",
     "desktop-only module"),
    (r"\.ljust\(", "str.ljust (use widgets.lj)"),
    (r"\.rjust\(", "str.rjust (use widgets.rj)"),
    (r"\.isprintable\(", "str.isprintable (missing on MicroPython)"),
    (r"\{:,", "',' format spec (use compat.group_thousands)"),
    (r"(?<![\w.])max\([^)\n]*default=", "max(default=) (use compat.gmax)"),
    (r"(?<![\w.])min\([^)\n]*default=", "min(default=) (restructure)"),
    (r"(?<![\w.])next\([^)\n]*,", "2-arg next() (use a loop)"),
    (r"isoformat|isocalendar|fromisoformat", "datetime API (use compat)"),
    (r"timespec=", "datetime API (use compat)"),
]


def main():
    problems = []
    for fname in sorted(os.listdir(PKG)):
        if not fname.endswith(".py") or fname in EXEMPT:
            continue
        path = os.path.join(PKG, fname)
        with open(path, "r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                for pat, why in RULES:
                    if fname == "compat.py" and "os.path" in why:
                        continue  # compat IS the guarded os.path shim
                    if re.search(pat, line):
                        problems.append("%s:%d  %s\n    %s" %
                                        (fname, lineno, why, stripped))
    if problems:
        print("MicroPython-compat check FAILED:")
        for p in problems:
            print("  " + p)
        sys.exit(1)
    n = len([f for f in os.listdir(PKG)
             if f.endswith(".py") and f not in EXEMPT])
    print("MicroPython-compat check passed (%d shared modules clean)." % n)


if __name__ == "__main__":
    main()
