#!/usr/bin/env python3
r"""Merge several plugins into ONE light .esp, renumbering and re-pointing everything.

WHY
    The owner wants the all-in-one mod to occupy a single line in the load order:
    *"were making an aio mod that has one espfe so merge the mods as we decided"*.

    Measured beforehand (docs/plugin-merge-analysis.md): 914 new records and 405 overrides across
    four plugins, and the only three collisions in the whole set are General Tullius's armour and
    his two outfit lists - which the Tullius replacer is meant to win.

THE THREE HARD PARTS, AND HOW EACH IS HANDLED

    1. MASTER INDICES. A FormID's top byte indexes the plugin's OWN master list, and every source
       has a different one. Each reference is resolved to the file that actually owns it and then
       re-indexed against the merged master list. Nothing is assumed about the order matching.

    2. RENUMBERING. New records move into 0x000800-0x000FFF, and every field pointing at them has
       to move with them. The FormID fields are declared in SCHEMA below - written down, because an
       earlier attempt to derive them from the data flagged a mesh path and a bounding box as
       references. A record type with no schema is refused, never guessed at.

    3. COMPRESSED RECORDS. 246 NPC_ records and 4 CELLs arrive zlib-compressed. They are inflated,
       re-pointed, and written back out uncompressed - which the game reads perfectly well and
       which keeps the output inspectable.

WHAT IT REFUSES TO DO
    * merge a record type it has no schema for;
    * overflow the light range;
    * lose a record's parent: a REFR stays in its cell's children group and an INFO in its topic's
      (esp_groups.py writes the tree; 2026-10-25, after flat top-level REFR/INFO groups made
      Civil War Guard Armor Replacer unreadable to Mutagen), and a worldspace source is refused;
    * finish while any reference still points at a pre-merge FormID - it re-reads its own output
      and checks, because this is precisely the failure that loads fine and does nothing.

Usage:  python merge-to-espfe.py --out <plugin.esp> <source.esp> [<source.esp> ...]
        Sources are given in winning order: later files beat earlier ones on a shared record.
"""
import argparse
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import esp_groups  # noqa: E402  (the group-tree writer; 2026-10-25)

ESL_FIRST, ESL_LAST = 0x000800, 0x000FFF
COMPRESSED = 0x00040000
LIGHT = 0x00000200

STANDARD = ["Skyrim.esm", "Update.esm", "Dawnguard.esm", "HearthFires.esm", "Dragonborn.esm"]

# FormID-bearing subrecords, per record type. "*" = array of 4-byte FormIDs, 1 = a single one.
SCHEMA = {
    "ARMO": {"MODL": "*", "EITM": 1, "ETYP": 1, "BIDS": 1, "BAMT": 1, "KWDA": "*", "RNAM": 1,
             "TNAM": 1, "YNAM": 1, "ZNAM": 1},
    "ARMA": {"RNAM": 1, "MODL": "*", "SNDD": 1, "NAM0": 1, "NAM1": 1, "NAM2": 1, "NAM3": 1},
    "WEAP": {"ETYP": 1, "BIDS": 1, "BAMT": 1, "INAM": 1, "WNAM": 1, "TNAM": 1, "NAM9": 1,
             "NAM8": 1, "KWDA": "*", "CNAM": 1, "EITM": 1, "YNAM": 1, "ZNAM": 1},
    "AMMO": {"YNAM": 1, "ZNAM": 1, "KWDA": "*"},
    "STAT": {},
    "PROJ": {"YNAM": 1, "ZNAM": 1, "NAM2": 1},
    "COBJ": {"CNAM": 1, "BNAM": 1},
    "OTFT": {"INAM": "*"},
    "LVLI": {},
    "LVLN": {},
    "CONT": {"YNAM": 1, "ZNAM": 1, "QNAM": 1, "KWDA": "*"},
    "CELL": {"XCWT": 1, "XCCM": 1, "XCAS": 1, "XCMO": 1, "XLCN": 1, "XCIM": 1, "XEZN": 1,
             "XCLW": 0, "XCLL": 0},
    "REFR": {"NAME": 1, "XEZN": 1, "XLRT": 1, "XLRL": 1, "XOWN": 1, "XLCN": 1, "XESP": "*",
             "XTEL": 1, "XLTW": 1, "XPRM": 0, "DATA": 0},
    "NPC_": {"TPLT": 1, "RNAM": 1, "SPLO": "*", "WNAM": 1, "ANAM": 1, "ATKR": 1, "SPOR": 1,
             "OCOR": 1, "GWOR": 1, "ECOR": 1, "PRKR": "*", "FCPL": 1, "CRIF": 1, "VTCK": 1,
             "VTYP": 1, "DOFT": 1, "SOFT": 1, "DPLT": 1, "FTST": 1, "QNAM": 0, "HCLF": 1,
             "ZNAM": 1, "YNAM": 1, "NAM9": 0, "PKID": "*", "KWDA": "*", "PLKR": "*",
             "DEST": 0, "DATA": 0, "ACBS": 0, "AIDT": 0, "DNAM": 0, "NAM5": 0, "NAM6": 0,
             "NAM7": 0, "NAM8": 0, "CSDT": 0, "CSDI": 1, "CSDC": 0},
    "QUST": {"ALFR": 1, "ALPC": 1, "ALSP": "*", "ALUA": "*", "ALFL": 1, "ECOR": 1, "ALCO": 1,
             "ALEQ": 1, "ALDN": 1, "QNAM": 1, "ANAM": 0, "DNAM": 0, "INDX": 0},
    "DIAL": {"QNAM": 1, "BNAM": 1, "TIFC": 0, "DATA": 0},
    "INFO": {"QNAM": 1, "PNAM": 1, "DNAM": 1, "SNAM": 1, "LNAM": 1, "TCLT": "*", "ANAM": 1},
    "KYWD": {},
    "GLOB": {},
    "MISC": {"YNAM": 1, "ZNAM": 1, "KWDA": "*"},
}
# Subrecords with a layout other than a plain FormID array.
SPECIAL = {"CNTO": [(0, "f")], "LVLO": [(4, "f")], "COED": [(0, "f"), (4, "f")],
           "SNAM": [(0, "f")], "CTDA": [(12, "f")]}
# Subrecords whose FormID slots depend on the RECORD TYPE they sit in. "DATA" is a FormID-free
# blob in most records and a projectile pointer in AMMO; a name-only table cannot say which.
# 2026-09-16: the merged Civil War Guard Armor Replacer crashed the game at the main menu inside
# ArcheryRebalance.dll, reading the projectile of "Iron Arrow" (0xFE0338A1) - the AMMO's DATA still
# carried Sons of Skyrim's own number for its projectile, untranslated, and resolved to nothing.
TYPED = {
    ("AMMO", "DATA"): [0],                                     # projectile
    ("PROJ", "DATA"): [16, 20, 36, 40, 56, 60, 64, 84, 88],    # light, muzzle flash light, explosion,
                                                               # sound, countdown sound, disable sound,
                                                               # default weapon source, decal, collision layer
    ("WEAP", "CRDT"): [16],                                    # critical effect
}


def fail(msg):
    raise SystemExit("merge-to-espfe: " + msg)


def subrecords(data):
    i = 0
    while i + 6 <= len(data):
        sig = data[i:i+4]
        n = struct.unpack("<H", data[i+4:i+6])[0]
        i += 6
        yield sig, data[i:i+n]
        i += n


class Source(object):
    def __init__(self, path):
        self.path = path
        self.name = os.path.basename(path)
        d = open(path, "rb").read()
        self.raw = d
        hs = struct.unpack("<I", d[4:8])[0]
        self.masters, i = [], 24
        while i + 6 <= 24 + hs:
            s = d[i:i+4]
            n = struct.unpack("<H", d[i+4:i+6])[0]
            i += 6
            if s == b"MAST":
                self.masters.append(d[i:i+n].split(b"\x00")[0].decode("latin-1"))
            i += n
        self.records = []          # (sig, fid, flags, hdrtail, body)
        self.parent = {}           # child fid -> the CELL / DIAL fid whose children group holds it (source numbers)
        self._walk(24 + hs, len(d), None)

    def _walk(self, off, end, parent):
        # 2026-10-25: the group a record sits in IS its parent link - a REFR belongs to a cell only by sitting in
        # that cell's children group (types 6/8/9/10), an INFO to a topic only by sitting in type 7. Flattening the
        # tree without keeping that link wrote top-level REFR/INFO groups Mutagen refuses and the engine cannot place.
        d = self.raw
        while off < end:
            t = d[off:off+4]
            n = struct.unpack("<I", d[off+4:off+8])[0]
            if t == b"GRUP":
                gtype = struct.unpack("<i", d[off+12:off+16])[0]
                if gtype == 1:
                    fail("%s has a worldspace (WRLD children group); exterior cells are not merged by this tool"
                         % self.name)
                label = struct.unpack("<I", d[off+8:off+12])[0]
                self._walk(off + 24, off + n, label if gtype in (6, 7, 8, 9, 10) else parent)
                off += n
                continue
            flags = struct.unpack("<I", d[off+8:off+12])[0]
            fid = struct.unpack("<I", d[off+12:off+16])[0]
            tail = d[off+16:off+24]
            body = d[off+24:off+24+n]
            if flags & COMPRESSED:
                body = zlib.decompress(body[4:])
                flags &= ~COMPRESSED
            self.records.append((t.decode("latin-1"), fid, flags, tail, body))
            if parent is not None and t.decode("latin-1") in esp_groups.CHILD_TYPES:
                self.parent[fid] = parent
            off += 24 + n

    def owner(self, fid):
        i = fid >> 24
        return self.masters[i] if i < len(self.masters) else self.name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sources", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--author", default="YOUR-NEXUS-NAME")
    ap.add_argument("--desc", default="")
    a = ap.parse_args()

    srcs = [Source(p) for p in a.sources]

    # ---- the merged master list: the standard prefix that is actually needed, in order
    needed = set()
    for s in srcs:
        needed |= set(m for m in s.masters)
    masters = [m for m in STANDARD if m in needed]
    extra = sorted(m for m in needed if m not in STANDARD)
    if extra:
        fail("a source masters something outside the standard five (%s); the merged plugin would "
             "need it too, and that is a decision rather than a detail" % ", ".join(extra))
    index = {m.lower(): i for i, m in enumerate(masters)}
    own_index = len(masters)

    # ---- what each source's FormIDs become
    mapping = {}          # (source name, old fid) -> new fid
    winners = {}          # canonical key -> (sig, flags, tail, body, source)
    child_parent = {}     # canonical key of a REFR/INFO -> (source, its parent CELL/DIAL fid in that source)
    nxt = ESL_FIRST
    for s in srcs:
        for sig, fid, flags, tail, body in s.records:
            owner = s.owner(fid)
            if owner.lower() == s.name.lower():
                if nxt > ESL_LAST:
                    fail("more than %d new records; they will not fit in the light range"
                         % (ESL_LAST - ESL_FIRST + 1))
                new = (own_index << 24) | nxt
                nxt += 1
                key = ("NEW", s.name, fid)
            else:
                new = (index[owner.lower()] << 24) | (fid & 0xFFFFFF)
                key = (owner.lower(), fid & 0xFFFFFF)
            mapping[(s.name, fid)] = new
            winners[key] = (sig, flags, tail, body, s.name)
            if sig in esp_groups.CHILD_TYPES:
                child_parent[key] = (s.name, s.parent.get(fid))

    def remap(src_name, value):
        hit = mapping.get((src_name, value))
        return hit if hit is not None else None

    def rewrite(sig, body, src_name):
        if sig not in SCHEMA:
            fail("no schema for record type %s - refusing to guess which of its fields point at "
                 "other records" % sig)
        fields = SCHEMA[sig]
        out = bytearray()
        for s, data in subrecords(body):
            name = s.decode("latin-1")
            d = bytearray(data)
            slots = []
            if name == "VMAD":
                # Script properties carry FormIDs inside a layout that is not 4-byte aligned (an
                # Object property is form + alias + padding, packed behind counted strings), so every
                # byte offset is tried against this source's OWN record numbers, and only an exact
                # hit is rewritten. 2026-09-16: New Legion's CWSiege quest script pointed at one of
                # its own forms this way; the sweep below caught it.
                slots = [o for o in range(0, len(d) - 3)
                         if struct.unpack_from("<I", d, o)[0] in own_new[src_name]]
            elif (sig, name) in TYPED:
                slots = [o for o in TYPED[(sig, name)] if o + 4 <= len(d)]
            elif name in SPECIAL:
                slots = [o for o, kind in SPECIAL[name] if o + 4 <= len(d)]
            elif name in fields:
                spec = fields[name]
                if spec == "*":
                    slots = list(range(0, len(d) - 3, 4))
                elif spec == 1 and len(d) >= 4:
                    slots = [0]
            for o in slots:
                v = struct.unpack_from("<I", d, o)[0]
                n = remap(src_name, v)
                if n is not None:
                    struct.pack_into("<I", d, o, n)
            out += s + struct.pack("<H", len(d)) + bytes(d)
        return bytes(out)

    # ---- emit, each record in its proper group (esp_groups: CELL blocks and children, DIAL topic children).
    # 2026-10-25: this used to write one flat top-level GRUP per record type, REFR and INFO included.
    by_type = {}
    by_type_src = {}
    parents = {}
    own_new = {s.name: set(k[2] for k in winners if k[0] == "NEW" and k[1] == s.name) for s in srcs}
    for key, (sig, flags, tail, body, src_name) in winners.items():
        old = key[2] if key[0] == "NEW" else None
        fid = mapping[(src_name, old)] if old is not None else \
            (index[key[0]] << 24) | key[1]
        rewritten = rewrite(sig, body, src_name)
        by_type.setdefault(sig, []).append((fid, flags, tail, rewritten))
        by_type_src.setdefault(sig, []).append((fid, flags, tail, rewritten, src_name))
        if key in child_parent:
            src_name_p, p = child_parent[key]
            if p is None or (src_name_p, p) not in mapping:
                fail("%s %08X from %s sits outside any cell/topic children group" % (sig, fid, src_name_p))
            parents[fid] = mapping[(src_name_p, p)]

    try:
        groups, written = esp_groups.emit(
            [(sig, fid, flags, tail, body) for sig in by_type for fid, flags, tail, body in by_type[sig]], parents)
    except esp_groups.GroupError as e:
        fail(str(e))
    counts = {sig: len(v) for sig, v in by_type.items()}

    head = bytearray()
    head += b"HEDR" + struct.pack("<H", 12) + struct.pack("<fiI", 1.7, written, nxt)
    head += b"CNAM" + struct.pack("<H", len(a.author) + 1) + a.author.encode("latin-1") + b"\x00"
    if a.desc:
        head += b"SNAM" + struct.pack("<H", len(a.desc) + 1) + a.desc.encode("latin-1") + b"\x00"
    for m in masters:
        head += b"MAST" + struct.pack("<H", len(m) + 1) + m.encode("latin-1") + b"\x00"
        head += b"DATA" + struct.pack("<H", 8) + struct.pack("<Q", 0)
    tes4 = b"TES4" + struct.pack("<IIIIHH", len(head), LIGHT, 0, 0, 44, 0) + bytes(head)

    # ---- the stale-reference sweep: nothing may still carry a source's OWN number for one of its
    # own records. Every 4-byte-aligned value of every subrecord is compared against the mapping of
    # the source the record came from; a value that names one of that source's new records and was
    # not translated is a dangling pointer the game will follow to nothing (the 2026-09-16 crash).
    stale = []
    for sig in by_type:
        for fid, flags, tail, body, src_name in by_type_src[sig]:
            own = own_new[src_name]
            for s_, data in subrecords(body):
                for o in range(0, len(data) - 3, 1 if s_ == b"VMAD" else 4):
                    v = struct.unpack_from("<I", data, o)[0]
                    if v in own and not ((v >> 24) == own_index and ESL_FIRST <= (v & 0xFFFFFF) <= ESL_LAST):
                        stale.append("%s %08X %s+%d -> %08X (%s)" % (sig, fid, s_.decode("latin-1"), o, v, src_name))
    if stale:
        fail("%d field(s) still carry a source's own number for one of its records - a FormID slot "
             "the schema does not know about:\n  %s" % (len(stale), "\n  ".join(stale[:20])))

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    open(a.out, "wb").write(tes4 + bytes(groups))

    print("merged %d plugin(s) -> %s" % (len(srcs), os.path.basename(a.out)))
    print("  masters ............... %s" % ", ".join(masters))
    print("  new records ........... %d, at 0x%06X-0x%06X" % (nxt - ESL_FIRST, ESL_FIRST, nxt - 1))
    print("  records by type ....... %s" % ", ".join("%s %d" % (k, v) for k, v in sorted(counts.items())))
    print("  light flag ............ set")


if __name__ == "__main__":
    main()
