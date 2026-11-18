r"""THE PEX HEADER GATE (gate-rules row shipped-pex-carries-no-build-identity, 2026-10-26).

The Papyrus compiler writes three strings into every compiled script's header: the source file path, the compiling
account's user name and the machine name. A .pex therefore carries the builder's identity into every package that
ships it, and the user-folder content row (shipped-files-carry-no-user-folder) cannot see it - the user field is the
bare account name, not a Users\<name>\ path. The project owner treats his name in anything that leaves the machine as
a severe privacy breach. Njordlinger Combat Gameplay Overhaul's tools\build-papyrus.py blanks the fields after
compiling; this gate refuses a .pex built any other way.

Header (UESP "Compiled Script File Format"): magic 0xFA57C0DE (big-endian for Skyrim; Fallout 4 / Starfield write it
little-endian and the whole file follows), major u8, minor u8, game id u16, compile time u64, then source name, user
name and machine name, each a u16 length followed by that many bytes.

A .pex fails when:
  - its header does not parse (wrong magic, truncated)
  - the user name or machine name is non-empty (the neutral placeholders in NEUTRAL - build-papyrus.py's own words -
    are allowed, since they identify nobody)
  - any of the three fields equals or contains the local account or computer name
  - the source path runs through a user folder (X:\Users\<name>\, /home/<name>/, /Users/<name>/)
The message never prints the name itself - only which field and how long it is.

Usage:
  python pex-header-gate.py --path <package folder>     every .pex under it (package-gate also passes --repo; ignored)
  python pex-header-gate.py --file <one.pex>            a single file
Exit 0 pass, 1 any hit, 2 no such folder. Fix: rebuild the scripts and blank the header strings after compiling
(see NjordlingerCombatGameplayOverhaul\tools\build-papyrus.py scrub()), or patch the shipped .pex the same way.
"""
import argparse, os, re, sys

MAGIC = 0xFA57C0DE
# Words a scrubber may write instead of an empty field. They name nobody (build-papyrus.py writes "author" / "build").
NEUTRAL = {"", "author", "build"}
USER_FOLDER = re.compile(r"(?i)([A-Za-z]:)?[\\/]+(Users|home|Documents and Settings)[\\/]+[^\\/]+[\\/]")


def parse_header(data):
    """Return (endian, source, user, machine) as bytes, or raise ValueError."""
    if len(data) < 16:
        raise ValueError("file is shorter than a .pex header")
    if int.from_bytes(data[0:4], "big") == MAGIC:
        endian = "big"
    elif int.from_bytes(data[0:4], "little") == MAGIC:
        endian = "little"
    else:
        raise ValueError("no .pex magic (0xFA57C0DE) at the start")
    pos = 16                      # magic 4 + major 1 + minor 1 + game id 2 + compile time 8
    fields = []
    for name in ("source name", "user name", "machine name"):
        if pos + 2 > len(data):
            raise ValueError("header ends before the %s" % name)
        n = int.from_bytes(data[pos:pos + 2], endian)
        if pos + 2 + n > len(data):
            raise ValueError("the %s runs past the end of the file" % name)
        fields.append(data[pos + 2:pos + 2 + n])
        pos += 2 + n
    return (endian,) + tuple(fields)


def local_names():
    names = set()
    for var in ("USERNAME", "USER", "LOGNAME", "COMPUTERNAME", "HOSTNAME"):
        v = (os.environ.get(var) or "").strip()
        if len(v) >= 3:
            names.add(v.lower())
    try:
        import platform
        v = platform.node().strip()
        if len(v) >= 3:
            names.add(v.lower())
    except Exception:
        pass
    try:
        v = os.path.basename(os.path.expanduser("~")).strip()
        if len(v) >= 3:
            names.add(v.lower())
    except Exception:
        pass
    return names


def problems(data, locals_=None):
    """A list of messages (empty = pass). Never includes the identity text itself."""
    locals_ = local_names() if locals_ is None else {n.lower() for n in locals_ if len(n) >= 3}
    try:
        _, src, user, machine = parse_header(data)
    except ValueError as e:
        return ["header does not parse: %s" % e]
    out = []
    dec = lambda b: b.decode("latin-1")
    for label, raw in (("user name", user), ("machine name", machine)):
        if dec(raw).strip().lower() not in NEUTRAL:
            out.append("%s present (%d chars)" % (label, len(raw)))
    for label, raw in (("source path", src), ("user name", user), ("machine name", machine)):
        low = dec(raw).lower()
        if any(n in low for n in locals_):
            out.append("%s contains this machine's account or computer name" % label)
    if USER_FOLDER.search(dec(src)):
        out.append("source path runs through a user folder (%d chars)" % len(src))
    # one message per defect: a field reported both as present and as the local name keeps both lines (each is true)
    return out


def pex_under(folder):
    for root, _, files in os.walk(folder):
        for f in files:
            if f.lower().endswith(".pex"):
                full = os.path.join(root, f)
                yield os.path.relpath(full, folder), full


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path")
    ap.add_argument("--file")
    a, _ = ap.parse_known_args()   # package-gate also passes --repo
    if a.file:
        items = [(os.path.basename(a.file), a.file)]
    elif a.path and os.path.isdir(a.path):
        items = list(pex_under(a.path))
    else:
        print("FAIL  pex-header-gate  no such folder: %s" % a.path)   # a scan of nothing must never read as a pass
        sys.exit(2)
    if not items:
        print("pex-header-gate  note  no .pex in the package")
        sys.exit(0)
    names = local_names()
    hits = 0
    for rel, full in items:
        try:
            data = open(full, "rb").read()
        except OSError as e:
            print("FAIL  pex-header-gate  %s unreadable: %s" % (rel, e.__class__.__name__))
            hits += 1
            continue
        for msg in problems(data, names):
            print("FAIL  pex-header-gate  %s: %s" % (rel, msg))
            hits += 1
    if not hits:
        print("pex-header-gate  pass  %d .pex header(s) carry no user name, machine name or user folder" % len(items))
    sys.exit(1 if hits else 0)


if __name__ == "__main__":
    main()
