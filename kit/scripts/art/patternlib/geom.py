"""patternlib.geom - plane geometry in world units (y up). Everything is deterministic: no random numbers, fixed
sampling steps, stable sort orders.

Polygons are (N, 2) float arrays, open (the last point is not a repeat of the first), counter-clockwise after
`ccw()`. A Region is an outer polygon minus round holes (medallion discs) and minus polygon holes, and answers a
signed distance (positive inside) - the one function every fitting step and every validator measures against."""
import math
import numpy as np
from matplotlib.path import Path
from scipy.spatial import cKDTree

STEP = 0.02          # the dense sampling step (world units) used for distance queries; error <= STEP / 2


def area(P):
    P = np.asarray(P, float); x, y = P[:, 0], P[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def ccw(P):
    P = np.asarray(P, float)
    return P if area(P) >= 0 else P[::-1].copy()


def length(P, closed=False):
    P = np.asarray(P, float); Q = np.vstack([P, P[:1]]) if closed else P
    return float(np.linalg.norm(np.diff(Q, axis=0), axis=1).sum())


def resample(P, step, closed=False):
    """Points every `step` along the polyline (closed: the loop, last point not repeated). Keeps the start point."""
    P = np.asarray(P, float); Q = np.vstack([P, P[:1]]) if closed else P
    seg = np.linalg.norm(np.diff(Q, axis=0), axis=1); s = np.concatenate([[0.0], np.cumsum(seg)]); L = s[-1]
    if L <= 0: return P[:1].copy()
    n = max(2, int(math.ceil(L / step)))
    t = np.linspace(0.0, L, n + (0 if closed else 1), endpoint=not closed)
    return np.stack([np.interp(t, s, Q[:, 0]), np.interp(t, s, Q[:, 1])], -1)


def arclen(P, closed=False):
    P = np.asarray(P, float); d = np.linalg.norm(np.diff(P, axis=0), axis=1)
    return np.concatenate([[0.0], np.cumsum(d)])


def smooth_closed(P, radius, step=None):
    """Moving-average smoothing of a closed loop over +-radius of arc (rounds corners to about that radius)."""
    step = step or STEP * 2; Q = resample(P, step, closed=True); n = max(1, int(round(radius / step)))
    k = np.ones(2 * n + 1) / (2 * n + 1)
    return np.stack([np.convolve(np.concatenate([Q[-n:, i], Q[:, i], Q[:n, i]]), k, mode="valid") for i in range(2)], -1)


def tangents(P, closed=False):
    P = np.asarray(P, float)
    if closed: T = np.roll(P, -1, 0) - np.roll(P, 1, 0)
    else: T = np.gradient(P, axis=0)
    n = np.linalg.norm(T, axis=1, keepdims=True); return T / np.maximum(n, 1e-12)


def normals_left(P, closed=False):
    T = tangents(P, closed); return np.stack([-T[:, 1], T[:, 0]], -1)


def simplify(P, tol=0.002):
    """Douglas-Peucker on a closed loop (for the inside test only: few vertices, same shape to tol)."""
    from skimage.measure import approximate_polygon
    P = np.asarray(P, float); Q = approximate_polygon(np.vstack([P, P[:1]]), tol)
    return Q[:-1] if len(Q) > 3 else P


def inside(Q, P):
    Q = np.asarray(Q, float).reshape(-1, 2); P = np.asarray(P, float); out = np.zeros(len(Q), bool)
    lo, hi = P.min(0), P.max(0); bb = (Q[:, 0] >= lo[0]) & (Q[:, 0] <= hi[0]) & (Q[:, 1] >= lo[1]) & (Q[:, 1] <= hi[1])
    if bb.any(): out[bb] = Path(P).contains_points(Q[bb], radius=0.0)
    return out


def poly_dist(Q, P, closed=True):
    """Unsigned distance from points Q to the polyline P (dense-sample KD-tree; exact to STEP / 2)."""
    D = resample(P, STEP, closed=closed); d, _ = cKDTree(D).query(np.asarray(Q, float).reshape(-1, 2)); return d


def clip_halfplane(P, n, c):
    """Sutherland-Hodgman: keep the part of polygon P where dot(n, p) >= c."""
    P = np.asarray(P, float); out = []; L = len(P)
    for i in range(L):
        a, b = P[i], P[(i + 1) % L]; fa, fb = float(np.dot(n, a) - c), float(np.dot(n, b) - c)
        if fa >= 0: out.append(a)
        if (fa >= 0) != (fb >= 0):
            t = fa / (fa - fb); out.append(a + (b - a) * t)
    return np.array(out) if len(out) >= 3 else np.zeros((0, 2))


def hermite_chain(pts, tans, closed, step, tension=1.0):
    """A C1 curve through pts with unit tangent directions tans (cubic Hermite, tangent length = chord x tension),
    sampled every `step`. Closed chains end where they start (last point not repeated)."""
    pts = np.asarray(pts, float); tans = np.asarray(tans, float); n = len(pts); out = []
    rng_ = range(n) if closed else range(n - 1)
    for i in rng_:
        a, b = pts[i], pts[(i + 1) % n]; ta, tb = tans[i], tans[(i + 1) % n]; ch = float(np.linalg.norm(b - a))
        m = max(2, int(math.ceil(ch * 1.6 / step))); t = np.linspace(0, 1, m, endpoint=False)[:, None]
        h00, h10, h01, h11 = 2 * t ** 3 - 3 * t ** 2 + 1, t ** 3 - 2 * t ** 2 + t, -2 * t ** 3 + 3 * t ** 2, t ** 3 - t ** 2
        out.append(h00 * a + h10 * ta * ch * tension + h01 * b + h11 * tb * ch * tension)
    if not closed: out.append(pts[-1:])
    C = np.vstack(out)
    return resample(C, step, closed=closed)


class Region:
    """outer polygon minus discs (cx, cy, r) minus polygon holes. sdf(Q) > 0 inside, = distance to the nearest edge."""

    def __init__(self, outer, discs=(), holes=()):
        self.outer = ccw(outer); self.discs = [tuple(map(float, d)) for d in discs]; self.holes = [ccw(h) for h in holes]
        self._tree = cKDTree(resample(self.outer, STEP, closed=True))
        self._htrees = [cKDTree(resample(h, STEP, closed=True)) for h in self.holes]
        self._outer_s = simplify(self.outer); self._holes_s = [simplify(h) for h in self.holes]

    def sdf(self, Q):
        Q = np.asarray(Q, float).reshape(-1, 2); d, _ = self._tree.query(Q)
        s = np.where(inside(Q, self._outer_s), d, -d)
        for (cx, cy, r) in self.discs:
            s = np.minimum(s, np.hypot(Q[:, 0] - cx, Q[:, 1] - cy) - r)
        for h, t in zip(self._holes_s, self._htrees):
            dh, _ = t.query(Q); s = np.minimum(s, np.where(inside(Q, h), -dh, dh))
        return s

    def grad(self, Q, e=1e-3):
        Q = np.asarray(Q, float).reshape(-1, 2)
        gx = (self.sdf(Q + [e, 0]) - self.sdf(Q - [e, 0])) / (2 * e); gy = (self.sdf(Q + [0, e]) - self.sdf(Q - [0, e])) / (2 * e)
        g = np.stack([gx, gy], -1); return g / np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-12)

    def bbox(self):
        return self.outer.min(0), self.outer.max(0)

    def area(self):
        return area(self.outer) - sum(math.pi * r * r for _, _, r in self.discs) - sum(area(h) for h in self.holes)


def offset_polygon(P, d, res=None):
    """True inward offset of polygon P by d (> 0 inward, < 0 outward): the d-level set of the exact distance to P,
    traced at a fine grid (res, default d / 40, at most 0.02) and resampled. Returns the pieces, largest first (an
    inset can split a face in two)."""
    from skimage import measure
    P = ccw(P); res = res or min(0.02, max(abs(d) / 25.0, 0.008))
    lo, hi = P.min(0) - max(0.0, -d) - 4 * res, P.max(0) + max(0.0, -d) + 4 * res
    xs = np.arange(lo[0], hi[0] + res, res); ys = np.arange(lo[1], hi[1] + res, res)
    G = np.stack(np.meshgrid(xs, ys), -1).reshape(-1, 2)
    R = Region(P); S = R.sdf(G).reshape(len(ys), len(xs))
    pieces = []
    for c in measure.find_contours(S, d):
        if len(c) < 8: continue
        W = np.stack([lo[0] + c[:, 1] * res, lo[1] + c[:, 0] * res], -1)
        if np.linalg.norm(W[0] - W[-1]) > 3 * res: continue                    # open contour: touches the grid edge
        W = ccw(W[:-1]); pieces.append(resample(W, STEP * 2, closed=True))
    pieces.sort(key=lambda w: -abs(area(w)))
    return pieces


def max_inscribed(region, res=0.05):
    """The point of the region farthest from its edges (the in-circle centre) and that distance."""
    lo, hi = region.bbox(); xs = np.arange(lo[0], hi[0], res); ys = np.arange(lo[1], hi[1], res)
    G = np.stack(np.meshgrid(xs, ys), -1).reshape(-1, 2); s = region.sdf(G); i = int(np.argmax(s))
    return G[i], float(s[i])
