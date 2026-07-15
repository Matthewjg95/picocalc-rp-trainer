"""RP Training System — PicoCalc boot entry.

Lives on the SD card root. Started by /main.py on internal flash (see
install_rpts.py), or manually from the on-screen REPL:

    import sys; sys.path.insert(0, '/sd'); import rpts_boot

Loads the app from /sd/mpy (precompiled, fast + low RAM) with a fallback
to /sd/py (plain source), sets up the clock, and runs the UI.
"""
import gc
import sys

DATA_DIR = "/sd/rpts_data"
CLOCK_FILE = DATA_DIR + "/clock.txt"
BOOT_LOG = "/sd/rpts_boot.log"


def _blog(msg):
    """Append a boot-phase marker to the SD card (flushed immediately) so a
    hang or crash during startup leaves a precise trace to read later."""
    try:
        with open(BOOT_LOG, "a") as f:
            try:
                free = gc.mem_free()
            except AttributeError:
                free = -1
            f.write("%s (free=%d)\n" % (msg, free))
    except OSError:
        pass


def _purge_rpts_modules():
    for name in list(sys.modules):
        if name == "rpts" or name.startswith("rpts."):
            del sys.modules[name]


def _import_app():
    """Load the app, preferring the low-RAM .mpy tree and falling back to
    plain .py source only if .mpy is absent or ABI-incompatible.

    Modules are imported one at a time with a gc.collect() between each so
    the transient allocations of one import are reclaimed before the next
    — this lowers *peak* heap use, which is what triggers MemoryError on
    the RP2040's small heap. A MemoryError is NOT caught here: retrying
    with the heavier .py path would only make it worse, so it propagates
    to run() for a clean message."""
    err = None
    for base in ("/sd/mpy", "/sd/py"):
        if base in sys.path:
            sys.path.remove(base)
        sys.path.insert(0, base)
        _purge_rpts_modules()
        gc.collect()
        try:
            from rpts.storage import DB
            gc.collect()
            from rpts.picoterm import PicoVtTerm
            gc.collect()
            from rpts.clockscreen import ClockScreen, restore_clock
            gc.collect()
            from rpts.app import App
            gc.collect()
            from rpts.screens_core import HomeScreen
            gc.collect()
            return App, ClockScreen, restore_clock, PicoVtTerm, \
                HomeScreen, DB
        except MemoryError:
            raise  # heavier .py path won't help; surface it in run()
        except Exception as e:
            # missing file, .mpy ABI mismatch, OR a CORRUPT .mpy on a bad
            # SD sector — any of these should fall through to the .py tree
            err = e
            _blog("import via %s failed: %r -> trying next tree" % (base, e))
            if base in sys.path:
                sys.path.remove(base)
            _purge_rpts_modules()
            gc.collect()
    raise err


def run():
    gc.collect()
    try:
        # collect earlier and more often — favors low peak over speed
        gc.threshold(gc.mem_free() // 4)
    except AttributeError:
        pass
    print("RP Training System loading...")
    _blog("--- boot start ---")
    try:
        (App, ClockScreen, restore_clock, PicoVtTerm,
         HomeScreen, DB) = _import_app()
        _blog("phase: modules imported")
    except MemoryError:
        print("Not enough free RAM to load. Do a FULL power cycle")
        print("(switch off, not just reset), then relaunch.")
        try:
            print("free bytes:", gc.mem_free())
        except AttributeError:
            pass
        return
    gc.collect()
    try:
        import os
        os.mkdir(DATA_DIR)
    except OSError:
        pass
    restore_clock(CLOCK_FILE)
    # the live window holds compact session SUMMARIES; full set-by-set
    # records stream from the JSONL archive on the card. Measured on
    # device: 24 summaries parse to ~52 KB of objects, leaving ~20 KB
    # after the first frame — opening a dashboard (lazy ~20 KB module
    # import) then OOMed. 14 summaries (~30 KB parsed) leaves the UI
    # real headroom, and still covers 2+ program cycles for the coach.
    db = DB(DATA_DIR, archive_keep=14, bw_keep=60).load()
    _blog("phase: db loaded")
    s = db.data["settings"]
    if not s.get("pico_tuned"):
        # the vt100 firmware font is ASCII; unicode art would render as
        # mojibake. Users can flip these back in Settings to experiment.
        s["charset"] = "ascii"
        s["graph_detail"] = "low"
        s["pico_tuned"] = True
        db.save()
    term = PicoVtTerm(clock_file=CLOCK_FILE)
    app = App(term, db)
    app.push(HomeScreen(app))
    app.push(ClockScreen(app, CLOCK_FILE))
    _blog("phase: screens ready, entering UI")
    term.enter()
    app.on_first_draw = lambda: _blog("phase: first frame drawn")
    try:
        app.run()
        _blog("phase: UI exited cleanly")
    except KeyboardInterrupt:
        pass
    except Exception as e:
        try:
            with open("/sd/rpts_crash.log", "a") as f:
                f.write("\n--- crash ---\n")
                sys.print_exception(e, f)
        except OSError:
            pass
        term.exit()
        raise
    term.exit()
    db.save()
    print("RP Training System closed.  Type 'import go' to restart,")
    print("or press the reset button.")


run()
