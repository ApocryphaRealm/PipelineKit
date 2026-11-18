#!/usr/bin/env python3
r"""Renumber a plugin's own records into the light range, fixing every reference to them.

WHY
    A light plugin's new records must live in 0x000800-0x000FFF. Most plugins were not written with
    that in mind, so making one light means renumbering - and renumbering means finding every field
    that POINTS at a renumbered record and moving it too. Miss one and the plugin loads happily
    while a recipe produces nothing, or an outfit dresses an NPC in air.

    Written for Gypsymama's Tullius outfit replacer (21 records at 0x005900-0x038325) on
    2026-09-16, and deliberately built as the core of the larger merge that follows.

THE SCHEMA IS WRITTEN DOWN, NOT GUESSED
    An earlier attempt derived reference fields by looking for values that resolve to real records.
    It found the true ones - and also flagged a mesh path, an editor ID and a bounding box, because
    a filename's bytes can look like a FormID. So the table below is explicit, and anything this
    script meets that is NOT in it causes a refusal rather than a silent pass.

WHAT IT REFUSES TO DO
    * renumber a record type it has no schema for;
    * produce more new records than the light range holds;
    * leave a reference pointing at an old number - it re-reads its own output and checks.

Usage:  python renumber-to-esl.py <plugin> --out <new plugin> [--first 0x800]
"""
import argparse
import os
import struct

# Subrecords that hold FormIDs, per record type. "*" means an array of 4-byte FormIDs.
SCHEMA = {
    "ARMO": {"MODL": "*", "EITM": 1, "ETYP": 1, "BIDS": 1, "BAMT": 1, "KWDA": "*", "RNAM": 1,
             "TNAM": 1, "YNAM": 1, "ZNAM": 1, "DNAM": 0, "BOD2": 0, "BODT": 0},
    "ARMA": {"RNAM": 1, "MODL": "*", "SNDD": 1, "NAM0": 1, "NAM1": 1, "NAM2": 1, "NAM3": 1,
             "DNAM": 0, "BOD2": 0, "BODT": 0},
    "WEAP": {"ETYP": 1, "BIDS": 1, "BAMT": 1, "INAM": 1, "WNAM": 1, "TNAM": 1, "NAM9": 1,
             "NAM8": 1, "KWDA": "*", "CNAM": 1, "EITM": 1, "YNAM": 1, "ZNAM": 1},
    "STAT": {},
    "COBJ": {"CNAM": 1, "BNAM": 1},          # CNTO handled specially: FormID then a count
    "OTFT": {"INAM": "*"},
    "LVLI": {},                               # LVLO handled specially
    "MISC": {"YNAM": 1, "ZNAM": 1, "KWDA": "*"},
    "KYWD": {},
    "GLOB": {},
}
# Subrecords whose layout is not a plain FormID array.
SPECIAL = {"CNTO": "formid+u32", "LVLO": "u32+formid+u32", "COED": "formid+formid+f32"}

ESL_FIRST, ESL_LAST = 0x000800, 0x000FFF


def fail(msg):
    raise SystemExit("renumber-to-esl: " + msg)


def subrecords(data):
    i = 0
    while i + 6 <= len(data):
        sig = data[i:i+4]
        n = struct.unpack("<H", data[i+4:i+6])[0]
        i += 6
        yield sig, data[i:i+n]
        i += n


def load(path):
    d = open(path, "rb").read()
    hs = struct.unpack("<I", d[4:8])[0]
    masters, i = [], 24
    while i + 6 <= 24 + hs:
        s = d[i:i+4]
        n = struct.unpack("<H", d[i+4:i+6])[0]
        i += 6
        if s == b"MAST":
            masters.append(d[i:i+n].split(b"\x00")[0].decode("latin-1"))
        i += n
    return d, hs, masters


def walk_records(d, start, end, out, depth=0):
    off = start
    while off < end:
        t = d[off:off+4]
        n = struct.unpack("<I", d[off+4:off+8])[0]
        if t == b"GRUP":
            out.append(("GRUP", off, n, d[off:off+24]))
            walk_records(d, off + 24, off + n, out, depth + 1)
            off += n
            continue
        out.append(("REC", off, n, d[off:off+24+n]))
        off += 24 + n


def remap_body(sig, body, mapping):
    """Rewrite every FormID field this record type declares. Refuse on anything unknown."""
    if sig not in SCHEMA:
        fail("no schema for record type %s - refusing to guess which of its fields are references"
             % sig)
    fields = SCHEMA[sig]
    out = bytearray()
    for s, data in subrecords(body):
        name = s.decode("latin-1")
        d = bytearray(data)
        if name in SPECIAL:
            kind = SPECIAL[name]
            if kind == "formid+u32" and len(d) >= 4:
                v = struct.unpack_from("<I", d, 0)[0]
                if v in mapping:
                    struct.pack_into("<I", d, 0, mapping[v])
            elif kind == "u32+formid+u32" and len(d) >= 8:
                v = struct.unpack_from("<I", d, 4)[0]
                if v in mapping:
                    struct.pack_into("<I", d, 4, mapping[v])
            elif kind == "formid+formid+f32":
                for off in (0, 4):
                    if len(d) >= off + 4:
                        v = struct.unpack_from("<I", d, off)[0]
                        if v in mapping:
                            struct.pack_into("<I", d, off, mapping[v])
        elif name in fields:
            spec = fields[name]
            if spec == "*":
                for off in range(0, len(d) - 3, 4):
                    v = struct.unpack_from("<I", d, off)[0]
                    if v in mapping:
                        struct.pack_into("<I", d, off, mapping[v])
            elif spec == 1 and len(d) >= 4:
                v = struct.unpack_from("<I", d, 0)[0]
                if v in mapping:
                    struct.pack_into("<I", d, 0, mapping[v])
        out += s + struct.pack("<H", len(d)) + bytes(d)
    return bytes(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plugin")
    ap.add_argument("--out", required=True)
    ap.add_argument("--first", type=lambda s: int(s, 0), default=ESL_FIRST)
    a = ap.parse_args()

    d, hs, masters = load(a.plugin)
    own = len(masters)
    items = []
    walk_records(d, 24 + hs, len(d), items)

    new_ids = [struct.unpack("<I", body[12:16])[0] for kind, off, n, body in items
               if kind == "REC" and (struct.unpack("<I", body[12:16])[0] >> 24) >= own]
    if len(new_ids) > (ESL_LAST - a.first + 1):
        fail("%d new records will not fit between 0x%06X and 0x%06X" % (len(new_ids), a.first, ESL_LAST))

    mapping = {}
    nxt = a.first
    for fid in new_ids:
        mapping[fid] = (own << 24) | nxt
        nxt += 1

    rebuilt = bytearray()
    counts = {}
    for kind, off, n, blob in items:
        if kind == "GRUP":
            continue
        sig = blob[:4].decode("latin-1")
        fid = struct.unpack("<I", blob[12:16])[0]
        flags = struct.unpack("<I", blob[8:12])[0]
        body = blob[24:]
        if flags & 0x00040000:
            fail("record %s %08X is compressed; this script does not handle that yet" % (sig, fid))
        body = remap_body(sig, body, mapping)
        newfid = mapping.get(fid, fid)
        rebuilt += (blob[:4] + struct.pack("<I", len(body)) + blob[8:12]
                    + struct.pack("<I", newfid) + blob[16:24] + body)
        counts[sig] = counts.get(sig, 0) + 1

    # one group per record type, in the order the types first appeared
    groups = bytearray()
    for sig in counts:
        payload = bytearray()
        for kind, off, n, blob in items:
            if kind != "REC" or blob[:4].decode("latin-1") != sig:
                continue
            fid = struct.unpack("<I", blob[12:16])[0]
            flags = struct.unpack("<I", blob[8:12])[0]
            body = remap_body(sig, blob[24:], mapping)
            payload += (blob[:4] + struct.pack("<I", len(body)) + blob[8:12]
                        + struct.pack("<I", mapping.get(fid, fid)) + blob[16:24] + body)
        groups += (b"GRUP" + struct.pack("<I", len(payload) + 24) + sig.encode("latin-1")
                   + struct.pack("<iii", 0, 0, 0) + payload)

    head = bytearray()
    head += b"HEDR" + struct.pack("<H", 12) + struct.pack("<fiI", 1.7, sum(counts.values()), nxt)
    for m in masters:
        head += b"MAST" + struct.pack("<H", len(m) + 1) + m.encode("latin-1") + b"\x00"
        head += b"DATA" + struct.pack("<H", 8) + struct.pack("<Q", 0)
    tes4 = b"TES4" + struct.pack("<IIIIHH", len(head), 0x200, 0, 0, 44, 0) + bytes(head)

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    open(a.out, "wb").write(tes4 + bytes(groups))

    # ---- prove it: nothing may still point at an old number
    v = open(a.out, "rb").read()
    stale = []
    vhs = struct.unpack("<I", v[4:8])[0]
    items2 = []
    walk_records(v, 24 + vhs, len(v), items2)
    for kind, off, n, blob in items2:
        if kind != "REC":
            continue
        for s, data in subrecords(blob[24:]):
            for o in range(0, len(data) - 3, 4):
                if struct.unpack_from("<I", data, o)[0] in mapping:
                    stale.append((blob[:4].decode(), s.decode()))
    if stale:
        fail("%d reference(s) still point at a pre-renumber FormID, e.g. %s %s"
             % (len(stale), stale[0][0], stale[0][1]))

    print("%s  ->  %s" % (os.path.basename(a.plugin), os.path.basename(a.out)))
    print("  masters ............... %s" % ", ".join(masters))
    print("  records ............... %s" % ", ".join("%s %d" % (k, v) for k, v in sorted(counts.items())))
    print("  renumbered ............ %d into 0x%06X-0x%06X" % (len(mapping), a.first, nxt - 1))
    print("  light flag ............ set")
    print("  no stale reference .... checked by re-reading the output")


if __name__ == "__main__":
    main()
