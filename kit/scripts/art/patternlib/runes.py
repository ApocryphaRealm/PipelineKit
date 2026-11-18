"""patternlib.runes - a rune band from our own stroke font of the Elder Futhark (drawn for this library: straight
staves and branches in a box 0.6 wide, 1.0 tall; nobody's font file). A band is a text laid along a straight or curved
centre line between two incised border lines; each rune is a set of incised strokes (role 'rune'), words parted by a
pair of dots. Text is in transliteration: f u th a r k g w h n i j ei p z s t b e m l ng d o, words split by spaces."""
import math
import numpy as np
from . import geom
from .model import Strand

FONT = {
    "f": [[(0, 0), (0, 1)], [(0, 0.55), (0.5, 0.82)], [(0, 0.78), (0.42, 1.0)]],
    "u": [[(0, 0), (0, 1), (0.5, 0.72), (0.5, 0)]],
    "th": [[(0, 0), (0, 1)], [(0, 0.74), (0.42, 0.5), (0, 0.26)]],
    "a": [[(0, 0), (0, 1)], [(0, 1.0), (0.45, 0.76)], [(0, 0.74), (0.45, 0.5)]],
    "r": [[(0, 0), (0, 1), (0.45, 0.78), (0, 0.55), (0.45, 0)]],
    "k": [[(0.45, 1.0), (0, 0.5), (0.45, 0)]],
    "g": [[(0, 1), (0.55, 0)], [(0, 0), (0.55, 1)]],
    "w": [[(0, 0), (0, 1), (0.42, 0.8), (0, 0.6)]],
    "h": [[(0, 0), (0, 1)], [(0.5, 0), (0.5, 1)], [(0, 0.66), (0.5, 0.34)]],
    "n": [[(0.25, 0), (0.25, 1)], [(0, 0.66), (0.5, 0.34)]],
    "i": [[(0, 0), (0, 1)]],
    "j": [[(0.28, 0.98), (0, 0.72), (0.28, 0.46)], [(0.3, 0.54), (0.58, 0.28), (0.3, 0.02)]],
    "ei": [[(0.25, 0), (0.25, 1)], [(0.25, 1), (0.52, 0.8)], [(0.25, 0), (-0.02, 0.2)]],
    "p": [[(0.45, 1.0), (0, 0.78), (0, 0.22), (0.45, 0)], [(0, 0.78), (0.4, 0.58)], [(0, 0.22), (0.4, 0.42)]],
    "z": [[(0.3, 0), (0.3, 1)], [(0.3, 0.6), (0, 0.95)], [(0.3, 0.6), (0.6, 0.95)]],
    "s": [[(0.45, 1.0), (0.05, 0.66), (0.45, 0.34), (0.05, 0)]],
    "t": [[(0.3, 0), (0.3, 1)], [(0, 0.7), (0.3, 1), (0.6, 0.7)]],
    "b": [[(0, 0), (0, 1), (0.45, 0.78), (0, 0.5), (0.45, 0.22), (0, 0)]],
    "e": [[(0, 0), (0, 1), (0.3, 0.66), (0.6, 1), (0.6, 0)]],
    "m": [[(0, 0), (0, 1), (0.6, 0.45)], [(0.6, 0), (0.6, 1), (0, 0.45)]],
    "l": [[(0, 0), (0, 1), (0.45, 0.74)]],
    "ng": [[(0.3, 0.12), (0.6, 0.5), (0.3, 0.88), (0, 0.5), (0.3, 0.12)]],
    "d": [[(0, 0), (0, 1), (0.6, 0), (0.6, 1), (0, 0)]],
    "o": [[(0, 0), (0.6, 0.62), (0.3, 0.95), (0, 0.62), (0.6, 0)]],
}
DIGRAPHS = ("th", "ng", "ei")


def tokens(text):
    out = []; words = text.lower().split()
    for wi, w in enumerate(words):
        i = 0
        while i < len(w):
            d = w[i:i + 2]
            if d in DIGRAPHS: out.append(d); i += 2
            elif w[i] in FONT: out.append(w[i]); i += 1
            else: raise KeyError("no rune for %r in %r" % (w[i], text))
        if wi < len(words) - 1: out.append(":")
    return out


def band(C, text, height, stroke, spacing=0.35, border=True, step=None, closed=False):
    """C: the band's centre line. height: the band's inner height (runes are 1.0 tall in font units -> height - 2 x
    stroke). Returns the rune strokes and the border lines [(pts, width, closed)]."""
    step = step or min(0.02, stroke / 6.0)
    Q = geom.resample(np.asarray(C, float), step, closed); s = geom.arclen(Q); N = geom.normals_left(Q, closed); T = geom.tangents(Q, closed)
    hgt = height - 2.2 * stroke; sc = hgt; tk = tokens(text); adv = []
    for t in tk: adv.append(0.18 * sc if t == ":" else (max(x for st in FONT[t] for x, _ in st) - min(x for st in FONT[t] for x, _ in st)) * sc)
    total = sum(adv) + spacing * sc * (len(tk) - 1); start = max(0.0, (s[-1] - total) / 2.0)
    def place(u, v):                      # u along (world), v across from the centre line
        i = int(np.clip(np.searchsorted(s, u), 1, len(s) - 1)); f = (u - s[i - 1]) / max(s[i] - s[i - 1], 1e-12)
        p = Q[i - 1] + (Q[i] - Q[i - 1]) * f; n = N[i - 1]; return p + n * v
    strokes = []; u = start
    for t, a in zip(tk, adv):
        if t == ":":
            for v in (0.28 * sc, -0.28 * sc):
                p = place(u + a / 2, v); d = T[int(np.clip(np.searchsorted(s, u), 0, len(T) - 1))] * stroke * 0.25
                strokes.append(Strand(np.array([p - d, p + d]), stroke, False, "rune", "terminal", "dot"))
        else:
            x0 = min(x for st in FONT[t] for x, _ in st)
            for st in FONT[t]:
                P = np.array([place(u + (x - x0) * sc, (y - 0.5) * sc) for x, y in st])
                strokes.append(Strand(geom.resample(P, step, False) if len(P) > 1 else P, stroke, False, "rune", "terminal", t))
        u += a + spacing * sc
    lines = []
    if border:
        for sg in (1, -1):
            lines.append((Q + N * sg * (height / 2.0), stroke * 0.8, closed))
    return strokes, lines, total
