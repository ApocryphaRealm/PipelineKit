#!/usr/bin/env python3
"""resolve.py - resolve a ROLE (a name in a roster) to a path on disk.

Commands: find, list, place, identify, explain, check [--callers | --schema NAME [--file PATH]], run,
distro <sub> (the distro / package-folder names that distro-names.ps1 used to compute - step 2.3; see cmd_distro).
Standard library only. See the roster contract in the pipeline-restructure plan (step 1.4).
"""
import datetime
import glob
import json
import os
import re
import subprocess
import sys
import zipfile

# resolve.py -> resolvers -> .MD -> ROOT: a copied resolver answers inside its own tree (for the real file: <ROOT>)
DEFAULT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROLE_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
TOKEN_RE = re.compile(r"\{([^{}\\]*)\}")
VAR_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
# copied character for character from distro-names.ps1 ($script:PackageNameRe); (?<n>) becomes (?P<n>)
PACKAGE_RE = re.compile(
    r"^(?P<mod>.+?)(?P<sym> - Debug Symbols)? (?P<ver>\d+\.\d+\.\d+)"
    r"(?P<tail>(?:-[A-Za-z0-9]+)?(?: FOMOD)?(?: - [^\\/]+?)?)(?P<ext>\.zip|\.7z)?$"
)
MAX_DEPTH = 8
KINDS = ("file", "dir", "place", "set", "value")


class RoleError(Exception):
    def __init__(self, role):
        Exception.__init__(self, role)
        self.role = role


class ExpandError(Exception):
    pass


def out(text=""):
    sys.stdout.write(text + "\n")


def err(text=""):
    sys.stderr.write(text + "\n")


class Rosters(object):
    def __init__(self, folder):
        self.folder = folder
        self.roles = {}
        self.origin = {}
        self.duplicates = []
        self.files = []
        if os.path.isdir(folder):
            for fn in sorted(os.listdir(folder)):
                if not fn.lower().endswith(".json"):
                    continue
                with open(os.path.join(folder, fn), "r", encoding="utf-8-sig") as fh:
                    data = json.load(fh)
                self.files.append(fn)
                for name, body in (data.get("roles") or {}).items():
                    if name in self.roles:
                        self.duplicates.append((name, self.origin[name], fn))
                        continue
                    self.roles[name] = body
                    self.origin[name] = fn

    def effective(self, name):
        """Follow 'retired' links. Returns (final_name, [retired names passed])."""
        seen = []
        cur = name
        while True:
            if cur not in self.roles:
                raise RoleError(cur)
            body = self.roles[cur]
            tgt = body.get("retired")
            if not tgt:
                return cur, seen
            if cur in seen:
                raise ExpandError("retired cycle at %s" % cur)
            seen.append(cur)
            cur = tgt

    def raw(self, name):
        final, _ = self.effective(name)
        body = self.roles[final]
        if body.get("kind") == "value":
            return body.get("value")
        return body.get("at") if body.get("at") is not None else body.get("find")


def expand(rosters, name, variables, root, home):
    """Return (final_text, steps). Substitutes until nothing changes (max depth 8)."""
    text = rosters.raw(name)
    if text is None:
        raise ExpandError("role %s has no 'at' or 'find'" % name)
    if rosters.roles[rosters.effective(name)[0]].get("kind") == "value":
        return text, []   # a value is a fact, not a path: no substitution, no separator change
    steps = []

    def repl(m):
        tok = m.group(1)
        if tok == "root":
            return root
        if tok == "home":
            return home
        if tok.startswith("role:"):
            sub = tok[5:]
            if sub in rosters.roles and rosters.roles[rosters.effective(sub)[0]].get("kind") == "value":
                raise ExpandError("value role used as a path: {role:%s}" % sub)
            r = rosters.raw(sub)
            if r is None:
                raise ExpandError("role %s has no 'at' or 'find'" % sub)
            return r
        if tok in variables:
            return variables[tok]
        return m.group(0)

    for _ in range(MAX_DEPTH):
        new = TOKEN_RE.sub(repl, text)
        if new == text:
            break
        steps.append(new)
        text = new
    else:
        new = TOKEN_RE.sub(repl, text)
        if new != text:
            raise ExpandError("substitution deeper than %d passes (cycle?) in %s" % (MAX_DEPTH, name))
    return text.replace("/", "\\"), steps


def leftover_vars(text):
    return [m.group(1) for m in TOKEN_RE.finditer(text)]


class Ctx(object):
    def __init__(self, rosters, root, variables):
        self.rosters = rosters
        self.root = root
        self.home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
        self.vars = variables

    def resolve(self, name):
        return expand(self.rosters, name, self.vars, self.root, self.home)


def parse_args(argv):
    opts = {"rosters": None, "root": DEFAULT_ROOT, "var": {}, "callers": False, "schema": None, "file": None}
    pos = []
    i = 0
    passthrough = None
    while i < len(argv):
        a = argv[i]
        if a in ("--rosters", "--root") and i + 1 < len(argv):
            opts[a[2:]] = argv[i + 1]
            i += 2
        elif a == "--schema" and i + 1 < len(argv):
            opts["schema"] = argv[i + 1]
            i += 2
        elif a in ("--file", "--rules-file") and i + 1 < len(argv):
            opts["file"] = argv[i + 1]
            i += 2
        elif a == "--var" and i + 1 < len(argv):
            k, _, v = argv[i + 1].partition("=")
            opts["var"][k] = v
            i += 2
        elif a == "--callers":
            opts["callers"] = True
            i += 1
        else:
            pos.append(a)
            i += 1
            if len(pos) == 2 and pos[0] == "run":
                passthrough = argv[i:]
                break
            if len(pos) == 1 and pos[0] == "distro":
                passthrough = argv[i:]
                break
    if passthrough is not None:
        pos.extend(passthrough)
    return opts, pos


def cmd_find(ctx, role):
    try:
        final, retired = ctx.rosters.effective(role)
        body = ctx.rosters.roles[final]
        path, _ = ctx.resolve(role)
    except RoleError as e:
        out("NO SUCH ROLE %s" % e.role)
        return 2
    except ExpandError as e:
        out("ERROR %s" % e)
        return 2
    if body.get("kind") == "value":
        if retired:
            err("RETIRED %s -> %s" % (retired[0], final))
        out(path)
        return 0
    if body.get("kind") in ("set", "place"):
        out("%s is a %s - use %s" % (role, body.get("kind"), "list" if body.get("kind") == "set" else "place"))
        return 4
    if retired:
        err("RETIRED %s -> %s" % (retired[0], final))
    left = leftover_vars(path)
    if left:
        out("UNFILLED %s" % left[0])
        return 1
    if os.path.exists(path):
        out(path)
        return 0
    out("MISSING %s -> %s" % (role, path))
    return 1


def cmd_list(ctx, role):
    try:
        final, retired = ctx.rosters.effective(role)
        body = ctx.rosters.roles[final]
        pattern, _ = ctx.resolve(role)
    except RoleError as e:
        out("NO SUCH ROLE %s" % e.role)
        return 2
    except ExpandError as e:
        out("ERROR %s" % e)
        return 2
    if body.get("kind") != "set":
        out("%s is not a set - use find or place" % role)
        return 4
    if retired:
        err("RETIRED %s -> %s" % (retired[0], final))
    members = sorted(glob.glob(pattern))
    if not members:
        out("EMPTY %s" % role)
        return 1
    for m in members:
        out(m)
    return 0


def cmd_place(ctx, role):
    try:
        final, retired = ctx.rosters.effective(role)
        path, _ = ctx.resolve(role)
    except RoleError as e:
        out("NO SUCH ROLE %s" % e.role)
        return 2
    except ExpandError as e:
        out("ERROR %s" % e)
        return 2
    if ctx.rosters.roles[final].get("kind") == "value":
        out("%s is a value - use find" % role)
        return 4
    if retired:
        err("RETIRED %s -> %s" % (retired[0], final))
    left = leftover_vars(path)
    if left:
        out("UNFILLED %s" % left[0])
        return 1
    out(path)
    return 0


def cmd_identify(ctx, path):
    ros = ctx.rosters
    target = path.replace("/", "\\")
    low = target.lower()
    best = None
    best_len = -1
    for name, body in ros.roles.items():
        if not name.startswith("stage-") or body.get("kind") != "dir" or body.get("retired"):
            continue
        try:
            sp, _ = ctx.resolve(name)
        except (RoleError, ExpandError):
            continue
        s = sp.rstrip("\\")
        sl = s.lower()
        if low == sl or low.startswith(sl + "\\"):
            if len(s) > best_len:
                best, best_len = name, len(s)
    if best is None:
        out("UNRECOGNISED")
        return 1
    rest = target[best_len:].lstrip("\\")
    segs = [x for x in rest.split("\\") if x]
    if len(segs) < 2:
        out("UNRECOGNISED")
        return 1
    middle, leaf = segs[0], segs[1]
    m = PACKAGE_RE.match(leaf)
    if not m:
        out("UNRECOGNISED")
        return 1
    game = middle.split(" - ", 1)[0] if " - " in middle else None
    out(json.dumps({"stage": best, "game": game, "mod": m.group("mod"),
                    "version": m.group("ver"), "tail": m.group("tail")}, ensure_ascii=False))
    return 0


def cmd_explain(ctx, role):
    ros = ctx.rosters
    try:
        final, retired = ros.effective(role)
    except RoleError as e:
        out("NO SUCH ROLE %s" % e.role)
        return 2
    except ExpandError as e:
        out("ERROR %s" % e)
        return 2
    body = ros.roles[final]
    try:
        path, steps = ctx.resolve(role)
    except RoleError as e:
        out("NO SUCH ROLE %s" % e.role)
        return 2
    except ExpandError as e:
        out("ERROR %s" % e)
        return 2
    lines = ["roster: %s" % ros.origin[final]]
    kind = body.get("kind")
    lines.append("kind: %s" % kind + (" (retired alias %s -> %s)" % (retired[0], final) if retired else ""))
    lines.append("raw: %s" % ros.raw(role))
    for s in steps:
        lines.append("subst: %s" % s)
    if body.get("note"):
        lines.append("note: %s" % body["note"])
    if kind == "value":
        lines.append("result: %s" % path)
        out("\n".join(lines))
        return 0
    if kind == "set":
        exists = bool(glob.glob(path))
    elif leftover_vars(path):
        exists = False
    else:
        exists = os.path.exists(path)
    lines.append("result: %s exists: %s" % (path, "yes" if exists else "no"))
    out("\n".join(lines))
    return 0


def scan_targets(ctx):
    md = os.path.join(ctx.root, ".MD")
    home = ctx.home
    patterns = [
        (os.path.join(md, "scripts", "**", "*.ps1"), True),
        (os.path.join(md, "scripts", "**", "*.py"), True),
        (os.path.join(md, "watcher", "**", "*.ps1"), True),
        (os.path.join(md, "watcher", "**", "*.py"), True),
        (os.path.join(md, "*.md"), False),
        (os.path.join(md, "rules", "*.md"), False),
        (os.path.join(home, ".claude", "skills", "**", "*.md"), True),
        (os.path.join(home, ".claude", "projects", re.sub(r"[^A-Za-z0-9]", "-", ctx.root), "memory", "*.md"), False),
        (os.path.join(home, ".claude", "settings.json"), False),
    ]
    seen = set()
    for pat, rec in patterns:
        for f in glob.glob(pat, recursive=rec):
            key = os.path.normcase(os.path.abspath(f))
            if key in seen or not os.path.isfile(f):
                continue
            seen.add(key)
            yield f


SCHEMA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema")
SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")


class _LineParser(object):
    """Parses JSON text into a value plus a map path -> (value line, key line)."""

    def __init__(self, text):
        self.t = text
        self.i = 0
        self.starts = [0] + [m.end() for m in re.finditer("\n", text)]
        self.lm = {}
        self.dec = json.JSONDecoder()

    def line(self, idx):
        lo, hi = 0, len(self.starts)
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if self.starts[mid] <= idx:
                lo = mid
            else:
                hi = mid
        return lo + 1

    def ws(self):
        while self.i < len(self.t) and self.t[self.i] in " \t\r\n":
            self.i += 1

    def value(self, path, keyline):
        self.ws()
        vline = self.line(self.i)
        self.lm[path] = (vline, keyline if keyline else vline)
        c = self.t[self.i:self.i + 1]
        if c == "{":
            self.i += 1
            obj = {}
            self.ws()
            if self.t[self.i:self.i + 1] == "}":
                self.i += 1
                return obj
            while True:
                self.ws()
                kline = self.line(self.i)
                key, self.i = self.dec.raw_decode(self.t, self.i)
                self.ws()
                if self.t[self.i:self.i + 1] != ":":
                    raise ValueError("expected ':' at line %d" % self.line(self.i))
                self.i += 1
                obj[key] = self.value(path + (key,), kline)
                self.ws()
                c2 = self.t[self.i:self.i + 1]
                self.i += 1
                if c2 == "}":
                    return obj
                if c2 != ",":
                    raise ValueError("expected ',' or '}' at line %d" % self.line(self.i - 1))
        if c == "[":
            self.i += 1
            arr = []
            self.ws()
            if self.t[self.i:self.i + 1] == "]":
                self.i += 1
                return arr
            while True:
                arr.append(self.value(path + (len(arr),), None))
                self.ws()
                c2 = self.t[self.i:self.i + 1]
                self.i += 1
                if c2 == "]":
                    return arr
                if c2 != ",":
                    raise ValueError("expected ',' or ']' at line %d" % self.line(self.i - 1))
        val, self.i = self.dec.raw_decode(self.t, self.i)
        return val


def load_with_lines(fpath):
    with open(fpath, "rb") as fh:
        text = fh.read().decode("utf-8-sig")
    p = _LineParser(text)
    val = p.value((), None)
    return val, p.lm


def _type_ok(v, t):
    if t == "object":
        return isinstance(v, dict)
    if t == "array":
        return isinstance(v, list)
    if t == "string":
        return isinstance(v, str)
    if t == "boolean":
        return isinstance(v, bool)
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    if t == "null":
        return v is None
    return False


def _show(path):
    s = "$"
    for p in path:
        s += "[%d]" % p if isinstance(p, int) else ".%s" % p
    return s


def validate(val, schema, path, errs):
    """Small schema dialect: type (name or list), required, properties, additionalProperties
    (default false; a schema applies to every unlisted key), enum, pattern, items."""
    t = schema.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        if not any(_type_ok(val, x) for x in types):
            errs.append((path, "expected %s, found %s" % ("/".join(types), type(val).__name__)))
            return
    if "enum" in schema and val not in schema["enum"]:
        errs.append((path, "%r is not one of: %s" % (val, ", ".join(str(x) for x in schema["enum"]))))
    if "pattern" in schema and isinstance(val, str) and not re.search(schema["pattern"], val):
        errs.append((path, "%r does not match pattern %s" % (val, schema["pattern"])))
    if isinstance(val, dict):
        for k in schema.get("required", []):
            if k not in val:
                errs.append((path, "missing required key '%s'" % k))
        props = schema.get("properties", {})
        extra = schema.get("additionalProperties", False)
        for k, v in val.items():
            if k in props:
                validate(v, props[k], path + (k,), errs)
            elif isinstance(extra, dict):
                validate(v, extra, path + (k,), errs)
            elif extra is not True:
                errs.append((path + (k,), "unknown key '%s'" % k))
    if isinstance(val, list) and "items" in schema:
        for n, item in enumerate(val):
            validate(item, schema["items"], path + (n,), errs)


def _err_line(val, lm, path):
    """Line of the nearest enclosing "id" (an object that has one), else of the nearest key."""
    for depth in range(len(path), -1, -1):
        sub = path[:depth]
        node = val
        for p in sub:
            node = node[p]
        if isinstance(node, dict) and isinstance(node.get("id"), str) and sub + ("id",) in lm:
            return lm[sub + ("id",)][1]
    for depth in range(len(path), -1, -1):
        sub = path[:depth]
        if sub in lm:
            return lm[sub][1]
    return 1


def schema_check_file(fpath, schema_name, label=None):
    """Returns a list of 'SCHEMA <file>:<line> <path>: <message>' strings."""
    label = label or os.path.basename(fpath)
    sp = os.path.join(SCHEMA_DIR, schema_name + ".json")
    if not os.path.isfile(sp):
        return ["SCHEMA %s:1 $: no schema file %s" % (label, sp)]
    with open(sp, "rb") as fh:
        schema = json.loads(fh.read().decode("utf-8-sig"))
    try:
        val, lm = load_with_lines(fpath)
    except (ValueError, OSError) as e:
        return ["SCHEMA %s:1 $: cannot parse (%s)" % (label, e)]
    errs = []
    validate(val, schema, (), errs)
    return ["SCHEMA %s:%d %s: %s" % (label, _err_line(val, lm, p), _show(p), m) for p, m in errs]


def cmd_schema(ctx, name, file_override):
    if not re.match(r"^[a-z0-9][a-z0-9-]*$", name or "") or not os.path.isfile(os.path.join(SCHEMA_DIR, name + ".json")):
        out("ERROR no schema named %s" % name)
        return 2
    lines = []
    if name == "roster":
        for fn in ctx.rosters.files:
            lines.extend(schema_check_file(os.path.join(ctx.rosters.folder, fn), name))
    else:
        target = file_override or os.path.join(SCRIPTS_DIR, name + ".json")
        if not os.path.isfile(target):
            out("ERROR no data file %s" % target)
            return 2
        lines.extend(schema_check_file(target, name))
    if lines:
        out("\n".join(lines))
        return 1
    out("OK")
    return 0


CALL_RE = re.compile(r"resolve\.(?:py|ps1)[\"']?\s+(?:find|list|place|explain|run)\s+[\"']?([a-z0-9][a-z0-9-]*)")
ROLETOK_RE = re.compile(r"\{role:([a-z0-9][a-z0-9-]*)\}")
STUB_RE = re.compile(r"RETIRED PATH \(stub, expires (\d{4}-\d{2}-\d{2})\)")


def cmd_check(ctx, callers):
    ros = ctx.rosters
    fails = []
    for fn in ros.files:
        fails.extend(schema_check_file(os.path.join(ros.folder, fn), "roster"))
    for name, f1, f2 in ros.duplicates:
        fails.append("FAIL duplicate role '%s' in %s and %s" % (name, f1, f2))
    for name, body in ros.roles.items():
        f = ros.origin[name]
        if not ROLE_RE.match(name):
            fails.append("FAIL %s: invalid role name (%s)" % (name, f))
        tgt = body.get("retired")
        if tgt:
            if tgt not in ros.roles:
                fails.append("FAIL %s: retired points to undefined role '%s' (%s)" % (name, tgt, f))
            else:
                try:
                    ros.effective(name)
                except (RoleError, ExpandError) as e:
                    fails.append("FAIL %s: retired chain broken (%s)" % (name, e))
            continue
        kind = body.get("kind")
        if kind not in KINDS:
            fails.append("FAIL %s: unknown kind %r (%s)" % (name, kind, f))
            continue
        if kind == "value":
            val = body.get("value")
            if not isinstance(val, str) or not val.strip():
                fails.append("FAIL %s: value role needs a non-empty string 'value' (%s)" % (name, f))
                continue
            pat = body.get("pattern")
            if pat is not None:
                try:
                    re.compile(pat)
                except (re.error, TypeError) as e:
                    fails.append("FAIL %s: pattern does not compile (%s) (%s)" % (name, e, f))
            continue
        field = "find" if kind == "set" else "at"
        if body.get(field) is None:
            fails.append("FAIL %s: kind %s needs '%s' (%s)" % (name, kind, field, f))
            continue
        try:
            path, _ = ctx.resolve(name)
        except RoleError as e:
            fails.append("FAIL %s: names undefined role '%s' (%s)" % (name, e.role, f))
            continue
        except ExpandError as e:
            fails.append("FAIL %s: %s (%s)" % (name, e, f))
            continue
        bad = False
        for tok in leftover_vars(path):
            if not VAR_RE.match(tok):
                fails.append("FAIL %s: bad token {%s} (%s)" % (name, tok, f))
                bad = True
            elif kind != "place":
                fails.append("FAIL %s: unfilled variable {%s} in a %s role (%s)" % (name, tok, kind, f))
                bad = True
        if bad:
            continue
        pl = path.lower()
        if "\\archive\\" in pl or ".bak" in pl or pl.endswith("\\archive"):
            fails.append("FAIL %s: path points into an archive or backup: %s" % (name, path))
            continue
        if kind in ("file", "dir"):
            ok = os.path.isfile(path) if kind == "file" else os.path.isdir(path)
            if not ok:
                fails.append("FAIL %s: %s does not exist: %s (%s)" % (name, kind, path, f))
        elif kind == "set":
            if not glob.glob(path):
                fails.append("FAIL %s: set has no member: %s (%s)" % (name, path, f))
    if callers:
        today = datetime.date.today().isoformat()
        scripts_dir = os.path.normcase(os.path.abspath(os.path.join(ctx.root, ".MD", "scripts"))) + os.sep
        reported = set()
        for fpath in scan_targets(ctx):
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                    lines = fh.read().split("\n")
            except OSError:
                continue
            in_scripts = os.path.normcase(os.path.abspath(fpath)).startswith(scripts_dir)
            for ln, line in enumerate(lines, 1):
                names = [m.group(1) for m in CALL_RE.finditer(line)] + [m.group(1) for m in ROLETOK_RE.finditer(line)]
                for nm in names:
                    if nm not in ros.roles:
                        key = (nm, fpath, ln)
                        if key not in reported:
                            reported.add(key)
                            fails.append("FAIL undefined role '%s' named in %s:%d" % (nm, fpath, ln))
                if in_scripts:
                    sm = STUB_RE.search(line)
                    if sm and sm.group(1) < today:
                        fails.append("FAIL expired stub (expired %s) in %s:%d" % (sm.group(1), fpath, ln))
    if fails:
        out("\n".join(fails))
        return 1
    out("OK %d roles in %d rosters" % (len(ros.roles), len(ros.files)))
    return 0


INDEX_STAMP_RE = re.compile(r"^<!-- GENERATED \d{4}-\d{2}-\d{2} by resolve\.py ")


def _index_cell(text):
    return str(text).replace("\r", " ").replace("\n", " ").replace("|", "\\|")


def index_text(ctx):
    """The INDEX.md text: one table row per role, sorted by roster then role (no exists test anywhere)."""
    ros = ctx.rosters
    rows = []
    for name in ros.roles:
        body = ros.roles[name]
        roster = os.path.splitext(ros.origin[name])[0]
        if body.get("retired"):
            kind = body.get("kind") or "-"
            target = "-> %s" % body["retired"]
        else:
            kind = body.get("kind") or "-"
            try:
                target, _ = ctx.resolve(name)
            except (RoleError, ExpandError) as e:
                target = "ERROR %s" % e
        note = body.get("note") or "-"
        rows.append((roster, name, kind, target, note))
    rows.sort(key=lambda r: (r[0], r[1]))
    lines = [
        "# Resolver index - every role, in one table (GENERATED by resolve.py index --build, do not edit by hand)",
        "<!-- GENERATED %s by resolve.py from %d roles in %d rosters -->" % (
            datetime.date.today().isoformat(), len(ros.roles), len(ros.files)),
        "",
        "Ask by role, never by path: `resolve find <role>`, `run <role>`, `place <role> --var ...`, `explain <role>`.",
        "A role missing here is undefined; define it in the roster its kind belongs to, then rebuild this index.",
        "",
        "| roster | role | kind | resolves to | note |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append("| " + " | ".join(_index_cell(c) for c in r) + " |")
    return "\n".join(lines) + "\n"


def index_path(ctx):
    return os.path.normpath(os.path.join(ctx.rosters.folder, "..", "INDEX.md"))


def _strip_stamp_date(text):
    parts = text.split("\n")
    if len(parts) > 1:
        parts[1] = re.sub(r"^<!-- GENERATED \d{4}-\d{2}-\d{2} ", "<!-- GENERATED DATE ", parts[1])
    return "\n".join(parts)


def cmd_index(ctx, mode):
    p = index_path(ctx)
    text = index_text(ctx)
    if mode == "--build":
        with open(p, "wb") as fh:
            fh.write(text.encode("utf-8"))
        out("WROTE %s (%d roles in %d rosters)" % (p, len(ctx.rosters.roles), len(ctx.rosters.files)))
        return 0
    if mode == "--check":
        if not os.path.isfile(p):
            out("NO INDEX.md")
            return 1
        with open(p, "rb") as fh:
            have = fh.read().decode("utf-8-sig").replace("\r\n", "\n")
        if _strip_stamp_date(have) != _strip_stamp_date(text):
            out("STALE INDEX.md")
            return 1
        out("OK %d roles" % len(ctx.rosters.roles))
        return 0
    err("usage: resolve.py index --build | --check")
    return 64


HELP_FLAGS = {"--help", "-help", "-h", "/?", "-?", "--?", "/help"}


def ps1_help(path, role):
    """The .ps1's header: its <# ... #> comment-based help, or the run of '#' lines at its top, or its param() line."""
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            text = f.read()
    except OSError as e:
        return "%s: cannot read %s (%s)" % (role, path, e)
    lines = text.splitlines()
    head = []
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i < len(lines) and lines[i].lstrip().startswith("<#"):
        while i < len(lines):
            head.append(lines[i])
            if "#>" in lines[i]:
                break
            i += 1
    else:
        while i < len(lines) and lines[i].lstrip().startswith("#"):
            head.append(lines[i].lstrip()[1:].rstrip())
            i += 1
    if not head:
        params = next((ln for ln in lines if ln.strip().lower().startswith("param(")), "")
        head = ["(no header comment)", params] if params else ["(no header comment)"]
    return "%s - %s (help only: nothing was run)\n%s" % (role, path, "\n".join(head))


def cmd_run(ctx, role, args):
    try:
        final, retired = ctx.rosters.effective(role)
        body = ctx.rosters.roles[final]
        path, _ = ctx.resolve(role)
    except RoleError as e:
        out("NO SUCH ROLE %s" % e.role)
        return 2
    except ExpandError as e:
        out("ERROR %s" % e)
        return 2
    if retired:
        err("RETIRED %s -> %s" % (retired[0], final))
    if body.get("kind") != "file":
        out("%s is not a file role - cannot run" % role)
        return 4
    if not os.path.isfile(path):
        out("MISSING %s -> %s" % (role, path))
        return 1
    ext = os.path.splitext(path)[1].lower()
    # A HELP FLAG NEVER RUNS A .ps1 (2026-10-24: 'resolve.py run mo2-launch --help' LAUNCHED the owner's MO2 - PowerShell
    # does not know --help, so the script ran as if called with no arguments). Its header comment is printed instead.
    if ext == ".ps1" and any(str(a).lower() in HELP_FLAGS for a in args):
        out(ps1_help(path, role))
        return 0
    if ext == ".ps1":
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", path] + list(args)
    elif ext == ".py":
        cmd = ["py", "-3", path] + list(args)
    else:
        cmd = [path] + list(args)
    sys.stdout.flush()
    return subprocess.call(cmd)


# ---------------------------------------------------------------------------------------------------------------------
# distro: the names distro-names.ps1 hands out, computed here (step 2.3). distro-names.ps1 keeps its function names and
# parameters and calls these; package_paths.py imports them. Rules (the owner, 2026-09-29 and 2026-10-01):
#   * every folder under "11. Nexus distro" is "<Game> - <Mod>", the mod part without the game's own words;
#     "_distro-folders.json" beside the folders is the authoritative folder -> mod-name map;
#   * packages live in "<stage>\<Game> - <Mod>\<Mod> <version>[ FOMOD][.zip]"; the game comes from the registry or from
#     what a package contains - never from its name.
# The distro root and the stage folders come from the stages roster (stage-nexus-distro, stage-test-builds,
# stage-finalized). String comparisons follow PowerShell's: -eq / -like / -match / hashtable keys ignore case,
# [regex]::Match does not.

DISTRO_GAMES = ("Oblivion Remastered", "Skyrim", "MO2", "Witcher 3")
# A name with map entries in several games, looked up WITHOUT a game: Skyrim (the project's default) first, then the
# newer games. distro-names.ps1 took the first entry in .NET hashtable order, which no file states; this order gives
# the same answer for every shared name in the map on 2026-10-09 (Apocrypha Menu Framework -> Skyrim, Unbind Vanilla
# Controls -> Skyrim, Simple Loadout System -> Witcher 3).
DISTRO_NOGAME_ORDER = ("Skyrim", "Witcher 3", "MO2", "Oblivion Remastered")
DISTRO_MAP_FILE = "_distro-folders.json"
FOLDER_GAME_RE = re.compile(r"^(Oblivion Remastered|Skyrim|MO2|Witcher 3) - ")
FOLDER_PARTS_RE = re.compile(r"^(Oblivion Remastered|Skyrim|MO2|Witcher 3) - (.+)$")
MO2_NAME_RE = re.compile(r"^MO2 |MO2 Theme$", re.I)


class DistroError(Exception):
    pass


def _ieq(a, b):
    return (a or "").lower() == (b or "").lower()


def _ps_join(a, b):
    """Join-Path: one backslash between the two, the parent's own separators kept."""
    b = b.lstrip("\\/")
    if not a:
        return b
    return a + b if a.endswith(("\\", "/")) else a + "\\" + b


def _like(text, pattern):
    """PowerShell -like: * ? [set], backtick escapes, case-insensitive, whole string."""
    rx = []
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if c == "`" and i + 1 < len(pattern):
            rx.append(re.escape(pattern[i + 1]))
            i += 2
            continue
        if c == "*":
            rx.append(".*")
        elif c == "?":
            rx.append(".")
        elif c == "[":
            j = pattern.find("]", i + 1)
            if j == -1:
                rx.append(re.escape(c))
            else:
                body = pattern[i + 1:j].replace("\\", "\\\\")
                if body.startswith("^"):
                    body = "\\" + body
                rx.append("[" + body + "]")
                i = j + 1
                continue
        else:
            rx.append(re.escape(c))
        i += 1
    return re.fullmatch("".join(rx), text or "", re.I | re.S) is not None


def _culture_sorted(keys):
    """Sort-Object on strings: the user's culture, ignoring case (CompareStringEx), ordinal-lower as a fallback."""
    keys = list(keys)
    try:
        import ctypes
        import functools
        fn = ctypes.windll.kernel32.CompareStringEx
        fn.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_wchar_p, ctypes.c_int, ctypes.c_wchar_p,
                       ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        fn.restype = ctypes.c_int

        def cmp(a, b):
            r = fn(None, 1, a, -1, b, -1, None, None, None)   # NORM_IGNORECASE
            if r == 0:
                raise OSError("CompareStringEx failed")
            return r - 2
        return sorted(keys, key=functools.cmp_to_key(cmp))
    except Exception:
        return sorted(keys, key=lambda s: (s.lower(), s))


def _is_hidden(entry):
    try:
        attrs = entry.stat(follow_symlinks=False).st_file_attributes
    except (OSError, AttributeError):
        return False
    return bool(attrs & 0x6)   # FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM


def _ps_children(path, force):
    """Get-ChildItem on one folder: directories first, then files, each in the file system's order;
    without force, hidden and system items are left out. Returns [(name, full_path, is_dir)]."""
    if os.path.isfile(path):
        return [(os.path.basename(path), path, False)]
    dirs, files = [], []
    try:
        with os.scandir(path) as it:
            for e in it:
                if not force and _is_hidden(e):
                    continue
                full = _ps_join(path, e.name)
                try:
                    isdir = e.is_dir()
                except OSError:
                    isdir = False
                (dirs if isdir else files).append((e.name, full, isdir))
    except OSError:
        return []
    return dirs + files


class DistroMap(object):
    """The folder -> mod-name map, with PowerShell hashtable semantics: keys ignore case, file order kept."""

    def __init__(self):
        self.keys = []
        self.vals = {}

    def find_key(self, key):
        low = (key or "").lower()
        for k in self.keys:
            if k.lower() == low:
                return k
        return None

    def get(self, key):
        k = self.find_key(key)
        return None if k is None else self.vals[k]

    def set(self, key, value):
        k = self.find_key(key)
        if k is None:
            self.keys.append(key)
            k = key
        self.vals[k] = value

    def items(self):
        return [(k, self.vals[k]) for k in self.keys]


def _ps_string(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "True" if v else "False"
    return v if isinstance(v, str) else str(v)


def _role_path(ctx, role):
    try:
        p, _ = ctx.resolve(role)
    except (RoleError, ExpandError) as e:
        raise DistroError("roster role %s: %s" % (role, e))
    return p


def _stage_path(ctx, stage):
    """A stage named by its roster role (stage-test-builds) or given as a folder path."""
    if stage and ROLE_RE.match(stage) and stage in ctx.rosters.roles:
        return _role_path(ctx, stage)
    return stage


def distro_root(ctx):
    return _role_path(ctx, "stage-nexus-distro")


def distro_map(ctx):
    p = _ps_join(distro_root(ctx), DISTRO_MAP_FILE)
    m = DistroMap()
    if os.path.exists(p):
        with open(p, "rb") as fh:
            data = json.loads(fh.read().decode("utf-8-sig"))
        for k, v in (data or {}).items():
            m.set(k, _ps_string(v))
    return m


def _ps51_json_string(s):
    """A string the way Windows PowerShell 5.1's ConvertTo-Json writes it."""
    outp = ['"']
    for ch in s:
        o = ord(ch)
        if ch == '"':
            outp.append('\\"')
        elif ch == "\\":
            outp.append("\\\\")
        elif ch in "'<>&":
            outp.append("\\u%04x" % o)
        elif ch == "\b":
            outp.append("\\b")
        elif ch == "\t":
            outp.append("\\t")
        elif ch == "\n":
            outp.append("\\n")
        elif ch == "\f":
            outp.append("\\f")
        elif ch == "\r":
            outp.append("\\r")
        elif o < 0x20:
            outp.append("\\u%04x" % o)
        else:
            outp.append(ch)
    outp.append('"')
    return "".join(outp)


def distro_map_set(ctx, folder, mod):
    """Set-DistroMapEntry: the map sorted by folder, written as PowerShell 5.1 wrote it (BOM, CRLF, 4-space indent)."""
    p = _ps_join(distro_root(ctx), DISTRO_MAP_FILE)
    m = distro_map(ctx)
    m.set(folder, mod)
    keys = _culture_sorted(m.keys)
    body = ",\r\n".join("    %s:  %s" % (_ps51_json_string(k), _ps51_json_string(m.vals[k])) for k in keys)
    text = "{\r\n" + body + "\r\n}\r\n"
    data = b"\xef\xbb\xbf" + text.encode("utf-8")
    with open(p, "wb") as fh:
        fh.write(data)


def distro_game(text):
    """ConvertTo-DistroGame: registry-style game values ('OblivionRemastered', 'SkyrimSE') to the folder's word."""
    t = _ps_string(text)
    if re.search(r"^\s*$", t):
        return ""
    if re.search("oblivion", t, re.I):
        return "Oblivion Remastered"
    if re.search("witcher", t, re.I):
        return "Witcher 3"
    if re.search(r"^(mo2|modorganizer)", t, re.I):
        return "MO2"
    return "Skyrim"


def distro_modpart(mod, game):
    """ConvertTo-DistroModPart: the full name with the game's own words taken out."""
    n = mod or ""
    g = (game or "").lower()
    if g == "oblivion remastered":
        n = re.sub(r" for Oblivion Remastered$", "", n, flags=re.I)
        n = re.sub(r" for Oblivion$", "", n, flags=re.I)
        n = re.sub(r"^Oblivion Remastered - ", "", n, flags=re.I)
    elif g == "mo2":
        n = re.sub(r"^MO2 ", "", n, flags=re.I)
        n = re.sub(r" MO2 Theme$", " Theme", n, flags=re.I)
    return n


def distro_foldergame(folder):
    m = FOLDER_GAME_RE.match(folder or "")
    return m.group(1) if m else ""


def _package_names(path):
    names = []

    def walk(cur, rel, depth):
        for name, full, isdir in _ps_children(cur, False):
            r = rel + "\\" + name if rel else name
            names.append(r)
            if isdir and depth < 3:
                walk(full, r, depth + 1)
    walk(path, "", 0)
    return names


def distro_packagegame(path):
    """Get-PackageGame: the game a package folder or zip is for, from what it contains ('' when nothing says)."""
    if os.path.isdir(path):
        names = _package_names(path)
    elif re.search(r"\.zip$", path or "", re.I):
        try:
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
        except Exception:
            return ""
    else:
        return ""
    joined = "\n".join(names)
    f = re.I | re.M
    if re.search(r"^(.*[\\/])?(OblivionRemastered|OBSE)[\\/]", joined, f):
        return "Oblivion Remastered"
    # Witcher 3 before Skyrim: its Mods\mod*\content\scripts tree would read as a Skyrim scripts\ folder
    if re.search(r"^(.*[\\/])?bin[\\/](x64_dx12|config[\\/]r4game)[\\/]", joined, f) or re.search(r"\.ws$", joined, f):
        return "Witcher 3"
    if re.search(r"^(.*[\\/])?(SKSE|Data|Interface|meshes|textures|scripts)[\\/]", joined, f) or \
            re.search(r"\.es[pml]$", joined, f):
        return "Skyrim"
    if re.search(r"^(.*[\\/])?plugins[\\/]", joined, f) or re.search(r"\.py$", joined, f) or \
            re.search(r"\.qss$", joined, f):
        return "MO2"
    return ""


def distro_testgame(path, folder_game):
    """Test-PackageGame: true when the package is for the folder's game (no game on either side matches)."""
    if not folder_game:
        return True
    g = distro_packagegame(path)
    return (not g) or _ieq(g, folder_game)


def _nogame_rank(key):
    g = distro_foldergame(key)
    return DISTRO_NOGAME_ORDER.index(g) if g in DISTRO_NOGAME_ORDER else len(DISTRO_NOGAME_ORDER)


def distro_folder(ctx, mod, game=""):
    """Resolve-DistroFolder: the distro folder's full path (existing, or where a new one goes)."""
    # an optional file of another mod's page (distro_optional): the parent's folder is where its material goes
    opt = distro_optional(ctx, mod)
    if opt:
        return distro_folder(ctx, opt["parent"], game)
    root = distro_root(ctx)
    m = distro_map(ctx)
    g = distro_game(game)
    items = m.items()
    # a name two games share (Apocrypha Menu Framework, 2026-09-29): the game's own map entry first
    if g:
        for k, v in items:
            if _ieq(v, mod) and _like(k, g + " - *") and os.path.exists(_ps_join(root, k)):
                return _ps_join(root, k)
    # ...and with the game known, never another game's entry (HUD Position Manager, 2026-09-30)
    order = items if g else sorted(items, key=lambda kv: _nogame_rank(kv[0]))
    for k, v in order:
        if _ieq(v, mod) and (not g or _like(k, g + " - *")) and os.path.exists(_ps_join(root, k)):
            return _ps_join(root, k)
    # ...nor another game's folder by name (Unbind Vanilla Controls W3, 2026-10-06)
    for gg in ([g] if g else list(DISTRO_GAMES)):
        cand = _ps_join(root, "%s - %s" % (gg, distro_modpart(mod, gg)))
        if os.path.exists(cand):
            return cand
    plain = _ps_join(root, mod)
    if os.path.exists(plain):
        return plain   # an unprefixed folder from before 2026-09-29
    # none exists: where a new one goes - Skyrim when nothing says otherwise
    if g:
        g2 = g
    elif re.search("Oblivion", mod, re.I):
        g2 = "Oblivion Remastered"
    elif MO2_NAME_RE.search(mod):
        g2 = "MO2"
    else:
        g2 = "Skyrim"
    return _ps_join(root, "%s - %s" % (g2, distro_modpart(mod, g2)))


def distro_modname(ctx, folder, finalized_root=""):
    """Resolve-DistroModName: the mod's full name (registry / finalized-folder form) for a distro folder name."""
    m = distro_map(ctx)
    v = m.get(folder)
    if v is not None:
        return v
    mt = FOLDER_PARTS_RE.match(folder or "")
    if not mt:
        return folder   # an unprefixed folder
    game, part = mt.group(1), mt.group(2)
    if game == "Oblivion Remastered":
        cands = [part, part + " for Oblivion Remastered", part + " for Oblivion"]
    elif game == "MO2":
        cands = [part, "MO2 " + part, re.sub(r" Theme$", " MO2 Theme", part, flags=re.I)]
    else:
        cands = [part]
    if finalized_root and os.path.exists(finalized_root):
        # the packages sit in "<FinalizedRoot>\<Game> - <Mod>\" since 2026-10-01 (the flat root is read for the transition)
        for where in (_ps_join(finalized_root, folder), finalized_root):
            if not os.path.exists(where):
                continue
            names = [n for n, _, _ in _ps_children(where, False)]
            for c in cands:
                if any(_like(n, c + " *") for n in names):
                    return c
    return cands[0]


def distro_parse(name):
    """ConvertFrom-PackageName: Mod, Version, Tail, Ext, Symbols - or None."""
    mt = PACKAGE_RE.match(name or "")
    if not mt:
        return None
    return {"Mod": mt.group("mod"), "Version": mt.group("ver"), "Tail": mt.group("tail"),
            "Ext": mt.group("ext") or "", "Symbols": mt.group("sym") is not None}


def distro_pkgfolder(ctx, mod, game):
    """Get-PackageFolderName: the folder a mod's packages live under in 7 and 10. The game is required."""
    if mod is None or mod.strip() == "" or mod != mod.strip():
        raise DistroError("package folder: refusing an empty or padded mod name '%s'" % (mod or ""))
    g = distro_game(game)
    if not g:
        raise DistroError("package folder: no game given for '%s' - the folder is never guessed" % mod)
    m = distro_map(ctx)
    for k in _culture_sorted(m.keys):
        if _ieq(m.vals[k], mod) and _like(k, g + " - *"):
            return k
    return "%s - %s" % (g, distro_modpart(mod, g))


def distro_pkgroot(ctx, stage, mod, game):
    """Resolve-PackageRoot: "<stage>\\<Game> - <Mod>" (existing or not)."""
    return _ps_join(_stage_path(ctx, stage), distro_pkgfolder(ctx, mod, game))


def distro_modgame(ctx, entry):
    """Get-ModGame: the game a version-registry entry is for."""
    if "game" in entry and _ps_string(entry.get("game")):
        g = distro_game(_ps_string(entry.get("game")))
        if g:
            return g
    if _like(_ps_string(entry.get("pluginDir")), "OblivionRemastered*"):
        return "Oblivion Remastered"
    dom = _ps_string(entry.get("nexusDomain"))
    if re.search("oblivion", dom, re.I):
        return "Oblivion Remastered"
    if re.search("witcher", dom, re.I):
        return "Witcher 3"
    name = _ps_string(entry.get("displayName"))
    if name:
        found = []
        for role in ("stage-test-builds", "stage-finalized"):
            stage = _role_path(ctx, role)
            for g in DISTRO_GAMES:
                if os.path.exists(distro_pkgroot(ctx, stage, name, g)) and g not in found:
                    found.append(g)
        if len(found) == 1:
            return found[0]
        if MO2_NAME_RE.search(name):
            return "MO2"
    return "Skyrim"


def distro_registry_entry(ctx, key):
    path = _role_path(ctx, "version-registry")
    with open(path, "rb") as fh:
        data = json.loads(fh.read().decode("utf-8-sig"))
    entry = data.get(key) if isinstance(data, dict) else None
    if not isinstance(entry, dict):
        raise DistroError("no version-registry entry '%s'" % key)
    return entry


def distro_optional(ctx, mod):
    """The 'optional file of <parent>' relation (the owner, 2026-10-19: Local Map Item Markers is an optional file of
    Local Map Upgrade's page, not a page of its own). A registry entry that carries "optionalFileOf": "<parent display
    name>" is posted as a file of the PARENT's page, so its distro material lives in the parent's folder: the folder
    resolves to the parent's, the page text, banner and notes belong to the parent, and the optional file keeps its own
    changelog file ("optionalChangelog", default "changelog-<slug of the mod's name>.txt"). Returns None for any mod
    that is not an optional file, else {parent, key, changelog}. Looked up by registry key or display name."""
    if not mod:
        return None
    path = _role_path(ctx, "version-registry")
    if not os.path.isfile(path):
        return None  # no registry (e.g. a bare copy of the repo): no optional-file relation
    with open(path, "rb") as fh:
        data = json.loads(fh.read().decode("utf-8-sig"))
    if not isinstance(data, dict):
        return None
    hit = None
    for k, v in data.items():
        if isinstance(v, dict) and (_ieq(k, mod) or _ieq(_ps_string(v.get("displayName")), mod)):
            hit = (k, v)
            break
    if not hit:
        return None
    key, entry = hit
    parent = _ps_string(entry.get("optionalFileOf"))
    if not parent:
        return None
    parent_entry = next((v for k, v in data.items() if isinstance(v, dict) and
                         (_ieq(k, parent) or _ieq(_ps_string(v.get("displayName")), parent))), None)
    if parent_entry is None:
        raise DistroError("'%s' is an optional file of '%s', which is not in the version registry" % (key, parent))
    if _ps_string(parent_entry.get("optionalFileOf")):
        raise DistroError("'%s' is an optional file of '%s', which is itself an optional file - name the page's mod" % (key, parent))
    parent_name = _ps_string(parent_entry.get("displayName")) or parent
    changelog = _ps_string(entry.get("optionalChangelog"))
    if not changelog:
        slug = re.sub(r"[^a-z0-9]+", "-", _ps_string(entry.get("displayName") or key).lower()).strip("-")
        changelog = "changelog-%s.txt" % slug
    return {"parent": parent_name, "key": key, "changelog": changelog}


def _version_string(v):
    try:
        return ".".join(str(int(x)) for x in v.split("."))
    except ValueError:
        return v


def distro_find_packages(ctx, stage, mod="", game="", version="", folders=False, archives=False, symbols=False):
    """Find-Packages: every package (folder, .zip, .7z) in a stage, read from its "<Game> - <Mod>" folders, plus the
    flat ones still in the stage root (flat=True; with a game, a flat one counts only when its contents say so).
    "- Debug Symbols" packages are left out unless symbols."""
    root = _stage_path(ctx, stage)
    if not root or not os.path.exists(root):
        return []
    base = os.path.abspath(root)
    g = distro_game(game) if game else ""
    games = [g] if g else list(DISTRO_GAMES)
    games_low = [x.lower() for x in games]
    top = _ps_children(base, True)
    dirs = [t for t in top if t[2] and distro_foldergame(t[0]).lower() in games_low and distro_foldergame(t[0])]
    if mod:
        want = [distro_pkgfolder(ctx, mod, gg).lower() for gg in games]
        dirs = [d for d in dirs if d[0].lower() in want]
    cands = []
    for d in dirs:
        for item in _ps_children(d[1], True):
            cands.append((item, distro_foldergame(d[0]), False))
    for item in top:
        if not distro_foldergame(item[0]):
            cands.append((item, "", True))
    outl = []
    for (name, full, isdir), pg, flat in cands:
        ext = os.path.splitext(name)[1].lower()
        if not isdir and ext not in (".zip", ".7z"):
            continue
        if folders and not archives and not isdir:
            continue
        if archives and not folders and isdir:
            continue
        p = distro_parse(name)
        if not p:
            continue
        if isdir and p["Ext"]:
            continue
        if p["Symbols"] and not symbols:
            continue
        if mod and not _ieq(p["Mod"], mod):
            continue
        if version and not _ieq(p["Version"], version):
            continue
        if flat and g:
            try:
                pg = distro_packagegame(full)
            except Exception:
                pg = ""
            if not _ieq(pg, g):
                continue
        outl.append({"name": name, "path": full, "mod": p["Mod"], "version": _version_string(p["Version"]),
                     "tail": p["Tail"], "game": pg, "flat": flat, "is_dir": isdir, "root": os.path.dirname(full)})
    return outl


DISTRO_USAGE = ("distro game <text> | root | map | map-set <folder> <mod> | modpart <mod> <game> | foldergame <folder> | "
                "packagegame <path> | testgame <path> <game> | folder <mod> [--game g] | "
                "modname <folder> [--finalized-root p] | parse <name> | pkgfolder <mod> --game g | "
                "pkgroot <stage> <mod> --game g | modgame <registry-key> | optional <mod> | "
                "find-packages <stage> [--mod m] [--game g] [--version v] [--folders] [--archives] [--symbols]   "
                "(<stage> is a stage role such as stage-test-builds, or a folder path; --stdin reads "
                "{root, argv[, entry]} as JSON and answers {value} or {error})")
DISTRO_FLAGS = ("folders", "archives", "symbols")
DISTRO_OPTS = ("game", "finalized-root", "mod", "version")


def _distro_args(argv):
    pos, o = [], {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--") and len(a) > 2:
            name, eq, val = a[2:].partition("=")
            if name in DISTRO_FLAGS and not eq:
                o[name] = True
                i += 1
                continue
            if name in DISTRO_OPTS:
                if eq:
                    o[name] = val
                    i += 1
                    continue
                if i + 1 < len(argv):
                    o[name] = argv[i + 1]
                    i += 2
                    continue
                raise DistroError("option --%s needs a value" % name)
            raise DistroError("unknown option %s" % a)
        pos.append(a)
        i += 1
    return pos, o


def distro_dispatch(ctx, argv, entry=None):
    """Runs one distro sub-command; returns its Python value."""
    pos, o = _distro_args(argv)
    if not pos:
        raise DistroError("usage: " + DISTRO_USAGE)
    sub, rest = pos[0], pos[1:]

    def need(n):
        if len(rest) < n:
            raise DistroError("usage: " + DISTRO_USAGE)
        return rest

    def arg(n):
        return rest[n] if len(rest) > n else ""
    if sub == "game":
        return distro_game(arg(0))
    if sub == "root":
        return distro_root(ctx)
    if sub == "map":
        m = distro_map(ctx)
        return dict(m.items())
    if sub == "map-set":
        need(2)
        distro_map_set(ctx, rest[0], rest[1])
        return None
    if sub == "modpart":
        need(1)
        return distro_modpart(rest[0], arg(1))
    if sub == "foldergame":
        need(1)
        return distro_foldergame(rest[0])
    if sub == "packagegame":
        need(1)
        return distro_packagegame(rest[0])
    if sub == "testgame":
        need(1)
        return distro_testgame(rest[0], arg(1))
    if sub == "folder":
        need(1)
        return distro_folder(ctx, rest[0], o.get("game", ""))
    if sub == "modname":
        need(1)
        return distro_modname(ctx, rest[0], o.get("finalized-root", ""))
    if sub == "parse":
        need(1)
        return distro_parse(rest[0])
    if sub == "pkgfolder":
        need(1)
        return distro_pkgfolder(ctx, rest[0], o.get("game", ""))
    if sub == "pkgroot":
        need(2)
        return distro_pkgroot(ctx, rest[0], rest[1], o.get("game", ""))
    if sub == "optional":
        need(1)
        return distro_optional(ctx, rest[0])
    if sub == "modgame":
        if entry is None:
            need(1)
            entry = distro_registry_entry(ctx, rest[0])
        return distro_modgame(ctx, entry)
    if sub == "find-packages":
        need(1)
        return distro_find_packages(ctx, rest[0], o.get("mod", ""), o.get("game", ""), o.get("version", ""),
                                    bool(o.get("folders")), bool(o.get("archives")), bool(o.get("symbols")))
    raise DistroError("unknown distro command %s - usage: %s" % (sub, DISTRO_USAGE))


def cmd_distro(ctx, argv):
    if argv[:1] == ["--stdin"]:
        # distro-names.ps1's route: arguments as JSON on stdin (Windows PowerShell 5.1 drops empty native arguments
        # and mangles quotes), the answer as ASCII-only JSON on stdout.
        try:
            req = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
            root = req.get("root") or DEFAULT_ROOT
            ctx.root = root.rstrip("\\/") if len(root) > 3 else root
            value = distro_dispatch(ctx, [_ps_string(a) for a in (req.get("argv") or [])], req.get("entry"))
        except Exception as e:   # every failure reaches the caller as a thrown error, never as a value
            out(json.dumps({"error": str(e) or e.__class__.__name__}, ensure_ascii=True))
            return 1
        out(json.dumps({"value": value}, ensure_ascii=True))
        return 0
    try:
        value = distro_dispatch(ctx, argv)
    except (DistroError, ValueError, OSError) as e:
        out("ERROR %s" % e)
        return 2
    sub = argv[0] if argv else ""
    if sub == "map-set":
        out("OK")
    elif isinstance(value, bool):
        out("true" if value else "false")
    elif value is None:
        out("null")
        return 1
    elif isinstance(value, (dict, list)):
        out(json.dumps(value, ensure_ascii=False))
    else:
        out(value)
    return 0


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
        sys.stderr.reconfigure(encoding="utf-8", newline="\n")
    except Exception:
        pass
    opts, pos = parse_args(argv)
    if not pos:
        err("usage: resolve.py [--rosters DIR] [--root PATH] <find|list|place|identify|explain|check|run> ...")
        return 64
    rost_dir = opts["rosters"] or os.path.join(os.path.dirname(os.path.abspath(__file__)), "rosters")
    root = opts["root"].rstrip("\\/") if len(opts["root"]) > 3 else opts["root"]
    ctx = Ctx(Rosters(rost_dir), root, opts["var"])
    cmd = pos[0]
    if cmd == "distro":
        return cmd_distro(ctx, pos[1:])
    if cmd == "check":
        if opts["schema"] is not None:
            return cmd_schema(ctx, opts["schema"], opts["file"])
        return cmd_check(ctx, opts["callers"])
    if cmd == "index":
        return cmd_index(ctx, pos[1] if len(pos) > 1 else "")
    if len(pos) < 2:
        err("usage: resolve.py %s <argument>" % cmd)
        return 64
    arg = pos[1]
    if cmd == "find":
        return cmd_find(ctx, arg)
    if cmd == "list":
        return cmd_list(ctx, arg)
    if cmd == "place":
        return cmd_place(ctx, arg)
    if cmd == "identify":
        return cmd_identify(ctx, arg)
    if cmd == "explain":
        return cmd_explain(ctx, arg)
    if cmd == "run":
        return cmd_run(ctx, arg, pos[2:])
    err("unknown command %s" % cmd)
    return 64


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
