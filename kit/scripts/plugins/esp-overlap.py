r"""esp-overlap.py - which records two (or more) plugins BOTH define or override, resolved to (origin plugin, local id),
with each one's record type and EDID, and where each plugin sits in a profile's load order.

    python esp-overlap.py <a.esp> <b.esp> [more.esp ...] [--profile "Njordlinger Test"]

Written 2026-09-22 for the Always Snowing / Ophyre's Honeyside patch.

ROOM AND PORTAL MARKERS (2026-10-27, pipeline assessment item 13): a placed RoomMarker (Skyrim.esm 0x1F) or PortalMarker
(0x20) that two of the plugins edit differently is listed with its cell and the plugin that WINS it (the last in the
profile's load order, else the last on the command line). It is FLAGGED (exit 1) when the winner is not the plugin that
moved the doorway - the one that edits the most other refs in that cell. Why: Skyrim Project Optimization's .esm
loaded after JK's Blue Palace Terrace and put room marker 0EB5A9 back to its vanilla size while JK had moved the
doorway, so a strip of the floor belonged to no room - see-through but walkable (past-mistakes library, Blue Palace).
Exit codes: 0 no marker flagged, 1 a room / portal marker is won by a plugin that did not move its doorway, 2 usage.
"""
import os, struct, sys, zlib

MARKER_BASES = {("skyrim.esm", 0x1F): "RoomMarker", ("skyrim.esm", 0x20): "PortalMarker"}


def read(path, cells=None):
    """(masters, recs). recs: (origin plugin lower, local id) -> (type, EDID, body). When `cells` is a dict, it is filled
    with key -> (parent cell key or None, base key or None) for every placed reference."""
    b = open(path, "rb").read()
    n = struct.unpack("<I", b[4:8])[0]; d = b[24:24 + n]; i = 0; masters = []
    while i < len(d):
        t = d[i:i + 4]; l = struct.unpack("<H", d[i + 4:i + 6])[0]
        if t == b"MAST":
            masters.append(d[i + 6:i + 6 + l].rstrip(b"\0").decode("cp1252"))
        i += 6 + l
    me = os.path.basename(path)

    def key(fid):
        idx = fid >> 24
        return ((masters[idx] if idx < len(masters) else me).lower(), fid & 0xFFFFFF)

    recs = {}

    def walk(p, e, parent):
        while p < e:
            sz = struct.unpack("<I", b[p + 4:p + 8])[0]
            if b[p:p + 4] == b"GRUP":
                gtype = struct.unpack("<i", b[p + 12:p + 16])[0]; label = struct.unpack("<I", b[p + 8:p + 12])[0]
                walk(p + 24, p + sz, key(label) if gtype in (6, 8, 9, 10) else parent); p += sz; continue
            t = b[p:p + 4].decode(); fl, fid = struct.unpack("<II", b[p + 8:p + 16])
            body = b[p + 24:p + 24 + sz]
            if fl & 0x40000:
                body = zlib.decompress(body[4:])
            edid = ""; base = None; j = 0
            while j + 6 <= len(body):
                st = body[j:j + 4]; l = struct.unpack("<H", body[j + 4:j + 6])[0]
                if st == b"EDID":
                    edid = body[j + 6:j + 6 + l].rstrip(b"\0").decode("cp1252", "replace")
                elif st == b"NAME" and t in ("REFR", "ACHR") and l == 4:
                    base = key(struct.unpack("<I", body[j + 6:j + 10])[0])
                j += 6 + l
            recs[key(fid)] = (t, edid, body)
            if cells is not None and t in ("REFR", "ACHR"):
                cells[key(fid)] = (parent, base)
            p += 24 + sz
    walk(24 + n, len(b), None)
    return masters, recs


def marker_findings(data, order):
    """[(flagged, text)] for every room / portal marker two or more plugins edit differently. data: plugin ->
    (masters, recs, cells); order: plugin names, earliest first (the last wins)."""
    out = []
    names = list(order)
    keys = set()
    for n in names:
        for k, (parent, base) in data[n][2].items():
            if base in MARKER_BASES:
                keys.add(k)
    for k in sorted(keys):
        editors = [n for n in names if k in data[n][1]]
        if len(editors) < 2 or len({data[n][1][k][2] for n in editors}) < 2:
            continue
        parent, base = next(data[n][2][k] for n in editors if k in data[n][2])
        winner = editors[-1]
        # the plugin that moved the doorway: the most OTHER refs edited in the same cell
        moved = {n: sum(1 for kk, (pp, bb) in data[n][2].items() if pp == parent and kk != k and bb not in MARKER_BASES)
                 for n in editors}
        mover = max(editors, key=lambda n: (moved[n], names.index(n)))
        flagged = moved[mover] > 0 and mover != winner
        cell = "%s:%06X" % parent if parent else "?"
        text = ("%s %s %06X from %s in cell %s: edited by %s; WINS: %s; doorway moved by %s (%d other ref(s) in the cell)"
                % ("FLAG" if flagged else "ok  ", MARKER_BASES[base], k[1], k[0], cell,
                   ", ".join("%s (%d refs)" % (n, moved[n]) for n in editors), winner, mover, moved[mover]))
        if flagged:
            text += (" - the winner restores a marker the doorway no longer fits: load %s after %s, or carry its marker "
                     "into a patch" % (mover, winner))
        out.append((flagged, text))
    return out


def main(argv):
    files = [a for a in argv if not a.startswith("--") and a.lower().endswith((".esp", ".esm", ".esl"))]
    if len(files) < 2:
        print(__doc__)
        return 2
    profile = argv[argv.index("--profile") + 1] if "--profile" in argv else None
    data = {}
    for f in files:
        cells = {}
        m, r = read(f, cells)
        data[os.path.basename(f)] = (m, r, cells)
    order = list(data)
    if profile:
        lo = [l.strip().lstrip("*").lower() for l in open(os.path.join(os.path.dirname(((os.environ.get("PIPELINE_MO2_INSTANCES") or "").split(";")[0]).rstrip("\\/")), "profiles", profile, "loadorder.txt"), encoding="utf-8")  # kit: the first MO2 instance]
        for n in data:
            print(f"load order in {profile}: {n} at {lo.index(n.lower()) if n.lower() in lo else 'absent'}")
        order.sort(key=lambda n: lo.index(n.lower()) if n.lower() in lo else 10 ** 6)
    names = list(data)
    for i in range(len(names)):
        for k in range(i + 1, len(names)):
            a, b_ = names[i], names[k]
            common = sorted(set(data[a][1]) & set(data[b_][1]))
            print(f"\n{a}  x  {b_}: {len(common)} shared record(s)")
            for key in common:
                t, e, body_a = data[a][1][key]; _, e2, body_b = data[b_][1][key]
                print(f"  {t} {key[1]:06X} from {key[0]} '{e or e2}'  {'identical' if body_a == body_b else 'DIFFERENT'}")
    findings = marker_findings(data, order)
    print("\nROOM / PORTAL MARKERS edited differently: %d (%d flagged)" % (len(findings), sum(f for f, _ in findings)))
    for _, text in findings:
        print("  " + text)
    return 1 if any(f for f, _ in findings) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
