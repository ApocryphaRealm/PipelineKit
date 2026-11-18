r"""THE BANNER LICENCE-PILL GATE (2026-10-24): every large banner of a mod with a LICENSE names a licence.

distro-licence-gate.py (2026-10-22) fails a banner whose pill names a licence OTHER than the repo LICENSE's - the
defect Nexus took Lock Interaction Overhaul down for on 2026-09-13 (past-mistakes library 5130). A banner that names
NO licence slipped past it: the 2026-10-24 settings-banner audit found most settings banners (Custom Difficulty UI,
Potion of Clarity, Souls to Perks, Character Progression Control's settings banner, Carryweight on Level Up, Compass
Navigation Overhaul, SkyHUD Settings Menu, Local Map Upgrade, Item Explorer ...) carrying a version pill and no licence
pill at all, so a visitor - or a moderator - reading the gallery cannot see the mod is GPL.

    python distro-banner-pill-gate.py --path <distro folder> --repo <repo>   (package-gate kind distro-repo-script-passes)

Checked: the distro folder's top-level 1920x1080 banner sources (banner-1920x1080*.html, the identity banner and the
settings / feature banners) - their visible text (data: URIs, <style> and <script> are not read) must name a licence
family. The 1300x372 header stays the empty-rim design (_BANNER-DESIGN-RULES.md) and is not checked; assets\ and
backups are skipped. Which licence is named is distro-licence-gate.py's job; this gate only asks that one is named.
FAIL (exit 1) on a banner naming none. SKIP (exit 0) without a repo, a LICENSE or a distro folder.
"""
import argparse, glob, os, sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib.util

_spec = importlib.util.spec_from_file_location("dlg", os.path.join(os.path.dirname(os.path.abspath(__file__)), "distro-licence-gate.py"))
dlg = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(dlg)


def banners(distro):
    out = []
    for p in sorted(glob.glob(os.path.join(distro, "banner-1920x1080*.html"))):
        lf = os.path.basename(p).lower()
        if ".bak" in lf or "before" in lf or "superseded" in lf:
            continue
        out.append(p)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True, help="the mod's 11. Nexus distro folder")
    ap.add_argument("--repo", help="the mod's repo (a LICENSE there makes the pill required)")
    a = ap.parse_args()
    if not a.repo or not os.path.isdir(a.repo):
        print("distro-banner-pill-gate  SKIP  no repo"); return 0
    if not os.path.isdir(a.path):
        print("distro-banner-pill-gate  SKIP  no distro folder"); return 0
    fam, _ = dlg.repo_family(a.repo)
    if not fam:
        print("distro-banner-pill-gate  SKIP  the repo has no LICENSE"); return 0
    bad = 0
    found = banners(a.path)
    for p in found:
        named = dlg.families(dlg.html_text(p))
        ok = bool(named)
        bad += not ok
        print(f"distro-banner-pill-gate  {'PASS' if ok else 'FAIL'}  {os.path.basename(p)}: "
              + (f"names {'/'.join(named)}" if ok else f"names no licence (LICENSE is {fam}) - add a pill such as \"GPL-3.0-or-later, open source\""))
    if not found:
        print("distro-banner-pill-gate  PASS  no 1920x1080 banner source in the distro folder")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
