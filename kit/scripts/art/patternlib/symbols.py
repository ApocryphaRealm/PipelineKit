"""patternlib.symbols - the Norse centrepieces as exact constructions, each fitted to a radius R (the strand's outer
edge stays inside R) about a centre c. Crossings and the alternating over-under come from crossings.py.

  triquetra : the trefoil curve x = sin t + 2 sin 2t, y = cos t - 2 cos 2t (one continuous strand through three lobes,
              three self-crossings), turned ONE LOBE UP (the weapon-engraving skill: two lobes up read as a skull);
              circle=True adds the interlaced ring through the lobes
  valknut   : three equilateral triangles, corners rounded by a fillet, each translated off the centre toward one
              corner of a downward triangle, so the three interlock (Borromean)
  horns     : Odin's triple horn - three open arcs (horns) widening from tip to mouth, turned 120 degrees apart and
              interlocked at the centre; the tips and mouths are terminal ends
The medallion (dark filled disc in a polished ring, the set's standard) is not a strand: fit.py adds it to the
pattern's discs and the symbol is sized inside it."""
import math
import numpy as np
from . import geom
from .model import Strand


def _rot(P, a):
    c, s = math.cos(a), math.sin(a); return P @ np.array([[c, s], [-s, c]])


def triquetra(c, R, width, circle=False, step=None, rot=0.0):
    step = step or min(0.02, width / 8.0)
    t = np.linspace(0, 2 * math.pi, 6000, endpoint=False)
    U = np.stack([np.sin(t) + 2 * np.sin(2 * t), np.cos(t) - 2 * np.cos(2 * t)], -1) * -1.0      # one lobe up
    sc = (R - width / 2.0) / float(np.linalg.norm(U, axis=1).max())
    P = _rot(U * sc, rot) + np.asarray(c, float)
    out = [Strand(geom.resample(P, step, True), width, True, "symbol", "closed", "triquetra")]
    if circle:
        rc = 0.60 * (R - width / 2.0); a = np.linspace(0, 2 * math.pi, 2000, endpoint=False)
        Cc = np.stack([np.cos(a), np.sin(a)], -1) * rc + np.asarray(c, float)
        out.append(Strand(geom.resample(Cc, step, True), width * 0.85, True, "symbol", "closed", "triquetra-ring"))
    return out


def valknut(c, R, width, offset=0.36, fillet=None, step=None, rot=0.0):
    """offset: each triangle's shift off the centre as a share of its circumradius."""
    step = step or min(0.02, width / 8.0); fillet = width * 0.9 if fillet is None else fillet
    # size: circumradius rt so the whole figure (shift + rt + half width) fits R
    rt = (R - width / 2.0) / (1.0 + offset); out = []
    for k in range(3):
        sh = offset * rt * np.array([math.cos(math.radians(-90 + 120 * k)), math.sin(math.radians(-90 + 120 * k))])
        V = np.array([[math.cos(math.radians(90 + 120 * j)), math.sin(math.radians(90 + 120 * j))] for j in range(3)]) * rt + sh
        T = geom.smooth_closed(V, fillet, step=step / 2)
        P = _rot(T, rot) + np.asarray(c, float)
        out.append(Strand(geom.resample(P, step, True), width, True, "symbol", "closed", "valknut%d" % k))
    return out


def horns(c, R, width, step=None, rot=0.0, sweep=230.0, ring=0.42, rad=0.50, tip_w=0.55):
    """Three horns: horn k is an arc of radius rad*R' about a centre ring*R' from c at angle 90 + 120k, swept `sweep`
    degrees; width grows from tip_w x width at the tip to width at the mouth."""
    step = step or min(0.02, width / 8.0); Rp = R - width / 2.0; out = []
    for k in range(3):
        phi = math.radians(90 + 120 * k); q = ring * Rp * np.array([math.cos(phi), math.sin(phi)])
        a0 = phi + math.radians(180 - sweep / 2.0); a = np.linspace(a0, a0 + math.radians(sweep), 1200)
        P = q + rad * Rp * np.stack([np.cos(a), np.sin(a)], -1)
        P = geom.resample(_rot(P, rot) + np.asarray(c, float), step, False)
        w = np.linspace(tip_w * width, width, len(P))
        out.append(Strand(P, w, False, "symbol", "terminal", "horn%d" % k))
    # keep the whole figure inside R: scale about c if any strand edge pokes out
    ext = max(float((np.linalg.norm(s.pts - np.asarray(c, float), axis=1) + s.width / 2).max()) for s in out)
    if ext > R:
        f = (R - width / 2.0) / (ext - width / 2.0)
        for s in out: s.pts = np.asarray(c, float) + (s.pts - np.asarray(c, float)) * f
    return out


SYMBOLS = {"triquetra": triquetra, "valknut": valknut, "horns": horns,
           "triquetra-ring": lambda c, R, w, **k: triquetra(c, R, w, circle=True, **k)}
