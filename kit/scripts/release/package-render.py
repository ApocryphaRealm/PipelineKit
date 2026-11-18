r"""Re-render a model mod's FINALIZED package before it is posted - role package-render (2026-11-12).

The owner, 2026-11-12 07:06: "From now on, we have to re-render the package before posting it as part of the
finalization process, so we don't run into the same issue as we did this time." Truly Nordic Carved Weapons Replacer
1.1.0 went out with the greatsword v4 blade's UVs stretched 2-5x near the tip: every render, composite, the Sketchfab
model and every check had looked at work-folder meshes, not at the NIF that shipped (the game build decimates the work
mesh, and the decimation is where the stretch came from).

WHAT IT DOES, for a package that ships any .nif (the FOMOD picture gate's definition of a model mod):
  1. finds the finalized package  10. finalized mods\<Game> - <Mod>\<Mod> <ver>\  (every main-file and FOMOD option
     folder in it) and hashes every .nif and .dds (SHA-256);
  2. imports every UNIQUE shipped NIF (by hash) into Blender with PyNifly and the DDS it names - resolved in the package
     only: the NIF's own data folder, then its main file's Common and other folders - and renders front / back / side /
     top orthographic and three-quarter views (sheathed too when the NIF carries a sheath), a close-up of every surface
     (each shape alone, in segments along its length, both faces), backface culling on, and a UV-density heat view per
     shape (package_render_blender.py);
  3. runs the design gates on what shipped:
       uv-stretch        every shown shape of every shipped NIF (package_render_uv.py): FAIL when a UV island's face has
                         more than 3% of its area over 2x or under 0.5x the island's own median texel density, on a patch
                         of at least 1% of the shape's surface (a smaller patch warns)
       renders           every unique NIF rendered, no render blank (library 13880), every shown texture found
       engraving-layout  role engraving-layout-gate --repo <repo> (where the repo keeps layout records, tools\items.py)
       surface-profile   role surface-profile-gate on the work folders items.py names (design records; not measured =
                         warn only, as that gate does)
  4. writes  11. Nexus distro\<Game> - <Mod>\assets\package-renders\<ver>\ :  package-render.json (the hash of every
     NIF and DDS of the package, what was rendered, each gate's result, the verdict), one sheet per unique NIF and an
     index sheet (JPEG), and every render (renders\<id>\*.jpg).

The gate (role package-render-gate) refuses posting a model mod unless that result exists for exactly the finalized
package's hashes and passed. finalize-mod.ps1 runs this tool as its last station; the upload step runs the gate (the kit uploads nothing - OPTIONAL-SCRIPTS.md).

  py -3 package-render.py --mod <key|display name> --version X.Y.Z [--package <dir>] [--distro <dir>] [--res 1000]
                          [--samples 24] [--resume] [--keep-work]
  py -3 package-render.py accept --mod <key> --version X.Y.Z --reason "<the owner's words>"
        records that the owner reviewed a FAILED result's sheets and accepts it for posting (same hashes only)
Exit: 0 PASS (or not a model mod), 1 FAIL, 2 usage / environment error.
"""
import argparse, datetime, hashlib, json, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__)); SCRIPTS = os.path.dirname(HERE); MD = os.path.dirname(SCRIPTS)
ROOT = os.path.dirname(MD); RESOLVE = os.path.join(MD, "resolvers", "resolve.py")
TOOL_VERSION = "1.0.0"
RESULT = "package-render.json"
sys.path.insert(0, SCRIPTS)


def role(name, fallback=None):
    try:
        r = subprocess.run([sys.executable, RESOLVE, "find", name], capture_output=True, text=True, timeout=60)
        p = r.stdout.strip().splitlines()[0].strip() if r.stdout.strip() else ""
        if r.returncode == 0 and p and not p.startswith(("NO SUCH", "MISSING")): return p
    except Exception: pass
    return fallback


def registry_entry(mod):
    reg = json.load(open(role("version-registry", os.path.join(SCRIPTS, "version-registry.json")), encoding="utf-8-sig"))
    reg = reg.get("mods", reg)
    for k, e in reg.items():
        if not isinstance(e, dict): continue
        names = [k, e.get("repo", ""), e.get("displayName", "")] + list(e.get("aliases") or [])
        if any(n and n.lower() == mod.lower() for n in names): return k, e
    return None, None


def distro_folder(display, game=""):
    r = subprocess.run([sys.executable, RESOLVE, "distro", "folder", display] + ([game] if game else []), capture_output=True, text=True, timeout=60)
    return r.stdout.strip().splitlines()[-1].strip() if r.returncode == 0 and r.stdout.strip() else None


def finalized_package(display, version):
    import package_paths as P
    for p in P.find_packages(P.STAGE10, mod=display, version=version, folders=True):
        if p["is_dir"] and p["name"] == f"{display} {version}": return p["path"], p["game"]
    return None, None


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def inventory(pkg):
    """{relative path (lower-case keys kept as shipped): sha256} for every .nif and .dds of the package."""
    out = {}
    for dp, _, fs in os.walk(pkg):
        for n in fs:
            if n.lower().endswith((".nif", ".dds")):
                full = os.path.join(dp, n); out[os.path.relpath(full, pkg).replace("/", "\\")] = sha(full)
    return dict(sorted(out.items()))


def is_model(pkg):
    return any(n.lower().endswith(".nif") for _, _, fs in os.walk(pkg) for n in fs)


def data_folder(pkg, rel):
    parts = rel.split("\\"); low = [x.lower() for x in parts]
    i = low.index("meshes") if "meshes" in low else len(parts) - 1
    return os.path.join(pkg, *parts[:i]) if i else pkg


def texture_roots(pkg, rel):
    """The NIF's own data folder, then the data folders of its main file (Common first), then every other one."""
    own = data_folder(pkg, rel); roots = [own]
    main = os.path.dirname(own) if os.path.normcase(own) != os.path.normcase(pkg) else pkg
    sib = sorted([os.path.join(main, d) for d in os.listdir(main) if os.path.isdir(os.path.join(main, d))],
                 key=lambda d: (os.path.basename(d).lower() != "common", d.lower()))
    roots += [d for d in sib if d not in roots]
    if os.path.isdir(os.path.join(pkg, "textures")) and pkg not in roots: roots.append(pkg)
    for dp, dns, _ in os.walk(pkg):
        if "textures" in (x.lower() for x in dns) and dp not in roots: roots.append(dp)
    return roots


def blender_exe():
    p = role("blender")
    if p and os.path.isfile(p): return p
    c = os.environ.get("BLENDER") or shutil.which("blender")   # kit: BLENDER, then blender on PATH
    if c and os.path.isfile(c): return c
    return None


def blank(png):
    from PIL import Image, ImageStat
    im = Image.open(png).convert("RGB"); st = ImageStat.Stat(im)
    return max(st.stddev) < 2.0


def sheet(item, src, dst, title_lines):
    """One sheet per unique NIF: the title, the standard views, the heat views, the close-ups (JPEG)."""
    from PIL import Image, ImageDraw, ImageFont
    try: font = ImageFont.load_default(size=22); small = ImageFont.load_default(size=16)
    except TypeError: font = small = ImageFont.load_default()
    rows = [("standard views", item["renders"]["standard"], 520), ("UV density (green = island median, red > 2x, blue < 0.5x)", item["renders"]["heat"], 420),
            ("close-ups (each shape alone, both faces, along its length)", item["renders"]["closeup"], 360)]
    W = 2400; tiles = []
    for label, names, h in rows:
        ims = []
        for n in names:
            p = os.path.join(src, n)
            if os.path.isfile(p):
                im = Image.open(p).convert("RGB"); r = min(h / im.height, 760 / im.width)   # a wide view (top) is capped in width
                im = im.resize((max(1, int(im.width * r)), max(1, int(im.height * r)))); ims.append((n, im))
        lines, cur, x = [], [], 0
        for n, im in ims:
            if cur and x + im.width > W: lines.append(cur); cur, x = [], 0
            cur.append((n, im)); x += im.width + 8
        if cur: lines.append(cur)
        tiles.append((label, lines, h))
    head = 30 * (len(title_lines) + 1)
    H = head + sum(34 + len(ls) * (h + 26) for _, ls, h in tiles) + 20
    S = Image.new("RGB", (W, H), (24, 24, 26)); d = ImageDraw.Draw(S); y = 10
    for i, t in enumerate(title_lines):
        d.text((14, y), t, fill=(255, 120, 110) if "FAIL" in t else (235, 235, 235), font=font if i == 0 else small); y += 30
    y += 10
    for label, lines, h in tiles:
        d.text((14, y), label, fill=(200, 200, 140), font=font); y += 34
        for ln in lines:
            x = 10
            for n, im in ln:
                S.paste(im, (x, y)); lab = os.path.splitext(n)[0].replace("close-", "").replace("heat-", "").replace("std-", "")
                lab = lab.replace("-seg", " ").replace("-face-", " ")[-max(4, im.width // 8):]
                d.text((x + 2, y + h + 2), lab, fill=(170, 170, 170), font=small); x += im.width + 8
            y += h + 26
    S.save(dst, quality=88)


def index_sheet(items, src, dst, title):
    from PIL import Image, ImageDraw, ImageFont
    try: font = ImageFont.load_default(size=22); small = ImageFont.load_default(size=16)
    except TypeError: font = small = ImageFont.load_default()
    h = 460; cells = []
    for it in items:
        p = os.path.join(src, it["id"], "std-front.png")
        if not os.path.isfile(p): continue
        im = Image.open(p).convert("RGB"); r = h / im.height; im = im.resize((max(1, int(im.width * r)), h))
        hp = [n for n in it["renders"]["heat"]][:1]
        if hp:
            hm = Image.open(os.path.join(src, it["id"], hp[0])).convert("RGB"); rr = h / hm.height; hm = hm.resize((max(1, int(hm.width * rr)), h))
            c = Image.new("RGB", (im.width + hm.width + 6, h), (24, 24, 26)); c.paste(im, (0, 0)); c.paste(hm, (im.width + 6, 0)); im = c
        cells.append((it, im))
    W = 2400; lines, cur, x = [], [], 0
    for it, im in cells:
        if cur and x + im.width > W: lines.append(cur); cur, x = [], 0
        cur.append((it, im)); x += im.width + 16
    if cur: lines.append(cur)
    H = 60 + len(lines) * (h + 70)
    S = Image.new("RGB", (W, H), (24, 24, 26)); d = ImageDraw.Draw(S); d.text((14, 14), title, fill=(255, 120, 110) if "FAIL" in title else (235, 235, 235), font=font); y = 60
    for ln in lines:
        x = 10
        for it, im in ln:
            S.paste(im, (x, y)); v = it.get("uv_verdict", "?")
            d.text((x + 2, y + h + 4), it["id"] + " " + v, fill=(255, 120, 110) if v == "FAIL" else (150, 220, 150), font=small)
            d.text((x + 2, y + h + 24), it["label"][:48], fill=(170, 170, 170), font=small); x += im.width + 16
        y += h + 70
    S.save(dst, quality=88)


def run_gate_script(path, args):
    if not path or not os.path.isfile(path): return None, "the gate script is not found"
    r = subprocess.run([sys.executable, path] + args, capture_output=True, text=True, timeout=600)
    return r.returncode, (r.stdout + r.stderr).strip()


def render(a):
    key, e = registry_entry(a.mod)
    if not e: print(f"package-render: '{a.mod}' is not in version-registry.json"); return 2
    display = e.get("displayName") or key
    pkg, game = (a.package, "") if a.package else finalized_package(display, a.version)
    if not pkg or not os.path.isdir(pkg): print(f"package-render: no finalized package '{display} {a.version}' in 10. finalized mods"); return 2
    if not is_model(pkg):
        print(f"package-render: OK - {os.path.basename(pkg)} ships no .nif (not a model mod) - nothing to render"); return 0
    distro = a.distro or distro_folder(display, game or "")
    if not distro or not os.path.isdir(distro): print(f"package-render: no distro folder for '{display}'"); return 2
    out = os.path.join(distro, "assets", "package-renders", a.version)
    blender = blender_exe()
    if not blender: print("package-render: Blender not found (set BLENDER, or put blender on PATH)"); return 2
    print(f"package-render: {display} {a.version}\n  package {pkg}\n  out     {out}")
    files = inventory(pkg)
    nifs = {}
    for rel, h in files.items():
        if rel.lower().endswith(".nif"): nifs.setdefault(h, []).append(rel)
    items = []
    for i, (h, rels) in enumerate(sorted(nifs.items(), key=lambda kv: kv[1][0].lower())):
        rel = rels[0]
        items.append({"id": f"n{i + 1:02d}", "sha256": h, "paths": rels, "nif": os.path.join(pkg, rel), "roots": texture_roots(pkg, rel),
                      "label": (lambda ps: "\\".join(ps[:2] + ps[-1:]) if len(ps) > 3 else "\\".join(ps))(rel.split("\\"))})
    print(f"  {sum(1 for r in files if r.lower().endswith('.nif'))} NIFs ({len(items)} unique by hash), "
          f"{sum(1 for r in files if r.lower().endswith('.dds'))} DDS")
    work = os.path.join(tempfile.gettempdir(), "package-render", f"{key}-{a.version}")
    if not a.resume and os.path.isdir(work): shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work, exist_ok=True)
    # 2026-11-15 (Nordic Skyforged 1.1.0): a finalized BodySlide ShapeData NIF sat at a 263-character path and PyNifly's
    # native reader cannot open a path past MAX_PATH ("Could not open ... as nif"), so Blender died before rendering
    # anything. A NIF whose full path is that long is read from a short-path copy in the work folder (same bytes - the
    # item's hash is still the shipped file's); textures still come from the package through texture_roots.
    for it in items:
        if len(it["nif"]) >= 240:
            short = os.path.join(work, "nif", it["id"] + ".nif")
            os.makedirs(os.path.dirname(short), exist_ok=True)
            shutil.copyfile("\\\\?\\" + os.path.abspath(it["nif"]), short)
            it["nif_shipped"] = it["nif"]; it["nif"] = short
    job = {"out": work, "res": a.res, "samples": a.samples, "resume": bool(a.resume), "items": items}
    jp = os.path.join(work, "job.json"); json.dump(job, open(jp, "w", encoding="utf-8"), indent=1)
    log = os.path.join(work, "blender.log")
    with open(log, "w", encoding="utf-8", errors="replace") as lf:
        r = subprocess.run([blender, "--background", "--factory-startup", "--python-exit-code", "1", "--python",
                            os.path.join(HERE, "package_render_blender.py"), "--", jp], stdout=lf, stderr=subprocess.STDOUT)
    if r.returncode != 0:
        print(f"package-render: Blender failed (exit {r.returncode}) - see {log}")
        print("".join(open(log, encoding="utf-8", errors="replace").readlines()[-15:])); return 2
    # ---- collect + gates
    gates, made = {}, []
    uv_fail, uv_warn, rend_fail, warn = [], [], [], []
    tex_used = set()
    for it in items:
        ip = os.path.join(work, it["id"], "item.json")
        if not os.path.isfile(ip): rend_fail.append(f"{it['label']}: not rendered"); continue
        info = json.load(open(ip, encoding="utf-8")); it["renders"] = info.get("renders", {}); it["shapes"] = info.get("shapes", [])
        if info.get("error"): rend_fail.append(f"{it['label']}: {info['error']}")
        for nm in sum((it["renders"].get(k, []) for k in ("standard", "closeup", "heat")), []):
            if blank(os.path.join(work, it["id"], nm)): rend_fail.append(f"{it['label']}: render {nm} is one flat colour (nothing in frame)")
        v = "PASS"
        for s in it["shapes"]:
            for k, p in s.get("textures", {}).items(): tex_used.add(os.path.relpath(p, pkg).replace("/", "\\"))
            if s.get("shown") and s.get("uv", {}).get("verdict") == "FAIL":
                v = "FAIL"
            for isl in (s.get("uv", {}).get("islands", []) if s.get("shown") else []):
                line = (f"{it['label']} [{s['name']}] island of {isl['triangles']} tris ({isl['area_share']:.0%} of the shape, "
                        f"centre {isl['centre']}): " + "; ".join(isl["why"]))
                if isl["verdict"] == "FAIL": uv_fail.append(line)
                elif isl["verdict"] == "WARN": uv_warn.append(line)
            if s.get("shown") and (("normal" not in s.get("textures", {})) or s.get("external")):
                warn.append(f"{it['label']} [{s['name']}]: texture(s) not in the package: {', '.join(s.get('external') or ['normal map'])}")
        it["uv_verdict"] = v
    gates["uv-stretch"] = {"verdict": "FAIL" if uv_fail else "PASS", "failures": uv_fail, "warnings": uv_warn,
                           "rule": "FAIL: a UV island whose face has more than 3% of its area over 2x or under 0.5x its own median texel "
                                   "density, covering at least 1% of the shape's surface; the same on a smaller patch warns"}
    gates["renders"] = {"verdict": "FAIL" if rend_fail else "PASS", "failures": rend_fail, "warnings": warn}
    repo = os.path.join(ROOT, "6. current wip mods", e.get("repo", key))
    eg = role("engraving-layout-gate")
    code, txt = run_gate_script(eg, ["--path", pkg, "--repo", repo]) if os.path.isdir(repo) else (0, "no repo folder - nothing to check")
    gates["engraving-layout"] = {"verdict": "PASS" if code == 0 else ("SKIP" if code is None else "FAIL"), "output": txt[-3000:], "failures": [l.strip() for l in txt.splitlines() if "FAIL" in l]}
    sg = role("surface-profile-gate"); wdirs = []
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("elg", eg); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        wdirs = [d for _, d in (m.work_dirs_from_items(repo) or [])] if os.path.isdir(repo) else []
    except Exception as ex: txt = f"could not read the repo's item table: {ex}"
    if wdirs:
        code, txt = run_gate_script(sg, wdirs)
        gates["surface-profile"] = {"verdict": "PASS" if code == 0 else ("SKIP" if code is None else "FAIL"), "output": txt[-3000:], "failures": [l.strip() for l in txt.splitlines() if "FAIL" in l],
                                    "note": "design records of the work folders items.py names (the gate has no shipped-NIF measure yet)"}
    else:
        gates["surface-profile"] = {"verdict": "PASS", "output": "no layout work folders (no tools\\items.py) - nothing to check"}
    failed = [g for g, r in gates.items() if r["verdict"] == "FAIL"]
    verdict = "FAIL" if failed else "PASS"
    # ---- write the distro folder's result
    if os.path.isdir(out): shutil.rmtree(out, ignore_errors=True)
    os.makedirs(os.path.join(out, "renders"), exist_ok=True)
    from PIL import Image
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    for it in items:
        src = os.path.join(work, it["id"]); dd = os.path.join(out, "renders", it["id"]); os.makedirs(dd, exist_ok=True)
        if not it.get("renders"): continue
        for nm in sum((it["renders"].get(k, []) for k in ("standard", "closeup", "heat")), []):
            Image.open(os.path.join(src, nm)).convert("RGB").save(os.path.join(dd, os.path.splitext(nm)[0] + ".jpg"), quality=90)
        shown = [s for s in it.get("shapes", []) if s.get("shown")]
        tl = [f"{display} {a.version} - package render {stamp} - {it['id']} - UV stretch {it['uv_verdict']}",
              "shipped as: " + "; ".join(it["paths"][:4]) + (f" (+{len(it['paths']) - 4} more)" if len(it["paths"]) > 4 else ""),
              f"sha256 {it['sha256'][:16]}...  shapes shown: " + ", ".join(f"{s['name']} ({s['uv']['verdict'] if s.get('uv') else '-'})" for s in shown)]
        for s in shown:
            for isl in [i for i in s.get("uv", {}).get("islands", []) if i["verdict"] == "FAIL"][:3]:
                tl.append(f"  UV FAIL {s['name']}: island {isl['triangles']} tris at {isl['centre']}: " + "; ".join(isl["why"]))
            nw = sum(1 for i in s.get("uv", {}).get("islands", []) if i["verdict"] == "WARN")
            if nw: tl.append(f"  UV warn {s['name']}: {nw} small patch(es) off their island's density (under 1% of the shape each) - look at the heat view")
        name = f"sheet-{it['id']}-{''.join(c if c.isalnum() else '-' for c in it['label'])}.jpg"
        sheet(it, src, os.path.join(out, name), tl); made.append(name)
    index_sheet(items, work, os.path.join(out, "sheet-00-index.jpg"), f"{display} {a.version} - package render {stamp} - {verdict}"
                + (f" ({', '.join(failed)})" if failed else "")); made.insert(0, "sheet-00-index.jpg")
    res = {"tool": "package-render", "tool_version": TOOL_VERSION, "mod": key, "display": display, "version": a.version,
           "made": datetime.datetime.now().isoformat(timespec="seconds"), "package": pkg,
           "files": files, "unique_nifs": [{k: it.get(k) for k in ("id", "sha256", "paths", "label", "uv_verdict", "shapes")} for it in items],
           "textures_rendered": sorted(tex_used), "gates": gates, "verdict": verdict, "sheets": made,
           "renders_dir": "renders", "settings": {"res": a.res, "samples": a.samples}}
    json.dump(res, open(os.path.join(out, RESULT), "w", encoding="utf-8"), indent=1)
    if not a.keep_work: shutil.rmtree(work, ignore_errors=True)
    print(f"  sheets  {len(made)} in {out}")
    for g, r in gates.items():
        print(f"  {g:17s} {r['verdict']}")
        for f in r.get("failures", [])[:30]: print("      " + f)
        for w in r.get("warnings", [])[:40]: print("      warn: " + w)
    print(f"package-render: {verdict} - {out}\\{RESULT}")
    try:
        plog = role("pipeline-log")
        if plog: subprocess.run(["powershell", "-NoProfile", "-File", plog, "-Action", "record", "-Stage", "10", "-Event", "package-rendered", "-Mod", display,
                                 "-Key", key, "-Version", a.version, "-Evidence", f"package-render {verdict}: {len(items)} unique NIFs; {out}", "-By", "package-render.py"],
                                capture_output=True, timeout=120)
    except Exception: pass
    return 0 if verdict == "PASS" else 1


def accept(a):
    key, e = registry_entry(a.mod)
    if not e: print(f"package-render: '{a.mod}' is not in version-registry.json"); return 2
    display = e.get("displayName") or key
    pkg, game = finalized_package(display, a.version); distro = a.distro or distro_folder(display, game or "")
    p = os.path.join(distro, "assets", "package-renders", a.version, RESULT)
    if not os.path.isfile(p): print(f"package-render accept: no result at {p} - render it first"); return 2
    if not a.reason or not a.reason.strip(): print("package-render accept: --reason \"<the owner's words>\" is required"); return 2
    res = json.load(open(p, encoding="utf-8"))
    if inventory(pkg) != res.get("files"): print("package-render accept: the package changed since it was rendered - render it again"); return 1
    res["accepted"] = {"reason": a.reason.strip(), "when": datetime.datetime.now().isoformat(timespec="seconds"), "verdict_accepted": res.get("verdict")}
    json.dump(res, open(p, "w", encoding="utf-8"), indent=1); print(f"package-render accept: recorded for {display} {a.version} ({res.get('verdict')})"); return 0


def main(argv):
    if argv and argv[0] == "accept":
        ap = argparse.ArgumentParser(prog="package-render.py accept"); ap.add_argument("--mod", required=True); ap.add_argument("--version", required=True)
        ap.add_argument("--reason", required=True); ap.add_argument("--distro"); return accept(ap.parse_args(argv[1:]))
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0]); ap.add_argument("--mod", required=True); ap.add_argument("--version", required=True)
    ap.add_argument("--package"); ap.add_argument("--distro"); ap.add_argument("--res", type=int, default=1000); ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--resume", action="store_true"); ap.add_argument("--keep-work", action="store_true")
    return render(ap.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
