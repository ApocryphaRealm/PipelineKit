"""line17-gate.py --path <package> [--repo <repo>] - a Skyrim SKSE DLL package must reach Skyrim 1.7.x.

Gate row `skse-dll-package-ships-line-17` (2026-11-07). The owner, 2026-11-07: "Figure out which mods are lacking the 1.7
build and start building it" - a Nexus player on Perfected Wheeler had been told a 1.7.x build was coming, and the
inventory found fourteen DLL mods that shipped the SE/AE DLL alone. A CommonLibSSE-NG 3.7 / b93280e DLL calls a 1.7 game
"SE", looks for version-1-7-104-0.bin and fails with "failed to open the address library file" - so a 1.7 player is
told his Address Library is missing when the mod simply has no 1.7 build.

PASS when the package is not a Skyrim SKSE DLL package, or it has a `Line-17` folder (the two-line FOMOD), or the repo's
own vendored CommonLib already reads 1.7 (its include/SKSE/Version.h defines RUNTIME_SSE_1_7_*: alandtse CommonLibVR
7.0+ / CommonLibSSE-NG 11+, one DLL for SE, AE and 1.7 - Localized Damage, DTD Bloodpool Patch, Beyond Mastery).
A mod deliberately left without a 1.7 build is listed in the row's exemptMods with the reason in the row.
"""
import argparse, os, re, sys

ap = argparse.ArgumentParser()
ap.add_argument("--path", required=True)
ap.add_argument("--repo")
a = ap.parse_args()
pkg = a.path

PROXY = re.compile(r"(?i)^(dinput8|winmm|version|dsound|d3d11|dxgi|xinput1_3)\.dll$")
dlls, has17 = [], False
for dp, dn, fn in os.walk(pkg):
    rel = os.path.relpath(dp, pkg)
    if any(d.lower() == "line-17" for d in dn) or os.path.basename(dp).lower() == "line-17":
        has17 = True
    low = rel.replace("\\", "/").lower()
    if "oblivionremastered" in low or "bin/x64" in low:
        print("OK  not a Skyrim package"); sys.exit(0)
    if "skse/plugins" in low:
        dlls += [os.path.join(rel, f) for f in fn if f.lower().endswith(".dll") and not PROXY.match(f)]

if not dlls:
    print("OK  no SKSE plugin DLL"); sys.exit(0)

# Only mods on Nexus need a 1.7 build (the owner, 2026-11-07: "you didn't need to make a 1.7 version for mods that aren't
# even posted on Nexus, because I don't use that version of the game"). A repo whose registry entry has no nexusModId passes.
if a.repo:
    try:
        import json
        reg = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "version-registry.json"),
                             encoding="utf-8-sig"))
        repo_name = os.path.basename(os.path.normpath(a.repo)).lower()
        for e in reg.values():
            if isinstance(e, dict) and str(e.get("repo", "")).lower() == repo_name and not e.get("nexusModId"):
                print("OK  not on Nexus - a 1.7 build is only needed for a posted mod"); sys.exit(0)
    except (OSError, ValueError):
        pass
if has17:
    print("OK  ships a Line-17 build"); sys.exit(0)

if a.repo and os.path.isdir(a.repo):
    for dp, dn, fn in os.walk(a.repo):
        dn[:] = [d for d in dn if d.lower() not in ("build", ".git", "node_modules", "vcpkg_installed", "out")]
        if "Version.h" in fn and dp.replace("\\", "/").lower().endswith("include/skse"):
            try:
                if "RUNTIME_SSE_1_7" in open(os.path.join(dp, "Version.h"), encoding="utf-8", errors="replace").read():
                    print("OK  one DLL: the repo's CommonLib (" + os.path.relpath(dp, a.repo) + ") reads Skyrim 1.7.x")
                    sys.exit(0)
            except OSError:
                pass

print("FAIL  " + ", ".join(dlls[:3]) + " ships no Line-17 build and its CommonLib cannot read Skyrim 1.7.x - add the second "
      "build line (cmake/ports-17 + manifest-17, RUNTIME_LINE 17, make-fomod.py; see 4. plans/line17-ports/INVENTORY.md) "
      "or list the mod in the row's exemptMods with the reason")
sys.exit(1)
