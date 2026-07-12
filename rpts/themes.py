"""ANSI color themes, shared by the desktop terminal and the PicoCalc's
VT100 terminal emulator (which parses standard SGR sequences).

Attribute names used by all drawing code:
  ""      normal text          "dim"    chrome / borders
  "hi"    emphasized           "title"  panel titles
  "good"  ok / green zone      "warn"   caution      "bad"  danger
  "accent" secondary highlight "inv"    inverse (selection)
"""

THEMES = {
    "phosphor": {
        "": "\x1b[32m", "dim": "\x1b[2;32m", "hi": "\x1b[1;92m",
        "title": "\x1b[1;92m", "good": "\x1b[92m", "warn": "\x1b[93m",
        "bad": "\x1b[91m", "accent": "\x1b[96m", "inv": "\x1b[7;32m",
    },
    "amber": {
        "": "\x1b[33m", "dim": "\x1b[2;33m", "hi": "\x1b[1;93m",
        "title": "\x1b[1;93m", "good": "\x1b[92m", "warn": "\x1b[93m",
        "bad": "\x1b[91m", "accent": "\x1b[97m", "inv": "\x1b[7;33m",
    },
    "cyan": {
        "": "\x1b[36m", "dim": "\x1b[2;36m", "hi": "\x1b[1;96m",
        "title": "\x1b[1;96m", "good": "\x1b[92m", "warn": "\x1b[93m",
        "bad": "\x1b[91m", "accent": "\x1b[95m", "inv": "\x1b[7;36m",
    },
    "white": {
        "": "\x1b[37m", "dim": "\x1b[90m", "hi": "\x1b[1;97m",
        "title": "\x1b[1;97m", "good": "\x1b[92m", "warn": "\x1b[93m",
        "bad": "\x1b[91m", "accent": "\x1b[96m", "inv": "\x1b[7m",
    },
    "mono": {
        "": "", "dim": "\x1b[2m", "hi": "\x1b[1m",
        "title": "\x1b[1m", "good": "", "warn": "\x1b[1m",
        "bad": "\x1b[7m", "accent": "\x1b[4m", "inv": "\x1b[7m",
    },
}
