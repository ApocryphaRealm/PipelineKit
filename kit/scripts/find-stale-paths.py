r"""Report project paths written in the documents that do not exist on disk.

Section 1 of optimize-project.ps1. It catches the one class of staleness a folder rename leaves
behind: a document still naming `<ROOT>\<old path>` after the folder moved.

Three things this got wrong before 2026-09-02, all of which made it cry wolf:

  * IT COUNTED THE WRONG STRING. The count came from `text.count("bug reports")` - the bare leaf -
    so every correct `2. Mod Types\bug reports` mention was counted as another stale reference.
    One prose mention was reported as 19.
  * IT SCANNED ONLY `.MD\*.md`, never `.MD\rules\*.md` - so the seven rules parts, which carry
    nearly every live path instruction in the project, were outside its scope entirely. A sweep
    that defines its own scope too narrowly and reports clean is this project's recurring failure
    (PROGRESS.md, 2026-08-27 - the icon audit skipping the root, the stage-name-only path scan);
    this was another instance of it.
  * IT DID NOT SAY WHERE. Without a line number every hit needed a grep before it could be judged,
    so the same handful of false positives were re-litigated on every run.

GOVERNING vs RECORD (rule 60). A governing document tells the pipeline what to do, so a dead path
in one is a live defect. A record document - PROGRESS.md, the assessments, the handoffs - is a
dated log of what happened, and the old name was the correct name at the time; rewriting history
there is worse than the inconsistency (rule 36 settled exactly this for `resources catalog`). So
hits in record documents are counted separately and never reported as actionable. The headline
total is the ACTIONABLE count, which is the number optimize-project.ps1 reads.
"""

import io, os, re, glob

ROOT = os.environ.get("PIPELINE_ROOT") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # kit
MD = os.path.join(ROOT, ".MD")

# Documents whose paths are LIVE INSTRUCTIONS - a dead path in one of these is a defect to fix.
# Everything else scanned is a record, reported separately as history.
#
# This list is rule 60's governing set plus one deliberate addition: every rules part (they ARE
# CLAUDE.md's content). AI-PIPELINE-REFERENCE.md was a second addition until it was archived on 2026-10-12
# (SIMPLIFY-4), with VERSION-RECONCILIATION.md; what follows explains why it had been here. The reference is not a governed document for
# docs-pipeline.ps1's purposes - it is not versioned, because it describes the pipeline rather than
# deciding it - but it is read as a current description rather than as a dated log, so a path in it
# that no longer exists misleads a reader today. The two lists answer different questions and are
# allowed to differ; if that ever stops being true, this comment is the place that says so.
GOVERNING = {
    "CLAUDE.md", "commands.md", "TRIAGE-CATEGORIES.md", "MACHINE-HEALTH.md",
    "PAST-MISTAKES-LIBRARY.md", "LOGIC-LIBRARY.md", "RESOURCES.md",
    "PREFLIGHT.md", "sub-agent-routing.md", "BANNED-WORDS.md", "DEFAULT-KEYS.md",
}

# Every real folder at depth 1 and 2, with its correct relative path.
real = {}
for d1 in os.listdir(ROOT):
    p1 = os.path.join(ROOT, d1)
    if not os.path.isdir(p1):
        continue
    real.setdefault(d1.lower(), d1)
    try:
        for d2 in os.listdir(p1):
            if os.path.isdir(os.path.join(p1, d2)):
                real.setdefault(d2.lower(), d1 + "\\" + d2)
    except PermissionError:
        pass

files = sorted(glob.glob(os.path.join(MD, "*.md")))
files += sorted(glob.glob(os.path.join(MD, "rules", "*.md")))
pat = re.compile(re.escape(os.path.basename(ROOT)) + r"\\([^`\s\)\]\|,;\"']+(?:[ ][^`\s\)\]\|,;\"']+)*)")

# A line carrying this marker - or sitting directly under one - is quoting a dead path deliberately.
EXEMPT = "<!-- stale-path: ok -->"


def scan(path):
    """-> {stale rel path: [correct path, [line numbers]]} for one document."""
    hits = {}
    with io.open(path, encoding="utf-8", errors="replace") as fh:
        previous = ""
        for lineno, line in enumerate(fh, 1):
            # Escape hatch, the same shape as rule 59's `<!-- amend-check: ok -->`: a document
            # sometimes QUOTES a dead path on purpose - the logic library's entry on Python
            # escape sequences quotes the very string whose `\b` became a backspace. Nothing a
            # scanner can see distinguishes that from a live instruction, so the document says
            # so itself, on the line or the one above it. An HTML comment renders as nothing.
            if EXEMPT in line or EXEMPT in previous:
                previous = line
                continue
            previous = line
            for m in pat.finditer(line):
                rel = m.group(1).rstrip(".,:;*_`")
                if not rel or rel.startswith("."):
                    continue
                if os.path.exists(os.path.join(ROOT, rel)):
                    continue
                # Does the LAST component exist somewhere else, under a different parent?
                correct = real.get(rel.split("\\")[-1].lower())
                if correct and correct.lower() != rel.lower():
                    hits.setdefault(rel, [correct, []])[1].append(lineno)
    return hits


def label(path):
    """-> (display name, is this a governing document)."""
    name = os.path.basename(path)
    if os.path.basename(os.path.dirname(path)) == "rules":
        return "rules\\" + name, True
    return name, name in GOVERNING


print("STALE PATH REFERENCES (path written does not exist on disk)")
print("=" * 78)

actionable = 0
historical = 0
historical_files = []

for f in files:
    hits = scan(f)
    if not hits:
        continue
    name, governing = label(f)
    n = sum(len(v[1]) for v in hits.values())
    if not governing:
        historical += n
        historical_files.append((name, n))
        continue
    actionable += n
    print("\n  %s   [governing - fix these]" % name)
    for wrong, (right, lines) in sorted(hits.items()):
        where = ", ".join("line %d" % l for l in lines[:6])
        if len(lines) > 6:
            where += ", +%d more" % (len(lines) - 6)
        print("      %-42s -> should be  %s" % (wrong, right))
        print("      %s" % where)

print("\n  %d stale reference(s) total" % actionable)

if historical:
    print("\n  %d further mention(s) in RECORD documents - counted separately, not to be rewritten:"
          % historical)
    for name, n in historical_files:
        print("      %-42s %dx" % (name, n))
    print("      A dated entry recorded the path that was correct on that date (rules 36 and 60).")
    print("      Read one before assuming: several are prose ABOUT a path that was already fixed.")
