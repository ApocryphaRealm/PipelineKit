r"""pex-scrub.py - blank the build identity in compiled Papyrus (.pex) headers, in place (2026-10-26).

The Papyrus compiler writes the source path, the compiling account's user name and the machine name into every .pex
header. gate-rules row shipped-pex-carries-no-build-identity (role pex-header-gate) refuses a package carrying them.
This rewrites the three header strings: the source keeps its bare file name, user and machine become the neutral
words "author" / "build" (the same words NjordlingerCombatGameplayOverhaul\tools\build-papyrus.py scrub() writes and
pex-header-gate.py accepts). The script body after the header is untouched, so the game runs the same code.
compile-papyrus.ps1 runs it on every script it compiles.

Usage:  python pex-scrub.py <file.pex | folder> [...]      every .pex under a folder
Exit 0 all scrubbed (or already clean), 1 a file whose header does not parse. Never prints the names it removes.
"""
import os, sys

MAGIC = 0xFA57C0DE


def scrub_bytes(d):
    if len(d) < 16:
        raise ValueError("shorter than a .pex header")
    if int.from_bytes(d[0:4], "big") == MAGIC:
        e = "big"
    elif int.from_bytes(d[0:4], "little") == MAGIC:
        e = "little"
    else:
        raise ValueError("no .pex magic")
    pos = 16
    fields = []
    for _ in range(3):
        if pos + 2 > len(d):
            raise ValueError("header truncated")
        n = int.from_bytes(d[pos:pos + 2], e)
        if pos + 2 + n > len(d):
            raise ValueError("header string runs past the end")
        fields.append(d[pos + 2:pos + 2 + n])
        pos += 2 + n
    src = fields[0].decode("latin-1").replace("/", "\\").rsplit("\\", 1)[-1].encode("latin-1")
    new = b"".join(len(s).to_bytes(2, e) + s for s in (src, b"author", b"build"))
    return d[:16] + new + d[pos:]


def files(args):
    for a in args:
        if os.path.isdir(a):
            for root, _, fs in os.walk(a):
                for f in fs:
                    if f.lower().endswith(".pex"):
                        yield os.path.join(root, f)
        else:
            yield a


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    bad = n = changed = 0
    for p in files(argv):
        n += 1
        d = open(p, "rb").read()
        try:
            out = scrub_bytes(d)
        except ValueError as ex:
            print("FAIL  pex-scrub  %s: %s" % (os.path.basename(p), ex))
            bad += 1
            continue
        if out != d:
            open(p, "wb").write(out)
            changed += 1
    print("pex-scrub  %d .pex, %d rewritten, %d already clean, %d failed" % (n, changed, n - changed - bad, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
