RP TRAINING SYSTEM — PicoCalc setup
====================================

This SD card contains the complete app. It runs 100% on the PicoCalc —
no computer needed after this one-time setup.

WHAT'S HERE
  rpts_boot.py         app launcher (runs from the SD card)
  install_rpts.py      one-time autostart installer
  py/rpts/             app source code
  mpy/rpts/            precompiled version (used automatically if the
                       firmware accepts it; otherwise py/ is used)
  rpts_data/           your training database (created on first run)

ONE-TIME SETUP (about 2 minutes, all on the PicoCalc)
  1. Put this SD card in the PicoCalc and power it on.
  2. In the boot menu, select:  RP_Training_System
     (it is now listed alongside MicroPython, NES, etc.)
  3. The first time only, you land at a MicroPython >>> prompt.
     Type exactly, then press Enter:

     import sys; sys.path.insert(0,'/sd'); import install_rpts

  4. It sets up autostart and prints a reboot command. Type it:

     import machine; machine.reset()

  5. The PicoCalc reboots. Pick RP_Training_System again — the app now
     launches straight in. Confirm the date/time when asked. Train.

EVERY BOOT AFTER THAT
  Power on -> pick RP_Training_System in the boot menu -> app launches
  directly, no typing. Your BASIC, NES, MicroPython, etc. are untouched
  and still selectable in the same menu whenever you like.

WHY THE ONE-TIME PROMPT?
  The boot menu runs a firmware image; autostart lives in the firmware's
  internal storage, which only the device itself can write. Step 3 does
  that once. After that it is fully automatic.

DAILY USE
  There is no battery clock: each boot shows a date confirm screen,
  pre-filled from the last time you used the app (usually just press
  Enter on SAVE, or fix the day first).
  Quit to the MicroPython prompt anytime with Q from the home screen.

DATA SAFETY
  Every set is saved to /sd/rpts_data the moment you log it. Powering
  off mid-workout is fine — the session resumes on next boot.
  To back up your training history: put this card in a computer and
  copy the rpts_data folder somewhere safe.

TURN OFF AUTOSTART
  Quit the app (Q), then at the >>> prompt:
      import os; os.remove('/main.py')

TROUBLESHOOTING
  App didn't start / dropped to >>>  -> is the SD card seated? Type
      import sys; sys.path.insert(0,'/sd'); import rpts_boot
  to see the error. Crashes are logged to /sd/rpts_crash.log and each
  boot's progress to /sd/rpts_boot.log.
  Garbled characters -> Settings [X] -> ASCII density should be 'ascii'
  (that is the default on the PicoCalc).

DIAGNOSTIC (run this if the screen stays blank or freezes)
  At the >>> prompt type:
      import sys; sys.path.insert(0,'/sd'); import rpts_diag
  It narrates on screen and writes /sd/rpts_diag.log. It checks: whether
  autostart installed, whether the screen handles cursor positioning and
  colors, whether a real app frame draws, and what bytes the keyboard
  sends. When it finishes (or if it freezes and you reset), put the SD
  card in your computer — the log file pinpoints the cause.
