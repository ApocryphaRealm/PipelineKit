r"""nif-readback.py - read back built Skyrim SE NIFs before anything is rendered or packaged (role nif-readback,
2026-11-18). numpy only: no Blender, no third-party NIF library (niflib.py and winding.py beside it are our own).

Generalised from the read-back checks two of our weapon builds ran on every NIF they wrote (Truly Nordic Carved Weapons
Replacer and Nordic Ebony Armor and Weapons Replacer): each fault below shipped once, or nearly did, because every
review render looked fine.

    py -3 nif-readback.py <folder or .nif> [...] [--tex-prefix textures\mymod] [--data-root <dir>] [--external <prefix>]
                          [--truepbr] [--see-through-max 0.004] [--lost-uv-max 0.01] [--smooth-deg 40] [--json <out>]
    py -3 nif-readback.py --self-test

OURS: a shape is one of ours when any path of its texture set starts with a --tex-prefix (case and slashes ignored);
with no --tex-prefix every lit shape but the blood decals is ours. A shape that is not ours is listed, never failed (a
vanilla part kept).
CALIBRATION: our Nordic Ebony mace reads 0 lost UVs, 0 bad tangents, 0 smoothed edges and see-through 0.47 %. A mesh
UV-mapped by a PLANAR projection gives the walls it wraps over (nearly) no UV area by design; raise --lost-uv-max for it
rather than reading those walls as lost UVs.

FAILS (exit 1), per shape of ours unless said otherwise:
  refs          a block reference that points outside the file (every shape, every block whose layout niflib knows)
  skinned flag  a skinned shape whose shader lacks SLSF1 Skinned (0x2), or a rigid one that has it - draws nothing
                (every lit shape: the invisible bow)
  textures      a texture path that resolves to no file under the data roots (the folder holding the NIF's meshes\, its
                siblings that hold textures\, every --data-root) unless it starts with an --external prefix
                (default textures\cubemaps\, the game's own)
  truepbr       (--truepbr) the shape is not a TruePBR shape: default shader type, the TruePBR bit, slots 0, 1 and 5
  lost UVs      more than --lost-uv-max of the surface (by 3D area) on faces with no UV area - draws one texel, black and
                flat in game; or a tangent / bitangent that is not a unit vector
  hard edges    a face whose three vertex normals all lean more than --smooth-deg off the face - a hard edge smoothed
                over (one normal per vertex), which lights a sharp tooth as a flat disc
  see-through   (--see-through-max) more than that share of rays at our shapes meet a back face first and no front face
                after - the game culls back faces, so the light behind shows through; always reported
  winding       an edge walked the same way by both its faces, or a surface whose back sees out more than its front
                (winding.py's ray vote, in each shape's world frame; two-sided caps are left out of the vote; a sheath
                shape named Scb is voted on its own)
WARNS (exit 0): a shape whose vertex data cannot be read (another vertex layout, a strip partition), a non-lit shape.
Identical NIFs (same bytes) are read once.
"""
import argparse, hashlib, json, math, os, struct, sys, tempfile
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import niflib, winding   # noqa: E402

EXTERNAL = ("textures\\cubemaps\\",)
SHEATH = "Scb"


def norm(p): return (p or "").replace("/", "\\").lstrip("\\").lower()


# ---- the shape's data ---------------------------------------------------------------------------------------------

def shape_refs(n, b):
    o = n.av_end(b, 0, [], []); return struct.unpack_from("<3i", n.blocks[b], o + 16)   # skin, shader, alpha


def shader_info(n, sh):
    """(shader type, flags1, flags2, texture paths) of a BSLightingShaderProperty"""
    blk = n.blocks[sh]; f1, f2 = struct.unpack_from("<II", blk, n.net_end(sh, 4, [], []))
    typ = struct.unpack_from("<I", blk, 0)[0]
    ts = n.i32(sh, n.ref_offsets(sh)[0][-1]); paths = []
    if 0 <= ts < len(n.blocks) and n.btypes[ts] == "BSShaderTextureSet":
        tb = n.blocks[ts]; k = struct.unpack_from("<I", tb, 0)[0]; q = 4
        for _ in range(k):
            L = struct.unpack_from("<I", tb, q)[0]; paths.append(tb[q + 4:q + 4 + L].decode("latin-1")); q += 4 + L
    return typ, f1, f2, paths


def parent_map(n):
    par = {}
    for p, t in enumerate(n.btypes):
        if t in niflib.NODES:
            for c in n.children(p)[0]:
                if c >= 0: par.setdefault(c, p)
    return par


def world_xf(n, b, par):
    R, t, cur = np.eye(3), np.zeros(3), b
    while cur is not None:
        _, tl, rl, sl = n.transform(cur); Rl = np.array(rl, np.float64).reshape(3, 3)
        R, t = Rl @ R * sl, Rl @ t * sl + np.array(tl); cur = par.get(cur)
    return R, t


def vertex_block(n, b):
    """(raw vertex bytes (nv, stride), vertex attribute flags, desc, triangles) of a BSTriShape - from the shape, or
    from its NiSkinPartition's global buffer (SSE) when the shape holds none. None when there is nothing to read."""
    o = n.av_end(b, 0, [], []); blk = n.blocks[b]; q = o + 28
    desc = struct.unpack_from("<Q", blk, q)[0]; ntri, nv = struct.unpack_from("<HH", blk, q + 8); size = struct.unpack_from("<I", blk, q + 12)[0]
    sk = struct.unpack_from("<i", blk, o + 16)[0]
    if size:
        stride = (desc & 0xF) * 4
        raw = np.frombuffer(bytes(blk[q + 16:q + 16 + nv * stride]), np.uint8).reshape(nv, stride)
        F = np.frombuffer(bytes(blk[q + 16 + nv * stride:q + 16 + nv * stride + ntri * 6]), np.uint16).reshape(-1, 3).astype(np.int64)
        return raw, desc >> 44, desc, F
    if sk < 0: return None
    part = struct.unpack_from("<i", n.blocks[sk], 4)[0]; pb = n.blocks[part]
    _, dsize, stride = struct.unpack_from("<III", pb, 0); desc = struct.unpack_from("<Q", pb, 12)[0]
    if not stride: return None
    raw = np.frombuffer(bytes(pb[20:20 + dsize]), np.uint8).reshape(-1, stride)
    F = winding._tris_from_shape(n, b)[1]
    return raw, desc >> 44, desc, F


def surface_frame(n, b, smooth_deg):
    """UV and tangent-frame health of one shape: the share (by 3D area) of faces with NO UV area, the vertices whose
    tangent or bitangent is not a unit vector, and the faces whose three vertex normals all lean more than smooth_deg
    off the face. Reads the vertex layout from the shape's own descriptor (SSE: position always 3 floats)."""
    vb = vertex_block(n, b)
    if vb is None: return {"unread": "no vertex data in the shape and no skin partition"}
    raw, fl, desc, F = vb
    if not (fl & 0x1) or not (fl & 0x2) or not (fl & 0x8):
        return {"unread": "vertex layout without position, UV or normal (flags %s)" % hex(fl)}
    if len(F) == 0: return {"unread": "no triangles"}
    uv_o, nrm_o, tan_o = ((desc >> 8) & 0xF) * 4, ((desc >> 16) & 0xF) * 4, ((desc >> 20) & 0xF) * 4
    P = raw[:, 0:12].copy().view(np.float32).astype(np.float64)
    U = raw[:, uv_o:uv_o + 4].copy().view(np.float16).astype(np.float64)
    Nb = raw[:, nrm_o:nrm_o + 4].astype(np.float64) / 127.5 - 1
    a3 = 0.5 * np.linalg.norm(np.cross(P[F[:, 1]] - P[F[:, 0]], P[F[:, 2]] - P[F[:, 0]]), axis=1)
    d1, d2 = U[F[:, 1]] - U[F[:, 0]], U[F[:, 2]] - U[F[:, 0]]; auv = 0.5 * np.abs(d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0])
    real = a3 > 1e-6
    if not real.any(): return {"unread": "every face has no area"}
    dens = auv / np.maximum(a3, 1e-12); med = np.median(dens[real])
    flat = real & (dens < med * 1e-3)
    bad_t = 0
    if fl & 0x10:                                                 # tangents: bitangent x (float), y (normal w), z (tangent w)
        Tb = raw[:, tan_o:tan_o + 4].astype(np.float64) / 127.5 - 1
        bx = raw[:, 12:16].copy().view(np.float32)[:, 0].astype(np.float64)
        T = Tb[:, :3]; Bt = np.stack([bx, Nb[:, 3], Tb[:, 3]], 1)
        bad_t = int(((np.abs(np.linalg.norm(T, axis=1) - 1) > 0.1) | (np.abs(np.linalg.norm(Bt, axis=1) - 1) > 0.1)).sum())
    g = np.cross(P[F[:, 1]] - P[F[:, 0]], P[F[:, 2]] - P[F[:, 0]]); g = g / np.maximum(np.linalg.norm(g, axis=1), 1e-12)[:, None]
    Nn = Nb[:, :3] / np.maximum(np.linalg.norm(Nb[:, :3], axis=1), 1e-9)[:, None]
    smoothed = (np.einsum("fkj,fj->fk", Nn[F], g).max(1) < math.cos(math.radians(smooth_deg))) & real
    return {"faces": int(len(F)), "no_uv_area_share": round(float(a3[flat].sum() / a3.sum()), 4), "no_uv_area_faces": int(flat.sum()),
            "bad_tangent_frames": bad_t, "tangents": bool(fl & 0x10), "smoothed_over_hard_edges": int(smoothed.sum()),
            "uv_range": [np.round(U.min(0), 4).tolist(), np.round(U.max(0), 4).tolist()]}


# ---- rays: see-through and winding ----------------------------------------------------------------------------------

def two_sided(W, ok):
    """faces with a reversed twin on the same three welded points - a two-sided cap: no inside to face, so it is left
    out of the facing-in vote (it still blocks rays)"""
    tw = np.zeros(len(W), bool); seen = {}
    for i in np.where(ok)[0]:
        a, b, c = (int(x) for x in W[i]); k = tuple(sorted((a, b, c)))
        r = min(((a, b, c), (b, c, a), (c, a, b)))
        for j, rj in seen.get(k, []):
            if rj != r: tw[i] = tw[j] = True
        seen.setdefault(k, []).append((i, r))
    return tw


def see_through(solids, rays=1500, seed=11, chunk=48):
    """solids: [(name, world triangles, ours)]. The share of rays, aimed at points on our shapes from every side, whose
    first surface is one of ours and a BACK face, with no FRONT face anywhere after it. None when nothing is ours."""
    rng = np.random.default_rng(seed)
    T = [t for _, t, _ in solids if len(t)]
    if not T: return None
    own = np.concatenate([np.full(len(t), o) for _, t, o in solids if len(t)]); T = np.concatenate(T)
    if not own.any(): return None
    tgt = T[own].mean(1); tgt = tgt[rng.choice(len(tgt), rays)]
    D = rng.normal(size=(rays, 3)); D /= np.linalg.norm(D, axis=1, keepdims=True); O = tgt - D * 200.0
    v0, e1, e2 = T[:, 0], T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]; nrm = np.cross(e1, e2)
    first_ours, through = 0, 0
    for s0 in range(0, rays, chunk):
        o = O[s0:s0 + chunk, None]; d = D[s0:s0 + chunk, None]
        p = np.cross(d, e2[None]); det = np.einsum("rtk,tk->rt", p, e1); good = np.abs(det) > 1e-12
        inv = np.where(good, 1 / np.where(good, det, 1), 0); tv = o - v0[None]; u = np.einsum("rtk,rtk->rt", tv, p) * inv
        q = np.cross(tv, e1[None]); v = np.einsum("rtk,rtk->rt", d, q) * inv; t = np.einsum("tk,rtk->rt", e2, q) * inv
        t = np.where(good & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-4), t, np.inf)
        tmin = t.min(1); j = t.argmin(1); hit = np.isfinite(tmin)
        front = np.einsum("tk,rk->rt", nrm, D[s0:s0 + chunk]) < 0
        first_front = front[np.arange(len(j)), j]
        anyfront = (np.isfinite(t) & front).any(1)
        mine = hit & own[j] & ~first_front
        first_ours += int((hit & own[j]).sum()); through += int((mine & ~anyfront).sum())
    return round(through / max(1, first_ours), 4)


def winding_world(shapes, ours, seed=7):
    """shapes: {block: (name, world vertices, faces)}. Per shape of ours: edges against a neighbour and surfaces facing
    in (winding.py), voted against every solid shape (a sheath on its own)."""
    rng = np.random.default_rng(seed)
    def tris(bs): return np.concatenate([shapes[b][1][shapes[b][2]] for b in bs]) if bs else np.zeros((0, 3, 3))
    solid = [b for b, (nm, _, _) in shapes.items() if "blood" not in nm.lower() and nm != SHEATH]
    rows, faults = [], 0
    for b, (nm, V, F) in shapes.items():
        if not ours(nm): continue
        Wd, ok = winding._weld(V, F); tw = two_sided(Wd, ok); bad, _ = winding.edges_against(Wd, ok)
        ok = ok & ~tw; _, pairs = winding.edges_against(Wd, ok)
        T = tris([b] if nm == SHEATH else sorted(set(solid) | {b})); inward = []
        for cp in winding.components(len(F), pairs, ok):
            front, back = winding.outward_vote(V, F, cp, T, rng)
            if back > front + 0.15 and back > 0.25: inward.append((len(cp), round(front, 2), round(back, 2)))
        faults += bad + len(inward)
        rows.append({"shape": nm, "faces": int(ok.sum()), "two_sided_faces": int(tw.sum()), "edges_against_neighbour": bad,
                     "surfaces_facing_in": len(inward), "facing_in": inward[:4]})
    return rows, faults


# ---- one NIF ----------------------------------------------------------------------------------------------------------

def data_roots(nif_path, top, extra):
    """where a shape's texture paths are looked up: the folder holding the NIF's meshes\\, then every folder under the
    target that holds textures\\ (a package's Common and option folders), then --data-root"""
    parts = os.path.abspath(nif_path).split(os.sep); low = [x.lower() for x in parts]
    roots = []
    if "meshes" in low:
        i = len(low) - 1 - low[::-1].index("meshes"); roots.append(os.sep.join(parts[:i]) or os.sep)
    for dp, dns, _ in os.walk(top):
        if any(d.lower() == "textures" for d in dns) and dp not in roots: roots.append(dp)
    return roots + [r for r in extra if r not in roots]


def check_nif(path, a, roots):
    n = niflib.Nif(path); faults, warns, rows = [], [], []
    for b in range(len(n.blocks)):                                  # every reference inside the file
        try: refs, _ = n.ref_offsets(b)
        except (NotImplementedError, struct.error): continue
        for o in refs:
            r = n.i32(b, o)
            if r >= len(n.blocks): faults.append(f"block {b} ({n.btypes[b]}) refers to block {r}, past the last ({len(n.blocks) - 1})")
    par = parent_map(n); shapes = {}; ours_names = set(); solids = []
    prefixes = tuple(norm(p).rstrip("\\") + "\\" for p in a.tex_prefix)
    external = tuple(norm(p) for p in (a.external or EXTERNAL))
    for b, t in enumerate(n.btypes):
        if t in ("BSDynamicTriShape", "BSSubIndexTriShape", "NiTriShape", "NiTriStrips"):
            warns.append(f"{n.name(b) if niflib.has_net(t) else b}: {t} is not read (only BSTriShape)"); continue
        if t != "BSTriShape": continue
        nm = n.name(b) or f"shape{b}"
        sk, sh, al = shape_refs(n, b)
        if any(r >= len(n.blocks) for r in (sk, sh, al)): faults.append(f"{nm}: a skin / shader / alpha reference outside the file"); continue
        try:
            V, F = winding._tris_from_shape(n, b); R, tr = world_xf(n, b, par)
            if len(F): shapes[b] = (nm, (V @ R.T) + tr, F)
        except (AssertionError, struct.error, ValueError) as e:
            warns.append(f"{nm}: geometry not read ({e})")
        row = {"shape": nm}
        if sh < 0 or n.btypes[sh] != "BSLightingShaderProperty":
            row["shader"] = n.btypes[sh] if sh >= 0 else None; rows.append(row); continue
        typ, f1, f2, paths = shader_info(n, sh)
        pbr = bool(f2 & 0x00800000)
        row.update(shader_type=typ, flags=[f"{f1:08x}", f"{f2:08x}"], truepbr=pbr, skinned=sk >= 0, textures=paths)
        if (sk >= 0) != bool(f1 & 0x2):
            faults.append(f"{nm}: SLSF1 Skinned is {'off' if sk >= 0 else 'on'} but the shape is {'skinned' if sk >= 0 else 'rigid'} - it draws nothing")
        # no --tex-prefix: every lit shape but the blood decals (they wear the game's own blood textures)
        mine = (not prefixes and "blood" not in nm.lower()) or (bool(prefixes) and any(norm(p).startswith(prefixes) for p in paths if p))
        row["ours"] = mine
        if "blood" not in nm.lower(): solids_entry = (nm, shapes[b][1][shapes[b][2]] if b in shapes else np.zeros((0, 3, 3)), mine and nm != SHEATH)
        else: solids_entry = None
        if solids_entry: solids.append(solids_entry)
        if not mine: rows.append(row); continue
        ours_names.add(nm)
        missing = [p for p in paths if p and not norm(p).startswith(external)
                   and not any(os.path.isfile(os.path.join(r, norm(p) if norm(p).startswith("textures\\") else "textures\\" + norm(p))) for r in roots)]
        row["missing_textures"] = missing
        for p in missing: faults.append(f"{nm}: texture {p} is in no data root ({len(roots)} looked in)")
        if a.truepbr:
            slots = [i for i, x in enumerate(paths) if x]
            if typ != 0 or not pbr or not all(s in slots for s in (0, 1, 5)):
                faults.append(f"{nm}: not a TruePBR shape (shader type {typ}, TruePBR bit {pbr}, slots used {slots}; want type 0, the bit, slots 0 1 5)")
        if "blood" in nm.lower(): rows.append(row); continue
        try: sf = surface_frame(n, b, a.smooth_deg)
        except (struct.error, ValueError) as e: sf = {"unread": str(e)}
        row["surface"] = sf
        if "unread" in sf: warns.append(f"{nm}: UVs and tangent frames not read - {sf['unread']}")
        else:
            if sf["no_uv_area_share"] > a.lost_uv_max:
                faults.append(f"{nm}: {sf['no_uv_area_share']:.1%} of the surface ({sf['no_uv_area_faces']} faces) has no UV area - lost UVs draw black and flat")
            if sf["bad_tangent_frames"]:
                faults.append(f"{nm}: {sf['bad_tangent_frames']} vertices with a tangent or bitangent that is not a unit vector")
            if sf["smoothed_over_hard_edges"]:
                faults.append(f"{nm}: {sf['smoothed_over_hard_edges']} faces whose vertex normals all lean over {a.smooth_deg:g} deg off them - a hard edge smoothed over")
        rows.append(row)
    st = see_through(solids)
    if st is not None and a.see_through_max is not None and st > a.see_through_max:
        faults.append(f"light through the mesh: {st:.2%} of the rays at our shapes meet a back face first and no front face after (limit {a.see_through_max:.2%})")
    wrows, wf = winding_world(shapes, lambda nm: nm in ours_names)
    for r in wrows:
        if r["edges_against_neighbour"] or r["surfaces_facing_in"]:
            faults.append(f"{r['shape']}: winding - {r['edges_against_neighbour']} edge(s) against a neighbour, {r['surfaces_facing_in']} surface(s) facing in {r['facing_in']}")
    return {"shapes": rows, "winding": wrows, "see_through_share": st, "faults": faults, "warnings": warns}


def run(a):
    seen, report, bad, n_nif = {}, {}, 0, 0
    for target in a.targets:
        files = [target] if os.path.isfile(target) else [os.path.join(dp, f) for dp, _, fs in os.walk(target) for f in fs if f.lower().endswith(".nif")]
        top = os.path.dirname(target) if os.path.isfile(target) else target
        for p in sorted(files):
            h = hashlib.md5(open(p, "rb").read()).hexdigest()
            rel = os.path.relpath(p, top)
            if h in seen: print(f"== {rel}: same bytes as {seen[h]} (read once)"); continue
            seen[h] = rel; n_nif += 1
            try: r = check_nif(p, a, data_roots(p, top, a.data_root))
            except Exception as e:
                r = {"faults": [f"not readable as an SSE NIF ({type(e).__name__}: {e})"], "warnings": [], "shapes": []}
            report[rel] = r; bad += len(r["faults"])
            print(f"== {rel}: {len(r['shapes'])} shape(s), see-through {r.get('see_through_share')}, "
                  f"{'PASS' if not r['faults'] else 'FAIL ' + str(len(r['faults']))}")
            for s in r["shapes"]:
                if s.get("shader") is not None or "truepbr" not in s:
                    print(f"   {s['shape']}: {s.get('shader')} (not a lit shape - listed)"); continue
                sf = s.get("surface") or {}
                print(f"   {s['shape']}: type {s['shader_type']} flags {s['flags'][0]} {s['flags'][1]} TruePBR {s['truepbr']} "
                      f"{'skinned ' if s['skinned'] else ''}{'ours' if s.get('ours') else 'not ours (listed)'}"
                      + (f"; lost-UV {sf.get('no_uv_area_share')}, bad tangents {sf.get('bad_tangent_frames')}, smoothed {sf.get('smoothed_over_hard_edges')}" if sf and "unread" not in sf else ""))
            for f in r["faults"]: print("   FAIL " + f)
            for w in r["warnings"]: print("   warn " + w)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f: json.dump(report, f, indent=1, default=str)
    if n_nif == 0:
        print("RESULT: no .nif found - nothing read is not a pass"); return 1
    print(f"RESULT {n_nif} NIF(s):", "PASS" if bad == 0 else f"FAIL {bad}")
    return 1 if bad else 0


def parse(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("targets", nargs="*"); ap.add_argument("--tex-prefix", action="append", default=[])
    ap.add_argument("--data-root", action="append", default=[]); ap.add_argument("--external", action="append", default=[])
    ap.add_argument("--truepbr", action="store_true"); ap.add_argument("--see-through-max", type=float, default=None)
    ap.add_argument("--lost-uv-max", type=float, default=0.01); ap.add_argument("--smooth-deg", type=float, default=40.0)
    ap.add_argument("--json"); ap.add_argument("--self-test", action="store_true")
    return ap.parse_args(argv)


def self_test():
    """The parts that need no NIF file: the ray tests on synthetic geometry (our own numbers, no game mesh)."""
    res = {}
    # a closed cube wound outward, and the same cube with one face pair flipped inward
    Vc = np.array([[x, y, z] for x in (0, 1) for y in (0, 1) for z in (0, 1)], float)
    quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    def tri(qs):
        F = []
        for a_, b_, c_, d_ in qs: F += [(a_, b_, c_), (a_, c_, d_)]
        return np.array(F, np.int64)
    F = tri(quads)
    c = Vc[F].mean(1) - 0.5; nrm = np.cross(Vc[F][:, 1] - Vc[F][:, 0], Vc[F][:, 2] - Vc[F][:, 0])
    if (np.einsum("ij,ij->i", c, nrm) < 0).any(): F = F[:, ::-1]                          # make every face point out
    rows, f = winding_world({0: ("cube", Vc, F)}, lambda nm: True); res["closed cube: no winding fault"] = (f, 0)
    G = F.copy(); G[:2] = G[:2, ::-1]
    rows, f = winding_world({0: ("cube", Vc, G)}, lambda nm: True); res["one face flipped: winding fault"] = (1 if f else 0, 1)
    res["closed cube: no light through"] = (1 if (see_through([("cube", Vc[F], True)]) or 0) > 0.004 else 0, 0)
    open_ = F[2:]                                                                          # two triangles gone: a hole
    res["open cube: light through"] = (1 if (see_through([("cube", Vc[open_], True)]) or 0) > 0.004 else 0, 1)
    W = np.array([[0, 1, 2], [2, 1, 0]]); ok = np.array([True, True]); res["two-sided cap found"] = (int(two_sided(W, ok).sum()), 2)
    ok_ = all(g == w for g, w in res.values())
    print("self-test", "PASS" if ok_ else "FAIL", {k: f"{g} (want {w})" for k, (g, w) in res.items()})
    return 0 if ok_ else 1


def main(argv):
    a = parse(argv)
    if a.self_test: return self_test()
    if not a.targets: print(__doc__); return 2
    return run(a)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
