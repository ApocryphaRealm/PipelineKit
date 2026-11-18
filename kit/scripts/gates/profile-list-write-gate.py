r"""THE WHOLE-LIST RESTORE GATE (2026-10-27, pipeline assessment item 2). No tool writes a whole modlist.txt or
plugins.txt from a saved copy.

WHY: on 2026-10-27 a helper put back a whole modlist.txt taken before Item Explorer 1.2.0's folder existed; MO2 re-added
the folder unticked at the top and the posted build sat inactive in the Test profile (past-mistakes library, "Posted
versions of our mods sat unticked"). A saved list is older than the profile it lands in: every line anyone changed
since - an install, a tick, an owner's own edit - is lost without a word. Restores put back only the lines a test
changed (combined-run finish merges entry by entry; install-test-build records its lines).

Two places it refuses:
  hook mode (no arguments, a PreToolUse JSON on stdin, Bash / PowerShell): a shell command that copies or moves a file
      ONTO a modlist.txt / plugins.txt (cp, mv, copy, move, Copy-Item, Move-Item, robocopy, xcopy - the destination
      is the file, or an MO2 profiles\ folder with a list file as the source), that redirects or Set-Content's another
      file's text onto one, or an inline Python shutil.copy*/move / os.replace onto one. Exit 2 blocks the call.
  scan mode  --scan [FILE...] (default: every .py / .ps1 under the md-scripts role): the same in tool source - a Python
      shutil.copy / copy2 / copyfile / move or os.replace / os.rename whose DESTINATION names a modlist.txt or
      plugins.txt (a literal, or a variable assigned from one), and a PowerShell Copy-Item / Move-Item whose
      -Destination (or second positional) does. Exit 1 lists the offending lines. The .MD pre-commit hook runs it on
      every staged tool, and package-gate runs it on every package (gate-rules row
      no-whole-list-restore-in-pipeline-tools; '--path <package>' scans the pipeline's tools).
Copying a list OUT (a backup) passes: the destination is then another name (modlist.txt.bak-..., a backup folder).
KNOWN lists the tools that already did it on 2026-10-27, each with why; they are reported, not failed, and a new one
never joins the list by default. An owner-approved whole-list put-back says so in the command:
'# owner-approved-whole-list-restore: <his words>'.

    python profile-list-write-gate.py --scan [FILE...]      exit 0 clean, 1 offences
    python profile-list-write-gate.py --check-command "<command>"   exit 0 pass, 2 refused (the hook's test)
"""
import ast, json, os, re, shlex, sys, warnings

warnings.filterwarnings("ignore", category=SyntaxWarning)    # ast.parse of other tools' sources

LIST =re.compile(r"(?<![\w.-])(modlist|plugins)\.txt(?![\w.-])", re.I)
BACKUP = re.compile(r"backup|\bbak\b|\.bak|snapshot|saved|batches|_work", re.I)   # a destination that IS the saved copy
OWNER_OK = re.compile(r"owner-approved-whole-list-restore:\s*\S", re.I)
KNOWN = {
    "bisect-profile.ps1": "bisect puts back its own pre-bisect snapshot of modlist.txt / plugins.txt at the end - "
                          "follow-up: make it line-level like combined-run finish",
    "nj-apostasy-layout.py": "a one-off build tool that writes a GENERATED proposed order, not a saved copy",
}
MSG = ("REFUSED by profile-list-write-gate: this writes a WHOLE %s from another file. A saved list is older than the "
       "profile it lands in and silently undoes every line changed since (Item Explorer 1.2.0 sat unticked, "
       "2026-10-27). Put back only the lines the test changed: combined-run finish (merges entry by entry), or edit the "
       "lines as bytes (detect the newline, split, write back). An owner-approved whole-list put-back says so in the "
       "command: '# owner-approved-whole-list-restore: <his words>'.")


# ------------------------------------------------------------------------------------------------ shell commands
COPY_VERBS = {"cp", "mv", "copy", "move", "copy-item", "move-item", "cpi", "mi", "robocopy", "xcopy", "install"}
WRITE_VERBS = {"set-content", "out-file", "sc", "add-content"}
READ_VERBS = {"cat", "type", "get-content", "gc"}


def _split_statements(cmd):
    return [s.strip() for s in re.split(r"\r?\n|;|&&|\|\|", cmd) if s.strip()]


def _tokens(stmt):
    try:
        return shlex.split(stmt.replace("\\", "/"), posix=True)
    except ValueError:
        return stmt.replace("\\", "/").split()


def _is_list(path):
    return bool(LIST.search(os.path.basename(path.strip("\"'").rstrip("/")) or ""))


def _into_backup(dest):
    """A copy whose destination is a backup / snapshot place is a copy OUT of the profile, which passes."""
    return bool(BACKUP.search(dest or ""))


def _named_list(text):
    m = LIST.search(text or "")
    return m.group(0) if m else None


def check_command(cmd):
    """The list file a shell command would overwrite from a saved copy, or None."""
    if not cmd or not LIST.search(cmd) or OWNER_OK.search(cmd):
        return None
    # inline Python: shutil.copy*/move or os.replace/rename onto a list file
    for m in re.finditer(r"(shutil\.(copy2?|copyfile|move)|os\.(replace|rename))\s*\(([^()]*(\([^()]*\))?[^()]*)\)", cmd):
        args = m.group(4).split(",")
        if len(args) >= 2 and _named_list(",".join(args[1:])):
            return _named_list(",".join(args[1:]))
    for stmt in _split_statements(cmd):
        pipe = [p.strip() for p in stmt.split("|")]
        # a read of one file piped into a write of a list file: Get-Content A | Set-Content B\modlist.txt
        if len(pipe) > 1:
            first = _tokens(pipe[0])
            last = _tokens(pipe[-1])
            if first and last and first[0].lower() in READ_VERBS and last[0].lower() in WRITE_VERBS:
                dst = [t for t in last[1:] if not t.startswith("-")]
                src = [t for t in first[1:] if not t.startswith("-")]
                if dst and _is_list(dst[0]) and src and os.path.normcase(src[0]) != os.path.normcase(dst[0]):
                    return os.path.basename(dst[0])
        toks = _tokens(pipe[0])
        if not toks:
            continue
        verb = toks[0].lower()
        # a redirect of another file onto a list file: cat backup/modlist.txt > profiles/X/modlist.txt
        if verb in READ_VERBS:
            m = re.search(r">\s*([\"']?)([^\"'>\s]+)\1\s*$", stmt)
            if m and _is_list(m.group(2)):
                srcs = [t for t in toks[1:] if not t.startswith("-") and ">" not in t and t.strip("\"'") != m.group(2)]
                if srcs:
                    return os.path.basename(m.group(2))
        if verb not in COPY_VERBS:
            continue
        args, dest = [], None
        i = 1
        while i < len(toks):
            t = toks[i]
            if t.lower() in ("-destination", "-dest"):
                dest = toks[i + 1] if i + 1 < len(toks) else None
                i += 2
                continue
            if t.lower() in ("-path", "-literalpath"):
                if i + 1 < len(toks):
                    args.append(toks[i + 1])
                i += 2
                continue
            if t.startswith("-") or (verb in ("robocopy", "xcopy") and t.startswith("/") and len(t) <= 6):
                i += 1
                continue
            args.append(t)
            i += 1
        if dest is None and len(args) >= 2:
            dest, args = args[-1], args[:-1]
        if verb == "robocopy" and len(args) >= 1 and dest is not None:
            # robocopy <src dir> <dst dir> <file>...: a list file named among the files, into a profiles folder
            files = args[1:] if len(args) > 1 else []
            if any(_is_list(f) for f in files) and "/profiles" in ("/" + dest.lower().replace("\\", "/")):
                return next(os.path.basename(f) for f in files if _is_list(f))
            continue
        if not dest:
            continue
        if _into_backup(dest):
            continue
        if _is_list(dest):
            return os.path.basename(dest.strip("\"'"))
        if "profiles/" in dest.lower().replace("\\", "/") + "/" and any(_is_list(s) for s in args):
            return next(os.path.basename(s) for s in args if _is_list(s))
    return None


def hook():
    try:
        data = json.load(sys.stdin)
    except Exception:                                  # noqa: BLE001 - a hook never breaks the tool on bad input
        return 0
    if data.get("tool_name") not in ("Bash", "PowerShell"):
        return 0
    hit = check_command((data.get("tool_input") or {}).get("command") or "")
    if hit:
        sys.stderr.write(MSG % hit + "\n")
        return 2
    return 0


# ------------------------------------------------------------------------------------------------ tool source
def _py_offences(path, src):
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    names = {}
    for node in ast.walk(tree):                      # NAME = <expression naming a list file>
        if isinstance(node, ast.Assign):
            seg = ast.get_source_segment(src, node.value) or ""
            if _named_list(seg):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        names[t.id] = seg
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or len(node.args) < 2:
            continue
        f = node.func
        fname = ("%s.%s" % (f.value.id, f.attr)) if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) else ""
        if fname not in ("shutil.copy", "shutil.copy2", "shutil.copyfile", "shutil.move", "os.replace", "os.rename"):
            continue
        dst = node.args[1]
        seg = ast.get_source_segment(src, dst) or ""
        if _into_backup(seg) or (isinstance(dst, ast.Name) and _into_backup(names.get(dst.id, ""))):
            continue
        if _named_list(seg) or (isinstance(dst, ast.Name) and dst.id in names):
            # a temp file of the tool's own being renamed over the list (write-then-replace) is the line-level path
            srcseg = ast.get_source_segment(src, node.args[0]) or ""
            if fname in ("os.replace", "os.rename") and re.search(r"tmp|temp", srcseg, re.I):
                continue
            out.append((node.lineno, (src.splitlines()[node.lineno - 1]).strip()))
    return out


def _ps_offences(path, src):
    code = re.sub(r"<#.*?#>", lambda m: "\n" * m.group(0).count("\n"), src, flags=re.S)
    lines = code.splitlines()
    names = {}
    for ln in lines:
        s = ln.split("#", 1)[0]
        m = re.match(r"\s*\$(\w+)\s*=\s*(.+)$", s)
        if m and _named_list(m.group(2)):
            names[m.group(1).lower()] = m.group(2)
    out = []
    for no, ln in enumerate(lines, 1):
        s = ln.split("#", 1)[0]
        for m in re.finditer(r"\b(Copy-Item|Move-Item)\b(.*?)(?=;|\}|$|\|)", s, re.I):
            rest = m.group(2)
            d = re.search(r"-Destination\s+(\([^)]*\)|\"[^\"]*\"|'[^']*'|\S+)", rest, re.I)
            dest = d.group(1) if d else None
            if dest is None:
                pos = [t for t in re.findall(r"(\([^)]*\)|\"[^\"]*\"|'[^']*'|\S+)", rest) if not t.startswith("-")]
                dest = pos[1] if len(pos) >= 2 else None
            if not dest:
                continue
            v = re.fullmatch(r"\$(\w+)", dest.strip())
            if _into_backup(dest) or (v and _into_backup(names.get(v.group(1).lower(), ""))):
                continue
            if _named_list(dest) or (v and v.group(1).lower() in names):
                out.append((no, ln.strip()))
    return out


def scan(files):
    found, known = [], []
    for p in files:
        try:
            with open(p, encoding="utf-8-sig", errors="replace") as f:
                src = f.read()
        except OSError:
            continue
        if os.path.basename(p) == os.path.basename(__file__) or "\\tests\\" in p or "/tests/" in p:
            continue
        hits = _py_offences(p, src) if p.lower().endswith(".py") else _ps_offences(p, src) if p.lower().endswith(".ps1") else []
        if OWNER_OK.search(src):
            hits = []
        for no, text in hits:
            (known if os.path.basename(p) in KNOWN else found).append((p, no, text))
    return found, known


def default_files():
    root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    out = []
    for d, _, fs in os.walk(root):
        if "__pycache__" in d or os.sep + "tests" in d:
            continue
        out += [os.path.join(d, f) for f in fs if f.lower().endswith((".py", ".ps1"))]
    return sorted(out)


def main(argv):
    if not argv:
        return hook()
    if argv[0] == "--check-command":
        hit = check_command(" ".join(argv[1:]))
        print((MSG % hit) if hit else "profile-list-write-gate: PASS")
        return 2 if hit else 0
    if argv[0] == "--path":                          # package-gate's 'package-script-passes' call: scan the pipeline's tools
        argv = ["--scan"]
    if argv[0] == "--scan":
        files = [os.path.abspath(f) for f in argv[1:]] or default_files()
        found, known = scan(files)
        for p, no, text in known:
            print("KNOWN %s:%d  %s  (%s)" % (p, no, text[:140], KNOWN[os.path.basename(p)]))
        for p, no, text in found:
            print("FAIL  %s:%d  %s" % (p, no, text[:160]))
        if found:
            print("profile-list-write-gate: FAIL - %d whole-list write(s) from a saved copy. %s" % (
                len(found), "Write back only the changed lines (bytes, same newline)."))
            return 1
        print("profile-list-write-gate: PASS - %d file(s) scanned, no new whole-list write (%d known)" % (len(files), len(known)))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:                                  # noqa: BLE001
        pass
    sys.exit(main(sys.argv[1:]))
