#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Render the GitHub social preview card for AI Video Studio (1280x640)."""
import os
import sys
from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 640
BG = (10, 10, 11)            # #0a0a0b  - the repo's badge labelColor
INDIGO = (99, 102, 241)      # #6366f1  - the repo's accent
INDIGO_DIM = (79, 82, 200)
WHITE = (255, 255, 255)
GREY = (161, 161, 170)       # zinc-400
GREY_DIM = (113, 113, 122)   # zinc-500
GREEN = (34, 197, 94)        # #22c55e - the MIT badge colour

FONTDIR = r"C:\Windows\Fonts"


def font(names, size):
    """First available font from `names`, else PIL's default."""
    for n in names:
        p = os.path.join(FONTDIR, n)
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


BOLD = ["segoeuib.ttf", "arialbd.ttf", "calibrib.ttf"]
SEMI = ["seguisb.ttf", "segoeuib.ttf", "arialbd.ttf"]
REG = ["segoeui.ttf", "arial.ttf", "calibri.ttf"]
MONO = ["consola.ttf", "cour.ttf", "arial.ttf"]

f_eyebrow = font(SEMI, 25)
f_title = font(BOLD, 100)
f_sub = font(REG, 38)
f_sub2 = font(REG, 30)
f_chip = font(SEMI, 23)
f_cap = font(REG, 21)
f_url = font(MONO, 25)

img = Image.new("RGB", (W, H), BG)


# ---------------------------------------------------------------- glow
def glow(center, radius, colour, strength):
    """Soft radial wash.

    PIL's radial_gradient is 0 at the centre and 255 at the edge. A linear
    inversion leaves a small but non-zero alpha along the paste box border,
    which shows up as a hard rectangular seam against a near-black
    background. Raising the falloff to a power drives alpha to exactly 0
    at the boundary, so the box edge is invisible.
    """
    size = radius * 2
    g = Image.radial_gradient("L").resize((size, size), Image.BICUBIC)

    lut = []
    for v in range(256):
        t = 1.0 - (v / 255.0)                 # 1 at centre -> 0 at edge
        lut.append(0 if t <= 0 else int(255 * strength * (t ** 2.2)))
    g = g.point(lut)

    layer = Image.new("RGB", (size, size), colour)
    img.paste(layer, (center[0] - radius, center[1] - radius), g)


glow((1060, 210), 520, INDIGO, 0.42)
glow((140, 590), 420, INDIGO_DIM, 0.20)

d = ImageDraw.Draw(img, "RGBA")

# Top accent rule
d.rectangle([0, 0, W, 5], fill=INDIGO)


# ------------------------------------------------- right-hand video motif
def frame(cx, cy, w, h, border, fill, width=3, radius=12):
    d.rounded_rectangle([cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2],
                        radius=radius, fill=fill, outline=border, width=width)


FW, FH = 300, 169                      # 16:9
CX, CY = 1086, 300
# stacked frames behind, suggesting a render queue
frame(CX + 22, CY - 22, FW, FH, (99, 102, 241, 45), (18, 18, 22, 170), 2)
frame(CX + 11, CY - 11, FW, FH, (99, 102, 241, 85), (16, 16, 20, 215), 2)
# front frame
frame(CX, CY, FW, FH, (99, 102, 241, 240), (13, 13, 17, 255), 3)

# play triangle (polygon, not a glyph - no font fallback to go wrong)
s = 38
d.polygon([(CX - s // 2 + 3, CY - s), (CX - s // 2 + 3, CY + s), (CX + s, CY)],
          fill=(99, 102, 241, 255))

# render progress bar under the frame
bx0, bx1, by = CX - FW // 2, CX + FW // 2, CY + FH // 2 + 34
d.rounded_rectangle([bx0, by, bx1, by + 8], radius=4, fill=(39, 39, 45, 255))
d.rounded_rectangle([bx0, by, bx0 + int((bx1 - bx0) * 0.68), by + 8],
                    radius=4, fill=INDIGO)
d.text((bx0, by + 20), "rendering  \u00b7  scene 6 of 8", font=f_cap, fill=GREY_DIM)


# ----------------------------------------------------------- left column
def tracked(xy, text, fnt, fill, track):
    """Draw text with extra letter-spacing."""
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=fnt, fill=fill)
        x += d.textlength(ch, font=fnt) + track
    return x


X = 84

# eyebrow, with a green rule echoing the MIT badge
ey = 96
d.rounded_rectangle([X, ey + 6, X + 5, ey + 26], radius=2, fill=GREEN)
tracked((X + 22, ey), "OPEN SOURCE  \u00b7  MIT  \u00b7  NO API KEYS",
        f_eyebrow, INDIGO, 1.6)

# title
d.text((X - 4, 142), "AI Video Studio", font=f_title, fill=WHITE)

# subtitle
d.text((X, 272), "Local AI video generator", font=f_sub, fill=INDIGO)
d.text((X, 326), "A text script becomes a narrated, subtitled,", font=f_sub2, fill=GREY)
d.text((X, 364), "colour-graded MP4 \u2014 entirely on your own GPU.",
       font=f_sub2, fill=GREY)

# model chips
chips = ["Wan2.1", "Gemma", "Kokoro TTS", "Whisper", "MusicGen", "FFmpeg"]
cx, cy = X, 444
for c in chips:
    w = int(d.textlength(c, font=f_chip)) + 30
    if cx + w > 910:                      # wrap before the video motif column
        cx, cy = X, cy + 46
    d.rounded_rectangle([cx, cy, cx + w, cy + 38], radius=19,
                        fill=(24, 24, 29, 255), outline=(63, 63, 72, 255), width=1)
    d.text((cx + 15, cy + 7), c, font=f_chip, fill=GREY)
    cx += w + 10

# footer
d.rectangle([X, 560, X + 560, 561], fill=(39, 39, 45))
d.text((X, 580), "github.com/06pratyush/ai-video-pipeline", font=f_url, fill=GREY_DIM)

out = sys.argv[1]
img.save(out, "PNG", optimize=True)

# ---- report geometry so collisions are checked, not eyeballed -------------
tw = d.textlength("AI Video Studio", font=f_title)
title_right = X - 4 + tw
motif_left = CX - FW // 2
print("wrote %s  %dx%d  %.0f KB" % (out, img.width, img.height,
                                    os.path.getsize(out) / 1024.0))
print("title right edge : %.0f" % title_right)
print("motif left edge  : %d" % motif_left)
print("horizontal gap   : %.0f px %s" % (motif_left - title_right,
                                         "OK" if motif_left - title_right > 20
                                         else "** COLLISION **"))
