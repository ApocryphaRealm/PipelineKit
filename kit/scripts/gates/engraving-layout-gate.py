"""Refuses an engraved design whose faces break the owner's engraving layout rule - at design time and at packaging.

The rule (weapon-engraving skill, "The three elements and their jobs", the owner 2026-11-10 20:07, and the 2026-11-11
additions): a BRAID has two uses only - a perimeter round something (a centerpiece) or a straight run along a long narrow
field; it never fills an area. WEAVE fills what the braid goes round. A Norse SYMBOL is the centerpiece. A face with no
centerpiece and no long run gets no braid (an outline + weave). The owner's animal engraving (the dagger's serpent, the
maces' beast heads) is an allowed field. The owner, 2026-11-11 23:39: "i noticed the battleaxe broke a rule so do a check
and see if the gate catches it in the design" - nothing did: the engraving checks recorded margins and coverage only.

THE RECORD: every paint step writes, in its engraving_check.json, a top-level "layouts" map {face: record} with
    {"perimeter": "braid"|"outline"|"none", "field": "weave"|"braid"|"knot"|"bands"|"animal"|"none",
     "centerpiece": "<symbol>"|null, "run": "straight-braid"|null}
(tn_knot.layout() / tn_knot.write_layouts() in the design workspace build it).

THE CHECK, per face:
    FAIL  field braid | knot | bands               - a braid (or knot bands) fills an area
    FAIL  perimeter braid, no centerpiece, no run   - the braid frames nothing
    FAIL  a face-like entry of engraving_check.json (one with coverage / face_px / case / by_owner / inset_px /
          centrepiece) that has no layout record, or a work folder with no "layouts" at all - so no paint step can skip it
    FAIL  fragments > 0 on a face (2026-11-12, the owner kept finding them by eye): the paint step counts, on its own
          height field inside the face's inset, strand pieces under 0.20 u^2 or thinner than 0.135 (stubs, cut-off
          slivers), flush specks under 0.20 u^2 that do not reach the plain margin, and dark pockets under 0.05 u^2
          (patternlib.measure, fragments()) and records "fragments" on the face
    FAIL  a braid run that is not along a STRAIGHT or EVEN-WIDTH band (the owner 2026-11-12 00:19 / 00:26: "not straight
          enough for the braid"; a run may curve only along a narrow band of even width with no area left over): the
          run record carries "run_metrics" {straightness = max distance of the centre line from its chord / chord,
          width_spread = (p95 - p5) / median of the band width, leftover = share of the inset outside the band}; it
          passes when straightness <= 0.03, or width_spread <= 0.30 (+-15 %) and leftover <= 0.10, or (2026-11-12) the band
          tapers smoothly (width_slope = p95 |d width / d length| <= 0.35) with leftover <= 0.10; a run the owner asked for
          by name that is outside these carries "owner_ruling" (his words) and only warns
    FAIL  a weave whose motif is too large for its panel (2026-11-12, the owner 02:35 on bow v5's plate: blocky T / H pieces
          clipped by the frame, "fragments 0" let it through): the paint step records "weave_scale" (engraving_measure.
          weave_scale: the panel's inner area in motif pieces, how many pieces are clipped by the frame); a weave field
          with panel_cells < 24 fails
    WARN  (not a failure) a face with no "fragments" count, or a run with no "run_metrics" - recorded before the check
          existed; re-measure it when the design is next painted
    FAIL  a symbol centerpiece NOT on the standard medallion (2026-11-13, the owner 2026-11-12 08:05 "I like the symbol
          with the dark filled circle. So make that the standard", and 2026-11-12 20:48 / 2026-11-13 01:48 "the war axe
          doesn't have the symbol in the black filled circle"; the ring-pass survey had passed war axe v4 by eye): every
          face whose layout names a centerpiece is judged on its MEASURED maps - <work>/medallion_check.json, written by
          a medallion measure of the maps (the original's design-workspace audit, not in the kit; this file's fields are read below): the circle round the symbol where
          carving floor steps up to flush steel). It fails when that circle's inside is under 85 % floor or its outside
          under 85 % flush (no dark disc / no ring step), the dark band inside it is under 2 px or brighter than 0.25 x
          the surrounding steel, or the flush ring is under 2 px wide, under 3 x the floor's luminance or not 0.2 smoother
          than the floor. A symbol record that says "ring": null fails too. A face with a centerpiece and no measurement
          WARNS at design time and FAILS at packaging (--repo), so no unmeasured symbol ships.
          EBONY MODE (2026-11-13, Truly Nordic 1.3.0, the owner's black-and-gold Ebony look): a medallion_check.json whose
          "mode" is "ebony" (tools/ebony.py measures the recoloured maps into <WORK>/ebony/medallion_check.json) is
          judged with the disc's ABSOLUTE darkness - the dark band's base-colour luminance (L_floor) <= 0.08 - in place of
          disc / steel <= 0.25, because the steel round the medallion is itself black (disc / steel reads 0.3-0.4 on a
          disc as dark as the Nordic one's); the ring must still be >= 2 px, >= 3 x the floor's luminance (now the gold
          ring against the dark disc) and 0.2 smoother. In --repo mode a repo with tools/ebony.py must have that file.
    FAIL  (2026-11-16) a face whose record says "generator": "patternlib" with a patternlib verdict that is not ok (or
          none): the pattern library's own validators refused it (scripts/art/patternlib, role patternlib)
    PASS  weave fields, outline + weave, a straight or even-width braid run, an animal field, a braid perimeter round a
          centerpiece, a symbol filling a small face, a plain face (none / none)

Usage:
    py -3 engraving-layout-gate.py <work dir or engraving_check.json> [...]      design time (render and sheet scripts)
    py -3 engraving-layout-gate.py --path <package> --repo <repo>                package-gate row
          `engraving-layout-follows-the-rule`: reads <repo>\\tools\\items.py (the item table) and checks the work folder
          of every engraved texture it names (a repo without tools\\items.py passes - not an engraved-model mod)
    py -3 engraving-layout-gate.py --self-test
"""
import argparse, importlib.util, json, os, sys, tempfile

FACE_KEYS = {"coverage", "face_px", "case", "by_owner", "inset_px", "centrepiece"}
FILLS = {"braid", "knot", "bands"}
STRAIGHT, EVEN, LEFTOVER, TAPER = 0.03, 0.30, 0.10, 0.35
MIN_PANEL_CELLS = 24                                 # a weave panel holds at least this many motif pieces          # run thresholds (patternlib.measure uses the same)
# the standard medallion, measured
MED_SIDE, MED_BAND_PX, MED_DISC_DARK, MED_RING_PX, MED_RING_L_X, MED_RING_ROUGH_D = 0.85, 2.0, 0.25, 2.0, 3.0, 0.20
MED_DISC_ABS = 0.08                                  # ebony mode: the dark band's own luminance (Nordic discs measure 0.04-0.056)
MED_HOW = "a medallion measure that writes medallion_check.json beside engraving_check.json (the fields medallion_problems() reads)"
WARN = []
REQUIRE_MEDALLION_MEASURE = [False]                  # True in --repo (packaging) mode


def medallion_problems(face, m, ebony=False):
    """The standard medallion on the measured maps: a list of what is missing (empty = on the standard). ebony: the disc
    is judged by its own darkness (L_floor <= MED_DISC_ABS), the steel round it being black."""
    out = []
    if not isinstance(m, dict): return [f"{face}: unreadable medallion measurement {m!r}"]
    ring = m.get("ring") or {}
    si, so = m.get("step_deep_inside") or 0.0, m.get("step_flush_outside") or 0.0
    if si < MED_SIDE or so < MED_SIDE:
        out.append(f"{face}: no circle round the symbol steps from carving floor to flush steel (floor inside {si:.2f}, flush outside {so:.2f};"
                   f" both must be >= {MED_SIDE}) - the symbol is not on a dark filled disc inside a polished ring")
        return out
    band, dd = m.get("dark_band_px") or 0.0, m.get("disc_dark")
    if ebony:
        lf = m.get("L_floor")
        if band < MED_BAND_PX or lf is None or lf > MED_DISC_ABS:
            out.append(f"{face}: the disc is not dark-filled (ebony mode: dark band {band} px, needs >= {MED_BAND_PX}; its luminance {lf}, needs <= {MED_DISC_ABS})")
    elif band < MED_BAND_PX or dd is None or dd > MED_DISC_DARK:
        out.append(f"{face}: the disc is not dark-filled (dark band {band} px, needs >= {MED_BAND_PX}; floor / steel luminance {dd}, needs <= {MED_DISC_DARK})")
    w, lx, rr_, rf = ring.get("width_px") or 0.0, ring.get("L_ring_vs_floor"), ring.get("rough_ring"), m.get("rough_floor")
    if w < MED_RING_PX or lx is None or lx < MED_RING_L_X or rr_ is None or rf is None or rr_ > rf - MED_RING_ROUGH_D:
        out.append(f"{face}: no polished ring round the disc (width {w} px >= {MED_RING_PX}; brightness x{lx} of the floor >= {MED_RING_L_X};"
                   f" roughness {rr_} vs floor {rf}, needs {MED_RING_ROUGH_D} smoother)")
    return out


def run_ok(m):
    straight = m.get("straightness", 1.0) <= STRAIGHT
    even = m.get("width_spread", 9.0) <= EVEN and m.get("leftover", 0.0) <= LEFTOVER
    taper = m.get("width_slope", 9.0) <= TAPER and m.get("leftover", 0.0) <= LEFTOVER
    return straight or even or taper


def judge(face, r):
    out = []
    if not isinstance(r, dict) or "perimeter" not in r or "field" not in r:
        return [f"{face}: malformed layout record {r!r}"]
    if r["field"] in FILLS:
        out.append(f"{face}: the field is {r['field']} - a braid fills an area (braid is only a perimeter or a straight run; weave fills)")
    if r["perimeter"] == "braid" and not r.get("centerpiece") and not r.get("run"):
        out.append(f"{face}: a braid perimeter with no centerpiece and no run - it frames nothing (use an outline + weave)")
    ws = r.get("weave_scale")
    if r.get("field") == "weave" and isinstance(ws, dict) and ws.get("panel_cells") is not None and ws["panel_cells"] < MIN_PANEL_CELLS:
        out.append(f"{face}: the weave's motif is too large for its panel ({ws['panel_cells']} pieces' worth of room, under {MIN_PANEL_CELLS};"
                   f" {ws.get('clipped')} of {ws.get('clipped', 0) + ws.get('whole', 0)} pieces clipped by the frame) - a finer weave, or no weave")
    # 2026-11-16: a face made by patternlib carries its validators' verdict - a refused pattern never passes here
    pl = r.get("patternlib")
    if r.get("generator") == "patternlib":
        if not isinstance(pl, dict): out.append(f"{face}: generator patternlib but no patternlib verdict recorded")
        elif not pl.get("ok"): out.append(f"{face}: patternlib refused it - " + "; ".join(str(x) for x in (pl.get("refusals") or ["(no reason recorded)"]))[:400])
    fr = r.get("fragments")
    if isinstance(fr, dict): fr = fr.get("fragments")
    if fr is None: WARN.append(f"{face}: no fragment count recorded")
    elif fr > 0: out.append(f"{face}: {fr} fragment(s) - stubs, slivers, specks or pockets left in the carving")
    if r.get("run"):
        m = r.get("run_metrics")
        if not isinstance(m, dict): WARN.append(f"{face}: braid run without run_metrics (straightness / width) - not measured")
        elif not run_ok(m) and r.get("owner_ruling"):
            WARN.append(f"{face}: braid run outside the straight / even / taper rule, kept by the owner's ruling: {r['owner_ruling']}")
        elif not run_ok(m):
            out.append(f"{face}: braid run along a band that is neither straight (straightness {m.get('straightness')} > {STRAIGHT}) nor even "
                       f"(width spread {m.get('width_spread')} > {EVEN} or leftover {m.get('leftover')} > {LEFTOVER}) - make it outline + weave")
    return out


def check_file(p):
    try:
        j = json.load(open(p, encoding="utf-8-sig"))
    except Exception as e:
        return [f"{p}: unreadable ({e})"], 0
    lay = j.get("layouts")
    if not isinstance(lay, dict) or not lay:
        return [f"{p}: no 'layouts' record - the paint step did not say what it carved"], 0
    bad = []
    for k, v in j.items():
        if k == "layouts" or not isinstance(v, dict): continue
        if FACE_KEYS & set(v) and k not in lay:
            bad.append(f"{k}: an engraved face with no layout record")
    for face, r in lay.items():
        if isinstance(r, dict) and "fragments" not in r and isinstance(j.get(face), dict) and "fragments" in j[face]:
            r = dict(r, fragments=j[face]["fragments"])          # the count may sit on the face's own check entry
        if isinstance(r, dict) and "weave_scale" not in r and isinstance(j.get(face), dict) and isinstance(j[face].get("weave"), dict) and "weave_scale" in j[face]["weave"]:
            r = dict(r, weave_scale=j[face]["weave"]["weave_scale"])
        bad += judge(face, r)
    # the standard medallion (2026-11-13): every centerpiece symbol measured on the maps
    medp = os.path.join(os.path.dirname(os.path.abspath(p)), "medallion_check.json")
    meds = None
    if os.path.isfile(medp):
        try: meds = json.load(open(medp, encoding="utf-8-sig")).get("faces", {})
        except Exception as e: bad.append(f"medallion_check.json unreadable ({e})"); meds = {}
    for face, r in lay.items():
        if not isinstance(r, dict) or not r.get("centerpiece") or str(r["centerpiece"]).lower() == "none": continue
        sym = j.get(face, {}).get("symbol") if isinstance(j.get(face), dict) else None
        if isinstance(sym, dict) and "ring" in sym and sym["ring"] is None:
            bad.append(f"{face}: the {r['centerpiece']} is recorded with no ring (\"ring\": null) - not on the dark filled disc and polished ring")
        m = (meds or {}).get(face)
        if m is None:
            msg = f"{face}: the {r['centerpiece']} has no medallion measurement (medallion_check.json) - run {MED_HOW}"
            (bad if REQUIRE_MEDALLION_MEASURE[0] else WARN).append(msg if REQUIRE_MEDALLION_MEASURE[0] else f"{p}: {msg}")
        else:
            bad += medallion_problems(face, m)
    return [f"{p}: {b}" for b in bad], len(lay)


def check_ebony(p):
    """An ebony-mode medallion_check.json (tools/ebony.py): every face judged in ebony mode; zero faces fails."""
    try: j = json.load(open(p, encoding="utf-8-sig"))
    except Exception as e: return [f"{p}: unreadable ({e})"], 0
    faces = j.get("faces") or {}
    if j.get("mode") != "ebony": return [f"{p}: not an ebony-mode measurement (\"mode\": \"ebony\" missing)"], 0
    if not faces: return [f"{p}: measures no medallion - an empty measurement checks nothing"], 0
    bad = []
    for face, m in faces.items(): bad += medallion_problems(face, m, ebony=True)
    return [f"{p}: {b}" for b in bad], len(faces)


def ebony_measure_from_items(repo):
    """<WORK>/ebony/medallion_check.json when the repo builds an ebony look (tools/ebony.py), else None"""
    if not os.path.isfile(os.path.join(repo, "tools", "ebony.py")): return None
    ip = os.path.join(repo, "tools", "items.py"); sys.path.insert(0, os.path.dirname(ip))
    spec = importlib.util.spec_from_file_location("items_for_gate_eb", ip); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return os.path.join(m.WORK, "ebony", "medallion_check.json")


def resolve(target):
    if os.path.isdir(target): return os.path.join(target, "engraving_check.json")
    return target


def work_dirs_from_items(repo):
    ip = os.path.join(repo, "tools", "items.py")
    if not os.path.isfile(ip): return None
    sys.path.insert(0, os.path.dirname(ip))
    spec = importlib.util.spec_from_file_location("items_for_gate", ip); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    dirs = []
    for key, it in m.ITEMS.items():
        # a shape whose texture is DERIVED from another design's pixels (2026-11-12: the Nordic arrows' atlas, copied
        # rectangle for rectangle out of the quiver design by quiver_atlas.py) names that design's work folder as
        # "design"; its faces are recorded in that folder's engraving_check.json, not beside the derived texture
        found = []
        for sh in it.get("shapes", {}).values():
            if sh.get("design"): found.append(sh["design"])
            elif sh.get("tex"): found.append(os.path.dirname(os.path.dirname(sh["tex"])))   # <work>\tex\<stem> -> <work>
        if it.get("sheath"): found.append(os.path.dirname(os.path.dirname(it["sheath"]["tex"])))
        for d in found:
            if (key, d) not in dirs: dirs.append((key, d))
    return dirs


def run(files, ebony_files=()):
    bad, n = [], 0
    for f in files:
        b, k = check_file(f); bad += b; n += k
    for f in ebony_files:
        if not os.path.isfile(f): bad.append(f"{f}: the ebony look's medallions are not measured - run tools\\ebony.py"); continue
        b, k = check_ebony(f); bad += b; n += k
    for b in bad: print("engraving-layout-gate: FAIL - " + b)
    for w in WARN: print("engraving-layout-gate: warn - " + w)
    WARN.clear()
    if not bad: print(f"engraving-layout-gate: OK - {n} face(s) in {len(files)} design(s) follow the layout rule")
    return 1 if bad else 0


def self_test():
    cases = {
        "battleaxe-like (braid + bands)": ({"crescent": {"coverage": 1}, "layouts": {"crescent": {"perimeter": "braid", "field": "bands", "centerpiece": "triquetra", "run": None}}}, 1),
        "braid frames nothing (old chape)": ({"chape": {"face_px": 9}, "layouts": {"chape": {"perimeter": "braid", "field": "weave", "centerpiece": None, "run": None}}}, 1),
        "face without a record": ({"bar": {"coverage": 1}, "layouts": {"other": {"perimeter": "none", "field": "none", "centerpiece": None, "run": None}}}, 1),
        "no layouts at all": ({"bar": {"coverage": 1}}, 1),
        "braid + weave + symbol": ({"face": {"coverage": 1}, "layouts": {"face": {"perimeter": "braid", "field": "weave", "centerpiece": "triquetra", "run": None}}}, 0),
        "outline + weave": ({"chape": {"face_px": 9}, "layouts": {"chape": {"perimeter": "outline", "field": "weave", "centerpiece": None, "run": None}}}, 0),
        "straight run on a blade": ({"blade": {"by_owner": "x"}, "layouts": {"blade": {"perimeter": "none", "field": "none", "centerpiece": None, "run": "straight-braid"}}}, 0),
        "animal field": ({"flat": {"coverage": 1}, "layouts": {"flat": {"perimeter": "outline", "field": "animal", "centerpiece": None, "run": None}}}, 0),
        "fragments on a face": ({"face": {"coverage": 1, "fragments": 3}, "layouts": {"face": {"perimeter": "outline", "field": "weave", "centerpiece": None, "run": None}}}, 1),
        "fragments in the record": ({"face": {"coverage": 1}, "layouts": {"face": {"perimeter": "outline", "field": "weave", "centerpiece": None, "run": None, "fragments": {"fragments": 2}}}}, 1),
        "no fragments": ({"face": {"coverage": 1, "fragments": 0}, "layouts": {"face": {"perimeter": "outline", "field": "weave", "centerpiece": None, "run": None}}}, 0),
        "curved uneven run": ({"claw": {"coverage": 1, "fragments": 0}, "layouts": {"claw": {"perimeter": "none", "field": "none", "centerpiece": None, "run": "straight-braid",
                               "run_metrics": {"straightness": 0.14, "width_spread": 1.7, "leftover": 0.4}}}}, 1),
        "straight tapering run": ({"blade": {"coverage": 1, "fragments": 0}, "layouts": {"blade": {"perimeter": "none", "field": "none", "centerpiece": None, "run": "straight-braid",
                                   "run_metrics": {"straightness": 0.01, "width_spread": 1.2, "leftover": 0.0}}}}, 0),
        "owner-ruled run": ({"hook": {"coverage": 1, "fragments": 0}, "layouts": {"hook": {"perimeter": "none", "field": "none", "centerpiece": None, "run": "straight-braid",
                             "owner_ruling": "the green highlight gets braid in the curve", "run_metrics": {"straightness": 0.5, "width_spread": 1.0, "width_slope": 0.8, "leftover": 0.09}}}}, 0),
        "smooth taper run": ({"tip": {"coverage": 1, "fragments": 0}, "layouts": {"tip": {"perimeter": "none", "field": "none", "centerpiece": None, "run": "straight-braid",
                              "run_metrics": {"straightness": 0.3, "width_spread": 0.9, "width_slope": 0.2, "leftover": 0.05}}}}, 0),
        "bow v5 plate: weave too coarse": ({"plate": {"coverage": 1, "fragments": 0, "weave": {"weave_scale": {"whole": 0, "clipped": 11, "whole_share": 0.0, "panel_cells": 17.9}}},
                                            "layouts": {"plate": {"perimeter": "braid", "field": "weave", "centerpiece": "triquetra", "run": None}}}, 1),
        "bow v6 plate: fine weave": ({"plate": {"coverage": 1, "fragments": 0, "weave": {"weave_scale": {"whole": 10, "clipped": 21, "whole_share": 0.323, "panel_cells": 40.4}}},
                                      "layouts": {"plate": {"perimeter": "braid", "field": "weave", "centerpiece": "triquetra", "run": None}}}, 0),
        "patternlib refused": ({"face": {"coverage": 1}, "layouts": {"face": {"perimeter": "outline", "field": "weave", "centerpiece": None, "run": None, "fragments": {"fragments": 0},
                                 "generator": "patternlib", "patternlib": {"ok": False, "refusals": ["REFUSED width-gap: strands 1 and 2 overlap"]}}}}, 1),
        "patternlib passed": ({"face": {"coverage": 1}, "layouts": {"face": {"perimeter": "outline", "field": "weave", "centerpiece": None, "run": None, "fragments": {"fragments": 0},
                                "generator": "patternlib", "patternlib": {"ok": True, "refusals": []}}}}, 0),
        "curved even band run": ({"band": {"coverage": 1, "fragments": 0}, "layouts": {"band": {"perimeter": "none", "field": "none", "centerpiece": None, "run": "straight-braid",
                                  "run_metrics": {"straightness": 0.2, "width_spread": 0.12, "leftover": 0.03}}}}, 0),
    }
    # the standard medallion (2026-11-13): (doc, want, medallion_check faces, packaging mode). The measurements are the
    # real ones of war axe v6-knurl (work_wa6_sf: bare triquetra) and v7-knurl (work_wa7_sf: on the standard).
    wa = lambda sym: {"blade face": {"coverage": 1, "fragments": 0, "symbol": sym},
                      "layouts": {"blade face": {"perimeter": "braid", "field": "weave", "centerpiece": "triquetra", "run": None}}}
    WA6 = {"step_deep_inside": 0.536, "step_flush_outside": 0.312, "dark_band_px": 0.0, "disc_dark": None, "rough_floor": None,
           "ring": {"width_px": 0.0, "L_ring_vs_floor": None, "rough_ring": None}}
    WA7 = {"step_deep_inside": 1.0, "step_flush_outside": 1.0, "dark_band_px": 6.5, "disc_dark": 0.075, "rough_floor": 0.648,
           "ring": {"width_px": 3.0, "L_ring_vs_floor": 14.15, "rough_ring": 0.229}}
    NORING = dict(WA7, ring={"width_px": 0.0, "L_ring_vs_floor": None, "rough_ring": None})
    PALE = dict(WA7, dark_band_px=6.5, disc_dark=0.62)
    med_cases = {
        "OLD WAR AXE v6: bare triquetra (record ring null + measured)": (wa({"R": 3.458, "ring": None}), 1, {"blade face": WA6}, False),
        "old war axe v6 measured only": (wa({"R": 3.458}), 1, {"blade face": WA6}, False),
        "old war axe v6 record only (ring null, not measured)": (wa({"R": 3.458, "ring": None}), 1, None, False),
        "war axe v7: standard medallion": (wa({"R": 3.35, "ring": {"disc_R": 3.47}}), 0, {"blade face": WA7}, False),
        "dark disc, no polished ring": (wa({"R": 3.35}), 1, {"blade face": NORING}, False),
        "ring round a pale disc": (wa({"R": 3.35}), 1, {"blade face": PALE}, False),
        "symbol not measured, design time (warn)": (wa({"R": 3.35}), 0, None, False),
        "symbol not measured, packaging (fail)": (wa({"R": 3.35}), 1, None, True),
    }
    # ebony mode (2026-11-13): real numbers of the Truly Nordic 1.3.0 Ebony look - the warhammer's disc against black steel
    # (disc / steel 0.303, the disc's own luminance 0.045) and a pale disc on black steel
    EB_OK = dict(WA7, disc_dark=0.303, L_floor=0.045, rough_floor=0.648, ring={"width_px": 2.5, "L_ring_vs_floor": 13.84, "rough_ring": 0.2})
    EB_PALE = dict(EB_OK, L_floor=0.15)
    eb_cases = {"ebony look: dark disc on black steel (ebony mode)": ({"mode": "ebony", "faces": {"hammer face": EB_OK}}, 0),
                "ebony look: pale disc on black steel (ebony mode)": ({"mode": "ebony", "faces": {"hammer face": EB_PALE}}, 1),
                "ebony file without its mode": ({"faces": {"hammer face": EB_OK}}, 1),
                "ebony file measuring nothing": ({"mode": "ebony", "faces": {}}, 1)}
    res = {}
    with tempfile.TemporaryDirectory() as t:
        for i, (name, (doc, want)) in enumerate(eb_cases.items()):
            p = os.path.join(t, f"e{i}.json"); json.dump(doc, open(p, "w")); res[name] = (run([], [p]), want)
        res["ebony look judged as Nordic (disc / steel) fails"] = (1 if medallion_problems("hammer face", EB_OK) else 0, 1)
        res["ebony look, measurement missing (packaging)"] = (run([], [os.path.join(t, "absent.json")]), 1)
        for i, (name, (doc, want)) in enumerate(cases.items()):
            p = os.path.join(t, f"c{i}.json"); json.dump(doc, open(p, "w")); res[name] = (run([p]), want)
        for i, (name, (doc, want, meds, pack)) in enumerate(med_cases.items()):
            d = os.path.join(t, f"m{i}"); os.makedirs(d); p = os.path.join(d, "engraving_check.json"); json.dump(doc, open(p, "w"))
            if meds is not None: json.dump({"faces": meds}, open(os.path.join(d, "medallion_check.json"), "w"))
            REQUIRE_MEDALLION_MEASURE[0] = pack
            res[name] = (run([p]), want)
            REQUIRE_MEDALLION_MEASURE[0] = False
    ok = all(g == w for g, w in res.values())
    print("self-test", "PASS" if ok else "FAIL", {k: f"exit {g} (want {w})" for k, (g, w) in res.items()})
    return 0 if ok else 1


def main(argv):
    ap = argparse.ArgumentParser(); ap.add_argument("targets", nargs="*"); ap.add_argument("--path"); ap.add_argument("--repo")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test: return self_test()
    if a.targets: return run([resolve(t) for t in a.targets])
    if a.repo:
        REQUIRE_MEDALLION_MEASURE[0] = True
        dirs = work_dirs_from_items(a.repo)
        if dirs is None:
            print("engraving-layout-gate: OK - no tools\\items.py in the repo (not an engraved-model mod)"); return 0
        eb = ebony_measure_from_items(a.repo)
        return run([resolve(d) for _, d in dirs], [eb] if eb else [])
    print("engraving-layout-gate: OK - nothing to check (no targets, no --repo)"); return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
