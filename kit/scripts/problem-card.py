r"""problem-card - every non-trivial fix, build or design task starts as an equation (rule 56, amended 2026-11-16).

The owner, 2026-11-16 18:12: "it seems like most of our issues or problem solving throughout this whole pipeline is or
can be boiled down to something simple as a mathematical equation solving approach, like define the variables that
take part in the equation, define the relationships between the variables and how they interact within the equation,
and then produce the output for the equation. And it seems like we could standardize that somehow." (Approved 18:17.)

THE CARD - five parts, written BEFORE the work:
  INPUTS         each variable, with "source:" naming where its TRUE value comes from (the game skeleton, not the bone
                 guess; the shipped file, not the work folder; the live Nexus page)
  RELATIONSHIPS  how the inputs constrain each other
  OUTPUT         what we want
  CHECK          what proves the output right - mechanical where possible (a gate already is one)
  ASSUMPTIONS    everything not yet verified; this is where bugs hide, so it is attacked FIRST (it feeds
                 falsification-log's -Kills and -Rivals)

USAGE (role problem-card: resolve.py run problem-card ...)
  problem-card new   --task "<title>" [--area <topic>] [--dir <folder>]
                     writes a skeleton to .MD\problem-cards\<yyyy-mm-dd>-<slug>.md (never overwrites: -2, -3 ...)
  problem-card check <card>
                     exit 0 PASS; exit 3 REFUSED when a section is missing or empty, an INPUT has no "source:", a
                     skeleton placeholder is left, CHECK is empty, or ASSUMPTIONS says "none" without a reason;
                     exit 2 when the card cannot be read
  problem-card assumptions <card>
                     prints the ASSUMPTIONS one per line (what to attack first)

Limits the card does not remove: design taste (the owner's eye is the final term - option sheets exist for it) and
unknown unknowns (testing and falsification flush them out). Worked examples: the troubleshooting skill's
references\PROBLEM-CARD.md.
"""
import argparse, datetime, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DIR = os.path.normpath(os.path.join(HERE, "..", "problem-cards"))
SECTIONS = ("INPUTS", "RELATIONSHIPS", "OUTPUT", "CHECK", "ASSUMPTIONS")
PLACEHOLDER = "<fill"
HEAD_RE = re.compile(r"^#{2,3}\s*(?:\d+\.\s*)?([A-Za-z]+)\b")
BULLET_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
SOURCE_RE = re.compile(r"\bsource\s*:\s*(\S.*)", re.I)
NONE_RE = re.compile(r"^(none|nothing|n/a|na)\b", re.I)
ANGLE_RE = re.compile(r"<[^<>\n]*>")


def blank(text):
    """True when nothing but <angle placeholders>, the word 'source:' and punctuation is left (a copied template)."""
    rest = re.sub(r"\bsource\s*:", "", ANGLE_RE.sub("", text), flags=re.I)
    return not re.sub(r"[\W_]+", "", rest)

SKELETON = """# Problem card: {task}

<!-- PROBLEM-CARD | {date} | area: {area} -->
*Written before the work (rule 56). Check it: `resolve.py run problem-card check "{path}"`.*

## INPUTS
<!-- one line per variable; each names where its TRUE value comes from: the game skeleton not the bone guess, the
     shipped file not the work folder, the live page not the manifest -->
- <fill: input 1> - source: <fill: where its true value is read from>
- <fill: input 2> - source: <fill: where its true value is read from>

## RELATIONSHIPS
<!-- how the inputs constrain each other: what depends on what, what must equal what, which rule groups or orders them -->
- <fill: relationship>

## OUTPUT
<!-- what we want, stated so it can be compared with the CHECK -->
<fill: the output>

## CHECK
<!-- what proves the output right; a gate, a hash, a render, an in-game observation - mechanical where possible -->
<fill: the check>

## ASSUMPTIONS
<!-- everything not yet verified - attacked FIRST; each one is a candidate -Kills / -Rivals for falsification-log.
     "none" is accepted only with the reason every input was verified -->
- <fill: assumption>
"""


def slugify(text):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s[:60].rstrip("-")) or "card"


def cmd_new(a):
    task = (a.task or "").strip()
    if not task:
        print("problem-card: FAILED - --task is required")
        return 2
    folder = os.path.normpath(a.dir or DEFAULT_DIR)
    os.makedirs(folder, exist_ok=True)
    date = datetime.date.today().isoformat()
    base = "%s-%s" % (date, slugify(task))
    path = os.path.join(folder, base + ".md")
    n = 2
    while os.path.exists(path):
        path = os.path.join(folder, "%s-%d.md" % (base, n))
        n += 1
    text = SKELETON.format(task=task, date=date, area=(a.area or "-").strip() or "-", path=path)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("problem-card: wrote %s" % path)
    print("Fill the five parts, then: resolve.py run problem-card check \"%s\"" % path)
    return 0


def strip_comments(text):
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


def parse(text):
    """{SECTION: [lines]} for the five sections; other headings end a section."""
    body = strip_comments(text)
    out, cur = {}, None
    for line in body.splitlines():
        m = HEAD_RE.match(line)
        if m:
            name = m.group(1).upper()
            cur = name if name in SECTIONS else None
            if cur and cur not in out:
                out[cur] = []
            continue
        if cur:
            out[cur].append(line.rstrip())
    return {k: [l for l in v if l.strip()] for k, v in out.items()}


def items(lines):
    """Bullet items with their continuation lines folded in; plain text with no bullet is one item."""
    res = []
    for l in lines:
        if BULLET_RE.match(l) or not res:
            res.append(BULLET_RE.sub("", l, count=1).strip())
        else:
            res[-1] += " " + l.strip()
    return [r for r in res if r]


def problems(text):
    sec = parse(text)
    bad = []
    for s in SECTIONS:
        if s not in sec:
            bad.append("section %s is missing (the five parts: %s)" % (s, ", ".join(SECTIONS)))
        elif not sec[s]:
            bad.append("section %s is empty" % s)
    for s in SECTIONS:
        lines = sec.get(s, [])
        hit = next((l for l in lines if PLACEHOLDER in l), None)
        if hit:
            bad.append("section %s still holds a skeleton placeholder: %s" % (s, hit.strip()))
        elif lines and all(blank(it) for it in items(lines)):
            bad.append("section %s holds only template placeholders: %s" % (s, " ".join(items(lines))))
    for it in items(sec.get("INPUTS", [])):
        m = SOURCE_RE.search(it)
        if not m or blank(m.group(1)):
            bad.append('INPUT without a "source:" naming where its true value comes from: %s' % it)
    ass = items(sec.get("ASSUMPTIONS", []))
    if sec.get("ASSUMPTIONS"):
        joined = " ".join(ass).strip()
        m = NONE_RE.match(joined)
        if m:
            rest = joined[m.end():].strip(" .,:;-–—()")
            if len(rest.split()) < 3:
                bad.append('ASSUMPTIONS says "%s" without a reason - name what was verified that leaves nothing '
                           'unverified, or list what was not' % m.group(1))
    return bad, sec


def read_card(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return f.read()
    except OSError as e:
        print("problem-card: FAILED - cannot read %s (%s)" % (path, e))
        return None


def cmd_check(a):
    text = read_card(a.card)
    if text is None:
        return 2
    bad, sec = problems(text)
    if bad:
        print("problem-card: REFUSED %s" % a.card)
        for b in bad:
            print("  - %s" % b)
        print("Fill the card before the work: INPUTS (each with its source of truth), RELATIONSHIPS, OUTPUT, CHECK,")
        print("ASSUMPTIONS (what is not yet verified - it is attacked first).")
        return 3
    ins = items(sec["INPUTS"])
    ass = items(sec["ASSUMPTIONS"])
    print("problem-card: PASS %s" % a.card)
    print("  inputs %d, relationships %d, check: %s" % (len(ins), len(items(sec["RELATIONSHIPS"])),
                                                          " ".join(items(sec["CHECK"]))[:160]))
    print("  attack these first (each is a -Kills / -Rivals candidate):")
    for x in ass:
        print("    - %s" % x)
    return 0


def cmd_assumptions(a):
    text = read_card(a.card)
    if text is None:
        return 2
    for x in items(parse(text).get("ASSUMPTIONS", [])):
        print(x)
    return 0


def main(argv):
    p = argparse.ArgumentParser(prog="problem-card", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("new"); s.add_argument("--task", required=True); s.add_argument("--area"); s.add_argument("--dir")
    s = sub.add_parser("check"); s.add_argument("card")
    s = sub.add_parser("assumptions"); s.add_argument("card")
    a = p.parse_args(argv)
    return {"new": cmd_new, "check": cmd_check, "assumptions": cmd_assumptions}[a.cmd](a)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:                                    # noqa: BLE001
        pass
    sys.exit(main(sys.argv[1:]))
