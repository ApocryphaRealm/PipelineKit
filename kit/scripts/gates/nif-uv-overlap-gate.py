"""THE UV OVERLAP GATE (2026-11-16, Truly Nordic Carved Weapons Replacer 1.4.0, the greatsword "notch").

A small dark bar crossed the greatsword's left bevel about mid-blade in both qualities, shipped from 1.1.0 to 1.3.0.
greatsword_v4_build.py had put the lower-guard boss's wall strip at a fixed atlas spot, WALL_UV = (8, 900), "below
everything v3 used", and checked it only against the shelf packer's rows - but the blade was a planar island down the
atlas's left column, outside the packer, so the wall strip sat on the bevel's texels and the painter (last triangle
wins) painted the wall's dark plain metal across the bevel in every map. Every design render showed it as a "notch"
in the steel; nothing looked at the atlas.

The defect class: two DIFFERENT pieces of a shape sharing atlas texels. One texel can only hold one painting, so one
of them shows the other's paint. Sharing that is by design is not a hit: a mirrored back face or a repeated part
reuses the SAME UV triangles (the same three UV corners), which is how "one painting serves both sides" is laid out.

For each BSTriShape (vertex data in the shape; skinned partitions are not read) in every .nif under the package: every
triangle's interior texel centres on a 2048 grid (at least 0.5 texel inside each edge, so neighbours sharing an edge do
not count) are collected; a texel covered by two triangles whose UV corners differ (rounded to 1/4 texel) is an
overlap texel. A shape with more than --min texels (default 24) fails, with the overlap's texel box and the 3D boxes
of the two sides. UVs outside 0..1 (tiling) are skipped. Identical NIFs (same bytes) are read once.

JUDGING (2026-11-16, registered as gate row nif-uv-pieces-do-not-share-texels): a shared-texel pair is only a defect when
it SHOWS - the shared texels' paint (the shape's albedo and normal DDS, found in the package by the texture set's paths
and decoded with texconv) differs by SAME (12/255) or more from either piece's own texels within 3 px beside them. The
war axe's and warhammer's knurl teeth and the lathe rings' edges share uniform plain steel and are listed as
'SAME-PAINT (not a defect)'; the greatsword's wall-on-bevel and the Ebony battle axe's gold rings on the socket fail.
Limit: when the winning piece's paint is uniform AND matches its neighbours, a piece hidden underneath with different
intended paint is not seen (the gate judges what is drawn, not what was meant).

Usage:  python nif-uv-overlap-gate.py --path <package folder> [--min N] [--repo <repo>]      exit 1 on any hit
"""
import argparse, hashlib, os, struct, sys
import numpy as np

G = 2048
TOL = 0.1            # model units: two points this close in a coordinate are the same there
FAR = 1.0            # model units: closer than this, the two pieces are one surface and its own edge (a planar
                     # projection carrying the face's texels over its chamfer or wall) - not a piece from elsewhere


def read_nif(path):
    d = open(path, "rb").read()
    p = d.index(b"\n") + 1
    version, endian, user, nblocks, bsver = struct.unpack_from("<IBIII", d, p); p += 17
    for _ in range(3):
        p += 1 + d[p]
    ntypes, = struct.unpack_from("<H", d, p); p += 2
    types = []
    for _ in range(ntypes):
        n, = struct.unpack_from("<I", d, p); p += 4; types.append(d[p:p + n].decode("latin-1")); p += n
    tidx = struct.unpack_from(f"<{nblocks}H", d, p); p += 2 * nblocks
    sizes = struct.unpack_from(f"<{nblocks}I", d, p); p += 4 * nblocks
    nstr, _ = struct.unpack_from("<II", d, p); p += 8
    strings = []
    for _ in range(nstr):
        n, = struct.unpack_from("<I", d, p); p += 4; strings.append(d[p:p + n].decode("latin-1")); p += n
    ngroups, = struct.unpack_from("<I", d, p); p += 4 + 4 * ngroups
    out = []
    blocks = []
    for i, s in enumerate(sizes):
        blocks.append((types[tidx[i] & 0x7FFF], d[p:p + s])); p += s
    def texpaths(shader_ref):
        """slot 0 (albedo) and slot 1 (normal) of the shape's BSLightingShaderProperty's texture set ('' when absent)"""
        try:
            t, b = blocks[shader_ref]
            if t != "BSLightingShaderProperty":
                return "", ""
            o = 8; nex = struct.unpack_from("<I", b, o)[0]; o += 4 + 4 * nex + 4 + 8 + 16      # Skyrim: shader type, then NiObjectNET
            ts = struct.unpack_from("<i", b, o)[0]
            t2, b2 = blocks[ts]
            if t2 != "BSShaderTextureSet":
                return "", ""
            n = struct.unpack_from("<i", b2, 0)[0]; o = 4; got = []
            for _ in range(min(n, 2)):
                ln = struct.unpack_from("<I", b2, o)[0]; o += 4; got.append(b2[o:o + ln].decode("latin-1").strip("\x00")); o += ln
            return (got + ["", ""])[:2]
        except Exception:
            return "", ""
    for i, (tname, blk) in enumerate(blocks):
        if tname != "BSTriShape" or bsver < 100:
            continue
        ni = struct.unpack_from("<i", blk, 0)[0]; name = strings[ni] if 0 <= ni < len(strings) else f"block{i}"
        o = 4; nex = struct.unpack_from("<I", blk, o)[0]; o += 4 + 4 * nex + 4          # NiObjectNET
        o += 4 + 12 + 36 + 4 + 4                                                          # NiAVObject
        q = o + 28                                                                       # bound, skin, shader, alpha
        if q + 16 > len(blk):
            continue
        desc = struct.unpack_from("<Q", blk, q)[0]; ntri, nv = struct.unpack_from("<HH", blk, q + 8); size = struct.unpack_from("<I", blk, q + 12)[0]
        fl = desc >> 44
        if not size or not (fl & 0x2):
            continue
        stride = (desc & 0xF) * 4; ou = ((desc >> 8) & 0xF) * 4; vd = q + 16
        if size != nv * stride + ntri * 6:
            continue
        raw = np.frombuffer(blk, np.uint8, nv * stride, vd).reshape(nv, stride)
        uv = raw[:, ou:ou + 4].copy().view(np.float16).reshape(nv, 2).astype(np.float64)
        pos = raw[:, 0:12].copy().view(np.float32).reshape(nv, 3).astype(np.float64)
        F = np.frombuffer(blk, np.uint16, ntri * 3, vd + nv * stride).reshape(-1, 3).astype(np.int64)
        shader = struct.unpack_from("<i", blk, o + 20)[0]
        out.append((name, pos, uv, F, texpaths(shader) if shader >= 0 else ("", "")))
    return out


def islands(F, nv):
    par = np.arange(nv)
    def find(i):
        while par[i] != i:
            par[i] = par[par[i]]; i = par[i]
        return i
    for a, b, c in F:
        ra, rb, rc = find(a), find(b), find(c)
        par[rb] = ra; par[find(rc)] = ra
    root = np.array([find(i) for i in range(nv)])
    return root[F[:, 0]]


def overlap(pos, uv, F, min_tex):
    """Islands (UV pieces joined by shared vertices) that share texels and are neither copies of each other (their UV
    corners coincide) nor mirror images (the shared texel lands on the same 3D point, or on its mirror through an axis
    plane). Sliver triangles count: a texel centre inside any triangle of the piece is the piece's."""
    U = uv[F] * G; P = pos[F]
    ok = np.isfinite(U).all((1, 2)) & (U.min((1, 2)) >= -0.5) & (U.max((1, 2)) <= G + 0.5)
    isl = islands(F, len(uv))
    texs, tris, pts = [], [], []
    for t in np.where(ok)[0]:
        (ax, ay), (bx, by), (cx, cy) = U[t]
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-6:
            continue
        x0, x1 = int(max(0, np.floor(min(ax, bx, cx) - 0.5))), int(min(G - 1, np.ceil(max(ax, bx, cx))))
        y0, y1 = int(max(0, np.floor(min(ay, by, cy) - 0.5))), int(min(G - 1, np.ceil(max(ay, by, cy))))
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        w0 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / den
        w1 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / den
        w2 = 1 - w0 - w1
        m = (w0 > 1e-9) & (w1 > 1e-9) & (w2 > 1e-9)
        if not m.any():
            continue
        idx = ((gy[m] - 0.5).astype(np.int64) * G + (gx[m] - 0.5).astype(np.int64))
        p3 = w0[m][:, None] * P[t, 0] + w1[m][:, None] * P[t, 1] + w2[m][:, None] * P[t, 2]
        texs.append(idx); tris.append(np.full(len(idx), t)); pts.append(p3)
    if not texs:
        return []
    tex = np.concatenate(texs); tri = np.concatenate(tris); pt = np.concatenate(pts)
    o = np.argsort(tex, kind="stable"); tex, tri, pt = tex[o], tri[o], pt[o]
    start = np.r_[True, tex[1:] != tex[:-1]]; first = np.where(start)[0]; gid = np.cumsum(start) - 1
    fi = first[gid]; ia, ib = isl[tri[fi]], isl[tri]
    other = ia != ib
    if not other.any():
        return []
    d = np.abs(pt - pt[fi]); mirror = ((d < TOL).sum(1) >= 2) | (np.linalg.norm(pt - pt[fi], axis=1) < FAR)
    pa, pb_, mi, tx = ia[other], ib[other], mirror[other], tex[other]
    hits = []
    pairs = {}
    for a_, b_, m_, x_ in zip(pa.tolist(), pb_.tolist(), mi.tolist(), tx.tolist()):
        k = (min(a_, b_), max(a_, b_)); e = pairs.setdefault(k, [0, 0, []]); e[0] += 1; e[1] += m_
        e[2].append(x_)
    vert_isl = np.full(len(uv), -1); vert_isl[F[:, 0]] = isl; vert_isl[F[:, 1]] = isl; vert_isl[F[:, 2]] = isl
    for (a_, b_), (n_, nm, xs) in pairs.items():
        if n_ <= min_tex or nm >= 0.5 * n_:
            continue
        va = np.unique(np.round(uv[vert_isl == a_] * G * 2).astype(np.int64), axis=0)
        vb = np.unique(np.round(uv[vert_isl == b_] * G * 2).astype(np.int64), axis=0)
        small, big = (va, vb) if len(va) <= len(vb) else (vb, va)
        bigset = set(map(tuple, big.tolist()))
        same = sum(1 for r in small.tolist() if tuple(r) in bigset) / max(1, len(small))
        if same >= 0.25:                  # a copy of the same UV piece (a repeated or rotated part)
            continue
        xs = np.array(xs); ys_, xs_ = xs // G, xs % G
        ta = isl == a_; tb = isl == b_
        hits.append(dict(texels=int(n_), box=(int(xs_.min()), int(ys_.min()), int(xs_.max()), int(ys_.max())),
                         a_y=(round(float(P[ta][:, :, 1].min()), 2), round(float(P[ta][:, :, 1].max()), 2)), a_tris=int(ta.sum()),
                         b_y=(round(float(P[tb][:, :, 1].min()), 2), round(float(P[tb][:, :, 1].max()), 2)), b_tris=int(tb.sum()), same=round(same, 2),
                         S=np.unique(xs), TA=np.unique(tex[isl[tri] == a_]), TB=np.unique(tex[isl[tri] == b_])))
    return hits

TEXCONV = os.environ.get("TEXCONV") or __import__("shutil").which("texconv")   # kit: TEXCONV, then texconv on PATH (Microsoft DirectXTex, not shipped)
SAME = 12.0          # 0-255: the shared texels' mean differs from the piece's own texels beside them by less than this
_TEXIDX, _TEXCACHE = {}, {}


def _tex_index(root):
    if root not in _TEXIDX:
        idx = {}
        for dp, _, fs in os.walk(root):
            for f in fs:
                if f.lower().endswith(".dds"):
                    full = os.path.join(dp, f); low = full.lower().replace("/", "\\")
                    k = low.find("\\textures\\")
                    if k >= 0:
                        idx.setdefault(low[k + 1:], full)
        _TEXIDX[root] = idx
    return _TEXIDX[root]


def _load_tex(rel, root):
    """the DDS a shape names, found in the package and decoded to an RGB array (texconv -> PNG in %TEMP%), or None"""
    rel = rel.lower().replace("/", "\\").lstrip("\\")
    if not rel.startswith("textures\\"):
        rel = "textures\\" + rel
    full = _tex_index(root).get(rel)
    if not full:
        return None
    if full in _TEXCACHE:
        return _TEXCACHE[full]
    import subprocess, tempfile
    from PIL import Image
    h = hashlib.md5(open(full, "rb").read()).hexdigest()
    out = os.path.join(tempfile.gettempdir(), "nif-uv-overlap-gate", h); os.makedirs(out, exist_ok=True)
    png = os.path.join(out, os.path.splitext(os.path.basename(full))[0] + ".png")
    if not os.path.exists(png) and TEXCONV:
        subprocess.run([TEXCONV, "-nologo", "-y", "-ft", "png", "-f", "R8G8B8A8_UNORM", "-o", out, full], capture_output=True)
    arr = np.asarray(Image.open(png).convert("RGB"), np.float32) if os.path.exists(png) else None
    _TEXCACHE[full] = arr
    return arr


def judge(h, tp, root):
    """Is the overlap visible? Two pieces sharing texels show a defect when the shared texels' paint differs from the
    paint of either piece's OWN texels right beside them (the greatsword: wall-dark 13 inside the bevel's bright 151).
    When the shared texels carry the same paint as both pieces' neighbouring texels (uniform plain metal - the knurl
    teeth of the war axe and warhammer laid on plain steel, a lathe ring's edge on brushed steel) nothing shows.
    Returns 'same paint ...' (benign), or a reason it is a hit."""
    maps = [m for m in (_load_tex(tp[0], root) if tp[0] else None, _load_tex(tp[1], root) if tp[1] else None) if m is not None]
    if not maps:
        return "no texture found to judge it"
    from scipy import ndimage
    S = np.zeros((G, G), bool); S.flat[h["S"]] = True
    TA = np.zeros((G, G), bool); TA.flat[h["TA"]] = True
    TB = np.zeros((G, G), bool); TB.flat[h["TB"]] = True
    near = ndimage.binary_dilation(S, iterations=3)
    worst, sides = 0.0, 0
    for T in (TA, TB):
        ring = near & T & ~S
        if ring.sum() < 4:
            continue
        sides += 1
        for m in maps:
            Hm, Wm = m.shape[:2]
            def val(mask):
                yy, xx = np.nonzero(mask)
                yi = np.clip(((yy + 0.5) / G * Hm).astype(int), 0, Hm - 1); xi = np.clip(((xx + 0.5) / G * Wm).astype(int), 0, Wm - 1)
                return m[yi, xi].mean(0)
            worst = max(worst, float(np.abs(val(S) - val(ring)).max()))
    if not sides:
        return "no texels of either piece beside the shared ones to compare"
    if worst < SAME:
        return f"same paint (largest channel difference {worst:.1f}/255 against the pieces' own texels beside it)"
    return f"paint differs by {worst:.0f}/255 from the pieces' own texels beside it"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True); ap.add_argument("--repo"); ap.add_argument("--min", type=int, default=24)
    a = ap.parse_args()
    seen, hits, n, benign = {}, [], 0, []
    for dp, _, fs in os.walk(a.path):
        for f in fs:
            if not f.lower().endswith(".nif"):
                continue
            p = os.path.join(dp, f); h = hashlib.md5(open(p, "rb").read()).hexdigest()
            if h in seen:
                continue
            seen[h] = p; n += 1
            try:
                shapes = read_nif(p)
            except Exception as e:
                print(f"WARN: {os.path.relpath(p, a.path)}: not read ({e})"); continue
            for name, pos, uv, F, tp in shapes:
                if "blood" in name.lower():      # the game's blood decals: vanilla's shared, tiled blood atlas
                    continue
                for h in overlap(pos, uv, F, a.min):
                    verdict = judge(h, tp, a.path)
                    if verdict.startswith("same paint"):
                        benign.append(f"{os.path.relpath(p, a.path)} :: {name}: {h['texels']} texels, box {h['box']}: {verdict}"); continue
                    hits.append(f"[{verdict}] " +f"{os.path.relpath(p, a.path)} :: {name}: {h['texels']} texels shared by two different UV pieces, atlas px "
                                f"box {h['box']} (of {G}); piece A {h['a_tris']} tris at 3D y {h['a_y']}, piece B {h['b_tris']} tris at "
                                f"3D y {h['b_y']} (UV corners in common {h['same']})")
    for b in benign[:40]:
        print("SAME-PAINT (not a defect):", b)
    if benign:
        print(f"note: {len(benign)} shared-texel pair(s) carry the same paint as the pieces' own texels beside them (uniform plain metal) - not a defect")
    for h in hits:
        print("HIT:", h)
    if hits:
        print(f"FAIL: {len(hits)} shape(s) paint two different pieces into the same texels ({n} distinct NIFs read). Move one "
              f"piece to free atlas space (and its texels with it), then rebuild."); sys.exit(1)
    print(f"OK: no shape shares atlas texels between different UV pieces ({n} distinct NIFs read, threshold {a.min} texels)")


if __name__ == "__main__":
    main()
