#!/usr/bin/env python3
"""events.py (role events) - the pipeline's one event log: record, read, fold, check.

Step 1 of the "one event log" design (4. plans\\pipeline-restructure\\SIMPLIFY-3-one-event-log.md, sections 3 and 6).
The log is role `pipeline-events` (resolve.py find pipeline-events); --log <path> overrides it (tests use a copy).

  record   append ONE v2 event. A bad kind or bad arguments: exit 2, nothing written. An I/O problem (no lock, no disk,
           no resolver) NEVER fails the caller: a warning line and exit 0. Appends happen under <log>.lock (created
           exclusively, retried up to 5 s, stale after 30 s); a writer that cannot take the lock appends to <log>.spill,
           and the next record that does take it merges the spill first. Prints the new event's id on success.
           --kind auto derives the kind from --event by LABEL_KINDS (what pipeline-log -Action record passes); an
           unmapped label then becomes kind "legacy", which an explicit --kind can never be.
           A gate event with outcome fail gets `reasons` from its note (step 2: the Format-GateFailNote grammar, see
           reasons_from_note), never empty; the note itself is kept as written. Other events carry `reasons` only
           when the writer passes --reasons.
  read     every event as one JSON line in v2 shape; v1 lines are upgraded IN MEMORY only, the file is never rewritten.
  fold V   a view folded from the events. Step 1 has only `stages` (what pipeline-log -Action summary counts).
  check    every line parses; every v2 line matches the schema. Counts per version and kind; exit 1 on a bad line.
           Also REPORTS (never fails on) step 3's closing check: live v2 events naming a mod without subject.key, and
           intake events whose stage differs from their refs.folder's stage.
  import-staged F
           appends a staged file (step 5 imports, step 6 reconstructions) through the locked path, all or nothing:
           only provenance reconstructed/imported, ids not already in the log, refs.about pointing at a real event.
  stage P  the stage (1-12 or null) each path sits in - what reconcile records an arrival under (step 3).
  last --kind K [--key M] [--version V]
           the LATEST event of that kind for that subject, as one JSON line (nothing when there is none; exit 0 either
           way). The subject matches on subject.key, or - for an event written without a key - on its display name
           equal to M (the key map applies, as in read). Latest = newest ts, ties by file order. Straight flow C
           (2026-10-13): pre-finalize-check.ps1 reads the last gate event of (mod key, version) before it runs.
  fold version-ledger | version-ledger-prerelease | gate-ledger | falsification-log
           (step 4, dual write) the ledger rebuilt from its mirror events: each ledger write also records an event
           carrying the WHOLE row (`row`) and refs.source "<file>#<index>"; the latest per row identity wins.
  check --view <ledger> [--file F]
           compares that fold with the real file, row by row and field by field: matched / differing /
           not yet covered (rows written before the dual write - step 5 imports them). Exit 1 only on a difference.

Writes UTF-8 without BOM, LF, one object per line, ensure_ascii=False. Standard library only.
"""
import argparse
import collections
import datetime
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
RESOLVE_PY = os.path.join(os.path.dirname(HERE), "resolvers", "resolve.py")

# Section 3's kind enum, plus `posted` (version-gate's 2026-10-11 action that spends a number on Nexus).
KINDS = ("build", "package", "install", "gate", "verdict", "verdict-resolved", "episode-open", "episode-attempt",
         "episode-close", "intake", "distro", "finalize", "prune", "drift", "doc-version", "rules-version", "withdraw",
         "posted", "posted-retracted")
# Only reachable through --kind auto (pipeline-log) or a v1 upgrade: a label the table does not know.
LEGACY = "legacy"
PROVENANCE = ("live", "imported", "backfilled", "reconstructed")

# v1 event label -> kind. Written from the labels actually in pipeline-events.jsonl on 2026-10-12 (counts in
# .MD\logs\steps\ev-1-report.md) plus the labels the current writers can still emit (drift-FOUND, build withdrawn).
LABEL_KINDS = {
    "build working": "build", "build failed": "build", "build untested": "build", "build scratch": "build",
    "build withdrawn": "withdraw", "built": "build",
    "gate-FAIL": "gate", "gate-pass": "gate", "gate PASS": "gate",
    "intake arrived": "intake",
    # stages 3, 5 and 9 record changes and departures too, and one 'present' per item that was already there (the
    # owner, 2026-10-27 20:11: "give them activity tracking"); reconcile.ps1 and stage-activity-backfill write them
    "intake changed": "intake", "intake left": "intake", "intake present": "intake",
    "packaged": "package",
    "installed": "install",
    "distro-synced": "distro", "distro package built": "distro",
    "pruned": "prune",
    "finalized": "finalize",
    "posted": "posted", "posted-retracted": "posted-retracted",
    "drift-check clean": "drift", "drift-FOUND": "drift",
    "compatibility-confirmed": "verdict", "compatibility-checked": "verdict",
}
# Prefix rules after the exact table: "verdict: <word>" is gate-ledger's verdict line.
LABEL_PREFIXES = (("verdict: ", "verdict"), ("verdict resolved: ", "verdict-resolved"),
                  ("episode open", "episode-open"), ("episode attempt: ", "episode-attempt"),
                  ("episode contest: ", "episode-attempt"), ("episode close: ", "episode-close"))

# Step 4 (dual write): the ledgers each ledger-writing tool also mirrors into the log. Every mirror event carries the
# WHOLE row as written (`row`) and refs.source = "<ledger file>#<row index>"; refs.removed marks a row taken out.
# The fold of a view is the latest mirror event per row identity (section 4: "the latest event gives the row").
LEDGER_VIEWS = {
    "version-ledger": {"file": "version-ledger.json", "role": "version-ledger", "identity": ("mod", "version")},
    "version-ledger-prerelease": {"file": "version-ledger-prerelease.json", "role": "version-ledger-prerelease",
                                  "identity": ("mod", "version", "archived")},
    "gate-ledger": {"file": "gate-ledger.json", "role": "gate-ledger", "identity": ("id",)},
    "falsification-log": {"file": "falsification-log.json", "role": "falsification-log", "identity": ("id",)},
}

# Step 2: a gate fail's `reasons` come from its note, in the 2026-10-10 grammar of pre-finalize-check's
# Format-GateFailNote - tokens joined by '; ': `gate-rules:<id>` per package-gate row that hit,
# `gate-rules:(unparsed)` when the row id could not be read, `rule <n>: <check>` for the script's own checks.
REASON_TOKEN_RE = re.compile(r"^(?:gate-rules:\(unparsed\)|gate-rules:[^\s\[\];]+|rule [^\s:;]+: \S.*)$")
NO_REASON = "(no reason recorded)"

LOCK_WAIT = 5.0
LOCK_STALE = 30.0


def kind_for_label(label):
    label = label or ""
    if label in LABEL_KINDS:
        return LABEL_KINDS[label]
    for prefix, kind in LABEL_PREFIXES:
        if label.startswith(prefix):
            return kind
    return LEGACY


def outcome_for_label(label):
    label = label or ""
    if label.startswith("build "):
        return label[6:].strip()
    if label.startswith("verdict: "):
        return label[9:].strip()
    for prefix in ("verdict resolved: ", "episode attempt: ", "episode contest: ", "episode close: "):
        if label.startswith(prefix):
            return label[len(prefix):].strip()
    low = label.lower()
    if low in ("gate-fail",):
        return "fail"
    if low in ("gate-pass", "gate pass"):
        return "pass"
    if label in ("intake changed", "intake left", "intake present"):
        return label.split(" ", 1)[1]
    if label == "drift-check clean":
        return "clean"
    if label == "drift-FOUND":
        return "found"
    return ""


def reasons_from_note(note):
    """The note's grammar tokens, in order, each once; never empty - a fail with no parsable token says so."""
    out = []
    for tok in (note or "").split("; "):
        tok = tok.strip()
        if tok and REASON_TOKEN_RE.match(tok) and tok not in out:
            out.append(tok)
    return out or [NO_REASON]


def warn(msg):
    sys.stdout.write("  [warn] events.py: %s\n" % msg)
    sys.stdout.flush()


def log_path(arg):
    if arg:
        return os.path.abspath(arg)
    r = subprocess.run([sys.executable, RESOLVE_PY, "find", "pipeline-events"], capture_output=True, text=True,
                       timeout=30)
    path = (r.stdout or "").strip().splitlines()[0].strip() if (r.stdout or "").strip() else ""
    if r.returncode != 0 or not path:
        raise OSError("resolve.py find pipeline-events failed (exit %s): %s" % (r.returncode, (r.stdout + r.stderr).strip()))
    return path


_STAGE_DIRS = None


def _stage_dirs():
    """[(path, stage number)] of every stage-* dir role, resolved by resolve.py's own Rosters (imported, not edited)."""
    global _STAGE_DIRS
    if _STAGE_DIRS is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location("resolve_for_events", RESOLVE_PY)
        rv = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rv)
        ctx = rv.Ctx(rv.Rosters(os.path.join(os.path.dirname(RESOLVE_PY), "rosters")), rv.DEFAULT_ROOT, {})
        dirs = []
        for name, body in ctx.rosters.roles.items():
            if not name.startswith("stage-") or body.get("kind") != "dir" or body.get("retired"):
                continue
            try:
                p, _ = ctx.resolve(name)
            except (rv.RoleError, rv.ExpandError):
                continue
            m = re.match(r"^(\d+)\.", os.path.basename(p.rstrip("\\")))
            num = int(m.group(1)) if m else None
            dirs.append((p.rstrip("\\"), num if num is not None and 1 <= num <= 12 else None))
        _STAGE_DIRS = dirs
    return _STAGE_DIRS


def stage_of(path):
    """The pipeline stage (1-12) a path sits in, or None. The same rule as `resolve.py identify` - the longest stage-*
    dir role that contains the path - without identify's requirement that the leaf be a package: identify answers
    UNRECOGNISED for a loose file such as an arrival in 4. plans. The number is the stage folder's leading number
    ("4. plans" -> 4); a stage folder numbered outside 1-12 (13. testbench) gives None."""
    low = os.path.abspath(path).replace("/", "\\").rstrip("\\").lower()
    best, best_len = None, -1
    for p, num in _stage_dirs():
        pl = p.lower()
        if (low == pl or low.startswith(pl + "\\")) and len(p) > best_len:
            best, best_len = num, len(p)
    return best


def cmd_stage(a):
    """One line per path, in the order given: the stage number or null."""
    for p in a.paths:
        s = stage_of(p)
        sys.stdout.write(("null" if s is None else str(s)) + "\n")
    return 0


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


# ------------------------------------------------------------------------------------------------------------------
# schema


def _str_or_none(v):
    return v is None or isinstance(v, str)


def schema_errors(o):
    """Errors of one v2 event against section 3. Extra fields (episode/verdict payloads) are allowed."""
    errs = []
    if o.get("v") != 2:
        errs.append("v must be 2")
    if not isinstance(o.get("id"), str) or not re.match(r"^\d{8}T\d{6}(\d+)?-[0-9a-f]{4}$", o.get("id") or ""):
        errs.append("id must be <compact ts>-<4 hex>")
    ts = o.get("ts")
    if not isinstance(ts, str):
        errs.append("ts must be a string")
    else:
        try:
            if datetime.datetime.fromisoformat(ts).tzinfo is None:
                errs.append("ts has no offset")
        except ValueError:
            errs.append("ts is not ISO 8601")
    st = o.get("stage", "missing")
    if not (st is None or (isinstance(st, int) and not isinstance(st, bool) and 1 <= st <= 12)):
        errs.append("stage must be 1-12 or null")
    if o.get("kind") not in KINDS + (LEGACY,):
        errs.append("kind %r not in the enum" % o.get("kind"))
    for f in ("event", "outcome", "note", "evidence", "by"):
        if not isinstance(o.get(f), str):
            errs.append("%s must be a string" % f)
    sub = o.get("subject")
    if not isinstance(sub, dict):
        errs.append("subject must be an object")
    else:
        for f in ("key", "display", "version", "game"):
            if f not in sub or not _str_or_none(sub[f]):
                errs.append("subject.%s must be a string or null" % f)
    if "reasons" in o:
        rs = o.get("reasons")
        if not isinstance(rs, list) or not all(isinstance(x, str) for x in rs):
            errs.append("reasons must be an array of strings")
    if o.get("kind") == "gate" and o.get("outcome") == "fail" and not o.get("reasons"):
        errs.append("a gate fail must carry reasons (step 2)")
    if not isinstance(o.get("refs"), dict):
        errs.append("refs must be an object")
    if "row" in o and not isinstance(o.get("row"), dict):
        errs.append("row must be an object")
    if "session" not in o or not _str_or_none(o.get("session")):
        errs.append("session must be a string or null")
    if o.get("provenance") not in PROVENANCE:
        errs.append("provenance %r not one of %s" % (o.get("provenance"), "/".join(PROVENANCE)))
    return errs


# ------------------------------------------------------------------------------------------------------------------
# v1 -> v2 on read


def upgrade_v1(o, lineno, basename):
    label = o.get("event") or ""
    seed = "%s#%d#%s" % (basename, lineno, o.get("ts") or "")
    compact = re.sub(r"[^0-9T]", "", (o.get("ts") or "")[:19]) or "00000000T000000"
    up = {
        "v": 2,
        "id": "%s-%s" % (compact, hashlib.sha1(seed.encode("utf-8")).hexdigest()[:4]),
        "ts": o.get("ts"),
        "stage": o.get("stage"),
        "kind": kind_for_label(label),
        "event": label,
        "outcome": outcome_for_label(label),
        "subject": {"key": None, "display": o.get("mod") or None, "version": o.get("version") or None, "game": None},
        "note": o.get("note") or "",
        "evidence": o.get("evidence") or "",
        "refs": {"source": "%s#%d" % (basename, lineno)},
        "by": o.get("by") or "",
        "session": None,
        "provenance": "backfilled" if o.get("backfilled") else "live",
        "upgraded_from": 1,
    }
    if up["kind"] == "gate" and up["outcome"] == "fail":
        # in memory only, like the rest of the upgrade: the 463 notes from before 2026-10-10 are empty and read back
        # as "(no reason recorded)", which is what they are; step 6 may reconstruct them (provenance reconstructed)
        items = list(up.items())
        up = dict(items[:8] + [("reasons", reasons_from_note(up["note"]))] + items[8:])
    return up


def iter_lines(path):
    """(lineno, raw text without line end, parsed object or None, error or None) for every non-blank line."""
    with open(path, "rb") as fh:
        data = fh.read()
    for i, raw in enumerate(data.split(b"\n"), 1):
        raw = raw.rstrip(b"\r")
        if not raw.strip():
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as e:
            yield i, None, None, "not UTF-8: %s" % e
            continue
        if text.startswith("\ufeff"):
            yield i, text, None, "starts with a BOM"
            continue
        try:
            o = json.loads(text)
        except ValueError as e:
            yield i, text, None, "not JSON: %s" % e
            continue
        if not isinstance(o, dict):
            yield i, text, None, "not a JSON object"
            continue
        yield i, text, o, None


def read_events(path, keymap=None, raw=False):
    """Every event in v2 shape. Unless raw:
      * subjects without a key get one from the key map (step 5: events-keymap.json), marked subject.key_from: keymap;
      * once the log holds imported ledger rows (step 5), the 288 v1 lines marked backfilled:true are skipped - they
        were derived from those same ledgers (section 5 item 3); they stay in the file.
    The file is never rewritten."""
    base = os.path.basename(path)
    out = []
    has_import = False
    for i, _t, o, err in iter_lines(path):
        if err or o is None:
            continue
        if o.get("v") == 2:
            out.append(o)
            if o.get("provenance") == "imported":
                has_import = True
        elif "v" not in o:
            out.append(upgrade_v1(o, i, base))
    if raw:
        return out
    if has_import:
        out = [e for e in out if not (e.get("upgraded_from") == 1 and e.get("provenance") == "backfilled")]
    km = load_keymap() if keymap is None else keymap
    if km:
        out = [apply_keymap(e, km) for e in out]
    return out


# ------------------------------------------------------------------------------------------------------------------
# step 5: the key map (one subject naming: the version-registry KEY)

KEYMAP_FILE = "events-keymap.json"


def load_keymap(path=None):
    """The key map, by role events-keymap (EVENTS_KEYMAP overrides, for tests); {} when there is none."""
    try:
        p = path or os.environ.get("EVENTS_KEYMAP") or role_path("events-keymap")
        with open(p, "r", encoding="utf-8-sig") as fh:
            return json.load(fh)
    except (OSError, ValueError, subprocess.SubprocessError):
        return {}


def keymap_lookup(km, name, version=None):
    if not km or not name:
        return None
    k = (km.get("names") or {}).get(name)
    if k:
        return k
    return ((km.get("by_version") or {}).get(name) or {}).get(version or "")


def apply_keymap(e, km):
    sub = e.get("subject") or {}
    if sub.get("key") or not sub.get("display"):
        return e
    k = keymap_lookup(km, sub.get("display"), sub.get("version"))
    if not k:
        return e
    e = dict(e)
    e["subject"] = dict(sub, key=k, key_from="keymap")
    return e


VERSION_TAIL = re.compile(r"\s+v?\d+\.\d+\.\d+$")


def build_keymap(names_versions, registry, ledger_rows):
    """Every subject name -> the registry key, by rules that read the registry and the ledger, never a guess:
      identity  - the name IS a registry key, repo, display name or alias (ignoring case), of exactly one entry;
      ledger    - the name is a key the version ledger still uses (a mod whose registry key changed since);
      then the same two after stripping ' - Debug Symbols' and/or a trailing version ('Dragon's Eye Minimap 1.6.4');
      by_version - a name shared by several entries (one display name across games) maps per version, when exactly one
                   of those entries has a ledger row with that version.
    Anything else is listed, unmapped."""
    ident = collections.defaultdict(dict)   # lower name -> {key: the registry field it matched}
    for k, e in registry.items():
        for field, vals in (("key", [k]), ("repo", [e.get("repo")]), ("displayName", [e.get("displayName")]),
                            ("alias", list(e.get("aliases") or []))):
            for n in vals:
                if n:
                    ident[n.lower()].setdefault(k, field)
    ledger_keys = collections.defaultdict(set)
    versions_of = collections.defaultdict(set)
    for r in ledger_rows:
        if r.get("mod"):
            ledger_keys[r["mod"].lower()].add(r["mod"])
            versions_of[r["mod"]].add(r.get("version"))

    def cands(n):
        c = dict(ident.get(n.lower(), {}))
        if not c:
            c = {k: "ledger-key" for k in ledger_keys.get(n.lower(), set())}
        return c

    names, rules, by_version, ambiguous, unmapped = {}, {}, {}, {}, []
    for name in sorted(names_versions):
        variants = [(name, "", None)]
        if name.endswith(" - Debug Symbols"):
            variants.append((name[:-len(" - Debug Symbols")], " (debug-symbols suffix)", None))
        for base_n, why, _v in list(variants):
            m = VERSION_TAIL.search(base_n)
            if m:
                variants.append((base_n[:m.start()], why + " (version in the name)", m.group(0).strip().lstrip("v")))
        found = None
        for v, why, tail_ver in variants:
            c = cands(v)
            if c:
                found = (c, why, tail_ver)
                break
        if not found:
            unmapped.append(name)
            continue
        c, why, tail_ver = found
        if len(c) == 1:
            k, field = next(iter(c.items()))
            names[name] = k
            rules[name] = field + why
            continue
        if tail_ver:   # a shared name that carries its own version: the one entry with a ledger row of that version
            hit = [k for k in c if tail_ver in versions_of.get(k, set())]
            if len(hit) == 1:
                names[name] = hit[0]
                rules[name] = "%s%s, the only one of %s with a ledger row %s" % (c[hit[0]], why, "/".join(sorted(c)), tail_ver)
                continue
        per, left = {}, []
        for ver in sorted(x for x in names_versions[name] if x):
            hit = [k for k in c if ver in versions_of.get(k, set())]
            if len(hit) == 1:
                per[ver] = hit[0]
            else:
                left.append(ver)
        if per:
            by_version[name] = per
        if left or "" in names_versions[name] or not per:
            ambiguous[name] = {"keys": sorted(c), "unresolved_versions": left,
                               "events_without_version": "" in names_versions[name]}
    return {"names": names, "rules": rules, "by_version": by_version, "ambiguous": ambiguous, "unmapped": unmapped}


def cmd_keymap(a):
    log = log_path(a.log)
    nv = collections.defaultdict(set)
    for e in read_events(log, keymap={}, raw=True):
        sub = e.get("subject") or {}
        for n in (sub.get("display"), sub.get("key")):
            if n:
                nv[n].add(sub.get("version") or "")
    registry = json.load(open(role_path("version-registry"), encoding="utf-8-sig"))
    ledger = load_ledger_rows(role_path("version-ledger"))
    km = build_keymap(nv, registry, ledger)
    km = {"_about": "subject name -> version-registry key, applied by events.py on read (SIMPLIFY-3 step 5); built by "
                    "`events.py keymap --build` from the registry and the version ledger - edit by rebuilding, never by hand",
          "_built": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), **km}
    out = a.out or os.path.join(HERE, KEYMAP_FILE)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(km, ensure_ascii=False, indent=1, sort_keys=False) + "\n")
    sys.stdout.write("%d name(s) mapped, %d mapped per version, %d ambiguous, %d unmapped -> %s\n"
                     % (len(km["names"]), len(km["by_version"]), len(km["ambiguous"]), len(km["unmapped"]), out))
    return 0


# ------------------------------------------------------------------------------------------------------------------
# step 5: the import - one `imported` event per ledger row

IMPORT_TS_FIELD = {"version-ledger": "recorded", "version-ledger-prerelease": "archived", "gate-ledger": "recorded",
                   "falsification-log": "opened"}


def _local_ts(text):
    try:
        d = datetime.datetime.fromisoformat(str(text))
    except (TypeError, ValueError):
        d = None
    if d is None:
        return None
    return d if d.tzinfo else d.astimezone()


def import_events(view, rows, registry, km, seq):
    spec = LEDGER_VIEWS[view]
    out = []
    for i, r in enumerate(rows):
        d = _local_ts(r.get(IMPORT_TS_FIELD[view])) or datetime.datetime(2026, 8, 24).astimezone()
        refs = {"source": "%s#%d" % (spec["file"], i)}
        if view in ("version-ledger", "version-ledger-prerelease"):
            key = r.get("mod")
            disp = (registry.get(key) or {}).get("displayName")
            ver = r.get("version")
            if view == "version-ledger-prerelease":
                kind, refs["prerelease"] = "withdraw", True
            else:
                kind = "withdraw" if r.get("status") == "withdrawn" else "build"
            outcome = r.get("status") or ""
            if r.get("sha256"):
                refs["sha256"] = r["sha256"]
        elif view == "gate-ledger":
            disp, ver = r.get("subject"), None
            key = keymap_lookup(km, disp)
            kind, outcome = "verdict", str(r.get("verdict") or "")
            refs["verdict_id"] = r.get("id")
        else:
            disp, ver = r.get("mod"), None
            key = keymap_lookup(km, disp)
            kind = "episode-close" if r.get("status") == "closed" else "episode-open"
            outcome = str(r.get("outcome") or r.get("status") or "")
            refs["episode_id"] = r.get("id")
        seq[0] += 1
        o = {"v": 2, "id": "%s-%04x" % ((d + datetime.timedelta(microseconds=seq[0] % 1000000)).strftime("%Y%m%dT%H%M%S%f"), seq[0] % 65536),
             "ts": d.isoformat(), "stage": None, "kind": kind, "event": "imported %s row" % view, "outcome": outcome,
             "subject": {"key": key or None, "display": disp or None, "version": ver or None, "game": None},
             "note": "", "evidence": str(r.get("evidence") or ""), "refs": refs, "by": "events.py stage-import",
             "session": None, "provenance": "imported", "row": r}
        errs = schema_errors(o)
        if errs:
            raise ValueError("%s row %d: %s" % (view, i, "; ".join(errs)))
        out.append(o)
    return out


def cmd_stage_import(a):
    """Builds the staged import file from the four ledgers (by role, or from --from-dir holding copies with the same
    file names, e.g. the frozen baseline). Never touches the log."""
    registry = json.load(open(role_path("version-registry"), encoding="utf-8-sig"))
    km = load_keymap(a.keymap) if a.keymap else load_keymap()
    seq = [0]
    lines, counts = [], {}
    for view, spec in LEDGER_VIEWS.items():
        p = os.path.join(a.from_dir, spec["file"]) if a.from_dir else role_path(spec["role"])
        rows = load_ledger_rows(p) if os.path.exists(p) else []
        evs = import_events(view, rows, registry, km, seq)
        counts[view] = len(evs)
        lines.extend(evs)
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        for o in lines:
            fh.write(dumps(o) + "\n")
    sys.stdout.write("staged %d imported event(s) -> %s  (%s)\n"
                     % (len(lines), a.out, ", ".join("%s %d" % kv for kv in counts.items())))
    return 0


def stats_events(events):
    """Statistics' view (section 5 item 3): an imported row counts only when no live event has the same (key, version,
    outcome) - the same build recorded once by its live event and once by the import is one build."""
    def ident(e):
        sub = e.get("subject") or {}
        # a subject with no key (a verdict on a mod that is not ours) is compared by its name, never as "None"
        who = sub.get("key") or ("name", (sub.get("display") or "").lower())
        return (who, sub.get("version"), e.get("outcome"))

    # Step 7 (2026-10-12): a "ledger row: ..." event is the VIEW's storage - the row version-gate (or materialize)
    # wrote - not an occurrence. version-gate also writes its own stage line ("build working", "posted") for the same
    # change, so counting both would count one build twice. Those events never count; the stage line does.
    events = [e for e in events if not is_storage_event(e)]
    live = {ident(e) for e in events if e.get("provenance") == "live"}
    return [e for e in events if e.get("provenance") != "imported" or ident(e) not in live]


def is_storage_event(e):
    """Not an occurrence: a "ledger row" event (the view's storage) or a reconstructed event with refs.about - a reason
    recovered (step 6) or marked unknown (step 7) FOR an earlier refusal, which is itself the occurrence."""
    if e.get("provenance") == "live" and str(e.get("event") or "").startswith("ledger row"):
        return True
    return e.get("provenance") == "reconstructed" and bool((e.get("refs") or {}).get("about"))


# ------------------------------------------------------------------------------------------------------------------
# record


class Lock(object):
    def __init__(self, path):
        self.path = path + ".lock"
        self.held = False

    def acquire(self, wait=LOCK_WAIT):
        deadline = time.monotonic() + wait
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, ("%d %s\n" % (os.getpid(), datetime.datetime.now().isoformat())).encode("ascii"))
                os.close(fd)
                self.held = True
                return True
            except FileExistsError:
                try:
                    if time.time() - os.path.getmtime(self.path) > LOCK_STALE:
                        os.remove(self.path)
                        continue
                except OSError:
                    pass
            except PermissionError:
                pass   # Windows: the lock file is being deleted by its holder
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.05)

    def release(self):
        if self.held:
            try:
                os.remove(self.path)
            except OSError:
                pass
            self.held = False


def _append_bytes(path, payload):
    """Append bytes, first adding a line end if the file does not end with one (a crash can cut a line)."""
    lead = b""
    if os.path.exists(path) and os.path.getsize(path) > 0:
        with open(path, "rb") as fh:
            fh.seek(-1, os.SEEK_END)
            if fh.read(1) != b"\n":
                lead = b"\n"
    with open(path, "ab") as fh:
        fh.write(lead + payload)
        fh.flush()
        os.fsync(fh.fileno())


def merge_spill(log):
    """Called with the lock held. The spill is renamed first so a writer spilling right now starts a new one."""
    spill = log + ".spill"
    if not os.path.exists(spill):
        return 0
    taking = "%s.merging.%d" % (spill, os.getpid())
    os.replace(spill, taking)
    with open(taking, "rb") as fh:
        data = fh.read()
    lines = [ln.rstrip(b"\r") for ln in data.split(b"\n") if ln.strip()]
    if lines:
        _append_bytes(log, b"\n".join(lines) + b"\n")
    os.remove(taking)
    return len(lines)


def build_event(a):
    """The v2 object from parsed arguments, or raises ValueError (-> exit 2)."""
    payload = {}
    if a.payload_file:
        try:
            with open(a.payload_file, "r", encoding="utf-8-sig") as fh:
                payload = json.load(fh)
        except (OSError, ValueError) as e:
            raise ValueError("--payload-file unreadable: %s" % e)
        if not isinstance(payload, dict):
            raise ValueError("--payload-file must hold a JSON object")

    def pick(name):
        v = getattr(a, name, None)
        return v if v is not None else payload.get(name)

    event = pick("event")
    kind = pick("kind")
    if not kind:
        raise ValueError("--kind is required (one of %s, or auto)" % ", ".join(KINDS))
    if kind == "auto":
        if not event:
            raise ValueError("--kind auto needs --event")
        kind = kind_for_label(event)
    elif kind not in KINDS:
        raise ValueError("unknown kind %r (allowed: %s)" % (kind, ", ".join(KINDS)))
    stage = pick("stage")
    if stage in ("", None):
        stage = None
    else:
        try:
            stage = int(stage)
        except (TypeError, ValueError):
            raise ValueError("--stage must be 1-12")
        if not 1 <= stage <= 12:
            raise ValueError("--stage must be 1-12")
    prov = pick("provenance") or "live"
    if prov not in PROVENANCE:
        raise ValueError("unknown provenance %r (allowed: %s)" % (prov, ", ".join(PROVENANCE)))
    refs = {}
    refs_json = a.refs_json if a.refs_json is not None else None
    if refs_json is not None:
        try:
            refs = json.loads(refs_json)
        except ValueError as e:
            raise ValueError("--refs-json is not JSON: %s" % e)
    elif isinstance(payload.get("refs"), dict):
        refs = dict(payload["refs"])
    if not isinstance(refs, dict):
        raise ValueError("--refs-json must be a JSON object")
    # step 4: a payload may add refs as JSON TEXT (refs_json) - how pipeline-log passes a caller's refs untouched
    if payload.get("refs_json"):
        try:
            extra = json.loads(payload["refs_json"])
        except (TypeError, ValueError) as e:
            raise ValueError("refs_json is not JSON: %s" % e)
        if not isinstance(extra, dict):
            raise ValueError("refs_json must be a JSON object")
        refs.update(extra)
    # step 4: the whole ledger row a mirror event carries, as an object (row) or as JSON text (row_json / --row-json)
    row = None
    row_text = a.row_json if getattr(a, "row_json", None) is not None else payload.get("row_json")
    if row_text:
        try:
            row = json.loads(row_text)
        except (TypeError, ValueError) as e:
            raise ValueError("row JSON is not JSON: %s" % e)
    elif payload.get("row") is not None:
        row = payload["row"]
    if row is not None and not isinstance(row, dict):
        raise ValueError("row must be a JSON object")
    reasons = a.reasons if a.reasons else payload.get("reasons")
    if reasons is not None and (not isinstance(reasons, list) or not all(isinstance(x, str) for x in reasons)):
        raise ValueError("reasons must be strings")
    ts = pick("ts")
    if ts:
        try:
            d = datetime.datetime.fromisoformat(ts)
        except ValueError:
            raise ValueError("--ts is not ISO 8601: %r" % ts)
        if d.tzinfo is None:
            d = d.astimezone()
            ts = d.isoformat()
    else:
        d = datetime.datetime.now().astimezone()
        ts = d.isoformat()
    outcome = pick("outcome")
    if outcome is None:
        outcome = outcome_for_label(event or "")
    outcome = str(outcome)
    if kind == "gate" and outcome == "fail" and not reasons:
        reasons = reasons_from_note(pick("note") or "")

    session = pick("session")
    if session is None:
        session = os.environ.get("CLAUDE_CODE_SESSION_ID") or None

    def s(name):
        v = pick(name)
        return "" if v is None else str(v)

    def n(name):
        v = pick(name)
        return None if v in (None, "") else str(v)

    o = {
        "v": 2,
        "id": "%s-%s" % (d.strftime("%Y%m%dT%H%M%S%f"), secrets.token_hex(2)),
        "ts": ts,
        "stage": stage,
        "kind": kind,
        "event": event or kind,
        "outcome": outcome,
        "subject": {"key": n("key"), "display": n("display"), "version": n("version"), "game": n("game")},
        "note": s("note"),
        "evidence": s("evidence"),
        "refs": refs,
        "by": s("by") or "interactive",
        "session": session,
        "provenance": prov,
    }
    if reasons:
        # placed after `subject`, where section 3 lists it; absent when there are none
        items = list(o.items())
        o = dict(items[:8] + [("reasons", list(reasons))] + items[8:])
    if row is not None:
        o["row"] = row
    errs = schema_errors(o)
    if errs:
        raise ValueError("; ".join(errs))
    return o


def cmd_record(a):
    try:
        o = build_event(a)
    except ValueError as e:
        sys.stdout.write("REFUSED %s\n" % e)
        return 2
    line = (dumps(o) + "\n").encode("utf-8")
    try:
        log = log_path(a.log)
        lock = Lock(log)
        if not lock.acquire():
            _append_bytes(log + ".spill", line)
            warn("could not take %s within %.0f s - event %s went to %s.spill; the next record merges it"
                 % (lock.path, LOCK_WAIT, o["id"], os.path.basename(log)))
            sys.stdout.write(o["id"] + "\n")
            return 0
        try:
            merged = merge_spill(log)
            _append_bytes(log, line)
        finally:
            lock.release()
        if merged:
            warn("merged %d spilled event(s) into %s" % (merged, os.path.basename(log)))
        sys.stdout.write(o["id"] + "\n")
    except Exception as e:   # the caller is packaging a mod or running a gate: a log that cannot write never fails it
        warn("could not record this event: %s: %s" % (type(e).__name__, e))
    return 0


def _append_lines_locked(log, lines):
    """Append several event lines under one lock (spill if the lock cannot be taken). Returns 'appended'/'spilled'."""
    payload = b"".join(lines)
    lock = Lock(log)
    if not lock.acquire():
        _append_bytes(log + ".spill", payload)
        warn("could not take %s within %.0f s - %d event(s) went to %s.spill; the next record merges them"
             % (lock.path, LOCK_WAIT, len(lines), os.path.basename(log)))
        return "spilled"
    try:
        merged = merge_spill(log)
        _append_bytes(log, payload)
    finally:
        lock.release()
    if merged:
        warn("merged %d spilled event(s) into %s" % (merged, os.path.basename(log)))
    return "appended"


def mirror_events(view, before_rows, after_rows, by, force=()):
    """Step 4 (dual write) for a tool that rewrites a whole ledger file (version-gate): one v2 event per row that is
    new or changed between BEFORE and AFTER (the row as now written, refs.source = <file>#<index in AFTER>), and one
    refs.removed event per row that is gone (the row as it was, index in BEFORE)."""
    spec = LEDGER_VIEWS[view]
    before = {}
    for i, r in enumerate(before_rows):
        before[_ident(r, spec)] = (i, r)
    seen = set()
    out = []
    now = datetime.datetime.now().astimezone()

    def make(kind, label, row, index, extra_refs):
        refs = {"source": "%s#%d" % (spec["file"], index)}
        if row.get("sha256"):
            refs["sha256"] = row["sha256"]
        refs.update(extra_refs)
        o = {
            "v": 2, "id": "%s-%s" % ((now + datetime.timedelta(microseconds=len(out))).strftime("%Y%m%dT%H%M%S%f"),
                                     secrets.token_hex(2)), "ts": now.isoformat(),
            "stage": None, "kind": kind, "event": label, "outcome": str(row.get("status") or ""),
            "subject": {"key": (str(row["mod"]) if row.get("mod") else None), "display": None,
                        "version": (str(row["version"]) if row.get("version") else None), "game": None},
            "note": "", "evidence": str(row.get("evidence") or ""), "refs": refs, "by": by,
            "session": os.environ.get("CLAUDE_CODE_SESSION_ID") or None, "provenance": "live", "row": row,
        }
        errs = schema_errors(o)
        if errs:
            raise ValueError("; ".join(errs))
        return o

    for i, r in enumerate(after_rows):
        k = _ident(r, spec)
        seen.add(k)
        old = before.get(k, (None, None))[1]
        if old == r and k not in force:
            continue
        if view == "version-ledger-prerelease":
            out.append(make("withdraw", "ledger row: archived before release", r, i, {"prerelease": True}))
        elif r.get("posted") and r.get("posted") != (old or {}).get("posted"):
            out.append(make("posted", "ledger row: posted", r, i, {}))
        elif (old or {}).get("posted") and not r.get("posted"):
            # version-gate's 'retract' (2026-10-25): the row's posted claim was wrong and is taken off; the whole row
            # (with its 'retracted' history) is the event's row, so the fold drops the claim like any other change
            out.append(make("posted-retracted", "ledger row: posted claim retracted", r, i, {"retracted": True}))
        elif r.get("status") == "withdrawn":
            out.append(make("withdraw", "ledger row: withdrawn", r, i, {}))
        else:
            out.append(make("build", "ledger row: %s" % (r.get("status") or ""), r, i, {}))
    for k, (i, r) in before.items():
        if k not in seen:
            out.append(make("withdraw", "ledger row removed", r, i, {"removed": True}))
    return out


# ------------------------------------------------------------------------------------------------------------------
# materialize (step 7, the switch-over): the log is the source, the ledger file is generated from it


MATERIALIZE_LOCK_WAIT = 20.0


def write_view_file(path, rows):
    """The view laid out the way the PowerShell writers wrote it: UTF-8 WITH a byte-order mark (Windows PowerShell 5.1
    reads BOM-less UTF-8 as cp1252), CRLF, 4-space indent, '"key":  value'. Written to a temp file and moved into
    place, so a reader never sees half a file."""
    text = json.dumps(rows, ensure_ascii=False, indent=4, separators=(",", ":  "))
    data = b"\xef\xbb\xbf" + text.replace("\n", "\r\n").encode("utf-8") + b"\r\n"
    tmp = "%s.materialize.%d" % (path, os.getpid())
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def materialize(view, proposed_rows, target, log, by):
    """Returns (code, message). 0 = the target was written FROM THE FOLD and reads back equal to proposed_rows.
    Any other code means nothing was written to the target; the caller then writes it the old way."""
    spec = LEDGER_VIEWS[view]
    lock = Lock(log)
    if not lock.acquire(MATERIALIZE_LOCK_WAIT):
        return 3, "could not take %s within %.0f s" % (lock.path, MATERIALIZE_LOCK_WAIT)
    try:
        merge_spill(log)
        fold = fold_ledger(read_events(log, raw=True), view)
        evs = mirror_events(view, fold, proposed_rows, by)
        if evs:
            _append_bytes(log, b"".join((dumps(o) + "\n").encode("utf-8") for o in evs))
        # ORDER (2026-10-13): the ROWS come from the log; their ORDER is the calling tool's. The fold sorts rows by the
        # position each had when last recorded, and version-gate rewrites a row by removing it and appending it, which
        # shifts every later row - so recorded positions go stale and re-recording them all would add hundreds of events
        # per record. Nothing reads a ledger by row order (check --view matches rows by identity), so the file is written
        # in the caller's order, every row taken from the fold; materialize still refuses unless the fold holds exactly
        # the caller's rows, field for field, and no identity twice. (Loot on Hover W3 1.0.0, 2026-10-13: the old
        # order repair re-recorded rows from the first visible difference only, rows before it kept stale positions,
        # and materialize refused with exit 4 - the ledger was written directly by the fallback.)
        folded = {_ident(r, spec): r for r in fold_ledger(read_events(log, raw=True), view)}
        idents = [_ident(r, spec) for r in proposed_rows]
        if len(set(idents)) != len(idents):
            return 4, "the rows to be written hold one identity twice (%d rows, %d identities)" % (len(idents), len(set(idents)))
        if set(folded) != set(idents) or any(folded[k] != r for k, r in zip(idents, proposed_rows)):
            diff = sorted(set(folded) ^ set(idents))[:3] or [k for k, r in zip(idents, proposed_rows) if folded.get(k) != r][:3]
            return 4, "the fold of %s differs from the rows to be written (%d folded, %d proposed; e.g. %s)" % (
                view, len(folded), len(proposed_rows), "; ".join(" ".join(k) for k in diff))
        fold = [folded[k] for k in idents]
        repaired = 0
        write_view_file(target, fold)
        if load_ledger_rows(target) != proposed_rows:
            return 5, "%s did not read back equal to the rows to be written" % target
        return 0, "%s: %d row(s) written from the log (%d new event(s)%s)" % (
            view, len(fold), len(evs), (", %d re-ordered" % repaired) if repaired else "")
    finally:
        lock.release()


def cmd_materialize(a):
    """Exit 0 only when the target was generated from the log. Any other exit leaves the target untouched for the
    calling tool to write directly - the switch-over's fallback, always reported, never silent."""
    if a.view not in LEDGER_VIEWS:
        sys.stdout.write("REFUSED unknown view %r\n" % a.view)
        return 2
    try:
        proposed = load_ledger_rows(a.proposed)
        target = os.path.abspath(a.target) if a.target else role_path(LEDGER_VIEWS[a.view]["role"])
        code, msg = materialize(a.view, proposed, target, log_path(a.log), a.by or "interactive")
    except Exception as e:
        code, msg = 6, "%s: %s" % (type(e).__name__, e)
    if code == 0:
        sys.stdout.write("materialize: %s\n" % msg)
    else:
        sys.stdout.write("materialize FAILED (%d): %s - the caller writes the file directly\n" % (code, msg))
    return code


IMPORT_PROVENANCE = ("reconstructed", "imported")


def cmd_import_staged(a):
    """Append a STAGED file of v2 events (step 5 imports, step 6 reconstructions) through the locked append path.
    All or nothing: every line is checked first, and one refused line refuses the file (exit 2, nothing written).
    A line is refused when it is not schema-valid v2, its provenance is not reconstructed/imported, its id is already in
    the log (a second import), or its refs.about points at no existing event - "<log file>#<line>" must be a parsable
    line of the log, anything else must be the id of an event in it (a v1 line's id as `read` gives it). A
    reconstructed line must carry refs.about."""
    log = log_path(a.log)
    base = os.path.basename(log)
    known_ids = {}   # id -> kind
    lines_ok = {}    # line number -> kind
    imported_sources = set()   # ledger rows already imported: a regenerated import must not land a second time
    for i, _t, o, err in iter_lines(log):
        if err or o is None:
            continue
        if o.get("v") == 2 and o.get("id"):
            known_ids[o["id"]] = o.get("kind")
            lines_ok[i] = o.get("kind")
            if o.get("provenance") == "imported" and (o.get("refs") or {}).get("source"):
                imported_sources.add(o["refs"]["source"])
        elif "v" not in o:
            up = upgrade_v1(o, i, base)
            known_ids[up["id"]] = up["kind"]
            lines_ok[i] = up["kind"]
    refused, staged, ids = [], [], set()
    current = {}
    for i, _t, o, err in iter_lines(a.file):
        if err:
            refused.append((i, err))
            continue
        errs = schema_errors(o) if o.get("v") == 2 else ["not a v2 event"]
        if o.get("provenance") not in IMPORT_PROVENANCE:
            errs.append("provenance %r is not one of %s" % (o.get("provenance"), "/".join(IMPORT_PROVENANCE)))
        if o.get("id") in known_ids or o.get("id") in ids:
            errs.append("id %s is already in the log (or twice in the file)" % o.get("id"))
        about = (o.get("refs") or {}).get("about")
        if about is None and o.get("provenance") == "reconstructed":
            errs.append("a reconstructed event needs refs.about")
        elif about is not None:
            # "<log file>#<line>" - the log's own name, or the role's file name when the log is a copy
            m = re.match(r"^(.+)#(\d+)$", str(about))
            if m and m.group(1) in (base, "pipeline-events.jsonl"):
                target = lines_ok.get(int(m.group(2)), "<none>")
            else:
                target = known_ids.get(about, "<none>")
            if target == "<none>":
                errs.append("about %s: no such event in the log" % about)
            elif target != o.get("kind"):
                errs.append("about %s: that event is kind %s, this one %s" % (about, target, o.get("kind")))
        if o.get("provenance") == "imported" and isinstance(o.get("row"), dict):
            src = (o.get("refs") or {}).get("source") or ""
            if src in imported_sources:
                errs.append("ledger row %s is already imported" % src)
            view = next((v for v, s in LEDGER_VIEWS.items() if src.rpartition("#")[0] == s["file"]), None)
            if view and not a.no_ledger_check:
                # the staged row must still BE the ledger's row: a write between staging and import would otherwise
                # let the older imported copy, appended later, win the fold over the newer mirror event
                if view not in current:
                    p = os.path.join(a.ledger_dir, LEDGER_VIEWS[view]["file"]) if a.ledger_dir else role_path(LEDGER_VIEWS[view]["role"])
                    current[view] = {_ident(r, LEDGER_VIEWS[view]): r for r in (load_ledger_rows(p) if os.path.exists(p) else [])}
                now_row = current[view].get(_ident(o["row"], LEDGER_VIEWS[view]))
                if now_row != o["row"]:
                    errs.append("%s: the ledger row %s since this import was staged - rebuild it (stage-import)"
                                % (src, "is gone" if now_row is None else "changed"))
        if errs:
            refused.append((i, "; ".join(errs)))
            continue
        ids.add(o["id"])
        staged.append((dumps(o) + "\n").encode("utf-8"))
    if refused:
        for i, e in refused[:30]:
            sys.stdout.write("  REFUSED line %d: %s\n" % (i, e))
        sys.stdout.write("IMPORT REFUSED - %d of %d line(s) refused; nothing written\n" % (len(refused), len(refused) + len(staged)))
        return 2
    if not staged:
        sys.stdout.write("nothing to import\n")
        return 0
    how = _append_lines_locked(log, staged)
    sys.stdout.write("imported %d event(s) into %s (%s)\n" % (len(staged), log, how))
    return 0


def cmd_mirror(a):
    """Never fails its caller: any problem is a warning and exit 0 (only bad arguments are exit 2)."""
    if a.view not in LEDGER_VIEWS:
        sys.stdout.write("REFUSED unknown view %r\n" % a.view)
        return 2
    try:
        before = load_ledger_rows(a.before) if a.before and os.path.exists(a.before) else []
        after = load_ledger_rows(a.after) if os.path.exists(a.after) else []
        evs = mirror_events(a.view, before, after, a.by or "interactive")
        if not evs:
            return 0
        log = log_path(a.log)
        _append_lines_locked(log, [(dumps(o) + "\n").encode("utf-8") for o in evs])
        sys.stdout.write("%d mirror event(s)\n" % len(evs))
    except Exception as e:
        warn("could not mirror %s: %s: %s" % (a.view, type(e).__name__, e))
    return 0


# ------------------------------------------------------------------------------------------------------------------
# read / fold / check


def _when(ts):
    try:
        d = datetime.datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return datetime.datetime.min
    if d.tzinfo is not None:
        d = d.astimezone().replace(tzinfo=None)
    return d


def cmd_read(a):
    path = log_path(a.log)
    evs = read_events(path, raw=a.raw)
    if a.stats:
        evs = stats_events(evs)
    for o in evs:
        sys.stdout.write(dumps(o) + "\n")
    return 0


def fold_stages(events):
    out = {}
    for s in range(1, 13):
        rows = [e for e in events if e.get("stage") == s]
        if not rows:
            out[s] = {"count": 0, "last": None, "last_event": None}
            continue
        last = max(enumerate(rows), key=lambda p: (_when(p[1].get("ts")), p[0]))[1]
        out[s] = {"count": len(rows), "last": _when(last.get("ts")).strftime("%m-%d"), "last_event": last.get("event")}
    return out


def _ident(row, spec):
    return tuple(json.dumps(row.get(k), sort_keys=True, ensure_ascii=False) for k in spec["identity"])


def fold_ledger(events, view):
    """A ledger rebuilt from its mirror events (step 4): per row identity, the LATEST event's `row`; a refs.removed
    event takes the row out. Rows come out in the order of their latest refs.source index (the file's order)."""
    spec = LEDGER_VIEWS[view]
    rows = {}
    for e in events:
        if e.get("v") != 2 or "upgraded_from" in e or not isinstance(e.get("row"), dict):
            continue
        refs = e.get("refs") or {}
        src, _, idx = str(refs.get("source") or "").rpartition("#")
        if os.path.basename(src.replace("\\", "/")).lower() != spec["file"].lower():
            continue
        ident = _ident(e["row"], spec)
        if refs.get("removed"):
            rows.pop(ident, None)
            continue
        try:
            i = int(idx)
        except ValueError:
            i = 10 ** 9
        rows[ident] = (i, e["row"])
    return [r for _i, r in sorted(rows.values(), key=lambda p: p[0])]


def load_ledger_rows(path):
    with open(path, "r", encoding="utf-8-sig") as fh:
        data = json.load(fh)
    out = []
    for item in (data if isinstance(data, list) else [data]):
        if isinstance(item, list):   # an old nested file ([[{..}]]), flattened the way the PS tools read it
            out.extend(item)
        elif item is not None:
            out.append(item)
    return out


def role_path(role):
    r = subprocess.run([sys.executable, RESOLVE_PY, "find", role], capture_output=True, text=True, timeout=30)
    lines = (r.stdout or "").strip().splitlines()
    m = re.match(r"^MISSING \S+ -> (.+)$", lines[0]) if lines else None
    if m:
        return m.group(1).strip()
    if r.returncode != 0 or not lines:
        raise OSError("resolve.py find %s failed: %s" % (role, (r.stdout + r.stderr).strip()))
    return lines[0].strip()


def check_view(view, log, real_file):
    """Step 4's check: every real row that has a mirror event must equal its folded row, field for field."""
    spec = LEDGER_VIEWS[view]
    real = load_ledger_rows(real_file) if os.path.exists(real_file) else []
    fold = fold_ledger(read_events(log, raw=True), view)
    folded = {_ident(r, spec): r for r in fold}
    seen = set()
    matched, differing, uncovered = 0, [], 0
    for i, r in enumerate(real):
        k = _ident(r, spec)
        seen.add(k)
        if k not in folded:
            uncovered += 1
        elif folded[k] == r:
            matched += 1
        else:
            f = folded[k]
            fields = sorted(x for x in set(r) | set(f) if r.get(x, "<absent>") != f.get(x, "<absent>"))
            differing.append((i, k, fields))
    extra = [k for k in folded if k not in seen]
    sys.stdout.write("%s: %d row(s) in %s, %d folded from the log\n" % (view, len(real), real_file, len(fold)))
    sys.stdout.write("  matched %d, differing %d, not yet covered %d, folded but not in the file %d\n"
                     % (matched, len(differing), uncovered, len(extra)))
    for i, k, fields in differing[:20]:
        sys.stdout.write("  DIFFERS row %d %s: %s\n" % (i, " ".join(k), ", ".join(fields)))
    for k in extra[:20]:
        sys.stdout.write("  EXTRA %s\n" % " ".join(k))
    return 1 if differing else 0


def last_event(events, kind, key=None, version=None, caller=None):
    """The latest event of `kind` whose subject is `key` (subject.key, or the display name of an event with no key) and
    `version`; None when there is none. Newest ts wins, ties by order in the log.
    `caller` (2026-10-22, gate C): only events whose refs.caller equals it - an event without refs.caller counts as
    "standalone" - so a standalone pre-finalize check's refusal is never the one a finalize run is compared against."""
    best = None
    for i, e in enumerate(events):
        if e.get("kind") != kind:
            continue
        if caller is not None and ((e.get("refs") or {}).get("caller") or "standalone") != caller:
            continue
        sub = e.get("subject") or {}
        if key is not None:
            k = sub.get("key")
            if not ((k and k.lower() == key.lower()) or (not k and (sub.get("display") or "").lower() == key.lower())):
                continue
        if version is not None and (sub.get("version") or "") != version:
            continue
        rank = (_when(e.get("ts")), i)
        if best is None or rank >= best[0]:
            best = (rank, e)
    return best[1] if best else None


def cmd_last(a):
    e = last_event(read_events(log_path(a.log)), a.kind, a.key, a.version, a.caller)
    if e is not None:
        sys.stdout.write(dumps(e) + "\n")
    return 0


def cmd_fold(a):
    path = log_path(a.log)
    if a.view in LEDGER_VIEWS:
        rows = fold_ledger(read_events(path, raw=True), a.view)
        sys.stdout.write(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
        return 0
    if a.view != "stages":
        sys.stdout.write("fold: views are stages, %s (asked: %s)\n" % (", ".join(LEDGER_VIEWS), a.view))
        return 2
    ev = read_events(path, raw=True)   # the stage view counts what pipeline-log summary counts, backfilled lines included
    st = fold_stages(ev)
    if a.json:
        sys.stdout.write(json.dumps({str(k): v for k, v in st.items()}, ensure_ascii=False) + "\n")
        return 0
    for s, r in st.items():
        if r["count"]:
            sys.stdout.write("%2d %5d event(s), last %s (%s)\n" % (s, r["count"], r["last"], r["last_event"]))
        else:
            sys.stdout.write("%2d NO EVENTS\n" % s)
    bf = sum(1 for e in ev if e.get("provenance") == "backfilled")
    sys.stdout.write("%d event(s); %d backfilled\n" % (len(ev), bf))
    return 0


def step3_report(live2):
    """Step 3's closing check, as a REPORT (never a failure): among the live v2 events, those that name a mod without
    its registry key, and intake events whose stage is not their folder's. The target is zero of both."""
    named = [(i, o) for i, o in live2 if (o.get("subject") or {}).get("display")]
    unmapped = [(i, o) for i, o in named if not (o.get("subject") or {}).get("key")]
    verdicts = sum(1 for _i, o in unmapped if o.get("kind") in ("verdict", "verdict-resolved"))
    intake = [(i, o) for i, o in live2 if o.get("kind") == "intake"]
    nofolder = [(i, o) for i, o in intake if not (o.get("refs") or {}).get("folder")]
    mismatch = []
    for i, o in intake:
        folder = (o.get("refs") or {}).get("folder")
        if folder:
            want = stage_of(folder)
            if want != o.get("stage"):
                mismatch.append((i, o.get("stage"), want, folder))
    sys.stdout.write("  step 3 report (not a failure) - %d live v2 event(s):\n" % len(live2))
    sys.stdout.write("    %d name a mod; %d of them without subject.key (%d are verdicts, whose subject is often a mod "
                     "outside the registry)\n" % (len(named), len(unmapped), verdicts))
    for i, o in unmapped[:10]:
        sys.stdout.write("      line %d: %s %r\n" % (i, o.get("event"), o["subject"].get("display")))
    sys.stdout.write("    %d intake event(s): %d stage differs from its folder's, %d carry no refs.folder\n"
                     % (len(intake), len(mismatch), len(nofolder)))
    for i, got, want, folder in mismatch[:10]:
        sys.stdout.write("      line %d: stage %s, folder %s is stage %s\n" % (i, got, folder, want))


def cmd_check(a):
    path = log_path(a.log)
    if getattr(a, "view", None):
        real = a.file or role_path(LEDGER_VIEWS[a.view]["role"])
        return check_view(a.view, path, real)
    base = os.path.basename(path)
    per_v = {}
    per_kind = {}
    bad = []
    live2 = []
    for i, _t, o, err in iter_lines(path):
        if err:
            bad.append((i, err))
            continue
        if "v" not in o:
            probs = []
            if not isinstance(o.get("ts"), str):
                probs.append("v1 line without a ts string")
            if not isinstance(o.get("event"), str):
                probs.append("v1 line without an event string")
            st = o.get("stage")
            if not (st is None or (isinstance(st, int) and 1 <= st <= 12)):
                probs.append("v1 stage %r" % (st,))
            if probs:
                bad.append((i, "; ".join(probs)))
                continue
            per_v["1"] = per_v.get("1", 0) + 1
            k = upgrade_v1(o, i, base)["kind"]
        elif o.get("v") == 2:
            errs = schema_errors(o)
            if errs:
                bad.append((i, "; ".join(errs)))
                continue
            per_v["2"] = per_v.get("2", 0) + 1
            k = o["kind"]
            if o.get("provenance") == "live":
                live2.append((i, o))
        else:
            bad.append((i, "unknown schema version %r" % (o.get("v"),)))
            continue
        per_kind[k] = per_kind.get(k, 0) + 1
    sys.stdout.write("%s: %d event(s)\n" % (path, sum(per_v.values())))
    sys.stdout.write("  per version: %s\n" % ", ".join("v%s %d" % (k, per_v[k]) for k in sorted(per_v)))
    sys.stdout.write("  per kind:\n")
    for k, c in sorted(per_kind.items(), key=lambda p: (-p[1], p[0])):
        sys.stdout.write("    %6d  %s\n" % (c, k))
    try:
        step3_report(live2)
    except Exception as e:   # a report: it never decides the check
        sys.stdout.write("  step 3 report unavailable: %s: %s\n" % (type(e).__name__, e))
    if bad:
        for i, e in bad[:50]:
            sys.stdout.write("  BAD line %d: %s\n" % (i, e))
        sys.stdout.write("CHECK FAILED - %d bad line(s)\n" % len(bad))
        return 1
    sys.stdout.write("CHECK OK\n")
    return 0


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    except (AttributeError, ValueError):
        pass
    p = argparse.ArgumentParser(prog="events.py", description="the pipeline's one event log")
    sub = p.add_subparsers(dest="cmd")

    r = sub.add_parser("record", help="append one v2 event")
    r.add_argument("--log")
    r.add_argument("--kind", help="one of: %s; or auto (from --event)" % ", ".join(KINDS))
    r.add_argument("--event")
    r.add_argument("--outcome")
    r.add_argument("--stage")
    r.add_argument("--key")
    r.add_argument("--display")
    r.add_argument("--version")
    r.add_argument("--game")
    r.add_argument("--note")
    r.add_argument("--evidence")
    r.add_argument("--by")
    r.add_argument("--provenance")
    r.add_argument("--reasons", action="append")
    r.add_argument("--refs-json", dest="refs_json")
    r.add_argument("--row-json", dest="row_json", help="the whole ledger row a mirror event carries (step 4)")
    r.add_argument("--ts", help="when it happened (default now); an offset-less time is taken as local")
    r.add_argument("--session")
    r.add_argument("--payload-file", dest="payload_file",
                   help="JSON object with any of the fields above (how pipeline-log passes text with quotes safely)")

    rd = sub.add_parser("read", help="print every event as v2 JSON lines")
    rd.add_argument("--log")
    rd.add_argument("--raw", action="store_true", help="no key map, backfilled lines kept")
    rd.add_argument("--stats", action="store_true", help="statistics' view: imported rows a live event already counts left out")
    km = sub.add_parser("keymap", help="build events-keymap.json (step 5)")
    km.add_argument("--build", action="store_true", required=True)
    km.add_argument("--log")
    km.add_argument("--out")
    si = sub.add_parser("stage-import", help="stage one imported event per ledger row (step 5); never touches the log")
    si.add_argument("--out", required=True)
    si.add_argument("--from-dir", dest="from_dir", help="read the ledgers from this folder (e.g. the frozen baseline)")
    si.add_argument("--keymap")
    f = sub.add_parser("fold", help="fold a view from the events")
    f.add_argument("view")
    f.add_argument("--log")
    f.add_argument("--json", action="store_true")
    c = sub.add_parser("check", help="validate every line")
    c.add_argument("--log")
    c.add_argument("--view", choices=sorted(LEDGER_VIEWS),
                   help="instead: compare that ledger's fold with the real file (step 4)")
    c.add_argument("--file", help="with --view: the ledger file to compare (default: its role)")
    im = sub.add_parser("import-staged", help="append a staged file of reconstructed/imported events (all or nothing)")
    im.add_argument("file")
    im.add_argument("--log")
    im.add_argument("--ledger-dir", dest="ledger_dir", help="compare imported rows with the ledgers in this folder (default: by role)")
    im.add_argument("--no-ledger-check", dest="no_ledger_check", action="store_true")
    mi = sub.add_parser("mirror", help="record one event per ledger row that changed between two copies (step 4)")
    mi.add_argument("--view", required=True)
    mi.add_argument("--before", help="the ledger as it was (absent = empty)")
    mi.add_argument("--after", required=True, help="the ledger as now written")
    mi.add_argument("--by")
    mi.add_argument("--log")
    ma = sub.add_parser("materialize", help="step 7: record what a ledger write changes, then write the ledger FROM the log")
    ma.add_argument("--view", required=True)
    ma.add_argument("--proposed", required=True, help="the rows the calling tool wants written (its old output)")
    ma.add_argument("--target", help="the ledger file to write (default: the view's role)")
    ma.add_argument("--by")
    ma.add_argument("--log")
    la = sub.add_parser("last", help="the latest event of a kind for one subject (mod key, version), as one JSON line")
    la.add_argument("--kind", required=True)
    la.add_argument("--key")
    la.add_argument("--version")
    la.add_argument("--caller", help="only events whose refs.caller is this (none = standalone); gate C, 2026-10-22")
    la.add_argument("--log")
    sg = sub.add_parser("stage", help="the stage (1-12 or null) each path sits in, one line per path")
    sg.add_argument("paths", nargs="+")

    try:
        a = p.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    if a.cmd == "record":
        return cmd_record(a)
    if not a.cmd:
        p.print_help()
        return 2
    try:
        return {"read": cmd_read, "fold": cmd_fold, "check": cmd_check, "stage": cmd_stage,
                "mirror": cmd_mirror, "import-staged": cmd_import_staged, "keymap": cmd_keymap,
                "stage-import": cmd_stage_import, "materialize": cmd_materialize, "last": cmd_last}[a.cmd](a)
    except OSError as e:
        sys.stdout.write("ERROR %s\n" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
