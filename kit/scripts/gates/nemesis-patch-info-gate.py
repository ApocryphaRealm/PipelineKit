"""THE NEMESIS PATCH INFO GATE (2026-11-12, Simple Dodge 1.0.0 - Nexus bug 1171565 "Nemesis Crash").

Nemesis Unlimited Behavior Engine reads every Nemesis_Engine\\mod\\<code>\\info.ini when it starts (connector.cpp
readMod, called before the window opens and before a command-line -generate). A patch whose info.ini lacks a
non-empty name=, author= or site= line is refused with TBT 1014 ("Missing info in "info.ini" file. Please contact
the mod author / Mod: <code>") in a CRITITAL ERROR box, and Nemesis closes - for EVERY player with that mod
installed, whether or not the patch is ticked. Pandora accepts the same file, so a Pandora-only test never sees it.
Simple Dodge 1.0.0 shipped site= empty; reproduced with Nemesis 0.84 and fixed by filling it.

The rule, from Nemesis's own source (src/connector.cpp): a line starting name= / author= / site= sets that value
(text after the first '='); 'name.length() == 0 || author.length() == 0 || site.length() == 0' -> TBT 1014.
auto= and hidden= are optional. A first line carrying a UTF-8 BOM would hide its key, so a BOM is refused too.

Usage:
  python nemesis-patch-info-gate.py --path <package or repo folder>   every Nemesis_Engine\\mod\\*\\info.ini under it
  [--repo <repo>]                                                     accepted (package-gate passes it), also scanned
Exit 1 on any hit, 0 when every info.ini passes or there is none.
"""
import argparse, os, sys

REQUIRED = ("name", "author", "site")


def check_info(path):
    """-> list of problems for one info.ini, read the way Nemesis 0.84 reads it."""
    raw = open(path, "rb").read()
    problems = []
    if raw.startswith(b"\xef\xbb\xbf"):
        problems.append("starts with a UTF-8 BOM, which hides the first key from Nemesis")
    text = raw.decode("utf-8", "replace")
    values = {}
    for line in text.splitlines():
        line = line.strip("\r")
        for key in REQUIRED:
            if line.lower().startswith(key + "="):
                values[key] = line[line.find("=") + 1:]
    for key in REQUIRED:
        if key not in values:
            problems.append("no %s= line" % key)
        elif len(values[key]) == 0:
            problems.append("%s= is empty" % key)
    return problems


def find_infos(root):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "build", "node_modules")]
        parts = [p.lower() for p in os.path.normpath(dirpath).split(os.sep)]
        if len(parts) >= 3 and parts[-3] == "nemesis_engine" and parts[-2] == "mod":
            for f in filenames:
                if f.lower() == "info.ini":
                    out.append(os.path.join(dirpath, f))
    return sorted(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True)
    ap.add_argument("--repo")
    a = ap.parse_args()
    roots = [a.path] + ([a.repo] if a.repo and os.path.isdir(a.repo) else [])
    infos = []
    for r in roots:
        infos += find_infos(r)
    if not infos:
        print("OK: no Nemesis patch (Nemesis_Engine\\mod\\*\\info.ini) under %s" % " / ".join(roots))
        return 0
    bad = 0
    for p in infos:
        probs = check_info(p)
        code = os.path.basename(os.path.dirname(p))
        if probs:
            bad += 1
            print("FAIL: %s (patch %s): %s - Nemesis refuses it with TBT 1014 and closes; fill name=, author= and "
                  "site= (site = the mod's Nexus page)" % (p, code, "; ".join(probs)))
        else:
            print("OK: %s (patch %s)" % (p, code))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
