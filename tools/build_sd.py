"""Assemble the SD-card payload for the PicoCalc.

Produces (default in ./build/sd):
    rpts_boot.py, install_rpts.py, README_PICOCALC.txt   (card root)
    py/rpts/*.py       plain source (always works, slower to import)
    mpy/rpts/*.mpy     precompiled bytecode (fast, low RAM; built when
                       mpy-cross is available: pip install mpy-cross)

rpts_boot.py prefers mpy/ and falls back to py/ automatically, so it is
safe to ship both even if the firmware's bytecode ABI differs.

Usage:  python tools/build_sd.py [output_dir]
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESKTOP_ONLY = {"term.py"}


def copy_sources(out):
    py_dir = os.path.join(out, "py", "rpts")
    os.makedirs(py_dir, exist_ok=True)
    names = []
    for fname in sorted(os.listdir(os.path.join(ROOT, "rpts"))):
        if fname.endswith(".py") and fname not in DESKTOP_ONLY:
            shutil.copy2(os.path.join(ROOT, "rpts", fname),
                         os.path.join(py_dir, fname))
            names.append(fname)
    for fname in os.listdir(os.path.join(ROOT, "pico_sd")):
        src = os.path.join(ROOT, "pico_sd", fname)
        if not os.path.isfile(src) or fname.startswith("__"):
            continue  # skip __pycache__ and any stray dirs
        shutil.copy2(src, os.path.join(out, fname))
    return names


def try_mpy_cross(out, names):
    mpy_dir = os.path.join(out, "mpy", "rpts")
    os.makedirs(mpy_dir, exist_ok=True)
    for fname in names:
        src = os.path.join(out, "py", "rpts", fname)
        dst = os.path.join(mpy_dir, fname[:-3] + ".mpy")
        # no -march flag: plain bytecode runs on RP2040 and RP2350 alike
        r = subprocess.run([sys.executable, "-m", "mpy_cross", src,
                            "-o", dst], capture_output=True, text=True)
        if r.returncode != 0:
            shutil.rmtree(os.path.join(out, "mpy"), ignore_errors=True)
            return False, (r.stderr or r.stdout).strip()
    return True, "%d modules" % len(names)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else \
        os.path.join(ROOT, "build", "sd")
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out, exist_ok=True)
    names = copy_sources(out)
    ok, msg = try_mpy_cross(out, names)
    print("sources : %d modules -> py/rpts/" % len(names))
    print("mpy     : %s" % ("compiled -> mpy/rpts/ (%s)" % msg if ok
                            else "SKIPPED (%s)" % msg))
    print("root    : rpts_boot.py, install_rpts.py, README_PICOCALC.txt")
    print("output  : %s" % out)


if __name__ == "__main__":
    main()
