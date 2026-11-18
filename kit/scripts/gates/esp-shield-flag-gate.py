"""THE SHIELD FLAG GATE (2026-11-16, Nordic Skyforged Armor and Weapons 1.1.0).

An ARMO's record header carries flag 0x40, "Shield", on every shield the game ships (ArmorEbonyShield and the rest).
Nordic Skyforged's build-esp.py wrote every record's header flags as 0, so the Skyforge Steel Shield lost it while its
template (Legacy of Ysgramor's NW_Wolf_Shield_Steel) and the vanilla Ebony Shield carry it. Simple Dual Sheath's
shield-on-back reads the flag: the owner saw our equipped shield stay on the left arm when sheathed and only flash onto
the back during the draw, while the Ebony Shield stayed on the back. The record parsed and looked right in every field
view; only the header flags differ.

Fails on any ARMO in a package plugin (.esp/.esm/.esl), defined or overridden, whose body slots (BOD2 / BODT) include
slot 39 and whose header lacks 0x40, unless it is non-playable (0x4: Skyrim.esm's FXDwarvenSphereCenturion is the
only slot-39 armour in the five masters without the flag).

Usage:  python esp-shield-flag-gate.py --path <package folder> [--repo <repo>]      exit 1 on any hit
"""
import argparse, os, struct, sys, zlib

SLOT_39 = 1 << (39 - 30)
SHIELD = 0x40
NON_PLAYABLE = 0x4      # creature and FX pieces on slot 39 (Skyrim.esm FXDwarvenSphereCenturion) are not shields


def subrecords(body):
    i, big = 0, None
    while i + 6 <= len(body):
        sig = body[i:i + 4]; n = struct.unpack_from("<H", body, i + 4)[0]; i += 6
        if sig == b"XXXX":
            big = struct.unpack_from("<I", body, i)[0]; i += n; continue
        if big is not None:
            n, big = big, None
        yield sig, body[i:i + n]; i += n


def scan(path):
    d = open(path, "rb").read()
    hits = []
    if d[:4] != b"TES4":
        return hits

    def walk(off, end):
        while off + 24 <= end:
            t = d[off:off + 4]; n = struct.unpack_from("<I", d, off + 4)[0]
            if t == b"GRUP":
                if n < 24:
                    return
                walk(off + 24, off + n); off += n; continue
            if t == b"ARMO":
                flags, fid = struct.unpack_from("<II", d, off + 8)
                body = d[off + 24:off + 24 + n]
                if flags & 0x00040000:
                    body = zlib.decompress(body[4:])
                subs = list(subrecords(body))
                bod = next((v for s, v in subs if s in (b"BOD2", b"BODT")), b"")
                if len(bod) >= 4 and struct.unpack_from("<I", bod)[0] & SLOT_39 and not flags & (SHIELD | NON_PLAYABLE):
                    edid = next((v.split(b"\x00")[0].decode("latin-1") for s, v in subs if s == b"EDID"), "")
                    hits.append("ARMO %08X %s: slot 39 without the Shield flag (header flags %08X)" % (fid, edid, flags))
            off += 24 + n
    walk(24 + struct.unpack_from("<I", d, 4)[0], len(d))
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True)
    ap.add_argument("--repo")
    a = ap.parse_args()
    paths = [a.path] if os.path.isfile(a.path) else [os.path.join(r, f) for r, ds, fs in os.walk(a.path)
                                                     if "_work" not in r.lower().split(os.sep) for f in fs
                                                     if f.lower().endswith((".esp", ".esm", ".esl"))]
    bad = 0
    for p in paths:
        for h in scan(p):
            print("FAIL %s: %s - set record flag 0x40 (Shield), as the game's shields carry it" % (os.path.relpath(p, a.path) if p != a.path else p, h))
            bad += 1
    if bad:
        return 1
    print("OK: every slot-39 armour carries the Shield flag")
    return 0


if __name__ == "__main__":
    sys.exit(main())
