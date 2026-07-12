"""On-device diagnostic for the RP Training System.

Run it from the PicoCalc MicroPython prompt:

    import sys; sys.path.insert(0,'/sd'); import rpts_diag

It walks through each capability the app needs — importing modules,
drawing to the screen two different ways, building a real frame, and
reading the keyboard — narrating on screen AND writing every step to
/sd/rpts_diag.log (flushed after each line). If anything hangs, the log
still holds every step up to the freeze, so the cause is unambiguous.

When it finishes (or if it hangs and you reset), put the SD card in your
computer so the log can be read.
"""
import gc
import sys
import time

LOG_PATH = "/sd/rpts_diag.log"
_logf = None


def log(msg):
    global _logf
    line = str(msg)
    try:
        print(line)
    except Exception:
        pass
    try:
        if _logf is None:
            _logf = open(LOG_PATH, "w")
        _logf.write(line)
        _logf.write("\n")
        _logf.flush()
    except Exception:
        pass


def _write(s):
    try:
        sys.stdout.write(s)
    except Exception:
        pass


def banner(msg):
    log("")
    log("========== " + msg + " ==========")


MODULES = ["rpts.compat", "rpts.themes", "rpts.canvas", "rpts.widgets",
           "rpts.exercise_db", "rpts.programs", "rpts.analytics",
           "rpts.coach", "rpts.storage", "rpts.app", "rpts.picoterm",
           "rpts.clockscreen", "rpts.screens_core"]


def run():
    banner("RPTS DIAG START")
    gc.collect()
    log("impl: %s" % (sys.implementation.name,))
    log("free at start: %d bytes" % gc.mem_free())

    # 0. did autostart get installed? inspect the internal flash filesystem
    banner("STEP 0: internal filesystem / autostart")
    try:
        import os
        root = os.listdir("/")
        log("root of internal flash: %r" % (root,))
        if "main.py" in root:
            try:
                with open("/main.py") as f:
                    body = f.read()
                log("/main.py present, %d bytes:" % len(body))
                log("  " + body.replace("\n", "\n  "))
                log("autostart installed = %s" % ("rpts_boot" in body))
            except Exception as e:
                log("could not read /main.py: %r" % e)
        else:
            log("NO /main.py on internal flash -> install did not complete")
    except Exception as e:
        log("filesystem inspect failed: %r" % e)

    # 1. which module tree is available, and does every module import?
    for base in ("/sd/mpy", "/sd/py"):
        if base not in sys.path:
            sys.path.insert(0, base)
    banner("STEP 1: import modules")
    for m in MODULES:
        try:
            __import__(m)
            gc.collect()
            log("  ok   %-22s free=%d" % (m, gc.mem_free()))
        except Exception as e:
            log("  FAIL %s -> %r" % (m, e))
            try:
                sys.print_exception(e, _logf)
            except Exception:
                pass
            log("Cannot continue without this module.")
            _close()
            return

    # 2. can the firmware terminal position text absolutely?
    banner("STEP 2: screen test A (absolute cursor positioning)")
    log("clearing screen; you should see 3 labelled lines...")
    time.sleep(1)
    _write("\x1b[2J")
    _write("\x1b[3;5HA> ABSOLUTE POSITION (row3)")
    _write("\x1b[5;5H\x1b[1;32mA> GREEN BOLD\x1b[0m")
    _write("\x1b[7;5H\x1b[7mA> INVERSE\x1b[0m")
    _write("\x1b[22;1H")
    time.sleep(4)
    log("wrote test A. On screen: did 'A> ABSOLUTE POSITION' appear at")
    log("row 3, with GREEN BOLD and INVERSE below it? (note Y/N)")

    # 3. does simple newline output show (framebuffer refresh check)?
    banner("STEP 3: screen test B (plain newlines)")
    time.sleep(1)
    _write("\x1b[2J\x1b[H")
    for i in range(6):
        _write("B> newline row %d\r\n" % i)
    time.sleep(4)
    log("wrote test B. Did 6 'B> newline row N' lines appear? (note Y/N)")

    # 4. build and draw one real home-screen frame the way the app does
    banner("STEP 4: render a real app frame")
    try:
        from rpts.storage import DB
        from rpts.picoterm import PicoVtTerm
        from rpts.app import App
        from rpts.screens_core import HomeScreen
        gc.collect()
        db = DB("/sd/rpts_data", archive_keep=24).load()
        log("db loaded, free=%d" % gc.mem_free())
        term = PicoVtTerm()
        app = App(term, db)
        app.push(HomeScreen(app))
        cv = app.build_frame()
        log("frame built %dx%d, free=%d" % (cv.w, cv.h, gc.mem_free()))
        term.enter()
        term.draw(cv, app.theme)
        _write("\x1b[40;1H")
        log("drew home frame — the dashboard should be on screen now")
        time.sleep(6)
    except Exception as e:
        log("FRAME FAIL -> %r" % e)
        try:
            sys.print_exception(e, _logf)
        except Exception:
            pass
        _close()
        return

    # 5. capture raw keyboard bytes so we can verify key decoding
    banner("STEP 5: keyboard capture (press keys for ~6 seconds)")
    _write("\x1b[2J\x1b[H")
    _write("Press keys now: try arrows, Enter, Esc, a few letters.\r\n")
    log("reading raw keyboard bytes for 6 seconds...")
    try:
        import picocalc
        kbd = picocalc.keyboard
    except Exception as e:
        log("no picocalc.keyboard: %r" % e)
        kbd = None
    if kbd is not None:
        buf = bytearray(16)
        seen = []
        end = time.time() + 6
        while time.time() < end:
            try:
                n = kbd.readinto(buf)
            except Exception as e:
                log("kbd.readinto error: %r" % e)
                break
            if n:
                for j in range(n):
                    seen.append(buf[j])
                _write(".")
            time.sleep(0.02)
        log("keyboard bytes seen: %r" % (bytes(seen),))
        log("(arrows should be 1b 5b 41-44; Enter 0d; Esc 1b 1b)")

    _write("\x1b[?25h")  # restore cursor (STEP 4's term.enter hid it)
    banner("DIAG DONE — put the SD card in your PC so the log can be read")
    _close()


def _close():
    global _logf
    try:
        if _logf:
            _logf.flush()
            _logf.close()
    except Exception:
        pass


run()
