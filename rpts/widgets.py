"""Drawing primitives: frames, bars, gauges, sparklines, tables."""

BOX_UNICODE = dict(tl="┌", tr="┐", bl="└", br="┘", h="─", v="│",
                   lt="├", rt="┤", tt="┬", bt="┴", x="┼")
BOX_ASCII = dict(tl="+", tr="+", bl="+", br="+", h="-", v="|",
                 lt="+", rt="+", tt="+", bt="+", x="+")
SPARK_UNICODE = "▁▂▃▄▅▆▇█"
SPARK_ASCII = "_.:-=+*#"

# safety net for ascii charset mode: transliterate anything non-7-bit that
# slipped into the frame (literal text, future additions)
ASCII_TRANSLATE = {
    "·": ".", "—": "-", "–": "-", "…": "...", "↑": "^", "↓": "v",
    "★": "*", "■": "#", "□": "o", "▸": ">", "█": "#", "░": ".",
    "─": "-", "│": "|", "┌": "+", "┐": "+", "└": "+", "┘": "+",
    "├": "+", "┤": "+", "┬": "+", "┴": "+", "┼": "+",
    "▁": "_", "▂": ".", "▃": ":", "▄": "-", "▅": "=", "▆": "+", "▇": "*",
}


class Style:
    """Charset bundle derived from settings (unicode vs ascii density)."""

    def __init__(self, settings):
        uni = settings.get("charset", "unicode") == "unicode"
        self.box = BOX_UNICODE if uni else BOX_ASCII
        self.full = "█" if uni else "#"
        self.empty = "░" if uni else "."
        self.spark = SPARK_UNICODE if uni else SPARK_ASCII
        self.bullet = "▸" if uni else ">"
        self.arrow_up = "↑" if uni else "^"
        self.arrow_dn = "↓" if uni else "v"
        self.blk_done = "■" if uni else "#"
        self.blk_miss = "□" if uni else "o"
        self.blk_rest = "·" if uni else "."
        self.star = "★" if uni else "*"


def clip(s, w):
    s = str(s)
    return s if len(s) <= w else (s[: max(0, w - 1)] + "~")


def wrap(text, width):
    """Word-wrap text into a list of lines no wider than `width`."""
    words = str(text).split(" ")
    lines, cur = [], ""
    for wd in words:
        if not cur:
            cur = wd
        elif len(cur) + 1 + len(wd) <= width:
            cur += " " + wd
        else:
            lines.append(cur)
            cur = wd
        while len(cur) > width:          # a single word longer than width
            lines.append(cur[:width])
            cur = cur[width:]
    if cur:
        lines.append(cur)
    return lines or [""]


def lj(s, n):
    """str.ljust (not available on MicroPython)."""
    s = str(s)
    return s + " " * (n - len(s)) if len(s) < n else s


def rj(s, n):
    """str.rjust (not available on MicroPython)."""
    s = str(s)
    return " " * (n - len(s)) + s if len(s) < n else s


def frame(cv, x, y, w, h, st, title=None, attr="dim", title_attr="title"):
    """Draw a box; optional title embedded in the top border."""
    b = st.box
    cv.put(x, y, b["tl"] + b["h"] * (w - 2) + b["tr"], attr)
    for yy in range(y + 1, y + h - 1):
        cv.put(x, yy, b["v"], attr)
        cv.put(x + w - 1, yy, b["v"], attr)
    cv.put(x, y + h - 1, b["bl"] + b["h"] * (w - 2) + b["br"], attr)
    if title:
        t = " %s " % clip(title, w - 6)
        cv.put(x + 2, y, t, title_attr)


def hsep(cv, x, y, w, st, attr="dim"):
    """Horizontal separator joining a frame's side borders."""
    b = st.box
    cv.put(x, y, b["lt"] + b["h"] * (w - 2) + b["rt"], attr)


def bar(pct, width, st):
    pct = max(0.0, min(1.0, pct))
    n = int(round(pct * width))
    return st.full * n + st.empty * (width - n)


def load_attr(pct):
    """Color for a utilization value: green -> yellow -> red."""
    if pct >= 0.85:
        return "bad"
    if pct >= 0.65:
        return "warn"
    return "good"


def health_attr(pct):
    """Color for a 'higher is better' value (recovery, readiness)."""
    if pct >= 0.70:
        return "good"
    if pct >= 0.40:
        return "warn"
    return "bad"


def resample(vals, n):
    """Reduce/stretch a series to exactly n points (mean-pooled)."""
    if not vals or n <= 0:
        return []
    if len(vals) <= n:
        return list(vals)
    out = []
    step = len(vals) / n
    for i in range(n):
        lo, hi = int(i * step), max(int(i * step) + 1, int((i + 1) * step))
        chunk = vals[lo:hi]
        out.append(sum(chunk) / len(chunk))
    return out


def spark(vals, st, width=None):
    """Unicode sparkline of a numeric series."""
    if width:
        vals = resample(list(vals), width)
    if not vals:
        return ""
    lo, hi = min(vals), max(vals)
    if hi - lo < 1e-9:
        return st.spark[3] * len(vals)
    ramp = st.spark
    return "".join(
        ramp[min(len(ramp) - 1, int((v - lo) / (hi - lo) * (len(ramp) - 1) + 0.5))]
        for v in vals)


def gauge(cv, x, y, label, pct, st, label_w=10, bar_w=10, attr=None,
          text=None):
    """One-line labelled gauge:  Recovery   ████████░░  84%"""
    a = attr or health_attr(pct)
    cv.put(x, y, lj(clip(label, label_w), label_w), "")
    cv.put(x + label_w + 1, y, bar(pct, bar_w, st), a)
    cv.put(x + label_w + bar_w + 2, y, text if text is not None
           else "%3d%%" % round(pct * 100), a)


def trend_arrow(slope, st):
    if slope > 0.01:
        return st.arrow_up, "good"
    if slope < -0.01:
        return st.arrow_dn, "bad"
    return "=", "dim"
