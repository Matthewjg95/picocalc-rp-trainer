RP TRAINING SYSTEM — PicoCalc setup
====================================

This SD card contains the complete app. It runs 100% on the PicoCalc —
no computer needed after this one-time setup.

WHAT'S HERE
  rpts_boot.py         app launcher (runs from the SD card)
  py/rpts/             app source code
  mpy/rpts/            precompiled version (used automatically if the
                       firmware accepts it; otherwise py/ is used)
  rpts_data/           your training database (created on first run)
  rpts_diag.py         on-device diagnostic (only if something looks wrong)

HOW TO LAUNCH (each boot)
  1. Put this SD card in the PicoCalc and power it on.
  2. In the boot menu, select:  RP_Training_System
     (listed alongside MicroPython, NES, etc.)
  3. At the MicroPython >>> prompt, type exactly and press Enter:

     import rpts_boot

  4. The app opens. Confirm the date when asked. Train.

  That one line is all you type. It loads only from the SD card (safe and
  fast). Your BASIC, NES, MicroPython, etc. stay selectable in the same
  boot menu whenever you like.

WHY NOT FULLY AUTOMATIC?
  This firmware bakes its own startup files into the image, so it ignores
  a filesystem auto-start file. Launching by typing one line is the
  reliable way. (Do NOT try an internal-flash installer: writing internal
  flash hangs this firmware. The SD-card launch above avoids that.)

DAILY USE
  There is no battery clock across a reset: each boot shows a date confirm
  screen, pre-filled from the last time you used the app (usually just
  arrow to fix the day, then Enter on SAVE). Within one power session the
  clock keeps correct time, so if you quit (Q) and relaunch with
  "import rpts_boot" WITHOUT a full reboot, the date is still right.
  Quit to the MicroPython prompt anytime with Q from the home screen.

DATA SAFETY
  Every set is saved to /sd/rpts_data the moment you log it. Powering
  off mid-workout is fine — the session resumes on next boot.
  To back up your training history: put this card in a computer and
  copy the rpts_data folder somewhere safe.

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
