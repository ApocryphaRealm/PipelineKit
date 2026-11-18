#!/usr/bin/env python3
r"""Put a plugin's misplaced REFR / INFO records back into their CELL / DIAL children groups.

WHY
    2026-10-25: "Civil War Guard Armor Replacer.esp" carried top-level REFR and INFO groups (merge-to-espfe.py
    used to flatten its sources' group trees), so Mutagen - and every Synthesis patcher that reads all groups -
    refused the file, and the engine could not place those records. The plugin had been edited by hand after the
    merge (outfits, shields, Tullius' kit), so re-running the merge would have thrown that work away; this tool
    repairs the file as it stands. Every record other than the moved ones is written back byte for byte.

HOW A PARENT IS FOUND (in this order; a record no rule places is a refusal, never a guess)
    1. --assign FID[-FID]=PARENT   an explicit parent, for records no reference plugin can place.
    2. the record is an OVERRIDE (its FormID belongs to a master): the parent its owner gives it in any
       --parents-from plugin (Skyrim.esm itself, or the source mod that edited it).
    3. the record is NEW: a child record of the same type in a --parents-from plugin with byte-identical DATA
       (a placed reference's position and rotation) - it must match exactly one, or the run refuses.
    All FormIDs are compared as (owning file, object ID), never as raw numbers, because each plugin numbers its
    masters differently.

Usage:  esp-regroup.py <plugin.esp> --out <fixed.esp> --parents-from <plugin> [...] [--assign 0x5000AF3-0x5000AF7=0x5DE24]
"""
import argparse
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import esp_groups  # noqa: E402

COMPRESSED = 0x00040000


def fail(msg):
    raise SystemExit("esp-regroup: " + msg)


class Plugin(object):
    def __init__(self, path, want_children_only=False):
        self.path = path
        self.name = os.path.basename(path)
        d = open(path, "rb").read()
        self.raw = d
        hs = struct.unpack_from("<I", d, 4)[0]
        self.header = d[:24 + hs]
        self.masters = []
        for sig, data in esp_groups._subrecords(d[24:24 + hs]):
            if sig == b"MAST":
                self.masters.append(data.split(b"\x00")[0].decode("latin-1"))
        self.records = []       # (sig, fid, flags, tail, body as stored, whole record bytes as stored)
        self.parent = {}        # child fid -> parent fid (this plugin's numbering)
        self.children = []      # (sig, fid, parent fid, DATA bytes) for every child record found in a children group
        self.misplaced = 0
        self.want_children_only = want_children_only
        self._walk(24 + hs, len(d), None, True)

    def key(self, fid):
        i = fid >> 24
        owner = self.masters[i] if i < len(self.masters) else self.name
        return (owner.lower(), fid & 0xFFFFFF)

    def _walk(self, off, end, parent, top):
        d = self.raw
        while off < end:
            t = d[off:off + 4]
            n = struct.unpack_from("<I", d, off + 4)[0]
            if t == b"GRUP":
                gtype = struct.unpack_from("<i", d, off + 12)[0]
                label = struct.unpack_from("<I", d, off + 8)[0]
                if self.want_children_only and gtype == 0 and d[off + 8:off + 12] not in (b"CELL", b"WRLD", b"DIAL"):
                    off += n
                    continue
                if not self.want_children_only and gtype == 1:
                    fail("%s has a worldspace; this tool regroups interior cells and topics only" % self.name)
                self._walk(off + 24, off + n, label if gtype in (6, 7, 8, 9, 10) else parent, False)
                off += n
                continue
            sig = t.decode("latin-1")
            flags, fid = struct.unpack_from("<II", d, off + 8)
            stored = d[off:off + 24 + n]
            if sig in esp_groups.CHILD_TYPES and parent is not None:
                body = d[off + 24:off + 24 + n]
                if flags & COMPRESSED:
                    body = zlib.decompress(body[4:])
                data = next((x for s, x in esp_groups._subrecords(body) if s == b"DATA"), None)
                self.children.append((sig, fid, parent, data))
                self.parent[fid] = parent
            if not self.want_children_only:
                # the body as STORED (compressed records stay compressed) - the repair moves records, it does
                # not re-encode them, so every record outside the moved ones comes out byte for byte the same
                self.records.append((sig, fid, flags, d[off + 16:off + 24], d[off + 24:off + 24 + n], stored))
            off += 24 + n


def parse_fid(s):
    return int(s, 16) if s.lower().startswith("0x") else int(s, 16)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plugin")
    ap.add_argument("--out", required=True)
    ap.add_argument("--parents-from", action="append", default=[])
    ap.add_argument("--assign", action="append", default=[])
    a = ap.parse_args()

    tgt = Plugin(a.plugin)
    refs = [Plugin(p, want_children_only=True) for p in a.parents_from]

    by_key, by_data = {}, {}
    for r in refs:
        for sig, fid, parent, data in r.children:
            by_key.setdefault((sig,) + r.key(fid), set()).add(r.key(parent))
            if data is not None:
                by_data.setdefault((sig, data), []).append(r.key(parent))

    assigned = {}
    for spec in a.assign:
        lhs, rhs = spec.split("=")
        lo, _, hi = lhs.partition("-")
        lo, hi = parse_fid(lo), parse_fid(hi or lo)
        for f in range(lo, hi + 1):
            assigned[f] = parse_fid(rhs)

    own_index = len(tgt.masters)
    index = {m.lower(): i for i, m in enumerate(tgt.masters)}

    def from_key(k):
        owner, obj = k
        if owner == tgt.name.lower():
            return (own_index << 24) | obj
        if owner not in index:
            fail("parent %s:%06X belongs to a file %s does not master" % (owner, obj, tgt.name))
        return (index[owner] << 24) | obj

    parents, how = {}, {"assign": 0, "override": 0, "position": 0, "kept": 0}
    for sig, fid, flags, tail, body, stored in tgt.records:
        if sig not in esp_groups.CHILD_TYPES:
            continue
        if fid in tgt.parent:
            parents[fid] = tgt.parent[fid]
            how["kept"] += 1
            continue
        if fid in assigned:
            parents[fid] = assigned[fid]
            how["assign"] += 1
            continue
        k = tgt.key(fid)
        if k[0] != tgt.name.lower():
            hits = by_key.get((sig,) + k)
            if not hits or len(hits) > 1:
                fail("%s %08X (override of %s:%06X): %s" % (sig, fid, k[0], k[1],
                     "no --parents-from plugin places it" if not hits else "placed in more than one parent"))
            parents[fid] = from_key(next(iter(hits)))
            how["override"] += 1
            continue
        plain = zlib.decompress(body[4:]) if flags & COMPRESSED else body
        data = next((x for s, x in esp_groups._subrecords(plain) if s == b"DATA"), None)
        hits = by_data.get((sig, data)) if data is not None else None
        if not hits or len(set(hits)) != 1 or len(hits) != 1:
            fail("%s %08X (new record): %s - pass --assign for it" % (sig, fid,
                 "no child with the same DATA in any --parents-from plugin" if not hits else
                 "its DATA matches %d children" % len(hits)))
        parents[fid] = from_key(hits[0])
        how["position"] += 1

    records = [(sig, fid, flags, tail, body) for sig, fid, flags, tail, body, stored in tgt.records]
    try:
        groups, written = esp_groups.emit(records, parents)
    except esp_groups.GroupError as e:
        fail(str(e))

    # The HEDR record count becomes records + groups; nothing else in the header changes.
    head = bytearray(tgt.header)
    hs = struct.unpack_from("<I", head, 4)[0]
    i = 24
    while i < 24 + hs:
        s = bytes(head[i:i + 4])
        n = struct.unpack_from("<H", head, i + 4)[0]
        if s == b"HEDR":
            struct.pack_into("<i", head, i + 6 + 4, written)
        i += 6 + n
    out = bytes(head) + groups

    # Proof: every record of the input is in the output, byte for byte, and each child sits under its parent.
    check = Plugin.__new__(Plugin)
    open_tmp = out
    check.raw, check.name, check.masters = open_tmp, tgt.name, tgt.masters
    check.records, check.parent, check.children, check.want_children_only = [], {}, [], False
    check._walk(24 + hs, len(open_tmp), None, True)
    before = {(r[0], r[1]): r[5] for r in tgt.records}
    after = {(r[0], r[1]): r[5] for r in check.records}
    if before != after:
        diff = sorted(set(before) ^ set(after))[:5] or [k for k in before if before[k] != after.get(k)][:5]
        fail("the rewritten file does not carry the same records - refusing to write (%s)" % diff)
    for fid, p in parents.items():
        if check.parent.get(fid) != p:
            fail("%08X did not land under %08X in the rewritten file" % (fid, p))

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    open(a.out, "wb").write(out)
    print("esp-regroup  %s -> %s" % (tgt.name, a.out))
    print("  records ............... %d (unchanged), groups+records in HEDR %d" % (len(records), written))
    print("  children placed ....... %d by override, %d by position, %d assigned, %d already in place"
          % (how["override"], how["position"], how["assign"], how["kept"]))


if __name__ == "__main__":
    main()
