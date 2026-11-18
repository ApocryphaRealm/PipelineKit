"""patternlib.fit - a face outline + a spec -> a validated pattern, the weapon-engraving skill's procedure as code:

  1. the face's outline (world units, the face's own plane)            -> spec["outline"]
  2. inset by an even margin (a TRUE offset, never a scale)            -> pattern.inset, the frame groove on that line
  3. perimeter: 'outline' (the groove alone) or 'braid' (an n-strand braid along the inset, a second groove inside it)
     - a braid perimeter only where it frames a centrepiece (the owner's rule; dropped with the symbol)
  4. centrepiece: a Norse symbol on the dark filled disc in its polished ring, at the field's widest point (or on the
     symmetry axis), only if it fits at a bold size (R >= R_min)
  5. field: the weave (mirror-curve plait) or a knot, fitted to what is left: its loops turn back along the frame and
     round the medallion ring, so nothing is cut off
  6. render at the target px per unit, run every validator; if one refuses, try the next candidate (grid phase, cell
     scale) in a FIXED order and keep the first that passes - the same spec always lands on the same candidate

spec keys (world units): outline, ppu, margin (auto: max(8 % of the narrow dimension, 12 px)), perimeter ('outline'|
'braid'|'none'), field ('weave'|'knot'|'none'), centerpiece (None|'triquetra'|'triquetra-ring'|'valknut'|'horns'),
strand (weave strand width; auto narrow / 13), cell (auto strand / 0.42), braid {n, hw, strand, pitch}, medallion
{R_max, R_min, ring, strand_ratio}, groove (0.085), gap (0.08), frame_gap (0.10), symmetry (None|'mirror-x'), axis (x of
the mirror axis), lattice_axis (a weave lattice mirrored about this x without asking the face to be symmetric), rot (weave grid turn, radians), knot {preset, p}, seed, depth (0.095), split {x, half_width} (two
fields either side of a plain band down x = x0, the bracer's polished ridge), min_cov, run {line, hw, n, strand, pitch}.
"""
import math
import numpy as np
from . import geom, knot, braid, weave, symbols, crossings as X, raster, validate as V, measure
from .model import Pattern, Strand, Crossing


def _auto(spec):
    O = geom.ccw(np.asarray(spec["outline"], float)); R0 = geom.Region(O); _, rin = geom.max_inscribed(R0, res=0.04)
    narrow = 2 * rin; ppu = float(spec["ppu"])
    M = spec.get("margin") or max(0.08 * narrow, 12.0 / ppu)
    return O, narrow, M, ppu


def build(spec, cand=None):
    """One candidate pattern (no validation)."""
    cand = cand or {}; O, narrow, M, ppu = _auto(spec); seed = int(spec.get("seed", 0))
    # widths in world units, but never under what the target density can hold (groove >= 3.2 px, cut >= 2.4 px)
    gw = spec.get("groove") or max(0.085, 3.2 / ppu); gap = spec.get("gap") or max(0.08, 2.4 / ppu); fg = spec.get("frame_gap") or max(0.10, 2.4 / ppu)
    pat = Pattern("face", dict(spec_keys=sorted(k for k in spec if k != "outline"), margin=round(M, 5), gap=gap, narrow=round(narrow, 4), candidate=cand,
                               min_cov=spec.get("min_cov", 0.85)), seed)
    pat.depth = spec.get("depth", 0.095); pat.outline = O
    insets = geom.offset_polygon(O, M)
    if not insets: raise ValueError("the margin %.3f leaves no inset in this outline" % M)
    split = spec.get("split")
    if split:                                                         # two fields either side of a plain band
        x0, hb = split["x"], split["half_width"]; halves = []
        for P in insets:
            for n_, c in (((-1.0, 0.0), -(x0 - hb)), ((1.0, 0.0), x0 + hb)):
                Hh = geom.clip_halfplane(P, np.array(n_), c)
                if len(Hh) >= 3 and abs(geom.area(Hh)) > 0.05: halves.append(geom.resample(geom.ccw(Hh), 0.04, True))
        pat.meta["margin_lines"] = [np.round(P, 5).tolist() for P in insets]     # the outline-facing inset, before the split
        insets = halves
    pat.inset = insets
    perim, field, cpiece = spec.get("perimeter", "outline"), spec.get("field", "weave"), spec.get("centerpiece")
    run = spec.get("run"); notes = []
    for P in insets: pat.grooves.append((P, gw, True)); pat.floors.append(P)
    fields = []; tuck_fields = list(insets)          # tuck: the weave runs on under the groove whose centre line this is
    for P in insets:
        inner = geom.offset_polygon(P, gw / 2.0 + 0.02)
        fields += inner
    # ---- centrepiece
    med = None
    if cpiece:
        mspec = dict(dict(R_max=1.6, R_min=0.9, ring=0.12, strand_ratio=0.20, clear=0.10), **spec.get("medallion", {}))
        reg0 = geom.Region(fields[0]) if fields else None
        room_extra = (2 * spec.get("braid", {}).get("hw", 0.45) + gw + fg) if perim == "braid" else 0.0
        if reg0 is not None:
            if spec.get("symmetry") == "mirror-x":
                ax = spec.get("axis", 0.0); lo, hi = reg0.bbox(); ys = np.arange(lo[1], hi[1], 0.02)
                s = reg0.sdf(np.stack([np.full(len(ys), ax), ys], -1)); i = int(np.argmax(s)); c, room = np.array([ax, ys[i]]), float(s[i])
            else: c, room = geom.max_inscribed(reg0, res=0.03)
            c = np.asarray(spec.get("medallion", {}).get("centre", c), float)
            room = float(reg0.sdf(c[None])[0])
            Rd = min(mspec["R_max"], room - room_extra - mspec["ring"] - fg - 0.35 * max(spec.get("cell", 0.6), 0.4))
            if Rd >= mspec["R_min"]: med = (float(c[0]), float(c[1]), Rd, mspec)
            else: notes.append("centrepiece dropped: room for R %.2f, under the bold minimum %.2f" % (Rd, mspec["R_min"]))
        if med is None:
            cpiece = None
            if perim == "braid": perim = "outline"; notes.append("braid perimeter dropped with the symbol (it framed nothing)")
    # ---- braid perimeter
    if perim == "braid":
        b = dict(dict(n=2, hw=0.45, strand=None, pitch=None), **spec.get("braid", {}))
        sw = b["strand"] or round(b["hw"] * 0.95, 4); pitch = b["pitch"] or 3.2 * b["hw"]
        newf = []; tuck_fields = []
        bg = fg * 0.5                                       # floor between the braid and each groove
        for P in fields:
            cl = geom.offset_polygon(P, b["hw"] + bg)
            if not cl: continue
            st, Q, hw, _ = braid.along(cl[0], True, b["n"], b["hw"], sw, pitch, smooth=b["hw"] * 0.8)
            for s_ in st: pat.add(s_)
            inner = geom.offset_polygon(P, 2 * b["hw"] + 2 * bg + gw / 2.0)
            for Pi in inner: pat.grooves.append((Pi, gw, True)); tuck_fields.append(Pi)
            newf += geom.offset_polygon(P, 2 * b["hw"] + 2 * bg + gw + 0.02)
        fields = newf
    # ---- medallion and symbol
    discs = []
    if med is not None:
        cx, cy, Rd, ms = med; pat.discs.append((cx, cy, Rd, ms["ring"])); discs.append((cx, cy, Rd + ms["ring"]))
        Rs = Rd - ms["clear"]; sw = max(ms["strand_ratio"] * Rs, 0.08)
        for s_ in symbols.SYMBOLS[cpiece]((cx, cy), Rs, sw): pat.add(s_)
    # ---- straight run (a long narrow field: one braid along it, end grooves across it)
    if run:
        line = np.asarray(run["line"], float); hw = run.get("hw", 0.45); sw = run.get("strand", hw * 0.95)
        st, Q, hwq, _ = braid.along(line, False, run.get("n", 3), hw, sw, run.get("pitch", 3.2 * hw))
        for s_ in st: pat.add(s_)
        T = geom.tangents(Q, False); N = np.stack([-T[:, 1], T[:, 0]], -1)
        for e, n_ in ((Q[0], N[0]), (Q[-1], N[-1])): pat.grooves.append((np.array([e - n_ * (hw + gw), e + n_ * (hw + gw)]), gw, False))
        pat.meta["run_metrics"] = dict(length=round(geom.length(Q), 3), width_median=round(2 * hw, 3))
    # ---- field: the weave strand from the FIELD's own narrow dimension (the skill: ~1/12-1/15 of the region it fills,
    #      here at least 4 px and at most the face's narrow / 13), the cell from the strand (strand = 0.42 cell)
    cell = spec.get("cell"); w = spec.get("strand")
    mode = spec.get("weave_mode", "tuck")
    if field == "weave" and mode == "tuck" and tuck_fields:
        fnar = 2 * max(geom.max_inscribed(geom.Region(P), res=0.04)[1] for P in tuck_fields)
        if w is None: w = max(min(fnar / 7.0, narrow / 13.0), 4.5 / ppu)
        w = round(w * cand.get("w_scale", 1.0), 4); pitch = (cell or w / 0.55) * cand.get("cell_scale", 1.0); cell = pitch
        regs = [geom.Region(P, discs=discs) for P in tuck_fields]
        sym = spec.get("symmetry") == "mirror-x"; ax = spec.get("axis", 0.0) if sym else None
        # separate fields mirrored about the axis (the split either side of a band): weave the left ones, mirror them
        # whole - strands, crossings AND over-under - onto the right, so the halves are exact mirror images
        mirror_halves = bool(sym and split and all(abs(float(np.mean(P[:, 0])) - ax) > 1e-6 for P in tuck_fields))
        if mirror_halves:                                  # only when the halves really are mirror images (to 1 px)
            L_ = [P for P in tuck_fields if float(np.mean(P[:, 0])) < ax]; R_ = [P for P in tuck_fields if float(np.mean(P[:, 0])) >= ax]
            mirror_halves = len(L_) == len(R_) and all(float(np.abs(geom.Region(np.stack([2 * ax - b[:, 0], b[:, 1]], -1)).sdf(a)).max()) <= 1.0 / ppu for a, b in zip(L_, R_))
            if not mirror_halves: notes.append("mirror requested but the two halves differ by more than 1 px: each half woven on the mirrored lattice")
        if mirror_halves: regs = [r_ for r_, P in zip(regs, tuck_fields) if float(np.mean(P[:, 0])) < ax]
        lat = spec.get("lattice_axis", ax)
        # an end piece must read as a piece by the gate's own rule (measure.fragments: area >= min(MIN_PIECE, 0.4 x the
        # median piece)); a whole piece runs from cut to cut over one crossing: about w x (2 pitch - w - 2 gap)
        med_piece = w * max(2 * pitch - w - 2 * gap, w)
        min_end = max(0.75 * w, 1.25 * min(measure.MIN_PIECE, measure.REL_PIECE * med_piece) / w)
        n_ph = 8 if sym else 6
        phases = [(i / n_ph, 0.0) for i in range(n_ph)] if sym else [(i / n_ph, j / n_ph) for i in range(n_ph) for j in range(n_ph)]
        best = None
        for ph in phases:
            st0 = [s_ for reg in regs for s_ in weave.lines(reg, pitch, w, ph, spec.get("rot", 0.0), mirror_axis=None if mirror_halves else lat)]
            st, cr, cf, log = weave.tidy(st0, gap, min_end, 3.0 * w, symmetric=bool(sym and not mirror_halves))
            tmp = Pattern("weave"); tmp.strands = st; tmp.crossings = cr
            sh, corner, _ = weave.end_pieces(tmp, gap)
            # fewest strands left out, then fewest ends cut back, then the longest shortest end piece
            score = (cf == 0 and corner == 0, -log["dropped"], -log["trimmed"], round(sh, 4))
            if best is None or score > best[0]: best = (score, ph, st, log, cr)
        base = len(pat.strands); n_l = len(best[2])
        for s_ in best[2]: pat.add(s_)
        pre = [Crossing(c.p, (base + c.over[0], c.over[1]), (base + c.under[0], c.under[1])) for c in best[4]]
        if mirror_halves:
            for s_ in best[2]:
                pat.add(Strand(np.stack([2 * ax - s_.pts[:, 0], s_.pts[:, 1]], -1), s_.width, False, s_.role, s_.ends, s_.name))
            pre += [Crossing((2 * ax - c.p[0], c.p[1]), (base + n_l + c.over[0], c.over[1]), (base + n_l + c.under[0], c.under[1])) for c in best[4]]
        pat.meta["_pre_weave"] = pre
        pat.params["min_end"] = round(min_end, 4); pat.meta["weave_phase"] = best[1]; pat.meta["weave_tidy"] = best[3]; pat.meta["stretch"] = [0.0]
    elif field in ("weave", "knot") and fields:
        # the field's corners rounded to ~0.45 cell first: a loop pushed into a sharp corner follows a diagonal gradient
        # and curls (the frame groove itself stays on the sharp inset line; the corner keeps a little floor)
        c_guess = cell or (max(min(2 * max(geom.max_inscribed(geom.Region(P), res=0.04)[1] for P in fields) / 7.0, narrow / 13.0), 4.5 / ppu) / 0.42)
        rnd = 0.45 * c_guess
        fields = [q for P in fields for q in geom.offset_polygon(geom.offset_polygon(P, rnd)[0], -rnd)] if all(geom.offset_polygon(P, rnd) for P in fields) else fields
        regs = [geom.Region(P, discs=discs) for P in fields]
        fnar = 2 * max(geom.max_inscribed(geom.Region(P), res=0.04)[1] for P in fields)
        if w is None: w = max(min(fnar / 7.0, narrow / 13.0), 4.5 / ppu)
        w = round(w * cand.get("w_scale", 1.0), 4)
        if cell is None: cell = round(w / 0.42, 4)
        cell = cell * cand.get("cell_scale", 1.0)
        for reg in regs:
            if spec.get("symmetry") == "mirror-x":
                ax = spec.get("axis", 0.0); c0, _ = geom.max_inscribed(reg, res=cell / 8.0); origin = np.array([ax, c0[1]])
            else: origin, _ = geom.max_inscribed(reg, res=cell / 8.0)
            origin = origin + np.asarray(cand.get("phase", (0.0, 0.0))) * cell
            br = ()
            if field == "knot":
                kp = spec.get("knot", {}); rng = np.random.default_rng(seed)
                cells_all = knot.region_cells(reg, knot.Grid(cell, origin, spec.get("rot", 0.0)), w / 2 + fg, knot.INSIDE)
                br = {e for e in knot._internal_edges(cells_all) if rng.random() < kp.get("p", 0.18)}
            st, cells, grid = knot.fill_region(reg, cell, w, fg, origin=origin, rot=spec.get("rot", 0.0), breaks=br, role="weave" if field == "weave" else "knot", gap=gap)
            for s_ in st: pat.add(s_)
            pat.meta.setdefault("stretch", []).append(round(max([abs(v) for v in knot.LAST_PUSH] + [0.0]) / cell, 3))
    # ---- crossings, group by group (a crossing BETWEEN groups is a defect the over-under validator re-finds)
    groups = {}
    for i, s in enumerate(pat.strands): groups.setdefault(s.role, []).append(i)
    allc, conf = [], 0
    for role, idx in sorted(groups.items()):
        if role == "rune": continue
        if role == "weave" and pat.meta.get("_pre_weave") is not None:
            allc += pat.meta.pop("_pre_weave"); continue
        sub = [pat.strands[i] for i in idx]; cr, cf = X.assign(sub, X.find(sub)); conf += cf
        for c in cr: c.over = (idx[c.over[0]], c.over[1]); c.under = (idx[c.under[0]], c.under[1]); allc.append(c)
    pat.crossings = allc; pat.conflicts = conf
    pat.symmetry = spec.get("symmetry"); pat.meta["sym_centre"] = (spec.get("axis", 0.0), 0.0)
    pat.layout = dict(perimeter=perim if perim != "none" else ("none"), field=field if (fields or tuck_fields) else "none", centerpiece=cpiece,
                      run="straight-braid" if run else None)
    pat.meta.update(notes=notes, strand=w, cell=cell, margin=M, narrow=narrow, weave_mode=mode if field == "weave" else None)
    pat.meta.pop("_pre_weave", None)
    return pat


CANDIDATES = [dict(), dict(phase=(0.5, 0.0)), dict(phase=(0.0, 0.5)), dict(phase=(0.5, 0.5)),
              dict(cell_scale=0.9), dict(cell_scale=0.9, phase=(0.5, 0.5)), dict(cell_scale=1.1), dict(cell_scale=0.8)]
TUCK_CANDIDATES = [dict(), dict(w_scale=0.85), dict(w_scale=0.72), dict(w_scale=0.6)]     # bold first, finer only when refused
GOOD_STRETCH = 0.25      # a passing candidate whose frame turns move under a quarter cell is taken at once


def weave_scale_finding(pat, R):
    """The gate's weave-scale rule (room for >= 24 motif pieces) measured on the VECTOR weave: a mirror-curve weave has
    no pieces clipped by its frame (every strand turns back), so its room is the count of its crossings."""
    if pat.layout.get("field") != "weave": return None
    n = sum(1 for c in pat.crossings if pat.strands[c.over[0]].role == "weave")
    ws = dict(whole=n, clipped=0, whole_share=1.0, panel_cells=float(n), method="patternlib: crossings of the weave (no frame-clipped pieces by construction)")
    ok = n >= 24
    return V.Finding("weave-scale", ok, ("the weave's motif is too large for its panel (%d crossings' worth of room, under 24)" % n) if not ok
                     else "room for %d motif pieces (>= 24)" % n, weave_scale=ws)


def end_piece_finding(pat):
    """A tuck weave's pieces at the frame: the shortest end piece >= 0.75 strand width, no corner pieces."""
    if pat.meta.get("weave_mode") != "tuck": return None
    sh, corner, rows = weave.end_pieces(pat, pat.params.get("gap", 0.08)); want = pat.params.get("min_end", 0.0)
    bad = []
    if corner: bad.append("%d corner piece(s) - a strand cut by the frame that crosses nothing" % corner)
    if sh < want: bad.append("shortest end piece %.3f long, under %.3f - a sliver at the frame" % (sh, want))
    return V.Finding("end-pieces", not bad, "; ".join(bad) or "shortest end piece %.3f (>= %.3f), no corner pieces" % (sh, want), shortest=round(sh, 4), corner=corner)


def fit(spec, frame=None, limits=None):
    """Build, render, validate every candidate in the FIXED order; keep the passing one whose frame turns stretch least
    (the first under GOOD_STRETCH is taken at once; ties go to the earlier). Returns (pattern, render, report); when no
    candidate passes, the last one with its refusals. frame: the raster frame (default upright round the outline)."""
    tries = []; best = None; last = None
    cands = TUCK_CANDIDATES if (spec.get("field", "weave") == "weave" and spec.get("weave_mode", "tuck") == "tuck") else CANDIDATES
    for ci, cand in enumerate(cands[: spec.get("max_candidates", len(cands))]):
        try: pat = build(spec, cand)
        except Exception as e: tries.append(dict(candidate=cand, error=str(e))); continue
        fr = frame or raster.Frame.fit(*pat.bbox(), spec["ppu"])
        R = raster.render(pat, fr); rep = V.validate(pat, R, fr.ppu, limits)
        for ws in (weave_scale_finding(pat, R), end_piece_finding(pat)):
            if ws is None: continue
            rep["findings"].append(ws)
            if not ws["ok"]: rep["refusals"].append("REFUSED %s: %s" % (ws["name"], ws["msg"])); rep["ok"] = False
        st = max(pat.meta.get("stretch") or [0.0])
        tries.append(dict(candidate=cand, ok=rep["ok"], stretch=st, refusals=rep["refusals"]))
        last = (pat, R, rep)
        if rep["ok"] and (best is None or st < best[3] - 1e-9): best = (pat, R, rep, st)
        if best is not None and best[3] <= GOOD_STRETCH: break
    if last is None: raise ValueError("no candidate could be built: %s" % tries)
    pat, R, rep = (best[:3] if best is not None else last); pat.meta["tries"] = tries; rep["tries"] = tries
    return pat, R, rep


def layout_record(pat, rep):
    """The engraving-layout gate's per-face record, with patternlib's verdict attached."""
    L = dict(pat.layout); fr = next((f.get("fragments") for f in rep["findings"] if f["name"] == "strand-continuity"), None)
    L["fragments"] = fr if fr is not None else dict(fragments=0)
    ws = next((f.get("weave_scale") for f in rep["findings"] if f["name"] == "weave-scale"), None)
    if ws: L["weave_scale"] = ws
    L["generator"] = "patternlib"
    L["patternlib"] = dict(ok=rep["ok"], refusals=rep["refusals"], ppu=rep["ppu"], strands=len(pat.strands), crossings=len(pat.crossings))
    if pat.meta.get("notes"): L["note"] = "; ".join(pat.meta["notes"])
    return L
