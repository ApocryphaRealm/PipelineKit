"""UV-stretch measure for a SHIPPED mesh (role package-render, 2026-11-12) - pure numpy, imported by Blender and by tests.

Why: Truly Nordic 1.1.0 was posted with the greatsword v4 blade's UVs stretched 2-5x near the tip (a ladder braid). The
design-time check (a design-workspace script of the original, not in the kit) read a work folder's paint dump, so it could not see the mesh that shipped -
and the work mesh (24,546 triangles) was fine: the stretch is in the shipped game NIF (13,898), made from it by the build.
This measure reads only what a NIF holds: per shape its vertices, triangles and UVs, and its base-colour texture's size.

THE MEASURE, per triangle: the map from the triangle's surface (game units) to its texture (pixels) has two singular
values (px per unit along its two principal directions). density = their geometric mean, anisotropy = their ratio.

REGIONS: a NIF splits its vertices at UV seams, so triangles joined through shared vertex indices form one UV ISLAND -
one continuously painted region. An atlas may give islands different densities on purpose (library 13701), so density
is judged only against the island's OWN median. Inside an island only its FACE is judged: the triangles whose normal is
within about 45 degrees (|cos| >= FACE_COS) of the island's principal normal axis (area-weighted; both faces of a plate
painted as one island count) - a planar-projected map squashes the steep walls and bevels it wraps over (the shield
boss's wall, an axe head's edge) on purpose, and nothing carved sits there.
    FAIL  an island whose face holds more than BAD_SHARE of its area at a density over HIGH x or under LOW x its median,
          when that off area is also at least SHAPE_SHARE of the whole shape's surface - a visible stretched patch
    WARN  the same, on a patch under SHAPE_SHARE of the shape (listed on the sheet for the owner's look; not a failure)
Calibrated on the shipped Truly Nordic 1.1.0 (21 unique NIFs): the greatsword blade's two faces have 21% and 8% of
their area off (6.5% and 2.4% of the shape) - FAIL; the next worst patch in the package is 0.22% of its shape (the
dagger's guard) - WARN. (Judging a two-sided island whole failed the battleaxe head on its bevel: 2.3% of the shape.) Anisotropy (absolute, and against the island's own median) is REPORTED, not judged: every thin
bevel is projected at 20-100:1 on purpose, and a limit on it failed every weapon in the package.
"""
import numpy as np

HIGH, LOW = 2.0, 0.5           # the coordinator's threshold: >2x from the median (and its inverse, a squashed region)
BAD_SHARE = 0.03               # share of an island face's area that must be off (noise floor)
SHAPE_SHARE = 0.01             # ...and of the whole shape's surface, for a FAIL
FACE_COS = 0.70
ANISO = 2.0                    # reported only


def wmedian(x, w):
    if len(x) == 0: return float("nan")
    o = np.argsort(x); c = np.cumsum(w[o]); return float(x[o][np.searchsorted(c, 0.5 * c[-1])])


def wpct(x, w, q):
    if len(x) == 0: return float("nan")
    o = np.argsort(x); c = np.cumsum(w[o]); return float(x[o][min(len(x) - 1, np.searchsorted(c, q / 100.0 * c[-1]))])


def islands(tris, nverts):
    """Union-find over shared vertex indices -> island id per triangle."""
    parent = np.arange(max(int(nverts), 1))
    def find(a):
        r = a
        while parent[r] != r: r = parent[r]
        while parent[a] != r: parent[a], a = r, parent[a]
        return r
    for t in tris:
        a, b, c = find(t[0]), find(t[1]), find(t[2])
        parent[b] = a; parent[find(c)] = a
    roots = np.array([find(t[0]) for t in tris]) if len(tris) else np.zeros(0, int)
    _, ids = np.unique(roots, return_inverse=True)
    return ids


def per_triangle(verts, uvs, tris, tex_w, tex_h):
    """(area, density px/unit, anisotropy, ok mask, unit normal) per triangle."""
    V = np.asarray(verts, np.float64); U = np.asarray(uvs, np.float64) * np.array([tex_w, tex_h], np.float64)
    T = np.asarray(tris, np.int64)
    P = V[T]; Q = U[T]
    e1, e2 = P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]
    n = np.cross(e1, e2); nl = np.linalg.norm(n, axis=1); area = 0.5 * nl
    uv_area = 0.5 * np.abs((Q[:, 1, 0] - Q[:, 0, 0]) * (Q[:, 2, 1] - Q[:, 0, 1]) - (Q[:, 2, 0] - Q[:, 0, 0]) * (Q[:, 1, 1] - Q[:, 0, 1]))
    ok = (area > 1e-9) & (uv_area > 1e-9)
    t1 = e1 / np.maximum(np.linalg.norm(e1, axis=1, keepdims=True), 1e-12)
    t2 = np.cross(n, t1); t2 /= np.maximum(np.linalg.norm(t2, axis=1, keepdims=True), 1e-12)
    S = np.stack([np.stack([(e * t1).sum(1), (e * t2).sum(1)], -1) for e in (e1, e2)], 1)      # surface edges (n,2,2)
    W = np.stack([Q[:, 1] - Q[:, 0], Q[:, 2] - Q[:, 0]], 1)                                      # pixel edges (n,2,2)
    den = np.zeros(len(T)); an = np.ones(len(T))
    if ok.any():
        J = np.linalg.solve(S[ok], W[ok])
        sv = np.linalg.svd(J, compute_uv=False)
        den[ok] = np.sqrt(sv[:, 0] * sv[:, 1]); an[ok] = sv[:, 0] / np.maximum(sv[:, 1], 1e-9)
    return area, den, an, ok, n / np.maximum(nl[:, None], 1e-12)


def measure_shape(name, verts, uvs, tris, tex_w, tex_h):
    """The report for one shape: shape median, islands (failures and warnings first) and verdict. '_ratio' holds each
    triangle's density / its island median (1.0 off the judged face), for the heat view."""
    tris = np.asarray(tris, np.int64)
    if len(tris) == 0 or len(uvs) == 0:
        return dict(name=name, triangles=int(len(tris)), verdict="SKIP", why="no triangles or no UVs", islands=[], _ratio=np.ones(len(tris)))
    area, den, an, ok, nrm = per_triangle(verts, uvs, tris, tex_w, tex_h)
    isl = islands(tris, len(verts))
    tot = float(area[ok].sum()) or 1.0
    shape_med = wmedian(den[ok], area[ok])
    out, fails, warns = [], 0, 0
    ratio = np.ones(len(tris))
    V = np.asarray(verts, np.float64)
    for i in np.unique(isl):
        s = ok & (isl == i)
        if not s.any(): continue
        A = float(area[s].sum()); idx = np.where(s)[0]
        # the island's principal normal axis (area-weighted): one face, or the two faces of a plate painted as one island
        C = (area[idx][:, None, None] * nrm[idx][:, :, None] * nrm[idx][:, None, :]).sum(0); axis = np.linalg.eigh(C)[1][:, -1]
        face = idx[np.abs(nrm[idx] @ axis) >= FACE_COS]
        if len(face) == 0: continue
        a = area[face]; d = den[face]; x = an[face]; Af = float(a.sum())
        med = wmedian(d, a); r = d / max(med, 1e-9); ratio[face] = r
        hi = float(a[r > HIGH].sum() / Af); lo = float(a[r < LOW].sum() / Af)
        off_shape = float(a[(r > HIGH) | (r < LOW)].sum() / tot)
        amed = wmedian(x, a); rel = float(a[x / max(amed, 1e-9) > 2.0].sum() / Af)
        why = []
        if hi > BAD_SHARE: why.append(f"{hi:.0%} of the island's face is over {HIGH:g}x its median texel density (max {float(r.max()):.2f}x)")
        if lo > BAD_SHARE: why.append(f"{lo:.0%} of the island's face is under {LOW:g}x its median texel density (min {float(r.min()):.2f}x)")
        verdict = "PASS"
        if why:
            why.append(f"{off_shape:.2%} of the shape's surface")
            if off_shape >= SHAPE_SHARE: verdict = "FAIL"; fails += 1
            else: verdict = "WARN"; warns += 1
        c = (a[:, None] * V[tris[face]].mean(1)).sum(0) / Af
        out.append(dict(island=int(i), triangles=int(len(idx)), face_triangles=int(len(face)), area=round(A, 3), area_share=round(A / tot, 4),
                        median_px_per_unit=round(med, 2), island_over_shape_median=round(med / max(shape_med, 1e-9), 3),
                        p95_over_median=round(wpct(r, a, 95), 3), p5_over_median=round(wpct(r, a, 5), 3),
                        max_over_median=round(float(r.max()), 3), min_over_median=round(float(r.min()), 3),
                        share_over_high=round(hi, 4), share_under_low=round(lo, 4), off_share_of_shape=round(off_shape, 5),
                        anisotropy_p95=round(wpct(x, a, 95), 3), share_anisotropic=round(float(a[x > ANISO].sum() / Af), 4), share_one_way=round(rel, 4),
                        centre=[round(float(v), 2) for v in c], verdict=verdict, why=why))
    rank = {"FAIL": 0, "WARN": 1, "PASS": 2}
    out.sort(key=lambda r: (rank[r["verdict"]], -r["off_share_of_shape"], -r["area_share"]))
    return dict(name=name, triangles=int(len(tris)), texture_px=[int(tex_w), int(tex_h)], area=round(tot, 3),
                median_px_per_unit=round(shape_med, 2), islands_total=len(out), islands_failed=fails, islands_warned=warns,
                verdict="FAIL" if fails else "PASS", islands=out[:12], _ratio=ratio)
