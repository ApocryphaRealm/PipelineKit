"""patternlib.make - one entry point: a spec (a dict, JSON-able) -> (pattern, render, report), for every pattern type.

  type "face"      the weapon-engraving skill's layout on a face outline (fit.py; every fit.py key)
  type "weave"     a framed weave panel: w x h rectangle (or "outline"), outline + weave (tuck; weave_mode "bounce" = the plait)
  type "knot"      a cols x rows Mercat / Cromwell knot panel: preset plait | cross | rings | random (seed), symmetry
  type "braid"     an n-strand braid along a straight run (length, hw, taper); a closed braid is a face perimeter
  type "symbol"    triquetra | triquetra-ring | valknut | horns of radius R on the medallion (dark disc in a polished ring)
  type "runes"     a rune band (text, length, height) from the library's own Elder Futhark strokes
  type "damascus"  a forge-layer field k (a..e; c = raindrop, the chosen look) over a w x h steel area
Common keys: ppu (pixels per world unit, required), seed, depth (0.095), gap. Everything is world units."""
import math
import numpy as np
from . import geom, fit, knot, braid, symbols, runes, damascus, crossings as X, raster, validate as V
from .model import Pattern, Strand


def _rect(w, h, c=(0.0, 0.0)):
    cx, cy = c; return np.array([[cx - w / 2, cy - h / 2], [cx + w / 2, cy - h / 2], [cx + w / 2, cy + h / 2], [cx - w / 2, cy + h / 2]], float)


def _circle(r, n=360, c=(0.0, 0.0)):
    a = np.linspace(0, 2 * math.pi, n, endpoint=False); return np.stack([np.cos(a) * r + c[0], np.sin(a) * r + c[1]], -1)


def _finish(pat, spec, frame=None):
    ppu = float(spec["ppu"]); fr = frame or raster.Frame.fit(*pat.bbox(), ppu)
    R = raster.render(pat, fr); rep = V.validate(pat, R, fr.ppu, spec.get("limits"))
    pat.meta["ppu"] = round(fr.ppu, 4); return pat, R, rep


def make(spec, frame=None):
    t = spec.get("type", "face"); ppu = float(spec["ppu"]); seed = int(spec.get("seed", 0))
    gap = spec.get("gap") or max(0.08, 2.4 / ppu)
    if t == "face":
        pat, R, rep = fit.fit(spec, frame); pat.meta["ppu"] = round(R["ppu"], 4); return pat, R, rep
    if t == "weave":
        sp = dict(spec, type="face", outline=spec.get("outline") or _rect(spec.get("w", 8.0), spec.get("h", 5.0)).tolist(), perimeter="outline", field="weave")
        pat, R, rep = fit.fit(sp, frame); pat.kind = "weave"; pat.meta["ppu"] = round(R["ppu"], 4); return pat, R, rep
    pat = Pattern(t, dict(spec, gap=gap), seed); pat.depth = spec.get("depth", 0.095)
    if t == "knot":
        cols, rows, cell = spec.get("cols", 6), spec.get("rows", 4), spec.get("cell", 1.0); w = spec.get("strand", 0.42 * cell)
        st, B = knot.knot_panel(cols, rows, cell, w, spec.get("preset", "random"), seed, spec.get("symmetry"), origin=(-cols * cell / 2, -rows * cell / 2), p=spec.get("p", 0.22))
        pat.add(*st); X.resolve(pat)
        O = _rect(cols * cell + 0.5, rows * cell + 0.5); pat.outline = O; pat.inset = [_rect(cols * cell + 0.2, rows * cell + 0.2)]; pat.floors = list(pat.inset)
        pat.grooves = [(pat.inset[0], max(0.085, 3.2 / ppu), True)]; pat.symmetry = spec.get("symmetry") if spec.get("symmetry") in ("mirror-x", "mirror-y") else None
        pat.meta["breaks"] = len(B)
    elif t == "braid":
        n, hw = spec.get("n", 3), spec.get("hw", 0.5); w = spec.get("strand", hw * (0.95 if n == 2 else 0.75)); pitch = spec.get("pitch", 3.2 * hw)
        if spec.get("closed"): raise ValueError("a closed braid is a face perimeter: type face, perimeter braid (it must frame a centrepiece)")
        else:
            L = spec.get("length", 10.0); C = np.array([[-L / 2, 0.0], [L / 2, 0.0]])
            hwv = hw if not spec.get("taper") else np.linspace(hw, hw * spec["taper"], 2)
            st, Q, hwq, _ = braid.along(C, False, n, hwv, w, pitch); pat.add(*st)
            band = np.vstack([Q + [0, 1] * (hwq[:, None] + 0.06), (Q - [0, 1] * (hwq[:, None] + 0.06))[::-1]])
            pat.inset = [band]; pat.floors = [band]; pat.outline = geom.offset_polygon(band, -0.3)[0]
            gw = max(0.085, 3.2 / ppu)
            pat.grooves = [(band, gw, True)]
            pat.layout = dict(perimeter="none", field="none", centerpiece=None, run="straight-braid")
        X.resolve(pat)
    elif t == "symbol":
        R0 = spec.get("R", 2.0); ring = spec.get("ring", 0.12); clear = spec.get("clear", 0.10); w = spec.get("strand", spec.get("strand_ratio", 0.18) * (R0 - clear))
        name = spec.get("symbol", "triquetra")
        pat.add(*symbols.SYMBOLS[name]((0.0, 0.0), R0 - clear, w)); X.resolve(pat)
        pat.discs = [(0.0, 0.0, R0, ring)]; pat.outline = _circle(R0 + ring + 0.35); pat.inset = [_circle(R0 + ring + 0.02)]
        pat.symmetry = spec.get("symmetry", "rot3"); pat.meta["sym_centre"] = (0.0, 0.0)
    elif t == "runes":
        L, h = spec.get("length", 12.0), spec.get("height", 1.6); stroke = spec.get("stroke", 0.14)
        C = np.array([[-L / 2, 0.0], [L / 2, 0.0]]); st, lines, total = runes.band(C, spec.get("text", "fehu uruz thurisaz"), h, stroke)
        pat.add(*st); pat.grooves = lines; pat.outline = _rect(L + 0.6, h + 0.8); pat.inset = [_rect(L + 0.2, h + 0.2)]
        pat.meta["text_length"] = round(total, 3)
        if total > L: pat.meta["overflow"] = round(total - L, 3)
    elif t == "damascus":
        w, h = spec.get("w", 10.0), spec.get("h", 4.0); k = spec.get("k", "c")
        fr = frame or raster.Frame.fit(np.array([-w / 2, -h / 2]), np.array([w / 2, h / 2]), ppu, pad=0.0)
        Wd = fr.world(); lay, P = damascus.layers(k, Wd[..., 1] - Wd[..., 1].min(), Wd[..., 0] - Wd[..., 0].min())
        # the thinnest layer the texture must hold: twice the largest inscribed distance along each layer's ridge, p2
        from scipy import ndimage
        thin = []
        for msk in (lay > 0.5, lay <= 0.5):
            dt = ndimage.distance_transform_edt(msk); ridge = (dt == ndimage.maximum_filter(dt, 3)) & msk & (dt > 0)
            if ridge.any(): thin.append(float(np.percentile(2 * dt[ridge], 2)) / fr.ppu)
        pat.damascus = dict(k=k, name=damascus.NAMES[k], period=P, thinnest_layer=min(thin) if thin else 0.0)
        pat.outline = _rect(w, h); pat.meta["ppu"] = round(fr.ppu, 4)
        R = dict(H=np.zeros(lay.shape, np.float32), face=np.ones(lay.shape, bool), inset=np.zeros(lay.shape, bool), strand=lay.astype(np.float32),
                 ring=np.zeros(lay.shape, bool), floor=np.zeros(lay.shape, np.float32), ppu=fr.ppu, depth=pat.depth, layers=lay)
        rep = V.validate(pat, R, fr.ppu, spec.get("limits")); return pat, R, rep
    else:
        raise KeyError("unknown pattern type %r" % t)
    return _finish(pat, spec, frame)
