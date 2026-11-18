#!/usr/bin/env python3
r"""Convert one of our plugins to an ESPFE: a .esp file carrying the light flag and nothing else.

WHY THIS EXISTS
    The owner, 2026-09-16: *"An ESPFE - .esp with the light flag - keeps the FE-space FormIDs and
    the freedom from the 254-slot limit, but sorts among the ordinary plugins - is the standing rule
    and we have to redo other mods that dont have this done"*.

    Ten of our plugins were not that. Most were `.esl` FILES, and Skyrim loads any `.esl` in the
    master block regardless of the header, so they sat pinned at the top of the load order where
    nothing can sort below them. Two of them also carried the ESM bit explicitly, which pins a
    plugin the same way even after it is renamed - so converting by extension alone would have
    looked right and changed nothing.

WHAT IT DOES
    * writes the plugin out as `.esp`, optionally under a new base name;
    * CLEARS the ESM bit (0x001), which is the one that pins it;
    * SETS the light bit (0x200);
    * leaves every other byte of the file exactly as it was.

WHAT IT REFUSES TO DO
    * convert a plugin whose new records fall outside 0x000800-0x000FFF, because the light flag
      would be a lie and the game would load it wrong;
    * overwrite an existing file, unless --force;
    * report success without proving it - the output is re-read and compared against the input, and
      the ONLY difference allowed is the four header flag bytes.

WHAT IT CANNOT DO FOR YOU
    A save records a plugin by FILE NAME. Renaming one - including changing its extension - breaks
    every save that used it. For a published mod that is a version bump and a note on the page, not
    a silent swap.

Usage:  python make-espfe.py <plugin> [--name <new base name>] [--out <dir>] [--force] [--in-place]
"""
import argparse
import os
import struct
import sys

ESM_FLAG = 0x00000001
LIGHT_FLAG = 0x00000200
ESL_FIRST, ESL_LAST = 0x000800, 0x000FFF


def fail(msg):
    raise SystemExit("make-espfe: " + msg)


def parse(data):
    """Return (header flags, master count, [new-record local ids])."""
    if data[:4] != b"TES4":
        fail("not a plugin - no TES4 header")
    hs = struct.unpack("<I", data[4:8])[0]
    flags = struct.unpack("<I", data[8:12])[0]
    masters, i = 0, 24
    while i + 6 <= 24 + hs:
        sig = data[i:i+4]
        n = struct.unpack("<H", data[i+4:i+6])[0]
        i += 6
        if sig == b"MAST":
            masters += 1
        i += n
    ids = []

    def walk(off, end):
        while off < end:
            t = data[off:off+4]
            n = struct.unpack("<I", data[off+4:off+8])[0]
            if t == b"GRUP":
                walk(off + 24, off + n)
                off += n
                continue
            fid = struct.unpack("<I", data[off+12:off+16])[0]
            if (fid >> 24) >= masters:
                ids.append(fid & 0xFFFFFF)
            off += 24 + n
    walk(24 + hs, len(data))
    return flags, masters, ids


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("plugin")
    ap.add_argument("--name", help="new base name, without extension (e.g. to drop a prefix)")
    ap.add_argument("--out", help="output directory (default: beside the input)")
    ap.add_argument("--force", action="store_true", help="overwrite an existing output file")
    ap.add_argument("--in-place", action="store_true", help="delete the input once the output verifies")
    a = ap.parse_args(argv)

    src = a.plugin
    if not os.path.isfile(src):
        fail("no such file: " + src)
    data = open(src, "rb").read()
    flags, masters, ids = parse(data)

    if ids and (min(ids) < ESL_FIRST or max(ids) > ESL_LAST):
        fail("%s has %d new records spanning 0x%06X-0x%06X, outside the light range 0x%06X-0x%06X. "
             "Flagging it light would be a lie; it needs renumbering first."
             % (os.path.basename(src), len(ids), min(ids), max(ids), ESL_FIRST, ESL_LAST))

    base = a.name or os.path.splitext(os.path.basename(src))[0]
    dest = os.path.join(a.out or os.path.dirname(src) or ".", base + ".esp")
    if os.path.abspath(dest) != os.path.abspath(src) and os.path.exists(dest) and not a.force:
        fail("%s already exists - pass --force to overwrite" % dest)

    new_flags = (flags & ~ESM_FLAG) | LIGHT_FLAG
    out = bytearray(data)
    struct.pack_into("<I", out, 8, new_flags)
    with open(dest, "wb") as f:
        f.write(bytes(out))

    # ---- prove it, rather than assume it
    check = open(dest, "rb").read()
    if len(check) != len(data):
        fail("output is a different length from the input - something other than flags changed")
    diff = [i for i in range(len(data)) if data[i] != check[i]]
    if any(i < 8 or i > 11 for i in diff):
        fail("bytes outside the header flags differ: %s" % diff[:8])
    vflags, _, vids = parse(check)
    if vflags & ESM_FLAG:
        fail("the ESM bit survived - the plugin would still be pinned to the top")
    if not vflags & LIGHT_FLAG:
        fail("the light bit is not set on the output")
    if vids != ids:
        fail("the record set changed, which it must not")

    if a.in_place and os.path.abspath(dest) != os.path.abspath(src):
        os.remove(src)

    print("%s  ->  %s" % (os.path.basename(src), os.path.basename(dest)))
    print("   flags 0x%08X -> 0x%08X   (ESM %s, light %s)"
          % (flags, new_flags,
             "cleared" if flags & ESM_FLAG else "was already off",
             "set" if not flags & LIGHT_FLAG else "was already on"))
    print("   new records ........ %d%s" % (len(ids),
          "" if not ids else "  (0x%06X-0x%06X, inside the light range)" % (min(ids), max(ids))))
    print("   verified ........... identical to the input apart from the four flag bytes")
    if a.in_place:
        print("   the original was removed")
    return dest


if __name__ == "__main__":
    main()
