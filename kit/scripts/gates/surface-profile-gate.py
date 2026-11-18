"""Refuses a carved face whose surface is UNEVEN under the light - at design time and at packaging.

The owner, 2026-11-12 02:54 / 02:55 / 02:58 (bow v7's band and hook): "the surface of the curved braid is uneven and you
can tell by the way the light hits the surface its uneven just like the greatsword emblem was" - "add a gate and a skill
update to check for surface elevation" - "there should also be consideration for consistent even rounding of a carving
like with the pommel". A carved face may be FLAT or UNIFORMLY ROUNDED; it fails when its profile wanders along it.

THE MEASURE (in the original, a Blender pass and an analysis script of its design workspace, not in the kit; written to
<work>\\surface_profile.json): on the exported NIF, on the surface THE GAME SHADES (the NIF's per-vertex normals
interpolated across each triangle - a geometrically flat face shaded with leaning normals reads exactly as a bumpy one),
every carved face (the paint dump's FILL patches) is cut into cross-sections every 0.2 along its centre line; each
section's shading-normal lean across it is fitted as  lean = tilt + crown * s  (s -1..1 across):
    crown_spread  p95 - p5 of the crown along the face (the rounding changes)          FAIL above 5 deg
    tilt_spread   p95 - p5 of the tilt along the face (it twists / leans in and out)     FAIL above 5 deg
    bumps         p95 of each section's residual about its fit (local bumps, dips)      FAIL above 1.5 deg
    along_bumps   std of the lean ALONG the centre line, detrended (rises and falls)    FAIL above 1.5 deg
Calibration (2026-11-12): bow v7's band+hook FAILS (crown spread 25, tilt 19, bumps 6.4); bow v8 PASSES (0.3 / 0.6 /
0.1); greatsword v3's lower guard (emblem) FAILS (27 / 20 / 9.5); the greatsword blade flats PASS (3.2 / 4.5 / 0.7 / 0.1).
NOTE: greatsword v4's lower guard arms also FAIL (37 / 38 / 9) - the same shading fault as v3 (the slab builder shares
the face's outline vertices with the chamfer, so the NIF normals lean ~24 deg); its level boss fixed the emblem's
geometry, not the arms' shading. A face with fewer than 4 sections (a small disc) is not judged by this measure.

Usage:
    py -3 surface-profile-gate.py <work dir or surface_profile.json> [...]     design time (design_gate.require)
    py -3 surface-profile-gate.py --path <package> --repo <repo>               package row: passes (no NIF measure there yet)
    py -3 surface-profile-gate.py --self-test
"""
import argparse, json, os, sys, tempfile

LIMITS = dict(crown_spread=5.0, tilt_spread=5.0, bumps=1.5, along_bumps=1.5)
MIN_SECTIONS = 4


def judge(f):
    if f.get("sections", 0) < MIN_SECTIONS: return []
    return [f"{k} {f[k]} > {v}" for k, v in LIMITS.items() if f.get(k, 0) > v]


def check(p):
    if os.path.isdir(p): p = os.path.join(p, "surface_profile.json")
    if not os.path.isfile(p): return None, [f"{p}: no surface_profile.json - the surface was not measured"]
    try: j = json.load(open(p, encoding="utf-8-sig"))
    except Exception as e: return [f"{p}: unreadable ({e})"], []
    bad = []
    for f in j.get("faces", []):
        b = judge(f)
        if b: bad.append(f"{p}: face {f.get('key')} at {f.get('centre')} (area {f.get('area')}): uneven - " + ", ".join(b))
    return bad, []


def run(targets, strict=False):
    bad, warn, n = [], [], 0
    for t in targets:
        b, w = check(t)
        if b is None: (bad if strict else warn).extend(w); continue
        bad += b; n += 1
    for b in bad: print("surface-profile-gate: FAIL - " + b)
    for w in warn: print("surface-profile-gate: warn - " + w)
    if not bad: print(f"surface-profile-gate: OK - {n} measured design(s), every carved face flat or evenly rounded along its length")
    return 1 if bad else 0


def self_test():
    v7 = {"key": 2, "sections": 129, "crown_spread": 24.89, "tilt_spread": 18.9, "bumps": 6.46, "along_bumps": 5.7, "centre": [-0.51, -16.69, 1.38], "area": 95.4}
    v8 = {"key": 2, "sections": 129, "crown_spread": 0.3, "tilt_spread": 0.25, "bumps": 0.1, "along_bumps": 0.1, "centre": [-0.51, -16.69, 1.38], "area": 95.4}
    gs3 = {"key": 2, "sections": 98, "crown_spread": 26.86, "tilt_spread": 19.79, "bumps": 9.54, "along_bumps": 3.83, "centre": [-0.29, 4.39, 1.45], "area": 58.3}
    blade = {"key": 1, "sections": 293, "crown_spread": 3.23, "tilt_spread": 4.48, "bumps": 0.69, "along_bumps": 0.14, "centre": [-1.66, 64.39, 0.48], "area": 181.8}
    disc = {"key": 4, "sections": 3, "crown_spread": 30.0, "tilt_spread": 30.0, "bumps": 9.0, "along_bumps": 9.0, "centre": [0, 0, 0], "area": 5.0}
    cases = {"bow v7 band+hook": ([v7], 1), "bow v8 band+hook": ([v8], 0), "greatsword v3 emblem guard": ([gs3], 1),
             "greatsword blade (gently curved, even)": ([blade], 0), "small disc (not judged)": ([disc], 0)}
    res = {}
    with tempfile.TemporaryDirectory() as t:
        for i, (name, (faces, want)) in enumerate(cases.items()):
            p = os.path.join(t, f"c{i}.json"); json.dump({"faces": faces}, open(p, "w")); res[name] = (run([p]), want)
        res["not measured (warn only)"] = (run([os.path.join(t, "none")]), 0)
        res["not measured, strict"] = (run([os.path.join(t, "none")], strict=True), 1)
    ok = all(g == w for g, w in res.values())
    print("self-test", "PASS" if ok else "FAIL", {k: f"exit {g} (want {w})" for k, (g, w) in res.items()})
    return 0 if ok else 1


def main(argv):
    ap = argparse.ArgumentParser(); ap.add_argument("targets", nargs="*"); ap.add_argument("--path"); ap.add_argument("--repo")
    ap.add_argument("--strict", action="store_true"); ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test: return self_test()
    if a.targets: return run(a.targets, strict=a.strict)
    print("surface-profile-gate: OK - nothing to check (design-time gate; pass work folders)"); return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
