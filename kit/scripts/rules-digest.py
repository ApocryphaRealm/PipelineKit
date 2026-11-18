#!/usr/bin/env python3
"""rules-digest.py - generate .MD\\RULES-DIGEST.md, the one-page session-start read, from the seven rule parts.

The owner, 2026-09-07 ("let's take the middle path on the cut session start read"): every session reads
CLAUDE.md + this digest + PREFLIGHT.md, and reads a PART in full when work enters the stage it governs.

For every "## N. Title" rule heading across rules\\*.md this writes: the heading (with its part), the most
recent "> **Amended YYYY-MM-DD" line if the rule has one, and the rule's first sentences (capped). It is
DERIVED - never hand-edit the output; rules-version.ps1 -Action bump re-runs this script.
"""
import io, os, re, sys, glob, datetime

MD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES = os.path.join(MD, "rules")
OUT = os.path.join(MD, "RULES-DIGEST.md")
CAP = 320   # characters of lead text per rule

H_RE = re.compile(r"^## (\d+)\. (.+)$")
AMEND_RE = re.compile(r"^> \*\*Amended (\d{4}-\d{2}-\d{2})[^*]*\*\*[:\s]*(.*)$")
PART_RE = re.compile(r"<!-- RULES-PART: (\d+) \|")


def clean(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    return s


def lead_text(lines):
    """First paragraph of ordinary prose after the heading (skips amendment quotes, tables, code, blank)."""
    buf = []
    for l in lines:
        t = l.rstrip()
        if not t:
            if buf: break
            continue
        if t.startswith(">") or t.startswith("|") or t.startswith("```") or t.startswith("#"):
            if buf: break
            continue
        buf.append(t)
    s = clean(" ".join(buf))
    if len(s) > CAP:
        cut = s.rfind(". ", 0, CAP)
        s = s[:cut + 1] if cut > 80 else s[:CAP].rstrip() + " ..."
    return s


def main():
    entries = []
    for path in sorted(glob.glob(os.path.join(RULES, "*.md"))):
        text = io.open(path, "rb").read().decode("utf-8-sig")
        m = PART_RE.search(text)
        part = m.group(1) if m else os.path.basename(path)[:2]
        lines = text.split("\n")
        idx = [i for i, l in enumerate(lines) if H_RE.match(l)]
        for n, i in enumerate(idx):
            end = idx[n + 1] if n + 1 < len(idx) else len(lines)
            hm = H_RE.match(lines[i])
            body = lines[i + 1:end]
            amends = [(am.group(1), clean(am.group(2))) for l in body for am in [AMEND_RE.match(l)] if am]
            latest = max(amends) if amends else None
            entries.append((int(hm.group(1)), hm.group(2).strip(), part, latest, lead_text(body)))
    entries.sort()
    stamp = ""
    cl = io.open(os.path.join(MD, "CLAUDE.md"), "rb").read().decode("utf-8-sig")
    sm = re.search(r"<!-- RULES-VERSION: ([^|]+)\|", cl)
    if sm: stamp = sm.group(1).strip()
    out = [
        "# Rules digest - the one-page session-start read (GENERATED, do not edit)",
        "",
        f"<!-- generated {datetime.date.today().isoformat()} from rules v{stamp} by scripts\\rules-digest.py -->",
        "",
        "Read this with CLAUDE.md and PREFLIGHT.md at every session start (the owner, 2026-09-07: the middle path).",
        "When work enters a stage, read that stage's PART in full - the table in CLAUDE.md says which. A line here is",
        "the rule's heading, its latest dated amendment and its opening sentences; the rule itself is in its part.",
        "",
    ]
    for num, title, part, latest, lead in entries:
        out.append(f"**{num}. {title}** (part {part})")
        if latest:
            out.append(f"  - Amended {latest[0]}: {latest[1][:CAP]}" if latest[1] else f"  - Amended {latest[0]}")
        if lead:
            out.append(f"  - {lead}")
        out.append("")
    io.open(OUT, "w", encoding="utf-8", newline="\n").write("\n".join(out))
    size = os.path.getsize(OUT)
    print(f"RULES-DIGEST.md: {len(entries)} rules, {size // 1024} KB, ~{size // 4} tokens")
    return 0


if __name__ == "__main__":
    sys.exit(main())
