"""Refuses a MODEL mod's FOMOD installer that offers a model without a picture of it.

The owner (2026-11-11 23:23, Truly Nordic Carved Weapons Replacer 1.1.0): pictures from the renders belong in the FOMOD
"so they know what they're installing at the point of installation", as standard practice. Narrowed the same evening
(23:25): "only applies to mods that are for models like these ... a lot of mods that have installers don't really have
any pictures that we would really put in a FOMOD anyways".

THE RULE (decided mechanically from what each option installs - no per-mod list):
    an option (<plugin>) of a fomod\\ModuleConfig.xml NEEDS a picture when anything it installs is a .nif - a
    <file source="...nif"> or a <folder source="X"> whose folder in the package holds a .nif at any depth. Such an option
    must carry <image path="..."/>, and that file must exist in the package the ModuleConfig belongs to (paths relative
    to the folder holding fomod\\). An option that installs no .nif (DLLs, INIs, plugins, scripts, textures, settings)
    is not checked, so an installer for a DLL or settings mod passes with no pictures at all.
    Every fomod\\ModuleConfig.xml under the package is checked (a release folder may hold several packages).

package-gate runs it through the gate-rules row `fomod-model-options-have-a-picture` (kind package-script-passes), so it
is called with --path <package> [--repo <repo>].   Self-test: py -3 fomod-option-image-gate.py --self-test

Usage: py -3 fomod-option-image-gate.py --path <package folder> [--repo X]
"""
import argparse
import os
import sys
import tempfile
import xml.etree.ElementTree as ET


def _tag(el): return el.tag.split("}")[-1]


def installs_a_nif(plugin, root_dir):
    for files in (c for c in plugin if _tag(c) == "files"):
        for f in files:
            src = (f.get("source") or "").replace("/", "\\")
            if _tag(f) == "file" and src.lower().endswith(".nif"):
                return True
            if _tag(f) == "folder":
                d = os.path.join(root_dir, src)
                if any(n.lower().endswith(".nif") for _, _, fs in os.walk(d) for n in fs):
                    return True
    return False


def check(cfg):
    root_dir = os.path.dirname(os.path.dirname(cfg)); bad = []; checked = 0
    try:
        root = ET.parse(cfg).getroot()
    except ET.ParseError as e:
        return [f"{cfg}: not readable XML ({e})"], 0
    for el in root.iter():
        if _tag(el) != "plugin" or not installs_a_nif(el, root_dir):
            continue
        checked += 1; name = el.get("name", "?")
        img = next((c for c in el if _tag(c) == "image"), None)
        if img is None or not img.get("path"):
            bad.append(f"option '{name}' installs a model but has no <image>"); continue
        if not os.path.isfile(os.path.join(root_dir, img.get("path").replace("/", "\\"))):
            bad.append(f"option '{name}' names {img.get('path')}, which the package does not contain")
    return [f"{cfg}: {b}" for b in bad], checked


def run(path):
    cfgs = [os.path.join(dp, f) for dp, _, fs in os.walk(path) for f in fs
            if f.lower() == "moduleconfig.xml" and os.path.basename(dp).lower() == "fomod"]
    if not cfgs:
        print("fomod-option-image-gate: OK - no FOMOD installer in the package")
        return 0
    bad, total = [], 0
    for c in cfgs:
        b, n = check(c); bad += b; total += n
    if bad:
        for b in bad:
            print("fomod-option-image-gate: FAIL - " + b)
        return 1
    print(f"fomod-option-image-gate: OK - {total} model option(s) in {len(cfgs)} installer(s), every one with a picture that ships")
    return 0


def self_test():
    def make(base, files, opts):
        for rel in files:
            p = os.path.join(base, rel); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "wb").write(b"x")
        os.makedirs(os.path.join(base, "fomod"), exist_ok=True)
        body = "".join(f'<plugin name="{n}"><description/>' + (f'<image path="{img}"/>' if img else "") +
                       f'<files><folder source="{src}" destination=""/></files><typeDescriptor><type name="Optional"/></typeDescriptor></plugin>'
                       for n, src, img in opts)
        open(os.path.join(base, "fomod", "ModuleConfig.xml"), "w").write(
            f'<config><moduleName>t</moduleName><installSteps order="Explicit"><installStep name="s"><optionalFileGroups order="Explicit">'
            f'<group name="g" type="SelectExactlyOne"><plugins order="Explicit">{body}</plugins></group></optionalFileGroups></installStep></installSteps></config>')
    results = {}
    with tempfile.TemporaryDirectory() as t:
        a = os.path.join(t, "model-no-images"); make(a, [r"A\meshes\x.nif", r"B\meshes\y.nif"], [("A", "A", None), ("B", "B", None)])
        b = os.path.join(t, "model-with-images"); make(b, [r"A\meshes\x.nif", r"B\meshes\y.nif", r"fomod\images\a.jpg", r"fomod\images\b.jpg"],
                                                       [("A", "A", r"fomod\images\a.jpg"), ("B", "B", r"fomod\images\b.jpg")])
        c = os.path.join(t, "dll-only"); make(c, [r"SE\SKSE\Plugins\x.dll", r"AE\SKSE\Plugins\x.dll"], [("SE", "SE", None), ("AE", "AE", None)])
        d = os.path.join(t, "model-image-missing"); make(d, [r"A\meshes\x.nif"], [("A", "A", r"fomod\images\gone.jpg")])
        for k, want in ((a, 1), (b, 0), (c, 0), (d, 1)):
            results[os.path.basename(k)] = (run(k), want)
    ok = all(g == w for g, w in results.values())
    print("self-test", "PASS" if ok else "FAIL", {k: f"exit {g} (want {w})" for k, (g, w) in results.items()})
    return 0 if ok else 1


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--path")
    ap.add_argument("--repo")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return self_test()
    if not a.path:
        ap.error("--path is required")
    return run(a.path)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
