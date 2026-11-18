"""patternlib.damascus - forge-welded layer patterns as resolution-free fields of world position (u across the blade,
v along it), absorbed from the damascus design study (the original's design workspace,
the owner chose option c, raindrop, 2026-11-16). The same smooth noise (seed 1347),
the same five fields and the same hard-edged layer stack, so a blade painted here matches the study's swatches.

  a wild    : u + nested domain warps          b ladder : |u| pushed in by a bump every L along the blade
  c rain    : wavy base + a dome at each jittered drop (concentric rings) - the CHOSEN look
  d feather : v - K|u| chevrons + a light warp e sharp A : the soft A grain, layered with hard edges

layers(k, u, v) -> 0..1 (1 = bright layer); the min-feature validator measures the thinnest layer in pixels."""
import numpy as np
from scipy import ndimage as ndi

_rng = np.random.default_rng(1347)
_G = [ndi.gaussian_filter(_rng.standard_normal((512, 512)), 3.0, mode="wrap") for _ in range(5)]
_G = [g / g.std() for g in _G]
NAMES = {"a": "wild", "b": "ladder", "c": "raindrop", "d": "feather", "e": "sharp-A"}


def noise(k, x, y):
    return ndi.map_coordinates(_G[k], [np.asarray(y).ravel() + 37 * k, np.asarray(x).ravel() + 91 * k], order=3, mode="grid-wrap").reshape(np.shape(x))


def h01(n, k):
    x = np.sin(n * 12.9898 + k * 78.233) * 43758.5453; return x - np.floor(x)


def field(k, u, v):
    if k == "a":
        w0 = noise(4, u * 3.4, v * 1.05); w1 = noise(2, (u + 0.3 * w0) * 5.0, v * 1.6) * 0.30; w2 = noise(1, u * 9.0, (v + w1 * 3) * 3.0) * 0.05
        return 1.65 * (0.5 * u + 0.75 * w0) + w1 + w2, 0.34
    if k == "b":
        L = 1.9; ph = v / L - np.round(v / L); bump = np.exp(-(ph / 0.16) ** 2); au = np.sqrt(u * u + 0.04)
        return au - 0.75 * bump * np.exp(-(au / 2.6) ** 2) + noise(2, u * 3.0, v * 1.0) * 0.06, 0.32
    if k == "c":
        sx, sy = 1.45, 1.6; iu, iv = np.floor(u / sx), np.floor(v / sy); best = np.zeros_like(u)
        for du in (-1, 0, 1):
            for dv in (-1, 0, 1):
                cu, cv = iu + du, iv + dv
                pu = (cu + 0.2 + 0.6 * h01(cu * 131 + cv, 3)) * sx; pv = (cv + 0.2 + 0.6 * h01(cu * 17 + cv * 7, 5)) * sy
                best = np.maximum(best, np.exp(-((u - pu) ** 2 + (v - pv) ** 2) / 0.62 ** 2))
        return 0.45 * (u + noise(0, u * 2.0, v * 0.6) * 0.5) + 1.25 * best, 0.30
    if k == "d":
        uc = np.sqrt(u * u + 0.01); w = noise(4, u * 1.6, v * 0.5) * 0.45 + noise(1, u * 6.0, v * 2.0) * 0.06
        return v - 1.5 * uc + 0.35 * uc * uc + w, 0.34
    if k == "e":
        w1 = noise(0, u * 2.4, v * 0.75) * 0.55; w2 = noise(1, (u + w1) * 7.0, v * 2.2) * 0.12; vv = v + noise(2, u * 3.0, v * 1.0) * 0.6
        return u + w1 + w2 + 0.35 * noise(3, u * 1.5, vv * 0.45), 0.32
    raise KeyError(k)


def layers(k, u, v, duty=0.45, jit=0.25, seed=None, px=None):
    """Hard-edged layer stack of field k; anti-aliased over one pixel (px = pixels per unit; default from the grid)."""
    f, P = field(k, np.asarray(u, float), np.asarray(v, float)); seed = ord(k) if seed is None else seed
    gy, gx = np.gradient(f); g = np.hypot(gx, gy); g = np.minimum(g, np.percentile(g, 95))
    aa = np.clip(g / P, 0.03, 0.5); t = f / P; n = np.floor(t); fr = t - n
    d = np.where(fr < duty, np.minimum(fr, duty - fr), -np.minimum(fr - duty, 1 - fr)); s = np.clip(d / aa + 0.5, 0, 1)
    bright = 1 - jit * h01(n, seed); dark = 0.12 * h01(n, seed + 7)
    return dark + s * (bright - dark), P
