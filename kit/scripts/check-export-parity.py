#!/usr/bin/env python3
"""
check-export-parity.py
Fails if Apocrypha Menu Framework's export table is not a SUPERSET of SKSE Menu Framework's.

    python check-export-parity.py <amf.dll> [<smf.dll>]

WHY THIS EXISTS
    A mod written for SKSE Menu Framework does not link against a framework. It resolves every
    drawing function it uses by name through GetProcAddress, so a name the framework does not export
    comes back null - the mod's page still registers and still appears in the list, and the part of
    it that needed the missing function silently draws nothing. That is what a user reported on
    2026-09-10 as "settings show up as blank", and it is invisible from our side: no error, no log
    line, nothing in a crash report.

    Because the failure is silent, it was only ever found by a user noticing. Names had been added
    three times by scanning whichever consumer mods happened to be installed - 65 in 1.5.9, 38 in
    1.7.1 - and each pass covered only what somebody had on disk. 1.7.2 closed the gap properly by
    vendoring cimgui, and this check is what keeps it closed: a build that drops below parity fails
    here rather than in somebody's game.

USE
    Standalone, or from pre-finalize-check.ps1. Exit code 0 = parity or better, 1 = a name is
    missing, 2 = could not read one of the files.
"""
import os
import struct
import sys

# The SME MO2 instance that used to hold this was deleted 2026-09-11, so a reference copy of
# the real SKSEMenuFramework.dll is kept in the project instead. Without a baseline this check
# can only SKIP, and a SKIP here silently removes the protection it exists to provide.
DEFAULT_SMF = os.path.join(os.environ.get("PIPELINE_ROOT") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "2. Mod Types", "Framework or Utility", "SKSE Menu Framework (reference copy)", "SKSEMenuFramework.dll")  # kit: under <ROOT>


def exports(path):
    """Every exported name in a PE image, read from its export directory."""
    with open(path, "rb") as f:
        d = f.read()
    pe = struct.unpack_from("<I", d, 0x3C)[0]
    if d[pe:pe + 4] != b"PE\0\0":
        raise ValueError(f"not a PE image: {path}")
    nsec = struct.unpack_from("<H", d, pe + 6)[0]
    optsz = struct.unpack_from("<H", d, pe + 20)[0]
    opt = pe + 24
    magic = struct.unpack_from("<H", d, opt)[0]
    dirs = opt + (112 if magic == 0x20b else 96)     # data directories; export is the first
    rva, _size = struct.unpack_from("<II", d, dirs)
    if rva == 0:
        return set()

    sech = opt + optsz
    secs = []
    for i in range(nsec):
        o = sech + i * 40
        vsz, va, rsz, praw = (struct.unpack_from("<I", d, o + k)[0] for k in (8, 12, 16, 20))
        secs.append((va, max(vsz, rsz), praw))

    def off(r):
        for va, sz, praw in secs:
            if va <= r < va + sz:
                return praw + (r - va)
        raise ValueError(f"rva {r:#x} is in no section")

    e = off(rva)
    count = struct.unpack_from("<I", d, e + 24)[0]
    names_at = off(struct.unpack_from("<I", d, e + 32)[0])
    out = set()
    for i in range(count):
        p = off(struct.unpack_from("<I", d, names_at + 4 * i)[0])
        out.add(d[p:d.index(b"\0", p)].decode("latin1"))
    return out


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    amf_path = argv[0]
    smf_path = argv[1] if len(argv) > 1 else DEFAULT_SMF

    for label, p in (("AMF", amf_path), ("SMF", smf_path)):
        if not os.path.exists(p):
            print(f"SKIP: {label} not found at {p}")
            return 2

    amf, smf = exports(amf_path), exports(smf_path)
    # Loader entry points are not part of the consumer surface: SKSEPlugin_Load/Query/Version are what SKSE calls,
    # not what a mod's page calls. An Oblivion Remastered build exports OBSEPlugin_Load instead and can never carry
    # them (2026-09-26, Apocrypha Menu Framework for Oblivion Remastered 1.0.1 - the only three "missing" names).
    if any(n.startswith("OBSEPlugin_") for n in amf):
        smf = {n for n in smf if not n.startswith("SKSEPlugin_")}
    missing = sorted(smf - amf)

    print(f"SKSE Menu Framework exports : {len(smf)}")
    print(f"Apocrypha Menu Framework    : {len(amf)}")
    if missing:
        print(f"\nFAIL: {len(missing)} name(s) SMF exports and this build does not.")
        print("Any consumer calling one of these gets a null pointer back, and that part of its")
        print("settings page draws nothing at all - with no error anywhere.\n")
        for m in missing[:60]:
            print("   ", m)
        if len(missing) > 60:
            print(f"    ... and {len(missing) - 60} more")
        return 1

    print(f"\nPASS: full parity. This build also exports {len(amf - smf)} name(s) of its own.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
