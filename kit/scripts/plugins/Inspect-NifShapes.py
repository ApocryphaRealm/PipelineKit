#!/usr/bin/env python3
"""
Inspect-NifShapes.py
Lists the SHAPES in a Skyrim SE mesh - their names and block types.

    python Inspect-NifShapes.py <file.nif> [<file.nif> ...]

WHY
    A BodySlide slider set names every shape it works on: `<Shape target="X">X</Shape>`. Those names
    have to match the mesh exactly, and reading them out of the file beats reading them off a
    screenshot of Outfit Studio or retyping them by eye.

    It reports names and types only. Vertex counts were tried and dropped: BSTriShape's counts sit
    behind a run of variable-length fields, the walk did not land reliably on real meshes, and a
    wrong count here would be worse than no count - Outfit Studio shows them anyway.

HOW IT READS THEM
    A Skyrim SE nif (Gamebryo 20.2.0.7) keeps every name in ONE shared string table in the header,
    and each block refers to a name by index into it. Every block derived from NiObjectNET - which
    includes every shape - begins with that 4-byte index, so the name is the first thing in the
    block and needs no per-type parsing.

"""
import struct
import sys


class Nif:
    def __init__(self, data: bytes):
        self.data = data
        nl = data.index(b"\n")
        if b"20.2.0.7" not in data[:nl]:
            raise SystemExit(f"not a Skyrim SE nif: {data[:nl]!r}")
        o = nl + 1
        self.version = struct.unpack_from("<I", data, o)[0]; o += 4
        o += 1                                                   # endian
        self.user_version = struct.unpack_from("<I", data, o)[0]; o += 4
        self.num_blocks = struct.unpack_from("<I", data, o)[0]; o += 4
        self.user_version2 = struct.unpack_from("<I", data, o)[0]; o += 4
        for _ in range(3):
            o += 1 + data[o]
        if self.user_version2 >= 130:
            o += 1 + data[o]
        n_types = struct.unpack_from("<H", data, o)[0]; o += 2
        self.block_types = []
        for _ in range(n_types):
            ln = struct.unpack_from("<I", data, o)[0]; o += 4
            self.block_types.append(data[o:o + ln].decode("latin1")); o += ln
        self.type_index = list(struct.unpack_from(f"<{self.num_blocks}H", data, o))
        o += 2 * self.num_blocks
        self.block_sizes = list(struct.unpack_from(f"<{self.num_blocks}I", data, o))
        o += 4 * self.num_blocks
        n_str = struct.unpack_from("<I", data, o)[0]; o += 4
        o += 4                                                   # max string length
        self.strings = []
        for _ in range(n_str):
            ln = struct.unpack_from("<I", data, o)[0]; o += 4
            self.strings.append(data[o:o + ln].decode("latin1")); o += ln
        n_groups = struct.unpack_from("<I", data, o)[0]; o += 4
        o += 4 * n_groups
        self.blocks_at = o

    def blocks(self):
        off = self.blocks_at
        for i, size in enumerate(self.block_sizes):
            yield i, self.block_types[self.type_index[i]], off, size
            off += size

    def name_of(self, off):
        idx = struct.unpack_from("<i", self.data, off)[0]
        return self.strings[idx] if 0 <= idx < len(self.strings) else None


SHAPE_TYPES = ("BSTriShape", "BSDynamicTriShape", "BSSubIndexTriShape", "NiTriShape", "NiTriStrips")


def main(paths):
    if not paths:
        raise SystemExit(__doc__)
    for p in paths:
        d = open(p, "rb").read()
        nif = Nif(d)
        print(f"\n{p}")
        print(f"   {nif.num_blocks} blocks, {len(nif.strings)} strings")
        found = 0
        for i, typ, off, size in nif.blocks():
            if typ not in SHAPE_TYPES:
                continue
            found += 1
            name = nif.name_of(off)
            print(f"   shape  {name!r:34s} {typ}")
        if not found:
            print("   (no shape blocks found - block types present: "
                  + ", ".join(sorted(set(nif.block_types))) + ")")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
