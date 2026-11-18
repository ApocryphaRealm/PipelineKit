"""esp-audit.py - the integrity gate for a Skyrim plugin we have edited.

Why this exists (2026-09-19): editing Tullius' inventory in Civil War Guard Armor Replacer removed two CNTO
entries and left COCT saying there were still five. The engine trusts the COUNT, not the entries, so it read two
items past the end of the list and the game crashed at data load inside SPID with a null form. Nothing in the
pipeline would have caught it: the plugin parsed, loaded in xEdit and looked right.

A count subrecord is a promise about how many of something follows, and every promise in a plugin we wrote is
checked here. Run it on any .esp/.esl before it is deployed or packaged; it EXITS NON-ZERO when a check fails.

    python esp-audit.py [--runtime 1.6.1170] <plugin> [<plugin> ...]

Checks:
  COCT == number of CNTO      container / inventory entry count (the crash above)
  LLCT == number of LVLO      levelled list entry count (same failure mode, same day, other record type)
  KSIZ == KWDA / 4            keyword count
  ARMO: one MODL per addon    a packed MODL keeps none of them and the piece is invisible (library, 2026-09-17)
  no dangling own-range ref   a FormID in this file's own index that no record in it defines - the engine
                              follows it and crashes (library entry 5534)
  ESPFE local id range        a light plugin's own records live in 0x800-0xFFF; outside it they are unreachable
                              (0x001-0xFFF for a 1.71-header plugin when --runtime is 1.6.1130 or later)
  form-44 WEAP CRDT is 24     a weapon stamped form 44 with the 16-byte form-43 CRDT has its crit spell read from
                              the wrong bytes (2026-09-22, Fenrir Blades: a bare restamp would have done exactly
                              this; esp-form44.py expands it)
  CELL DATA                   every CELL carries DATA (no DATA reads as exterior; a patcher built on it crashes the game)
  group tree                  every record sits in the group the engine and Mutagen read it from: no top-level
                              REFR/ACHR/INFO/NAVM... group, CELL records inside block/sub-block groups with their
                              children groups, INFO inside its DIAL's topic-children group (2026-10-25, Civil War
                              Guard Armor Replacer: Mutagen refused the file; see group_tree_fails)
  model hashes fit the form   a record of form version 40 or later holds MODT/MO2T-MO5T/DMDT as a header, not as the
                              flat triples of form 39 and below (2026-11-04, Campfire Camp Addon crashed at load;
                              see model_hash_fail)
"""
import os, struct, sys, zlib

COMPRESSED = 0x00040000
RUNTIME = None          # --runtime X.Y.Z: the game version the plugin is about to load into (plugin-gate passes it)
EXTENDED_ESL = False    # the runtime reads the extended light range of a 1.71 header (1.6.1130 and later)
FORMVER = {}   # formid -> record form version, filled by records()

FORMID_SLOTS = {
    b"CNTO": (8, 0), b"LVLO": (12, 4),
    b"DOFT": (4, 0), b"SOFT": (4, 0), b"INAM": (4, 0), b"CNAM": (4, 0),
    b"BNAM": (4, 0), b"SNAM": (4, 0), b"WNAM": (4, 0), b"ANAM": (4, 0),
    b"TNAM": (4, 0), b"NAM0": (4, 0), b"RNAM": (4, 0), b"ZNAM": (4, 0),
    b"YNAM": (4, 0), b"QNAM": (4, 0), b"ENAM": (4, 0), b"MODL": (4, 0),
}

# Subrecords that share a reference slot's signature but hold no FormID in that record type. QUST ANAM is the quest's
# next alias ID, a counter (DBReV.esp 1.5.2, 2026-10-03: ANAM 1 in a 0-master quest failed the gate as a dangling ref).
# ACTI RNAM is the activation prompt text (OarsAndSails.esl, 2026-11-08: "Row" read as FormID 00776F52).
NOT_REFS = {(b"QUST", b"ANAM"), (b"ACTI", b"RNAM")}

# The model texture-hash subrecords. Read from Skyrim.esm 2026-11-04: all 11526 below form 40 are flat triples and all 13620
# at 40 or later have the header, across every record type and every one of these signatures.
MODEL_HASHES = {b"MODT", b"MO2T", b"MO3T", b"MO4T", b"MO5T", b"DMDT"}
MODEL_HASH_HEADER_FORM = 40


def model_hash_fail(form, ssig, value):
    """What is wrong with one model-hash subrecord of a record of this form version, or None.
    Form 40 and later: u32 H, then H header words - the texture count, then (H >= 2) the addon count - then 12 bytes per
    texture and 4 per addon. So size == 4 + 4*H + 12*textures + 4*addons. H is 2 in every vanilla record; DynDOLOD writes
    H = 1 (no addon word) on its STAT and TREE records, and the list loads those, so H = 1 is not failed. Skyrim 1.5.97's parser (ID 14623,
    called by the STAT loader, ID 17615) finds the data at base + (H+1)*4 and trusts the counts.
    Below form 40 the parser reads flat 12-byte triples with no header, so copying one across that line makes the first
    hash the header count, and the game reads a wild address while loading the plugin (Campfire Camp Addon, 2026-11-04: a
    form-39 Skyrim.esm STAT's MODT in a form-44 record; the plugin parsed and passed every other check here).
    Below form 40 nothing is failed: a flat reader has no count to trust."""
    if form < MODEL_HASH_HEADER_FORM:
        return None
    name, size = ssig.decode("ascii", "replace"), len(value)
    if size < 8:
        return "%s is %d bytes - form %d needs at least a header count and a texture count" % (name, size, form)
    header, textures = struct.unpack_from("<II", value)
    addons = struct.unpack_from("<I", value, 8)[0] if header >= 2 and size >= 12 else 0
    if header < 1 or 4 + 4 * header + 12 * textures + 4 * addons != size:
        return ("%s is %d bytes but its header says %d header words, %d textures, %d addons - form %d has a header; "
                "these look like the flat hashes of form 39 and below, copied across" % (name, size, header, textures, addons, form))
    return None


def subrecords(body):
    """(offset, signature, length) for every subrecord, honouring an XXXX length override."""
    i, override = 0, None
    while i + 6 <= len(body):
        sig = body[i:i + 4]
        ln = struct.unpack_from("<H", body, i + 4)[0]
        if sig == b"XXXX":
            override = struct.unpack_from("<I", body, i + 6)[0]
            i += 6 + ln
            continue
        if override is not None:
            ln, override = override, None
        yield i, sig, ln
        i += 6 + ln


def records(data):
    """Every record in the file: (signature, formid, flags, body) with compressed bodies expanded."""
    stack = [(0, len(data))]
    while stack:
        pos, end = stack.pop()
        while pos + 24 <= end:
            tag = data[pos:pos + 4]
            size = struct.unpack_from("<I", data, pos + 4)[0]
            if tag == b"GRUP":
                if size < 24:
                    break
                stack.append((pos + 24, pos + size))
                pos += size
                continue
            flags = struct.unpack_from("<I", data, pos + 8)[0]
            formid = struct.unpack_from("<I", data, pos + 12)[0]
            body = data[pos + 24:pos + 24 + size]
            if flags & COMPRESSED and len(body) > 4:
                try:
                    body = zlib.decompress(body[4:])
                except zlib.error:
                    pass
            FORMVER[formid] = struct.unpack_from("<H", data, pos + 20)[0]
            yield tag, formid, flags, body
            pos += 24 + size


# Record types that only live inside a CELL's children group (types 8/9/10), and INFO, which only lives inside a DIAL's
# topic-children group (type 7).
PLACED = {b"REFR", b"ACHR", b"PARW", b"PBAR", b"PBEA", b"PCON", b"PFLA", b"PGRE", b"PHZD", b"PMIS", b"NAVM", b"LAND"}
NESTED = PLACED | {b"INFO"}


def group_tree_fails(data, limit=12):
    """Where each record sits. 2026-09-21: Civil War Guard Armor Replacer carried top-level REFR and INFO groups
    (xEdit: "top level group without known sort order"). 2026-10-25: the same plugin also held its CELL records
    loose in the CELL group with no block / sub-block / children groups - a Mutagen patcher refused the file
    ("Read in data that was not a GRUP"), and Mutagen's full import silently dropped every cell, reference and
    dialogue response (1238 of 1312 records read). merge-to-espfe.py had flattened its sources' trees. So the
    whole tree is checked, not only the top-level labels:
      top level ......... only type-0 groups; never one labelled with a child type (REFR, ACHR, INFO, NAVM ...);
                          a plain group holds only records of its own label
      CELL .............. type 2 (block) > type 3 (sub-block) > CELL records, each optionally followed by its
                          type 6 children group > type 8/9/10 groups > placed records only
      WRLD .............. WRLD records, each optionally followed by its type 1 group > the persistent CELL with its
                          children, and type 4 > type 5 > CELL + children
      DIAL .............. DIAL records, each optionally followed by its type 7 group > INFO records only
    """
    fails = []

    def bad(msg):
        if len(fails) < limit:
            fails.append("group tree: " + msg)

    def recs(pos, end):
        while pos + 24 <= end:
            tag = data[pos:pos + 4]
            size = struct.unpack_from("<I", data, pos + 4)[0]
            if tag == b"GRUP":
                if size < 24 or pos + size > end:
                    bad("GRUP at 0x%X has an impossible size %d" % (pos, size))
                    return
                yield tag, pos, size, struct.unpack_from("<i", data, pos + 12)[0], struct.unpack_from("<I", data, pos + 8)[0]
                pos += size
            else:
                yield tag, pos, size, None, struct.unpack_from("<I", data, pos + 12)[0]
                pos += 24 + size

    def name(tag):
        return tag.decode("latin-1", "replace")

    def cell_children(pos, end, cell):
        for tag, p, s, gtype, label in recs(pos, end):
            if tag != b"GRUP" or gtype not in (8, 9, 10):
                bad("CELL %08X's children group holds %s - only persistent/temporary/distant groups belong there"
                    % (cell, name(tag) if tag != b"GRUP" else "a type-%d group" % gtype))
                continue
            if label != cell:
                bad("a type-%d group under CELL %08X is labelled %08X" % (gtype, cell, label))
            for t2, p2, s2, g2, l2 in recs(p + 24, p + s):
                if t2 == b"GRUP" or t2 not in PLACED:
                    bad("CELL %08X's references group holds %s" % (cell, "a group" if t2 == b"GRUP" else name(t2)))

    def cells_with_children(pos, end, where):
        last = None
        for tag, p, s, gtype, label in recs(pos, end):
            if tag == b"CELL":
                last = label
            elif tag == b"GRUP" and gtype == 6:
                if last is None or label != last:
                    bad("a cell-children group labelled %08X in %s does not follow its CELL" % (label, where))
                cell_children(p + 24, p + s, label)
                last = None
            else:
                yield tag, p, s, gtype, label

    for tag, p, s, gtype, label in recs(24 + struct.unpack_from("<I", data, 4)[0], len(data)):
        if tag != b"GRUP":
            bad("a %s record sits outside every group" % name(tag))
            continue
        lab = data[p + 8:p + 12]
        if gtype != 0:
            bad("a type-%d group sits at the top level" % gtype)
            continue
        if lab in NESTED:
            bad("top-level GRUP %s: those records only load inside their %s group"
                % (name(lab), "DIAL topic" if lab == b"INFO" else "CELL/WRLD"))
            continue
        if lab == b"CELL":
            for t1, p1, s1, g1, l1 in recs(p + 24, p + s):
                if t1 != b"GRUP" or g1 != 2:
                    bad("the CELL group holds %s directly - interior cells go in block (type 2) and sub-block "
                        "(type 3) groups" % (name(t1) + " %08X" % l1 if t1 != b"GRUP" else "a type-%d group" % g1))
                    continue
                for t2, p2, s2, g2, l2 in recs(p1 + 24, p1 + s1):
                    if t2 != b"GRUP" or g2 != 3:
                        bad("an interior block holds %s - only sub-block (type 3) groups belong there"
                            % (name(t2) if t2 != b"GRUP" else "a type-%d group" % g2))
                        continue
                    for t3, p3, s3, g3, l3 in cells_with_children(p2 + 24, p2 + s2, "an interior sub-block"):
                        bad("an interior sub-block holds %s" % (name(t3) if t3 != b"GRUP" else "a type-%d group" % g3))
        elif lab == b"WRLD":
            last = None
            for t1, p1, s1, g1, l1 in recs(p + 24, p + s):
                if t1 == b"WRLD":
                    last = l1
                    continue
                if t1 != b"GRUP" or g1 != 1 or l1 != last:
                    bad("the WRLD group holds %s that is not a WRLD record or its own world-children group"
                        % (name(t1) if t1 != b"GRUP" else "a type-%d group" % g1))
                    continue
                for t2, p2, s2, g2, l2 in cells_with_children(p1 + 24, p1 + s1, "WRLD %08X" % l1):
                    if t2 == b"GRUP" and g2 == 4:
                        for t3, p3, s3, g3, l3 in recs(p2 + 24, p2 + s2):
                            if t3 != b"GRUP" or g3 != 5:
                                bad("an exterior block holds %s" % (name(t3) if t3 != b"GRUP" else "a type-%d group" % g3))
                                continue
                            for t4, p4, s4, g4, l4 in cells_with_children(p3 + 24, p3 + s3, "an exterior sub-block"):
                                bad("an exterior sub-block holds %s" % (name(t4) if t4 != b"GRUP" else "a type-%d group" % g4))
                    elif t2 != b"ROAD":
                        bad("WRLD %08X's children hold %s" % (l1, name(t2) if t2 != b"GRUP" else "a type-%d group" % g2))
        elif lab == b"DIAL":
            last = None
            for t1, p1, s1, g1, l1 in recs(p + 24, p + s):
                if t1 == b"DIAL":
                    last = l1
                elif t1 == b"GRUP" and g1 == 7:
                    if last is None or l1 != last:
                        bad("a topic-children group labelled %08X does not follow its DIAL" % l1)
                    for t2, p2, s2, g2, l2 in recs(p1 + 24, p1 + s1):
                        if t2 != b"INFO":
                            bad("DIAL %08X's topic-children group holds %s" % (l1, "a group" if t2 == b"GRUP" else name(t2)))
                    last = None
                else:
                    bad("the DIAL group holds %s" % (name(t1) if t1 != b"GRUP" else "a type-%d group" % g1))
        else:
            for t1, p1, s1, g1, l1 in recs(p + 24, p + s):
                if t1 != lab:
                    bad("the top-level %s group holds %s" % (name(lab), "a group" if t1 == b"GRUP" else name(t1)))
                    break
    return fails


def audit(path):
    data = open(path, "rb").read()
    fails, notes = [], []
    if data[:4] != b"TES4":
        return ["%s is not a plugin (no TES4 header)" % path], notes

    header_flags = struct.unpack_from("<I", data, 8)[0]
    light = bool(header_flags & 0x200)
    masters = 0
    hedr = 0.0
    hdr = data[24:24 + struct.unpack_from("<I", data, 4)[0]]
    for off, sig, ln in subrecords(hdr):
        if sig == b"MAST":
            masters += 1
        elif sig == b"HEDR" and ln >= 4:
            hedr = struct.unpack_from("<f", hdr, off + 6)[0]
    own = masters << 24

    # The group tree (2026-09-21, widened 2026-10-25): every record sits where the engine and Mutagen look for it.
    fails.extend(group_tree_fails(data))

    defined, refs, count = set(), [], 0
    for sig, formid, flags, body in records(data):
        if sig == b"TES4":
            continue
        count += 1
        defined.add(formid)
        where = "%s %08X" % (sig.decode("ascii", "replace"), formid)

        # A CELL with no DATA (2026-11-05, Ysgramor's Armor addon 1.0.1: an EDID alone over a vanilla interior) blanks the
        # cell's flags, and a patcher built on it writes the cell as exterior, which crashed the game on a null worldspace.
        # A plugin of ours that must carry a parent CELL copies it whole from the winner. A deleted record has no fields.
        if sig == b"CELL" and not flags & 0x20 and not any(ssig == b"DATA" for _, ssig, _ in subrecords(body)):
            fails.append("%s: a CELL with no DATA - copy the whole record from the previous winner, or remove it" % where)

        # COCT/CNTO can appear MORE THAN ONCE in a record - a quest carries one block per reference alias -
        # so each count is checked against the entries that follow IT, not against the record's total.
        blocks, coct, cnto = [], None, 0
        llct = ksiz = None
        lvlo = kwda = modl = 0
        for off, ssig, ln in subrecords(body):
            if ssig == b"COCT" and ln == 4:
                if coct is not None:
                    blocks.append((coct, cnto))
                coct, cnto = struct.unpack_from("<I", body, off + 6)[0], 0
            elif ssig == b"CNTO":
                cnto += 1
            elif ssig == b"LLCT" and ln == 1:
                llct = body[off + 6]
            elif ssig == b"LVLO":
                lvlo += 1
            elif ssig == b"KSIZ" and ln == 4:
                ksiz = struct.unpack_from("<I", body, off + 6)[0]
            elif ssig == b"KWDA":
                kwda += ln // 4
            elif ssig == b"CRDT" and sig == b"WEAP" and FORMVER.get(formid, 0) >= 44 and ln != 24:
                fails.append("%s: form-44 weapon with a %d-byte CRDT - the form-43 layout; the crit spell is read from the wrong bytes (esp-form44.py converts it)" % (where, ln))
            elif ssig == b"MODL":
                modl += 1
                if sig == b"ARMO" and ln != 4:
                    fails.append("%s: ARMO MODL is %d bytes - one MODL per armature addon, never a packed list" % (where, ln))
            if ssig in MODEL_HASHES:
                wrong = model_hash_fail(FORMVER.get(formid, 0), ssig, body[off + 6:off + 6 + ln])
                if wrong:
                    fails.append("%s: model hashes: %s" % (where, wrong))
            slot = None if (sig, ssig) in NOT_REFS else FORMID_SLOTS.get(ssig)
            if slot:
                stride, inner = slot
                for k in range(0, ln - inner - 3, stride):
                    refs.append((where, ssig.decode("ascii", "replace"),
                                 struct.unpack_from("<I", body, off + 6 + k + inner)[0]))
        if coct is not None:
            blocks.append((coct, cnto))

        for said, held in blocks:
            if said != held:
                fails.append("%s: COCT says %d but %d CNTO entries follow it - the engine reads past the list" % (where, said, held))
        if llct is not None and llct != lvlo:
            fails.append("%s: LLCT says %d but the record holds %d LVLO entries" % (where, llct, lvlo))
        if ksiz is not None and ksiz != kwda:
            fails.append("%s: KSIZ says %d but KWDA holds %d keywords" % (where, ksiz, kwda))
        if light and (formid >> 24) == masters:
            local = formid & 0xFFFFFF
            # 2026-10-11 (AMF 2.1.9 AE test): a plugin with header version 1.71 may use the extended light range
            # 0x001-0xFFF, which the game reads from 1.6.1130 on - Navigation Restrictions NG 3.0.1 and Lurking Menace
            # 4.0.1 ship such ESLs for AE. The 0x800 floor holds for every older runtime (SE 1.5.97) and older header.
            lo = 0x001 if (EXTENDED_ESL and hedr >= 1.705) else 0x800
            if not (lo <= local <= 0xFFF):
                fails.append("%s: light plugin's own record is outside 0x%03X-0xFFF - it is unreachable at runtime%s"
                             % (where, lo, "" if lo == 0x001 else " (header %.2f, runtime %s)" % (hedr, RUNTIME or "SE/unknown")))

    for where, ssig, ref in refs:
        if ref == 0 or (ref >> 24) != masters:
            continue
        if ref not in defined:
            fails.append("%s: %s points at %08X, which no record in this file defines" % (where, ssig, ref))

    notes.append("%s  %s  %d masters, %d records, %d references checked"
                 % (os.path.basename(path), "ESPFE" if light else "full plugin", masters, count, len(refs)))
    return fails, notes


def main(argv):
    global RUNTIME, EXTENDED_ESL
    if "--runtime" in argv:
        i = argv.index("--runtime")
        RUNTIME = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
        try:
            EXTENDED_ESL = tuple(int(x) for x in RUNTIME.split(".")[:3]) >= (1, 6, 1130)
        except ValueError:
            EXTENDED_ESL = False
    if not argv:
        print(__doc__)
        return 2
    bad = 0
    for path in argv:
        fails, notes = audit(path)
        for n in notes:
            print("esp-audit  " + n)
        for f in fails:
            print("  FAIL  " + f)
        if fails:
            bad += 1
        else:
            print("  pass  every count matches its entries and every own reference resolves")
    if bad:
        print("esp-audit  FAIL  %d plugin(s) would load a lie to the engine" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
