r"""Generate (or check) the index at the top of PAST-MISTAKES-LIBRARY.md.

WHY THIS EXISTS, AND WHY THE LIBRARY IS NOT SPLIT INTO PARTS THE WAY THE RULES ARE
---------------------------------------------------------------------------------
The rules split into seven parts because their retrieval key is known BEFORE you open them: you
know which pipeline stage you are in, so "load part 05 for testing" is a decision that is correct
every time. The past-mistakes library's key is a SYMPTOM, and the entry that saves you is routinely from a
different domain than the problem you are standing in - that is its own stated bar, and why its
entries are titled by symptom "so they can be found while investigating something unrelated".
A domain split would make the reader guess the domain of the answer before knowing the answer,
which is this project's recurring failure: a scan whose scope excludes the place the answer lives.

Worked example, 2026-09-02: the entry that explained damage to a C++ source file in a mod build was
a PYTHON string-handling entry. Under a domain split, nobody working on the build would have opened
it.

So the size problem is solved without moving anything. The index is one line per entry - the
heading (which in this library is already the lesson), its line number, and auto-derived topic
tags. Read ~90 lines, then open only the entries that look relevant, by line number.

USAGE
    python logic-index.py            # rewrite the index block in place
    python logic-index.py --check    # exit 1 if the block is stale (optimize-project.ps1 uses this)

The block is delimited by INDEX:START / INDEX:END HTML comments, so everything outside it - the
document's own prose, the versioning block, every entry - is untouched. Line endings are preserved
exactly: this file is LF (checked 2026-09-14 - an earlier note here said CRLF, and trusting it produced
a whole-file flip), and a wholesale flip would bury the next real diff (see the entry on exactly that).
"""

import io, re, sys, os

def resolve_doc():
    """Ask the resolver for the file that holds the role past-mistakes-library (step 9.1b)."""
    import subprocess
    here = os.path.dirname(os.path.abspath(__file__))
    resolver = os.path.join(here, "..", "resolvers", "resolve.py")
    try:
        r = subprocess.run(["py", "-3", resolver, "find", "past-mistakes-library"],
                           capture_output=True, text=True)
    except OSError as e:
        sys.exit("logic-index: cannot run the resolver for role past-mistakes-library: %s" % e)
    if r.returncode != 0 or not r.stdout.strip():
        sys.exit("logic-index: resolver failed for role past-mistakes-library (exit %d): %s"
                 % (r.returncode, (r.stderr or r.stdout).strip()))
    return r.stdout.strip().splitlines()[0]


if "--doc" in sys.argv:  # test hook: point at a fixture library; an explicit --doc wins over the lookup
    DOC = sys.argv[sys.argv.index("--doc") + 1]
else:
    DOC = resolve_doc()
# Step 12.13 (G6): an entry whose heading date is on or after this date must carry a Root cause line.
ROOT_CAUSE_REQUIRED_FROM = "2026-10-09"
ROOT_CAUSE_RE = re.compile(r"^\s*(?:- )?\*\*Root cause:\*\*", re.M)
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
START = "<!-- INDEX:START -->"
END = "<!-- INDEX:END -->"

# A tag is claimed when one of its patterns appears in the entry. Patterns are matched
# case-insensitively against the whole entry text, heading included. Keep them SPECIFIC: a tag that
# matches everything sorts nothing, and this index is only worth reading if its tags discriminate.
TAGS = {
    "mo2":        [r"\bMO2\b", r"Mod Organizer", r"modlist\.txt", r"plugins\.txt", r"usvfs", r"\bprofile\b"],
    "skyrim":     [r"SkyrimSE", r"\bSKSE\b", r"\bESP\b", r"\bESL\b", r"\bESM\b", r"Papyrus", r"\bcoc\b", r"load order"],
    "scaleform":  [r"Scaleform", r"\.swf\b", r"GetMember", r"ActionScript", r"\bAS2\b", r"HUDMenu", r"Infinity UI"],
    "cpp":        [r"CommonLibSSE", r"\bhook\b", r"trampoline", r"RELOCATION_ID", r"\bDLL\b", r"singleton", r"\.cpp\b", r"\.h\b"],
    "powershell": [r"PowerShell", r"\.ps1\b", r"Get-Content", r"Set-Content", r"splat", r"cmdlet", r"-LiteralPath"],
    "python":     [r"\bPython\b", r"\.py\b", r"\bPillow\b", r"raw string", r"universal newline"],
    "git":        [r"\bgit\b", r"commit", r"\bpush\b", r"\bdiff\b", r"line ending", r"\bCRLF\b"],
    "build":      [r"\bCMake\b", r"vcpkg", r"\bxmake\b", r"\bcl\.exe\b", r"\bbuild tree\b", r"rebuild", r"\blinker\b"],
    "packaging":  [r"package", r"\.zip\b", r"\.pdb\b", r"README", r"manifest", r"Nexus distro"],
    "versioning": [r"version number", r"version-ledger", r"FileVersion", r"\bbump\b", r"\btag\b.*\bv\d", r"rollover"],
    "testing":    [r"test build", r"in game", r"reproduce", r"bisect", r"control run", r"\bsave\b", r"launch"],
    "devbench":   [r"DevBench", r"/api/tool", r"\bMCP\b"],
    "settings":   [r"\bINI\b", r"setting", r"default", r"persist", r"keybind", r"toggle"],
    "logging":    [r"\blog\b", r"logger::", r"spdlog", r"trace level", r"log file"],
    "crash":      [r"crash", r"access violation", r"EXCEPTION_", r"\bdump\b", r"stack trace", r"\bhang\b"],
    "ui":         [r"\bmenu\b", r"minimap", r"compass", r"\bHUD\b", r"banner", r"\bfont\b", r"artwork"],
    "process":    [r"\brule \d+", r"pipeline", r"gate", r"\bqueue\b", r"handoff", r"sub-agent", r"watcher"],
    "licensing":  [r"licen[cs]e", r"\bMIT\b", r"\bGPL\b", r"\bLGPL\b", r"copyleft", r"permission"],
}
MAX_TAGS = 3

# The owner, 2026-11-10 19:36: "make sure your logging all the visual design work in its own index in the mistakes
# library". The entries stay in the one library (see the docstring for why it is not split); visual design work gets a
# SECOND index block of its own under the main one, listing every entry about modelling, texturing, engraving, renders
# and the owner's drawn marks. An entry is listed when it carries the topic "visual-design" on its Topics: line, or its
# heading/body matches enough of these patterns.
VISUAL_DESIGN = [r"\bBlender\b", r"\brender", r"engrav", r"\bcarv", r"knot", r"\bbraid", r"\bmesh", r"\bNIF\b",
                 r"\btextur", r"\bPBR\b", r"\bUVs?\b", r"\bbanner", r"silhouette", r"\boutline", r"\boverlay",
                 r"\bsword\b", r"\baxe\b", r"hammer", r"greatsword", r"\bweapon model", r"drawn", r"symmetr"]
VISUAL_DESIGN_MIN_HITS = 3


def is_visual_design(heading, body):
    m = re.search(r"^Topics:(.*)$", body, re.M)
    if m and "visual-design" in m.group(1):
        return True
    text = heading + "\n" + body
    return sum(1 for p in VISUAL_DESIGN if re.search(p, text, re.I)) >= VISUAL_DESIGN_MIN_HITS

# The owner, 2026-11-11 16:17: "add an index for animation work in the mistakes library". A THIRD index block, same
# mechanism as the visual design one: animation clips, behaviour files, skeletons, poses and the animation engines
# (Pandora, Nemesis, OAR, DAR). An entry is listed when it carries the topic "animation" on its Topics: line, or its
# heading/body matches enough of these patterns.
ANIMATION = [r"\banimation", r"\.hkx\b", r"\bhkx\b", r"\bbehaviou?r (graph|file|patch)", r"\bPandora\b", r"\bNemesis\b",
             r"\bdodge", r"\broll\b", r"\bpose\b", r"\bskeleton",
             r"\bIK\b", r"\bkeyfram", r"animmotion", r"motion data", r"\bclip\b", r"T-pose", r"\bstep dodge"]
ANIMATION_MIN_HITS = 3


def is_animation(heading, body):
    m = re.search(r"^Topics:(.*)$", body, re.M)
    if m and re.search(r"\banimation\b", m.group(1)):
        return True
    text = heading + "\n" + body
    return sum(1 for p in ANIMATION if re.search(p, text, re.I)) >= ANIMATION_MIN_HITS

HEADER = [
    "> **Index of the past-mistakes library - read this, then open only the entries you need.** Each line is an entry's heading",
    "> (which in this library is the lesson itself), the line it starts on, and its topics. Jump",
    "> straight to a line, or grep this block for a topic. Regenerate with",
    "> `python .MD\\scripts\\logic-index.py`; `optimize-project.ps1` fails section 6 when it is stale.",
    ">",
    "> The library is deliberately NOT split into parts the way the rules are. The rules are looked",
    "> up by pipeline stage, which you know before you open them; this file is looked up by SYMPTOM,",
    "> and its entries earn their place by applying to a problem in some OTHER domain. Splitting it",
    "> by domain would make you guess where the answer lives before you know what it is.",
    "",
]


def read(path):
    return io.open(path, encoding="utf-8", newline="").read()


def entries(text):
    """-> [(line number, heading text, body)] for every '## ' entry."""
    lines = text.replace("\r\n", "\n").split("\n")
    out = []
    for i, line in enumerate(lines):
        if line.startswith("## "):
            out.append([i + 1, line[3:].strip(), []])
        elif out:
            out[-1][2].append(line)
    return [(n, h, "\n".join(b)) for n, h, b in out]


def root_cause_report(text):
    """-> (failures, predating). An entry is exempt (predating) when its heading's last date is before
    ROOT_CAUSE_REQUIRED_FROM, or when it has no date. Otherwise it needs a '**Root cause:**' line."""
    failures, predating = [], 0
    for lineno, heading, body in entries(text):
        dates = DATE_RE.findall(heading)
        if not dates or dates[-1] < ROOT_CAUSE_REQUIRED_FROM:
            predating += 1
        elif not ROOT_CAUSE_RE.search(body):
            failures.append("NO ROOT CAUSE %d: %s" % (lineno, heading))
    return failures, predating


def tags_for(heading, body):
    text = heading + "\n" + body
    scored = []
    for tag, patterns in TAGS.items():
        hits = sum(len(re.findall(p, text, re.I)) for p in patterns)
        if hits:
            scored.append((hits, tag))
    scored.sort(key=lambda s: (-s[0], s[1]))
    return [t for _, t in scored[:MAX_TAGS]]


def build_index(text):
    rows = []
    for lineno, heading, body in entries(text):
        # An entry numbered "12. Something" already carries its number in the heading.
        tags = ", ".join(tags_for(heading, body)) or "-"
        rows.append("| %d | %s | %s |" % (lineno, heading.replace("|", "\\|"), tags))
    block = list(HEADER)
    block.append("| line | entry | topics |")
    block.append("|---:|---|---|")
    block.extend(rows)
    block.append("")
    block.append("*%d entries.*" % len(rows))
    vd = [(lineno, heading) for lineno, heading, body in entries(text) if is_visual_design(heading, body)]
    block.append("")
    block.append("### Visual design index - modelling, texturing, engraving, renders, the owner's drawn marks")
    block.append("")
    block.append("> Its own index (the owner, 2026-11-10). Read it before any weapon, armour, banner or render work, "
                 "with the skill `weapon-engraving`. Tag a new design entry `visual-design` on its Topics: line.")
    block.append("")
    block.append("| line | entry |")
    block.append("|---:|---|")
    block.extend("| %d | %s |" % (ln, h.replace("|", "\\|")) for ln, h in vd)
    block.append("")
    block.append("*%d visual design entries.*" % len(vd))
    an = [(lineno, heading) for lineno, heading, body in entries(text) if is_animation(heading, body)]
    block.append("")
    block.append("### Animation index - clips, poses, skeletons, behaviour files, Pandora / Nemesis / OAR")
    block.append("")
    block.append("> Its own index (the owner, 2026-11-11). Read it before any animation, dodge, behaviour-patch or "
                 "replacer work. Tag a new animation entry `animation` on its Topics: line.")
    block.append("")
    block.append("| line | entry |")
    block.append("|---:|---|")
    block.extend("| %d | %s |" % (ln, h.replace("|", "\\|")) for ln, h in an)
    block.append("")
    block.append("*%d animation entries.*" % len(an))
    return "\n".join(block)


def splice(text, index_md):
    nl = "\r\n" if text.count("\r\n") >= (text.count("\n") - text.count("\r\n")) else "\n"
    flat = text.replace("\r\n", "\n")
    new_block = START + "\n" + index_md + "\n" + END
    if START in flat and END in flat:
        pre, rest = flat.split(START, 1)
        _, post = rest.split(END, 1)
        flat = pre + new_block + post
    else:
        # First run: place it after the document's own prose, immediately before the first entry's
        # horizontal rule, so the intro that explains what the file IS still reads first.
        marker = "\n---\n\n## "
        if marker not in flat:
            print("cannot find where the entries begin; index not inserted")
            sys.exit(2)
        head, tail = flat.split(marker, 1)
        flat = head + "\n\n" + new_block + marker + tail
    return flat.replace("\n", nl)


def render(text):
    """Splice the index in, then RE-DERIVE it from the spliced document until the line numbers
    stop moving. The index sits above the entries, so inserting it pushes every entry down by the
    block's own height - the first pass necessarily records pre-insertion line numbers. Iterating
    to a fixed point is what makes the numbers you can actually jump to. (First run reported entry
    1 at line 45 when it was at 146; a stale line number is worse than none, because it sends you
    to a real line that says something else.)"""
    for _ in range(6):
        updated = splice(text, build_index(text))
        if updated == text:
            return text
        text = updated
    return text


def main():
    check = "--check" in sys.argv
    text = read(DOC)
    updated = render(text)
    if check:
        failures, predating = root_cause_report(text)
        bad = bool(failures)
        if updated == text:
            print("past-mistakes library index: CURRENT (%d entries)" % len(entries(text)))
        else:
            print("past-mistakes library index: STALE - run  python .MD\\scripts\\logic-index.py")
            bad = True
        for f in failures:
            print(f)
        print("%d entries predate the root-cause rule" % predating)
        sys.exit(1 if bad else 0)
    if updated == text:
        print("past-mistakes library index already current (%d entries)" % len(entries(text)))
        return
    io.open(DOC, "w", encoding="utf-8", newline="").write(updated)
    print("past-mistakes library index rewritten: %d entries" % len(entries(text)))


if __name__ == "__main__":
    main()
