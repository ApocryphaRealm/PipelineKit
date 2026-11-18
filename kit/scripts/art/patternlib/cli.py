"""patternlib command line (role patternlib-cli).

    py -3 cli.py <spec.json> <out dir> [--face NAME]
    py -3 cli.py --validate <pattern.json> [--ppu N]

Generate: writes <out>/pattern.json (the vector pattern), pattern.svg, height.png (0 = floor, 1 = flush), normal_dx.png,
normal_gl.png, mask.png (the face), preview.png (lit), validation.json, and engraving_check.json with the face's
layout record for the engraving-layout gate ({"layouts": {NAME: {..., "generator": "patternlib", "patternlib": verdict}}}).
Prints every finding; on a refusal prints "REFUSED <validator>: <reason>" and exits 2 (the files are still written, so
the refusal can be looked at). --validate re-renders a saved pattern at its own ppu (or --ppu) and re-runs the
validators: exit 2 when refused. Same spec -> same bytes."""
import argparse, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
import numpy as np
from PIL import Image
from patternlib import make as MK, raster, validate as V, fit
from patternlib.model import Pattern


def save_png(a, path, mode):
    Image.fromarray(np.clip(np.asarray(a) * 255 + 0.5, 0, 255).astype(np.uint8), mode).save(path, optimize=False)


def write(pat, R, rep, out, name="face"):
    os.makedirs(out, exist_ok=True)
    pat.to_json(os.path.join(out, "pattern.json"))
    if pat.kind != "damascus":
        pat.to_svg(os.path.join(out, "pattern.svg"), 40.0)
        save_png(raster.height_png(R), os.path.join(out, "height.png"), "L")
        ndx, ngl = raster.normals(R["H"], R["ppu"]); save_png(ndx, os.path.join(out, "normal_dx.png"), "RGB"); save_png(ngl, os.path.join(out, "normal_gl.png"), "RGB")
        save_png(R["face"].astype(np.float32), os.path.join(out, "mask.png"), "L"); save_png(raster.shade(R), os.path.join(out, "preview.png"), "RGB")
    else:
        save_png(R["layers"], os.path.join(out, "layers.png"), "L")
    with open(os.path.join(out, "validation.json"), "w", newline="\n") as f: json.dump(rep, f, indent=1, sort_keys=True, default=str)
    if pat.layout:
        rec = fit.layout_record(pat, rep) if pat.kind in ("face", "weave") else dict(pat.layout, generator="patternlib", fragments=next((x.get("fragments") for x in rep["findings"] if x["name"] == "strand-continuity"), None),
                                                                                      patternlib=dict(ok=rep["ok"], refusals=rep["refusals"], ppu=rep["ppu"]))
        cov = next((x.get("coverage") for x in rep["findings"] if x["name"] == "coverage"), None)
        with open(os.path.join(out, "engraving_check.json"), "w", newline="\n") as f:
            json.dump({name: dict(coverage=cov, generator="patternlib"), "layouts": {name: rec}}, f, indent=1, sort_keys=True, default=str)


def report(rep):
    for x in rep["findings"]: print("  %-18s %s  %s" % (x["name"], "ok     " if x["ok"] else "REFUSED", x["msg"]))
    for r in rep["refusals"]: print(r)
    print("patternlib:", "PASS" if rep["ok"] else "REFUSED (%d)" % len(rep["refusals"]))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", nargs="?"); ap.add_argument("out", nargs="?"); ap.add_argument("--face", default="face")
    ap.add_argument("--validate"); ap.add_argument("--ppu", type=float)
    a = ap.parse_args(argv)
    if a.validate:
        pat = Pattern.from_json(a.validate); ppu = a.ppu or pat.meta.get("ppu") or 40.0
        if pat.kind == "damascus":
            p2, R, rep = MK.make(dict(pat.params, type="damascus", ppu=ppu))
        else:
            R = raster.render(pat, raster.Frame.fit(*pat.bbox(), ppu)); rep = V.validate(pat, R, ppu)
            if pat.kind in ("face", "weave"):
                for f in (fit.weave_scale_finding(pat, R), fit.end_piece_finding(pat)):
                    if f is not None:
                        rep["findings"].append(f)
                        if not f["ok"]: rep["refusals"].append("REFUSED %s: %s" % (f["name"], f["msg"])); rep["ok"] = False
        report(rep); return 0 if rep["ok"] else 2
    if not (a.spec and a.out): ap.error("give <spec.json> <out dir>, or --validate <pattern.json>")
    spec = json.load(open(a.spec))
    try: pat, R, rep = MK.make(spec)
    except ValueError as e:                                # no candidate could even be built (no inset, no room)
        print("REFUSED fit: %s" % e); print("patternlib: REFUSED (1)"); return 2
    write(pat, R, rep, a.out, a.face); report(rep)
    return 0 if rep["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
