"""THE BANNER HIGHLIGHT GATE (2026-10-12).

make-feature-banners.py once found a template's picture pane with a regex that stopped at the first </div> after the
pane's comment - the template's FIRST highlight box. A template with two or more boxes left the others, and the old
pane's closing tag, on the new banner: stray gold boxes over a picture they were never measured for. The tool now
parses the pane and checks its own output; this gate reads the banners already in a Nexus distro folder.

Every banner-*.html in the folder (top level - what gets posted) that the tool made (data-generator="make-feature-banners"):
  * FAIL - a highlight box (class "hl") outside the picture pane;
  * FAIL - the pane holds a different number of boxes than it declares: data-highlights="N" (written since this fix),
    or, on an older banner, its comment ("the boxes below mark ..." means at least one, "none - the subject is the
    whole screen" means none);
  * WARN - a </div> that closes nothing (the old pane's tail, left by the same bug; rebuilding the banner with the
    fixed tool removes it). Reported, not failed: it moves no box.

Usage:
  python banner-highlight-gate.py --path <distro folder>
Exit 1 on any FAIL; each hit is printed as a FAIL line.
"""
import argparse
import glob
import importlib.util
import os
import re
import subprocess
import sys


def load_tool():
    resolver = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "resolvers", "resolve.py")
    r = subprocess.run([sys.executable, resolver, "find", "make-feature-banners"], capture_output=True, text=True)
    path = (r.stdout or "").strip().splitlines()[0] if r.returncode == 0 and r.stdout.strip() else None
    if not path or not os.path.isfile(path):
        print("FAIL cannot resolve role make-feature-banners: " + (r.stdout + r.stderr).strip())
        sys.exit(1)
    spec = importlib.util.spec_from_file_location("make_feature_banners", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def check(text, tool):
    """(fails, warns) for one banner's text."""
    fails, warns = [], []
    pane = tool.find_pane(text)
    if pane is None:
        return ["the picture pane is missing or never closed"], warns
    strays, orphans = tool.stray_highlights(text)
    if strays:
        fails.append(f"{len(strays)} highlight box(es) outside the picture pane")
    m = re.search(r'data-generator="make-feature-banners"[^>]*?data-highlights="(\d+)"', text)
    head = text[pane[0]:pane[1]]
    if m:
        if int(m.group(1)) != pane[2]:
            fails.append(f"the pane declares {m.group(1)} highlight(s) and holds {pane[2]}")
    elif "none - the subject is the whole screen" in head and pane[2]:
        fails.append(f"the pane says it has no highlight and holds {pane[2]}")
    elif "the boxes below mark" in head and not pane[2]:
        fails.append("the pane says it has highlight boxes and holds none")
    if orphans:
        warns.append(f"{len(orphans)} </div> closing nothing (rebuild with make-feature-banners.py to drop it)")
    return fails, warns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True)
    ap.add_argument("--repo")
    a = ap.parse_args()
    tool = load_tool()
    n_fail = 0
    for f in sorted(glob.glob(os.path.join(a.path, "banner-*.html"))):
        text = open(f, encoding="utf-8", errors="replace").read()
        if 'data-generator="make-feature-banners"' not in text:
            continue
        fails, warns = check(text, tool)
        for x in fails:
            print(f"FAIL {os.path.basename(f)}: {x}")
        for x in warns:
            print(f"WARN {os.path.basename(f)}: {x}")
        n_fail += len(fails)
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
