"""One-time installer for the RP Training System launcher.

Run this ONCE from the PicoCalc's on-screen MicroPython REPL:

    import sys; sys.path.insert(0, '/sd'); import install_rpts

This firmware freezes its own boot.py/main.py into the image, so a
filesystem /main.py is ignored and cannot auto-start the app. Instead we
install a tiny launcher on internal flash so the app starts with a short,
memorable command from the boot prompt:

    import go

We also write /main.py in case a future firmware does honor it (harmless
either way).
"""
import os

# Short launcher on internal flash. It lives on the default import path
# (the boot working directory is '/'), so `import go` finds it without any
# sys.path setup. It purges cached modules first so `import go` relaunches
# the app cleanly every time — even after you quit back to the prompt.
GO = """# RP Training System launcher  ->  type: import go
import sys, gc
if '/sd' not in sys.path:
    sys.path.insert(0, '/sd')
for _m in list(sys.modules):
    if _m == 'rpts_boot' or _m == 'rpts' or _m.startswith('rpts.'):
        del sys.modules[_m]
gc.collect()
try:
    import rpts_boot
finally:
    sys.modules.pop('go', None)  # so a later `import go` runs again
"""

MAIN = """# RP Training System autostart (written by install_rpts.py)
import gc
gc.collect()
try:
    import sys
    sys.path.insert(0, '/sd')
    import rpts_boot
except Exception as e:
    import sys
    sys.print_exception(e)
    print('RPTS failed to start - dropping to REPL.')
"""


def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def install():
    with open("/go.py", "w") as f:
        f.write(GO)
    with open("/main.py", "w") as f:
        f.write(MAIN)
    print("")
    print("  ================ RP TRAINING SYSTEM ================")
    print("  Launcher installed on internal flash.")
    print("")
    print("  TO START THE APP, at this >>> prompt type:")
    print("")
    print("      import go")
    print("")
    print("  Do that after every boot (pick RP_Training_System in the")
    print("  boot menu first). It is the only thing you type.")
    print("  ===================================================")
    print("")


install()
