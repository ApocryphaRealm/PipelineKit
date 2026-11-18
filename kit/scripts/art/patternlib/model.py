"""patternlib.model - the VECTOR pattern: strands (centre lines with widths), crossings (which pass is over), incised
grooves, medallion discs, the region it was fitted to. Saved as JSON (floats rounded to 1e-5, so the same inputs give the
same bytes) and as SVG (strand outlines, the under pass broken at each crossing - what a person reads)."""
import json, math
import numpy as np

ROLES = ("weave", "knot", "braid", "symbol", "rune", "ring")
ENDS = ("closed", "border", "terminal")


class Strand:
    def __init__(self, pts, width, closed, role, ends=None, name=""):
        self.pts = np.asarray(pts, float); self.closed = bool(closed); self.role = role
        w = np.asarray(width, float); self.width = np.full(len(self.pts), float(w)) if w.ndim == 0 else w
        self.ends = ends or ("closed" if closed else "border"); self.name = name
        assert role in ROLES, role; assert self.ends in ENDS, self.ends

    @property
    def hw(self): return self.width * 0.5

    def to_dict(self):
        return dict(name=self.name, role=self.role, closed=self.closed, ends=self.ends,
                    pts=np.round(self.pts, 5).tolist(), width=np.round(self.width, 5).tolist())

    @staticmethod
    def from_dict(d):
        return Strand(d["pts"], d["width"], d["closed"], d["role"], d["ends"], d.get("name", ""))


class Crossing:
    """A point where two passes meet: (strand, sample index) for the pass on top and the pass underneath."""

    def __init__(self, p, over, under):
        self.p = np.asarray(p, float); self.over = (int(over[0]), int(over[1])); self.under = (int(under[0]), int(under[1]))

    def to_dict(self): return dict(p=np.round(self.p, 5).tolist(), over=list(self.over), under=list(self.under))

    @staticmethod
    def from_dict(d): return Crossing(d["p"], d["over"], d["under"])


class Pattern:
    """kind: the pattern type; params + seed: everything it was generated from; region: the face outline, the inset
    (carving limit) and the field(s); strands, crossings; grooves [(pts, width, closed)]; discs [(cx, cy, r_disc,
    ring_w)] - a dark filled disc of r_disc inside a flush polished ring ring_w wide (the set's medallion);
    floors [polygon]: carved ground (dark floor) between strands; symmetry: 'mirror-x' | 'mirror-y' | 'rot3' | None
    (asked for, checked by the symmetry validator); depth: the carving depth (world units)."""

    def __init__(self, kind, params=None, seed=0):
        self.kind = kind; self.params = dict(params or {}); self.seed = int(seed)
        self.outline = None; self.inset = []; self.strands = []; self.crossings = []; self.grooves = []
        self.discs = []; self.floors = []; self.symmetry = None; self.depth = 0.095; self.conflicts = 0
        self.layout = None; self.damascus = None; self.meta = {}

    def add(self, *strands):
        for s in strands: self.strands.append(s)
        return self

    def bbox(self):
        pts = [s.pts for s in self.strands] + [g[0] for g in self.grooves]
        if self.outline is not None: pts.append(self.outline)
        for (cx, cy, r, rw) in self.discs: pts.append(np.array([[cx - r - rw, cy - r - rw], [cx + r + rw, cy + r + rw]]))
        A = np.vstack(pts); return A.min(0), A.max(0)

    def to_dict(self):
        r = lambda a: None if a is None else np.round(np.asarray(a, float), 5).tolist()
        return dict(patternlib=1, kind=self.kind, params=self.params, seed=self.seed, depth=self.depth, symmetry=self.symmetry,
                    outline=r(self.outline), inset=[r(p) for p in self.inset], floors=[r(p) for p in self.floors],
                    grooves=[dict(pts=r(g[0]), width=round(float(g[1]), 5), closed=bool(g[2])) for g in self.grooves],
                    discs=[[round(float(v), 5) for v in d] for d in self.discs], layout=self.layout, damascus=self.damascus,
                    strands=[s.to_dict() for s in self.strands], crossings=[c.to_dict() for c in self.crossings],
                    conflicts=self.conflicts, meta=self.meta)

    def to_json(self, path):
        with open(path, "w", newline="\n") as f: json.dump(self.to_dict(), f, separators=(",", ":"), sort_keys=True)

    @staticmethod
    def from_dict(d):
        p = Pattern(d["kind"], d.get("params"), d.get("seed", 0)); a = lambda v: None if v is None else np.asarray(v, float)
        p.depth = d.get("depth", 0.095); p.symmetry = d.get("symmetry"); p.outline = a(d.get("outline"))
        p.inset = [a(v) for v in d.get("inset", [])]; p.floors = [a(v) for v in d.get("floors", [])]
        p.grooves = [(a(g["pts"]), g["width"], g["closed"]) for g in d.get("grooves", [])]
        p.discs = [tuple(v) for v in d.get("discs", [])]; p.layout = d.get("layout"); p.damascus = d.get("damascus")
        p.strands = [Strand.from_dict(s) for s in d.get("strands", [])]; p.crossings = [Crossing.from_dict(c) for c in d.get("crossings", [])]
        p.conflicts = d.get("conflicts", 0); p.meta = d.get("meta", {}); return p

    @staticmethod
    def from_json(path):
        return Pattern.from_dict(json.load(open(path)))

    # ---- SVG: the outline, the inset, grooves, discs, every strand as a filled ribbon; the under pass is cut at each
    #      crossing by drawing the over pass again on top with a background-coloured halo (the gap)
    def to_svg(self, path, px_per_unit=40.0, gap=None):
        lo, hi = self.bbox(); pad = 0.5; W = (hi[0] - lo[0] + 2 * pad) * px_per_unit; H = (hi[1] - lo[1] + 2 * pad) * px_per_unit
        X = lambda p: "%.2f,%.2f" % ((p[0] - lo[0] + pad) * px_per_unit, (hi[1] - p[1] + pad) * px_per_unit)
        out = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %.1f %.1f">' % (W, H, W, H),
               '<rect width="100%" height="100%" fill="#1b1c1f"/>']
        poly = lambda P, closed: ("M " + " L ".join(X(p) for p in P) + (" Z" if closed else ""))
        if self.outline is not None: out.append('<path d="%s" fill="#55585e" stroke="none"/>' % poly(self.outline, True))
        for P in self.floors: out.append('<path d="%s" fill="#0d0d0f" stroke="none"/>' % poly(P, True))
        for P in self.inset: out.append('<path d="%s" fill="none" stroke="#e0b040" stroke-width="1" stroke-dasharray="4 3"/>' % poly(P, True))
        for (P, w, c) in self.grooves: out.append('<path d="%s" fill="none" stroke="#0d0d0f" stroke-width="%.2f"/>' % (poly(P, c), w * px_per_unit))
        for (cx, cy, r, rw) in self.discs:
            out.append('<circle cx="%s" cy="%s" r="%.2f" fill="#c8cbd0"/>' % (*X((cx, cy)).split(","), (r + rw) * px_per_unit))
            out.append('<circle cx="%s" cy="%s" r="%.2f" fill="#0d0d0f"/>' % (*X((cx, cy)).split(","), r * px_per_unit))
        g = self.params.get("gap", 0.08) if gap is None else gap

        def ribbon(s, i0=None, i1=None, halo=0.0, fill="#c8cbd0"):
            P = s.pts if i0 is None else s.pts[i0:i1]; w = float(np.median(s.width)) + 2 * halo
            if len(P) < 2: return ""
            return '<path d="%s" fill="none" stroke="%s" stroke-width="%.2f" stroke-linejoin="round" stroke-linecap="%s"/>' % (
                poly(P, s.closed and i0 is None), fill, w * px_per_unit, "butt" if s.role != "rune" else "round")
        for s in self.strands:
            out.append(ribbon(s, fill="#0d0d0f" if s.role == "rune" else "#c8cbd0"))
        for c in self.crossings:
            s = self.strands[c.over[0]]; n = len(s.pts); i = c.over[1]; k = max(3, int(round((float(s.width[i]) * 2.0 + g) / 0.02)))
            idx = [(i + j) % n for j in range(-k, k + 1)] if s.closed else list(range(max(0, i - k), min(n, i + k + 1)))
            sub = Strand(s.pts[idx], s.width[idx], False, s.role)
            out.append(ribbon(sub, halo=g, fill="#0d0d0f")); out.append(ribbon(sub))
        out.append("</svg>")
        with open(path, "w", newline="\n") as f: f.write("\n".join(o for o in out if o))
