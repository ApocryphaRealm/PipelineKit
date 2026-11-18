"""patternlib.weave - the owner's bold diagonal over-under WEAVE in its approved form (the warhammer weave, the
weapon-engraving skill's "outline + weave"): two families of straight strands at +-45 degrees crossing at right
angles, alternating over-under like a basket, running on UNDER the frame groove (and under a medallion's ring) at the
field's edge.

What made the old painted weave fail (stubs, slivers, corner pieces - library entries 14080, 14775 and the bow v5
plate) is the piece of strand between the frame and the first crossing: at an unlucky grid phase it is a sliver. Here
the strands are vectors, so that END PIECE is measured exactly: end_pieces() gives every strand end's visible length
(frame to the first cut) and the corner pieces (strands that cross nothing), and fit.py searches the grid phase in a
fixed order for the layout whose shortest end piece is longest. The plait whose strands turn back at the frame
instead is knot.fill_region (weave_mode 'bounce')."""
import math
import numpy as np
from . import geom
from .model import Strand


def lines(region, pitch, width, phase=(0.0, 0.0), rot=0.0, step=None, mirror_axis=None):
    """Strands of the two diagonal families clipped to the region (region.sdf >= 0). pitch: the distance between
    neighbouring parallel strands. phase: the families' offsets as fractions of the pitch. mirror_axis: x of a mirror
    axis - family B is then the mirror image of family A, so the weave is symmetric about it."""
    step = step or min(0.03, width / 8.0); lo, hi = region.bbox(); c = (lo + hi) / 2.0; R = float(np.linalg.norm(hi - lo)) / 2.0 + pitch
    ca, sa = math.cos(math.pi / 4 + rot), math.sin(math.pi / 4 + rot)
    dA = np.array([ca, sa]); dB = np.array([-sa, ca])                     # the two strand directions (perpendicular)
    ref = np.array([mirror_axis, c[1]]) if mirror_axis is not None else c
    out = []
    fams = [(dA, phase[0]), (dB, (-phase[0] if mirror_axis is not None else phase[1]))]
    for fi, (d, ph) in enumerate(fams):
        n = np.array([-d[1], d[0]]); kmax = int(math.ceil(R / pitch)) + 1
        for k in range(-kmax, kmax + 1):
            off = (k + ph) * pitch; base = ref + n * off + (c - ref) @ d * d
            t = np.arange(-R, R + step, step); P = base[None] + t[:, None] * d[None]
            s = region.sdf(P); inn = s >= 0
            if not inn.any(): continue
            idx = np.where(np.diff(np.concatenate([[0], inn.astype(int), [0]])) != 0)[0]
            for a, b in zip(idx[::2], idx[1::2]):
                if b - a < 2: continue
                seg = P[a:b].copy()
                # put each end exactly on the region's edge (bisection along the strand)
                for end, sgn in ((0, -1), (-1, 1)):
                    q = seg[end]; lo_t, hi_t = 0.0, step
                    for _ in range(30):
                        m = 0.5 * (lo_t + hi_t)
                        if region.sdf((q + sgn * m * d)[None])[0] >= 0: lo_t = m
                        else: hi_t = m
                    seg[end] = q + sgn * lo_t * d
                out.append(Strand(seg, width, False, "weave", "border", name="w%d.%d" % (fi, k)))
    return out


def _passes(crossings):
    P = {}
    for c in crossings:
        P.setdefault(c.over[0], []).append((c.over[1], True, c.under[0], c.under[1])); P.setdefault(c.under[0], []).append((c.under[1], False, c.over[0], c.over[1]))
    for k in P: P[k].sort()
    return P


def _end_vis(strands, k, ps, arc, gap, which):
    """Visible length of strand k's end piece (which 0 = start, 1 = end): from the end to where it is first cut - at
    its first pass if that pass is under, else at the next pass (it is under, the passes alternate) or the far end."""
    L = float(arc[-1]); seq = ps if which == 0 else ps[::-1]
    dist = (lambda i: float(arc[i])) if which == 0 else (lambda i: L - float(arc[i]))
    i, over, so, io = seq[0]
    if not over: return dist(i) - float(strands[so].hw[io]) - gap
    if len(seq) > 1:
        i2, _, so2, io2 = seq[1]; return dist(i2) - float(strands[so2].hw[io2]) - gap
    return L


def end_pieces(pat, gap):
    """For every open weave strand: the visible length of each end piece that is not tucked under a crossing strand,
    and the corner pieces (open weave strands that cross nothing). Returns (shortest, corner pieces, rows)."""
    P = _passes(pat.crossings); shortest, corner, rows = 9e9, 0, []
    for k, s in enumerate(pat.strands):
        if s.role != "weave" or s.closed: continue
        ps = P.get(k, []); arc = geom.arclen(s.pts)
        if not ps: corner += 1; rows.append(dict(strand=k, corner=True, length=round(float(arc[-1]), 3))); shortest = min(shortest, 0.0); continue
        t = tucked_ends(s); vis = [_end_vis(pat.strands, k, ps, arc, gap, w) for w in (0, 1) if not t[w]]
        rows.append(dict(strand=k, ends=[round(v, 3) for v in vis]))
        if vis: shortest = min(shortest, min(vis))
    return shortest, corner, rows


def partner_of(s):
    """The mirror partner's name of a strand made by lines(..., mirror_axis=x): w0.k <-> w1.-k."""
    try: f, k = s.name.split("."); return "w%d.%d" % (1 - int(f[1:]), -int(k))
    except Exception: return None


def tidy(strands, gap, min_end, min_len, passes=8, symmetric=False):
    """Make every end piece readable, in vector form (never by cleaning pixels):
      A (repeated until nothing changes) leave out a strand that crosses nothing (a corner piece), is shorter than
        min_len, or crosses only once, under, with a piece under min_end on either side - that corner stays floor;
      B (once, after A, so no strand a tucked end hides under is left out later) an end whose first pass is UNDER and
        whose visible piece is under min_end is cut back to half a gap past that crossing: the strand then ends under
        the strand crossing it (tucked), as a woven strand ends.
      symmetric: a strand left out takes its mirror partner with it (a mirrored lattice stays mirrored).
    Returns (strands, crossings, conflicts, log)."""
    from . import crossings as X
    st = list(strands); log = dict(dropped=0, trimmed=0)
    for _ in range(passes):
        cr, cf = X.assign(st, X.find(st)); P = _passes(cr); drop = set()
        for k, s in enumerate(st):
            ps = P.get(k, []); arc = geom.arclen(s.pts)
            short1 = len(ps) == 1 and not ps[0][1] and min(_end_vis(st, k, ps, arc, gap, 0), _end_vis(st, k, ps, arc, gap, 1)) < min_end
            if not ps or float(arc[-1]) < min_len or short1: drop.add(s.name)
        if symmetric: drop |= {partner_of(s) for s in st if s.name in drop}
        keep = [s for s in st if s.name not in drop]; log["dropped"] += len(st) - len(keep)
        if len(keep) == len(st): break
        st = keep
    cr, cf = X.assign(st, X.find(st)); P = _passes(cr); out = []
    for k, s in enumerate(st):
        ps = P.get(k, []); arc = geom.arclen(s.pts); i0, i1 = 0, len(s.pts); stp = max(float(np.median(np.diff(arc))), 1e-6)
        k_ = int(math.ceil(0.5 * gap / stp)); t0 = t1 = False
        if len(ps) > 1 and not ps[0][1] and _end_vis(st, k, ps, arc, gap, 0) < min_end: i0 = max(0, ps[0][0] - k_); t0 = True; log["trimmed"] += 1
        if len(ps) > 1 and not ps[-1][1] and _end_vis(st, k, ps, arc, gap, 1) < min_end: i1 = min(len(s.pts), ps[-1][0] + k_ + 1); t1 = True; log["trimmed"] += 1
        out.append(Strand(s.pts[i0:i1], s.width[i0:i1], False, s.role, "border", name=("t0" if t0 else "") + "|" + ("t1" if t1 else "")))
    cr, cf = X.assign(out, X.find(out))
    return out, cr, cf, log


def tucked_ends(s):
    """(start tucked under a crossing, end tucked) for a tidied weave strand."""
    tags = s.name.split("|") if "|" in s.name else ["", ""]
    return tags[0] == "t0", tags[-1] == "t1"
