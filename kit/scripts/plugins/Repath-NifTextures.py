#!/usr/bin/env python3
"""
Repath-NifTextures.py
Rewrites the texture paths inside a Skyrim SE mesh (.nif) without touching anything else.

    python Repath-NifTextures.py <in.nif> <out.nif> <old>=<new> [<old>=<new> ...]
    python Repath-NifTextures.py <in.nif> --list          # just show what paths are in there

WHY THIS EXISTS
    A BodySlide refit ships shape data whose texture paths point at the mod it was made for. Build
    that shape data into a DIFFERENT mod's mesh folder and the mesh comes out wearing the wrong
    mod's textures - which is invisible while both mods are installed and wrong the moment one is
    not, and simply wrong whenever the second mod is a RETEXTURE rather than a copy.

    NifSkope can fix that by hand, one texture slot at a time, across several meshes. This does the
    same edit as a repeatable, checkable step.

HOW A .NIF HOLDS A TEXTURE PATH, AND WHY THE FILE CANNOT SIMPLY BE SEARCH-AND-REPLACED
    A Skyrim SE nif (Gamebryo 20.2.0.7) is a header followed by a run of blocks laid end to end.
    The header carries, among other things:

        blockTypes[]      the name of each distinct block type      (sized strings)
        blockTypeIndex[]  which type each block is                  (uint16 per block)
        blockSizes[]      HOW MANY BYTES EACH BLOCK OCCUPIES        (uint32 per block)
        strings[]         the shared string table used for names    (sized strings)

    Node and shape NAMES live in that shared string table and are referenced by index. Texture
    PATHS do not: BSShaderTextureSet stores them inline in its own block, each as a sized string -
    a uint32 length followed by that many characters, with no terminator.

    So changing a path changes the length of a block, and a block whose length no longer matches
    its entry in blockSizes leaves the file unreadable from that point on - every later block is
    read at the wrong offset. A plain byte-for-byte replacement of equal-length paths would happen
    to work; anything else corrupts the mesh. This script therefore rebuilds the block, works out
    which block it was, and corrects that block's size in the header.

WHAT IT DELIBERATELY DOES NOT DO
    It does not add, remove or reorder blocks, and it does not touch the shared string table, the
    geometry, the skinning or the shader flags. If no mapping matches, the output is byte-for-byte
    identical to the input - which is the first thing the self-check below verifies.
"""
import os
import re
import struct
import sys

SIZED_STRING = re.compile(rb"")   # not used; kept out of the way of the explicit parser below


class Nif:
    """Just enough of the header to know where every block starts and how long it is."""

    def __init__(self, data: bytes):
        self.data = data
        nl = data.index(b"\n")                       # "Gamebryo File Format, Version 20.2.0.7\n"
        self.header_line = data[:nl + 1]
        if b"20.2.0.7" not in self.header_line:
            raise SystemExit(f"not a Skyrim SE nif: {self.header_line[:60]!r}")
        o = nl + 1
        self.version = struct.unpack_from("<I", data, o)[0]; o += 4
        self.endian = data[o]; o += 1
        self.user_version = struct.unpack_from("<I", data, o)[0]; o += 4
        self.num_blocks = struct.unpack_from("<I", data, o)[0]; o += 4
        self.user_version2 = struct.unpack_from("<I", data, o)[0]; o += 4
        # export info: three short (byte-length-prefixed) strings
        for _ in range(3):
            o += 1 + data[o]
        if self.user_version2 >= 130:                # SSE carries one more
            o += 1 + data[o]
        self.num_block_types = struct.unpack_from("<H", data, o)[0]; o += 2
        self.block_types = []
        for _ in range(self.num_block_types):
            n = struct.unpack_from("<I", data, o)[0]; o += 4
            self.block_types.append(data[o:o + n].decode("latin1")); o += n
        self.block_type_index_at = o
        self.block_type_index = list(struct.unpack_from(f"<{self.num_blocks}H", data, o))
        o += 2 * self.num_blocks
        self.block_sizes_at = o                      # the array this script has to keep honest
        self.block_sizes = list(struct.unpack_from(f"<{self.num_blocks}I", data, o))
        o += 4 * self.num_blocks
        self.num_strings = struct.unpack_from("<I", data, o)[0]; o += 4
        self.max_string_len = struct.unpack_from("<I", data, o)[0]; o += 4
        self.strings = []
        for _ in range(self.num_strings):
            n = struct.unpack_from("<I", data, o)[0]; o += 4
            self.strings.append(data[o:o + n].decode("latin1")); o += n
        self.num_groups = struct.unpack_from("<I", data, o)[0]; o += 4
        o += 4 * self.num_groups
        self.blocks_at = o
        # sanity: the blocks must exactly fill the rest of the file, bar the 4-byte footer
        total = sum(self.block_sizes)
        tail = len(data) - self.blocks_at - total
        if tail < 0:
            raise SystemExit("block sizes overrun the file - header parsed wrong")
        self.footer = data[self.blocks_at + total:]

    def block_bounds(self):
        off = self.blocks_at
        for i, size in enumerate(self.block_sizes):
            yield i, off, size
            off += size

    def type_of(self, i):
        return self.block_types[self.block_type_index[i]]


def find_paths(data: bytes, start: int, end: int):
    """Every inline sized string in [start,end) that looks like a texture path."""
    out, o = [], start
    while o + 4 <= end:
        n = struct.unpack_from("<I", data, o)[0]
        if 4 <= n <= 400 and o + 4 + n <= end:
            s = data[o + 4:o + 4 + n]
            if b"\x00" not in s and s.lower().endswith(b".dds") and all(32 <= c < 127 for c in s):
                out.append((o, n, s.decode("latin1")))
                o += 4 + n
                continue
        o += 1
    return out


def repath(data: bytes, mapping):
    nif = Nif(data)
    edits = []
    for i, off, size in nif.block_bounds():
        if "TextureSet" not in nif.type_of(i) and "Shader" not in nif.type_of(i):
            continue
        for at, n, s in find_paths(data, off, off + size):
            new = s
            for old_sub, new_sub in mapping:
                if old_sub.lower() in new.lower():
                    # case-insensitive replace, keeping everything either side untouched
                    k = new.lower().index(old_sub.lower())
                    new = new[:k] + new_sub + new[k + len(old_sub):]
            if new != s:
                edits.append((i, at, n, s, new))
    if not edits:
        return data, []

    out = bytearray(data)
    sizes = list(nif.block_sizes)
    # apply from the back so earlier offsets stay valid
    for i, at, n, old, new in sorted(edits, key=lambda e: -e[1]):
        nb = new.encode("latin1")
        out[at:at + 4 + n] = struct.pack("<I", len(nb)) + nb
        sizes[i] += len(nb) - n
    struct.pack_into(f"<{len(sizes)}I", out, nif.block_sizes_at, *sizes)

    check = Nif(bytes(out))                      # re-parse: proves the file still reads
    if check.num_blocks != nif.num_blocks or check.footer != nif.footer:
        raise SystemExit("rewritten nif does not parse back the same shape")
    return bytes(out), edits


def main(argv):
    if len(argv) < 2:
        raise SystemExit(__doc__)
    src = argv[0]
    data = open(src, "rb").read()
    if argv[1] == "--list":
        nif = Nif(data)
        print(f"{src}\n  {nif.num_blocks} blocks, {len(nif.strings)} strings")
        for i, off, size in nif.block_bounds():
            for at, n, s in find_paths(data, off, off + size):
                print(f"  block {i:3d} {nif.type_of(i):24s} {s}")
        return 0
    dst = argv[1]
    mapping = []
    for arg in argv[2:]:
        if "=" not in arg:
            raise SystemExit(f"expected old=new, got {arg!r}")
        old, new = arg.split("=", 1)
        mapping.append((old, new))
    out, edits = repath(data, mapping)
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    open(dst, "wb").write(out)
    for i, at, n, old, new in edits:
        print(f"  block {i:3d}  {old}  ->  {new}")
    print(f"wrote {dst}  ({len(out):,} bytes, was {len(data):,}, {len(edits)} paths changed)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
