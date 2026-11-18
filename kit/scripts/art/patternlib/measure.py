r"""patternlib.measure - the raster fragment and weave-scale measures, ABSORBED from the original's design-workspace measure (2026-11-12,
the rules the engraving-layout gate has judged every Carved face by since): one copy here, so patternlib does not reach
into a plan folder. Same thresholds, same counting. H: heights (world units, 0 = flush, -depth = floor)."""
import math
import numpy as np
from scipy import ndimage
MIN_PIECE, THIN_PIECE, MIN_POCKET = 0.20, 0.135, 0.05     # u^2, u (half a 0.27 strand), u^2
REL_PIECE = 0.40                                          # of the face's median piece
FLUSH_TOL = 0.01                                          # |H| under 1 % of the depth is flush steel (a strand top dips at least 2 %)
STRAIGHT, EVEN, LEFTOVER, TAPER = 0.03, 0.30, 0.10, 0.35               # the gate's run thresholds (also in engraving-layout-gate.py)

def _pieces(H, face, inset, px, depth):
    ins = face & inset; raw = ins & (H < -FLUSH_TOL * depth) & (H > -0.5 * depth); strand = ndimage.binary_opening(raw)
    lab, n = ndimage.label(strand)
    if not n: return raw, strand, lab, 0, None, None, None, 0.0
    lab = np.where(raw, ndimage.grey_dilation(lab, size=3), 0) * raw     # the piece's area counts its rim back in
    a = ndimage.sum(raw, lab, range(1, n + 1)) / px / px
    t = 2 * np.asarray(ndimage.maximum(ndimage.distance_transform_edt(strand), lab, range(1, n + 1))) / px
    # a stub: smaller than MIN_PIECE AND than REL_PIECE of the face's median piece (a narrow braid's whole segments are
    # smaller than a weave cell), or thinner than THIN_PIECE
    lim = min(MIN_PIECE, REL_PIECE * float(np.median(a)))
    return raw, strand, lab, n, a, t, (a < 0.95 * lim) | (t < THIN_PIECE), lim

def fragments(H, face, inset, px, depth):
    H = np.asarray(H, np.float64); ins = face & inset
    strand = ins & (H < -FLUSH_TOL * depth) & (H > -0.5 * depth); flush = ins & (H >= -FLUSH_TOL * depth); floor = ins & (H <= -0.5 * depth)
    out = dict(pieces=0, stubs=0, specks=0, pockets=0, smallest_piece=None)
    raw, strand, lab, n, a, t, bad, lim = _pieces(H, face, inset, px, depth)
    if n:
        out["pieces"] = int(n); out["stubs"] = int(bad.sum()); out["smallest_piece"] = round(float(a.min()), 3); out["piece_limit"] = round(lim, 3)
        if bad.any():
            ob = ndimage.find_objects(lab); out["stub_at_px"] = [[ob[i][0].start, ob[i][1].start, round(float(a[i]), 3), round(float(t[i]), 3)] for i in np.where(bad)[0][:12] if ob[i] is not None]
    # flush islands that do not touch the plain margin (the face outside its inset is the margin)
    margin = face & ~inset; lab, n = ndimage.label(flush | margin)
    if n:
        keep = np.unique(lab[margin]); a = ndimage.sum(flush, lab, range(1, n + 1)) / px / px
        isl = np.ones(n + 1, bool); isl[0] = False; isl[keep] = False
        # 1-3 px anti-aliasing specks are invisible
        # a long thin flush island (longer than 1.0) is a frame line between a groove and a band, not a speck
        ob_ = ndimage.find_objects(lab); ext = np.array([math.hypot(o[0].stop - o[0].start, o[1].stop - o[1].start) / px if o is not None else 0.0 for o in ob_])
        sp = np.where(isl[1:] & (a < MIN_PIECE) & (a * px * px >= 4) & (ext <= 1.0))[0]; out["specks"] = int(len(sp))
        if len(sp):
            ob = ndimage.find_objects(lab); out["speck_at_px"] = [[ob[i][0].start, ob[i][1].start, int(round(a[i] * px * px))] for i in sp[:12]]
    lab, n = ndimage.label(floor)
    if n:
        a = ndimage.sum(floor, lab, range(1, n + 1)) / px / px; pk = np.where((a < MIN_POCKET) & (a * px * px >= 4))[0]; out["pockets"] = int(len(pk))
        if len(pk):                                       # patternlib addition: where they are (row, col, px)
            ob = ndimage.find_objects(lab); out["pocket_at_px"] = [[ob[i][0].start, ob[i][1].start, int(round(a[i] * px * px))] for i in pk[:12]]
    out["fragments"] = out["stubs"] + out["specks"] + out["pockets"]
    return out

def weave_scale(H, panel, px, depth, rim=0.12, groove=0.10):
    """Is the weave's motif the right scale for its panel? (2026-11-12, the owner 02:35 on bow v5: blocky T / H pieces
    clipped by the panel's frame read as an oversized tile.) Pieces = the raised strand pieces inside the panel's frame;
    a piece is CLIPPED when it reaches the frame (it runs on under the rim), WHOLE otherwise. Returns counts, the share of
    whole pieces, and the panel's size in motif cells (its inner area over the median whole piece's area)."""
    dW = ndimage.distance_transform_edt(np.pad(panel, 1))[1:-1, 1:-1] / px; inner = panel & (dW >= rim + groove)
    raw = inner & (np.asarray(H) < -FLUSH_TOL * depth) & (np.asarray(H) > -0.5 * depth); st = ndimage.binary_opening(raw)
    lab, n = ndimage.label(st)
    if not n: return dict(whole=0, clipped=0, whole_share=0.0, panel_cells=0.0)
    edge = inner & (dW < rim + groove + 2.5 / px)
    touch = np.zeros(n + 1, bool); touch[np.unique(lab[edge & st])] = True; touch[0] = False
    a = ndimage.sum(st, lab, range(1, n + 1)); wh = ~touch[1:]
    medw = float(np.median(a[wh])) if wh.any() else float(np.median(a))
    return dict(whole=int(wh.sum()), clipped=int((~wh).sum()), whole_share=round(float(wh.mean()), 3),
                panel_cells=round(float(inner.sum() / max(medw, 1.0)), 1), median_piece=round(medw / px / px, 3))

