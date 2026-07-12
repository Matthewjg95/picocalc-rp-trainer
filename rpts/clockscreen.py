"""Boot-time clock confirmation for battery-less RTCs (PicoCalc).

The Pico's RTC resets on power loss, but a workout log lives and dies by
its dates. On boot we restore the last persisted timestamp, then show a
quick date/time confirm screen — usually two keypresses: adjust day,
Enter. Device-only; desktop never pushes this screen.
"""
import time

from . import compat
from .app import Field, FormScreen


def restore_clock(clock_file):
    """If the RTC looks unset (cold boot -> year 2021 on rp2), push it to
    the last timestamp we persisted. Returns the ISO string used, or None.
    """
    if time.localtime()[0] >= 2025:
        return None  # RTC already plausible (warm reset)
    try:
        with open(clock_file) as f:
            iso = f.read().strip()
        y, m, d = compat.parse_iso(iso)
        hh = int(iso[11:13]) if len(iso) >= 16 else 12
        mm = int(iso[14:16]) if len(iso) >= 16 else 0
    except (OSError, ValueError, IndexError):
        return None
    _set_rtc(y, m, d, hh, mm)
    return iso


def _set_rtc(y, mo, d, hh, mm):
    import machine
    wd = compat.weekday(compat.fmt_date(y, mo, d))
    machine.RTC().datetime((y, mo, d, wd, hh, mm, 0, 0))


class ClockScreen(FormScreen):
    """Confirm/adjust date and time; sets the RTC and persists it."""

    def __init__(self, app, clock_file):
        self.clock_file = clock_file
        t = time.localtime()
        y, mo, d, hh = t[0], t[1], t[2], t[3]
        if y < 2025:
            y, mo, d, hh = 2026, 1, 1, 12
        # date is what a training log needs; hour is enough for ordering.
        # minutes were dropped — they added typing for no real benefit.
        fields = [
            Field("y", "Year", "int", y, lo=2025, hi=2100),
            Field("mo", "Month", "int", mo, lo=1, hi=12),
            Field("d", "Day", "int", d, lo=1, hi=31),
            Field("hh", "Hour", "int", hh, lo=0, hi=23),
        ]
        super().__init__(app, "CONFIRM DATE", fields,
                         intro=["No battery clock on this hardware -",
                                "check the date so your log stays true.",
                                "(ESC keeps the restored clock)"])

    def submit(self):
        v = self.values()
        # clamp day to the month's length
        days = [31, 29 if v["y"] % 4 == 0 and
                (v["y"] % 100 != 0 or v["y"] % 400 == 0) else 28,
                31, 30, 31, 30, 31, 31, 30, 31, 30, 31][v["mo"] - 1]
        v["d"] = min(v["d"], days)
        try:
            _set_rtc(v["y"], v["mo"], v["d"], v["hh"], 0)
        except ImportError:
            pass  # desktop / no machine module
        try:
            with open(self.clock_file, "w") as f:
                f.write(compat.now_iso())
        except OSError:
            pass
        self.app.pop()
