r"""THE LICENCE-LABEL GATE (2026-10-08): the licence a DLL states about itself must be the licence its repo carries.

Lock Interaction Overhaul was taken down from Nexus over an MIT label on a GPL build. On 2026-09-16 Compass Navigation
Overhaul, Dragon's Eye Minimap (SMF) and Local Map Upgrade were relicensed to GPL-3 - but only their LICENSE changed;
`cmake/version.rc.in` kept `LegalCopyright "MIT License"`, so every DLL built since said MIT in its own file
properties. Nothing compared the two; the 2026-10-08 archive sweep found it.

    python licence-label-gate.py --path <package> [--repo <repo>]     (package-script-passes; also runs on its own)
    python licence-label-gate.py --repo <repo>

Reads the repo's LICENSE (GPL / LGPL / MIT / other) and every LegalCopyright in the repo's *.rc / *.rc.in outside build
folders. FAIL (exit 1) when they name different licence families. SKIP (exit 0) without a repo, LICENSE or resource file.
"""
import os, re, sys

sys.stdout.reconfigure(encoding="utf-8")
args = sys.argv[1:]
repo = args[args.index("--repo") + 1] if "--repo" in args else None
SKIP_DIRS = {"build", "extern", "external", ".git", "vcpkg_installed", "dist", "out", "sdk"}


def family(text):
    t = text.upper()
    if "LESSER GENERAL PUBLIC" in t or re.search(r"\bLGPL", t):
        return "LGPL"
    if "GENERAL PUBLIC LICENSE" in t or re.search(r"\bGPL", t):
        return "GPL"
    if re.search(r"\bMIT\b", t):
        return "MIT"
    return None


if not repo or not os.path.isdir(repo):
    print("licence-label-gate  SKIP  no repo")
    sys.exit(0)
lic = next((os.path.join(repo, n) for n in ("LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING") if os.path.isfile(os.path.join(repo, n))), None)
if not lic:
    print("licence-label-gate  SKIP  the repo has no LICENSE")
    sys.exit(0)
# The licence is named in its TITLE - the first few non-empty lines. A later mention (an MIT LICENSE noting that an
# optional devbench.dll is a separate GPL program) must not decide it.
head = [l for l in open(lic, encoding="utf-8", errors="replace").read(4000).splitlines() if l.strip()][:3]
repo_family = family("\n".join(head))
labels = []
for base, dirs, files in os.walk(repo):
    dirs[:] = [d for d in dirs if d.lower() not in SKIP_DIRS and not d.lower().startswith("build")]
    for f in files:
        if f.lower().endswith((".rc", ".rc.in")):
            p = os.path.join(base, f)
            for m in re.finditer(r'"LegalCopyright"\s*,\s*"([^"]*)"', open(p, encoding="utf-8", errors="replace").read()):
                labels.append((os.path.relpath(p, repo), m.group(1)))
if not labels:
    print("licence-label-gate  SKIP  no LegalCopyright in a resource file")
    sys.exit(0)
bad = [(p, v) for p, v in labels if family(v) and family(v) != repo_family]
for p, v in labels:
    print(f"licence-label-gate  {'FAIL' if (p, v) in bad else 'PASS'}  {p}: \"{v}\" vs LICENSE {repo_family}")
sys.exit(1 if bad else 0)
