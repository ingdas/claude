#!/usr/bin/env python3
"""Generate the Hatched Hour watch face (Watch Face Format v1) and matching previews.

    python3 tools/generate.py                       # writes app/src/main/res/raw/watchface.xml
    python3 tools/generate.py --svg 10:31:20 10:58:00@2 10:31:20~aod   # preview SVGs in docs/build/

Concept: a wall drawing that builds itself every hour.
  * Every hour starts with an empty grid of 12 cells (a De Stijl-style subdivision).
  * The cells are worked clockwise from 12 o'clock, 5 minutes each. Each cell is filled with
    parallel lines in its own direction and colour, after Sol LeWitt's wall drawings. Every
    line grows from nothing to full length in its own time slot, so the pen is always moving.
  * By :59 the drawing is finished; at :00 a new grid starts. There are 4 seeded grids,
    rotated by 0/90/180/270 degrees through the 12 hours, so every hour looks different.
  * A ring of 60 ticks fills up with the seconds. The time, date, battery, heart rate and steps
    sit on a sign in the middle. The 8 and 4 o'clock buttons are app-shortcut slots
    (Spotify / Google Wallet).
"""
from __future__ import annotations

import argparse
import math
import os
from xml.sax.saxutils import escape, quoteattr

SIZE = 450
C = SIZE / 2
VIEW_R = 222                 # visible radius used to clip hatch lines
CELLS = 12
CELL_SECONDS = 3600 // CELLS  # 300 s per cell
VARIANTS = 4                 # seeded grids; hour % 4 picks one, hour // 4 rotates it
SPACING = 9.0
HATCH_W = 2.4
GRID = "#3A3A3A"
TICK_R1, TICK_R2 = 206, 214
SHORTCUT_R = 196
SHORTCUT_HOURS = (8, 4)
SIGN_W, SIGN_H = 156, 84
WHITE = "#F2F2F2"

PALETTES = [  # id, name, 5 hatch colours (index 3 is also the sign colour)
    ("primary", "Primary", ["#D8352A", "#1F4FBF", "#F2C230", "#E9E4D8", "#8A8A8A"]),
    ("mono_red", "Mono + Red", ["#D8352A", "#5A5A5A", "#9A9A9A", "#D0D0D0", "#F2F2F2"]),
    ("neon", "Neon Night", ["#E0187A", "#0AA5C2", "#B5F23D", "#E6DDFF", "#FF9F1C"]),
]
PAL = [f"[CONFIGURATION.palette.{i}]" for i in range(5)]
DIRS = [-90, 0, -45, 45]     # drawing direction per cell (screen degrees): up, right, up-right, down-right
T_EXPR = "([MINUTE] * 60 + [SECOND_MILLISECOND])"


# ----------------------------------------------------------------------------- geometry
def prng(seed: int):
    s = (seed * 9301 + 49297) % 2147483647 or 1

    def nxt() -> float:
        nonlocal s
        s = (s * 16807) % 2147483647
        return s / 2147483647

    return nxt


def area(c):
    return c[2] * c[3]


def clock_angle(cell, rot=0):
    cx, cy = cell[0] + cell[2] / 2 - C, cell[1] + cell[3] / 2 - C
    return (math.degrees(math.atan2(cx, -cy)) + rot + 360) % 360


def subdivide(seed: int, n: int = CELLS, min_side: float = 70):
    """Split the face into n rectangles, always splitting one of the largest visible cells."""
    rnd = prng(seed)
    cells = [(0.0, 0.0, float(SIZE), float(SIZE))]
    guard = 0
    while len(cells) < n and guard < 500:
        guard += 1
        vis = [(c, i) for i, c in enumerate(cells) if math.hypot(c[0] + c[2] / 2 - C, c[1] + c[3] / 2 - C) < 200]
        vis.sort(key=lambda ci: -area(ci[0]))
        c, i = vis[int(rnd() * min(3, len(vis)))]
        x, y, w, h = c
        k = 0.34 + rnd() * 0.32
        if w >= h and w * min(k, 1 - k) >= min_side / 2:
            cells[i:i + 1] = [(x, y, w * k, h), (x + w * k, y, w * (1 - k), h)]
        elif h * min(k, 1 - k) >= min_side / 2:
            cells[i:i + 1] = [(x, y, w, h * k), (x, y + h * k, w, h * (1 - k))]
    # work the cells clockwise from 12 o'clock
    return sorted(cells, key=lambda c: clock_angle(c))


def clip_rect(p, u, rect, inset=4):
    """Intersect the infinite line p + t*u with the inset rect (Liang-Barsky). Returns (t0, t1) or None."""
    x, y, w, h = rect
    lo, hi = -1e9, 1e9
    for pc, uc, a, b in ((p[0], u[0], x + inset, x + w - inset), (p[1], u[1], y + inset, y + h - inset)):
        if abs(uc) < 1e-9:
            if pc < a or pc > b:
                return None
        else:
            t1, t2 = (a - pc) / uc, (b - pc) / uc
            lo, hi = max(lo, min(t1, t2)), min(hi, max(t1, t2))
    return (lo, hi) if hi > lo else None


def clip_circle(p, u, t0, t1, r=VIEW_R):
    dx, dy = p[0] - C, p[1] - C
    b = dx * u[0] + dy * u[1]
    cc = dx * dx + dy * dy - r * r
    disc = b * b - cc
    if disc <= 0:
        return None
    s = math.sqrt(disc)
    lo, hi = max(t0, -b - s), min(t1, -b + s)
    return (lo, hi) if hi > lo else None


def hatch_lines(cell, direction):
    """Parallel lines filling a cell, each (start, end), ordered across the cell."""
    a = math.radians(direction)
    u = (math.cos(a), math.sin(a))
    nrm = (-u[1], u[0])
    x, y, w, h = cell
    corners = [(x, y), (x + w, y), (x, y + h), (x + w, y + h)]
    proj = [cx * nrm[0] + cy * nrm[1] for cx, cy in corners]
    lines = []
    off = min(proj) + SPACING / 2
    while off < max(proj):
        p = (nrm[0] * off, nrm[1] * off)
        seg = clip_rect(p, u, cell)
        if seg:
            seg = clip_circle(p, u, *seg)
        if seg and seg[1] - seg[0] > 6:
            s0 = (p[0] + u[0] * seg[0], p[1] + u[1] * seg[0])
            s1 = (p[0] + u[0] * seg[1], p[1] + u[1] * seg[1])
            lines.append((s0, s1))
        off += SPACING
    return lines


def variant(v: int):
    """[(cell, colour index, direction, [lines])] for grid variant v."""
    cells = subdivide(v * 131 + 7)
    return [(cell, k % 5, DIRS[(k + v) % 4], hatch_lines(cell, DIRS[(k + v) % 4])) for k, cell in enumerate(cells)]


VARIANT_CACHE = [variant(v) for v in range(VARIANTS)]
ROTATIONS = 12 // VARIANTS  # each variant is shown at 0, 90 and 180 degrees


def start_offsets(v):
    """For each rotation, which cell (in the variant's clockwise order) is at 12 o'clock.
    Rotating a clockwise order only shifts its start, so the build always begins at the top."""
    cells = [c for c, *_ in VARIANT_CACHE[v]]
    return [min(range(len(cells)), key=lambda k: clock_angle(cells[k], r * 90)) for r in range(ROTATIONS)]


OFFSETS = [start_offsets(v) for v in range(VARIANTS)]


def build_slot(v, k, rot_index):
    """Position of cell k in the build order for this variant and rotation."""
    return (k - OFFSETS[v][rot_index]) % CELLS


def line_window(slot, j, n):
    """Start time and duration (seconds into the hour) of line j of n in the cell built at `slot`."""
    dur = CELL_SECONDS / n
    return CELL_SECONDS * slot + dur * j, dur


ROT_EXPR = "floor([HOUR_0_11] / 4)"


def slot_expr(v, k):
    o = OFFSETS[v]
    off = f"({ROT_EXPR} == 1 ? {o[1]} : ({ROT_EXPR} == 2 ? {o[2]} : {o[0]}))"
    return f"(({k} + {CELLS} - {off}) % {CELLS})"


# ----------------------------------------------------------------------------- XML helpers
INT_GEOMETRY = {"Group", "PartDraw", "PartText", "PartImage", "ComplicationSlot", "BoundingOval", "BoundingBox"}


class X:
    def __init__(self):
        self.parts: list[str] = []

    def open(self, tag, **a):
        self.parts.append(f"<{tag}{fmt(a, tag)}>")

    def close(self, tag):
        self.parts.append(f"</{tag}>")

    def leaf(self, tag, text=None, **a):
        self.parts.append(f"<{tag}{fmt(a, tag)}/>" if text is None else f"<{tag}{fmt(a, tag)}>{escape(text)}</{tag}>")

    def raw(self, s):
        self.parts.append(s)

    def text(self):
        return "\n".join(self.parts) + "\n"


def n(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")


def fmt(attrs, tag):
    out = []
    for k, v in attrs.items():
        if v is None:
            continue
        k = k.rstrip("_")
        if tag in INT_GEOMETRY and k in ("x", "y", "width", "height"):
            v = int(round(float(v)))
        elif isinstance(v, float):
            v = n(v)
        out.append(f" {k}={quoteattr(str(v))}")
    return "".join(out)


def full_part(x, name):
    x.open("PartDraw", name=name, x=0, y=0, width=SIZE, height=SIZE)


def rect(x, r, color, thickness):
    x.open("Rectangle", x=n(r[0]), y=n(r[1]), width=n(r[2]), height=n(r[3]))
    x.leaf("Stroke", color=color, thickness=n(thickness))
    x.close("Rectangle")


def circle(x, cx, cy, r, fill=None, line=None, width=3.0):
    x.open("Ellipse", x=n(cx - r), y=n(cy - r), width=n(2 * r), height=n(2 * r))
    if line:
        x.leaf("Stroke", color=line, thickness=n(width))
    if fill:
        x.leaf("Fill", color=fill)
    x.close("Ellipse")


def condition(x, prefix, selector, count, body):
    x.open("Condition")
    x.open("Expressions")
    for k in range(count):
        x.leaf("Expression", f"{selector} == {k}", name=f"{prefix}{k}")
    x.close("Expressions")
    for k in range(count):
        x.open("Compare", expression=f"{prefix}{k}")
        body(k)
        x.close("Compare")
    x.close("Condition")


def rotated_variants(x, prefix, body):
    """Pick the grid variant for this hour and rotate it by 90 degrees every 4 hours."""
    x.open("Group", name=f"{prefix}_rot", x=0, y=0, width=SIZE, height=SIZE, pivotX="0.5", pivotY="0.5")
    x.leaf("Transform", target="angle", value="floor([HOUR_0_11] / 4) * 90")
    condition(x, prefix, f"([HOUR_0_11] % {VARIANTS})", VARIANTS, body)
    x.close("Group")


# ----------------------------------------------------------------------------- scene layers
def hatch_layer(x, v):
    for k, (cell, col, direction, lines) in enumerate(VARIANT_CACHE[v]):
        nl = max(len(lines), 1)
        slot = slot_expr(v, k)
        for j, (s0, s1) in enumerate(lines):
            _t, dur = line_window(0, j, nl)
            t0 = f"({slot} * {CELL_SECONDS} + {dur * j:.1f})"
            length = math.hypot(s1[0] - s0[0], s1[1] - s0[1])
            w, h = int(math.ceil(length)) + 1, 6
            name = f"v{v}c{k}l{j}"
            # Group: placed at the line start and rotated to the line direction (pivot = start).
            x.open("Group", name=name, x=round(s0[0]), y=round(s0[1]) - h // 2, width=w, height=h,
                   pivotX="0", pivotY="0.5", angle=n(direction))
            # Part: a horizontal line that grows along its own axis from the start point.
            x.open("PartDraw", name=name + "p", x=0, y=0, width=w, height=h, pivotX="0", pivotY="0.5")
            x.leaf("Transform", target="scaleX", value=f"clamp(({T_EXPR} - {t0}) / {dur:.2f}, 0, 1)")
            x.open("Line", startX=0, startY=n(h / 2), endX=n(length), endY=n(h / 2))
            x.leaf("Stroke", color=PAL[col], thickness=n(HATCH_W), cap="BUTT")
            x.close("Line")
            x.close("PartDraw")
            x.close("Group")
    # grid on top of the hatching, plus a white frame around the cell being drawn
    full_part(x, f"v{v}_grid")
    for cell, *_ in VARIANT_CACHE[v]:
        rect(x, cell, GRID, 4)
    x.close("PartDraw")
    for k, (cell, *_rest) in enumerate(VARIANT_CACHE[v]):
        x.open("PartDraw", name=f"v{v}_active{k}", x=0, y=0, width=SIZE, height=SIZE, alpha=0)
        x.leaf("Transform", target="alpha",
               value=f"(floor({T_EXPR} / {CELL_SECONDS}) == {slot_expr(v, k)}) ? 255 : 0")
        rect(x, (cell[0] + 3, cell[1] + 3, cell[2] - 6, cell[3] - 6), WHITE, 2)
        x.close("PartDraw")


def grid_only(x, v, color, thickness):
    full_part(x, f"aod_v{v}_grid")
    for cell, *_ in VARIANT_CACHE[v]:
        rect(x, cell, color, thickness)
    x.close("PartDraw")


def seconds_ticks(x):
    full_part(x, "ticks_dim")
    for i in range(60):
        a = math.radians(i * 6)
        r1 = TICK_R1 - (4 if i % 5 == 0 else 0)
        x.open("Line", startX=n(C + r1 * math.sin(a)), startY=n(C - r1 * math.cos(a)),
               endX=n(C + TICK_R2 * math.sin(a)), endY=n(C - TICK_R2 * math.cos(a)))
        x.leaf("Stroke", color="#1E1E1E", thickness="2.5", cap="ROUND")
        x.close("Line")
    x.close("PartDraw")
    for i in range(60):
        a = math.radians(i * 6)
        r1 = TICK_R1 - (4 if i % 5 == 0 else 0)
        x.open("PartDraw", name=f"tick{i}", x=0, y=0, width=SIZE, height=SIZE, alpha=0)
        x.leaf("Transform", target="alpha", value=f"[SECOND] > {i - 0.5} ? 255 : 0")
        x.open("Line", startX=n(C + r1 * math.sin(a)), startY=n(C - r1 * math.cos(a)),
               endX=n(C + TICK_R2 * math.sin(a)), endY=n(C - TICK_R2 * math.cos(a)))
        x.leaf("Stroke", color="#9A9A9A", thickness="2.5", cap="ROUND")
        x.close("Line")
        x.close("PartDraw")
    # the current second, in the accent colour
    x.open("Group", name="tick_now", x=0, y=0, width=SIZE, height=SIZE, pivotX="0.5", pivotY="0.5")
    x.leaf("Transform", target="angle", value="[SECOND] * 6")
    full_part(x, "tick_now_draw")
    x.open("Line", startX=n(C), startY=n(C - TICK_R1 + 6), endX=n(C), endY=n(C - TICK_R2 - 2))
    x.leaf("Stroke", color=PAL[0], thickness="4", cap="ROUND")
    x.close("Line")
    x.close("PartDraw")
    x.close("Group")


def text(x, name, cx, cy, w, h, size, color, template, params, weight="NORMAL"):
    x.open("PartText", name=name, x=cx - w / 2, y=cy - h / 2, width=w, height=h)
    x.open("Text", align="CENTER")
    x.open("Font", family="SYNC_TO_DEVICE", size=size, color=color, weight=weight)
    x.open("Template")
    x.raw(escape(template))
    for p in params:
        x.leaf("Parameter", expression=p)
    x.close("Template")
    x.close("Font")
    x.close("Text")
    x.close("PartText")


def time_text(x, name, cy, color, size):
    def body(src, suffix):
        text(x, f"{name}_{suffix}", C, cy, SIGN_W, 40, size, color, "%s:%s", [src, "[MINUTE_Z]"], weight="BOLD")

    x.open("Condition")
    x.open("Expressions")
    x.leaf("Expression", "[IS_24_HOUR_MODE] == 1", name="is24")
    x.close("Expressions")
    x.open("Compare", expression="is24")
    body("[HOUR_0_23_Z]", "24h")
    x.close("Compare")
    x.open("Default")
    body("[HOUR_1_12]", "12h")
    x.close("Default")
    x.close("Condition")


def sign(x, fill, line, ink, sub_ink, prefix=""):
    x.open("PartDraw", name=f"{prefix}sign", x=C - SIGN_W / 2, y=C - SIGN_H / 2, width=SIGN_W, height=SIGN_H)
    x.open("Rectangle", x=0, y=0, width=SIGN_W, height=SIGN_H)
    x.leaf("Stroke", color=line, thickness="4")
    if fill:
        x.leaf("Fill", color=fill)
    x.close("Rectangle")
    x.close("PartDraw")
    time_text(x, f"{prefix}time", C - 14, ink, 36)
    text(x, f"{prefix}date", C, C + 14, SIGN_W, 18, 13, sub_ink, "%s %s · %s%%",
         ["[DAY_OF_WEEK_S]", "[DAY]", "[BATTERY_PERCENT]"], weight="SEMI_BOLD")
    text(x, f"{prefix}health", C, C + 30, SIGN_W, 18, 12, sub_ink, "%s bpm · %s steps",
         ["[HEART_RATE]", "[STEP_COUNT]"])


def shortcut_slots(x):
    for slot, hr in enumerate(SHORTCUT_HOURS):
        a = math.radians(hr * 30)
        cx, cy = C + SHORTCUT_R * math.sin(a), C - SHORTCUT_R * math.cos(a)
        r = 21
        x.open("ComplicationSlot", slotId=slot, name=f"shortcut_{slot}", x=cx - r, y=cy - r, width=2 * r, height=2 * r,
               supportedTypes="SMALL_IMAGE MONOCHROMATIC_IMAGE EMPTY", isCustomizable="TRUE",
               displayName="Left button" if slot == 0 else "Right button")
        x.leaf("DefaultProviderPolicy", defaultSystemProvider="APP_SHORTCUT", defaultSystemProviderType="SMALL_IMAGE")
        x.leaf("BoundingOval", x=0, y=0, width=2 * r, height=2 * r)
        for ctype in ("SMALL_IMAGE", "MONOCHROMATIC_IMAGE"):
            x.open("Complication", type=ctype)
            x.open("PartDraw", name=f"sc{slot}_{ctype}_bg", x=0, y=0, width=2 * r, height=2 * r)
            circle(x, r, r, r - 1.5, fill="#000000", line=WHITE, width=3)
            x.close("PartDraw")
            x.open("PartImage", name=f"sc{slot}_{ctype}_icon", x=r - 13, y=r - 13, width=26, height=26)
            x.leaf("Image", resource=f"[COMPLICATION.{ctype}]")
            x.close("PartImage")
            x.close("Complication")
        x.open("Complication", type="EMPTY")
        x.open("PartDraw", name=f"sc{slot}_empty", x=0, y=0, width=2 * r, height=2 * r)
        circle(x, r, r, r - 1.5, fill="#000000", line=WHITE, width=3)
        for (ax, ay, bx, by) in ((r - 7, r, r + 7, r), (r, r - 7, r, r + 7)):
            x.open("Line", startX=ax, startY=ay, endX=bx, endY=by)
            x.leaf("Stroke", color=WHITE, thickness="3", cap="ROUND")
            x.close("Line")
        x.close("PartDraw")
        x.close("Complication")
        x.leaf("Variant", mode="AMBIENT", target="alpha", value="0")
        x.close("ComplicationSlot")


def build_xml():
    x = X()
    x.raw('<?xml version="1.0" encoding="utf-8"?>')
    x.raw("<!-- GENERATED by tools/generate.py - edit the generator, not this file. -->")
    x.open("WatchFace", width=SIZE, height=SIZE, clipShape="CIRCLE")
    x.leaf("Metadata", key="CLOCK_TYPE", value="DIGITAL")
    x.leaf("Metadata", key="PREVIEW_TIME", value="10:38:20")
    x.open("UserConfigurations")
    x.open("ColorConfiguration", id="palette", displayName="Palette", defaultValue=PALETTES[0][0])
    for pid, name, cols in PALETTES:
        x.leaf("ColorOption", id=pid, displayName=name, colors=" ".join(cols))
    x.close("ColorConfiguration")
    x.close("UserConfigurations")
    x.open("Scene", backgroundColor="#FF000000")

    x.open("Group", name="active", x=0, y=0, width=SIZE, height=SIZE)
    x.leaf("Variant", mode="AMBIENT", target="alpha", value="0")
    rotated_variants(x, "v", lambda v: hatch_layer(x, v))
    seconds_ticks(x)
    sign(x, PAL[3], "#000000", "#111111", "#3A3A3A")
    x.close("Group")

    x.open("Group", name="ambient", x=0, y=0, width=SIZE, height=SIZE, alpha=0)
    x.leaf("Variant", mode="AMBIENT", target="alpha", value="255")
    rotated_variants(x, "a", lambda v: grid_only(x, v, "#2A2A2A", 2))
    sign(x, "#000000", "#6A6A6A", "#D6D6D6", "#8A8A8A", prefix="aod_")
    x.close("Group")

    shortcut_slots(x)
    x.close("Scene")
    x.close("WatchFace")
    return x.text()


# ----------------------------------------------------------------------------- SVG preview
def svg_at(h, m, s, palette=0, ambient=False):
    cols = PALETTES[palette][2]
    v, ri = h % VARIANTS, (h % 12) // VARIANTS
    rot = ri * 90
    t = m * 60 + s
    o = [f'<g transform="rotate({rot} {C} {C})">']
    if ambient:
        for cell, *_ in VARIANT_CACHE[v]:
            o.append(f'<rect x="{cell[0]:.1f}" y="{cell[1]:.1f}" width="{cell[2]:.1f}" height="{cell[3]:.1f}" fill="none" stroke="#2A2A2A" stroke-width="2"/>')
        o.append("</g>")
    else:
        for k, (cell, col, _d, lines) in enumerate(VARIANT_CACHE[v]):
            nl = max(len(lines), 1)
            for j, (s0, s1) in enumerate(lines):
                t0, dur = line_window(build_slot(v, k, ri), j, nl)
                f = min(max((t - t0) / dur, 0), 1)
                if f > 0:
                    o.append(f'<line x1="{s0[0]:.1f}" y1="{s0[1]:.1f}" x2="{s0[0] + (s1[0] - s0[0]) * f:.1f}" y2="{s0[1] + (s1[1] - s0[1]) * f:.1f}" stroke="{cols[col]}" stroke-width="{HATCH_W}"/>')
        for cell, *_ in VARIANT_CACHE[v]:
            o.append(f'<rect x="{cell[0]:.1f}" y="{cell[1]:.1f}" width="{cell[2]:.1f}" height="{cell[3]:.1f}" fill="none" stroke="{GRID}" stroke-width="4"/>')
        k = next(i for i in range(CELLS) if build_slot(v, i, ri) == int(t // CELL_SECONDS))
        cell = VARIANT_CACHE[v][k][0]
        o.append(f'<rect x="{cell[0] + 3:.1f}" y="{cell[1] + 3:.1f}" width="{cell[2] - 6:.1f}" height="{cell[3] - 6:.1f}" fill="none" stroke="{WHITE}" stroke-width="2"/>')
        o.append("</g>")
        for i in range(60):
            a = math.radians(i * 6)
            r1 = TICK_R1 - (4 if i % 5 == 0 else 0)
            c = cols[0] if i == int(s) else ("#9A9A9A" if i <= s else "#1E1E1E")
            o.append(f'<line x1="{C + r1 * math.sin(a):.1f}" y1="{C - r1 * math.cos(a):.1f}" x2="{C + TICK_R2 * math.sin(a):.1f}" y2="{C - TICK_R2 * math.cos(a):.1f}" stroke="{c}" stroke-width="{4 if i == int(s) else 2.5}" stroke-linecap="round"/>')
    fill, line, ink, sub = ("#000", "#6A6A6A", "#D6D6D6", "#8A8A8A") if ambient else (cols[3], "#000", "#111", "#3A3A3A")
    o.append(f'<rect x="{C - SIGN_W / 2}" y="{C - SIGN_H / 2}" width="{SIGN_W}" height="{SIGN_H}" fill="{fill}" stroke="{line}" stroke-width="4"/>')
    font = 'font-family="Roboto,Helvetica,Arial,sans-serif" text-anchor="middle"'
    o.append(f'<text x="{C}" y="{C - 14 + 13}" font-size="36" font-weight="800" fill="{ink}" {font}>{h % 12 or 12}:{m:02d}</text>')
    o.append(f'<text x="{C}" y="{C + 14 + 5}" font-size="13" font-weight="600" fill="{sub}" {font}>Sun 22 · 72%</text>')
    if not ambient:
        o.append(f'<text x="{C}" y="{C + 30 + 4}" font-size="12" fill="{sub}" {font}>64 bpm · 8412 steps</text>')
        for hr, icon in zip(SHORTCUT_HOURS, ("spotify", "wallet")):
            a = math.radians(hr * 30)
            px, py = C + SHORTCUT_R * math.sin(a), C - SHORTCUT_R * math.cos(a)
            o.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="19.5" fill="#000" stroke="{WHITE}" stroke-width="3"/>')
            if icon == "spotify":
                o.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="12" fill="#1DB954"/>')
                for w, dy in ((14, -4), (11, 1), (8, 5)):
                    o.append(f'<path d="M{px - w / 2:.1f} {py + dy:.1f} q{w / 2:.1f} -3 {w:.1f} 0" fill="none" stroke="#000" stroke-width="2" stroke-linecap="round"/>')
            else:
                o.append(f'<rect x="{px - 11:.1f}" y="{py - 8:.1f}" width="22" height="16" rx="3" fill="#fff"/>')
                for i, c in enumerate(("#4285F4", "#34A853", "#FBBC04")):
                    o.append(f'<rect x="{px - 9:.1f}" y="{py - 6 + i * 4:.1f}" width="18" height="3" rx="1" fill="{c}"/>')
    body = "\n".join(o)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SIZE} {SIZE}" width="{SIZE}" height="{SIZE}">'
            f'<defs><clipPath id="face"><circle cx="{C}" cy="{C}" r="{C}"/></clipPath></defs>'
            f'<g clip-path="url(#face)"><rect width="{SIZE}" height="{SIZE}" fill="#000"/>{body}</g></svg>')


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser()
    ap.add_argument("--svg", nargs="*", metavar="HH:MM:SS[.f][@palette][~aod]")
    ap.add_argument("--out-dir", default=os.path.join(root, "docs", "build"))
    args = ap.parse_args()
    out = os.path.join(root, "app", "src", "main", "res", "raw", "watchface.xml")
    xml = build_xml()
    with open(out, "w", encoding="utf-8") as f:
        f.write(xml)
    print(f"wrote {os.path.relpath(out, root)} ({len(xml) / 1024:.0f} KiB)")
    for spec in args.svg or []:
        amb = spec.endswith("~aod")
        spec_ = spec[:-4] if amb else spec
        t, _, pal = spec_.partition("@")
        hh, mm, ss = t.split(":")
        os.makedirs(args.out_dir, exist_ok=True)
        name = f"preview-{t.replace(':', '-')}{'-' + pal if pal else ''}{'-aod' if amb else ''}.svg"
        with open(os.path.join(args.out_dir, name), "w") as f:
            f.write(svg_at(int(hh), int(mm), float(ss), int(pal or 0), amb))


if __name__ == "__main__":
    main()
