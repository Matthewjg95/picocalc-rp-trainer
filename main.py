#!/usr/bin/env python3
"""RP Training System launcher.

Usage:  python main.py
Env:    RPTS_DATA   override the data directory (default: ./data)
        RPTS_COLS / RPTS_ROWS   force a fixed screen size (e.g. PicoCalc)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rpts.app import App
from rpts.screens_core import HomeScreen
from rpts.storage import DB
from rpts.term import Term


def main():
    try:  # box-drawing chars need UTF-8 even on legacy Windows consoles
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    data_dir = os.environ.get("RPTS_DATA") or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "data")
    db = DB(data_dir).load()
    terminal = Term()
    app = App(terminal, db)
    app.push(HomeScreen(app))
    terminal.enter()
    try:
        app.run()
    except KeyboardInterrupt:
        pass
    finally:
        terminal.exit()
        db.save()


if __name__ == "__main__":
    main()
