r"""esp-drop-cells.py - remove whole CELL records (and every record in their child groups) from a plugin, keeping its
file name, header and every other record, so patches that name the plugin as a master still load.

The owner, 2026-09-22, on Skyrim Project Optimization: "if possible i dont want spo to affct player homes so either
convert the no homes version the the required esl or alter the required esl version to exclude player homes". The
Snazzy Interiors patches name "Skyrim Project Optimization - Full ESL Version.esm" as their master, and SPO's own No
Homes file differs from the Full one by exactly five cells (Breezehome, Hjerim, Proudspire Manor, Honeyside, Vlindrel
Hall - measured by comparing SPO 1.4 Full ESL and No Homes ESL). This drops those cells from the Full file.

What it does:
  * removes each named CELL record and the GRUP that follows it holding its children (types 6/8/9, labelled with the
    cell's FormID), and any group left empty by that;
  * recomputes every GRUP size, the TES4 HEDR record count, and drops the removed FormIDs from the TES4 ONAM list;
  * fails if any remaining record in the file still points at a removed FormID (a FormID-shaped scan of the plain
    data, the same approach esp-audit.py uses for references).

    python esp-drop-cells.py <in.esm> <out.esm> --cells 000165A8,00016778,...
"""
import struct, sys, zlib


def main(argv):
    src, dst = argv[0], argv[1]
    drop_cells = {int(x, 16) for x in argv[argv.index("--cells") + 1].split(",")}
    b = open(src, "rb").read()
    hsz = struct.unpack("<I", b[4:8])[0]
    removed = set()

    def children_of(p, e):
        """Records and groups inside [p, e) as (start, end, kind, formid/label, gtype)."""
        out = []
        while p < e:
            if b[p:p + 4] == b"GRUP":
                sz = struct.unpack("<I", b[p + 4:p + 8])[0]
                out.append((p, p + sz, "GRUP", struct.unpack("<I", b[p + 8:p + 12])[0], struct.unpack("<i", b[p + 12:p + 16])[0]))
                p += sz
            else:
                sz = struct.unpack("<I", b[p + 4:p + 8])[0]
                out.append((p, p + 24 + sz, b[p:p + 4].decode(), struct.unpack("<I", b[p + 12:p + 16])[0], None))
                p += 24 + sz
        return out

    def collect(p, e):
        for s, t, kind, fid, _ in children_of(p, e):
            if kind == "GRUP":
                collect(s + 24, t)
            else:
                removed.add(fid)

    def rebuild(p, e):
        """Rebuilt bytes of [p, e) with the dropped cells removed."""
        out = []
        items = children_of(p, e)
        skip_group_for = None
        for s, t, kind, fid, gtype in items:
            if kind == "CELL" and fid in drop_cells:
                removed.add(fid)
                skip_group_for = fid
                continue
            if kind == "GRUP" and gtype in (6, 8, 9) and fid in drop_cells:
                collect(s + 24, t)
                continue
            if kind == "GRUP":
                inner = rebuild(s + 24, t)
                if not inner and gtype != 0:
                    continue   # a block/sub-block left empty
                head = bytearray(b[s:s + 24]); struct.pack_into("<I", head, 4, 24 + len(inner))
                out.append(bytes(head) + inner)
            else:
                out.append(b[s:t])
        return b"".join(out)

    body = rebuild(24 + hsz, len(b))
    missing = drop_cells - removed
    if missing:
        raise SystemExit("esp-drop-cells: FAIL  cell(s) not found: " + ", ".join(f"{c:08X}" for c in sorted(missing)))

    # TES4: record count and ONAM
    hdr = b[24:24 + hsz]; out_sub = []; i = 0
    while i < len(hdr):
        t = hdr[i:i + 4]; l = struct.unpack("<H", hdr[i + 4:i + 6])[0]; v = hdr[i + 6:i + 6 + l]
        if t == b"ONAM":
            ids = [struct.unpack("<I", v[k:k + 4])[0] for k in range(0, len(v), 4)]
            kept = [x for x in ids if x not in removed]
            print(f"esp-drop-cells: ONAM {len(ids)} -> {len(kept)}")
            v = b"".join(struct.pack("<I", x) for x in kept)
        out_sub.append((t, v)); i += 6 + l
    count = 0
    def count_records(p, e):
        nonlocal count
        for s, t, kind, fid, _ in children_of_bytes(body, p, e):
            if kind == "GRUP":
                count += 1; count_records(s + 24, t)
            else:
                count += 1
    def children_of_bytes(buf, p, e):
        out = []
        while p < e:
            sz = struct.unpack("<I", buf[p + 4:p + 8])[0]
            if buf[p:p + 4] == b"GRUP":
                out.append((p, p + sz, "GRUP", 0, 0)); p += sz
            else:
                out.append((p, p + 24 + sz, "REC", 0, 0)); p += 24 + sz
        return out
    count_records(0, len(body))
    new_hdr = b""
    for t, v in out_sub:
        if t == b"HEDR":
            v = v[:4] + struct.pack("<I", count) + v[8:]
        new_hdr += t + struct.pack("<H", len(v)) + v
    tes4 = bytearray(b[:24]); struct.pack_into("<I", tes4, 4, len(new_hdr))
    result = bytes(tes4) + new_hdr + body

    # nothing left may point at a removed FormID
    dangling = []
    for s, t, kind, fid, _ in children_of_bytes(result, 24 + len(new_hdr), len(result)):
        pass
    def scan(buf, p, e):
        while p < e:
            sz = struct.unpack("<I", buf[p + 4:p + 8])[0]
            if buf[p:p + 4] == b"GRUP":
                scan(buf, p + 24, p + sz); p += sz; continue
            fl = struct.unpack("<I", buf[p + 8:p + 12])[0]; own = struct.unpack("<I", buf[p + 12:p + 16])[0]
            data = buf[p + 24:p + 24 + sz]
            if fl & 0x40000:
                data = zlib.decompress(data[4:])
            for k in range(0, len(data) - 3):
                v = struct.unpack("<I", data[k:k + 4])[0]
                if v in removed and v != own:
                    dangling.append((buf[p:p + 4].decode(), own, v)); break
            p += 24 + sz
    scan(result, 24 + len(new_hdr), len(result))
    if dangling:
        raise SystemExit("esp-drop-cells: FAIL  remaining records still point at removed forms: " +
                         ", ".join(f"{t} {o:08X}->{v:08X}" for t, o, v in dangling[:8]))
    open(dst, "wb").write(result)
    print(f"esp-drop-cells: removed {len(drop_cells)} cell(s) and {len(removed) - len(drop_cells)} child record(s); "
          f"{len(b)} -> {len(result)} bytes; HEDR count {count}; written {dst}")


if __name__ == "__main__":
    main(sys.argv[1:])
