"""Read an Address Library database (version-*-*.bin) and map IDs to module offsets.

Why this exists: CommonLibSSE only binds the handful of engine functions somebody has needed so
far. When a mechanism needs a function it has NOT bound - here, whatever renders the UI 3D scene -
the way to find it is to disassemble a function that calls it and map the call targets back to
Address Library IDs, which is what everyone else's offsets are quoted in.

The on-disk SkyrimSE.exe is Steam-packed, so this never reads the exe: offsets come from the
library file, and the bytes to disassemble are read out of the RUNNING process by the plugin.

Format is meh321's, as implemented by CommonLibSSE's REL::IDDatabase:
    int32 format, int32 version[4], int32 nameLen + name, int32 pointerSize, int32 addressCount
    then addressCount entries, each a type byte whose low nibble encodes the ID delta and whose
    high nibble encodes the offset delta (bit 3 of the high nibble means "in pointer-size units").

Usage:
    python addrlib.py <bin> id <id> [<id> ...]     - offsets for these IDs
    python addrlib.py <bin> offset <hex> [...]     - which ID owns each offset (exact match)
    python addrlib.py <bin> range <lo> <hi>        - every ID in a range, with its offset
"""

import struct
import sys


def load(path):
    with open(path, 'rb') as f:
        data = f.read()
    pos = 0

    def u8():
        nonlocal pos
        v = data[pos]; pos += 1; return v

    def i32():
        nonlocal pos
        v = struct.unpack_from('<i', data, pos)[0]; pos += 4; return v

    def u16():
        nonlocal pos
        v = struct.unpack_from('<H', data, pos)[0]; pos += 2; return v

    def u32():
        nonlocal pos
        v = struct.unpack_from('<I', data, pos)[0]; pos += 4; return v

    def u64():
        nonlocal pos
        v = struct.unpack_from('<Q', data, pos)[0]; pos += 8; return v

    fmt = i32()
    # SE's version-1-5-97-0.bin declares format 1 and AE's declares 2; both carry the same
    # delta-encoded body, so both are read the same way.
    if fmt not in (1, 2):
        raise SystemExit(f'unsupported address library format {fmt}')
    ver = [i32() for _ in range(4)]
    name_len = i32()
    pos += name_len
    ptr_size = i32()
    count = i32()

    mapping = {}
    prev_id = 0
    prev_off = 0
    for _ in range(count):
        t = u8()
        lo, hi = t & 0xF, t >> 4

        if lo == 0:
            ident = u64()
        elif lo == 1:
            ident = prev_id + 1
        elif lo == 2:
            ident = prev_id + u8()
        elif lo == 3:
            ident = prev_id - u8()
        elif lo == 4:
            ident = prev_id + u16()
        elif lo == 5:
            ident = prev_id - u16()
        elif lo == 6:
            ident = u16()
        elif lo == 7:
            ident = u32()
        else:
            raise SystemExit(f'bad id encoding {lo}')

        tmp = (prev_off // ptr_size) if (hi & 8) else prev_off
        h = hi & 7
        if h == 0:
            off = u64()
        elif h == 1:
            off = tmp + 1
        elif h == 2:
            off = tmp + u8()
        elif h == 3:
            off = tmp - u8()
        elif h == 4:
            off = tmp + u16()
        elif h == 5:
            off = tmp - u16()
        elif h == 6:
            off = u16()
        elif h == 7:
            off = u32()
        else:
            raise SystemExit(f'bad offset encoding {h}')
        if hi & 8:
            off *= ptr_size

        mapping[ident] = off
        prev_id, prev_off = ident, off

    return ver, ptr_size, mapping


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    ver, ptr_size, mapping = load(sys.argv[1])
    mode = sys.argv[2]
    print(f'# version {".".join(map(str, ver))}, {len(mapping)} ids, pointer size {ptr_size}')

    if mode == 'id':
        for a in sys.argv[3:]:
            i = int(a, 0)
            off = mapping.get(i)
            print(f'{i}\t{"0x%X" % off if off is not None else "MISSING"}')
    elif mode == 'offset':
        rev = {v: k for k, v in mapping.items()}
        for a in sys.argv[3:]:
            off = int(a, 16)
            print(f'0x{off:X}\t{rev.get(off, "no exact id")}')
    elif mode == 'range':
        lo, hi = int(sys.argv[3], 0), int(sys.argv[4], 0)
        for i in range(lo, hi + 1):
            if i in mapping:
                print(f'{i}\t0x{mapping[i]:X}')
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
