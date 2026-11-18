#!/usr/bin/env python3
r"""render_lib.py - Blender renders of built Skyrim SE meshes with GAME-LIKE lighting (role render-lib, promoted
2026-11-18 from the Nordic Ebony repo's tools\render_lib.py, which stays; generalised: no mod's names, prefixes or
folders in here).

Each shape is textured from ITS OWN texture set, read from the NIF with niflib (no guessing a normal map from a diffuse
name):
  * a TruePBR shape (texture set slots 0 / 1 / 5): Principled BSDF with base colour = albedo, metallic = RMAOS green,
    roughness = RMAOS red, the normal map from slot 1 - lit by a sky-to-ground gradient world that the reflections see
    (the camera sees a plain backdrop): the stand-in for a shader mod's cube-map reflections;
  * a classic shape (diffuse, normal, environment mask in slot 5): no metallic, specular strength from the mask, the same
    gradient world.
Shapes whose diffuse starts with none of `prefixes` are hidden (an empty list shows every shape but the blood decals).

    render(shots, tex_roots, out_dir, prefixes=(), size=(900, 1200), up="z", same_frame=(), samples=48)
        shots       {name: ([nif paths], yaw)} or {name: ([nif paths], yaw, "z"|"y")} -> <out_dir>\<name>.png
        tex_roots   data folders the texture paths are looked up in (each holds textures\)
        up          the model's up axis: "z" for armour standing upright, "y" for a weapon lying along Y (per shot, or
                    one value for every shot)
        same_frame  groups of shot names that share ONE camera - fitted to all of them - so a before / after pair is
                    framed identically (before-after-sheet.py uses it)
    card(path, size)   a render cropped to its content, centred on a plain card (PIL)
    find_blender()     BLENDER, then blender on PATH, then the newest C:\Program Files\Blender Foundation\Blender *\
    pynifly_ok()       (True, "") when Blender can enable PyNifly (io_scene_nifly), else (False, why)

Needs Blender with PyNifly - a third-party add-on the person installs into Blender themselves; nothing of it is shipped
or copied here. PIL for card(). Blender is the only process it starts; nothing reaches the network.
"""
import glob
import json
import os
import shutil
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import niflib  # noqa: E402

BLENDER_SCRIPT = r'''
import bpy, os, sys, json, math, addon_utils
from mathutils import Vector, Matrix
addon_utils.enable("io_scene_nifly", default_set=True)
job = json.load(open(sys.argv[sys.argv.index("--") + 1]))
sc = bpy.context.scene; sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = job.get("samples", 48); sc.cycles.use_denoising = True
sc.view_settings.view_transform = "Standard"; sc.render.film_transparent = True
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True; bg = w.node_tree.nodes["Background"]; bg.inputs["Color"].default_value = (0.35, 0.36, 0.38, 1)
nt_ = w.node_tree; tc = nt_.nodes.new("ShaderNodeTexCoord"); sep = nt_.nodes.new("ShaderNodeSeparateXYZ")
ramp = nt_.nodes.new("ShaderNodeValToRGB"); ramp.color_ramp.elements[0].position = 0.35; ramp.color_ramp.elements[0].color = (0.10, 0.10, 0.11, 1)
ramp.color_ramp.elements[1].position = 0.75; ramp.color_ramp.elements[1].color = (1.0, 1.0, 1.02, 1)
mapr = nt_.nodes.new("ShaderNodeMapRange"); mapr.inputs["From Min"].default_value = -1.0; mapr.inputs["From Max"].default_value = 1.0
nt_.links.new(tc.outputs["Generated"], sep.inputs[0]); nt_.links.new(sep.outputs["Z"], mapr.inputs["Value"]); nt_.links.new(mapr.outputs["Result"], ramp.inputs["Fac"])
bg2 = nt_.nodes.new("ShaderNodeBackground"); nt_.links.new(ramp.outputs["Color"], bg2.inputs["Color"]); bg2.inputs["Strength"].default_value = 1.3
lp = nt_.nodes.new("ShaderNodeLightPath"); mx = nt_.nodes.new("ShaderNodeMixShader")
nt_.links.new(lp.outputs["Is Camera Ray"], mx.inputs["Fac"]); nt_.links.new(bg2.outputs[0], mx.inputs[1]); nt_.links.new(bg.outputs[0], mx.inputs[2])
nt_.links.new(mx.outputs[0], nt_.nodes["World Output"].inputs["Surface"])
mats = {}
def img(p, data):
    if not p or not os.path.isfile(p): return None
    i = bpy.data.images.load(p, check_existing=True)
    if data: i.colorspace_settings.name = "Non-Color"
    return i
def material(ts):
    key = json.dumps(ts)
    if key in mats: return mats[key]
    m = bpy.data.materials.new("m%d" % len(mats)); m.use_nodes = True; nt = m.node_tree; b = nt.nodes["Principled BSDF"]
    d = img(ts["d"], False); n = img(ts["n"], True); x = img(ts["x"], True)
    if d:
        t = nt.nodes.new("ShaderNodeTexImage"); t.image = d; nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    if n:
        tn = nt.nodes.new("ShaderNodeTexImage"); tn.image = n
        nm = nt.nodes.new("ShaderNodeNormalMap"); nt.links.new(tn.outputs["Color"], nm.inputs["Color"]); nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    if ts["pbr"] and x:
        tx = nt.nodes.new("ShaderNodeTexImage"); tx.image = x; sp = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(tx.outputs["Color"], sp.inputs[0]); nt.links.new(sp.outputs[0], b.inputs["Roughness"]); nt.links.new(sp.outputs[1], b.inputs["Metallic"])
        b.inputs["Specular IOR Level"].default_value = 0.5
    else:
        b.inputs["Metallic"].default_value = 0.0
        if x:
            tm = nt.nodes.new("ShaderNodeTexImage"); tm.image = x
            sm = nt.nodes.new("ShaderNodeMath"); sm.operation = "MULTIPLY_ADD"; sm.inputs[1].default_value = 0.9; sm.inputs[2].default_value = 0.3
            nt.links.new(tm.outputs["Color"], sm.inputs[0]); nt.links.new(sm.outputs[0], b.inputs["Specular IOR Level"]); b.inputs["Roughness"].default_value = 0.3
        else:
            b.inputs["Roughness"].default_value = 0.5
    if ts.get("alpha") and d:
        nt.links.new(t.outputs["Alpha"], b.inputs["Alpha"])
    mats[key] = m; return m
def load(name):
    for o in list(bpy.data.objects): bpy.data.objects.remove(o)
    objs = []
    for p in job["shots"][name][0]:
        tex = job["tex"][p]; before = set(bpy.data.objects)
        bpy.ops.import_scene.pynifly(filepath=p, import_collisions=False)
        for o in [o for o in bpy.data.objects if o not in before]:
            if o.type != "MESH": continue
            nm = o.name if o.name in tex else o.name.split(".")[0]; ts = tex.get(nm)
            if not ts: o.hide_render = True; continue
            o.data.materials.clear(); o.data.materials.append(material(ts)); objs.append(o)
    return objs
def axes(name):
    yaw = job["shots"][name][1]; upv = Vector((0, 0, 1)) if job["up"][name] == "z" else Vector((0, 1, 0))
    yw = math.radians(yaw)
    if upv.z: fwd = Vector((math.sin(yw), -math.cos(yw), 0.08)).normalized()
    else: fwd = Vector((math.sin(yw), 0, math.cos(yw)))
    right = upv.cross(fwd).normalized(); up = fwd.cross(right); return right, up, fwd
def extents(name, objs):
    right, up, fwd = axes(name); dg = bpy.context.evaluated_depsgraph_get(); P = []
    for o in objs:
        e = o.evaluated_get(dg); me = e.to_mesh(); P += [e.matrix_world @ v.co for v in me.vertices]; e.to_mesh_clear()
    if not P: return None
    xs = [p.dot(right) for p in P]; ys = [p.dot(up) for p in P]; zs = [p.dot(fwd) for p in P]
    return [min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)]
group = {}
for gi, g in enumerate(job.get("same_frame", [])):
    for nm in g: group[nm] = gi
ext = {}
for gi, g in enumerate(job.get("same_frame", [])):           # first pass: one frame for every shot of a group
    E = [e for e in (extents(nm, load(nm)) for nm in g) if e]
    if E: ext[gi] = [min(e[0] for e in E), max(e[1] for e in E), min(e[2] for e in E), max(e[3] for e in E), min(e[4] for e in E), max(e[5] for e in E)]
for name in job["shots"]:
    objs = load(name)
    for L, rot, e in (("key", (math.radians(40), math.radians(-35), 0), 3.0), ("rim", (math.radians(-55), math.radians(145), 0), 2.0), ("fill", (math.radians(60), math.radians(160), 0), 1.0)):
        l = bpy.data.lights.new(L, "SUN"); l.energy = e; lo = bpy.data.objects.new(L, l); lo.rotation_euler = rot; sc.collection.objects.link(lo)
    E = ext.get(group.get(name, -1)) or extents(name, objs)
    if not E: print("SHOT", name, "EMPTY"); continue
    right, up, fwd = axes(name)
    W, H = job["size"]; w_, h_ = E[1] - E[0], E[3] - E[2]
    cam = bpy.data.cameras.new("c"); cam.type = "ORTHO"; cam.clip_start = 1; cam.clip_end = 5000
    cam.ortho_scale = 1.08 * (max(h_, w_ * H / W) if H >= W else max(w_, h_ * W / H))
    co = bpy.data.objects.new("c", cam); sc.collection.objects.link(co); sc.camera = co
    co.location = right * (E[1] + E[0]) / 2 + up * (E[3] + E[2]) / 2 + fwd * (E[5] + 300)
    co.rotation_mode = "QUATERNION"; co.rotation_quaternion = Matrix((right, up, fwd)).transposed().to_quaternion()
    sc.render.resolution_x, sc.render.resolution_y = W, H; sc.render.filepath = os.path.join(job["out"], name + ".png")
    bpy.ops.render.render(write_still=True); print("SHOT", name, len(objs))
'''


def find_blender():
    b = os.environ.get("BLENDER") or shutil.which("blender")
    if b and os.path.isfile(b):
        return b
    c = sorted(glob.glob(r"C:\Program Files\Blender Foundation\Blender *\blender.exe"))
    return c[-1] if c else None


def pynifly_ok(timeout=180):
    """(True, "") when Blender starts in the background and enables io_scene_nifly; else (False, the reason)."""
    b = find_blender()
    if not b:
        return False, "Blender not found (set BLENDER, or put blender on PATH)"
    expr = ("import addon_utils, sys\n"
            "try:\n    addon_utils.enable('io_scene_nifly', default_set=True)\n    import io_scene_nifly\n    print('PYNIFLY-OK')\n"
            "except Exception as e:\n    print('PYNIFLY-MISSING', e)\n")
    try:
        r = subprocess.run([b, "--background", "--factory-startup", "--python-expr", expr], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, f"Blender did not run ({e})"
    if "PYNIFLY-OK" in r.stdout:
        return True, ""
    return False, "PyNifly (io_scene_nifly) is not installed in this Blender"


def _texsets(path, tex_roots, prefixes):
    """shape name -> {d, n, x, pbr, alpha} for the shown shapes of one NIF"""
    n = niflib.Nif(path); out = {}
    for b, t in enumerate(n.btypes):
        if t not in ("BSTriShape", "BSDynamicTriShape", "BSSubIndexTriShape", "NiTriShape"):
            continue
        try:
            o = n.av_end(b, 0, [], [])
            sh = struct.unpack_from("<i", n.blocks[b], o + 16 + 4)[0]
        except Exception:
            continue
        if sh < 0 or n.btypes[sh] != "BSLightingShaderProperty":
            continue
        ts = n.i32(sh, n.ref_offsets(sh)[0][-1])
        if ts < 0:
            continue
        blk = n.blocks[ts]; k = struct.unpack_from("<I", blk, 0)[0]; q = 4; paths = []
        for _ in range(k):
            L = struct.unpack_from("<I", blk, q)[0]; paths.append(blk[q + 4:q + 4 + L].decode("latin-1")); q += 4 + L
        d0 = paths[0].lower().replace("/", "\\") if paths else ""
        if prefixes and not d0.startswith(tuple(prefixes)):
            continue
        if not prefixes and ("blood" in (n.name(b) or "").lower() or not d0):
            continue
        f2 = struct.unpack_from("<I", n.blocks[sh], n.net_end(sh, 4, [], []) + 4)[0]

        def find(rel):
            if not rel:
                return ""
            rel = rel.replace("/", "\\").lstrip("\\")
            if not rel.lower().startswith("textures\\"):
                rel = "textures\\" + rel
            for r in tex_roots:
                p = os.path.join(r, rel.replace("\\", os.sep))
                if os.path.isfile(p):
                    return p
            return ""
        alpha = any(n.btypes[x] == "NiAlphaProperty" for x in [struct.unpack_from("<i", n.blocks[b], o + 16 + 8)[0]] if x >= 0)
        out[n.name(b)] = {"d": find(paths[0]), "n": find(paths[1] if len(paths) > 1 else ""),
                          "x": find(paths[5] if len(paths) > 5 else ""), "pbr": bool(f2 & 0x00800000), "alpha": alpha}
    return out


def render(shots, tex_roots, out_dir, prefixes=(), size=(900, 1200), up="z", same_frame=(), samples=48):
    os.makedirs(out_dir, exist_ok=True)
    norm_shots, ups = {}, {}
    for k, s in shots.items():
        ps, yaw = s[0], s[1]
        for p in ps:
            if not os.path.isfile(p):
                raise SystemExit("render_lib: no %s" % p)
        norm_shots[k] = [[os.path.abspath(p) for p in ps], yaw]
        ups[k] = (s[2] if len(s) > 2 else (up.get(k, "z") if isinstance(up, dict) else up)).lower()
        if ups[k] not in ("z", "y"):
            raise SystemExit("render_lib: up must be z or y (shot %s)" % k)
    tex_roots = [os.path.abspath(r) for r in tex_roots]   # Blender reads a relative path against the .blend, not the cwd
    pre = [x.lower().replace("/", "\\") for x in prefixes]
    tex = {p: _texsets(p, tex_roots, pre) for ps, _ in norm_shots.values() for p in ps}
    job = {"shots": norm_shots, "tex": tex, "out": os.path.abspath(out_dir), "size": list(size), "up": ups,
           "same_frame": [list(g) for g in same_frame], "samples": int(samples)}
    jp = os.path.join(out_dir, "job.json"); json.dump(job, open(jp, "w"))
    sp = os.path.join(out_dir, "render.py"); open(sp, "w", encoding="utf-8").write(BLENDER_SCRIPT)
    b = find_blender()
    if not b:
        raise SystemExit("render_lib: Blender not found - set BLENDER, or put blender on PATH")
    r = subprocess.run([b, "--background", "--factory-startup", "--python-exit-code", "1", "--python", sp, "--", jp],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("render_lib: Blender failed\n" + (r.stdout + r.stderr)[-3000:])
    return out_dir


def card(path, size, bg=(38, 39, 42), rotate=0):
    from PIL import Image
    im = Image.open(path).convert("RGBA")
    if rotate:
        im = im.rotate(rotate)
    box = im.getbbox(); im = im.crop(box) if box else im
    im.thumbnail(size); c = Image.new("RGB", size, bg); c.paste(im, ((size[0] - im.width) // 2, (size[1] - im.height) // 2), im)
    return c
