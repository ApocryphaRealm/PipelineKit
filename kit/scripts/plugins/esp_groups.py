#!/usr/bin/env python3
r"""Write a Skyrim plugin's records into the group tree the engine and Mutagen expect.

WHY
    2026-10-25: a Mutagen patcher could not read "Civil War Guard Armor Replacer.esp". merge-to-espfe.py had walked its
    sources' group trees, kept only the records, and written one flat top-level GRUP per record type - so the plugin
    carried top-level REFR and INFO groups, and its CELL records sat directly in the CELL group with no block,
    sub-block or children groups. A placed reference only belongs to a cell because it sits in that cell's children
    group, and a dialogue response only belongs to a topic because it sits in that topic's children group; written
    flat, the parent is gone. The engine skips what it cannot place, and Mutagen refuses the whole file.

WHAT IT WRITES
    * top-level groups (type 0) in the engine's own order, one per record type;
    * CELL (interior only): block (type 2) and sub-block (type 3) groups by object ID - block = id % 10,
      sub-block = (id // 10) % 10, as the Creation Kit files them - then each CELL followed by its children group
      (type 6) holding a persistent (type 8) and/or temporary (type 9) group of its placed references;
    * DIAL: each topic followed by its topic-children group (type 7) holding its INFO records.
    Children keep the order they were handed in (a source's own order), since INFO order is the response order.

WHAT IT REFUSES
    * a placed reference or INFO whose parent is not given, or whose parent record is not in the set;
    * an exterior cell (it would need its WRLD record and world children, which this module does not write);
    * any child record type it does not know where to put.
    It refuses rather than guesses, because a reference filed under the wrong cell loads into the wrong room.
"""
import struct

# Record types that may only live inside a CELL's children group, and INFO, which lives inside a DIAL's.
PLACED = {"REFR", "ACHR", "PARW", "PBAR", "PBEA", "PCON", "PFLA", "PGRE", "PHZD", "PMIS", "NAVM", "LAND"}
CHILD_TYPES = PLACED | {"INFO"}

PERSISTENT_FLAG = 0x00000400
INTERIOR_FLAG = 0x0001          # CELL DATA bit 0

# The order the Creation Kit (and xEdit, and Mutagen) write Skyrim's top-level groups in.
TOP_ORDER = ("GMST KYWD LCRT AACT TXST GLOB CLAS FACT HDPT HAIR EYES RACE SOUN ASPC MGEF SCPT LTEX ENCH SPEL SCRL "
             "ACTI TACT ARMO BOOK CONT DOOR INGR LIGH MISC APPA STAT SCOL MSTT PWAT GRAS TREE CLDC FLOR FURN WEAP "
             "AMMO NPC_ LVLN KEYM ALCH IDLM COBJ PROJ HAZD SLGM LVLI WTHR CLMT SPGD RFCT REGN NAVI CELL WRLD DIAL "
             "QUST IDLE PACK CSTY LSCR LVSP ANIO WATR EFSH EXPL DEBR IMGS IMAD FLST PERK BPTD ADDN AVIF CAMS CPTH "
             "VTYP MATT IPCT IPDS ARMA ECZN LCTN MESG RGDL DOBJ LGTM MUSC FSTP FSTS SMBN SMQN SMEN DLBR MUST DLVW "
             "WOOP SHOU EQUP RELA SCEN ASTP OTFT ARTO MATO MOVT SNDR DUAL SNCT SOPM COLL CLFM REVB").split()


class GroupError(Exception):
    pass


def _subrecords(body):
    i = 0
    while i + 6 <= len(body):
        sig = body[i:i + 4]
        n = struct.unpack_from("<H", body, i + 4)[0]
        yield sig, body[i + 6:i + 6 + n]
        i += 6 + n


def _record(sig, fid, flags, tail, body):
    return sig.encode("latin-1") + struct.pack("<III", len(body), flags, fid) + tail + body


def _group(label_bytes, gtype, payload):
    return b"GRUP" + struct.pack("<I", len(payload) + 24) + label_bytes + struct.pack("<iii", gtype, 0, 0) + payload


def _fid_label(fid):
    return struct.pack("<I", fid)


def _is_interior(body, flags=0):
    if flags & 0x00040000:          # a compressed record: 4-byte inflated size, then zlib
        import zlib
        body = zlib.decompress(body[4:])
    for sig, data in _subrecords(body):
        if sig == b"DATA" and len(data) >= 1:
            return bool(data[0] & INTERIOR_FLAG)
    return False


def emit(records, parents):
    """records: iterable of (sig, fid, flags, tail8, body); a body is written exactly as given, so a compressed
    record (flag 0x40000, body = inflated size + zlib stream) passes through compressed.
    parents: {child fid: parent fid} for every record whose type is in CHILD_TYPES.
    Returns (group bytes, number of records + groups written) - the second is what HEDR's count holds."""
    by_type = {}
    for r in records:
        by_type.setdefault(r[0], []).append(r)

    cells = {r[1]: r for r in by_type.get("CELL", [])}
    dials = {r[1]: r for r in by_type.get("DIAL", [])}
    cell_kids, dial_kids = {}, {}
    for sig in sorted(t for t in by_type if t in CHILD_TYPES):
        for r in by_type[sig]:
            p = parents.get(r[1])
            if p is None:
                raise GroupError("%s %08X has no parent given - refusing to guess which %s it belongs to"
                                 % (sig, r[1], "topic" if sig == "INFO" else "cell"))
            if sig == "INFO":
                if p not in dials:
                    raise GroupError("INFO %08X belongs to DIAL %08X, which is not in the plugin" % (r[1], p))
                dial_kids.setdefault(p, []).append(r)
            else:
                if p not in cells:
                    raise GroupError("%s %08X belongs to CELL %08X, which is not in the plugin" % (sig, r[1], p))
                if sig in ("NAVM", "LAND"):
                    raise GroupError("%s %08X: navmesh/landscape children are not written by this module" % (sig, r[1]))
                cell_kids.setdefault(p, []).append(r)

    out, count = bytearray(), 0
    known = [t for t in TOP_ORDER if t in by_type and t not in CHILD_TYPES]
    other = sorted(t for t in by_type if t not in TOP_ORDER and t not in CHILD_TYPES)
    for sig in known + other:
        if sig == "CELL":
            blocks = {}
            for fid, r in cells.items():
                if not _is_interior(r[4], r[2]):
                    raise GroupError("CELL %08X is an exterior cell - it needs its WRLD and world children groups, "
                                     "which this module does not write" % fid)
                obj = fid & 0xFFFFFF
                blocks.setdefault(obj % 10, {}).setdefault((obj // 10) % 10, []).append(r)
            payload = bytearray()
            for b in sorted(blocks):
                bpay = bytearray()
                for s in sorted(blocks[b]):
                    spay = bytearray()
                    for r in sorted(blocks[b][s], key=lambda x: x[1]):
                        spay += _record(*r)
                        count += 1
                        kids = cell_kids.get(r[1], [])
                        if kids:
                            cpay = bytearray()
                            for gtype, want in ((8, True), (9, False)):
                                sel = [k for k in kids if bool(k[2] & PERSISTENT_FLAG) == want]
                                if sel:
                                    cpay += _group(_fid_label(r[1]), gtype,
                                                   b"".join(_record(*k) for k in sel))
                                    count += 1 + len(sel)
                            spay += _group(_fid_label(r[1]), 6, bytes(cpay))
                            count += 1
                    bpay += _group(struct.pack("<i", s), 3, bytes(spay))
                    count += 1
                payload += _group(struct.pack("<i", b), 2, bytes(bpay))
                count += 1
        elif sig == "DIAL":
            payload = bytearray()
            for fid in sorted(dials):
                payload += _record(*dials[fid])
                count += 1
                kids = dial_kids.get(fid, [])
                if kids:
                    payload += _group(_fid_label(fid), 7,
                                      b"".join(_record(*k) for k in kids))
                    count += 1 + len(kids)
        else:
            payload = b"".join(_record(*r) for r in sorted(by_type[sig], key=lambda x: x[1]))
            count += len(by_type[sig])
        out += _group(sig.encode("latin-1"), 0, bytes(payload))
        count += 1
    return bytes(out), count
