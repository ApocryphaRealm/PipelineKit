"""Print every install destination a package can deliver, one lower-case relative path per line.

    python fomod-destinations.py <package folder>

A FOMOD package (fomod\\ModuleConfig.xml): every <file>/<folder> entry anywhere in the installer - required files,
every option of every step, conditional installs - with folders expanded to their files. A flat package: its own
files. Used by package-gate.ps1 rule kind fomod-delivers-previous-files (2026-09-24: Norden UI - Black 1.0.3's
installer could not deliver Interface\\racemenu\\buttonart.swf, which 1.0.2 shipped).
"""
import os, sys
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")
pkg = sys.argv[1]
mc = os.path.join(pkg, "fomod", "ModuleConfig.xml")
out = set()
if os.path.isfile(mc):
    for el in ET.parse(mc).getroot().iter():
        if el.tag not in ("file", "folder") or el.get("source") is None:
            continue
        src = os.path.join(pkg, el.get("source").replace("/", "\\"))
        dst = (el.get("destination") or "").replace("/", "\\")
        if el.tag == "file":
            out.add((dst if el.get("destination") is not None else os.path.basename(src)).lower())
        else:
            for dp, _, fn in os.walk(src):
                for f in fn:
                    rel = os.path.relpath(os.path.join(dp, f), src)
                    out.add((os.path.join(dst, rel) if dst else rel).lower())
else:
    for dp, _, fn in os.walk(pkg):
        for f in fn:
            out.add(os.path.relpath(os.path.join(dp, f), pkg).lower())
for p in sorted(out):
    print(p)
