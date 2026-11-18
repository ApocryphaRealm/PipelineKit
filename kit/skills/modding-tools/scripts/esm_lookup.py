r"""Look a record up by EditorID in a Skyrim SE plugin (.esm/.esp/.esl) and print its FormID - so a FormID in a test
script or in code comes from the plugin's own records, never from memory (memory look-up-form-ids-never-recall-them:
0x0002ACD2 "recalled" as Dawnbreaker was Volendrung, and a whole in-game run was lost to it).

    python esm_lookup.py <plugin> <TYPE> <EditorID or wildcard> [--full]
    e.g. python esm_lookup.py "<MO2>\<test instance>\Stock Game\Data\Skyrim.esm" WEAP "*Dawnbreaker*"   -> 0004E4EE DA09Dawnbreaker
         python esm_lookup.py Skyrim.esm SPEL Firebolt

Prints  FORMID  TYPE  EDITORID  [FULL name with --full]  for every match. The FormID is as stored in the file: its top
byte indexes the plugin's own master list (printed first), so 0x00 in Skyrim.esm is Skyrim.esm itself. A record from
a light or regular plugin gets its RUNTIME prefix from the load order - ask the running game for that
(role resolve-formid: resolve.py find resolve-formid), never write it down.
Reads only the top-level group of TYPE; compressed records (flag 0x00040000) are inflated. Read-only.
"""
import fnmatch, struct, sys, zlib


def subrecords(data):
    i, big = 0, None
    while i + 6 <= len(data):
        sig, size = data[i:i + 4], struct.unpack_from("<H", data, i + 4)[0]
        i += 6
        if sig == b"XXXX":                      # next subrecord's size does not fit in 16 bits
            big = struct.unpack_from("<I", data, i)[0]
            i += size
            continue
        if big is not None:
            size, big = big, None
        yield sig, data[i:i + size]
        i += size


def zstr(b):
    return b.split(b"\0", 1)[0].decode("cp1252", "replace")


def main():
    args = [a for a in sys.argv[1:] if a != "--full"]
    if len(args) != 3:
        sys.exit(__doc__)
    path, rtype, pattern = args[0], args[1].upper().encode(), args[2]
    want_full = "--full" in sys.argv
    buf = open(path, "rb").read()
    if buf[:4] != b"TES4":
        sys.exit(f"{path}: not a Skyrim plugin (no TES4 header)")
    hsize = struct.unpack_from("<I", buf, 4)[0]
    masters = [zstr(d) for s, d in subrecords(buf[24:24 + hsize]) if s == b"MAST"]
    print("masters:", ", ".join(f"{i:02X}={m}" for i, m in enumerate(masters)) or "(none)")
    pos, hits = 24 + hsize, 0
    while pos + 24 <= len(buf):
        if buf[pos:pos + 4] != b"GRUP":
            sys.exit(f"unexpected data at offset {pos:#x}")
        gsize, label = struct.unpack_from("<I4s", buf, pos + 4)
        if label == rtype:
            hits += scan(buf, pos + 24, pos + gsize, rtype, pattern, want_full)
        pos += gsize
    if not hits:
        print(f"no {rtype.decode()} record matches {pattern!r}")
        sys.exit(1)


def scan(buf, pos, end, rtype, pattern, want_full):
    hits = 0
    while pos < end:
        sig = buf[pos:pos + 4]
        size = struct.unpack_from("<I", buf, pos + 4)[0]
        if sig == b"GRUP":                      # nested groups (CELL/WRLD/DIAL children): descend
            hits += scan(buf, pos + 24, pos + size, rtype, pattern, want_full)
            pos += size
            continue
        flags, formid = struct.unpack_from("<II", buf, pos + 8)
        data = buf[pos + 24:pos + 24 + size]
        if flags & 0x00040000:
            data = zlib.decompress(data[4:])
        edid = full = ""
        for s, d in subrecords(data):
            if s == b"EDID":
                edid = zstr(d)
            elif s == b"FULL" and want_full:
                full = zstr(d) if len(d) != 4 else f"(localized string {struct.unpack('<I', d)[0]:#x})"
        if sig == rtype and fnmatch.fnmatchcase(edid.lower(), pattern.lower()):
            print(f"{formid:08X}  {sig.decode()}  {edid}" + (f"  {full}" if full else ""))
            hits += 1
        pos += 24 + size
    return hits


if __name__ == "__main__":
    main()
