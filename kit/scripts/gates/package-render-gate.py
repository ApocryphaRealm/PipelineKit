r"""Refuses POSTING a model mod whose finalized package was not re-rendered, or whose re-render failed - role
package-render-gate (2026-11-12).

The owner, 2026-11-12 07:06: "From now on, we have to re-render the package before posting it as part of the
finalization process, so we don't run into the same issue as we did this time." (Truly Nordic Carved Weapons Replacer
1.1.0 was posted with the greatsword v4 blade's UVs stretched 2-5x; every picture and check had looked at work meshes.)

A MODEL MOD is a package that ships any .nif (the FOMOD picture gate's definition). For one, this gate needs
    11. Nexus distro\<Game> - <Mod>\assets\package-renders\<ver>\package-render.json   (role package-render writes it)
and REFUSES (exit 1) when
    - it is missing;
    - its "files" (SHA-256 of every .nif and .dds) differ from the finalized package's NOW (a file added, removed or
      changed since the render - names the files);
    - its verdict is not PASS, unless "accepted" records the owner's reason for posting it after reviewing the sheets
      (package-render.py accept --reason "<his words>"), which passes with a warning.
It WARNS (exit 0) when posting material in the distro folder - images in the folder itself, assets\sketchfab,
assets\preview, assets\banner-build - is older than the render: pictures made before the package render may show
something other than what ships.
A package that ships no .nif passes at once.

    py -3 package-render-gate.py --mod <key|display> --version X.Y.Z          (the upload step, finalize-mod.ps1)
    py -3 package-render-gate.py --package <finalized dir> --distro <distro dir> --version X.Y.Z
    py -3 package-render-gate.py --self-test
"""
import argparse, importlib.util, json, os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__)); SCRIPTS = os.path.dirname(HERE)
_spec = importlib.util.spec_from_file_location("package_render", os.path.join(SCRIPTS, "release", "package-render.py"))
PR = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(PR)
MEDIA = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".glb", ".gltf")


def media_older_than(distro, t):
    old = []
    for sub, deep in (("", False), (os.path.join("assets", "sketchfab"), False), (os.path.join("assets", "preview"), True), (os.path.join("assets", "banner-build"), False)):
        d = os.path.join(distro, sub)
        if not os.path.isdir(d): continue
        walk = os.walk(d) if deep else [(d, [], os.listdir(d))]
        for dp, _, fs in walk:
            for n in fs:
                p = os.path.join(dp, n)
                if n.lower().endswith(MEDIA) and os.path.isfile(p) and os.path.getmtime(p) < t: old.append(os.path.relpath(p, distro))
    return sorted(old)


def check(pkg, distro, version):
    """(exit code, lines)"""
    if not pkg or not os.path.isdir(pkg): return 1, [f"FAIL - no finalized package folder ({pkg})"]
    if not PR.is_model(pkg): return 0, [f"OK - {os.path.basename(pkg)} ships no .nif (not a model mod)"]
    rp = os.path.join(distro or "", "assets", "package-renders", version, PR.RESULT)
    fix = f"run: resolve.py run package-render --mod <key> --version {version}  (finalize-mod runs it as its last station)"
    if not os.path.isfile(rp):
        return 1, [f"FAIL - {os.path.basename(pkg)} ships models and has no package render ({rp} is missing)", "  " + fix]
    res = json.load(open(rp, encoding="utf-8"))
    if res.get("version") != version: return 1, [f"FAIL - {rp} is for version {res.get('version')}, not {version}", "  " + fix]
    now = PR.inventory(pkg); then = res.get("files") or {}
    if now != then:
        ch = sorted(k for k in set(now) | set(then) if now.get(k) != then.get(k))
        return 1, [f"FAIL - the package changed since it was rendered ({len(ch)} file(s) differ) - the render shows something other than what ships"] + \
               [f"  {'changed' if k in now and k in then else ('added' if k in now else 'removed')}: {k}" for k in ch[:20]] + ["  " + fix]
    lines, code = [], 0
    if res.get("verdict") != "PASS":
        def why(r):
            f = r.get("failures") or [l.strip() for l in (r.get("output") or "").splitlines() if "FAIL" in l]
            return f[:3] or [(r.get("output") or "")[-200:]]
        fails = [f"  {g}: " + " | ".join(why(r)) for g, r in (res.get("gates") or {}).items() if r.get("verdict") == "FAIL"]
        if res.get("accepted", {}).get("reason"):
            lines += [f"WARN - the package render FAILED but the owner accepted it: {res['accepted']['reason']}"] + fails[:6]
        else:
            return 1, [f"FAIL - the package render of {os.path.basename(pkg)} FAILED its design gates ({rp})"] + fails[:12] + \
                   ["  fix the model, rebuild, record working, finalize again (which re-renders); or, after the owner reviews the sheets and rules the flag wrong:",
                    f"  package-render.py accept --mod <key> --version {version} --reason \"<his words>\""]
    t = os.path.getmtime(rp)
    for p in media_older_than(distro, t):
        lines.append(f"WARN - {p} is older than the package render - make posting pictures from the rendered package")
    lines.insert(0, f"OK - {os.path.basename(pkg)}: package render {res.get('verdict')} ({res.get('made')}) matches all {len(now)} NIF/DDS hashes; sheets in {os.path.dirname(rp)}")
    return code, lines


def self_test():
    import hashlib
    results = {}
    with tempfile.TemporaryDirectory() as t:
        def mk(rel, data):
            p = os.path.join(t, rel); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "wb").write(data); return p
        pkg = os.path.join(t, "pkg"); distro = os.path.join(t, "distro")
        mk(r"pkg\Common\meshes\a.nif", b"nif1"); mk(r"pkg\Common\textures\a.dds", b"dds1"); os.makedirs(distro)
        results["missing render refuses"] = (check(pkg, distro, "1.0.0")[0], 1)
        rd = os.path.join(distro, "assets", "package-renders", "1.0.0"); os.makedirs(rd)
        def write(**kw):
            doc = {"version": "1.0.0", "files": PR.inventory(pkg), "verdict": "PASS", "gates": {}, "made": "x"}; doc.update(kw)
            json.dump(doc, open(os.path.join(rd, PR.RESULT), "w"))
        write(); results["current PASS passes"] = (check(pkg, distro, "1.0.0")[0], 0)
        write(verdict="FAIL", gates={"uv-stretch": {"verdict": "FAIL", "failures": ["blade island over 2x"]}})
        results["FAIL refuses"] = (check(pkg, distro, "1.0.0")[0], 1)
        write(verdict="FAIL", gates={"uv-stretch": {"verdict": "FAIL", "failures": ["x"]}}, accepted={"reason": "the owner: fine"})
        results["accepted FAIL passes"] = (check(pkg, distro, "1.0.0")[0], 0)
        write(); mk(r"pkg\Common\meshes\a.nif", b"nif2")
        c, lines = check(pkg, distro, "1.0.0"); results["changed NIF refuses"] = (c, 1)
        results["changed NIF named"] = (0 if any("changed: Common\\meshes\\a.nif" in l for l in lines) else 1, 0)
        write(); mk(r"pkg\Common\textures\b.dds", b"new"); results["added DDS refuses"] = (check(pkg, distro, "1.0.0")[0], 1)
        write(version="0.9.0"); results["other version refuses"] = (check(pkg, distro, "1.0.0")[0], 1)
        np_ = os.path.join(t, "plain"); mk(r"plain\SKSE\Plugins\x.dll", b"dll"); results["no .nif passes"] = (check(np_, distro, "1.0.0")[0], 0)
        write(); old = mk(r"distro\banner.png", b"png"); os.utime(old, (1, 1))
        c, lines = check(pkg, distro, "1.0.0"); results["old picture warns, passes"] = (c if any("banner.png is older" in l for l in lines) else 9, 0)
    ok = all(g == w for g, w in results.values())
    print("self-test", "PASS" if ok else "FAIL", {k: f"exit {g} (want {w})" for k, (g, w) in results.items()})
    return 0 if ok else 1


def main(argv):
    ap = argparse.ArgumentParser(); ap.add_argument("--mod"); ap.add_argument("--version"); ap.add_argument("--package"); ap.add_argument("--distro")
    ap.add_argument("--self-test", action="store_true"); a = ap.parse_args(argv)
    if a.self_test: return self_test()
    if not a.version: print("package-render-gate: --version is required"); return 2
    pkg, distro = a.package, a.distro
    if a.mod:
        key, e = PR.registry_entry(a.mod)
        if not e: print(f"package-render-gate: '{a.mod}' is not in version-registry.json"); return 2
        display = e.get("displayName") or key
        if not pkg: pkg, game = PR.finalized_package(display, a.version)
        else: game = ""
        distro = distro or PR.distro_folder(display, game or "")
    code, lines = check(pkg, distro, a.version)
    for l in lines: print("package-render-gate: " + l if not l.startswith("  ") else l)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
