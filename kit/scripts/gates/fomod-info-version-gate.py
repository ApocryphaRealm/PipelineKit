"""Refuses a package whose FOMOD fomod\\info.xml <Version> is not the package's own version.

package-mod.ps1 seeds a new package from the previous release's installer, so fomod\\info.xml came along with the old
number and nothing compared it (QuickLoot Container Merge 1.1.0 and Unbind Vanilla Controls 1.5.0 both packaged with the
previous version in the installer, 2026-11-06). The package's version is read from its folder name ("<Mod> X.Y.Z").
A package with no fomod\\info.xml, or an info.xml with no <Version>, passes.

package-gate runs it through the gate-rules row `fomod-info-version-is-the-package-version` (kind package-script-passes),
so it is called with --path <package> [--repo <repo>].

Usage: py -3 fomod-info-version-gate.py --path <package folder> [--repo X]
"""
import argparse
import os
import re
import sys


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True)
    ap.add_argument("--repo")
    a = ap.parse_args(argv)
    pkg = os.path.normpath(a.path)
    m = re.search(r" (\d+\.\d+\.\d+)$", os.path.basename(pkg))
    if not m:
        print("fomod-info-version-gate: SKIP - no X.Y.Z at the end of the package folder name: %s" % pkg)
        return 0
    want = m.group(1)
    info = os.path.join(pkg, "fomod", "info.xml")
    if not os.path.isfile(info):
        print("fomod-info-version-gate: OK - no fomod\\info.xml")
        return 0
    raw = open(info, "rb").read()
    for enc in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            text = raw.decode(enc)
            if "<" in text:
                break
        except UnicodeDecodeError:
            continue
    found = re.findall(r"<Version[^>]*>\s*([^<]*?)\s*</Version>", text, re.I)
    if not found:
        print("fomod-info-version-gate: OK - fomod\\info.xml has no <Version>")
        return 0
    bad = [v for v in found if v != want]
    if bad:
        print("fomod-info-version-gate: FAIL - fomod\\info.xml says <Version>%s</Version>, the package is %s (%s)"
              % (bad[0], want, info))
        return 1
    print("fomod-info-version-gate: OK - fomod\\info.xml <Version> is %s" % want)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
