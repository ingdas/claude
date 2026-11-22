#!/usr/bin/env python3
"""Generate the Metro Rush watch face (Watch Face Format v1) and matching previews.

Everything visual comes from the geometry model in this file, so the watch face XML
and the preview images can never drift apart.

    python3 tools/generate.py                 # writes app/src/main/res/raw/watchface.xml
    python3 tools/generate.py --svg 10:31:20  # also writes docs/preview-10-31-20.svg

Concept ("Rush of Everything"):
  * The bezel is a circle line with 12 hour stations; the current hour station is ringed.
    A coloured track fills the ring as the minutes pass; a white train laps it once a
    minute (seconds).
  * Inside, a seeded metro network grows through the hour (25% of its track at :00,
    almost complete at :59) and is regenerated - a brand-new map - every minute. During
    the last 3 seconds of each minute it cross-fades into the next map.
  * Two bold "express" lines act as hands: white to the hour, accent colour to the
    minute, routed like a transit map (straight, then 45 degrees).
  * Trains shuttle on every line. Time sits on a station sign in the middle.
  * Spotify / Google Wallet live in the 8 and 4 o'clock ring stations (user-configurable
    app-shortcut complication slots).
"""
from __future__ import annotations

import argparse
import math
import os
from xml.sax.saxutils import escape, quoteattr

# ----------------------------------------------------------------------------- constants
SIZE = 450
C = SIZE / 2
RING_R = 190
HOUR_LINE_R = 118
MINUTE_LINE_R = 178
NET_R = 160                      # network stays inside this radius
SIGN_W, SIGN_H = 124, 46         # station sign holding the time
SIGN_CY = C + 2
GHOST = "#1A1A1A"
TRACK = "#262626"
WHITE = "#F2F2F2"
LABEL = "#A8A8A8"
SHORTCUT_HOURS = (8, 4)          # ring stations that double as app shortcuts
MORPH_SECONDS = 3

PALETTES = [  # id, display name, 5 colours: accent, line 2, line 3, sign/line 4, unused
    ("primary", "Primary", ["#D8352A", "#1F4FBF", "#F2C230", "#E9E4D8", "#F2F2F2"]),
    ("mono_red", "Mono + Red", ["#D8352A", "#5A5A5A", "#9A9A9A", "#D0D0D0", "#F2F2F2"]),
    ("neon", "Neon Night", ["#E0187A", "#0AA5C2", "#B5F23D", "#E6DDFF", "#F2F2F2"]),
]
PAL = [f"[CONFIGURATION.palette.{i}]" for i in range(5)]  # colour references in the XML

NET_STARTS = [  # (start point, initial heading in 45-degree steps, palette index)
    ((C - SIGN_W / 2, SIGN_CY - 8), 6, 0),
    ((C + SIGN_W / 2, SIGN_CY + 8), 2, 1),
    ((C - 30, SIGN_CY + SIGN_H / 2), 5, 2),
    ((C + 30, SIGN_CY - SIGN_H / 2), 1, 3),
]
NET_STEPS = 7
NET_ALPHA = 150                  # 0-255, network sits behind the express lines
NET_SPEED = 36.0                 # px per second
EXPRESS_SPEED = 26.0


# ----------------------------------------------------------------------------- geometry
def prng(seed: int):
    s = (seed * 9301 + 49297) % 2147483647 or 1

    def nxt() -> float:
        nonlocal s
        s = (s * 16807) % 2147483647
        return s / 2147483647

    return nxt


def on_ring(r: float, deg: float):
    a = math.radians(deg)
    return (C + r * math.sin(a), C - r * math.cos(a))


def in_sign_zone(p) -> bool:
    return abs(p[0] - C) < SIGN_W / 2 + 6 and abs(p[1] - SIGN_CY) < SIGN_H / 2 + 6


def crosses_sign(a, b) -> bool:
    return any(in_sign_zone((a[0] + (b[0] - a[0]) * t / 8, a[1] + (b[1] - a[1]) * t / 8)) for t in range(1, 8))


def remainder(full, vis):
    """The not-yet-built part of a line (drawn as faint 'planned' track)."""
    built = sum(seg_lengths(vis))
    out, acc = [], 0.0
    for a, b in zip(full, full[1:]):
        ln = math.hypot(b[0] - a[0], b[1] - a[1])
        if acc + ln > built + 0.5:
            t = max(0.0, (built - acc) / ln)
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
        acc += ln
    return dedupe(out + [full[-1]]) if out else []


def gen_line(seed: int, start, heading: int):
    """Seeded wandering octilinear polyline with a fixed number of steps."""
    rnd = prng(seed)
    p, d = start, heading
    pts = [p]
    for _ in range(NET_STEPS):
        for _try in range(10):
            nd = (d + [0, 0, 1, -1, 1, -1][int(rnd() * 6)] + 8) % 8
            ln = 36 + int(rnd() * 4) * 12
            q = (p[0] + ln * math.sin(math.radians(nd * 45)), p[1] - ln * math.cos(math.radians(nd * 45)))
            if math.hypot(q[0] - C, q[1] - C) < NET_R and not in_sign_zone(q) and not crosses_sign(p, q):
                p, d = q, nd
                pts.append(p)
                break
    return pts


def route(a, b):
    """Transit-map route a->b: straight along the major axis, then a 45-degree diagonal."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    d = min(abs(dx), abs(dy))
    if abs(dx) > abs(dy):
        mid = (b[0] - math.copysign(d, dx), a[1])
    else:
        mid = (a[0], b[1] - math.copysign(d, dy))
    return dedupe([a, mid, b])


def dedupe(pts):
    out = [pts[0]]
    for p in pts[1:]:
        if math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > 0.5:
            out.append(p)
    return out


def seg_lengths(pts):
    return [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])]


def cut(pts, length):
    out = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        ln = math.hypot(b[0] - a[0], b[1] - a[1])
        if length >= ln:
            out.append(b)
            length -= ln
        else:
            t = length / ln if ln else 0
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
            break
    return dedupe(out)


def growth(minute: int) -> float:
    return 0.25 + 0.75 * minute / 60


def network(minute: int):
    """[(palette index, full polyline, visible polyline)] for a given minute of the hour."""
    out = []
    for i, (start, heading, col) in enumerate(NET_STARTS):
        full = dedupe(gen_line(1000 * i + 7919 * minute + 17, start, heading))
        vis = cut(full, sum(seg_lengths(full)) * growth(minute))
        out.append((col, full, vis))
    return out


def minute_line(minute: int):
    return route((C, SIGN_CY), on_ring(MINUTE_LINE_R, minute * 6))


def hour_line(idx: int):
    """idx = hour(0-11) * 5 + minute // 12, i.e. the hour hand in 6-degree steps."""
    return route((C, SIGN_CY), on_ring(HOUR_LINE_R, idx * 6))


# ----------------------------------------------------------------------------- trains
class Train:
    """A train ping-ponging along a polyline. Position is a pure function of seconds."""

    def __init__(self, pts, speed, phase, margin=14.0):
        self.pts = pts
        self.lens = seg_lengths(pts)
        self.total = sum(self.lens)
        self.margin = min(margin, self.total / 2)
        self.span = max(self.total - 2 * self.margin, 0.001)
        self.speed, self.phase = speed, phase

    # distance along the line at time t (seconds within the minute)
    def dist(self, t):
        u = (t * self.speed + self.phase) % (2 * self.span)
        return self.span - abs(self.span - u) + self.margin

    def pos(self, t):
        d = self.dist(t)
        x, y = self.pts[0]
        acc = 0.0
        ang = 0.0
        for (a, b), ln in zip(zip(self.pts, self.pts[1:]), self.lens):
            k = min(max(d - acc, 0), ln)
            x += (b[0] - a[0]) / ln * k
            y += (b[1] - a[1]) / ln * k
            if d > acc:
                ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
            acc += ln
        return x, y, ang

    # the same maths as WFF expressions
    def wff_dist(self):
        s = f"{self.span:.1f}"
        return (f"({s}-abs({s}-(([SECOND_MILLISECOND]*{self.speed:g}+{self.phase:g})"
                f"%{2 * self.span:.1f}))+{self.margin:.1f})")

    def wff_xy(self, cx_off, cy_off):
        d = self.wff_dist()
        xs, ys, acc = [f"{self.pts[0][0] - cx_off:.1f}"], [f"{self.pts[0][1] - cy_off:.1f}"], 0.0
        for (a, b), ln in zip(zip(self.pts, self.pts[1:]), self.lens):
            ux, uy = (b[0] - a[0]) / ln, (b[1] - a[1]) / ln
            term = f"clamp({d}-{acc:.1f},0,{ln:.1f})"
            if abs(ux) > 1e-6:
                xs.append(term if abs(ux - 1) < 1e-6 else f"-{term}" if abs(ux + 1) < 1e-6 else f"{ux:.3f}*{term}")
            if abs(uy) > 1e-6:
                ys.append(term if abs(uy - 1) < 1e-6 else f"-{term}" if abs(uy + 1) < 1e-6 else f"{uy:.3f}*{term}")
            acc += ln
        return "+".join(xs).replace("+-", "-"), "+".join(ys).replace("+-", "-")

    def wff_angle(self):
        d = self.wff_dist()
        angs, acc, starts = [], 0.0, []
        for (a, b), ln in zip(zip(self.pts, self.pts[1:]), self.lens):
            angs.append(round(math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))))
            starts.append(acc)
            acc += ln
        expr = f"{angs[0]:g}"
        for st, an in zip(starts[1:], angs[1:]):  # only '>' is used: it is the safest operator
            expr = f"({d}>{st:.1f}?{an:g}:{expr})"
        return expr


def net_trains(minute):
    return [(col, Train(vis, NET_SPEED, i * 83.0)) for i, (col, _full, vis) in enumerate(network(minute))]


# ----------------------------------------------------------------------------- XML helpers
class X:
    def __init__(self):
        self.parts: list[str] = []
        self.depth = 0

    def open(self, tag, **attrs):
        self.parts.append(f"<{tag}{fmt(attrs, tag)}>")
        self.depth += 1

    def close(self, tag):
        self.depth -= 1
        self.parts.append(f"</{tag}>")

    def leaf(self, tag, text=None, **attrs):
        pad = ""
        if text is None:
            self.parts.append(f"{pad}<{tag}{fmt(attrs, tag)}/>")
        else:
            self.parts.append(f"{pad}<{tag}{fmt(attrs, tag)}>{escape(text)}</{tag}>")

    def raw(self, s):
        self.parts.append(s)

    def text(self):
        return "\n".join(self.parts) + "\n"


# In the WFF schema these elements take integer x/y/width/height ("dimensionType");
# shapes inside a PartDraw take floats.
INT_GEOMETRY = {"Group", "PartDraw", "PartText", "PartImage", "ComplicationSlot",
                "BoundingOval", "BoundingBox", "AnalogClock", "DigitalClock"}


def fmt(attrs, tag=""):
    out = []
    for k, v in attrs.items():
        if tag in INT_GEOMETRY and k in ("x", "y", "width", "height") and v is not None:
            v = int(round(float(v)))
        if v is None:
            continue
        k = k.rstrip("_")
        if isinstance(v, float):
            v = f"{v:.2f}".rstrip("0").rstrip(".")
        out.append(f" {k}={quoteattr(str(v))}")
    return "".join(out)


def n(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")


def stroke(x: X, color, thickness, cap="ROUND"):
    x.leaf("Stroke", color=color, thickness=n(thickness), cap=cap)


def draw_polyline(x: X, pts, color, thickness):
    for a, b in zip(pts, pts[1:]):
        x.open("Line", startX=n(a[0]), startY=n(a[1]), endX=n(b[0]), endY=n(b[1]))
        stroke(x, color, thickness)
        x.close("Line")


def draw_circle(x: X, cx, cy, r, fill=None, line=None, width=3.0):
    x.open("Ellipse", x=n(cx - r), y=n(cy - r), width=n(2 * r), height=n(2 * r))
    if line:
        stroke(x, line, width, cap="BUTT")
    if fill:
        x.leaf("Fill", color=fill)
    x.close("Ellipse")


def full_part(x: X, name):
    x.open("PartDraw", name=name, x=0, y=0, width=SIZE, height=SIZE)


def station(x: X, p, big=False):
    if big:
        draw_circle(x, p[0], p[1], 13, line=WHITE, width=2)
        draw_circle(x, p[0], p[1], 10, fill=WHITE, line="#000000", width=3)
    else:
        draw_circle(x, p[0], p[1], 7, fill="#000000", line=WHITE, width=3)


def train_group(x: X, name, tr: Train, color):
    w, h = 26, 14
    gx, gy = tr.wff_xy(w / 2, h / 2)
    x.open("Group", name=name, x=0, y=0, width=w, height=h, pivotX="0.5", pivotY="0.5")
    x.leaf("Transform", target="x", value=gx)
    x.leaf("Transform", target="y", value=gy)
    x.leaf("Transform", target="angle", value=tr.wff_angle())
    x.open("PartDraw", name=name + "_body", x=0, y=0, width=w, height=h)
    x.open("RoundRectangle", x=0, y=0, width=w, height=h, cornerRadiusX=3, cornerRadiusY=3)
    stroke(x, "#000000", 2, cap="BUTT")
    x.leaf("Fill", color=color)
    x.close("RoundRectangle")
    x.open("RoundRectangle", x=w - 10, y=3, width=5, height=h - 6, cornerRadiusX=1, cornerRadiusY=1)
    x.leaf("Fill", color="#B3FFFFFF")
    x.close("RoundRectangle")
    x.close("PartDraw")
    x.close("Group")


def condition(x: X, prefix, selector, count, body):
    """Condition with one Compare per value of `selector` (0..count-1)."""
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


MINUTE_SEL = "[MINUTE]"
HOUR_SEL = "([HOUR_0_11] * 5 + floor([MINUTE] / 12))"
RAMP = f"clamp(([SECOND_MILLISECOND] - {60 - MORPH_SECONDS}) / {MORPH_SECONDS}, 0, 1)"


# ----------------------------------------------------------------------------- scene layers
def layer_minute_static(x: X, m: int, with_trains: bool, tag: str):
    """Everything that changes once per minute: ring minute track, network, minute line."""
    full_part(x, f"{tag}ring_track_{m}")
    if m > 0:
        x.open("Arc", centerX=C, centerY=C, width=2 * RING_R, height=2 * RING_R, startAngle=0, endAngle=m * 6)
        stroke(x, PAL[0], 9)
        x.close("Arc")
    else:
        draw_circle(x, C, C - RING_R, 4.5, fill=PAL[0])
    x.close("PartDraw")

    net = network(m)
    if with_trains:
        full_part(x, f"{tag}net_ghost_{m}")
        for _col, full, vis in net:
            rest = remainder(full, vis)
            if len(rest) > 1:
                draw_polyline(x, rest, GHOST, 8)
        x.close("PartDraw")

    x.open("Group", name=f"{tag}net_{m}", x=0, y=0, width=SIZE, height=SIZE, alpha=NET_ALPHA)
    full_part(x, f"{tag}net_lines_{m}")
    for col, _full, vis in net:
        draw_polyline(x, vis, PAL[col], 8)
    if with_trains:
        for _col, _full, vis in net:
            for i, p in enumerate(vis[1:-1]):
                if i % 2 == 1:
                    station(x, p)
    x.close("PartDraw")
    if with_trains:
        for i, (col, tr) in enumerate(net_trains(m)):
            train_group(x, f"{tag}net_train_{m}_{i}", tr, PAL[col])
    x.close("Group")

    ml = minute_line(m)
    full_part(x, f"{tag}minute_line_{m}")
    draw_polyline(x, ml, PAL[0], 7)
    station(x, ml[-1])
    x.close("PartDraw")
    if with_trains:
        train_group(x, f"{tag}minute_train_{m}", Train(ml, EXPRESS_SPEED, 20.0, margin=40), PAL[0])


def layer_hour(x: X, idx: int):
    hl = hour_line(idx)
    full_part(x, f"hour_line_{idx}")
    draw_polyline(x, hl, WHITE, 8)
    station(x, hl[-1], big=True)
    x.close("PartDraw")
    train_group(x, f"hour_train_{idx}", Train(hl, EXPRESS_SPEED * 0.7, 0.0, margin=40), WHITE)


def ring_stations(x: X):
    full_part(x, "ring_track")
    draw_circle(x, C, C, RING_R, line=TRACK, width=9)
    x.close("PartDraw")


def ring_station_dots(x: X):
    full_part(x, "ring_stations")
    for hr in range(12):
        if hr in SHORTCUT_HOURS:
            continue
        station(x, on_ring(RING_R, hr * 30))
    x.close("PartDraw")
    # current-hour marker: a ring around the station, rotated to the hour
    x.open("Group", name="hour_marker", x=0, y=0, width=SIZE, height=SIZE, pivotX="0.5", pivotY="0.5")
    x.leaf("Transform", target="angle", value="[HOUR_0_11] * 30")
    full_part(x, "hour_marker_draw")
    draw_circle(x, C, C - RING_R, 15, line=WHITE, width=2.5)
    draw_circle(x, C, C - RING_R, 9, fill=WHITE, line="#000000", width=3)
    x.close("PartDraw")
    x.close("Group")


def seconds_train(x: X):
    x.open("Group", name="seconds_train", x=0, y=0, width=SIZE, height=SIZE, pivotX="0.5", pivotY="0.5")
    x.leaf("Transform", target="angle", value="[SECOND_MILLISECOND] * 6")
    full_part(x, "seconds_train_draw")
    x.open("RoundRectangle", x=C - 15, y=C - RING_R - 7.5, width=30, height=15, cornerRadiusX=4, cornerRadiusY=4)
    stroke(x, "#000000", 2, cap="BUTT")
    x.leaf("Fill", color="#FFFFFF")
    x.close("RoundRectangle")
    x.close("PartDraw")
    x.close("Group")


def text(x: X, name, cx, cy, w, h, size, color, template, params, weight="NORMAL"):
    x.open("PartText", name=name, x=n(cx - w / 2), y=n(cy - h / 2), width=w, height=h)
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


def pill(x: X, name, cx, cy, w, h, fill="#000000", line=None):
    x.open("PartDraw", name=name, x=n(cx - w / 2), y=n(cy - h / 2), width=w, height=h)
    x.open("RoundRectangle", x=0, y=0, width=w, height=h, cornerRadiusX=n(h / 2 if not line else 8), cornerRadiusY=n(h / 2 if not line else 8))
    if line:
        stroke(x, line, 2, cap="BUTT")
    if fill:
        x.leaf("Fill", color=fill)
    x.close("RoundRectangle")
    x.close("PartDraw")


def time_text(x: X, name, color, size=34):
    def body(hour_src):
        text(x, f"{name}_{'24h' if 'HOUR_0_23' in hour_src else '12h'}", C, SIGN_CY + 1, SIGN_W, SIGN_H, size, color, "%s:%s", [hour_src, "[MINUTE_Z]"], weight="BOLD")

    x.open("Condition")
    x.open("Expressions")
    x.leaf("Expression", "[IS_24_HOUR_MODE] == 1", name="is24")
    x.close("Expressions")
    x.open("Compare", expression="is24")
    body("[HOUR_0_23_Z]")
    x.close("Compare")
    x.open("Default")
    body("[HOUR_1_12]")
    x.close("Default")
    x.close("Condition")


def labels(x: X, color=LABEL):
    pill(x, "date_bg", C, SIGN_CY + 46, 86, 22)
    text(x, "date", C, SIGN_CY + 46, 86, 22, 15, color, "%s %s", ["[DAY_OF_WEEK_S]", "[DAY]"], weight="SEMI_BOLD")
    pill(x, "stats_bg", C, 112, 210, 22)
    text(x, "stats", C, 112, 210, 22, 14, color, "%s bpm · %s steps · %s%%", ["[HEART_RATE]", "[STEP_COUNT]", "[BATTERY_PERCENT]"], weight="SEMI_BOLD")


def shortcut_slots(x: X):
    for slot, hr in enumerate(SHORTCUT_HOURS):
        cx, cy = on_ring(RING_R, hr * 30)
        r = 22
        x.open("ComplicationSlot", slotId=slot, name=f"shortcut_{slot}", x=n(cx - r), y=n(cy - r), width=2 * r, height=2 * r,
               supportedTypes="SMALL_IMAGE MONOCHROMATIC_IMAGE EMPTY", isCustomizable="TRUE",
               displayName="Left station" if slot == 0 else "Right station")
        x.leaf("DefaultProviderPolicy", defaultSystemProvider="APP_SHORTCUT", defaultSystemProviderType="SMALL_IMAGE")
        x.leaf("BoundingOval", x=0, y=0, width=2 * r, height=2 * r)
        for ctype, src in (("SMALL_IMAGE", "[COMPLICATION.SMALL_IMAGE]"), ("MONOCHROMATIC_IMAGE", "[COMPLICATION.MONOCHROMATIC_IMAGE]")):
            x.open("Complication", type=ctype)
            x.open("PartDraw", name=f"shortcut_{slot}_{ctype}_bg", x=0, y=0, width=2 * r, height=2 * r)
            draw_circle(x, r, r, r - 1.5, fill="#000000", line=WHITE, width=3)
            x.close("PartDraw")
            x.open("PartImage", name=f"shortcut_{slot}_{ctype}_icon", x=r - 13, y=r - 13, width=26, height=26)
            x.leaf("Image", resource=src)
            x.close("PartImage")
            x.close("Complication")
        x.open("Complication", type="EMPTY")
        x.open("PartDraw", name=f"shortcut_{slot}_empty", x=0, y=0, width=2 * r, height=2 * r)
        draw_circle(x, r, r, r - 1.5, fill="#000000", line=WHITE, width=3)
        x.open("Line", startX=r - 7, startY=r, endX=r + 7, endY=r)
        stroke(x, WHITE, 3)
        x.close("Line")
        x.open("Line", startX=r, startY=r - 7, endX=r, endY=r + 7)
        stroke(x, WHITE, 3)
        x.close("Line")
        x.close("PartDraw")
        x.close("Complication")
        x.leaf("Variant", mode="AMBIENT", target="alpha", value="0")
        x.close("ComplicationSlot")


def ambient_layer(x: X):
    """Always-on display: thin outlines, no animation, few lit pixels."""
    x.open("Group", name="ambient", x=0, y=0, width=SIZE, height=SIZE, alpha=0)
    x.leaf("Variant", mode="AMBIENT", target="alpha", value="255")
    full_part(x, "aod_ring")
    draw_circle(x, C, C, RING_R, line="#303030", width=2)
    x.close("PartDraw")

    def minute_body(m):
        full_part(x, f"aod_minute_{m}")
        if m > 0:
            x.open("Arc", centerX=C, centerY=C, width=2 * RING_R, height=2 * RING_R, startAngle=0, endAngle=m * 6)
            stroke(x, PAL[0], 3)
            x.close("Arc")
        draw_polyline(x, minute_line(m), PAL[0], 3)
        x.close("PartDraw")

    condition(x, "am", MINUTE_SEL, 60, minute_body)

    def hour_body(idx):
        full_part(x, f"aod_hour_{idx}")
        hl = hour_line(idx)
        draw_polyline(x, hl, "#BDBDBD", 3)
        draw_circle(x, hl[-1][0], hl[-1][1], 8, fill="#000000", line="#BDBDBD", width=2)
        x.close("PartDraw")

    condition(x, "ah", HOUR_SEL, 60, hour_body)
    x.open("Group", name="aod_hour_marker", x=0, y=0, width=SIZE, height=SIZE, pivotX="0.5", pivotY="0.5")
    x.leaf("Transform", target="angle", value="[HOUR_0_11] * 30")
    full_part(x, "aod_hour_marker_draw")
    draw_circle(x, C, C - RING_R, 9, fill="#000000", line="#BDBDBD", width=2)
    x.close("PartDraw")
    x.close("Group")
    pill(x, "aod_sign", C, SIGN_CY, SIGN_W, SIGN_H, fill="#000000", line="#7A7A7A")
    time_text(x, "aod_time", "#D6D6D6")
    text(x, "aod_date", C, SIGN_CY + 46, 86, 22, 15, "#8A8A8A", "%s %s", ["[DAY_OF_WEEK_S]", "[DAY]"])
    x.close("Group")


def build_xml() -> str:
    x = X()
    x.raw('<?xml version="1.0" encoding="utf-8"?>')
    x.raw("<!-- GENERATED by tools/generate.py - edit the generator, not this file. -->")
    x.open("WatchFace", width=SIZE, height=SIZE, clipShape="CIRCLE")
    x.leaf("Metadata", key="CLOCK_TYPE", value="DIGITAL")
    x.leaf("Metadata", key="PREVIEW_TIME", value="10:31:20")
    x.open("UserConfigurations")
    x.open("ColorConfiguration", id="palette", displayName="Palette", defaultValue=PALETTES[0][0])
    for pid, name, cols in PALETTES:
        x.leaf("ColorOption", id=pid, displayName=name, colors=" ".join(cols))
    x.close("ColorConfiguration")
    x.close("UserConfigurations")

    x.open("Scene", backgroundColor="#FF000000")
    x.open("Group", name="active", x=0, y=0, width=SIZE, height=SIZE)
    x.leaf("Variant", mode="AMBIENT", target="alpha", value="0")
    ring_stations(x)

    # current minute, fading out during the morph
    x.open("Group", name="minute_now", x=0, y=0, width=SIZE, height=SIZE)
    x.leaf("Transform", target="alpha", value=f"255 - {RAMP} * 255")
    condition(x, "m", MINUTE_SEL, 60, lambda m: layer_minute_static(x, m, True, ""))
    x.close("Group")
    # next minute's map fading in during the last seconds (no trains)
    x.open("Group", name="minute_next", x=0, y=0, width=SIZE, height=SIZE, alpha=0)
    x.leaf("Transform", target="alpha", value=f"{RAMP} * 255")
    condition(x, "n", MINUTE_SEL, 60, lambda m: layer_minute_static(x, (m + 1) % 60, False, "next_"))
    x.close("Group")

    condition(x, "h", HOUR_SEL, 60, lambda i: layer_hour(x, i))
    ring_station_dots(x)
    pill(x, "sign", C, SIGN_CY, SIGN_W, SIGN_H, fill=PAL[3], line="#000000")
    time_text(x, "time", "#111111")
    labels(x)
    seconds_train(x)
    x.close("Group")

    ambient_layer(x)
    shortcut_slots(x)
    x.close("Scene")
    x.close("WatchFace")
    return x.text()


# ----------------------------------------------------------------------------- SVG preview
def svg_at(h: int, m: int, s: float, palette=0, ambient=False) -> str:
    cols = PALETTES[palette][2]
    o = []
    line = lambda pts, c, w: o.append(f'<polyline points="{" ".join(f"{p[0]:.1f},{p[1]:.1f}" for p in pts)}" fill="none" stroke="{c}" stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round"/>')
    circ = lambda p, r, fill, st="none", w=3: o.append(f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="{r}" fill="{fill}" stroke="{st}" stroke-width="{w}"/>')

    def stn(p, big=False):
        if big:
            circ(p, 13, "none", WHITE, 2)
            circ(p, 10, WHITE, "#000", 3)
        else:
            circ(p, 7, "#000", WHITE, 3)

    def arc(deg, c, w):
        if deg <= 0:
            return
        a1 = on_ring(RING_R, 0)
        a2 = on_ring(RING_R, deg)
        o.append(f'<path d="M{a1[0]:.1f} {a1[1]:.1f} A{RING_R} {RING_R} 0 {1 if deg > 180 else 0} 1 {a2[0]:.1f} {a2[1]:.1f}" fill="none" stroke="{c}" stroke-width="{w}" stroke-linecap="round"/>')

    def train(tr, t, c):
        x, y, a = tr.pos(t)
        o.append(f'<g transform="translate({x:.1f} {y:.1f}) rotate({a:.1f})"><rect x="-13" y="-7" width="26" height="14" rx="3" fill="{c}" stroke="#000" stroke-width="2"/><rect x="3" y="-4" width="5" height="8" rx="1" fill="#fff" opacity=".7"/></g>')

    def txt(cx, cy, s_, size, c, weight=600):
        o.append(f'<text x="{cx:.1f}" y="{cy + size * 0.36:.1f}" font-size="{size}" fill="{c}" text-anchor="middle" font-weight="{weight}" font-family="Roboto,Helvetica,Arial,sans-serif">{escape(s_)}</text>')

    hidx = (h % 12) * 5 + m // 12
    if ambient:
        circ((C, C), RING_R, "none", "#303030", 2)
        arc(m * 6, cols[0], 3)
        line(minute_line(m), cols[0], 3)
        hl = hour_line(hidx)
        line(hl, "#BDBDBD", 3)
        circ(hl[-1], 8, "#000", "#BDBDBD", 2)
        circ(on_ring(RING_R, (h % 12) * 30), 9, "#000", "#BDBDBD", 2)
        o.append(f'<rect x="{C - SIGN_W / 2}" y="{SIGN_CY - SIGN_H / 2}" width="{SIGN_W}" height="{SIGN_H}" rx="8" fill="#000" stroke="#7A7A7A" stroke-width="2"/>')
        txt(C, SIGN_CY + 1, f"{h % 12 or 12}:{m:02d}", 34, "#D6D6D6", 800)
        txt(C, SIGN_CY + 46, "Sun 22", 15, "#8A8A8A")
        return wrap(o)

    k = min(max((s - (60 - MORPH_SECONDS)) / MORPH_SECONDS, 0), 1)
    circ((C, C), RING_R, "none", TRACK, 9)

    def minute_layer(mm, alpha, trains):
        o.append(f'<g opacity="{alpha:.3f}">')
        arc(mm * 6, cols[0], 9)
        if mm == 0:
            circ((C, C - RING_R), 4.5, cols[0])
        net = network(mm)
        if trains:
            for _c, full, vis in net:
                rest = remainder(full, vis)
                if len(rest) > 1:
                    line(rest, GHOST, 8)
        o.append(f'<g opacity="{NET_ALPHA / 255:.3f}">')
        for c, _f, vis in net:
            line(vis, cols[c], 8)
        if trains:
            for _c, _f, vis in net:
                for i, p in enumerate(vis[1:-1]):
                    if i % 2 == 1:
                        stn(p)
        if trains:
            for c, tr in net_trains(mm):
                train(tr, s, cols[c])
        o.append("</g>")
        ml = minute_line(mm)
        line(ml, cols[0], 7)
        stn(ml[-1])
        if trains:
            train(Train(ml, EXPRESS_SPEED, 20.0, margin=40), s, cols[0])
        o.append("</g>")

    minute_layer(m, 1 - k, True)
    if k > 0:
        minute_layer((m + 1) % 60, k, False)
    hl = hour_line(hidx)
    line(hl, WHITE, 8)
    stn(hl[-1], big=True)
    train(Train(hl, EXPRESS_SPEED * 0.7, 0.0, margin=40), s, WHITE)
    for hr in range(12):
        if hr not in SHORTCUT_HOURS:
            stn(on_ring(RING_R, hr * 30))
    p = on_ring(RING_R, (h % 12) * 30)
    circ(p, 15, "none", WHITE, 2.5)
    circ(p, 9, WHITE, "#000", 3)
    o.append(f'<rect x="{C - SIGN_W / 2}" y="{SIGN_CY - SIGN_H / 2}" width="{SIGN_W}" height="{SIGN_H}" rx="8" fill="{cols[3]}" stroke="#000" stroke-width="2"/>')
    txt(C, SIGN_CY + 1, f"{h % 12 or 12}:{m:02d}", 34, "#111", 800)
    o.append(f'<rect x="{C - 43}" y="{SIGN_CY + 35}" width="86" height="22" rx="11" fill="#000"/>')
    txt(C, SIGN_CY + 46, "Sun 22", 15, LABEL)
    o.append(f'<rect x="{C - 105}" y="101" width="210" height="22" rx="11" fill="#000"/>')
    txt(C, 112, "64 bpm · 8412 steps · 72%", 14, LABEL)
    sx, sy = on_ring(RING_R, s * 6)
    o.append(f'<g transform="translate({sx:.1f} {sy:.1f}) rotate({s * 6:.1f})"><rect x="-15" y="-7.5" width="30" height="15" rx="4" fill="#fff" stroke="#000" stroke-width="2"/></g>')
    for hr, icon in zip(SHORTCUT_HOURS, ("spotify", "wallet")):
        p = on_ring(RING_R, hr * 30)
        circ(p, 20.5, "#000", WHITE, 3)
        if icon == "spotify":
            circ(p, 12, "#1DB954")
            for i, (w, dy) in enumerate(((14, -4), (11, 1), (8, 5))):
                o.append(f'<path d="M{p[0] - w / 2:.1f} {p[1] + dy:.1f} q{w / 2:.1f} -3 {w:.1f} 0" fill="none" stroke="#000" stroke-width="2" stroke-linecap="round"/>')
        else:
            o.append(f'<rect x="{p[0] - 11:.1f}" y="{p[1] - 8:.1f}" width="22" height="16" rx="3" fill="#fff"/>')
            for i, c in enumerate(("#4285F4", "#34A853", "#FBBC04")):
                o.append(f'<rect x="{p[0] - 9:.1f}" y="{p[1] - 6 + i * 4:.1f}" width="18" height="3" rx="1" fill="{c}"/>')
    return wrap(o)


def wrap(o):
    body = "\n".join(o)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SIZE} {SIZE}" width="{SIZE}" height="{SIZE}">'
            f'<defs><clipPath id="face"><circle cx="{C}" cy="{C}" r="{C}"/></clipPath></defs>'
            f'<g clip-path="url(#face)"><rect width="{SIZE}" height="{SIZE}" fill="#000"/>{body}</g></svg>')


# ----------------------------------------------------------------------------- main
def main():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    ap = argparse.ArgumentParser()
    ap.add_argument("--svg", nargs="*", metavar="HH:MM:SS[.f][@palette][~aod]", help="also write preview SVGs")
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
        print("wrote", os.path.join(os.path.relpath(args.out_dir, root), name))


if __name__ == "__main__":
    main()
