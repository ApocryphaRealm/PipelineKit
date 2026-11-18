# package_render_blender.py - the Blender half of role package-render (2026-11-12). Run only by package-render.py:
#   blender --background --factory-startup --python-exit-code 1 --python package_render_blender.py -- <job.json>
# For every unique shipped NIF in the job: import it with PyNifly, give each shape a material made from the DDS the NIF
# names (resolved in the SHIPPED package only - the shape's own data folder first, then the main file's Common and other
# folders), render the standard views (front, back, side, top orthographic, three-quarter) and a close-up of every
# carved surface (each shape cut into segments along its length, seen from both faces), backface culling ON (library
# 13760: proofs of game NIFs show one-sided faults), plus a UV-density heat view per shape; measure every shape's UV
# stretch on the NIF's own vertices/UVs/triangles (package_render_uv.py). Writes <out>/<id>/item.json + PNGs.
import bpy, addon_utils, sys, os, json, math, struct, time
import numpy as np
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import package_render_uv as UVM
JOB = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
RES = int(JOB.get("res", 1000)); SAMPLES = int(JOB.get("samples", 24))
CLOSE_RES = int(JOB.get("close_res", RES * 1.6))        # close-ups and heat views: a thin blade still gets detail across it
HIDE = ("edgeblood", "edge blood", "bhk", "collision")
addon_utils.enable("io_scene_nifly", default_set=True)
from io_scene_nifly.pyn.pynifly import NifFile


def log(*a): print("[package-render]", *a, flush=True)


def dds_size(p):
    h = open(p, "rb").read(20)
    if h[:4] != b"DDS ": return None
    hh, ww = struct.unpack("<II", h[12:20]); return int(ww), int(hh)


def resolve_tex(rel, roots):
    rel = rel.replace("/", "\\").lstrip("\\")
    if not rel: return None
    if not rel.lower().startswith("textures\\"): rel = "textures\\" + rel
    for r in roots:
        p = os.path.join(r, rel)
        if os.path.isfile(p): return p
        # case-insensitive walk (Windows is, but keep the shipped spelling out of it)
    return None


def slots(f, s):
    out = {}
    for slot, name in ((0, "diffuse"), (1, "normal"), (5, "rmaos")):
        try: out[name] = s.shader._readtexture(f._handle, s._handle, slot + 1) or ""
        except Exception: out[name] = (s.shader.textures.get({0: "Diffuse", 1: "Normal"}.get(slot, "-"), "") if hasattr(s.shader, "textures") else "")
    return out


def scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("io_scene_nifly", default_set=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"; sc.cycles.samples = SAMPLES; sc.cycles.use_denoising = True; sc.cycles.device = "CPU"
    try:
        pr = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("OPTIX", "CUDA", "HIP", "ONEAPI"):
            try:
                pr.compute_device_type = kind; pr.get_devices()
                if any(d.type == kind for d in pr.devices):
                    for d in pr.devices: d.use = d.type == kind
                    sc.cycles.device = "GPU"; break
            except Exception: continue
    except Exception: pass
    sc.view_settings.view_transform = "AgX"; sc.render.film_transparent = False
    w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.30, 0.31, 0.33, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.8
    for nm, en, rot in (("Key", 3.5, (math.radians(50), 0, math.radians(-35))), ("Fill", 1.2, (math.radians(70), 0, math.radians(140))),
                        ("Rim", 1.0, (math.radians(-60), 0, math.radians(20)))):
        L = bpy.data.objects.new(nm, bpy.data.lights.new(nm, "SUN")); sc.collection.objects.link(L); L.data.energy = en; L.rotation_euler = rot
    cd = bpy.data.cameras.new("C"); cd.type = "ORTHO"; cd.clip_start = 0.1; cd.clip_end = 100000   # library 13880: set the clip range
    cam = bpy.data.objects.new("C", cd); sc.collection.objects.link(cam); sc.camera = cam
    sc.render.image_settings.file_format = "PNG"
    return sc, cam


def img(p, colour):
    if not p: return None
    i = bpy.data.images.load(p, check_existing=True)
    i.colorspace_settings.name = "sRGB" if colour else "Non-Color"
    return i


def material(name, tex):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; N = nt.nodes; Lk = nt.links
    bs = N["Principled BSDF"]; out = N["Material Output"]
    d, n, r = img(tex.get("diffuse"), True), img(tex.get("normal"), False), img(tex.get("rmaos"), False)
    if d:
        t = N.new("ShaderNodeTexImage"); t.image = d; Lk.new(t.outputs["Color"], bs.inputs["Base Color"])
    else:
        bs.inputs["Base Color"].default_value = (1.0, 0.0, 1.0, 1)          # a missing texture shows magenta
    if n:
        t = N.new("ShaderNodeTexImage"); t.image = n
        sep = N.new("ShaderNodeSeparateColor"); comb = N.new("ShaderNodeCombineColor"); inv = N.new("ShaderNodeMath"); inv.operation = "SUBTRACT"
        inv.inputs[0].default_value = 1.0
        Lk.new(t.outputs["Color"], sep.inputs["Color"]); Lk.new(sep.outputs["Red"], comb.inputs["Red"])
        Lk.new(sep.outputs["Green"], inv.inputs[1]); Lk.new(inv.outputs[0], comb.inputs["Green"]); Lk.new(sep.outputs["Blue"], comb.inputs["Blue"])
        nm = N.new("ShaderNodeNormalMap"); Lk.new(comb.outputs["Color"], nm.inputs["Color"]); Lk.new(nm.outputs["Normal"], bs.inputs["Normal"])
    if r:
        t = N.new("ShaderNodeTexImage"); t.image = r; sep = N.new("ShaderNodeSeparateColor"); Lk.new(t.outputs["Color"], sep.inputs["Color"])
        Lk.new(sep.outputs["Red"], bs.inputs["Roughness"]); Lk.new(sep.outputs["Green"], bs.inputs["Metallic"])
    else:
        bs.inputs["Roughness"].default_value = 0.45; bs.inputs["Metallic"].default_value = 0.5
    # backface culling in Cycles: a back face is fully transparent (the game draws one side only)
    geo = N.new("ShaderNodeNewGeometry"); tr = N.new("ShaderNodeBsdfTransparent"); mix = N.new("ShaderNodeMixShader")
    Lk.new(geo.outputs["Backfacing"], mix.inputs["Fac"]); Lk.new(bs.outputs["BSDF"], mix.inputs[1]); Lk.new(tr.outputs["BSDF"], mix.inputs[2])
    Lk.new(mix.outputs["Shader"], out.inputs["Surface"]); m.use_backface_culling = True
    return m


def heat_material():
    m = bpy.data.materials.new("heat"); m.use_nodes = True; N = m.node_tree.nodes; Lk = m.node_tree.links
    for x in list(N):
        if x.type != "OUTPUT_MATERIAL": N.remove(x)
    a = N.new("ShaderNodeVertexColor"); a.layer_name = "ratio"; e = N.new("ShaderNodeEmission"); Lk.new(a.outputs["Color"], e.inputs["Color"])
    geo = N.new("ShaderNodeNewGeometry"); tr = N.new("ShaderNodeBsdfTransparent"); mix = N.new("ShaderNodeMixShader")
    Lk.new(geo.outputs["Backfacing"], mix.inputs["Fac"]); Lk.new(e.outputs["Emission"], mix.inputs[1]); Lk.new(tr.outputs["BSDF"], mix.inputs[2])
    Lk.new(mix.outputs["Shader"], N["Material Output"].inputs["Surface"])
    return m


def ratio_colour(r):
    # 1x grey-green; over 2x red; under 0.5x blue; in between blended on a log scale
    l = math.log2(max(min(r, 8.0), 0.125))
    if l >= 0: t = min(l, 1.0); return (0.25 + 0.75 * t, 0.6 * (1 - t) + 0.05, 0.25 * (1 - t), 1)
    t = min(-l, 1.0); return (0.25 * (1 - t), 0.6 * (1 - t) + 0.1, 0.25 + 0.75 * t, 1)


def shoot(sc, cam, png, P, view, up, pad=1.06, res=RES):
    view = Vector(view).normalized(); up = Vector(up)
    right = view.cross(up).normalized(); up = right.cross(view).normalized()
    c0 = sum(P, Vector()) / len(P)
    pr = [(p - c0).dot(right) for p in P]; pu = [(p - c0).dot(up) for p in P]; pv = [(p - c0).dot(view) for p in P]
    tgt = c0 + right * (0.5 * (min(pr) + max(pr))) + up * (0.5 * (min(pu) + max(pu)))
    ew, eh = max(max(pr) - min(pr), 1e-3) * pad, max(max(pu) - min(pu), 1e-3) * pad
    if ew >= eh: w, h = res, max(240, int(res * eh / ew))
    else: w, h = max(240, int(res * ew / eh)), res
    cam.data.ortho_scale = max(ew, eh)
    depth = max(pv) - min(pv)
    cam.location = tgt - view * (depth + 50.0); cam.rotation_mode = "QUATERNION"
    cam.rotation_quaternion = Matrix((right, up, -view)).transposed().to_quaternion()
    sc.render.resolution_x, sc.render.resolution_y = w, h; sc.render.filepath = png
    bpy.ops.render.render(write_still=True)
    return os.path.basename(png)


STD = [("front", (0, 0, -1), (0, 1, 0)), ("back", (0, 0, 1), (0, 1, 0)), ("side", (-1, 0, 0), (0, 1, 0)), ("top", (0, -1, 0), (0, 0, -1))]
TQ = ("three-quarter", (math.sin(math.radians(35)) * math.cos(math.radians(10)), -math.sin(math.radians(10)), -math.cos(math.radians(35)) * math.cos(math.radians(10))), (0, 1, 0))
AX = [Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))]


def run_item(it, outroot):
    t0 = time.time(); od = os.path.join(outroot, it["id"]); os.makedirs(od, exist_ok=True)
    sc, cam = scene()
    f = NifFile(it["nif"]); info = {"id": it["id"], "nif": it["nif"], "shapes": [], "renders": {"standard": [], "closeup": [], "heat": []}}
    nshapes = {s.name: s for s in f.shapes}
    before = set(bpy.data.objects)
    bpy.ops.import_scene.pynifly(filepath=it["nif"], import_collisions=False)
    objs = [o for o in bpy.data.objects if o not in before]
    shown = []
    for s in f.shapes:
        tx = slots(f, s); low = (s.name + " " + tx.get("diffuse", "")).lower()
        rec = {"name": s.name, "triangles": len(s.tris), "vertices": len(s.verts), "textures": {}, "missing": [], "external": []}
        for k, rel in tx.items():
            if not rel: continue
            p = resolve_tex(rel, it["roots"])
            if p: rec["textures"][k] = p
            else: rec["external"].append(rel)
        rec["skinned"] = bool(getattr(s, "has_skin_instance", False))
        if any(h in low for h in HIDE) or "\\blood\\" in low:
            rec["shown"] = False; rec["why_hidden"] = "blood / collision shape (vanilla effect, not a model surface)"
        elif "diffuse" not in rec["textures"]:
            rec["shown"] = False; rec["why_hidden"] = "its base-colour texture is not in the package (a vanilla leftover the game resolves from its own archives)"
        else:
            rec["shown"] = True
        if rec["shown"]:
            ws = dds_size(rec["textures"]["diffuse"]) or (2048, 2048)
            u = UVM.measure_shape(s.name, s.verts, s.uvs, s.tris, ws[0], ws[1]); rec["_ratio"] = u.pop("_ratio"); rec["uv"] = u
        info["shapes"].append(rec)
    byname = {r["name"]: r for r in info["shapes"]}
    for o in objs:
        if o.type != "MESH": continue
        r = byname.get(o.name) or byname.get(o.name.split(".")[0])
        if not r or not r["shown"]: o.hide_render = True; continue
        o.data.materials.clear(); o.data.materials.append(material(o.name + "_pr", r["textures"])); shown.append((o, r))
    if not shown:
        info["error"] = "no shape of this NIF has its texture in the package - nothing to render"
        json.dump(info, open(os.path.join(od, "item.json"), "w", encoding="utf-8"), indent=1); return info
    dg = bpy.context.evaluated_depsgraph_get(); ALL = []; per = {}
    for o, r in shown:
        e = o.evaluated_get(dg); me = e.to_mesh(); pts = [e.matrix_world @ v.co for v in me.vertices]; e.to_mesh_clear()
        per[r["name"]] = pts; ALL += pts
    # standard views: the item as it is drawn (a sheath shape - 'Scb', the one the game leaves on the hip - would cover
    # the blade, so it is left out here); then, when there is one, the item sheathed
    def vis(names):
        for o, r in shown: o.hide_render = r["name"] not in names
    groups = [("", [r["name"] for _, r in shown if not r["name"].lower().startswith("scb")])]
    if any(r["name"].lower().startswith("scb") for _, r in shown): groups.append(("sheathed-", [r["name"] for _, r in shown]))
    if not groups[0][1]: groups = groups[1:]
    for tag, names in groups:
        vis(names); P = [p for n in names for p in per[n]]
        for nm, v, u in STD + [TQ]:
            info["renders"]["standard"].append(shoot(sc, cam, os.path.join(od, f"std-{tag}{nm}.png"), P, v, u))
    # close-ups: each shape along its longest extent in segments about 1.5x its width, seen along its thinnest axis
    for o, r in shown:
        P = per[r["name"]]
        if len(P) < 3: continue
        lo = [min(p[i] for p in P) for i in range(3)]; hi = [max(p[i] for p in P) for i in range(3)]
        ext = [hi[i] - lo[i] for i in range(3)]; order = sorted(range(3), key=lambda i: -ext[i])
        L, Wd, thin = order[0], order[1], order[2]
        n = max(1, min(4, math.ceil(ext[L] / max(1.5 * ext[Wd], 1e-3))))
        up = AX[L]; view = AX[thin]
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in r["name"]); vis([r["name"]])   # the shape alone
        for k in range(n):
            a = lo[L] + ext[L] * (k / n) - ext[L] * 0.06; b = lo[L] + ext[L] * ((k + 1) / n) + ext[L] * 0.06
            Q = [p for p in P if a <= p[L] <= b]
            if len(Q) < 3: continue
            for side, sg in (("face-a", 1), ("face-b", -1)):
                info["renders"]["closeup"].append(shoot(sc, cam, os.path.join(od, f"close-{safe}-seg{k + 1}of{n}-{side}.png"), Q, view * sg, up, pad=1.08, res=CLOSE_RES))
        r["_axes"] = (L, thin)
    # UV-density heat views: one new mesh per shape from the NIF's own triangles, faces coloured by density / island median
    hm = heat_material()
    for o, _ in shown: o.hide_render = True
    for o, r in shown:
        s = nshapes.get(r["name"]); ratio = r.pop("_ratio", None)
        if s is None or ratio is None: continue
        me = bpy.data.meshes.new("heat"); me.from_pydata([tuple(v) for v in s.verts], [], [tuple(t) for t in s.tris]); me.update()
        if len(me.polygons) != len(s.tris): continue
        ca = me.color_attributes.new("ratio", "FLOAT_COLOR", "CORNER"); cols = np.empty((len(me.loops), 4), np.float32)
        for pi, poly in enumerate(me.polygons):
            c = ratio_colour(float(ratio[pi]))
            for li in poly.loop_indices: cols[li] = c
        ca.data.foreach_set("color", cols.ravel())
        ho = bpy.data.objects.new("heat_" + r["name"], me); sc.collection.objects.link(ho); ho.matrix_world = o.matrix_world.copy(); me.materials.append(hm)
        bpy.context.view_layer.update()
        P = [ho.matrix_world @ v.co for v in me.vertices]; L, thin = r.get("_axes", (1, 2))
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in r["name"])
        for side, sg in (("face-a", 1), ("face-b", -1)):
            info["renders"]["heat"].append(shoot(sc, cam, os.path.join(od, f"heat-{safe}-{side}.png"), P, AX[thin] * sg, AX[L], pad=1.06, res=CLOSE_RES))
        ho.hide_render = True
        r.pop("_axes", None)
    for r in info["shapes"]: r.pop("_axes", None); r.pop("_ratio", None)
    info["seconds"] = round(time.time() - t0, 1); info["device"] = sc.cycles.device
    json.dump(info, open(os.path.join(od, "item.json"), "w", encoding="utf-8"), indent=1)
    log("item", it["id"], "done in", info["seconds"], "s,", len(info["renders"]["standard"]) + len(info["renders"]["closeup"]) + len(info["renders"]["heat"]), "renders")
    return info


for it in JOB["items"]:
    if os.path.isfile(os.path.join(JOB["out"], it["id"], "item.json")) and JOB.get("resume"):
        log("item", it["id"], "already rendered (resume)"); continue
    run_item(it, JOB["out"])
log("all done")
