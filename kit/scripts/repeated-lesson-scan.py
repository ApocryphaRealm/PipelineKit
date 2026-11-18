r"""Which lesson does the past-mistakes library hold three or more times with no gate behind it? (role repeated-lesson-scan)

WHY (2026-11-18): "Root Builder copies the deployed files back at exit" was in the library three times as entries
only, and was hit a fourth time - each entry was read as a new lesson, none became a refusing check. Logic 5 says a
mistake has two outputs, the lesson and the gate; this finds the lessons that kept coming back without the second.

How: every "## " heading of PAST-MISTAKES-LIBRARY.md is reduced to its subject terms (tool and component names:
multi-word capitalised names, CamelCase and acronyms, plus the subject words in its "(context, date)" tail). A term
in 3+ headings is a REPEATED lesson. It is COVERED when the gate corpus names it: gate-rules.json, the scripts in
scripts\gates, and the PreToolUse hook scripts in ~/.claude/settings.json. Uncovered repeats are listed with their
headings - each is a decision: write the gate, or add the term to repeated-lesson-scan-ignore.txt with why.

Usage: py -3 repeated-lesson-scan.py [--min 3] [--all] [--strict]   a review list; --strict exits 1 on an uncovered repeat
A term is a topic, not one lesson: a cluster (one mod's many bugs) is read for a lesson that repeats, never gated blindly.
"""
import argparse
import glob
import json
import os
import re
import sys

MD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(MD, "PAST-MISTAKES-LIBRARY.md")
IGNORE = os.path.join(MD, "scripts", "repeated-lesson-scan-ignore.txt")
STOP = set("""a an the and or of to in on at by for from with without into over under after before while when
whose its it is are was were be been not no one two three this that these those every each any all our we i he she
they you game mod mods new old first last same own real fix fixed build builds test tests testing""".split())


def terms(heading):
    h = re.sub(r"\s*\(([^()]*)\)\s*$", lambda m: " " + m.group(1), heading)   # keep the context tail's words
    h = re.sub(r"\d{4}-\d{2}-\d{2}", " ", h)
    out = set()
    for m in re.finditer(r"\b([A-Z][\w+.-]*(?:\s+[A-Z][\w+.-]*)+)\b", h):        # multi-word names: Root Builder
        w = [x for x in m.group(1).split() if x.lower() not in STOP]
        if len(w) >= 2:
            out.add(" ".join(w).lower())
    for m in re.finditer(r"\b([A-Za-z]*[a-z][A-Z]\w*|[A-Z]{2,}\w*|\w+\.(?:esp|dll|ini|exe|json|py|ps1))\b", h):
        out.add(m.group(1).lower())                                             # CamelCase, acronyms, file names
    return out


def corpus():
    parts = []
    for p in [os.path.join(MD, "scripts", "gate-rules.json")] + glob.glob(os.path.join(MD, "scripts", "gates", "*")):
        if os.path.isfile(p):
            parts.append(open(p, encoding="utf-8", errors="replace").read())
    try:
        s = json.load(open(os.path.expanduser(r"~/.claude/settings.json"), encoding="utf-8"))
        for m in s.get("hooks", {}).get("PreToolUse", []):
            for h in m.get("hooks", []):
                for f in re.findall(r'"([^"]+\.py)"', h.get("command", "")):
                    if os.path.isfile(f):
                        parts.append(open(f, encoding="utf-8", errors="replace").read())
    except Exception:
        pass
    return "\n".join(parts).lower()


ap = argparse.ArgumentParser()
ap.add_argument("--min", type=int, default=3)
ap.add_argument("--all", action="store_true", help="also list covered repeats")
ap.add_argument("--strict", action="store_true", help="exit 1 when an uncovered repeat is found")
a = ap.parse_args()

heads = []
in_index = False
for line in open(LIB, encoding="utf-8", errors="replace"):
    if line.startswith("<!-- INDEX:START"):
        in_index = True
    elif line.startswith("<!-- INDEX:END"):
        in_index = False
    elif line.startswith("## ") and not in_index:
        heads.append(line[3:].strip())
ignored = {}
if os.path.isfile(IGNORE):
    for line in open(IGNORE, encoding="utf-8"):
        t = line.split("#")[0].strip().lower()
        if t:
            ignored[t] = line.strip()
by = {}
for h in heads:
    for t in terms(h):
        by.setdefault(t, []).append(h)
gate = corpus()
rep = sorted(((t, hs) for t, hs in by.items() if len(hs) >= a.min and t not in ignored), key=lambda x: -len(x[1]))
uncovered = [(t, hs) for t, hs in rep if t not in gate]
for t, hs in rep:
    if t in gate and not a.all:
        continue
    print("%-9s %-28s %d entries" % ("covered" if t in gate else "NO GATE", t, len(hs)))
    if t not in gate:
        for h in hs[-4:]:
            print("            - " + h[:150])
print("repeated-lesson-scan: %d heading(s), %d term(s) repeated %d+ times, %d without a gate (%d ignored)"
      % (len(heads), len(rep), a.min, len(uncovered), len(ignored)))
sys.exit(1 if (uncovered and a.strict) else 0)
