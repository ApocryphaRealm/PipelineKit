"""patternlib.knot - knotwork and weave by the tile / mirror-curve method (Mercat's tile grid, Cromwell's construction,
Gerdes' mirror curves).

The construction: a set of grid cells, each `cell` world units square. The strands run on the diagonals through the
MIDPOINTS of the cell edges. At an edge with an in-cell on both sides and no break, two strands cross (straight on);
at an edge on the boundary of the cell set, or at an internal BREAK, the strand turns back (a mirror) in a smooth
U-turn parallel to that edge. So by construction every strand is a closed loop (nothing ends, nothing is cut off at a
frame), every crossing is a clean right angle, and the crossings can be given an alternating over-under (crossings.py).

    no breaks                 -> the plait / the owner's bold diagonal over-under WEAVE, turning back at the frame
    breaks (preset or seeded) -> Celtic / Norse knot panels

Fitted to a Region (any outline, discs cut out): the cells are those whose centre lies inside the region by a
clearance; every boundary turn is then pushed out along its edge normal until the strand's outer edge sits `frame_gap`
from the region's edge, its tangent turned to follow the edge - so the loops trace the outline instead of a staircase.
"""
import math
import numpy as np
INSIDE = 0.16            # a cell joins when its centre lies clearance + INSIDE x cell inside: frame turns then move -0.5..+0.5 cell
LAST_PUSH = []           # the push of every boundary turn of the last curves() call (world units), for the stretch score
from . import geom
from .model import Strand


def _adj(e):
    k, i, j = e
    return ((i, j - 1), (i, j)) if k == "h" else ((i - 1, j), (i, j))


def _mid(e):
    k, i, j = e
    return (i + 0.5, float(j)) if k == "h" else (float(i), j + 0.5)


def _node_at(x, y):
    if abs(y - round(y)) < 1e-6: return ("h", int(math.floor(x)), int(round(y)))
    return ("v", int(round(x)), int(math.floor(y)))


def trace(cells, breaks=()):
    """The mirror curves of a cell set: a list of loops, each a list of passes (node, d_out, is_mirror)."""
    cells = set(cells); breaks = set(breaks); nodes = {}
    for (i, j) in cells:
        for e in (("h", i, j), ("h", i, j + 1), ("v", i, j), ("v", i + 1, j)):
            if e in nodes: continue
            a, b = _adj(e); n = (a in cells) + (b in cells)
            nodes[e] = "mirror" if (n == 1 or e in breaks) else "cross"
    seen = set(); loops = []

    def key(e, d, mirror): return (e, "m") if mirror else (e, d[0] * d[1])

    for e in sorted(nodes):
        starts = []
        if nodes[e] == "cross": starts = [(1, 1), (1, -1)]
        else:
            a, b = _adj(e)
            if e[0] == "h": starts = [(1, 1 if b in cells else -1)]
            else: starts = [(1 if b in cells else -1, 1)]
        for d0 in starts:
            mir = nodes[e] == "mirror"
            if key(e, d0, mir) in seen: continue
            loop = []; cur, d = e, d0; guard = 0
            while True:
                m = nodes[cur] == "mirror"; seen.add(key(cur, d, m)); loop.append((cur, d, m))
                x, y = _mid(cur); nx, ny = x + 0.5 * d[0], y + 0.5 * d[1]; nxt = _node_at(nx, ny)
                if nxt not in nodes: raise RuntimeError("mirror curve left the cell set at %s" % (nxt,))
                if nodes[nxt] == "mirror": d = (d[0], -d[1]) if nxt[0] == "h" else (-d[0], d[1])
                cur = nxt; guard += 1
                if key(cur, d, nodes[cur] == "mirror") == key(e, d0, mir): break
                if guard > 4 * len(nodes) + 8: raise RuntimeError("mirror curve did not close")
            loops.append(loop)
    return loops, nodes


class Grid:
    """grid -> world: world = origin + R(rot) . (g * cell)"""

    def __init__(self, cell, origin=(0.0, 0.0), rot=0.0):
        self.cell = float(cell); self.o = np.asarray(origin, float); c, s = math.cos(rot), math.sin(rot)
        self.R = np.array([[c, -s], [s, c]])

    def w(self, g): return self.o + (np.asarray(g, float) * self.cell) @ self.R.T

    def g(self, w): return ((np.asarray(w, float) - self.o) @ self.R) / self.cell

    def dir(self, d): v = np.asarray(d, float) @ self.R.T; return v / np.linalg.norm(v, axis=-1, keepdims=True)


def curves(cells, breaks, grid, width, role="weave", bounce=0.16, region=None, clearance=None, step=None, tension=1.0, gap=0.08):
    """The strands of a cell set. region + clearance: boundary turns pushed out to `clearance` from the region's edge.
    At an internal break the two facing U-turns stand back from the break line by half a width plus the gap each, so
    they never touch."""
    loops, nodes = trace(cells, breaks); step = step or min(0.03, width / 8.0); out = []; LAST_PUSH.clear()
    bounce_break = max(bounce, (width / 2.0 + gap * 0.75) / grid.cell)
    cells = set(cells)
    for loop in loops:
        P, T = [], []
        for (e, d, m) in loop:
            x, y = _mid(e)
            if not m:
                P.append(grid.w((x, y))); T.append(grid.dir(d)); continue
            n_in = np.array([0.0, d[1]]) if e[0] == "h" else np.array([d[0], 0.0])
            t_par = np.array([d[0], 0.0]) if e[0] == "h" else np.array([0.0, d[1]])
            a, b = _adj(e); boundary = (a in cells) != (b in cells)
            p0 = grid.w(np.array([x, y]) + (bounce if boundary else bounce_break) * n_in); tw = grid.dir(t_par)
            if region is not None and boundary:
                nw = grid.dir(n_in); c = grid.cell
                f = lambda t: float(region.sdf(p0 - t * nw)[0]) - clearance
                lo, hi = -0.6 * c, 1.2 * c
                if f(lo) <= 0: t = lo
                elif f(hi) >= 0: t = hi
                else:
                    for _ in range(40):
                        mid = 0.5 * (lo + hi)
                        if f(mid) > 0: lo = mid
                        else: hi = mid
                    t = 0.5 * (lo + hi)
                LAST_PUSH.append(t); p0 = p0 - t * nw; gr = region.grad(p0)[0]; tt = np.array([-gr[1], gr[0]])
                tw = tt if np.dot(tt, tw) >= 0 else -tt
            P.append(p0); T.append(tw)
        C = geom.hermite_chain(np.array(P), np.array(T), True, step, tension)
        out.append(Strand(C, width, True, role, "closed"))
    return out


# ---------------------------------------------------------------- rectangular panels and break presets
def rect_cells(cols, rows):
    return {(i, j) for i in range(cols) for j in range(rows)}


def _internal_edges(cells):
    E = set()
    for (i, j) in cells:
        for e in (("h", i, j), ("v", i, j)):
            a, b = _adj(e)
            if a in cells and b in cells: E.add(e)
    return sorted(E)


def _sym_images(e, cols, rows, symmetry):
    k, i, j = e; out = {e}
    if symmetry in ("mirror-x", "mirror-xy", "rot2"):
        pass
    imgs = [e]
    if symmetry in ("mirror-x", "mirror-xy"): imgs.append((k, cols - 1 - i, j) if k == "h" else (k, cols - i, j))
    if symmetry in ("mirror-y", "mirror-xy"): imgs += [(kk, ii, rows - jj) if kk == "h" else (kk, ii, rows - 1 - jj) for (kk, ii, jj) in list(imgs)]
    if symmetry == "rot2": imgs.append((k, cols - 1 - i, rows - j) if k == "h" else (k, cols - i, rows - 1 - j))
    out.update(imgs); return out


def breaks_preset(cols, rows, preset, seed=0, p=0.22, symmetry=None):
    """Break sets for a cols x rows panel: 'plait' (none), 'cross' (a centre cross of alternate breaks, the four-panel
    knot), 'rings' (breaks round a ring one cell in, so an inner and an outer knot interlace), 'random' (each internal
    edge a break with probability p from a seeded generator, made symmetric under `symmetry`)."""
    cells = rect_cells(cols, rows); E = _internal_edges(cells)
    if preset == "plait": return set()
    if preset == "cross":
        B = set(); mc, mr = cols // 2, rows // 2
        for j in range(rows):
            if j % 2 == 0 and cols % 2 == 0: B.add(("v", mc, j))
        for i in range(cols):
            if i % 2 == 0 and rows % 2 == 0: B.add(("h", i, mr))
        return B
    if preset == "rings":
        B = set()
        for i in range(1, cols - 1):
            if i % 2 == 1: B.add(("h", i, 1)); B.add(("h", i, rows - 1))
        for j in range(1, rows - 1):
            if j % 2 == 1: B.add(("v", 1, j)); B.add(("v", cols - 1, j))
        return B
    if preset == "random":
        rng = np.random.default_rng(seed); B = set()
        for e in E:
            if rng.random() < p:
                for im in _sym_images(e, cols, rows, symmetry):
                    if im in E: B.add(im)
        return B
    raise KeyError(preset)


def region_cells(region, grid, clearance, inside=INSIDE):
    """The cells of `grid` whose centre lies at least clearance + inside x cell within the region."""
    lo, hi = region.bbox(); corners = np.array([[lo[0], lo[1]], [lo[0], hi[1]], [hi[0], lo[1]], [hi[0], hi[1]]])
    G = grid.g(corners); g0 = np.floor(G.min(0)).astype(int) - 1; g1 = np.ceil(G.max(0)).astype(int) + 1
    ii, jj = np.meshgrid(np.arange(g0[0], g1[0]), np.arange(g0[1], g1[1]), indexing="ij")
    C = np.stack([ii.ravel() + 0.5, jj.ravel() + 0.5], -1); s = region.sdf(grid.w(C))
    ok = s >= clearance + inside * grid.cell
    return {(int(a), int(b)) for a, b in zip(ii.ravel()[ok], jj.ravel()[ok])}


def _prune(cells):
    """Drop cells joined to the rest by a corner only or sticking out alone (a lone cell makes a tiny closed loop):
    keep cells with at least two in-set side neighbours, repeat; then keep the largest 4-connected piece."""
    cells = set(cells)
    for _ in range(50):
        drop = {c for c in cells if sum(((c[0] + a, c[1] + b) in cells) for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))) < 2}
        if not drop: break
        cells -= drop
    pieces = []; left = set(cells)
    while left:
        st = [min(left)]; comp = set()
        while st:
            c = st.pop()
            if c in comp or c not in left: continue
            comp.add(c)
            st += [(c[0] + a, c[1] + b) for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))]
        left -= comp; pieces.append(comp)
    pieces.sort(key=lambda p: (-len(p), min(p)))
    return pieces


def fill_region(region, cell, width, frame_gap, origin=None, rot=0.0, breaks=(), role="weave", bounce=0.16, inside=INSIDE, all_pieces=True, gap=0.08):
    """Fill a Region with a weave (no breaks) or knot field. origin: a grid point (default the region's in-centre, so a
    symmetric region gets a symmetric field). Returns (strands, cells, grid)."""
    if origin is None: origin, _ = geom.max_inscribed(region, res=cell / 8.0)
    grid = Grid(cell, origin, rot); clearance = width / 2.0 + frame_gap
    cells = region_cells(region, grid, clearance, inside); pieces = _prune(cells)
    keep = set().union(*pieces) if (pieces and all_pieces) else (pieces[0] if pieces else set())
    if not keep: return [], set(), grid
    br = {e for e in breaks if all(c in keep for c in _adj(e))}
    return curves(keep, br, grid, width, role, bounce, region, clearance, gap=gap), keep, grid


def knot_panel(cols, rows, cell, width, preset="random", seed=0, symmetry=None, origin=(0.0, 0.0), p=0.22, bounce=0.16):
    """A rectangular knot panel, its lower left corner at origin; returns (strands, breaks)."""
    cells = rect_cells(cols, rows); B = breaks_preset(cols, rows, preset, seed, p, symmetry)
    return curves(cells, B, Grid(cell, origin), width, "knot" if B else "weave", bounce), B
