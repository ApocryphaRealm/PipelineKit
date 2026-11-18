r"""stage8-verdict-audit - the one-off list of stage-8 compatibility verdicts never checked against reality
(2026-10-27, pipeline assessment item 2b), written for the owner to pick which releases get a real check first.

    py -3 stage8-verdict-audit.py [--ledger F] [--out F]
      default out: 4. plans\pipeline-assessment-2026-10-27\STAGE8-AUDIT.md (role stage-plans + that folder)

One row per unresolved stage-8 verdict (held is null): id, date, subject, verdict, whether it carries a condition
(guard) and an evidence reference, and the start of its evidence text; sorted compatible-without-condition first, then
oldest first. Read-only on the ledger.
"""
import argparse, datetime, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MD = os.path.dirname(HERE)


def rows_of(path):
    with open(path, encoding="utf-8-sig") as f:
        d = json.load(f)
    return d if isinstance(d, list) else []


def build(rows):
    s8 = [r for r in rows if str(r.get("stage")) == "8" and r.get("held") is None]
    s8.sort(key=lambda r: (not ((r.get("verdict") or "").lower() == "compatible" and not r.get("guard")),
                           str(r.get("recorded") or "")))
    bare = sum(1 for r in s8 if (r.get("verdict") or "").lower() == "compatible" and not r.get("guard"))
    lines = ["# Stage-8 verdicts never checked against reality (generated %s by stage8-verdict-audit.py)"
             % datetime.date.today().isoformat(), "",
             "%d unresolved stage-8 verdicts; %d of them are 'compatible' with no condition (rule 58 asks for one). "
             "Each is a prediction until a test or a report could have contradicted it. Pick the releases to check "
             "for real first; a re-check is recorded with `gate-ledger.ps1 -Action resolve -Id <id> -Held:$true|$false "
             "-What \"...\"`, a new verdict with `-Guard` and `-EvidenceRef` (required since 2026-10-27)." % (len(s8), bare),
             "", "| # | Recorded | Subject | Verdict | Condition | Evidence ref | Evidence (start) |", "|---|---|---|---|---|---|---|"]
    for r in s8:
        ev = " ".join(str(r.get("evidence") or "").split())[:90].replace("|", "\\|")
        lines.append("| %s | %s | %s | %s | %s | %s | %s |" % (
            r.get("id"), str(r.get("recorded") or "")[:10], str(r.get("subject") or "").replace("|", "\\|"),
            r.get("verdict"), "yes" if r.get("guard") else "**none**", "yes" if r.get("evidence_ref") else "none", ev))
    return "\n".join(lines) + "\n", len(s8), bare


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default=os.path.join(HERE, "gate-ledger.json"))
    ap.add_argument("--out", default=os.path.join(os.path.dirname(MD), "4. plans", "pipeline-assessment-2026-10-27",
                                                  "STAGE8-AUDIT.md"))
    a = ap.parse_args(argv)
    text, n, bare = build(rows_of(a.ledger))
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("stage8-verdict-audit: %d unresolved stage-8 verdicts (%d compatible with no condition) -> %s" % (n, bare, a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
