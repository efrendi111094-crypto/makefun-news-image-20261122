#!/usr/bin/env python3
"""Sunday 22 November 2026, drawn as one newspaper front page.

A deterministic, standard-library-only Python 3.13 program. It paints a
1024x1024 PNG at /output/entry.png (or $MAKEFUN_OUTPUT_DIR/entry.png)
that sums up the world news of Sunday 22 November 2026: drones set the
sanctioned Russian cargo ship Sparta II ablaze in the Gulf of Finland,
Mexico captured FBI most-wanted cartel boss "El Chapo Isidro", the COP31
climate talks deadlocked over fossil fuels, and nine more stories from
six regions. Every headline and figure comes from reporting published
on 22 November 2026 (Reuters, AP, BBC, CNN, AFP, Times of India, The
Hindu and NDTV, listed in the footer).

The picture is drawn, not pasted: a hand-built 5x7 bitmap typeface, a
small rasteriser (rectangles, lines, circles, triangles) over an RGB
buffer, and a PNG writer built on zlib and struct. There is no network
access, no clock, no randomness, so the same source always produces
the same PNG bytes.

Layout, top to bottom: a navy masthead naming the date, a full-width
lead story with a drawn Baltic sea scene, two half-width stories, a row
of three stories, a by-the-numbers strip, an also-today strip with five
more stories, and a sources footer.
"""

import math
import os
import struct
import zlib
from pathlib import Path

# ---------------------------------------------------------------------------
# Page geometry and palette
# ---------------------------------------------------------------------------
W = 1024
H = 1024
M = 26                      # outer margin
CW = W - 2 * M              # content width

PAPER = (248, 244, 235)     # warm newsprint
INK = (16, 16, 18)          # near-black type
NAVY = (22, 36, 72)         # masthead band
NAVY2 = (40, 58, 104)       # lighter navy
RED = (172, 32, 32)         # accent red
GOLD = (216, 166, 64)       # warm gold
GREY = (110, 106, 98)       # secondary type
RULE = (58, 54, 48)         # thin rules
SEA = (14, 26, 48)          # night sea in the lead scene
SEA2 = (24, 46, 80)         # lighter sea
FLAME = (236, 150, 40)      # fire amber
SMOKE = (122, 124, 134)     # smoke grey
GREEN = (34, 112, 64)       # small positive accent
WHITE = (250, 248, 242)
CREAM = (232, 222, 198)     # pale panel
SKYDAY = (176, 204, 226)    # pale daytime sky


# ---------------------------------------------------------------------------
# Canvas: an RGB buffer with tiny drawing primitives
# ---------------------------------------------------------------------------
class Canvas:
    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.buf = bytearray(bg * (w * h))

    def put(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.buf[i:i + 3] = bytes(c)

    def rect(self, x, y, w, h, c):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        row = bytes(c) * (x1 - x0)
        for yy in range(y0, y1):
            i = (yy * self.w + x0) * 3
            self.buf[i:i + len(row)] = row

    def hline(self, x, y, w, c):
        self.rect(x, y, w, 1, c)

    def vline(self, x, y, h, c):
        self.rect(x, y, 1, h, c)

    def line(self, x0, y0, x1, y1, c):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.put(x0, y0, c)
            if x0 == x1 and y0 == y1:
                return
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def circle(self, cx, cy, r, c, fill=True):
        for yy in range(cy - r, cy + r + 1):
            dy = yy - cy
            span = int((r * r - dy * dy) ** 0.5)
            if fill:
                self.rect(cx - span, yy, span * 2 + 1, 1, c)
            else:
                self.put(cx - span, yy, c)
                self.put(cx + span, yy, c)

    def triangle(self, ax, ay, bx, by, cx, cy, c):
        # Filled triangle by scanlines.
        pts = sorted([(ax, ay), (bx, by), (cx, cy)], key=lambda p: p[1])
        (x0, y0), (x1, y1), (x2, y2) = pts

        def edge_x(xa, ya, xb, yb, y):
            if yb == ya:
                return xa
            return xa + (xb - xa) * (y - ya) / (yb - ya)

        for y in range(y0, y2 + 1):
            if y < y1:
                xa = edge_x(x0, y0, x1, y1, y)
                xb = edge_x(x0, y0, x2, y2, y)
            else:
                xa = edge_x(x1, y1, x2, y2, y)
                xb = edge_x(x0, y0, x2, y2, y)
            lo, hi = sorted([int(round(xa)), int(round(xb))])
            self.rect(lo, y, hi - lo + 1, 1, c)


# ---------------------------------------------------------------------------
# PNG writer: signature, IHDR, one IDAT, IEND; filter 0 on every row
# ---------------------------------------------------------------------------
def _chunk(kind, data):
    out = struct.pack(">I", len(data)) + kind + data
    out += struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return out


def write_png(path, canvas):
    w, h = canvas.w, canvas.h
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(0)
        raw += canvas.buf[y * stride:(y + 1) * stride]
    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", ihdr)
    png += _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += _chunk(b"IEND", b"")
    Path(path).write_bytes(png)

# ---------------------------------------------------------------------------
# Typeface: a 5x7 bitmap font. Each glyph is 7 rows; each row is a 5-bit
# value, bit 4 is the leftmost pixel. Only capitals, digits and the
# punctuation the page needs.
# ---------------------------------------------------------------------------
FONT = {
    "A": [0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11],
    "B": [0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E],
    "C": [0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E],
    "D": [0x1E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x1E],
    "E": [0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F],
    "F": [0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10],
    "G": [0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0F],
    "H": [0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11],
    "I": [0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E],
    "J": [0x07, 0x02, 0x02, 0x02, 0x02, 0x12, 0x0C],
    "K": [0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11],
    "L": [0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F],
    "M": [0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11],
    "N": [0x11, 0x19, 0x15, 0x13, 0x11, 0x11, 0x11],
    "O": [0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E],
    "P": [0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10],
    "Q": [0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D],
    "R": [0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11],
    "S": [0x0F, 0x10, 0x10, 0x0E, 0x01, 0x01, 0x1E],
    "T": [0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04],
    "U": [0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E],
    "V": [0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04],
    "W": [0x11, 0x11, 0x11, 0x15, 0x15, 0x15, 0x0A],
    "X": [0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11],
    "Y": [0x11, 0x11, 0x0A, 0x04, 0x04, 0x04, 0x04],
    "Z": [0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F],
    "0": [0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E],
    "1": [0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E],
    "2": [0x0E, 0x11, 0x01, 0x06, 0x08, 0x10, 0x1F],
    "3": [0x1F, 0x02, 0x04, 0x02, 0x01, 0x11, 0x0E],
    "4": [0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02],
    "5": [0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E],
    "6": [0x06, 0x08, 0x10, 0x1E, 0x11, 0x11, 0x0E],
    "7": [0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08],
    "8": [0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E],
    "9": [0x0E, 0x11, 0x11, 0x0F, 0x01, 0x02, 0x0C],
    " ": [0, 0, 0, 0, 0, 0, 0],
    ".": [0, 0, 0, 0, 0, 0x0C, 0x0C],
    ",": [0, 0, 0, 0, 0x0C, 0x04, 0x08],
    ":": [0, 0x0C, 0x0C, 0, 0x0C, 0x0C, 0],
    ";": [0, 0x0C, 0x0C, 0, 0x0C, 0x04, 0x08],
    "-": [0, 0, 0, 0x0E, 0, 0, 0],
    "'": [0x04, 0x04, 0x08, 0, 0, 0, 0],
    "(": [0x02, 0x04, 0x08, 0x08, 0x08, 0x04, 0x02],
    ")": [0x08, 0x04, 0x02, 0x02, 0x02, 0x04, 0x08],
    "/": [0x01, 0x02, 0x02, 0x04, 0x08, 0x08, 0x10],
    "%": [0x19, 0x1A, 0x02, 0x04, 0x08, 0x0B, 0x13],
    "+": [0, 0x04, 0x04, 0x1F, 0x04, 0x04, 0],
    "&": [0x0C, 0x12, 0x14, 0x08, 0x15, 0x12, 0x0D],
    "!": [0x04, 0x04, 0x04, 0x04, 0x04, 0, 0x04],
    "?": [0x0E, 0x11, 0x01, 0x02, 0x04, 0, 0x04],
    '"': [0x0A, 0x0A, 0, 0, 0, 0, 0],
    "=": [0, 0, 0x1F, 0, 0x1F, 0, 0],
    "$": [0x04, 0x0F, 0x14, 0x0E, 0x05, 0x1E, 0x04],
}


def text_w(s, scale):
    return len(s) * 6 * scale - scale


def draw_text(cv, x, y, s, scale, color):
    cx = x
    for ch in s:
        glyph = FONT.get(ch, FONT[" "])
        for row in range(7):
            bits = glyph[row]
            for col in range(5):
                if bits & (1 << (4 - col)):
                    cv.rect(cx + col * scale, y + row * scale,
                            scale, scale, color)
        cx += 6 * scale
    return cx


def text_center(cv, cx, y, s, scale, color):
    draw_text(cv, cx - text_w(s, scale) // 2, y, s, scale, color)


def wrap(s, max_chars):
    lines = []
    for para in s.split("\n"):
        words = para.split()
        cur = ""
        for w in words:
            trial = (cur + " " + w).strip()
            if len(trial) <= max_chars:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
    return lines


def paragraph(cv, x, y, s, scale, color, max_chars, leading):
    yy = y
    for line in wrap(s, max_chars):
        draw_text(cv, x, yy, line, scale, color)
        yy += 7 * scale + leading
    return yy

# ---------------------------------------------------------------------------
# Stories of the day (all reported on 22 November 2026)
# ---------------------------------------------------------------------------
MASTHEAD = "THE WORLD IN ONE DAY"
DATE_LINE = "SUNDAY 22 NOVEMBER 2026"
DATE_TAG = "12 STORIES  -  6 REGIONS"

LEAD = {
    "kicker": "GULF OF FINLAND  |  WAR AT SEA",
    "headline": "DRONES SET RUSSIAN SHIP ABLAZE IN THE BALTIC",
    "summary": (
        "TWO DRONES HIT THE SANCTIONED CARGO SHIP SPARTA II, BOUND FOR "
        "KALININGRAD, AND IT CAUGHT FIRE AND DRIFTED INTO FINNISH WATERS. "
        "ITS 16 CREW WERE EVACUATED. FINLAND SAID UKRAINE WAS LIKELY "
        "BEHIND THE ATTACK AND WARNED THE WAR IS SPILLING OVER."
    ),
}

HALF_STORIES = [
    {
        "kicker": "GUASAVE, MEXICO  |  CARTELS",
        "headline": "MEXICO CAPTURES FBI MOST-WANTED CARTEL BOSS",
        "summary": (
            "TROOPS SEIZED FAUSTO ISIDRO MEZA FLORES, KNOWN AS EL CHAPO "
            "ISIDRO, IN A FRIDAY NIGHT RAID. 11 DIED AS GUNMEN FOUGHT "
            "BACK ACROSS SINALOA."
        ),
        "scene": "badge",
    },
    {
        "kicker": "ANTALYA  |  CLIMATE",
        "headline": "COP31 DEADLOCK OVER FOSSIL FUELS",
        "summary": (
            "THE UN CLIMATE SUMMIT RAN PAST ITS DEADLINE AS NEARLY 200 "
            "NATIONS FAILED TO AGREE ON FOSSIL FUELS. TALKS SPILLED "
            "INTO SUNDAY WITH NO DEAL IN SIGHT."
        ),
        "scene": "globe",
    },
]

THIRD_STORIES = [
    {
        "kicker": "TALLINN  |  EUROPE",
        "headline": "ESTONIA SHUTS ITS BORDER WITH RUSSIA",
        "summary": (
            "ALL FIVE ROAD CROSSINGS CLOSE FROM 1 DECEMBER FOR SIX "
            "MONTHS. MOSCOW CALLS IT A NEW IRON CURTAIN."
        ),
        "scene": "barrier",
    },
    {
        "kicker": "BRASILIA  |  BRAZIL",
        "headline": "BOLSONARO IN INTENSIVE CARE",
        "summary": (
            "THE FORMER PRESIDENT, 71, IS IN HOSPITAL WITH AN ACUTE "
            "BOWEL OBSTRUCTION. DOCTORS WEIGH SURGERY."
        ),
        "scene": "cross",
    },
    {
        "kicker": "WELLINGTON  |  SPORT",
        "headline": "INDIA FACE NEW ZEALAND IN FIRST TEST",
        "summary": (
            "INDIA OPENED IN WINDY WELLINGTON AS KL RAHUL LED THE "
            "BATTING. NEW ZEALAND CHOSE TO BOWL FIRST."
        ),
        "scene": "cricket",
    },
]

NUMBERS = [
    ("2", "DRONES HIT SPARTA II"),
    ("16", "CREW EVACUATED"),
    ("11", "KILLED IN SINALOA"),
    ("5", "ESTONIA CROSSINGS SHUT"),
    ("200", "NATIONS AT COP31"),
    ("$5M", "FBI REWARD"),
]

ALSO_TODAY = [
    "MODI OPENS NITISH SETU BRIDGE IN BIHAR",
    "CYCLONE AKVAN: 14 FLIGHTS AXED AT RANCHI",
    "CRICKETER CHAHAL JOINS BJP, GETS OBC ROLE",
    "US AIRLINES WARNED OF ATTACK THREAT BEFORE THANKSGIVING",
    "TWO TANKERS HIT OFF OMAN, UK REPORTS",
]

FOOTER = ("SOURCES: REUTERS, AP, BBC, CNN, AFP, TIMES OF INDIA, THE HINDU, "
          "NDTV  -  DRAWN, NOT PHOTOGRAPHED  -  SUNDAY 22 NOVEMBER 2026")


# ---------------------------------------------------------------------------
# Scenes: small drawn pictures for the lead and the half/third stories
# ---------------------------------------------------------------------------
def scene_baltic(cv, x, y, w, h):
    # Night sea, burning ship, smoke, rescue boat. Everything stays
    # inside the scene rectangle.
    cv.rect(x, y, w, h, SEA)
    cv.rect(x, y, w, h // 3, (18, 30, 58))
    cv.circle(x + w - 90, y + 26, 18, (228, 226, 210))          # moon
    cv.circle(x + w - 98, y + 22, 16, (18, 30, 58))
    horizon = y + h - 24
    cv.rect(x, horizon, w, h - (h - 24), SEA2)
    for i in range(9):                                            # waves
        wx = x + 20 + i * (w - 40) // 9
        cv.rect(wx, horizon + 6 + (i % 2) * 8, 46, 3, (90, 130, 170))
    # Ship: dark hull, containers, funnel, masts.
    sx, sy = x + w // 2 - 190, horizon - 22
    cv.rect(sx, sy, 380, 22, (12, 12, 14))
    cv.triangle(sx, sy, sx + 30, sy + 22, sx, sy + 22, (12, 12, 14))
    cv.triangle(sx + 380, sy, sx + 350, sy + 22, sx + 380, sy + 22,
                (12, 12, 14))
    cv.rect(sx + 40, sy - 22, 90, 22, (150, 52, 40))
    cv.rect(sx + 140, sy - 22, 90, 22, (52, 96, 140))
    cv.rect(sx + 240, sy - 22, 90, 22, (150, 52, 40))
    cv.rect(sx + 300, sy - 38, 16, 16, (30, 30, 34))
    cv.line(sx + 60, sy - 22, sx + 60, sy - 42, (200, 200, 200))
    cv.line(sx + 320, sy - 22, sx + 320, sy - 42, (200, 200, 200))
    # Small flames and smoke puffs above the deck.
    for fx, fr in [(sx + 90, 11), (sx + 180, 12), (sx + 270, 10)]:
        cv.circle(fx, sy - 26, fr, FLAME)
        cv.circle(fx, sy - 31, fr - 5, GOLD)
    for px, py, pr in [(sx + 110, sy - 38, 7), (sx + 200, sy - 42, 8),
                       (sx + 290, sy - 36, 7)]:
        cv.circle(px, py, pr, SMOKE)
    # Small rescue boat with a light.
    bx, by = x + 60, horizon + 10
    cv.rect(bx, by, 90, 12, (200, 80, 40))
    cv.triangle(bx + 90, by, bx + 106, by + 12, bx + 90, by + 12,
                (200, 80, 40))
    cv.circle(bx + 45, by - 6, 4, GOLD)
    cv.rect(bx + 20, by - 12, 4, 10, WHITE)


def scene_badge(cv, x, y, w, h):
    # Desert dusk with a sheriff's star.
    cv.rect(x, y, w, h, (232, 196, 140))
    cv.circle(x + w - 46, y + 26, 20, (238, 150, 60))
    cv.rect(x, y + h - 30, w, 30, (176, 116, 64))
    cv.rect(x, y + h - 46, w, 8, (150, 96, 54))
    cx, cy = x + w // 2, y + h // 2 - 4
    r = h // 2 - 6
    pts = []
    for i in range(10):
        rr = r if i % 2 == 0 else r // 2 + 2
        a = -math.pi / 2 + i * math.pi / 5
        pts.append((cx + int(rr * math.cos(a)), cy + int(rr * math.sin(a))))
    for i in range(10):
        cv.line(pts[i][0], pts[i][1], pts[(i + 1) % 10][0],
                pts[(i + 1) % 10][1], GOLD)
    cv.circle(cx, cy, 12, GOLD)
    draw_text(cv, cx - 6, cy - 10, "$", 3, NAVY)


def scene_globe(cv, x, y, w, h):
    # A warming globe: blue oceans, green land, red crack.
    cx, cy = x + w // 2, y + h // 2
    r = h // 2 - 4
    cv.circle(cx, cy, r, (52, 110, 180))
    cv.circle(cx - r // 3, cy - r // 4, r // 3, GREEN)
    cv.circle(cx + r // 3, cy + r // 5, r // 2 - 4, GREEN)
    cv.circle(cx + r // 8, cy - r // 2, r // 5, GREEN)
    for dy in (-r // 2, 0, r // 2):                               # latitude
        cv.hline(cx - r + 4, cy + dy, 2 * r - 8, (140, 190, 230))
    cv.line(cx - r // 6, cy - r, cx + r // 12, cy - r // 3, RED)
    cv.line(cx + r // 12, cy - r // 3, cx - r // 8, cy + r // 6, RED)
    cv.line(cx - r // 8, cy + r // 6, cx + r // 5, cy + r // 2, RED)
    cv.line(cx + r // 5, cy + r // 2, cx, cy + r, RED)


def scene_barrier(cv, x, y, w, h):
    # A striped border barrier under a grey sky.
    cv.rect(x, y, w, h, (198, 202, 208))
    cv.rect(x, y + h - 22, w, 22, (120, 124, 120))
    for i in range(5):                                            # posts
        cv.rect(x + 14 + i * 34, y + h - 34, 6, 14, INK)
    for i in range(5):                                            # stripes
        cv.rect(x + 10 + i * 34, y + h - 40, 30, 10,
                RED if i % 2 == 0 else WHITE)
    cv.rect(x + w - 96, y + 8, 84, 34, WHITE)
    draw_text(cv, x + w - 88, y + 15, "CLOSED", 2, RED)


def scene_cross(cv, x, y, w, h):
    # A hospital building with a red cross on its roof.
    cv.rect(x, y, w, h, (214, 226, 232))
    cx = x + w // 2
    cv.rect(cx - 6, y + 2, 12, 20, RED)
    cv.rect(cx - 14, y + 8, 28, 10, RED)
    cv.rect(x + 30, y + 24, w - 60, h - 24, WHITE)
    cv.rect(x + 30, y + 24, w - 60, 5, NAVY)
    for i in range(4):
        cv.rect(x + 44 + i * 34, y + 36, 18, 14, SKYDAY)


def scene_cricket(cv, x, y, w, h):
    # Green pitch, stumps and a red ball.
    cv.rect(x, y, w, h, (120, 168, 92))
    cv.rect(x + w // 2 - 26, y + 6, 52, h - 12, (214, 196, 150))
    for i, sx in enumerate([-14, 0, 14]):
        cv.rect(x + w // 2 + sx - 2, y + 12, 4, 28, GOLD)
    cv.circle(x + w // 2, y + h - 26, 10, RED)
    cv.circle(x + w // 2 - 3, y + h - 29, 3, (255, 120, 120))
    cv.line(x + 16, y + h - 14, x + w - 16, y + h - 14, WHITE)

# ---------------------------------------------------------------------------
# Layout: masthead, lead, halves, thirds, numbers, also-today, footer
# ---------------------------------------------------------------------------
SCENES = {
    "badge": scene_badge,
    "globe": scene_globe,
    "barrier": scene_barrier,
    "cross": scene_cross,
    "cricket": scene_cricket,
}


def story_block(cv, x, y, w, story, scene_h, head_scale, sum_scale,
                sum_chars):
    cv.rect(x, y, w, 2, RULE)
    draw_text(cv, x, y + 10, story["kicker"], 2, RED)
    yy = y + 10 + 7 * 2 + 8
    yy = paragraph(cv, x, yy, story["headline"], head_scale, INK,
                   max(1, w // (6 * head_scale)), 4)
    yy += 6
    if story.get("scene"):
        SCENES[story["scene"]](cv, x, yy, w, scene_h)
        yy += scene_h + 10
    yy = paragraph(cv, x, yy, story["summary"], sum_scale, INK,
                   max(1, w // (6 * sum_scale)), 3)
    return yy


def build():
    cv = Canvas(W, H, PAPER)

    # Masthead.
    cv.rect(0, 0, W, 92, NAVY)
    cv.rect(0, 92, W, 4, GOLD)
    text_center(cv, W // 2, 10, MASTHEAD, 4, WHITE)
    text_center(cv, W // 2, 10 + 7 * 4 + 4, DATE_LINE, 3, GOLD)
    text_center(cv, W // 2, 10 + 7 * 4 + 4 + 7 * 3 + 4, DATE_TAG, 2,
                (200, 204, 220))

    y = 104

    # Lead story, full width, with the Baltic scene.
    cv.rect(M, y, CW, 2, RULE)
    draw_text(cv, M, y + 10, LEAD["kicker"], 2, RED)
    yy = y + 10 + 7 * 2 + 8
    yy = paragraph(cv, M, yy, LEAD["headline"], 4, INK,
                   max(1, CW // 24), 4)
    yy += 6
    scene_baltic(cv, M, yy, CW, 96)
    yy += 96 + 10
    yy = paragraph(cv, M, yy, LEAD["summary"], 2, INK,
                   max(1, CW // 12), 3)
    y = yy + 6

    # Two half-width stories.
    half = (CW - 24) // 2
    left_end = story_block(cv, M, y, half, HALF_STORIES[0], 60, 3, 2, 0)
    right_end = story_block(cv, M + half + 24, y, half, HALF_STORIES[1],
                            60, 3, 2, 0)
    y = max(left_end, right_end) + 6

    # Three third-width stories.
    third = (CW - 48) // 3
    ends = []
    for i, story in enumerate(THIRD_STORIES):
        ends.append(story_block(cv, M + i * (third + 24), y, third,
                                story, 50, 2, 2, 0))
    y = max(ends) + 6

    # By-the-numbers strip.
    cv.rect(M, y, CW, 2, RULE)
    draw_text(cv, M, y + 8, "BY THE NUMBERS", 2, RED)
    ny = y + 8 + 7 * 2 + 8
    cell = CW // 6
    for i, (num, label) in enumerate(NUMBERS):
        cx = M + i * cell
        text_center(cv, cx + cell // 2, ny, num, 3, NAVY)
        paragraph(cv, cx + 4, ny + 7 * 3 + 8, label, 1, GREY,
                  max(1, (cell - 8) // 6), 2)
    y = ny + 7 * 3 + 6 + 7 * 2 + 8

    # Also-today strip.
    cv.rect(M, y, CW, 2, RULE)
    draw_text(cv, M, y + 8, "ALSO TODAY", 2, RED)
    ay = y + 8 + 7 * 2 + 8
    for item in ALSO_TODAY:
        draw_text(cv, M + 18, ay, item, 2, INK)
        cv.circle(M + 7, ay + 6, 4, RED)
        ay += 7 * 2 + 1
    y = ay + 4

    # Footer.
    cv.rect(M, y, CW, 2, RULE)
    draw_text(cv, M, y + 10, FOOTER, 1, GREY)
    return cv


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    out = Path(out_dir) / "entry.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    write_png(str(out), build())


if __name__ == "__main__":
    main()
