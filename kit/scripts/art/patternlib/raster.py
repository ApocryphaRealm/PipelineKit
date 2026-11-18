"""patternlib.raster - a vector Pattern to height / normal / masks at ANY pixel density. Nothing in the vector model
depends on the texture size; this is the only place pixels appear.

A Frame maps world (x, y) to pixel (col, row): [col, row] = M . [x, y, 1] (2 x 3). Frame.fit(lo, hi, ppu) is the usual
upright frame (y up in the world = rows going up the image). Heights in world units: 0 = flush steel, -depth = the
carved floor, strand tops just below 0 with a rounded profile. At a crossing the under pass is cut back by `gap` round
the over pass and dips a little as it goes under."""
import math
import numpy as np
from scipy.spatial import cKDTree
from . import geom


def smooth01(x):
    x = np.clip(x, 0, 1); return x * x * (3 - 2 * x)


def strand_top(r, depth, crown=0.27):
    """rounded strand top: -0.03 depth on the crown (strictly below flush, as measure.fragments reads strands) down to
    -0.30 depth at the edge"""
    return -depth * (0.03 + crown * (1 - np.sqrt(np.clip(1 - np.clip(r, 0, 1) ** 2, 0, 1))))


class Frame:
    def __init__(self, M, W, H):
        self.M = np.asarray(M, float); self.W, self.H = int(W), int(H)
        A = self.M[:, :2]; self.Ainv = np.linalg.inv(A); self.ppu = float(math.sqrt(abs(np.linalg.det(A))))

    @staticmethod
    def fit(lo, hi, ppu, pad=0.4):
        lo = np.asarray(lo, float) - pad; hi = np.asarray(hi, float) + pad
        W = int(math.ceil((hi[0] - lo[0]) * ppu)); H = int(math.ceil((hi[1] - lo[1]) * ppu))
        return Frame([[ppu, 0, -lo[0] * ppu], [0, -ppu, hi[1] * ppu]], W, H)

    def world(self):
        cc, rr = np.meshgrid(np.arange(self.W) + 0.5, np.arange(self.H) + 0.5)
        P = np.stack([cc - self.M[0, 2], rr - self.M[1, 2]], -1) @ self.Ainv.T; return P

    def to_px(self, P):
        P = np.asarray(P, float); return P @ self.M[:, :2].T + self.M[:, 2]


def render(pat, frame, gap=None, groove_depth=0.6, dip=0.15, close_eyes=None):
    """-> dict(H, face, inset, strand, ring, floor, ppu) for the pattern in the frame."""
    ppu = frame.ppu; D = pat.depth; W = frame.world(); Hh, Ww = frame.H, frame.W; Q = W.reshape(-1, 2)
    gap = pat.params.get("gap", 0.08) if gap is None else gap
    face = geom.inside(Q, pat.outline).reshape(Hh, Ww) if pat.outline is not None else np.ones((Hh, Ww), bool)
    inset = np.zeros((Hh, Ww), bool)
    for P in pat.inset: inset |= geom.inside(Q, P).reshape(Hh, Ww)
    H = np.zeros((Hh, Ww), np.float32); FL = np.zeros((Hh, Ww), np.float32); RING = np.zeros((Hh, Ww), bool)
    for P in pat.floors:
        s = geom.Region(P).sdf(Q).reshape(Hh, Ww); c = smooth01(s * ppu + 0.5); FL = np.maximum(FL, c)
    for (cx, cy, r, rw) in pat.discs:
        rr = np.hypot(W[..., 0] - cx, W[..., 1] - cy)
        FL = np.where(rr < r + rw, smooth01((r - rr) * ppu + 0.5), FL); RING |= (rr >= r) & (rr < r + rw)
    H = (-D * FL).astype(np.float32)
    # ---- strands (not runes): nearest strand sample per pixel
    st = [k for k, s in enumerate(pat.strands) if s.role != "rune"]; STR = np.zeros((Hh, Ww), np.float32)
    if st:
        S = np.vstack([pat.strands[k].pts for k in st]); HW = np.concatenate([pat.strands[k].hw for k in st])
        tree = cKDTree(S); d, j = tree.query(Q, distance_upper_bound=float(HW.max()) + 2.0 / ppu)
        ok = np.isfinite(d); jj = np.where(ok, j, 0); hw = HW[jj]; dd = np.where(ok, d, 1e9)
        cov = (smooth01((hw - dd) * ppu + 0.5) * ok).reshape(Hh, Ww); top = strand_top(dd / hw, D).reshape(Hh, Ww)
        H = (H * (1 - cov) + top * cov).astype(np.float32); STR = cov.astype(np.float32)
        # ---- crossings: the over pass on top, the under pass cut back by `gap` and dipping. Each pixel is redrawn by its
        #      NEAREST crossing only - a neighbour's window must not fill this crossing's cut back in
        CT = cKDTree(np.array([c.p for c in pat.crossings])) if pat.crossings else None
        for ci, c in enumerate(pat.crossings):
            so, io = c.over; su, iu = c.under; O, U = pat.strands[so], pat.strands[su]
            hwo, hwu = float(O.hw[io]), float(U.hw[iu]); Rc = 1.6 * (hwo + gap) + hwu + 2.0 / ppu
            def local(s, i):
                n = len(s.pts); k = int(math.ceil(2.5 * Rc / max(float(np.median(np.linalg.norm(np.diff(s.pts[:50], axis=0), axis=1))), 1e-4)))
                idx = [(i + t) % n for t in range(-k, k + 1)] if s.closed else list(range(max(0, i - k), min(n, i + k + 1)))
                return s.pts[idx], s.hw[idx]
            Po, ho = local(O, io); Pu, hu = local(U, iu)
            pc = frame.to_px(c.p); r0 = int(max(0, math.floor(pc[1] - Rc * ppu - 2))); r1 = int(min(Hh, math.ceil(pc[1] + Rc * ppu + 3)))
            c0 = int(max(0, math.floor(pc[0] - Rc * ppu - 2))); c1 = int(min(Ww, math.ceil(pc[0] + Rc * ppu + 3)))
            if r1 <= r0 or c1 <= c0: continue
            Wl = W[r0:r1, c0:c1].reshape(-1, 2)
            dO, jo = cKDTree(Po).query(Wl); dU, ju = cKDTree(Pu).query(Wl); hwO = ho[jo]; hwU = hu[ju]
            near = (np.hypot(Wl[:, 0] - c.p[0], Wl[:, 1] - c.p[1]) < Rc) & (CT.query(Wl)[1] == ci)
            base = -D * FL[r0:r1, c0:c1].reshape(-1)
            covU = smooth01((hwU - dU) * ppu + 0.5); covO = smooth01((hwO - dO) * ppu + 0.5)
            dc = np.hypot(Wl[:, 0] - c.p[0], Wl[:, 1] - c.p[1])
            topU = strand_top(dU / hwU, D) - dip * D * np.exp(-(dc / (hwo + gap)) ** 2)
            cut = smooth01((dO - hwO - gap) * ppu + 0.5)
            Hu = base + (topU - base) * covU * cut
            Ho = Hu + (strand_top(dO / hwO, D) - Hu) * covO
            sel = near & ((dU < hwU + 1.5 / ppu) | (dO < hwO + 1.5 / ppu))
            blk = H[r0:r1, c0:c1].reshape(-1); blk[sel] = Ho[sel]; H[r0:r1, c0:c1] = blk.reshape(r1 - r0, c1 - c0)
            sb = STR[r0:r1, c0:c1].reshape(-1); sb[sel] = np.maximum(covO, covU * cut)[sel]; STR[r0:r1, c0:c1] = sb.reshape(r1 - r0, c1 - c0)
        # ---- clip: field strands (weave, knot, braid) stay inside the inset and outside every medallion (they run on
        #      under the frame groove and under the ring); a symbol stays inside its disc
        GRP = np.array([1 if pat.strands[k].role == "symbol" else 0 for k in st for _ in range(len(pat.strands[k].pts))])[jj].reshape(Hh, Ww)
        if pat.inset:                                      # field strands end at the frame groove's inner edge, so the floor
            from scipy import ndimage                       # beside every strand end runs on along the groove (no pockets)
            gw_ = max([g[1] for g in pat.grooves if g[2]] + [0.0])
            allow0 = ndimage.distance_transform_edt(inset) / ppu >= 0.5 * gw_
        else: allow0 = np.ones((Hh, Ww), bool)
        allow1 = np.zeros((Hh, Ww), bool) if pat.discs else np.ones((Hh, Ww), bool)
        for (cx, cy, r, rw) in pat.discs:
            rr = np.hypot(W[..., 0] - cx, W[..., 1] - cy); allow0 &= rr >= r + rw; allow1 |= rr < r
        bad = (STR > 0) & ~np.where(GRP == 1, allow1, allow0)
        H = np.where(bad, -D * FL, H).astype(np.float32); STR = np.where(bad, 0.0, STR).astype(np.float32)
    # ---- a loop's eye too small to carve (a floor island under measure.MIN_POCKET, closed in by strands) is closed:
    #      raised to the strand edge, so it reads as part of the strand round it, never as a speck of black
    if close_eyes is None: close_eyes = any(s.closed and s.role in ("weave", "knot") for s in pat.strands)   # loop eyes: bounce / knot fields only
    if close_eyes and st:
        from scipy import ndimage
        from . import measure
        fl = face & (H <= -0.5 * D); lab, n = ndimage.label(fl)
        if n:
            a = ndimage.sum(fl, lab, range(1, n + 1)) / ppu / ppu; small = np.zeros(n + 1, bool); small[1:] = a < measure.MIN_POCKET * 1.05
            # only an eye ENCLOSED by strands: none of its rim is flush steel or off the face (a pocket against the frame
            # is a real fragment and stays for the validator to count)
            flush_rim = ndimage.binary_dilation((H > -0.01 * D) | ~face, iterations=2) & fl
            small[np.unique(lab[flush_rim])] = False; small[0] = False
            eye = small[lab] & fl; H = np.where(eye, -0.30 * D, H).astype(np.float32); STR = np.where(eye, 0.6, STR).astype(np.float32)
    # ---- incised grooves (frame lines) and rune strokes
    for (P, w, closed) in pat.grooves:
        d = geom.poly_dist(Q, P, closed).reshape(Hh, Ww); g = -groove_depth * D * smooth01((w / 2 - d) * ppu + 0.5)       # flat floor, one-pixel edges: never a strand-height rim
        H = np.minimum(H, g.astype(np.float32))
    for s in pat.strands:
        if s.role != "rune": continue
        d = geom.poly_dist(Q, s.pts, False).reshape(Hh, Ww); hw = float(np.median(s.hw))
        g = -D * 0.8 * smooth01((hw - d) * ppu + 0.5) * (1 - 0.5 * np.clip(d / hw, 0, 1) ** 2); H = np.minimum(H, g.astype(np.float32))
    H = np.where(face, H, 0.0).astype(np.float32)
    return dict(H=H, face=face, inset=inset, strand=STR * face, ring=RING & face, floor=FL * face, ppu=ppu, depth=D)


def normals(H, ppu):
    """(n_dx, n_gl) in 0..1, the set's convention (tn_knot.maps): GL green = + dH / d row."""
    gx = np.zeros_like(H); gy = np.zeros_like(H); gx[:, 1:-1] = (H[:, 2:] - H[:, :-2]) / 2 * ppu; gy[1:-1] = (H[2:] - H[:-2]) / 2 * ppu
    n = np.stack([-gx, gy, np.ones_like(gx)], -1); n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return (n * np.array([1, -1, 1], np.float32)) * 0.5 + 0.5, n * 0.5 + 0.5


def shade(R, light=(-0.45, 0.55, 0.70)):
    """A quick lit preview (RGB 0..1) for sheets: dark floors, bright polished strand tops and rings, mid steel."""
    H, ppu, D = R["H"], R["ppu"], R["depth"]; _, ngl = normals(H, ppu); n = ngl * 2 - 1
    L = np.asarray(light, float); L /= np.linalg.norm(L); lam = np.clip((n * np.array([L[0], L[1], L[2]])).sum(-1), 0, 1)
    floor = smooth01(-H / D * 1.3 - 0.15); top = np.clip(R["strand"], 0, 1)
    alb = 0.42 + 0.30 * top * (1 - floor) + 0.30 * R["ring"]; alb = alb * (1 - floor) + 0.05 * floor
    v = alb * (0.35 + 0.75 * lam); v = np.where(R["face"], v, 0.16)
    return np.clip(np.stack([v * 0.98, v, v * 1.03], -1), 0, 1)


def height_png(R):
    return np.clip(R["H"] / R["depth"] + 1, 0, 1)
