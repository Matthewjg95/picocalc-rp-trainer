"""Optional one-time setup: install the short `import go` launch command.

Run this ONCE from the PicoCalc >>> prompt:

    import sys; sys.path.insert(0,'/sd'); import setup_go

It writes a tiny /go.py launcher to the Pico's INTERNAL flash. That file
does the sys.path setup and starts the app itself, so afterwards you can
launch any time by just typing:

    import go

IMPORTANT: on this firmware, writing internal flash can briefly FREEZE the
screen. That is expected and harmless — the file still gets written. If the
screen looks frozen after you run this, just reset the PicoCalc once; the
`import go` shortcut will work from then on.

(You never have to run this — the app also launches without any setup via
`import sys; sys.path.insert(0,'/sd'); import rpts_boot`. This just makes
the daily command shorter.)
"""

# /go.py adds the SD card to the import path, clears any cached app modules
# (so it relaunches cleanly), starts the app, then removes itself from the
# module cache so a later `import go` runs it again.
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
    sys.modules.pop('go', None)
"""

with open("/go.py", "w") as f:
    f.write(GO)

print("")
print("  Shortcut installed. Launch the app any time with:  import go")
print("  (If the screen froze while writing, reset once - it worked.)")
