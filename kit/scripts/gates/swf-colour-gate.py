r"""swf-colour-gate.py - proves a recoloured SWF is actually recoloured.

Why this exists (2026-09-18/19, two failures of the same shape):

  * A recolour pass ran, reported success and changed nothing, because it matched
    `red="\d+" green="\d+" blue="\d+"` - and FFDec writes colour attributes ALPHABETICALLY
    (alpha, blue, green, red). The regex could never match. The menu looked identical in game and the
    next hour went into the wrong questions.
  * Folding a Dynamic Interface Patcher output into Norden UI - Black put the patcher's GREY racesex_menu
    back over the black one, and nothing noticed until the menu was opened.

Both are the same class: a transform whose EFFECT was never read back. This gate reads the shipped file -
not the script, not the intermediate XML - and fails when a file that is supposed to be black is not.

    python swf-colour-gate.py <file-or-folder> [...] [--max 40] [--allow-grey 32,83] [--grey-max 210]
    python swf-colour-gate.py <file-or-folder> [...] --band 41,102

  --band       (2026-09-22) fail only on a neutral INSIDE this range - Norden's panel greys (51, 64, 77, 88,
               102) are what the recolour darkens; white and light-grey TEXT and highlights (153-255) are
               left alone by design, so a menu with white labels (RaceMenu's racesex_menu) fails --max
               while being exactly as black as intended. A file still carrying Norden grey fails the band.
               In band mode a colour is neutral only at a channel spread <= 3 - recolour.py's own definition -
               so a warm tint (moreHUD IE's 41,36,37, SkyUI's 50,49,44) that the recolour leaves alone passes.
  --allow-grey also takes FILE:ids (tweenmenu.swf:32,83) to limit the allowance to one file's shapes.

  --max        the brightest neutral (grey/white) a black file may contain; default 40
  --allow-grey shape ids that are allowed up to --grey-max (the tween menu's dividers and arrows)
  --grey-max   how bright those shapes may be; default 210

Hued colours (an icon's red, a health bar's green) are left alone, exactly as the recolour does:
a colour counts as neutral only when its channels are within 8 of each other.
EXIT CODES: 0 every file is as black as it claims, 1 at least one is not.
"""
import glob, os, re, subprocess, sys, tempfile

FFDEC = os.environ.get("FFDEC_CLI", r"C:\Program Files (x86)\FFDec\ffdec-cli.exe")
ATTR = re.compile(r'(\w+)="([^"]*)"')
NODE = re.compile(r'<(\w+) type="RGBA?"((?:\s+\w+="[^"]*")+)/>')
SHAPE = re.compile(r'<item type="Define\w*Shape\w*Tag"([^>]*)>')


# ffdec-cli.exe (launch4j) gives Java a heap the size of the machine's RAM (-Xmx32166m on 31 GB): one -swf2xml
# of a large StatsCard.swf reached 11.7 GB and left 0.5 GB free beside a running game (2026-10-23). Run the jar
# with a capped heap instead; FFDEC_HEAP overrides the cap.
HEAP = os.environ.get("FFDEC_HEAP", "4g")


def ffdec_cmd():
    jar = os.path.splitext(FFDEC)[0] + ".jar"
    if FFDEC.lower().endswith(".exe") and os.path.exists(jar):
        return ["java", "-Xmx" + HEAP, "-jar", jar]
    return [FFDEC]


def to_xml(swf):
    # The temporary folder is removed on every exit path, failures included: mkdtemp alone left one
    # swfgate-* folder per file read, about 28,700 of them in %TEMP% by 2026-11-05.
    with tempfile.TemporaryDirectory(prefix="swfgate-", ignore_cleanup_errors=True) as tmp:
        out = os.path.join(tmp, os.path.basename(swf) + ".xml")
        r = subprocess.run(ffdec_cmd() + ["-swf2xml", swf, out], capture_output=True, text=True)
        if not os.path.exists(out):
            raise RuntimeError((r.stderr or r.stdout or "ffdec produced nothing")[-300:])
        with open(out, encoding="utf-8", errors="replace") as fh:
            return fh.read()


def shape_spans(xml):
    spans, marks = [], []
    for m in SHAPE.finditer(xml):
        at = dict(ATTR.findall(m.group(1)))
        try:
            marks.append((m.start(), int(at.get("shapeId", "-1"))))
        except ValueError:
            marks.append((m.start(), -1))
    for i, (pos, sid) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(xml)
        spans.append((pos, end, sid))
    return spans


def check(swf, max_neutral, allow_grey, grey_max, band=None):
    allow_grey = {x[1] if isinstance(x, tuple) else x for x in allow_grey
                  if not isinstance(x, tuple) or x[0] == os.path.basename(swf).lower()}
    xml = to_xml(swf)
    spans = shape_spans(xml)

    def shape_at(pos):
        for a, b, sid in spans:
            if a <= pos < b:
                return sid
        return -1

    worst, offenders, neutrals = 0, [], 0
    for m in NODE.finditer(xml):
        if m.group(1) != "color":       # textColor / dropShadowColor belong to the author
            continue
        a = dict(ATTR.findall(m.group(2)))
        try:
            r, g, b = int(a["red"]), int(a["green"]), int(a["blue"])
        except KeyError:
            continue
        if max(r, g, b) - min(r, g, b) > (3 if band else 8):
            continue                    # a hue, not a neutral
        neutrals += 1
        v = max(r, g, b)
        sid = shape_at(m.start())
        limit = grey_max if sid in allow_grey else max_neutral
        worst = max(worst, v)
        if band:
            if band[0] <= v <= band[1] and sid not in allow_grey:
                offenders.append((sid, v, band[1]))
        elif v > limit:
            offenders.append((sid, v, limit))
    return neutrals, worst, offenders


def differs_from_source(black_dir, source_dir):
    """The silent-no-op check: every file the black mod ships must DIFFER from the same path in the mod it was
    recoloured from. A byte-identical copy means the pass ran and changed nothing - which is exactly what the
    alphabetical-attribute regex did, and exactly what it looked like from the script's own output: success."""
    import hashlib
    same, checked, missing = [], 0, []
    for root, _, names in os.walk(black_dir):
        for n in names:
            if not n.lower().endswith(".swf"):
                continue
            b = os.path.join(root, n)
            rel = os.path.relpath(b, black_dir)
            src = os.path.join(source_dir, rel)
            if not os.path.exists(src):
                missing.append(rel)          # our own art, or another mod's file - not part of this check
                continue
            checked += 1
            h = lambda p: hashlib.sha1(open(p, "rb").read()).hexdigest()
            if h(b) == h(src):
                same.append(rel)
    return checked, same, missing


def main(argv):
    files, dirs, max_neutral, allow_grey, grey_max, against, band = [], [], 40, set(), 210, None, None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--max":
            i += 1; max_neutral = int(argv[i])
        elif a == "--grey-max":
            i += 1; grey_max = int(argv[i])
        elif a == "--band":
            i += 1; band = tuple(int(x) for x in argv[i].split(","))
        elif a == "--against":
            i += 1; against = argv[i]
        elif a == "--allow-grey":
            i += 1
            for part in argv[i].split(";"):
                if ":" in part:
                    fn, ids = part.split(":", 1)
                    allow_grey |= {(fn.strip().lower(), int(x)) for x in ids.split(",") if x.strip()}
                else:
                    allow_grey |= {int(x) for x in part.split(",") if x.strip()}
        elif os.path.isdir(a):
            dirs.append(a)
            files += sorted(glob.glob(os.path.join(a, "**", "*.swf"), recursive=True))
        else:
            files += sorted(glob.glob(a))
        i += 1
    if against:
        if len(dirs) != 1:
            print("--against takes one folder: the recoloured mod, compared against the mod it was made from")
            return 2
        checked, same, missing = differs_from_source(dirs[0], against)
        print("swf-colour-gate  %d file(s) compared against %s" % (checked, against))
        for rel in missing:
            print("  note  %s is not in the source mod - our own art, or another mod's file" % rel)
        if same:
            for rel in same:
                print("  FAIL  %s is byte-identical to the original - the recolour pass changed nothing" % rel)
            print("swf-colour-gate  FAIL  %d file(s) ship the original art under a recoloured mod's name" % len(same))
            return 1
        print("swf-colour-gate  pass  every shipped file differs from the art it was made from")
        return 0
    if not files:
        print(__doc__)
        return 2
    bad = 0
    for f in files:
        try:
            neutrals, worst, offenders = check(f, max_neutral, allow_grey, grey_max, band)
        except Exception as e:
            print("swf-colour-gate  FAIL  %s could not be read: %s" % (os.path.basename(f), e))
            bad += 1
            continue
        name = os.path.basename(f)
        if offenders:
            bad += 1
            print("swf-colour-gate  FAIL  %s  %d neutral colours, brightest %d" % (name, neutrals, worst))
            for sid, v, limit in sorted(set(offenders), key=lambda x: -x[1])[:6]:
                print("        shape %-4s value %-3d  (limit %d) - this file was not recoloured, or something grey was written over it" % (sid, v, limit))
        else:
            print("swf-colour-gate  pass  %-28s %d neutral colours, brightest %d" % (name, neutrals, worst))
    if bad:
        print("swf-colour-gate  FAIL  %d file(s) are not the colour they are meant to be" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
