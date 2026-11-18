"""THE XINPUT IMPORT GATE (the owner, 2026-09-27: Outfit Wheeler left his controller dead "as long as that mod is loaded
and activated on Mod Organizer 2 ... even on the main menu").

Skyrim imports XINPUT1_3.dll. An SKSE plugin that links any OTHER XInput DLL in its import table (xinput1_4,
xinput9_1_0) makes Windows load it the moment SKSE loads the plugin, before the game's controller is up, and a
Steam Input pad (PlayStation, Switch, generic) never reaches the game for the whole session. Proven with a virtual
DualShock 4: Outfit Wheeler 3.2 as released - 0 gamepad events; its import renamed to XINPUT1_3 - pad back.
Loading XInput LATER (on first use) was harmless in the same test.

Usage:
  python xinput-import-gate.py --profile "Njordlinger Test"     every enabled mod's SKSE\\Plugins DLLs
  python xinput-import-gate.py --path <folder>                   every DLL under a folder (a package)
Exit 1 on any hit. Fix: resolve XInputGetState from the game's loaded module on first use (GetModuleHandleW), never
link or load one; for a third-party DLL, rename the import to XINPUT1_3.dll (same length, ordinal 2 = XInputGetState).
"""
import argparse, os, struct, sys

GAME_XINPUT = "xinput1_3.dll"
NJ = os.path.dirname(((os.environ.get("PIPELINE_MO2_INSTANCES") or "").split(";")[0]).rstrip("\\/"))  # kit: the first MO2 instance


def import_names(path):
    b = open(path, "rb").read()
    if b[:2] != b"MZ":
        return []
    pe = struct.unpack_from("<I", b, 0x3C)[0]
    if b[pe:pe + 4] != b"PE\0\0":
        return []
    nsec = struct.unpack_from("<H", b, pe + 6)[0]
    optsz = struct.unpack_from("<H", b, pe + 20)[0]
    magic = struct.unpack_from("<H", b, pe + 24)[0]
    dd = pe + 24 + (112 if magic == 0x20B else 96)
    imp_rva = struct.unpack_from("<I", b, dd + 8)[0]
    secs = []
    o = pe + 24 + optsz
    for _ in range(nsec):
        vs, va, rs, ra = struct.unpack_from("<IIII", b, o + 8)
        secs.append((va, max(vs, rs), ra))
        o += 40

    def off(rva):
        for va, sz, ra in secs:
            if va <= rva < va + sz:
                return rva - va + ra
        return None

    names = []
    p = off(imp_rva) if imp_rva else None
    while p is not None and p + 20 <= len(b):
        name_rva = struct.unpack_from("<I", b, p + 12)[0]
        if name_rva == 0:
            break
        q = off(name_rva)
        if q is None:
            break
        names.append(b[q:b.index(b"\0", q)].decode(errors="replace"))
        p += 20
    return names


def bad_imports(path):
    try:
        return [n for n in import_names(path) if n.lower().startswith("xinput") and n.lower() != GAME_XINPUT]
    except Exception as e:  # unreadable DLL - report, do not pass silently
        return [f"unreadable: {e}"]


def dlls_for_profile(profile):
    rows = open(os.path.join(NJ, "profiles", profile, "modlist.txt"), encoding="utf-8").read().splitlines()
    for m in (r[1:] for r in rows if r.startswith("+")):
        d = os.path.join(NJ, "mods", m, "SKSE", "Plugins")
        if os.path.isdir(d):
            for f in os.listdir(d):
                if f.lower().endswith(".dll"):
                    yield m, os.path.join(d, f)


def dlls_under(folder):
    for root, _, files in os.walk(folder):
        for f in files:
            if f.lower().endswith(".dll") and "skse" in root.lower():
                yield os.path.relpath(root, folder), os.path.join(root, f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile")
    ap.add_argument("--path")
    a, _ = ap.parse_known_args()   # package-gate also passes --repo
    if not a.profile and not (a.path and os.path.isdir(a.path)):
        print(f"FAIL  xinput-import-gate  no such folder: {a.path}")   # a scan of nothing must never read as a pass
        sys.exit(2)
    items = list(dlls_for_profile(a.profile) if a.profile else dlls_under(a.path))
    if not items:
        print("xinput-import-gate  note  no SKSE plugin DLLs found to check")
    hits = [(m, p, bad) for m, p in items for bad in [bad_imports(p)] if bad]
    for m, p, bad in hits:
        print(f"FAIL  xinput-import-gate  {m} | {os.path.basename(p)} links {', '.join(bad)} at load - a Steam Input "
              f"controller will be dead; rename the import to XINPUT1_3.dll or leave the mod off")
    if not hits:
        print(f"xinput-import-gate  pass  no SKSE plugin links an XInput DLL other than the game's {GAME_XINPUT}")
    sys.exit(1 if hits else 0)


if __name__ == "__main__":
    main()
