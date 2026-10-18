#!/usr/bin/env python3
"""Generates every asset for Meadow Friends: tiles, maps, palettes, sound.

All art is drawn here in code. Outputs go to build/ along with assets.inc
(constants and tables for the assembler) and preview PNGs.
"""
import math
import os
import random
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
import spc  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "build")
os.makedirs(OUT, exist_ok=True)


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def bgr555(c):
    r, g, b = c
    return (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)


def pal16(colors):
    """colors: list of up to 15 hex strings for indices 1..15."""
    p = [rgb("#000000")] + [rgb(c) for c in colors]
    p += [rgb("#000000")] * (16 - len(p))
    return p


# ---------------------------------------------------------------- shapes

def ellipse(cx, cy, rx, ry):
    s = set()
    for y in range(int(cy - ry) - 2, int(cy + ry) + 3):
        for x in range(int(cx - rx) - 2, int(cx + rx) + 3):
            dx = (x + 0.5 - cx) / rx
            dy = (y + 0.5 - cy) / ry
            if dx * dx + dy * dy <= 1.0:
                s.add((x, y))
    return s


def rect(x0, y0, x1, y1):
    return {(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)}


def poly(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    s = set()
    for y in range(int(min(ys)) - 1, int(max(ys)) + 2):
        for x in range(int(min(xs)) - 1, int(max(xs)) + 2):
            px, py = x + 0.5, y + 0.5
            inside = False
            j = len(pts) - 1
            for i in range(len(pts)):
                xi, yi = pts[i]
                xj, yj = pts[j]
                if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi) + xi:
                    inside = not inside
                j = i
            if inside:
                s.add((x, y))
    return s


def dilate(m, diag=False):
    out = set(m)
    nb = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    if diag:
        nb += [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    for x, y in m:
        for dx, dy in nb:
            out.add((x + dx, y + dy))
    return out


def mirror(m, w=32):
    return {(w - 1 - x, y) for x, y in m}


def shift(m, dx, dy):
    return {(x + dx, y + dy) for x, y in m}


def pts(*p):
    return set(p)


class Canvas:
    def __init__(self, w, h, fill=0):
        self.w, self.h = w, h
        self.p = [fill] * (w * h)

    def get(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.p[y * self.w + x]
        return 0

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.p[y * self.w + x] = c

    def paint(self, m, c):
        for x, y in m:
            self.set(x, y, c)

    def part(self, m, fill, outline=1, diag=False):
        self.paint(dilate(m, diag) - m, outline)
        self.paint(m, fill)

    def rim(self, m, c, dx=1, dy=2):
        """Shade pixels of m whose (x+dx, y+dy) neighbour falls outside m."""
        self.paint({(x, y) for x, y in m if (x + dx, y + dy) not in m}, c)

    def blit(self, other, ox, oy):
        for y in range(other.h):
            for x in range(other.w):
                v = other.p[y * other.w + x]
                if v:
                    self.set(ox + x, oy + y, v)

    def tile(self, tx, ty):
        return [self.get(tx * 8 + x, ty * 8 + y) for y in range(8) for x in range(8)]


def tile4bpp(pix):
    out = bytearray(32)
    for y in range(8):
        b = [0, 0, 0, 0]
        for x in range(8):
            v = pix[y * 8 + x]
            for p in range(4):
                if (v >> p) & 1:
                    b[p] |= 0x80 >> x
        out[y * 2] = b[0]
        out[y * 2 + 1] = b[1]
        out[16 + y * 2] = b[2]
        out[16 + y * 2 + 1] = b[3]
    return bytes(out)


# ---------------------------------------------------------------- fonts

FONT5x7 = {
    "A": [".XXX.", "X...X", "X...X", "XXXXX", "X...X", "X...X", "X...X"],
    "B": ["XXXX.", "X...X", "X...X", "XXXX.", "X...X", "X...X", "XXXX."],
    "D": ["XXXX.", "X...X", "X...X", "X...X", "X...X", "X...X", "XXXX."],
    "E": ["XXXXX", "X....", "X....", "XXXX.", "X....", "X....", "XXXXX"],
    "F": ["XXXXX", "X....", "X....", "XXXX.", "X....", "X....", "X...."],
    "I": [".XXX.", "..X..", "..X..", "..X..", "..X..", "..X..", ".XXX."],
    "M": ["X...X", "XX.XX", "X.X.X", "X.X.X", "X...X", "X...X", "X...X"],
    "N": ["X...X", "XX..X", "X.X.X", "X..XX", "X...X", "X...X", "X...X"],
    "O": [".XXX.", "X...X", "X...X", "X...X", "X...X", "X...X", ".XXX."],
    "R": ["XXXX.", "X...X", "X...X", "XXXX.", "X.X..", "X..X.", "X...X"],
    "S": [".XXXX", "X....", "X....", ".XXX.", "....X", "....X", "XXXX."],
    "W": ["X...X", "X...X", "X...X", "X.X.X", "X.X.X", "XX.XX", "X...X"],
    "X": ["X...X", "X...X", ".X.X.", "..X..", ".X.X.", "X...X", "X...X"],
    "Y": ["X...X", "X...X", ".X.X.", "..X..", "..X..", "..X..", "..X.."],
}

FONT3x5 = {
    "A": [".X.", "X.X", "XXX", "X.X", "X.X"],
    "B": ["XX.", "X.X", "XX.", "X.X", "XX."],
    "X": ["X.X", "X.X", ".X.", "X.X", "X.X"],
    "Y": ["X.X", "X.X", ".X.", ".X.", ".X."],
    "L": ["X..", "X..", "X..", "X..", "XXX"],
    "R": ["XX.", "X.X", "XX.", "X.X", "X.X"],
}


def glyph(font, ch, ox, oy, scale=1):
    s = set()
    for y, row in enumerate(font[ch]):
        for x, c in enumerate(row):
            if c == "X":
                for sy in range(scale):
                    for sx in range(scale):
                        s.add((ox + x * scale + sx, oy + y * scale + sy))
    return s


# ---------------------------------------------------------------- palettes

ANIMALS = ["bunny", "puppy", "kitty", "piggy", "frog", "chick"]
# 1 outline 2 main 3 shade 4 light 5 pink 6 eye 7 white 8 accent 9 accent2
ANIMAL_PALS = {
    "bunny": ["#5A4660", "#F6F2F8", "#D4CCE0", "#FFFFFF", "#FF9EC4", "#241C2C", "#FFFFFF", "#FFC4DA", "#E07898"],
    "puppy": ["#4A2E1C", "#DCA068", "#B87C48", "#FAE6C8", "#FF94AC", "#201818", "#FFFFFF", "#8C5C38", "#2A2020"],
    "kitty": ["#5C3018", "#FFB454", "#E08A30", "#FFF2DE", "#FF94AC", "#201818", "#FFFFFF", "#E07420", "#FF7898"],
    "piggy": ["#6E3044", "#FFBACA", "#F094AA", "#FFDCE4", "#FF7EA0", "#2A1820", "#FFFFFF", "#F07C98", "#9A3858"],
    "frog":  ["#24461E", "#72D25E", "#4CA842", "#DAF8B4", "#FF9AB0", "#14200E", "#FFFFFF", "#A6EC86", "#C04060"],
    "chick": ["#6A4C14", "#FFE24A", "#F2B82C", "#FFF6A8", "#FF9C9C", "#241C10", "#FFFFFF", "#FF9420", "#D06010"],
}

# OBJ palette 6: items, particles, shadows
FX_PAL = ["#3A2030", "#F04040", "#B02838", "#50C040", "#2E8030", "#FF9830", "#D06818",
          "#FFE040", "#E0A010", "#FFFFFF", "#8A5A30", "#FF80B0", "#48A0FF", "#B070F0", "#1E3A1E"]
FX = {n: i + 1 for i, n in enumerate(["ol", "red", "dred", "grn", "dgrn", "org", "dorg", "yel",
                                         "gold", "wht", "brn", "pink", "blue", "purp", "shadow"])}
# OBJ palette 7: balloons + HUD highlights
BAL_PAL = ["#281838", "#6040B0", "#402880", "#8A70D8", "#B8A8F0", "#9080D0", "#E0D8FF",
           "#FFFFFF", "#E8E8E8", "#FFE040", "#FFF8A0", "#E09800", "#301848", "#FF8040", "#A0A0A0"]
BAL = {n: i + 1 for i, n in enumerate(["ol", "pur", "purd", "purl", "lav", "lavd", "lavl",
                                          "wht", "str", "glow", "glowl", "glowd", "ink", "orange", "gray"])}

# BG palette 0 (sky region), per time of day
# 1-3 sky bands, 4-6 stars per band, 7-8 cloud, 9-10 sun/moon, 11-12 hill, 13-14 tree, 15 trunk
SKY_TOD = {
    "day":     ["#4898F0", "#70B8F8", "#A8D8FF", "#4898F0", "#70B8F8", "#A8D8FF", "#FFFFFF", "#D0E4F8",
                "#FFF050", "#FFC020", "#78C070", "#58A058", "#3C9848", "#287038", "#805030"],
    "sunset":  ["#6050A8", "#E07890", "#FFB070", "#6050A8", "#E07890", "#FFB070", "#FFD0C0", "#E8A0A0",
                "#FF9040", "#FF6030", "#8A6090", "#6A4878", "#4A7040", "#305030", "#5A3828"],
    "night":   ["#101838", "#182450", "#203060", "#FFFFD0", "#E8E8FF", "#C8C8F0", "#404A70", "#303858",
                "#F8F8D8", "#D8D8B8", "#1C3848", "#142838", "#1A4030", "#10281E", "#2A2018"],
    "morning": ["#90C8F0", "#B8E0F8", "#F0E8D0", "#90C8F0", "#B8E0F8", "#F0E8D0", "#FFFFFF", "#F0E0E8",
                "#FFF8B0", "#FFE080", "#88C8A0", "#68A888", "#58A060", "#3C7848", "#7A5838"],
}
# BG palette 1 (meadow): 1 base 2 light 3 dark 4 tuft 5 red 6 yellow 7 white 8 blue 9 centre 10 pink
#                        11 leaf 12 rock 13 rock dark
GRASS_TOD = {
    "day":     ["#68C050", "#88D868", "#50A040", "#3C8830", "#F05050", "#FFE048", "#FFFFFF", "#6090FF",
                "#FFB020", "#FF90C8", "#3A9030", "#B8B8B0", "#888880"],
    "sunset":  ["#78A850", "#98C068", "#608840", "#4C7030", "#E04848", "#F8C840", "#FFE8E0", "#7078D8",
                "#F09820", "#F080B0", "#4A7830", "#B8A098", "#887068"],
    "night":   ["#1E4838", "#285848", "#183C2E", "#12301F", "#803040", "#A09040", "#B0B8C8", "#3850A0",
                "#907030", "#905878", "#183820", "#505868", "#384050"],
    "morning": ["#70C868", "#90E088", "#58A850", "#448838", "#F06060", "#FFE860", "#FFFFFF", "#78A0FF",
                "#FFC040", "#FFA0D0", "#48A040", "#C0C0B8", "#909088"],
}
TOD_ORDER = ["day", "sunset", "night", "morning"]

# BG palette 4: title letters. 1 outline 2 shadow 3-8 colours 9-14 light variants
TITLE_PAL = ["#302040", "#1A1430", "#F04848", "#FF9830", "#FFD830", "#50C040", "#3890F8", "#A060E8",
             "#FF9090", "#FFC880", "#FFF0A0", "#A0F090", "#98D0FF", "#D0A8FF"]
# BG palette 5: progress slots
SLOT_PAL = ["#403020", "#F4F0F0", "#D0CCD8", "#FFE040", "#E8A000", "#FFFFFF"]
# BG palette 7: HUD board + controllers
HUD_PAL = ["#C89A60", "#E2BA84", "#9A6E40", "#DCDCE4", "#B4B4C0", "#848494", "#34343E", "#5838A0",
           "#3E2878", "#B4A4EC", "#8C7CC8", "#FFFFFF", "#28202E", "#9C9CAC", "#585868"]
HUD = {n: i + 1 for i, n in enumerate(["base", "light", "dark", "c1", "c2", "c3", "pad", "pur", "purd",
                                          "lav", "lavd", "wht", "ol", "well", "padl"])}


# ---------------------------------------------------------------- animals

O, MAIN, SHADE, LIGHT, PINK, EYE, WHITE, ACC, ACC2 = range(1, 10)


def eyes(c, happy, lx=11, y=13, frog=False):
    """Left eye at columns lx..lx+1, right eye mirrored."""
    if happy:
        left = pts((lx - 1, y + 2), (lx, y + 1), (lx + 1, y + 1), (lx + 2, y + 2))
        c.paint(left | mirror(left), EYE)
        return
    left = rect(lx, y, lx + 1, y + 2)
    c.paint(left | mirror(left), EYE)
    c.set(lx, y, WHITE)
    c.set(31 - lx - 1, y, WHITE)


def body_and_feet(c, frame, feet_col=MAIN, belly=True):
    body = ellipse(16, 24, 7, 5.5)
    c.part(body, MAIN)
    c.rim(body, SHADE, 0, 1)
    if belly:
        c.paint(ellipse(16, 25, 4, 3), LIGHT)
    if frame == 1:
        lf, rf = ellipse(12, 27.5, 3, 2), ellipse(20, 29, 3, 2)
    else:
        lf, rf = ellipse(12.5, 29, 3, 2), ellipse(19.5, 29, 3, 2)
    c.part(lf, feet_col)
    c.part(rf, feet_col)
    arm = ellipse(9, 23.5, 2, 2.5)
    c.part(arm, MAIN)
    c.part(mirror(arm), MAIN)


def head(c, cx=16, cy=14, rx=11, ry=9.5):
    h = ellipse(cx, cy, rx, ry)
    c.part(h, MAIN)
    c.rim(h, SHADE, 1, 2)
    return h


def cheeks(c, y=17):
    c.paint(pts((8, y), (9, y)) | mirror(pts((8, y), (9, y))), PINK)


def draw_bunny(c, frame, happy):
    ear = ellipse(11.5, 6.5, 2.7, 6.2)
    c.part(ear, MAIN)
    c.part(mirror(ear), MAIN)
    inner = ellipse(11.5, 7, 1.2, 4.3)
    c.paint(inner | mirror(inner), ACC)
    body_and_feet(c, frame)
    head(c, cy=15, ry=9)
    eyes(c, happy, y=14)
    cheeks(c, 18)
    c.paint(pts((15, 18), (16, 18)), ACC2)
    c.paint(pts((14, 20), (15, 19), (16, 19), (17, 20)), O)


def draw_puppy(c, frame, happy):
    body_and_feet(c, frame)
    head(c)
    c.paint(ellipse(20.5, 12.5, 3, 2.6), ACC)  # spot over the right eye
    muzzle = ellipse(16, 18.5, 4.5, 3.2)
    c.paint(muzzle, LIGHT)
    ear = ellipse(6.5, 13.5, 3, 6)
    c.part(ear, ACC)
    c.part(mirror(ear), ACC)
    eyes(c, happy)
    c.paint(rect(15, 16, 16, 17), ACC2)
    c.paint(pts((15, 18), (16, 18), (14, 19), (17, 19)), O)
    if happy:
        c.paint(rect(15, 19, 16, 21), PINK)
    cheeks(c, 17)


def draw_kitty(c, frame, happy):
    ear = poly([(5.5, 12), (7, 1.5), (14, 7)])
    c.part(ear, MAIN)
    c.part(mirror(ear), MAIN)
    inner = poly([(7.2, 9.5), (8, 4.5), (11.5, 7.5)])
    c.paint(inner | mirror(inner), PINK)
    body_and_feet(c, frame)
    head(c)
    stripes = rect(15, 5, 16, 7) | pts((12, 6), (12, 7)) | pts((19, 6), (19, 7))
    c.paint(stripes, ACC)
    c.paint(ellipse(16, 18.5, 3.6, 2.4), LIGHT)
    eyes(c, happy)
    c.paint(pts((15, 17), (16, 17)), ACC2)
    c.paint(pts((14, 19), (15, 18), (16, 18), (17, 19)), O)
    whisk = pts((2, 16), (3, 16), (4, 17)) | pts((2, 19), (3, 19), (4, 18))
    c.paint(whisk | mirror(whisk), O)
    cheeks(c, 17)


def draw_piggy(c, frame, happy):
    ear = poly([(5.5, 9), (7, 2), (13, 6)])
    c.part(ear, MAIN)
    c.part(mirror(ear), MAIN)
    c.paint(poly([(7.3, 7.5), (8, 4.2), (11, 6.2)]) | mirror(poly([(7.3, 7.5), (8, 4.2), (11, 6.2)])), ACC)
    body_and_feet(c, frame)
    head(c)
    eyes(c, happy, y=12)
    snout = ellipse(16, 17.5, 4, 2.8)
    c.part(snout, ACC)
    c.paint(pts((14, 17), (14, 18), (17, 17), (17, 18)), ACC2)
    c.paint(pts((15, 21), (16, 21)), O)
    cheeks(c, 16)


def draw_frog(c, frame, happy):
    body_and_feet(c, frame)
    h = ellipse(16, 15.5, 12, 8)
    c.part(h, MAIN)
    c.rim(h, SHADE, 1, 2)
    bump = ellipse(10, 8.5, 4.2, 4.2)
    c.part(bump, MAIN)
    c.part(mirror(bump), MAIN)
    white = ellipse(10, 8.5, 3, 3)
    c.paint(white | mirror(white), WHITE)
    if happy:
        arc = pts((8, 9), (9, 8), (10, 8), (11, 9))
        c.paint(arc | mirror(arc), EYE)
    else:
        pupil = rect(10, 7, 11, 9)
        c.paint(pupil | mirror(pupil), EYE)
        c.set(10, 7, WHITE)
        c.set(20, 7, WHITE)
    smile = pts((10, 16), (11, 17), (12, 18), (13, 18), (14, 19), (15, 19), (16, 19), (17, 19),
                (18, 18), (19, 18), (20, 17), (21, 16))
    c.paint(smile, O)
    if happy:
        c.paint(rect(14, 20, 17, 20), ACC2)
    c.paint(pts((6, 17), (7, 17)) | mirror(pts((6, 17), (7, 17))), PINK)


def draw_chick(c, frame, happy):
    body_and_feet(c, frame, feet_col=ACC)
    h = head(c, cy=15, ry=10)
    tuft = pts((15, 3), (15, 4), (16, 2), (16, 3), (16, 4), (17, 3), (14, 4), (17, 4))
    c.part(tuft, MAIN)
    wing = ellipse(6, 18, 2.2, 3.5)
    c.part(wing, SHADE)
    c.part(mirror(wing), SHADE)
    eyes(c, happy, y=13)
    beak = poly([(13.5, 16.5), (18.5, 16.5), (16, 20)])
    c.part(beak, ACC)
    c.paint(pts((14, 16), (15, 16), (16, 16), (17, 16)), ACC)
    cheeks(c, 17)


def icon(name):
    """16x16 face for the on-screen controller."""
    c = Canvas(16, 16)
    hx, hy = 8, 9.5
    if name == "bunny":
        ear = ellipse(5.5, 3.5, 1.6, 3.6)
        c.part(ear, MAIN); c.part(mirror(ear, 16), MAIN)
        c.paint(pts((5, 2), (5, 3), (5, 4)) | mirror(pts((5, 2), (5, 3), (5, 4)), 16), ACC)
    elif name == "kitty":
        ear = poly([(2.5, 7), (3.5, 1.5), (7.5, 5)])
        c.part(ear, MAIN); c.part(mirror(ear, 16), MAIN)
    elif name == "piggy":
        ear = poly([(2.5, 6), (3.5, 2), (7, 4.5)])
        c.part(ear, MAIN); c.part(mirror(ear, 16), MAIN)
    elif name == "frog":
        hy = 10
    elif name == "chick":
        c.part(pts((7, 2), (8, 2), (8, 3), (7, 3), (6, 3)), MAIN)
    head = ellipse(hx, hy, 6.6, 5.4) if name != "frog" else ellipse(hx, hy, 7, 4.6)
    c.part(head, MAIN)
    c.rim(head, SHADE, 1, 1)
    if name == "puppy":
        ear = ellipse(2.5, 9, 1.8, 3.4)
        c.part(ear, ACC); c.part(mirror(ear, 16), ACC)
        c.paint(ellipse(8, 11.5, 2.6, 1.8), LIGHT)
        c.paint(pts((7, 10), (8, 10)), ACC2)
    if name == "frog":
        bump = ellipse(4.5, 6, 2.6, 2.6)
        c.part(bump, MAIN); c.part(mirror(bump, 16), MAIN)
        c.paint(pts((4, 5), (4, 6)) | mirror(pts((4, 5), (4, 6)), 16), EYE)
        c.paint(pts((5, 11), (6, 12), (7, 12), (8, 12), (9, 12), (10, 11)), O)
    else:
        e = pts((5, 9), (5, 10))
        c.paint(e | mirror(e, 16), EYE)
        c.paint(pts((3, 11)) | mirror(pts((3, 11)), 16), PINK)
    if name == "piggy":
        sn = ellipse(8, 11.5, 2.4, 1.6)
        c.part(sn, ACC)
        c.paint(pts((7, 11), (8, 11)), ACC2)
    if name in ("bunny", "kitty"):
        c.paint(pts((7, 11), (8, 11)), ACC2)
    if name == "chick":
        c.part(pts((7, 11), (8, 11), (7, 12), (8, 12)), ACC)
    return c


DRAW = {"bunny": draw_bunny, "puppy": draw_puppy, "kitty": draw_kitty,
        "piggy": draw_piggy, "frog": draw_frog, "chick": draw_chick}


def animal_frames(name):
    frames = []
    for frame, happy in ((0, False), (1, False), (0, True)):
        c = Canvas(32, 32)
        DRAW[name](c, frame, happy)
        frames.append(c)
    return frames


# ---------------------------------------------------------------- balloons, HUD lights

def balloon(letter):
    c = Canvas(32, 32)
    dark = letter in "AB"
    body_c, shade_c, light_c = (BAL["pur"], BAL["purd"], BAL["purl"]) if dark else \
                               (BAL["lav"], BAL["lavd"], BAL["lavl"])
    # string first so the balloon covers its top
    string = pts((16, 27), (15, 28), (15, 29), (16, 30), (16, 31))
    c.paint(string, BAL["str"])
    b = ellipse(16, 13, 11.5, 12.5)
    c.part(b, body_c, BAL["ol"])
    c.rim(b, shade_c, 1, 2)
    knot = poly([(13.5, 27.5), (18.5, 27.5), (16, 24.5)])
    c.part(knot, shade_c, BAL["ol"])
    c.paint(ellipse(10, 6.5, 2.2, 3.2), light_c)
    c.set(9, 5, BAL["wht"])
    g = glyph(FONT5x7, letter, 11, 7, 2)
    c.paint(dilate(g, True) - g, BAL["ink"])
    c.paint(g, BAL["wht"])
    return c


def lit_button(letter):
    c = Canvas(16, 16)
    circ = ellipse(7.5, 7.5, 6.6, 6.6)
    c.part(circ, BAL["glow"], BAL["glowd"])
    c.paint(ellipse(5.5, 5.5, 2.2, 1.8), BAL["glowl"])
    c.paint(glyph(FONT3x5, letter, 6, 5), BAL["ink"])
    return c


def lit_dpad_up():
    c = Canvas(16, 16)
    arm = rect(4, 2, 11, 10)
    c.part(arm, BAL["glow"], BAL["glowd"])
    c.paint(poly([(6, 8), (10, 8), (8, 4)]), BAL["glowd"])
    return c


def lit_dpad_right():
    c = Canvas(16, 16)
    arm = rect(5, 4, 13, 11)
    c.part(arm, BAL["glow"], BAL["glowd"])
    c.paint(poly([(7, 6), (7, 10), (11, 8)]), BAL["glowd"])
    return c


def lit_pill():
    c = Canvas(16, 16)
    pill = rect(4, 6, 11, 9) | rect(3, 7, 12, 8)
    c.part(pill, BAL["glow"], BAL["glowd"])
    return c


def lit_shoulder():
    c = Canvas(32, 32)
    bar = rect(2, 1, 25, 7) | rect(1, 2, 26, 6)
    c.part(bar, BAL["glow"], BAL["glowd"])
    return c


# ---------------------------------------------------------------- items & effects

def item_apple():
    c = Canvas(16, 16)
    a = ellipse(8, 9.5, 6, 5.5) | ellipse(5.5, 8, 3.5, 3.5) | ellipse(10.5, 8, 3.5, 3.5)
    c.part(a, FX["red"], FX["ol"])
    c.rim(a, FX["dred"], 1, 1)
    c.paint(pts((8, 2), (8, 3), (8, 4)), FX["brn"])
    leaf = pts((9, 2), (10, 2), (11, 2), (10, 3), (11, 3), (12, 3), (10, 1), (11, 1))
    c.part(leaf, FX["grn"], FX["ol"])
    c.paint(pts((5, 7), (5, 8), (6, 6)), FX["wht"])
    return c


def item_carrot():
    c = Canvas(16, 16)
    body = poly([(4, 5.5), (12, 5.5), (8.5, 15.5)]) | ellipse(8, 6.5, 4, 2)
    c.part(body, FX["org"], FX["ol"])
    c.paint(pts((6, 8), (7, 8), (9, 10), (10, 10), (7, 12)), FX["dorg"])
    c.paint(pts((6, 6), (6, 7)), FX["wht"])
    tops = pts((6, 1), (6, 2), (7, 3), (8, 0), (8, 1), (8, 2), (8, 3), (10, 1), (10, 2), (9, 3), (7, 4), (8, 4), (9, 4))
    c.part(tops, FX["grn"], FX["ol"])
    return c


def item_strawberry():
    c = Canvas(16, 16)
    body = ellipse(8, 8, 6, 4.5) | poly([(2.5, 8), (13.5, 8), (8, 15.5)])
    c.part(body, FX["red"], FX["ol"])
    c.rim(body, FX["dred"], 1, 1)
    for p in ((5, 8), (8, 9), (11, 8), (6, 11), (10, 11), (8, 13), (7, 6), (10, 6)):
        c.set(p[0], p[1], FX["yel"])
    cap = pts((4, 4), (5, 4), (6, 3), (7, 4), (8, 3), (9, 4), (10, 3), (11, 4), (12, 4), (8, 2), (8, 1))
    c.part(cap, FX["grn"], FX["ol"])
    return c


def star_shape(cx, cy, r_out, r_in, rot=-math.pi / 2):
    p = []
    for i in range(10):
        r = r_out if i % 2 == 0 else r_in
        a = rot + i * math.pi / 5
        p.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return poly(p)


def item_star():
    c = Canvas(16, 16)
    s = star_shape(8, 8.6, 7.6, 3.6)
    c.part(s, FX["yel"], FX["ol"])
    c.rim(s, FX["gold"], 1, 1)
    c.paint(pts((6, 8), (6, 9), (9, 8), (9, 9)), FX["ol"])
    c.set(5, 6, FX["wht"])
    return c


def sparkle(big):
    c = Canvas(16, 16)
    r = 5 if big else 3
    s = {(8, 8 + d) for d in range(-r, r)} | {(8 + d, 8) for d in range(-r, r)}
    s |= {(7, 7), (7, 8), (8, 7)} if big else set()
    c.part(s, FX["wht"], FX["yel"])
    return c


def confetti(shape, color):
    c = Canvas(16, 16)
    if shape == 0:
        m = rect(5, 6, 10, 9)
    else:
        m = pts((5, 9), (6, 8), (7, 7), (8, 7), (9, 8), (10, 9), (5, 10), (6, 9), (7, 8), (8, 8), (9, 9), (10, 10))
    c.paint(m, FX[color])
    c.paint({(x, y) for x, y in m if (x, y - 1) not in m}, FX["wht"])
    return c


def heart():
    c = Canvas(16, 16)
    h = ellipse(5.5, 6.5, 3.2, 3.2) | ellipse(10.5, 6.5, 3.2, 3.2) | poly([(2.3, 7.5), (13.7, 7.5), (8, 14)])
    c.part(h, FX["pink"], FX["ol"])
    c.paint(pts((4, 5), (5, 4)), FX["wht"])
    return c


def shadow():
    c = Canvas(16, 16)
    c.paint(ellipse(8, 12.5, 7, 2.2), FX["shadow"])
    return c


def burst():
    c = Canvas(32, 32)
    s = star_shape(16, 16, 15, 8, rot=0)
    s |= star_shape(16, 16, 12, 7, rot=math.pi / 5)
    c.part(s, FX["yel"], FX["org"])
    c.paint(ellipse(16, 16, 6, 6), FX["wht"])
    return c


# ---------------------------------------------------------------- OBJ sheet

class ObjSheet:
    def __init__(self):
        self.c = Canvas(128, 256)   # two 16x16-tile tables stacked
        self.next_large = 0
        self.small = []

    def place(self, cv, tx, ty):
        self.c.blit(cv, tx * 8, ty * 8)
        table, row = divmod(ty, 16)
        return table * 256 + row * 16 + tx

    def add_large(self, cv):
        i = self.next_large
        self.next_large += 1
        table, k = divmod(i, 16)
        tx, ty = (k % 4) * 4, table * 16 + (k // 4) * 4
        return self.place(cv, tx, ty)

    def add_small_area(self, start_row):
        self.small_free = [(tx, ty) for ty in range(start_row, 32, 2) for tx in range(0, 16, 2)]

    def add_small(self, cv):
        tx, ty = self.small_free.pop(0)
        return self.place(cv, tx, ty)

    def tiles(self):
        out = bytearray()
        for ty in range(32):
            for tx in range(16):
                out += tile4bpp(self.c.tile(tx, ty))
        return bytes(out)


# ---------------------------------------------------------------- background

class BG:
    """256x224 image of (palette << 4 | index) values."""

    def __init__(self):
        self.c = Canvas(256, 224)

    def tiles_and_map(self, tileset, rows=28, prio=False):
        m = [0] * (32 * 32)
        for ty in range(rows):
            for tx in range(32):
                raw = self.c.tile(tx, ty)
                if not any(raw):
                    continue
                pals = {v >> 4 for v in raw if v & 15}
                assert len(pals) == 1, f"tile {tx},{ty} mixes palettes {pals}"
                pal = pals.pop()
                pix = [v & 15 for v in raw]
                idx, flips = tileset.add(pix)
                m[ty * 32 + tx] = idx | (pal << 10) | flips | (0x2000 if prio else 0)
        return m


class TileSet:
    def __init__(self):
        self.tiles = [[0] * 64]
        self.index = {tuple([0] * 64): (0, 0)}

    def add(self, pix):
        key = tuple(pix)
        if key in self.index:
            return self.index[key]
        i = len(self.tiles)
        self.tiles.append(pix)
        rows = [pix[y * 8:(y + 1) * 8] for y in range(8)]
        variants = {
            0x0000: rows,
            0x4000: [r[::-1] for r in rows],
            0x8000: rows[::-1],
            0xC000: [r[::-1] for r in rows[::-1]],
        }
        # register flipped versions so later tiles can reuse this one
        for flag, rr in variants.items():
            k = tuple(v for r in rr for v in r)
            self.index.setdefault(k, (i, flag))
        return i, 0

    def blob(self):
        return b"".join(tile4bpp(t) for t in self.tiles)


def draw_sky(bg, rnd):
    c = bg.c
    for y in range(48):
        band = 1 if y < 14 else 2 if y < 28 else 3
        for x in range(256):
            c.set(x, y, band)
    for x in range(0, 256, 2):  # dithered band edges
        c.set(x, 14, 1)
        c.set(x + 1, 13, 2)
        c.set(x, 28, 2)
        c.set(x + 1, 27, 3)
    for _ in range(26):
        x, y = rnd.randrange(256), rnd.randrange(0, 34)
        band = c.get(x, y)
        if band in (1, 2, 3):
            c.set(x, y, band + 3)
            if rnd.random() < 0.3:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    if c.get(x + dx, y + dy) == band:
                        c.set(x + dx, y + dy, band + 3)
    # sun / moon
    sun = ellipse(228, 34, 9, 9)
    c.paint(dilate(sun, True), 10)
    c.paint(sun, 9)
    # clouds
    for cx, cy in ((40, 32), (120, 28), (176, 36)):
        cl = ellipse(cx, cy, 9, 5) | ellipse(cx - 9, cy + 2, 6, 4) | ellipse(cx + 9, cy + 2, 7, 4) | \
             ellipse(cx + 2, cy - 3, 6, 4)
        c.paint(cl, 7)
        c.paint({(x, y) for x, y in cl if (x, y + 2) not in cl}, 8)
    # hills
    for x in range(256):
        top = 38 + 3.5 * math.sin(x / 21.0) + 2 * math.sin(x / 7.3 + 1)
        for y in range(int(top), 48):
            c.set(x, y, 11 if y < 45 or (x + y) % 3 else 12)
    # trees on the hills
    for tx in (14, 70, 98, 150, 204, 246):
        top = 38 + 3.5 * math.sin(tx / 21.0) + 2 * math.sin(tx / 7.3 + 1)
        crown = ellipse(tx, top - 3, 5, 5.5) | ellipse(tx - 4, top, 4, 4) | ellipse(tx + 4, top, 4, 4)
        c.paint(rect(tx - 1, int(top), tx, int(top) + 6), 15)
        c.paint(crown, 13)
        c.paint({(x, y) for x, y in crown if (x + 1, y + 2) not in crown}, 14)
    for y in range(48):  # everything above is palette 0
        for x in range(256):
            c.set(x, y, c.get(x, y) & 15)


def draw_meadow(bg, rnd):
    c = bg.c
    P = 0x10
    for y in range(48, 176):
        for x in range(256):
            c.set(x, y, P | 1)
    occupied = []

    def free(x, y, r):
        for ox, oy, orad in occupied:
            if abs(ox - x) < r + orad and abs(oy - y) < r + orad:
                return False
        return True

    def spot(r, ymin=52, ymax=168):
        for _ in range(200):
            x, y = rnd.randrange(6, 250), rnd.randrange(ymin, ymax)
            if free(x, y, r):
                occupied.append((x, y, r))
                return x, y
        return None

    for _ in range(46):  # light streaks
        s = spot(3)
        if s:
            x, y = s
            for dx in range(rnd.randrange(3, 6)):
                c.set(x + dx, y, P | 2)
    for _ in range(44):  # tufts
        s = spot(4)
        if s:
            x, y = s
            for px, py in ((0, 0), (0, 1), (2, 1), (4, 0), (4, 1), (1, 2), (2, 2), (3, 2)):
                c.set(x + px, y + py, P | 3)
            c.set(x + 2, y, P | 2)
    colors = [5, 6, 7, 8, 10]
    for i in range(34):  # flowers
        s = spot(4)
        if s:
            x, y = s
            col = colors[i % len(colors)]
            for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
                c.set(x + dx, y + dy, P | col)
            c.set(x, y, P | (6 if col == 7 else 9))
            c.set(x + 1, y + 2, P | 11)
            c.set(x, y + 2, P | 11)
    for _ in range(4):  # pebbles
        s = spot(5)
        if s:
            x, y = s
            r = ellipse(x, y, 3, 2)
            c.paint(r, P | 12)
            c.paint({(a, b) for a, b in r if (a, b + 1) not in r}, P | 13)


CTRL_W, CTRL_H = 96, 40
HUD_Y = 178
HUD_X = (16, 144)


def draw_controller():
    c = Canvas(CTRL_W, CTRL_H)
    sh_l = rect(5, 1, 29, 8) | rect(4, 2, 30, 8)
    sh_r = mirror(sh_l, CTRL_W)
    c.part(sh_l, HUD["c3"], HUD["ol"])
    c.part(sh_r, HUD["c3"], HUD["ol"])
    body = ellipse(16, 22, 16.4, 16.4) | ellipse(79, 22, 16.4, 16.4) | rect(16, 8, 79, 36)
    c.part(body, HUD["c1"], HUD["ol"])
    c.rim(body, HUD["c2"], 0, 2)
    c.paint(ellipse(16, 22, 13, 13), HUD["c2"])
    cross = rect(12, 10, 19, 33) | rect(4, 18, 27, 25)
    c.part(cross, HUD["pad"], HUD["ol"])
    c.paint({(x, y) for x, y in cross if (x - 1, y - 1) not in cross}, HUD["padl"])
    c.paint(ellipse(79, 22, 15.4, 15.4), HUD["well"])
    for letter, (bx, by) in (("X", (79, 13)), ("A", (88, 22)), ("B", (79, 31)), ("Y", (70, 22))):
        dark = letter in "AB"
        b = ellipse(bx + 0.5, by + 0.5, 5.6, 5.6)
        c.part(b, HUD["pur"] if dark else HUD["lav"], HUD["ol"])
        c.rim(b, HUD["purd"] if dark else HUD["lavd"], 1, 1)
        c.paint(glyph(FONT3x5, letter, bx - 1, by - 2), HUD["wht"] if dark else HUD["ol"])
    for px in (40, 50):
        pill = rect(px, 25, px + 7, 28)
        c.part(pill, HUD["c3"], HUD["ol"])
    return c


def draw_hud(bg):
    c = bg.c
    P = 0x70
    for y in range(176, 224):
        for x in range(256):
            v = HUD["base"]
            if y == 176:
                v = HUD["ol"]
            elif y == 177:
                v = HUD["light"]
            elif y in (190, 206) and (x // 37) % 2 == 0:
                v = HUD["dark"]
            elif y == 198 and (x // 29) % 2 == 1:
                v = HUD["dark"]
            c.set(x, y, P | v)
    ctrl = draw_controller()
    for hx in HUD_X:
        for y in range(CTRL_H):
            for x in range(CTRL_W):
                v = ctrl.get(x, y)
                if v:
                    c.set(hx + x, HUD_Y + y, P | v)


def draw_title(bg):
    c = bg.c
    P = 0x40
    words = [("MEADOW", 30), ("FRIENDS", 60)]
    k = 0
    for word, y in words:
        adv = 19
        width = len(word) * adv - 4
        x0 = 128 - width // 2
        for i, ch in enumerate(word):
            g = glyph(FONT5x7, ch, x0 + i * adv, y, 3)
            col = 3 + (k % 6)
            k += 1
            c.paint(shift(dilate(g, True), 2, 2), P | 2)
            c.paint(dilate(g, True) - g, P | 1)
            c.paint(g, P | col)
            hi = {(x, yy) for x, yy in g if (x, yy - 3) not in g}
            c.paint(hi, P | (col + 6))


SLOT_COL0, SLOT_ROW = 1, 1


def slot_canvas(filled):
    c = Canvas(16, 16)
    c.paint(dilate(ellipse(8, 8, 6.6, 6.6)) - ellipse(8, 8, 6.6, 6.6), 1)
    c.paint(ellipse(8, 8, 6.6, 6.6), 2)
    s = star_shape(8, 8.5, 6.2, 2.9)
    if filled:
        c.paint(dilate(s) - s, 5)
        c.paint(s, 4)
        c.paint({(x, y) for x, y in s if (x - 1, y - 1) not in s}, 6)
    else:
        c.paint(s, 3)
    return c


def draw_progress(bg):
    c = bg.c
    P = 0x50
    sl = slot_canvas(False)
    for i in range(10):
        x = (SLOT_COL0 + 3 * i) * 8
        y = SLOT_ROW * 8
        for yy in range(16):
            for xx in range(16):
                v = sl.get(xx, yy)
                if v:
                    c.set(x + xx, y + yy, P | v)


# ---------------------------------------------------------------- main

def write(name, data):
    with open(os.path.join(OUT, name), "wb") as f:
        f.write(data)


def preview(canvas, pal_rows, name, scale=4):
    """pal_rows: dict palette-number -> list of 16 rgb; canvas values pal<<4|idx (or idx w/ pal 0)."""
    img = Image.new("RGB", (canvas.w, canvas.h), (40, 40, 48))
    px = img.load()
    for y in range(canvas.h):
        for x in range(canvas.w):
            v = canvas.get(x, y)
            if v & 15:
                px[x, y] = pal_rows[v >> 4][v & 15]
    img = img.resize((canvas.w * scale, canvas.h * scale), Image.NEAREST)
    img.save(os.path.join(OUT, name))


def main():
    rnd = random.Random(20261018)
    lines = ["; generated by tools/gen.py - do not edit", ""]

    # ---- OBJ graphics
    sheet = ObjSheet()
    animal_tiles = []
    for name in ANIMALS:
        for fr in animal_frames(name):
            animal_tiles.append(sheet.add_large(fr))
    balloon_tiles = [sheet.add_large(balloon(ch)) for ch in "ABXY"]
    burst_tile = sheet.add_large(burst())
    shoulder_tile = sheet.add_large(lit_shoulder())
    assert sheet.next_large <= 24
    sheet.add_small_area(16 + 8)
    item_tiles = [sheet.add_small(f()) for f in (item_apple, item_carrot, item_strawberry, item_star)]
    spark_tile = sheet.add_small(sparkle(True))
    spark2 = sheet.add_small(sparkle(False))
    assert spark2 == spark_tile + 2
    confetti_tiles = [sheet.add_small(confetti(s, col)) for col in ("red", "yel", "blue", "grn")
                      for s in (0, 1)]
    heart_tile = sheet.add_small(heart())
    shadow_tile = sheet.add_small(shadow())
    btn_tiles = {ch: sheet.add_small(lit_button(ch)) for ch in "ABXY"}
    up_tile = sheet.add_small(lit_dpad_up())
    right_tile = sheet.add_small(lit_dpad_right())
    pill_tile = sheet.add_small(lit_pill())
    icon_tiles = [sheet.add_small(icon(n)) for n in ANIMALS]
    write("obj_tiles.bin", sheet.tiles())

    obj_pals = [pal16(ANIMAL_PALS[a]) for a in ANIMALS] + [pal16(FX_PAL), pal16(BAL_PAL)]
    write("pal_obj.bin", b"".join(bgr555(c).to_bytes(2, "little") for p in obj_pals for c in p))

    # sheet preview with a palette per region
    prev = Canvas(128, 256)
    rows = {}
    for i in range(len(ANIMALS)):
        rows[i] = obj_pals[i]
    rows[6], rows[7] = obj_pals[6], obj_pals[7]
    for k in range(sheet.next_large):
        table, kk = divmod(k, 16)
        tx, ty = (kk % 4) * 4, table * 16 + (kk // 4) * 4
        pal = k // 3 if k < 18 else (6 if k == 22 else 7)
        for y in range(32):
            for x in range(32):
                v = sheet.c.get(tx * 8 + x, ty * 8 + y)
                if v:
                    prev.set(tx * 8 + x, ty * 8 + y, (pal << 4) | v)
    for y in range(192, 256):
        for x in range(128):
            v = sheet.c.get(x, y)
            if v:
                ti = ((y // 8 - 24) // 2) * 8 + x // 16
                pal = 6 if ti < 16 else 7 if ti < 23 else ti - 23
                prev.set(x, y, (pal << 4) | v)
    preview(prev, rows, "preview_obj.png", 4)

    # ---- BG graphics
    tileset = TileSet()
    bg1 = BG()
    draw_sky(bg1, rnd)
    draw_meadow(bg1, rnd)
    draw_hud(bg1)
    bg1_map = bg1.tiles_and_map(tileset)
    title = BG()
    draw_title(title)
    title_map = title.tiles_and_map(tileset, prio=True)
    prog = BG()
    draw_progress(prog)
    prog_map = prog.tiles_and_map(tileset, prio=True)
    filled = slot_canvas(True)
    star_tiles = []
    for ty in range(2):
        for tx in range(2):
            star_tiles.append(tileset.add(filled.tile(tx, ty))[0])
    empty_tiles = [prog_map[SLOT_ROW * 32 + SLOT_COL0] & 0x3FF, prog_map[SLOT_ROW * 32 + SLOT_COL0 + 1] & 0x3FF,
                   prog_map[(SLOT_ROW + 1) * 32 + SLOT_COL0] & 0x3FF, prog_map[(SLOT_ROW + 1) * 32 + SLOT_COL0 + 1] & 0x3FF]
    assert len(tileset.tiles) <= 1024, len(tileset.tiles)
    write("bg_tiles.bin", tileset.blob())
    pack = lambda m: b"".join(v.to_bytes(2, "little") for v in m)
    write("bg1_map.bin", pack(bg1_map))
    write("bg2_title.bin", pack(title_map))
    write("bg2_play.bin", pack(prog_map))

    bg_sets = []
    for tod in TOD_ORDER:
        pals = [pal16(SKY_TOD[tod]), pal16(GRASS_TOD[tod]), pal16([]), pal16([]),
                pal16(TITLE_PAL), pal16(SLOT_PAL), pal16([]), pal16(HUD_PAL)]
        pals[0][0] = rgb(SKY_TOD[tod][0])
        bg_sets.append(b"".join(bgr555(c).to_bytes(2, "little") for p in pals for c in p))
    write("pal_bg.bin", b"".join(bg_sets))

    # full-screen preview (day) with title text over it
    day = {0: pal16(SKY_TOD["day"]), 1: pal16(GRASS_TOD["day"]), 4: pal16(TITLE_PAL),
           5: pal16(SLOT_PAL), 7: pal16(HUD_PAL)}
    comp = Canvas(256, 224)
    comp.blit(bg1.c, 0, 0)
    comp.blit(title.c, 0, 0)
    preview(comp, day, "preview_title.png", 3)
    comp2 = Canvas(256, 224)
    comp2.blit(bg1.c, 0, 0)
    comp2.blit(prog.c, 0, 0)
    for i, tod in enumerate(TOD_ORDER):
        pr = dict(day)
        pr[0], pr[1] = pal16(SKY_TOD[tod]), pal16(GRASS_TOD[tod])
        preview(comp2, pr, f"preview_play_{tod}.png", 2)

    # ---- sound
    spc_img = spc.build()
    write("spc.bin", spc_img)

    # ---- assets.inc
    def const(name, v):
        lines.append(f"{name} = ${v:04X}")

    const("SPC_SIZE", len(spc_img))
    const("BG_TILES_SIZE", len(tileset.tiles) * 32)
    const("NUM_ANIMALS", len(ANIMALS))
    const("BURST_TILE", burst_tile)
    const("SPARK_TILE", spark_tile)
    const("HEART_TILE", heart_tile)
    const("SHADOW_TILE", shadow_tile)
    const("SLOT_COL0", SLOT_COL0)
    const("SLOT_ROW", SLOT_ROW)
    const("HUD_Y", HUD_Y)
    const("HUD_X1", HUD_X[0])
    const("HUD_X2", HUD_X[1])
    lines.append("")
    lines.append('.segment "RODATA"')
    lines.append("animal_tiles: .word " + ", ".join(f"${t:03X}" for t in animal_tiles))
    lines.append("balloon_tiles: .word " + ", ".join(f"${t:03X}" for t in balloon_tiles))
    lines.append("item_tiles: .word " + ", ".join(f"${t:03X}" for t in item_tiles))
    # eight confetti pieces, then a star and a heart that only the party rain uses
    rain = confetti_tiles + [item_tiles[3], heart_tile]
    lines.append("confetti_tiles: .word " + ", ".join(f"${t:03X}" for t in rain))
    lines.append("icon_tiles: .word " + ", ".join(f"${t:03X}" for t in icon_tiles))
    lines.append("star_slot_tiles: .word " + ", ".join(f"${t:03X}" for t in star_tiles))
    lines.append("empty_slot_tiles: .word " + ", ".join(f"${t:03X}" for t in empty_tiles))

    # HUD highlight elements: button mask, dx, dy, tile, attr (flips), size
    # SNES pad word: B Y Sel St Up Dn Lt Rt | A X L R 0 0 0 0
    M = {"B": 0x8000, "Y": 0x4000, "SELECT": 0x2000, "START": 0x1000, "UP": 0x0800, "DOWN": 0x0400,
         "LEFT": 0x0200, "RIGHT": 0x0100, "A": 0x0080, "X": 0x0040, "L": 0x0020, "R": 0x0010}
    elems = [
        ("A", 88 - 7, 22 - 7, btn_tiles["A"], 0, 0),
        ("B", 79 - 7, 31 - 7, btn_tiles["B"], 0, 0),
        ("X", 79 - 7, 13 - 7, btn_tiles["X"], 0, 0),
        ("Y", 70 - 7, 22 - 7, btn_tiles["Y"], 0, 0),
        ("UP", 16 - 8, 22 - 14, up_tile, 0, 0),
        ("DOWN", 16 - 8, 22 - 2, up_tile, 0x80, 0),
        ("RIGHT", 16 - 2, 22 - 8, right_tile, 0, 0),
        ("LEFT", 16 - 14, 22 - 8, right_tile, 0x40, 0),
        ("SELECT", 40 - 4, 25 - 6, pill_tile, 0, 0),
        ("START", 50 - 4, 25 - 6, pill_tile, 0, 0),
        ("L", 3, 0, shoulder_tile, 0, 2),
        ("R", 61, 0, shoulder_tile, 0x40, 2),
    ]
    lines.append("hud_elems:")
    for name, dx, dy, tile, flips, size in elems:
        lines.append(f"  .word ${M[name]:04X}")
        lines.append(f"  .byte {dx}, {dy}")
        lines.append(f"  .word ${tile:03X}")
        lines.append(f"  .byte ${flips:02X}, {size}")
    lines.append(f"NUM_HUD_ELEMS = {len(elems)}")

    with open(os.path.join(OUT, "assets.inc"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"bg tiles: {len(tileset.tiles)}  spc: {len(spc_img)} bytes  large sprites: {sheet.next_large}")


if __name__ == "__main__":
    main()
