r"""root-topology-gate (role root-topology-gate): the visible project root is the twelve pipeline stages and nothing else.

The owner, 2026-10-27: "there's a lot of folders in the root of the Claude output that shouldn't be at the top level.
There should just be the 12 pipeline folders." Backups, quarantines, captures, scratch and tool sources had collected
beside the stages (rule 39 says the root IS the pipeline), because nothing refused them - each was put there by a
session that needed somewhere to put something.

The check, against the project root the resolver names:
  * every stage folder - each non-retired `stage-*` dir role whose folder sits directly in the root - must exist;
  * every other entry must be one of the role `root-tool-folders` (what tools need at the root: .MD, .tools, .claude,
    build temp folders ...) AND carry the Hidden attribute, so the root a person sees in Explorer is the twelve stages;
  * anything else - visible or hidden - FAILS: it belongs inside a stage or inside .MD, found by role
    (`resolve.py place` / `find`), never at the root.

Exit 0 OK, 1 FAIL (one line per offender, each starting FAIL), 2 the resolver could not be read.
package-gate runs it through the gate-rules row `root-holds-only-the-twelve-stages` (kind package-script-passes), so it
is called with --path <package> [--repo <repo>]; both are ignored - the root is what is checked.

Usage: py -3 root-topology-gate.py [--root <project root>] [--rosters <rosters folder>] [--path X] [--repo X]
"""
import argparse
import importlib.util
import os
import stat
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RESOLVE_PY = os.path.normpath(os.path.join(HERE, "..", "..", "resolvers", "resolve.py"))


def _load_resolver():
    spec = importlib.util.spec_from_file_location("resolve_for_root_gate", RESOLVE_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _hidden(entry):
    try:
        attrs = entry.stat(follow_symlinks=False).st_file_attributes
    except (AttributeError, OSError):
        return entry.name.startswith(".")
    return bool(attrs & stat.FILE_ATTRIBUTE_HIDDEN)


def check(root=None, rosters=None):
    """(exit code, report lines)"""
    try:
        rv = _load_resolver()
        ctx = rv.Ctx(rv.Rosters(rosters or os.path.join(os.path.dirname(RESOLVE_PY), "rosters")),
                     (root or rv.DEFAULT_ROOT).rstrip("\\/"), {})
    except Exception as e:  # the gate cannot be skipped by losing its resolver
        return 2, ["FAIL root-topology: cannot load the resolver at %s (%s)" % (RESOLVE_PY, e)]
    root = ctx.root
    norm = lambda p: os.path.normcase(os.path.normpath(p))
    stages = {}
    for name, body in ctx.rosters.roles.items():
        if not name.startswith("stage-") or body.get("kind") != "dir" or body.get("retired"):
            continue
        try:
            path, _ = ctx.resolve(name)
        except Exception:
            continue
        if norm(os.path.dirname(path)) == norm(root):
            stages[os.path.basename(path).lower()] = (name, os.path.basename(path))
    try:
        tools_value, _ = ctx.resolve("root-tool-folders")
        tools = {t.strip().lower() for t in tools_value.split("|") if t.strip()}
    except Exception as e:
        return 2, ["FAIL root-topology: role root-tool-folders cannot be read (%s)" % e]
    if not stages:
        return 2, ["FAIL root-topology: the rosters name no stage folder in %s" % root]

    fails, seen, hidden_tools = [], set(), 0
    try:
        entries = list(os.scandir(root))
    except OSError as e:
        return 2, ["FAIL root-topology: cannot list %s (%s)" % (root, e)]
    for e in sorted(entries, key=lambda x: x.name.lower()):
        key = e.name.lower()
        if key in stages:
            seen.add(key)
            continue
        if key in tools:
            if _hidden(e):
                hidden_tools += 1
            else:
                fails.append("FAIL root-topology: '%s' may stay at the root for the tools (role root-tool-folders), "
                             "but it is VISIBLE - set it Hidden (attrib +h)" % e.name)
            continue
        fails.append("FAIL root-topology: '%s' is not one of the twelve stages%s - move it by role into the stage or "
                     ".MD folder it belongs to (resolve.py place/find); the root holds only the stages"
                     % (e.name, " (and Hidden does not excuse it)" if _hidden(e) else ""))
    for key, (role, name) in sorted(stages.items()):
        if key not in seen:
            fails.append("FAIL root-topology: stage folder '%s' (role %s) is missing from %s" % (name, role, root))
    if fails:
        return 1, fails
    return 0, ["OK root-topology: %s holds the %d stages and %d hidden tool folder(s), nothing else"
               % (root, len(stages), hidden_tools)]


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root")
    ap.add_argument("--rosters")
    ap.add_argument("--path")   # package-gate passes the package; the root is what is checked
    ap.add_argument("--repo")
    a = ap.parse_args(argv)
    code, lines = check(a.root, a.rosters)
    print("\n".join(lines))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
