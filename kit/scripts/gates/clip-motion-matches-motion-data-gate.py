"""Refuses a package whose clips carry their own root motion ("animmotion" annotations) that disagrees with the motion
data its behaviour patch gives the same clip in animationdatasinglefile.

Why (Simple Dodge 1.2.0 round 2, batch B-20261113-031456-c03f): Animation Motion Revolution (AMR, Nexus 50258, in most
combat lists) moves the character by a clip's own animmotion annotations whenever the clip has them and then ignores
animationdatasinglefile (its Hooks.cpp, ProcessTranslationData_Hook). The patch gave the long roll x1.5 motion data
but pointed it at the standard roll's .hkx, and the installer's "Shorter" option shipped only motion data - so in game
the long roll went exactly as far as the standard roll (470 / 470) and Shorter changed nothing. Without AMR the motion
data drives the distance, so the two must agree for a distance to be the same for every player.

For the package's Common folder, and Common overlaid by each other option folder (as the FOMOD installs it):
  for each hkbClipGenerator in a Nemesis_Engine\\mod\\<code> graph whose clip name has a motion entry in that patch's
  animationdatasinglefile (DefaultMale~1 for third person, FirstPerson~1 for _1stperson), every shipped .hkx that
  plays for it - the animationName under meshes\\actors\\character (or _1stperson), and the same file inside any
  OpenAnimationReplacer folder - that carries animmotion annotations must reach the motion data's end point at its
  duration, on each axis within max(3 units, 2 %).
A clip without annotations, or a clip name with no motion entry in the patch, is not checked (vanilla behaviour).
Exit 0 pass / nothing to check; 1 on any FAIL. package-gate runs it through row clip-motion-matches-motion-data.
Usage: py -3 clip-motion-matches-motion-data-gate.py --path <package or mod folder>
"""
import argparse, os, re, struct, sys

ANN = re.compile(rb"animmotion (-?[0-9.eE+-]+) (-?[0-9.eE+-]+) (-?[0-9.eE+-]+)\x00")
CLIP = re.compile(r'<hkobject name="[^"]+" class="hkbClipGenerator"(.*?)</hkobject>', re.S)
SKIP_OPTION = re.compile(r"(?i)^(fomod|line-|common$)")


def annotations(path):
    b = open(path, "rb").read()
    ms = [tuple(float(m.group(i)) for i in (1, 2)) for m in ANN.finditer(b)]
    if not ms:
        return None
    first = b.find(b"animmotion ")
    n = len(ms)
    for start in range(first - 16 * n, max(0, first - 16 * n - 512), -4):
        ts = [struct.unpack_from("<f", b, start + 16 * k)[0] for k in range(n)]
        if abs(ts[0]) < 1e-6 and all(0 <= ts[k + 1] - ts[k] < 2 for k in range(n - 1)) and ts[-1] > 0:
            return list(zip(ts, ms))
    return [(0.0, (0.0, 0.0))] + [(99.0, ms[-1])]  # times not found: judge by the last value


def reach(ann, duration):
    t = min(duration, ann[-1][0])
    for k, (tk, mk) in enumerate(ann):
        if t <= tk + 1e-6:
            if k == 0:
                return mk
            t0, m0 = ann[k - 1]
            f = (t - t0) / (tk - t0) if tk > t0 else 1.0
            return tuple(m0[i] * (1 - f) + mk[i] * f for i in (0, 1))
    return ann[-1][1]


def tree(root):
    out = {}
    for dp, dn, fn in os.walk(root):
        for f in fn:
            p = os.path.join(dp, f)
            out[os.path.relpath(p, root).replace("\\", "/").lower()] = p
    return out


def motion_end(files, base, project, clip):
    pre = "%s/animationdatasinglefile/%s/" % (base, project)
    for k, p in files.items():
        if k.startswith(pre) and os.path.basename(k).startswith(clip.lower() + "~"):
            mid = open(p, encoding="ascii", errors="replace").read().split("\n")[1].strip()
            mp = files.get(pre + mid.lower() + ".txt")
            if not mp:
                return None
            lines = [l.strip() for l in open(mp, encoding="ascii", errors="replace").read().split("\n")]
            dur, n = float(lines[1]), int(lines[2])
            t, x, y, z = lines[2 + n].split(" ")
            return mid, dur, (float(x), float(y))
    return None


def check(files, label):
    fails, n = [], 0
    bases = sorted({k.split("/info.ini")[0] for k in files if re.match(r"nemesis_engine/mod/[^/]+/info\.ini$", k)})
    for base in bases:
        for k, p in files.items():
            if not k.startswith(base + "/") or not k.endswith(".txt") or "/animationdatasinglefile/" in k:
                continue
            first = k[len(base) + 1:].startswith("_1stperson/")
            t = open(p, encoding="utf-8", errors="replace").read()
            for m in CLIP.finditer(t):
                name = re.search(r'name="name">([^<]*)<', m.group(1))
                anim = re.search(r'name="animationName">([^<]*)<', m.group(1))
                if not name or not anim:
                    continue
                md = motion_end(files, base, "firstperson~1" if first else "defaultmale~1", name.group(1))
                if not md:
                    continue
                mid, dur, end = md
                arel = anim.group(1).replace("\\", "/").lower()                  # animations/tkdodge/x.hkx
                char = "meshes/actors/character/" + ("_1stperson/" if first else "")
                tail = arel.split("animations/", 1)[-1]
                cands = [char + arel] + [q for q in files if q.startswith(char) and "/openanimationreplacer/" in q
                                         and ("/_1stperson/" in q) == first and q.endswith("/" + tail)]
                for c in cands:
                    if c not in files:
                        continue
                    ann = annotations(files[c])
                    if ann is None:
                        continue
                    n += 1
                    got = reach(ann, dur)
                    for i, axis in ((0, "x"), (1, "y")):
                        if abs(got[i] - end[i]) > max(3.0, 0.02 * abs(end[i])):
                            fails.append("%s: clip %s plays %s, whose own motion reaches %s %.1f at %.3fs, but motion "
                                         "data %s says %.1f" % (label, name.group(1), c, axis, got[i], dur, mid, end[i]))
    return fails, n


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--path", required=True); ap.add_argument("--repo")
    a = ap.parse_args()
    root = a.path
    common = os.path.join(root, "Common")
    base = tree(common) if os.path.isdir(common) else tree(root)
    sets = [("Common", base)]
    if os.path.isdir(common):
        for opt in sorted(os.listdir(root)):
            od = os.path.join(root, opt)
            if os.path.isdir(od) and not SKIP_OPTION.match(opt):
                merged = dict(base); merged.update(tree(od)); sets.append(("Common + " + opt, merged))
    fails, total = [], 0
    for label, files in sets:
        f, n = check(files, label); fails += f; total += n
    for f in fails[:40]:
        print("FAIL clip-motion: " + f)
    if len(fails) > 40:
        print("FAIL clip-motion: ... %d more" % (len(fails) - 40))
    if not fails:
        print("clip-motion  pass  %d clip file(s) checked against their motion data across %d install set(s)" % (total, len(sets)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
