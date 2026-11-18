r"""THE COMPATIBILITY EVIDENCE GATE (2026-10-27, pipeline assessment item 2b). A package passes only when its latest
stage-8 "compatible" verdict names evidence that still exists.

WHY: 102 stage-8 verdicts were never checked against reality and 60 of the 64 "compatible" ones carried no condition -
the compatibility stop passed on paper. gate-ledger.ps1 now refuses a compatible verdict without -Guard and an
-EvidenceRef that exists; this gate (gate-rules row compat-verdict-evidence-exists, run by package-gate at package and
finalize time) checks the reference is STILL there when the mod is packaged or finalized: the batch file, the test
request, or the record file it names.

The mod is the package folder's display name ('<Display> <X.Y.Z>[ FOMOD]'); its verdicts are gate-ledger rows at
stage 8 whose subject is that name. The latest one decides:
  - compatible / compatible-with-caveats with an evidence_ref that resolves      PASS
  - ... with an evidence_ref that no longer resolves                              FAIL
  - ... with no evidence_ref, recorded after the rule began (2026-10-28 on)        FAIL
  - ... with no evidence_ref, recorded before                                     PASS, LEGACY (listed by the audit,
                                                                                  4. plans\pipeline-assessment-2026-10-27\STAGE8-AUDIT.md)
  - conflict, or no stage-8 verdict at all                                        PASS (other gates own those)

    python compat-evidence-gate.py --path <package folder> [--repo <repo>]   exit 0 pass, 1 FAIL
Environment for tests: GATE_LEDGER (the ledger file), AGENT_BUS_DIR (the bus), COMPAT_PROJECT_ROOT (relative refs).
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MD = os.path.normpath(os.path.join(HERE, "..", ".."))
RULE_START = "2026-10-28"
COMPATIBLE = ("compatible", "compatible-with-caveats")
PKG_RE = re.compile(r"^(?P<name>.+?)\s+\d+\.\d+\.\d+(?:\s+FOMOD)?$", re.I)


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def ledger_rows():
    p = os.environ.get("GATE_LEDGER") or os.path.join(MD, "scripts", "gate-ledger.json")
    try:
        with open(p, encoding="utf-8-sig") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return []
    return d if isinstance(d, list) else []


def resolve_ref(ref):
    r = (ref or "").strip().strip('"')
    if not r:
        return None
    bus = os.environ.get("AGENT_BUS_DIR") or os.path.join(MD, "agent-bus")
    if re.fullmatch(r"B-\d{8}-\d{6}-[0-9a-f]{4}", r):
        p = os.path.join(bus, "test-requests", "batches", r + ".json")
        return p if os.path.isfile(p) else None
    if re.fullmatch(r"\d{8}-\d{6}-[A-Za-z0-9-]+-[0-9a-f]{4}", r):
        p = os.path.join(bus, "test-requests", r + ".json")
        return p if os.path.isfile(p) else None
    if os.path.isabs(r):
        return r if os.path.exists(r) else None
    root = os.environ.get("COMPAT_PROJECT_ROOT") or os.path.dirname(MD)
    p = os.path.join(root, r)
    return p if os.path.exists(p) else None


def judge(display, rows):
    """(passed, line)."""
    mine = [r for r in rows if str(r.get("stage")) == "8" and norm(r.get("subject")) == norm(display)]
    if not mine:
        return True, "PASS - no stage-8 verdict recorded for %s" % display
    last = max(mine, key=lambda r: (str(r.get("recorded") or ""), r.get("id") or 0))
    v = (last.get("verdict") or "").lower()
    if v not in COMPATIBLE:
        return True, "PASS - the latest stage-8 verdict for %s is %s (#%s)" % (display, v, last.get("id"))
    ref = last.get("evidence_ref")
    if ref:
        found = resolve_ref(ref)
        if found:
            return True, "PASS - verdict #%s (%s) rests on %s, which exists" % (last.get("id"), v, found)
        return False, ("FAIL - verdict #%s (%s) for %s names evidence that no longer exists: %s. Record the verdict "
                       "again on evidence that exists (gate-ledger.ps1 -Action record -Stage 8 ... -Guard ... "
                       "-EvidenceRef ...)" % (last.get("id"), v, display, ref))
    if str(last.get("recorded") or "") >= RULE_START:
        return False, ("FAIL - verdict #%s (%s) for %s has no evidence reference (required since 2026-10-27)"
                       % (last.get("id"), v, display))
    return True, ("PASS - LEGACY verdict #%s (%s, %s) for %s has no evidence reference - unverified, listed in the "
                  "stage-8 audit" % (last.get("id"), v, str(last.get("recorded"))[:10], display))


def main(argv):
    if "--path" not in argv or argv.index("--path") + 1 >= len(argv):
        print(__doc__)
        return 2
    pkg = argv[argv.index("--path") + 1]
    m = PKG_RE.match(os.path.basename(os.path.normpath(pkg)))
    display = m.group("name") if m else os.path.basename(os.path.normpath(pkg))
    ok, line = judge(display, ledger_rows())
    print("compat-evidence-gate: " + line)
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:                                  # noqa: BLE001
        pass
    sys.exit(main(sys.argv[1:]))
