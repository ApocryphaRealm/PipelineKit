r"""esp-form44.py - convert a form-43 (Oldrim-layout) plugin to form version 44, the way a Creation Kit resave does,
for the record layouts that differ between the two - and refuse the ones it does not know how to convert.

The owner, 2026-09-22: "update the plugin for fenrir blades to form 44".

What changes:
  * the TES4 header's form version -> 44 (HEDR must already say 1.7; the script refuses otherwise)
  * every record's form version -> 44
  * WEAP CRDT: the 16-byte form-43 layout (damage u16, pad 2, mult f32, flags u8, pad 3, effect FormID) becomes the
    24-byte form-44 layout (damage u16, pad 2, mult f32, flags u8, pad 7, effect FormID, pad 4). Stamping 44 over a
    16-byte CRDT would make the game read the crit spell from the wrong bytes.
  * record and GRUP sizes are recomputed; compressed records keep their compressed payload (only the header changes)
Refuses: any record carrying BODT (ARMO/ARMA biped data - the form-43 layout is 12 bytes, form 44 uses BOD2; restamping
it shifts every later field, which crashed Nordic Dragonbone 1.0.1), any record below form 40 carrying model hashes (MODT,
MO2T-MO5T, DMDT are flat triples there and start with a header from form 40 on, so a restamp makes the first hash a header
count and the game crashes at load - Campfire Camp Addon, 2026-11-04), and any compressed WEAP (its CRDT would need a
re-compress). The original is never overwritten without a backup beside the output path the caller chose.

    python esp-form44.py <plugin> [--out <path>] [--dry-run]
"""
import os, shutil, struct, sys, time, zlib


def subrecords(d):
    i, out = 0, []
    while i + 6 <= len(d):
        t = d[i:i + 4]; l = struct.unpack("<H", d[i + 4:i + 6])[0]
        out.append((t, d[i + 6:i + 6 + l])); i += 6 + l
    return out


def pack_subs(subs):
    return b"".join(t + struct.pack("<H", len(v)) + v for t, v in subs)


class Refuse(Exception):
    pass


stats = {"records": 0, "crdt": 0}


def convert_record(b, p):
    t = b[p:p + 4]; sz, flags = struct.unpack("<II", b[p + 4:p + 12])
    head = bytearray(b[p:p + 24]); data = b[p + 24:p + 24 + sz]
    compressed = bool(flags & 0x40000)
    plain = zlib.decompress(data[4:]) if compressed else data
    subs = subrecords(plain)
    if any(s == b"BODT" for s, _ in subs):
        raise Refuse("%s record %08X carries BODT - convert it in the Creation Kit" % (t.decode(), struct.unpack("<I", head[12:16])[0]))
    form = struct.unpack("<H", head[20:22])[0]
    flat = [s for s, _ in subs if s in (b"MODT", b"MO2T", b"MO3T", b"MO4T", b"MO5T", b"DMDT")]
    if form < 40 and flat:
        raise Refuse("%s record %08X is form %d and carries %s - flat hashes that form 44 would read as a header; "
                     "convert it in the Creation Kit" % (t.decode(), struct.unpack("<I", head[12:16])[0], form, flat[0].decode()))
    if t == b"WEAP":
        if compressed:
            raise Refuse("compressed WEAP %08X" % struct.unpack("<I", head[12:16])[0])
        new = []
        for s, v in subs:
            if s == b"CRDT" and len(v) == 16:
                v = v[0:8] + v[8:9] + b"\0" * 7 + v[12:16] + b"\0" * 4
                stats["crdt"] += 1
            new.append((s, v))
        data = pack_subs(new)
    struct.pack_into("<H", head, 20, 44)
    struct.pack_into("<I", head, 4, len(data))
    stats["records"] += 1
    return bytes(head) + data, p + 24 + sz


def convert_range(b, s, e):
    out, p = [], s
    while p < e:
        if b[p:p + 4] == b"GRUP":
            gsz = struct.unpack("<I", b[p + 4:p + 8])[0]
            inner = convert_range(b, p + 24, p + gsz)
            head = bytearray(b[p:p + 24]); struct.pack_into("<I", head, 4, 24 + len(inner))
            out.append(bytes(head) + inner); p += gsz
        else:
            rec, p = convert_record(b, p); out.append(rec)
    return b"".join(out)


def main(argv):
    if not argv:
        print(__doc__); return 2
    src = argv[0]
    out = argv[argv.index("--out") + 1] if "--out" in argv else src
    b = open(src, "rb").read()
    if b[:4] != b"TES4":
        print("not a plugin: " + src); return 1
    n = struct.unpack("<I", b[4:8])[0]
    hedr = [v for s, v in subrecords(b[24:24 + n]) if s == b"HEDR"]
    if not hedr or abs(struct.unpack("<f", hedr[0][:4])[0] - 1.7) > 0.01:
        print("HEDR is not 1.7 - this is not an SE plugin yet; convert it in the Creation Kit"); return 1
    try:
        body = convert_range(b, 24 + n, len(b))
    except Refuse as e:
        print("esp-form44  REFUSED  " + str(e)); return 1
    tes4 = bytearray(b[:24 + n]); struct.pack_into("<H", tes4, 20, 44)
    result = bytes(tes4) + body
    print("esp-form44  %s: %d record(s) -> 44, %d CRDT expanded 16->24, %d -> %d bytes"
          % (os.path.basename(src), stats["records"], stats["crdt"], len(b), len(result)))
    if "--dry-run" in argv:
        return 0
    if os.path.abspath(out) == os.path.abspath(src):
        bak = src + ".form43-" + time.strftime("%Y%m%d-%H%M%S") + ".bak"
        shutil.copy2(src, bak); print("esp-form44  original kept at " + bak)
    open(out, "wb").write(result)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
