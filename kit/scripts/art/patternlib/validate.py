"""patternlib.validate - the validators that make a pattern reliable. Each returns a Finding; validate() runs the set a
pattern asks for and the report's refusals are printed as

    REFUSED <validator>: <what is wrong, where, by how much>

and the CLI exits 2. The validators (limits are the defaults; a spec may tighten them):
  strand-continuity   every strand closed, or ending on the carving's border / a groove / under a crossing strand
                      (a tucked weave end) / declared terminal (symbol tips, rune strokes); no strand shorter than 3
                      widths (an open weave strand is judged by its end pieces instead: fit.py's end-pieces finding); on the raster, 0 fragments (stubs, slivers,
                      specks, pockets - the engraving-layout gate's own counting, measure.fragments)
  over-under          every geometric crossing has an assigned over and under (re-found from the final curves), no
                      colouring conflict, and along every strand the passes go over, under, over... (cyclic when closed)
  width-gap           every strand >= 4 px wide and every gap between strands (and the cut at a crossing) >= 2 px at the
                      target px per unit
  margin              no strand edge outside the inset (tolerance half a pixel), no carved pixel outside the inset beyond
                      the frame groove, margin spread (largest / smallest margin - 1) <= 0.25
  coverage            share of the inset that is carving (strands, floor, grooves, the medallion) >= 0.85
  symmetry            (when asked) the strand set maps onto itself under the mirror / rotation: p99 distance <= 1 px
  min-feature         the smallest feature the texture must hold - strand, gap, groove, rune stroke, medallion ring,
                      damascus layer - >= 3 px
  layout-rule         (face layouts) the owner's rule: a braid perimeter frames a centrepiece, a braid never fills a field
"""
import math
import numpy as np
from scipy.spatial import cKDTree
from . import geom, crossings as X, measure

LIMITS = dict(min_w_px=4.0, min_gap_px=2.0, min_feature_px=3.0, min_cov=0.85, margin_spread=0.25, sym_px=1.0, min_len_widths=3.0)


class Finding(dict):
    def __init__(self, name, ok, msg, **kw):
        super().__init__(name=name, ok=bool(ok), msg=msg, **kw)


def _step(s):
    d = np.linalg.norm(np.diff(s.pts, axis=0), axis=1); return float(np.median(d)) if len(d) else 0.0


def continuity(pat, R=None, ppu=None, lim=LIMITS):
    bad = []; ends_on = []
    for P in pat.inset: ends_on.append((P, True))
    if pat.outline is not None: ends_on.append((pat.outline, True))
    for (P, w, c) in pat.grooves: ends_on.append((P, c))
    for k, s in enumerate(pat.strands):
        if s.role == "rune": continue
        L = geom.length(s.pts, s.closed); w = float(np.median(s.width))
        if L < lim["min_len_widths"] * w and not (s.role == "weave" and not s.closed): bad.append("strand %d (%s) is %.2f long, under %.0f widths" % (k, s.role, L, lim["min_len_widths"]))
        if s.closed:
            if np.linalg.norm(s.pts[0] - s.pts[-1]) > 4 * _step(s) + 1e-6: bad.append("strand %d is marked closed but its ends are %.3f apart" % (k, np.linalg.norm(s.pts[0] - s.pts[-1])))
        elif s.ends == "border":
            tk = (s.name.split("|")[0] == "t0", s.name.split("|")[-1] == "t1") if "|" in s.name else (False, False)
            for e, tucked in ((s.pts[0], tk[0]), (s.pts[-1], tk[1])):
                if tucked:                                   # ends under the strand crossing it (a tidied weave end)
                    others = [o for j, o in enumerate(pat.strands) if j != k and o.role == s.role]
                    dmin = min([float(geom.poly_dist(e[None], o.pts, o.closed)[0]) for o in others] + [9e9])
                    if dmin > float(s.hw.max()) * 0.5 + pat.params.get("gap", 0.08): bad.append("strand %d's tucked end at (%.2f, %.2f) is not under a strand" % (k, e[0], e[1]))
                    continue
                dmin = min([float(geom.poly_dist(e[None], P, c)[0]) for P, c in ends_on] + [abs(math.hypot(e[0] - cx, e[1] - cy) - r) for cx, cy, r, rw in pat.discs] + [9e9])
                if dmin > float(s.hw.max()) + 0.05: bad.append("strand %d (%s) ends in the open at (%.2f, %.2f), %.2f from any border or groove" % (k, s.role, e[0], e[1], dmin))
    frag = None
    if R is not None:
        ins = R["inset"] if R["inset"].any() else R["face"]
        frag = measure.fragments(R["H"], R["face"], ins, R["ppu"], R["depth"])
        if frag["fragments"]: bad.append("raster: %d fragment(s) - %d stub(s), %d speck(s), %d pocket(s)%s" % (frag["fragments"], frag["stubs"], frag["specks"], frag["pockets"],
                                         (" first at px [row, col, size] %s" % (frag.get("stub_at_px") or frag.get("speck_at_px") or frag.get("pocket_at_px"))[:3]) if (frag.get("stub_at_px") or frag.get("speck_at_px") or frag.get("pocket_at_px")) else ""))
    return Finding("strand-continuity", not bad, "; ".join(bad[:6]) or "%d strands, all closed or ending on a border" % len(pat.strands),
                   strands=len(pat.strands), closed=sum(s.closed for s in pat.strands), fragments=frag)


def alternation(pat, lim=LIMITS):
    bad = []
    if pat.conflicts: bad.append("%d over-under colouring conflict(s)" % pat.conflicts)
    idx = [i for i, s in enumerate(pat.strands) if s.role != "rune"]
    found = X.find([pat.strands[i] for i in idx])
    rec = np.array([c.p for c in pat.crossings]) if pat.crossings else np.zeros((0, 2))
    if len(found) != len(pat.crossings):
        bad.append("the curves cross %d times but %d crossings carry an over-under" % (len(found), len(pat.crossings)))
    elif len(found):
        d, _ = cKDTree(rec).query(np.array([f[0] for f in found]))
        if (d > 0.05).any(): bad.append("%d crossing(s) of the curves have no recorded over-under (worst %.3f off)" % (int((d > 0.05).sum()), float(d.max())))
    passes = {}
    for ci, c in enumerate(pat.crossings):
        if c.over == c.under: bad.append("crossing %d has the same pass over and under" % ci)
        passes.setdefault(c.over[0], []).append((c.over[1], True, ci)); passes.setdefault(c.under[0], []).append((c.under[1], False, ci))
    broken = 0
    for s, lst in passes.items():
        lst.sort(); seq = [o for _, o, _ in lst]
        pairs = list(zip(seq, seq[1:])) + ([(seq[-1], seq[0])] if pat.strands[s].closed and len(seq) > 1 else [])
        k = sum(a == b for a, b in pairs)
        if k: broken += 1; bad.append("strand %d goes %s twice in a row %d time(s)" % (s, "over/under", k)) if broken <= 3 else None
    return Finding("over-under", not bad, "; ".join(bad[:6]) or "%d crossings, every strand alternates" % len(pat.crossings), crossings=len(pat.crossings))


def width_gap(pat, ppu, lim=LIMITS):
    bad = []; gap = pat.params.get("gap", 0.08)
    sts = [(k, s) for k, s in enumerate(pat.strands)]
    if not sts: return Finding("width-gap", True, "no strands")
    wmin = min(float(s.width.min()) for _, s in sts) * ppu
    if wmin < lim["min_w_px"]: bad.append("narrowest strand %.1f px wide, under %.1f px" % (wmin, lim["min_w_px"]))
    cr = [c for c in pat.crossings]
    if cr and gap * ppu < lim["min_gap_px"]: bad.append("the cut at a crossing is %.1f px, under %.1f px" % (gap * ppu, lim["min_gap_px"]))
    S, HW, SID, IX, ARC = [], [], [], [], []
    for k, s in sts:
        if s.role == "rune": continue
        keep = np.ones(len(s.pts), bool)
        if not s.closed and s.ends == "border":            # the ends run on under the frame groove / a crossing strand
            gw_ = max([g[1] for g in pat.grooves] + [0.0]); ex = 1.42 * float(s.hw.max()) + gw_ / 2 + lim["min_gap_px"] / ppu
            a_ = geom.arclen(s.pts); keep = (a_ > ex) & (a_ < a_[-1] - ex)
        S.append(s.pts[keep]); HW.append(s.hw[keep]); SID.append(np.full(int(keep.sum()), k)); IX.append(np.arange(len(s.pts))[keep]); ARC.append(geom.arclen(s.pts)[keep])
    gmin = None
    if S:
        S = np.vstack(S); HW = np.concatenate(HW); SID = np.concatenate(SID); IX = np.concatenate(IX); ARC = np.concatenate(ARC)
        need = lim["min_gap_px"] / ppu; r = 2 * float(HW.max()) + need + 1e-6
        pr = cKDTree(S).query_pairs(r, output_type="ndarray")
        if len(pr):
            i, j = pr[:, 0], pr[:, 1]; dist = np.linalg.norm(S[i] - S[j], axis=1); clr = dist - HW[i] - HW[j]
            same = SID[i] == SID[j]; L = np.array([geom.length(pat.strands[k].pts, pat.strands[k].closed) for k in range(len(pat.strands))])
            da = np.abs(ARC[i] - ARC[j]); closed = np.array([pat.strands[k].closed for k in range(len(pat.strands))])
            da = np.where(same & closed[SID[i]], np.minimum(da, L[SID[i]] - da), da)
            skip = same & (da <= dist * 1.25 + 0.06)
            if cr:
                CP = np.array([c.p for c in cr]); Rc = np.array([1.6 * (pat.strands[c.over[0]].hw[c.over[1]] + gap) + pat.strands[c.under[0]].hw[c.under[1]] for c in cr])
                ct = cKDTree(CP); near_i = ct.query_ball_point(S[i], float(Rc.max()))
                pairset = [{c.over[0], c.under[0]} for c in cr]
                for t in np.where(~skip & (clr < need))[0]:
                    for ci in near_i[t]:
                        if {SID[i[t]], SID[j[t]]} <= pairset[ci] and np.linalg.norm(S[i[t]] - CP[ci]) < Rc[ci] and np.linalg.norm(S[j[t]] - CP[ci]) < Rc[ci]:
                            skip[t] = True; break
            chk = ~skip
            if chk.any():
                t = int(np.argmin(np.where(chk, clr, 9e9))); gmin = float(clr[t])
                if gmin < need:
                    bad.append("strands %d and %d come %.1f px apart at (%.2f, %.2f), under %.1f px" % (SID[i[t]], SID[j[t]], max(gmin, 0) * ppu if gmin > -9 else -1, S[i[t]][0], S[i[t]][1], lim["min_gap_px"]) if gmin >= 0 else
                               "strands %d and %d overlap by %.1f px at (%.2f, %.2f) without a crossing" % (SID[i[t]], SID[j[t]], -gmin * ppu, S[i[t]][0], S[i[t]][1]))
    return Finding("width-gap", not bad, "; ".join(bad) or "narrowest strand %.1f px, tightest gap %s" % (wmin, "%.1f px" % (gmin * ppu) if gmin is not None else ">= %.1f px everywhere" % lim["min_gap_px"]),
                   min_width_px=round(wmin, 2), min_gap_px=None if gmin is None else round(gmin * ppu, 2))


def margin(pat, R=None, ppu=None, lim=LIMITS):
    if not pat.inset: return Finding("margin", True, "no inset (a free-standing pattern)")
    bad = []; regs = [geom.Region(P) for P in pat.inset]; worst = 9e9
    for k, s in enumerate(pat.strands):
        # an open field strand runs on under the frame groove: its centre line must stay in, its sides are clipped there
        sd = np.max(np.stack([r.sdf(s.pts) for r in regs]), 0) - (0.0 if (not s.closed and s.ends == "border") else s.hw); m = float(sd.min()); worst = min(worst, m)
        if m < -0.5 / (ppu or 40.0): bad.append("strand %d (%s) pokes %.3f out of the inset at (%.2f, %.2f)" % (k, s.role, -m, *s.pts[int(np.argmin(sd))]))
    spread = None
    if pat.outline is not None:
        lines = [np.asarray(P, float) for P in pat.meta.get("margin_lines", [])] or pat.inset
        ds = np.concatenate([geom.poly_dist(geom.resample(P, 0.05, True), pat.outline, True) for P in lines if len(P)])
        cut = pat.params.get("margin_cut_px", None)
        # inset edges that are not offsets of the outline (a split line, a medallion) lie farther in; the margin is the
        # outline-facing part: distances within 2 x the target margin
        M = pat.params.get("margin")
        if M: ds = ds[ds < 1.6 * M]
        if len(ds):
            spread = float(ds.max() / max(ds.min(), 1e-9) - 1)
            if spread > lim["margin_spread"]: bad.append("margin %.3f..%.3f (spread %.0f %%, over %.0f %%)" % (ds.min(), ds.max(), spread * 100, lim["margin_spread"] * 100))
    out_px = None
    if R is not None:
        gw = max([w for _, w, _ in pat.grooves] + [0.0]); Q = None
        carved = (R["H"] < -0.01 * R["depth"]) & R["face"] & ~R["inset"]
        if carved.any():
            from scipy import ndimage
            dist_in = ndimage.distance_transform_edt(~R["inset"]) / R["ppu"]
            out_px = int((carved & (dist_in > gw / 2 + 1.5 / R["ppu"])).sum())
            if out_px: bad.append("%d carved px outside the inset beyond the frame groove" % out_px)
        else: out_px = 0
    return Finding("margin", not bad, "; ".join(bad[:4]) or "inside the inset (closest strand edge %.3f in), margin spread %s" % (worst, "%.0f %%" % (spread * 100) if spread is not None else "n/a"),
                   closest=round(worst, 4), spread=None if spread is None else round(spread, 3), outside_px=out_px)


def coverage(pat, R, lim=LIMITS):
    ins = R["inset"]
    if not ins.any(): return Finding("coverage", True, "no inset (a free-standing pattern)")
    carved = (R["H"] < -0.01 * R["depth"]) | (R["strand"] > 0.5) | R["ring"]
    cov = float((carved & ins).sum() / ins.sum()); want = pat.params.get("min_cov", lim["min_cov"])
    return Finding("coverage", cov >= want, ("%.1f %% of the inset is carving, under %.0f %%" % (cov * 100, want * 100)) if cov < want else "%.1f %% of the inset is carving" % (cov * 100), coverage=round(cov, 4))


def symmetry(pat, ppu, lim=LIMITS):
    sym = pat.symmetry
    if not sym: return Finding("symmetry", True, "not asked")
    c = np.asarray(pat.meta.get("sym_centre", (0.0, 0.0)), float)
    # judged on the centre lines; the last (strand width + end-piece) of an open strand is left out - a tucked weave end
    # is cut back on one side only (the over-under of a weave is mirrored with it, so which end tucks differs)
    S = []
    for s in pat.strands:
        if s.role == "rune": continue
        if s.closed or s.ends != "border": S.append(s.pts); continue
        a_ = geom.arclen(s.pts); ex = 2.0 * float(s.width.max()); m = (a_ > ex) & (a_ < a_[-1] - ex)
        if m.any(): S.append(s.pts[m])
    S = np.vstack(S) - c
    if sym == "mirror-x": T = S * [-1, 1]
    elif sym == "mirror-y": T = S * [1, -1]
    elif sym.startswith("rot"):
        n = int(sym[3:]); a = 2 * math.pi / n; T = S @ np.array([[math.cos(a), math.sin(a)], [-math.sin(a), math.cos(a)]])
    else: return Finding("symmetry", False, "unknown symmetry %r" % sym)
    Sall = np.vstack([s.pts for s in pat.strands if s.role != "rune"]) - c
    d, _ = cKDTree(Sall).query(T); p99 = float(np.percentile(d, 99)) * ppu; tol = lim["sym_px"]
    return Finding("symmetry", p99 <= tol, ("%s broken: p99 %.2f px off its image, over %.1f px" % (sym, p99, tol)) if p99 > tol else "%s holds (p99 %.2f px)" % (sym, p99), p99_px=round(p99, 3))


def min_feature(pat, ppu, R=None, lim=LIMITS):
    feats = []
    for s in pat.strands: feats.append(("%s strand" % s.role, float(s.width.min())))
    for (_, w, _) in pat.grooves: feats.append(("groove", w))
    for (_, _, r, rw) in pat.discs: feats.append(("medallion ring", rw))
    if pat.damascus: feats.append(("damascus layer", pat.damascus["thinnest_layer"]))
    if not feats: return Finding("min-feature", True, "no features")
    name, v = min(feats, key=lambda f: f[1]); px = v * ppu; want = lim["min_feature_px"]
    return Finding("min-feature", px >= want, ("smallest feature (%s) is %.1f px, under %.1f px - the texture cannot hold it" % (name, px, want)) if px < want else "smallest feature (%s) %.1f px" % (name, px), smallest_px=round(px, 2), smallest=name)


def layout_rule(pat):
    L = pat.layout
    if not L: return Finding("layout-rule", True, "not a face layout")
    if L.get("field") in ("braid", "knot", "bands"): return Finding("layout-rule", False, "a %s fills the field - the owner's rule: weave fills, a braid never fills an area" % L["field"])
    if L.get("perimeter") == "braid" and not L.get("centerpiece") and not L.get("run"):
        return Finding("layout-rule", False, "a braid perimeter with no centrepiece frames nothing - an outline + weave panel instead")
    return Finding("layout-rule", True, "%s perimeter, %s field, centrepiece %s" % (L.get("perimeter"), L.get("field"), L.get("centerpiece")))


def validate(pat, R=None, ppu=None, limits=None):
    lim = dict(LIMITS, **(limits or {})); ppu = ppu or (R["ppu"] if R is not None else 40.0)
    F = []
    if pat.kind == "damascus":
        F.append(min_feature(pat, ppu, R, lim))
    else:
        F += [continuity(pat, R, ppu, lim), alternation(pat, lim), width_gap(pat, ppu, lim), margin(pat, R, ppu, lim)]
        if R is not None: F.append(coverage(pat, R, lim))
        F += [symmetry(pat, ppu, lim), min_feature(pat, ppu, R, lim), layout_rule(pat)]
    refusals = ["REFUSED %s: %s" % (f["name"], f["msg"]) for f in F if not f["ok"]]
    return dict(ok=not refusals, ppu=round(ppu, 3), findings=F, refusals=refusals)


def summary(rep):
    if rep["ok"]: return "PASS"
    return "; ".join(r.replace("REFUSED ", "") for r in rep["refusals"])
