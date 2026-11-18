r"""ini-edit - change INI keys without changing anything else in the file (role ini-edit, 2026-10-23).

Why: in the 2026-10-23 combined run a Git Bash `sed -i` on Dynamic Terrain Deformation's INI turned its CRLF line ends
into LF (the file had to be restored from a backup). This edits one key at a time and keeps the rest byte for byte:
the line ends (CRLF or LF, as the file has them), the encoding and its BOM (UTF-8, UTF-8 with BOM, UTF-16 LE/BE, or
ANSI), comments, blank lines, the spacing around '=' on a line it rewrites, and whether the file ends in a newline.

  ini-edit.py FILE --set "Section:Key=Value" [--set ...] [--delete "Section:Key"] [--backup] [--dry-run]
  ini-edit.py FILE --get "Section:Key"

Sections and keys match case-insensitively. --set changes the key's first line in that section, or adds the key at
the end of the section (after its last key, before trailing blank lines), or adds the section at the end of the file.
A file with NO [sections] keeps its keys in the empty section: write ":Key=Value" / ":Key". Naming a section on such a
file is refused (exit 2) instead of appending a new section the file never had.
"Section:Key" splits on the FIRST colon, so a key may hold one (Skyrim's "fAutoVanityModeDelay:Camera" is section
Camera, key fAutoVanityModeDelay: write it "Camera:fAutoVanityModeDelay"). --backup copies the file to
FILE.bak-<yyyymmdd-hhmmss> first. --dry-run prints what would change and writes nothing.

Exit codes: 0 done (or --get found it), 1 --get found nothing / the file could not be read, 2 usage.
As a module (combined-run imports it): read_ini, write_ini, get_value, set_value, delete_key, keys.
"""
import argparse, codecs, datetime, os, re, shutil, sys

_SECTION = re.compile(r"^\s*\[([^\]]*)\]")
_KEY = re.compile(r"^(\s*)([^=;#\[\s][^=]*?)(\s*)=(\s*)(.*?)(\s*)$")


# ---- reading and writing, byte-faithful -------------------------------------------------------------------------------
def read_ini(path):
    """(lines without their line ends, meta) - meta holds what write_ini needs to give the file back unchanged."""
    with open(path, "rb") as f:
        raw = f.read()
    if raw.startswith(codecs.BOM_UTF16_LE):
        enc, bom = "utf-16-le", codecs.BOM_UTF16_LE
    elif raw.startswith(codecs.BOM_UTF16_BE):
        enc, bom = "utf-16-be", codecs.BOM_UTF16_BE
    elif raw.startswith(codecs.BOM_UTF8):
        enc, bom = "utf-8", codecs.BOM_UTF8
    else:
        enc, bom = "utf-8", b""
    body = raw[len(bom):]
    try:
        text = body.decode(enc)
    except UnicodeDecodeError:
        enc = "cp1252"                                  # an ANSI INI (Skyrim's own are)
        text = body.decode(enc, errors="surrogateescape")
    crlf, lf = text.count("\r\n"), text.count("\n") - text.count("\r\n")
    newline = "\r\n" if crlf >= lf and crlf else "\n"
    final = text.endswith("\n")
    lines = text.split("\n")
    if final:
        lines.pop()
    # each line keeps no line end; a lone '\r' left by CRLF is the line end, not content
    lines = [ln[:-1] if ln.endswith("\r") else ln for ln in lines]
    return lines, {"encoding": enc, "bom": bom, "newline": newline, "final_newline": final}


def render(lines, meta):
    text = meta["newline"].join(lines) + (meta["newline"] if meta["final_newline"] and lines else "")
    errors = "surrogateescape" if meta["encoding"] == "cp1252" else "strict"
    return meta["bom"] + text.encode(meta["encoding"], errors=errors)


def write_ini(path, lines, meta):
    data = render(lines, meta)
    tmp = path + ".ini-edit-tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


# ---- the model: which line is which section / key ---------------------------------------------------------------------
def split_spec(spec):
    """'Section:Key' -> (section, key); split on the first colon."""
    if ":" not in spec:
        raise ValueError("'%s' is not Section:Key" % spec)
    sec, key = spec.split(":", 1)
    if not key.strip():
        raise ValueError("'%s' has no key" % spec)
    return sec.strip(), key.strip()


def _scan(lines):
    """[(index, section_lower, key_lower_or_None)] for every line; the lines before any [section] are section ''."""
    out, sec = [], ""
    for i, ln in enumerate(lines):
        m = _SECTION.match(ln)
        if m:
            sec = m.group(1).strip().lower()
            out.append((i, sec, None))
            continue
        k = _KEY.match(ln)
        out.append((i, sec, k.group(2).strip().lower() if k and not ln.lstrip().startswith((";", "#")) else None))
    return out


def keys(lines):
    """{(section_lower, key_lower): value} - the first line of each key wins, as the game reads it."""
    out = {}
    for i, sec, key in _scan(lines):
        if key is not None and (sec, key) not in out:
            out[(sec, key)] = _KEY.match(lines[i]).group(5)
    return out


def check_section(lines, section):
    """A SECTIONLESS file (keys only, no [header] - e.g. some SKSE plugins' INIs) holds its keys in section ''. A named
    section there would not be the key the caller means: --set appended a new [Section] at the end and left the real key
    alone, and --get answered "not found" (combined run 2026-10-24). Raises ValueError saying to write ':Key'."""
    if section.strip() and not any(_SECTION.match(ln) for ln in lines) and any(k for _, _, k in _scan(lines)):
        raise ValueError("this file has no [sections] - its keys are written ':Key' (an empty section), not '%s:Key'"
                         % section.strip())


def get_value(lines, section, key):
    return keys(lines).get((section.strip().lower(), key.strip().lower()))


def set_value(lines, section, key, value):
    """Set section:key = value in place; returns (new lines, 'changed' | 'unchanged' | 'added' | 'added-section')."""
    sl, kl = section.strip().lower(), key.strip().lower()
    scan = _scan(lines)
    for i, sec, k in scan:
        if sec == sl and k == kl:
            m = _KEY.match(lines[i])
            if m.group(5) == value:
                return lines, "unchanged"
            new = "%s%s%s=%s%s%s" % (m.group(1), m.group(2), m.group(3), m.group(4), value, m.group(6))
            return lines[:i] + [new] + lines[i + 1:], "changed"
    check_section(lines, section)   # never a new [Section] at the end of a sectionless file
    in_sec = [i for i, sec, k in scan if sec == sl]
    header = [i for i, sec, k in scan if sec == sl and k is None and _SECTION.match(lines[i])]
    if in_sec and (header or sl == ""):
        last_key = max([i for i, sec, k in scan if sec == sl and k is not None] or [header[0] if header else -1])
        at = last_key + 1
        return lines[:at] + ["%s=%s" % (key, value)] + lines[at:], "added"
    tail = list(lines)
    if tail and tail[-1].strip():
        tail.append("")
    return tail + ["[%s]" % section, "%s=%s" % (key, value)], "added-section"


def delete_key(lines, section, key):
    sl, kl = section.strip().lower(), key.strip().lower()
    for i, sec, k in _scan(lines):
        if sec == sl and k == kl:
            return lines[:i] + lines[i + 1:], "deleted"
    return lines, "absent"


# ---- command line -----------------------------------------------------------------------------------------------------
def main(argv):
    p = argparse.ArgumentParser(prog="ini-edit", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("file")
    p.add_argument("--set", action="append", default=[], metavar="SECTION:KEY=VALUE")
    p.add_argument("--delete", action="append", default=[], metavar="SECTION:KEY")
    p.add_argument("--get", metavar="SECTION:KEY")
    p.add_argument("--backup", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    try:
        a = p.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    if not (a.set or a.delete or a.get):
        print("ini-edit: nothing to do - give --set, --delete or --get")
        return 2
    try:
        lines, meta = read_ini(a.file)
    except OSError as e:
        print("ini-edit: cannot read %s: %s" % (a.file, e))
        return 1
    try:
        for spec in [a.get] * bool(a.get) + [s.split("=", 1)[0] for s in a.set] + a.delete:
            check_section(lines, split_spec(spec)[0])
        if a.get:
            v = get_value(lines, *split_spec(a.get))
            print("" if v is None else v)
            return 0 if v is not None else 1
        report = []
        for spec in a.set:
            if "=" not in spec:
                print("ini-edit: --set '%s' is not Section:Key=Value" % spec)
                return 2
            target, value = spec.split("=", 1)
            sec, key = split_spec(target)
            old = get_value(lines, sec, key)
            lines, what = set_value(lines, sec, key, value)
            report.append("  [%s] %s: %s (%s -> %s)" % (sec, key, what, "absent" if old is None else old, value))
        for spec in a.delete:
            sec, key = split_spec(spec)
            lines, what = delete_key(lines, sec, key)
            report.append("  [%s] %s: %s" % (sec, key, what))
    except ValueError as e:
        print("ini-edit: %s" % e)
        return 2
    ends = "CRLF" if meta["newline"] == "\r\n" else "LF"
    if a.dry_run:
        print("ini-edit: DRY RUN on %s (%s, %s line ends) - nothing written\n%s" % (a.file, meta["encoding"], ends,
                                                                                  "\n".join(report)))
        return 0
    if a.backup:
        bak = "%s.bak-%s" % (a.file, datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
        shutil.copy2(a.file, bak)
        report.append("  backup: " + bak)
    write_ini(a.file, lines, meta)
    print("ini-edit: wrote %s (%s, %s line ends kept)\n%s" % (a.file, meta["encoding"], ends, "\n".join(report)))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:                                    # noqa: BLE001
        pass
    sys.exit(main(sys.argv[1:]))
