"""patternlib.braid - n-strand plaits along a curve: a closed perimeter braid round an inset outline, or an open
straight (or evenly tapering) run along a long narrow field.

Strand k sits at the lateral offset a_k(s) = A(s) * sin(2 pi s / pitch + 2 pi k / n) from the centre line, A(s) =
band half width - strand half width, so every strand stays inside the band. n = 2 is the two-strand twist, n = 3 the
three-strand plait (adjacent lanes swap alternately top and bottom - the hair braid). Crossings and the alternating
over-under come from crossings.py; on a closed loop the number of pitches is a whole number so every strand closes on
itself."""
import math
import numpy as np
from . import geom
from .model import Strand


def along(C, closed, n, band_hw, width, pitch, phase=0.0, step=None, smooth=None, role="braid"):
    """C: the centre line (world). band_hw: a number or one value per point of C (a taper). Returns the strands and
    the resampled centre line with its band half widths (for the run metrics)."""
    step = step or min(0.03, width / 8.0)
    if closed and smooth: C = geom.smooth_closed(C, smooth)
    C0 = np.asarray(C, float); s0 = geom.arclen(np.vstack([C0, C0[:1]]) if closed else C0)
    hw0 = np.asarray(band_hw, float)
    Q = geom.resample(C0, step, closed); sq = geom.arclen(np.vstack([Q, Q[:1]]) if closed else Q)[:len(Q)]
    if hw0.ndim == 0: hw = np.full(len(Q), float(hw0))
    else:
        hw0 = np.concatenate([hw0, hw0[:1]]) if closed else hw0
        hw = np.interp(sq / max(sq[-1] if not closed else s0[-1], 1e-9) * s0[-1], s0, hw0)
    L = geom.length(Q, closed)
    if closed: pitch = L / max(1, int(round(L / pitch)))
    N = geom.normals_left(Q, closed); A = np.maximum(hw - width / 2.0, 0.0); out = []
    for k in range(n):
        th = 2 * math.pi * sq / pitch + 2 * math.pi * k / n + phase
        a = A * np.sin(th); P = Q + N * a[:, None]
        out.append(Strand(P, width, closed, role, "closed" if closed else "border", name="braid%d" % k))
    return out, Q, hw, pitch
