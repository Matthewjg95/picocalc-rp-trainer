"""RP Training System — an offline strength-training operating system.

Layers:
    term        low-level terminal driver (ANSI, themes, keyboard)
    widgets     drawing primitives (frames, bars, sparklines, gauges)
    exercise_db exercise library + RP volume landmarks
    programs    program templates (UL / PPL / FB)
    storage     JSON persistence, backup, CSV import/export
    analytics   derived metrics (e1RM, tonnage, trends, PRs)
    coach       RP auto-regulation engine (MEV/MAV/MRV, deloads, swaps)
    app         screen manager / event loop
    screens_*   user interface screens
"""

VERSION = "1.0"
APP_NAME = "RP TRAINING SYSTEM"
