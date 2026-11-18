"""patternlib catalogue (role patternlib-catalogue): every pattern type at three densities, each with its validator
verdict printed under it.

    py -3 catalogue.py <out dir> [--ppu 12,24,48] [--only name,name]

Writes <out>/PATTERNS-sheet.png and <out>/PATTERNS-sheet.json (every cell's spec, verdict and refusals). The densities
are pixels per world unit: 12 is about a far LOD, 24 the set's armour atlases, 48 close to the weapon fittings (60)."""
import argparse, json, math, os, sys, textwrap, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from patternlib import make as MK, raster, validate as V

t_ = np.linspace(-1, 1, 80)
AXE = np.vstack([[[-4.5, -2.0]], np.stack([5.2 + 2.2 * np.cos(t_ * 1.05), 5.6 * np.sin(t_ * 1.05)], -1), [[-4.5, 2.0]]]).tolist()
SHIELD = (np.stack([np.cos(np.linspace(0, 2 * math.pi, 240, endpoint=False)) * 6.0, np.sin(np.linspace(0, 2 * math.pi, 240, endpoint=False)) * 4.6], -1)).tolist()
TYPES = [
    ("weave panel (tuck, the set's weave)", dict(type="weave", w=9.0, h=5.0)),
    ("weave plait (strands turn at the frame)", dict(type="weave", w=9.0, h=5.0, weave_mode="bounce")),
    ("knot panel, seeded breaks, mirror-x", dict(type="knot", cols=8, rows=4, cell=1.0, preset="random", seed=7, symmetry="mirror-x", p=0.3)),
    ("knot panel, 'rings' preset", dict(type="knot", cols=7, rows=5, cell=1.0, preset="rings")),
    ("braid run, 2 strands", dict(type="braid", n=2, hw=0.5, length=10.0)),
    ("braid run, 3-strand plait", dict(type="braid", n=3, hw=0.6, length=10.0)),
    ("face: braid perimeter + weave + triquetra", dict(type="face", outline=SHIELD, perimeter="braid", field="weave", centerpiece="triquetra", braid=dict(n=2, hw=0.42), medallion=dict(R_max=1.7))),
    ("face: outline + weave + valknut (axe)", dict(type="face", outline=AXE, perimeter="outline", field="weave", centerpiece="valknut", medallion=dict(R_max=1.8))),
    ("triquetra with ring, on the medallion", dict(type="symbol", symbol="triquetra-ring", R=2.0)),
    ("valknut, on the medallion", dict(type="symbol", symbol="valknut", R=2.0)),
    ("Odin's horns, on the medallion", dict(type="symbol", symbol="horns", R=2.0, strand_ratio=0.16)),
    ("rune band (our own Elder Futhark strokes)", dict(type="runes", text="ek erilaz fahido", length=12.0, height=1.6, stroke=0.15)),
    ("damascus c - raindrop (the chosen look)", dict(type="damascus", k="c", w=10.0, h=4.0)),
    ("damascus a - wild", dict(type="damascus", k="a", w=10.0, h=4.0)),
]


def font(sz, bold=False):
    for f in (("arialbd.ttf",) if bold else ()) + ("arial.ttf",):
        try: return ImageFont.truetype(f, sz)
        except Exception: pass
    return ImageFont.load_default()


def cell_image(pat, R):
    if pat.kind == "damascus":
        v = R["layers"]; a = 0.30 + 0.45 * v; return np.stack([a * 0.97, a, a * 1.04], -1)
    return raster.shade(R)


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("--ppu", default="12,24,48"); ap.add_argument("--only", default="")
    a = ap.parse_args(argv); dens = [float(x) for x in a.ppu.split(",")]; only = [s for s in a.only.split(",") if s]
    CW, CH, TH = 380, 250, 118; F, Fb, Fs = font(15), font(17, True), font(13)
    rows = [t for t in TYPES if not only or any(o in t[0] for o in only)]
    W = 300 + len(dens) * (CW + 16) + 20; H = 70 + len(rows) * (CH + TH + 14)
    sheet = Image.new("RGB", (W, H), (22, 23, 26)); d = ImageDraw.Draw(sheet)
    d.text((20, 14), "patternlib %s - every pattern type at %s px per unit, each with its validator verdict" % (__import__("patternlib").VERSION, ", ".join("%g" % x for x in dens)), font=font(22, True), fill=(235, 235, 235))
    for i, x in enumerate(dens): d.text((300 + i * (CW + 16), 46), "%g px / unit" % x, font=Fb, fill=(240, 200, 90))
    log = []
    for ri, (name, spec) in enumerate(rows):
        y = 70 + ri * (CH + TH + 14); d.text((20, y + 6), "\n".join(textwrap.wrap(name, 30)), font=Fb, fill=(230, 230, 230))
        for ci, ppu in enumerate(dens):
            x = 300 + ci * (CW + 16); t0 = time.time()
            try:
                pat, R, rep = MK.make(dict(spec, ppu=ppu)); img = cell_image(pat, R); ok = rep["ok"]; refs = rep["refusals"]
                extra = "%d strands, %d crossings" % (len(pat.strands), len(pat.crossings)) if pat.kind != "damascus" else "thinnest layer %.1f px" % (pat.damascus["thinnest_layer"] * ppu)
            except Exception as e:
                img = np.full((50, 80, 3), 0.1); ok = False; refs = ["ERROR %s: %s" % (type(e).__name__, e)]; extra = ""
            im = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)); sc = min(CW / im.width, CH / im.height)
            im = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.NEAREST if sc >= 1 else Image.LANCZOS)
            sheet.paste(im, (x + (CW - im.width) // 2, y + (CH - im.height) // 2))
            ty = y + CH + 4; d.text((x, ty), ("PASS" if ok else "REFUSED") + "   " + extra, font=Fb, fill=(140, 230, 140) if ok else (255, 130, 110)); ty += 21
            for r in refs[:3]:
                for ln in textwrap.wrap(r.replace("REFUSED ", ""), 52)[:2]: d.text((x, ty), ln, font=Fs, fill=(230, 200, 190)); ty += 15
            log.append(dict(type=name, ppu=ppu, ok=ok, refusals=refs, seconds=round(time.time() - t0, 1)))
            print("%-45s %5g  %s  %s" % (name[:45], ppu, "PASS" if ok else "REFUSED", "; ".join(r[:70] for r in refs[:2])), flush=True)
    os.makedirs(a.out, exist_ok=True); sheet.save(os.path.join(a.out, "PATTERNS-sheet.png"))
    json.dump(dict(version=__import__("patternlib").VERSION, densities=dens, cells=log), open(os.path.join(a.out, "PATTERNS-sheet.json"), "w"), indent=1)
    print("wrote", os.path.join(a.out, "PATTERNS-sheet.png"))


if __name__ == "__main__":
    main()
