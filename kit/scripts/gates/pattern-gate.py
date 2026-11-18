"""pattern-gate (role pattern-gate, 2026-11-16) - refuses an engraving pattern that patternlib's validators refuse.

    py -3 pattern-gate.py <pattern.json | folder> [...]

  * a pattern.json (written by patternlib) is RE-RENDERED at its own px per unit and re-validated - strand continuity,
    over-under alternation, strand width and gap in pixels, margin, coverage, symmetry, minimum feature, the layout
    rule, and for a weave the weave-scale and end-piece rules - so a hand-edited or stale pattern cannot pass on an old
    verdict;
  * a folder: every pattern.json in it (not recursive), and its engraving_check.json: each layout record that says
    "generator": "patternlib" must carry a patternlib verdict with ok true.
Prints "pattern-gate: FAIL - <path>: <reason>" per failure and exits 1; "pattern-gate: OK - ..." and exit 0 otherwise.
A folder with neither file FAILS (nothing to judge is not a pass). The engraving-layout gate refuses the same refused
records independently (its patternlib rule), so the design_gate.require() chain catches them too."""
import json, os, subprocess, sys
MD = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CLI = os.path.join(MD, "scripts", "art", "patternlib", "cli.py")


def check_pattern(p):
    r = subprocess.run([sys.executable, CLI, "--validate", p], capture_output=True, text=True)
    if r.returncode == 0: return []
    refs = [ln for ln in r.stdout.splitlines() if ln.startswith("REFUSED")] or [(r.stdout + r.stderr).strip()[-400:]]
    return ["%s: %s" % (p, x) for x in refs]


def check_record(p):
    try: d = json.load(open(p))
    except Exception as e: return ["%s: unreadable (%s)" % (p, e)], 0
    bad, n = [], 0
    for face, rec in (d.get("layouts") or {}).items():
        if not isinstance(rec, dict) or rec.get("generator") != "patternlib": continue
        n += 1; v = rec.get("patternlib")
        if not isinstance(v, dict): bad.append("%s: %s: generator patternlib but no verdict" % (p, face))
        elif not v.get("ok"): bad.append("%s: %s: %s" % (p, face, "; ".join(v.get("refusals") or ["refused"])))
    return bad, n


def main(argv):
    if not argv: print(__doc__); return 2
    bad, judged = [], 0
    for t in argv:
        if os.path.isfile(t):
            if t.lower().endswith("engraving_check.json"): b, n = check_record(t); bad += b; judged += n
            else: bad += check_pattern(t); judged += 1
            continue
        if not os.path.isdir(t): bad.append("%s: no such file or folder" % t); continue
        pats = sorted(f for f in os.listdir(t) if f.endswith("pattern.json"))
        for f in pats: bad += check_pattern(os.path.join(t, f)); judged += 1
        ec = os.path.join(t, "engraving_check.json")
        if os.path.isfile(ec): b, n = check_record(ec); bad += b; judged += n
        if not pats and not os.path.isfile(ec): bad.append("%s: no pattern.json and no engraving_check.json - nothing to judge" % t)
    for b in bad: print("pattern-gate: FAIL - " + b)
    if bad: return 1
    print("pattern-gate: OK - %d pattern(s) / record(s) pass patternlib's validators" % judged); return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
