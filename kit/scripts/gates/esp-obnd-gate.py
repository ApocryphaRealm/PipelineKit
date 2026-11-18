"""THE OBJECT BOUNDS GATE (2026-11-16, Nordic Skyforged Armor and Weapons 1.1.0).

The Skyforge Steel Shield shipped with OBND 0,0,0 / 0,0,0: build-esp.py copied Legacy of Ysgramor's NW_Wolf_Shield_Steel
record, whose own bounds are zero. With Immersive Equipment Displays the favourited, unequipped shield did not show on
the player's back, while the vanilla-record Ebony Shield (bounds -23,-35,-9 / 23,27,2) did; every other item in the
plugin had real bounds. The Creation Kit writes bounds from the model; a generator that copies or writes records by
hand has to do the same, and nothing checked it.

Fails on any ARMO that carries a ground model (MOD2), or WEAP / AMMO that carries a model (MODL), whose OBND is all
zero, in any plugin (.esp/.esm/.esl) under the package. Only records the plugin itself DEFINES are checked (an override
keeps the master's bounds as the master has them - Skyrim.esm's own MS06ShieldL18 is all zero), and not items built on
a template (ARMO TNAM, WEAP CNAM: the game's enchanted variants carry zero and take the template's). Items with no
model (skins, unarmed) are not checked.

Usage:  python esp-obnd-gate.py --path <package folder> [--repo <repo>]      exit 1 on any hit
"""
import argparse, os, struct, sys, zlib

CHECK = {b"ARMO": b"MOD2", b"WEAP": b"MODL", b"AMMO": b"MODL"}
TEMPLATE = {b"ARMO": b"TNAM", b"WEAP": b"CNAM"}


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
    hs = struct.unpack_from("<I", d, 4)[0]
    tes4 = d[24:24 + hs]
    if struct.unpack_from("<I", d, 8)[0] & 0x00040000:
        tes4 = zlib.decompress(tes4[4:])
    own = sum(1 for s, v in subrecords(tes4) if s == b"MAST")     # a plugin's own records carry index = master count

    def walk(off, end):
        while off + 24 <= end:
            t = d[off:off + 4]; n = struct.unpack_from("<I", d, off + 4)[0]
            if t == b"GRUP":
                if n < 24:
                    return
                walk(off + 24, off + n); off += n; continue
            if t in CHECK:
                flags, fid = struct.unpack_from("<II", d, off + 8)
                if fid >> 24 != own:
                    off += 24 + n
                    continue
                body = d[off + 24:off + 24 + n]
                if flags & 0x00040000:
                    body = zlib.decompress(body[4:])
                subs = list(subrecords(body))
                templated = any(s == TEMPLATE.get(t) and len(v) == 4 and struct.unpack("<I", v)[0] for s, v in subs)
                if not templated and any(s == CHECK[t] and v.strip(b"\x00") for s, v in subs):
                    ob = next((v for s, v in subs if s == b"OBND"), None)
                    if ob is None or len(ob) != 12 or not any(struct.unpack("<6h", ob)):
                        edid = next((v.split(b"\x00")[0].decode("latin-1") for s, v in subs if s == b"EDID"), "")
                        hits.append("%s %08X %s: OBND %s" % (t.decode(), fid, edid,
                                                             "missing" if ob is None else "all zero"))
            off += 24 + n
    walk(24 + hs, len(d))
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True)
    ap.add_argument("--repo")
    a = ap.parse_args()
    bad = 0
    for root, dirs, files in os.walk(a.path):
        dirs[:] = [x for x in dirs if x.lower() != "_work"]
        for f in files:
            if f.lower().endswith((".esp", ".esm", ".esl")):
                p = os.path.join(root, f)
                for h in scan(p):
                    print("FAIL %s: %s - write the item's bounds from its model (as the Creation Kit does)"
                          % (os.path.relpath(p, a.path), h))
                    bad += 1
    if bad:
        return 1
    print("OK: no item with a model has all-zero object bounds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
