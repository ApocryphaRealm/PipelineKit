"""Refuses a package whose repo keeps its own FOMOD installer that the package does not carry, byte for byte.

Why (Simple Dodge 1.2.0, 2026-11-12): the installer gained a "Step distance: Normal / Shorter" step. The repo held the
new fomod\\ModuleConfig.xml and the Shorter option's files under fomod-options\\Step-Shorter\\, but package-mod.ps1
seeded the package from the previous release and copied only fomod\\info.xml from the repo - so the package would have
shipped 1.1.0's installer (no Step distance step) and no Step-Shorter folder at all, with every other row passing.
package-mod.ps1 now copies both; this row proves a package actually has them.

THE RULE (only when the repo has fomod\\ModuleConfig.xml):
    * the package has fomod\\ModuleConfig.xml and it is the repo's file (same bytes);
    * for every file under the repo's fomod-options\\<Option>\\..., the package has <Option>\\... with the same bytes
      (an option folder sits at the package root, beside Common\\, as the installer's <folder source="..."> names it);
    * every <folder source="X"> / <file source="X"> the repo's ModuleConfig names exists in the package.
A repo without fomod\\ModuleConfig.xml is not judged (exit 0): its installer, if any, comes from the seed.

package-gate runs it through the gate-rules row `repo-fomod-installer-ships` (kind package-script-passes).
Usage: py -3 fomod-repo-installer-shipped-gate.py --path <package folder> --repo <repo>     exit 1 on any miss
       py -3 fomod-repo-installer-shipped-gate.py --self-test
"""
import argparse, hashlib, os, shutil, sys, tempfile
import xml.etree.ElementTree as ET


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def sub_packages(pkg):
    """SEVERAL DOWNLOADS (2026-11-16, Truly Nordic Ebony / Skyforged 1.0.0: a 3D main file and a Flat optional file,
    each its own FOMOD from the same repo installer): a version folder with no fomod\\ of its own whose subfolders each
    carry fomod\\ModuleConfig.xml is judged one subfolder at a time."""
    if os.path.isfile(os.path.join(pkg, "fomod", "ModuleConfig.xml")) or not os.path.isdir(pkg):
        return []
    return sorted(d for d in os.listdir(pkg) if os.path.isfile(os.path.join(pkg, d, "fomod", "ModuleConfig.xml")))


def check(pkg, repo):
    subs = sub_packages(pkg)
    if subs:
        allm, notes = [], []
        for d in subs:
            m, n = check(os.path.join(pkg, d), repo)
            allm += ["%s: %s" % (d, x) for x in m]; notes.append("%s: %s" % (d, n))
        return allm, "; ".join(notes)
    misses = []
    mc = os.path.join(repo, "fomod", "ModuleConfig.xml")
    if not os.path.isfile(mc):
        return misses, "repo has no fomod\\ModuleConfig.xml - not judged"
    pmc = os.path.join(pkg, "fomod", "ModuleConfig.xml")
    if not os.path.isfile(pmc):
        misses.append("package has no fomod\\ModuleConfig.xml (the repo has one)")
    elif sha(pmc) != sha(mc):
        misses.append("package fomod\\ModuleConfig.xml is not the repo's (seeded from an older release?)")
    opts = os.path.join(repo, "fomod-options")
    n = 0
    if os.path.isdir(opts):
        for root, _, files in os.walk(opts):
            for f in files:
                src = os.path.join(root, f)
                rel = os.path.relpath(src, opts)
                n += 1
                dst = os.path.join(pkg, rel)
                if not os.path.isfile(dst):
                    misses.append("package lacks installer option file %s" % rel)
                elif sha(dst) != sha(src):
                    misses.append("package %s is not the repo's fomod-options\\%s" % (rel, rel))
    try:
        root = ET.parse(mc).getroot()
        for el in root.iter():
            tag = el.tag.split("}")[-1]
            if tag in ("folder", "file") and el.get("source"):
                s = el.get("source").replace("/", os.sep).replace("\\", os.sep)
                if not os.path.exists(os.path.join(pkg, s)):
                    misses.append("ModuleConfig names %s '%s', which the package does not have" % (tag, el.get("source")))
    except ET.ParseError as e:
        misses.append("repo ModuleConfig.xml does not parse: %s" % e)
    return misses, "%d option file(s) checked" % n


def self_test():
    t = tempfile.mkdtemp(prefix="fomod-repo-gate-")
    try:
        repo, pkg = os.path.join(t, "repo"), os.path.join(t, "pkg")
        os.makedirs(os.path.join(repo, "fomod")); os.makedirs(os.path.join(repo, "fomod-options", "Opt", "a"))
        cfg = ('<config><requiredInstallFiles><folder source="Common" destination=""/></requiredInstallFiles>'
               '<installSteps><installStep><optionalFileGroups><group><plugins><plugin><files>'
               '<folder source="Opt" destination="" priority="1"/></files></plugin></plugins></group>'
               '</optionalFileGroups></installStep></installSteps></config>')
        open(os.path.join(repo, "fomod", "ModuleConfig.xml"), "w").write(cfg)
        open(os.path.join(repo, "fomod-options", "Opt", "a", "x.txt"), "w").write("new")
        # 1: seeded package with an OLD installer and no option folder -> FAIL
        os.makedirs(os.path.join(pkg, "fomod")); os.makedirs(os.path.join(pkg, "Common"))
        open(os.path.join(pkg, "fomod", "ModuleConfig.xml"), "w").write("<config/>")
        m1, _ = check(pkg, repo)
        assert len(m1) >= 3, m1
        # 2: the repo's installer and option copied -> PASS
        shutil.copy(os.path.join(repo, "fomod", "ModuleConfig.xml"), os.path.join(pkg, "fomod", "ModuleConfig.xml"))
        shutil.copytree(os.path.join(repo, "fomod-options", "Opt"), os.path.join(pkg, "Opt"))
        m2, _ = check(pkg, repo)
        assert m2 == [], m2
        # 3: option file edited in the package -> FAIL
        open(os.path.join(pkg, "Opt", "a", "x.txt"), "w").write("stale")
        m3, _ = check(pkg, repo)
        assert len(m3) == 1 and "not the repo's" in m3[0], m3
        # 5: several downloads - a version folder holding two packages, one good, one with an old installer -> FAIL
        open(os.path.join(pkg, "Opt", "a", "x.txt"), "w").write("new")
        ver = os.path.join(t, "ver"); shutil.copytree(pkg, os.path.join(ver, "3D")); shutil.copytree(pkg, os.path.join(ver, "Flat"))
        m5a, _ = check(ver, repo)
        assert m5a == [], m5a
        open(os.path.join(ver, "Flat", "fomod", "ModuleConfig.xml"), "w").write("<config/>")
        m5, _ = check(ver, repo)
        assert len(m5) == 1 and m5[0].startswith("Flat: "), m5
        # 4: repo without its own installer -> not judged
        os.remove(os.path.join(repo, "fomod", "ModuleConfig.xml"))
        m4, why = check(pkg, repo)
        assert m4 == [] and "not judged" in why, (m4, why)
        print("self-test PASS (5 cases)")
        return 0
    finally:
        shutil.rmtree(t, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path"); ap.add_argument("--repo"); ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.path or not a.repo:
        print("fomod-repo-installer-shipped  pass  no repo given - not judged")
        return 0
    misses, note = check(a.path, a.repo)
    if misses:
        for m in misses:
            print("FAIL fomod-repo-installer-shipped: " + m)
        return 1
    print("fomod-repo-installer-shipped  pass  " + note)
    return 0


if __name__ == "__main__":
    sys.exit(main())
