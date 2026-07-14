"""Compatibility layer so the whole engine runs on CPython 3.8+ AND
MicroPython (RP2040/RP2350). Everything here is dependency-free and uses
only features present in both runtimes.

Provides:
  * pure-Python calendar math (MicroPython has no datetime)
  * filesystem helpers (MicroPython has no os.path / shutil)
  * minimal CSV quoting/parsing (MicroPython has no csv)
  * json dump with best-effort indent
  * deep clone, max/min with default, thousands formatting
"""
import json
import os
import sys
import time

MICROPYTHON = sys.implementation.name == "micropython"


# -- calendar -----------------------------------------------------------
# Howard Hinnant's days-from-civil algorithms (proleptic Gregorian).

def _days_from_civil(y, m, d):
    """Days since 1970-01-01."""
    y -= 1 if m <= 2 else 0
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - era * 400
    doy = (153 * (m + (9 if m <= 2 else -3)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def _civil_from_days(z):
    z += 719468
    era = (z if z >= 0 else z - 146096) // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + (3 if mp < 10 else -9)
    return y + (1 if m <= 2 else 0), m, d


def parse_iso(s):
    """'YYYY-MM-DD...' -> (y, m, d)."""
    return int(s[0:4]), int(s[5:7]), int(s[8:10])


def fmt_date(y, m, d):
    return "%04d-%02d-%02d" % (y, m, d)


def to_ord(iso):
    y, m, d = parse_iso(iso)
    return _days_from_civil(y, m, d)


def from_ord(z):
    return fmt_date(*_civil_from_days(z))


def today():
    t = time.localtime()
    return fmt_date(t[0], t[1], t[2])


def now_iso():
    t = time.localtime()
    return "%s %02d:%02d:%02d" % (fmt_date(t[0], t[1], t[2]),
                                  t[3], t[4], t[5])


def stamp():
    t = time.localtime()
    return "%04d%02d%02d_%02d%02d%02d" % (t[0], t[1], t[2], t[3], t[4], t[5])


def date_add(iso, days):
    return from_ord(to_ord(iso) + days)


def date_diff(a, b):
    """Days from b to a (a - b)."""
    return to_ord(a) - to_ord(b)


def weekday(iso):
    """0 = Monday."""
    return (to_ord(iso) + 3) % 7  # 1970-01-01 was a Thursday


def monday_of(iso):
    return date_add(iso, -weekday(iso))


def iso_week(iso):
    """ISO 8601 (year, week) — the week that owns the date's Thursday."""
    z = to_ord(iso)
    thursday = z - ((z + 3) % 7) + 3
    ty, _, _ = _civil_from_days(thursday)
    jan1 = _days_from_civil(ty, 1, 1)
    return ty, (thursday - jan1) // 7 + 1


def week_key(iso):
    y, w = iso_week(iso)
    return "%d-W%02d" % (y, w)


# -- filesystem ---------------------------------------------------------

_HAS_PATH = hasattr(os, "path")


def pjoin(*parts):
    if _HAS_PATH:
        return os.path.join(*parts)
    return "/".join(p.rstrip("/") for p in parts if p)


def exists(path):
    if _HAS_PATH:
        return os.path.exists(path)
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def getsize(path):
    return os.stat(path)[6]


def makedirs(path):
    if _HAS_PATH:
        os.makedirs(path, exist_ok=True)
        return
    parts = path.split("/")
    cur = ""
    for p in parts:
        if not p:
            cur = "/"
            continue
        cur = cur + ("" if cur in ("", "/") else "/") + p
        try:
            os.mkdir(cur)
        except OSError:
            pass


def replace(src, dst):
    if hasattr(os, "replace"):
        os.replace(src, dst)
        return
    try:
        os.remove(dst)
    except OSError:
        pass
    os.rename(src, dst)


def remove_quiet(path):
    try:
        os.remove(path)
    except OSError:
        pass


def copyfile(src, dst, bufsize=1024):
    with open(src, "rb") as fi, open(dst, "wb") as fo:
        while True:
            chunk = fi.read(bufsize)
            if not chunk:
                break
            fo.write(chunk)


def listdir_sorted(path):
    try:
        return sorted(os.listdir(path))
    except OSError:
        return []


# -- json ---------------------------------------------------------------

def json_dump(obj, f):
    # compact on purpose: pretty-printing added ~40% pure whitespace, and
    # the RP2040 has to fit the parsed document in RAM
    try:
        json.dump(obj, f, separators=(",", ":"))
    except TypeError:  # MicroPython json may not take separators
        json.dump(obj, f)


# -- csv -------------------------------------------------------------------

def csv_row(values):
    out = []
    for v in values:
        s = "" if v is None else str(v)
        if any(c in s for c in ',"\n\r'):
            s = '"' + s.replace('"', '""') + '"'
        out.append(s)
    return ",".join(out)


def csv_split(line):
    out, cur, in_q = [], [], False
    i, n = 0, len(line)
    while i < n:
        c = line[i]
        if in_q:
            if c == '"':
                if i + 1 < n and line[i + 1] == '"':
                    cur.append('"')
                    i += 1
                else:
                    in_q = False
            else:
                cur.append(c)
        elif c == '"':
            in_q = True
        elif c == ",":
            out.append("".join(cur))
            cur = []
        elif c not in "\r\n":
            cur.append(c)
        i += 1
    out.append("".join(cur))
    return out


# -- misc -----------------------------------------------------------------

def clone(obj):
    """Deep copy of JSON-shaped data (no copy module on MicroPython)."""
    return json.loads(json.dumps(obj))


def gmax(iterable, default=0):
    """max() with default (MicroPython max() lacks the kwarg)."""
    best, found = default, False
    for v in iterable:
        if not found or v > best:
            best, found = v, True
    return best


def group_thousands(n):
    """12345 -> '12,345' (MicroPython format() lacks the ',' spec)."""
    neg = n < 0
    s = str(int(round(abs(n))))
    parts = []
    while len(s) > 3:
        parts.insert(0, s[-3:])
        s = s[:-3]
    parts.insert(0, s)
    return ("-" if neg else "") + ",".join(parts)
