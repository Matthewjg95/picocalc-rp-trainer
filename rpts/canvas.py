"""Character canvas: a w x h grid of (char, attr) cells.

Two implementations with identical put/fill/clear/render APIs:

* Canvas      — list-of-lists of Python str objects. Handles Unicode
                (box-drawing glyphs) and is used on the desktop.
* ByteCanvas  — two flat bytearrays (one char byte + one attr index per
                cell). ~10x less RAM and near-zero per-frame allocation,
                which is what the RP2040 needs. ASCII only, which is fine
                because the PicoCalc runs in ascii charset mode.

`build_frame()` picks ByteCanvas on MicroPython, Canvas on desktop.
"""

# attr name -> small integer index (ByteCanvas stores the index per cell)
ATTR_ORDER = ("", "dim", "hi", "title", "good", "warn", "bad", "accent",
              "inv")
ATTR_INDEX = {a: i for i, a in enumerate(ATTR_ORDER)}

# unicode codepoint -> ascii byte, a safety net for any glyph that reaches
# a ByteCanvas (the device draws in ascii mode, so this rarely triggers)
_FALLBACK = {
    0x2500: 45, 0x2502: 124, 0x250C: 43, 0x2510: 43, 0x2514: 43,
    0x2518: 43, 0x251C: 43, 0x2524: 43, 0x252C: 43, 0x2534: 43,
    0x253C: 43, 0x2588: 35, 0x2591: 46, 0x00B7: 46, 0x2014: 45,
    0x2013: 45, 0x2192: 62, 0x2191: 94, 0x2193: 118, 0x25A0: 35,
    0x25A1: 111, 0x2605: 42, 0x25B8: 62, 0x2026: 46,
    0x2581: 95, 0x2582: 46, 0x2583: 58, 0x2584: 45, 0x2585: 61,
    0x2586: 43, 0x2587: 42,
}


class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.chars = [[" "] * w for _ in range(h)]
        self.attrs = [[""] * w for _ in range(h)]

    def put(self, x, y, s, attr=""):
        if not 0 <= y < self.h:
            return
        row, arow = self.chars[y], self.attrs[y]
        for i, ch in enumerate(str(s)):
            xx = x + i
            if 0 <= xx < self.w:
                row[xx] = ch
                arow[xx] = attr

    def fill(self, x, y, w, h, ch=" ", attr=""):
        line = ch * w
        for yy in range(y, y + h):
            self.put(x, yy, line, attr)

    def clear(self, ch=" ", attr=""):
        """Reset every cell in place, reusing the existing row lists so a
        redraw doesn't reallocate the whole grid (matters on the RP2040)."""
        for y in range(self.h):
            row, arow = self.chars[y], self.attrs[y]
            for x in range(self.w):
                row[x] = ch
                arow[x] = attr

    def render(self, theme):
        """ANSI-decorated string per row."""
        out = []
        for y in range(self.h):
            parts, cur = [], None
            row, arow = self.chars[y], self.attrs[y]
            for x in range(self.w):
                a = arow[x]
                if a != cur:
                    parts.append("\x1b[0m" + theme.get(a, ""))
                    cur = a
                parts.append(row[x])
            parts.append("\x1b[0m")
            out.append("".join(parts))
        return out


class ByteCanvas:
    """Flat-bytearray canvas: 1 char byte + 1 attr-index byte per cell.
    Same API as Canvas but ~10x lighter and allocation-free to clear."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        n = w * h
        self._blank = b" " * n          # reusable templates for fast clear
        self._zero = b"\x00" * n        # (not bytes(n) — clearer on upy)
        self.chars = bytearray(self._blank)
        self.attrs = bytearray(self._zero)

    def put(self, x, y, s, attr=""):
        if not 0 <= y < self.h:
            return
        ai = ATTR_INDEX.get(attr, 0)
        base = y * self.w
        w = self.w
        chars, attrs = self.chars, self.attrs
        s = str(s)
        for i in range(len(s)):
            xx = x + i
            if 0 <= xx < w:
                c = ord(s[i])
                if c > 127:
                    c = _FALLBACK.get(c, 63)  # 63 = '?'
                chars[base + xx] = c
                attrs[base + xx] = ai

    def fill(self, x, y, w, h, ch=" ", attr=""):
        line = str(ch) * w
        for yy in range(y, y + h):
            self.put(x, yy, line, attr)

    def clear(self, ch=" ", attr=""):
        if ch == " " and ATTR_INDEX.get(attr, 0) == 0:
            # in-place, allocation-free reset via memoryview chunk copies —
            # under heap pressure/fragmentation even a 2 KB alloc can fail
            # (it crashed the device), so clear() must not allocate at all
            try:
                dst_c = memoryview(self.chars)
                dst_a = memoryview(self.attrs)
                src_c = memoryview(self._blank)
                src_a = memoryview(self._zero)
                n = len(self.chars)
                i = 0
                while i < n:
                    j = min(i + 256, n)
                    dst_c[i:j] = src_c[i:j]
                    dst_a[i:j] = src_a[i:j]
                    i = j
            except (TypeError, NotImplementedError):
                # runtime without memoryview slice assignment: reallocate
                self.chars = bytearray(self._blank)
                self.attrs = bytearray(self._zero)
            return
        c = ord(ch)
        if c > 127:
            c = 32
        ai = ATTR_INDEX.get(attr, 0)
        for i in range(len(self.chars)):
            self.chars[i] = c
            self.attrs[i] = ai

    def render(self, theme):
        out = []
        w = self.w
        chars, attrs = self.chars, self.attrs
        order = ATTR_ORDER
        for y in range(self.h):
            base = y * w
            parts, cur = [], -1
            for x in range(w):
                a = attrs[base + x]
                if a != cur:
                    parts.append("\x1b[0m" + theme.get(order[a], ""))
                    cur = a
                parts.append(chr(chars[base + x]))
            parts.append("\x1b[0m")
            out.append("".join(parts))
        return out
