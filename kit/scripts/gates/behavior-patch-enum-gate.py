"""Refuses a behaviour patch (Nemesis/Pandora format) that gives a node an enum value its class does not have.

Why (Simple Dodge 1.2.0, batch B-20261112-200853-f998): six hkbStateMachine nodes got selfTransitionMode
SELF_TRANSITION_MODE_BLEND - a value of hkbBlendingTransitionEffect's selfTransitionMode, not of the state machine's.
Nemesis built it; Pandora logged "Enum dose not contain SELF_TRANSITION_MODE_BLEND", dropped every new node of the patch
and still wrote the graphs, and the game crashed loading a save. The values below are the hkx 2010 enums.

Checks every node file (*.txt) under each Nemesis_Engine\\mod\\<code>\\ in the package (and the repo's dist when given):
  hkbStateMachine        selfTransitionMode  NO_TRANSITION | TRANSITION_TO_START_STATE | FORCE_TRANSITION_TO_START_STATE
                         startStateMode      DEFAULT | SYNC | RANDOM | CHOOSER
  hkbBlendingTransitionEffect selfTransitionMode CONTINUE_IF_CYCLIC_BLEND_IF_ACYCLIC | CONTINUE | RESET | BLEND
                         eventMode           DEFAULT | PROCESS_ALL | IGNORE_FROM_GENERATOR | IGNORE_TO_GENERATOR
Exit 1 on any hit. package-gate runs it through row behavior-patch-enum-values-are-the-class-own.
Usage: py -3 behavior-patch-enum-gate.py --path <package or folder> [--repo R]
"""
import argparse, os, re, sys

ALLOWED = {
    "hkbStateMachine": {
        "selfTransitionMode": {"SELF_TRANSITION_MODE_NO_TRANSITION", "SELF_TRANSITION_MODE_TRANSITION_TO_START_STATE",
                               "SELF_TRANSITION_MODE_FORCE_TRANSITION_TO_START_STATE"},
        "startStateMode": {"START_STATE_MODE_DEFAULT", "START_STATE_MODE_SYNC", "START_STATE_MODE_RANDOM",
                           "START_STATE_MODE_CHOOSER"},
    },
    "hkbBlendingTransitionEffect": {
        "selfTransitionMode": {"SELF_TRANSITION_MODE_CONTINUE_IF_CYCLIC_BLEND_IF_ACYCLIC", "SELF_TRANSITION_MODE_CONTINUE",
                               "SELF_TRANSITION_MODE_RESET", "SELF_TRANSITION_MODE_BLEND"},
        "eventMode": {"EVENT_MODE_DEFAULT", "EVENT_MODE_PROCESS_ALL", "EVENT_MODE_IGNORE_FROM_GENERATOR",
                      "EVENT_MODE_IGNORE_TO_GENERATOR"},
    },
}
OBJ = re.compile(r'<hkobject name="([^"]+)" class="(\w+)"')


def scan(root):
    hits, n = [], 0
    for dp, dn, fn in os.walk(root):
        parts = re.split(r"[\\/]", dp)
        if not any(p.lower() == "nemesis_engine" for p in parts):
            continue
        for f in fn:
            if not f.endswith(".txt"):
                continue
            p = os.path.join(dp, f)
            t = open(p, encoding="utf-8", errors="replace").read()
            objs = list(OBJ.finditer(t))
            for i, m in enumerate(objs):
                cls = m.group(2)
                if cls not in ALLOWED:
                    continue
                n += 1
                body = t[m.end(): objs[i + 1].start() if i + 1 < len(objs) else len(t)]
                for param, ok in ALLOWED[cls].items():
                    for v in re.findall(r'<hkparam name="%s">([^<]*)</hkparam>' % param, body):
                        if v.strip() not in ok:
                            hits.append("%s: %s %s has %s = %s, which %s does not have" % (
                                os.path.relpath(p, root), cls, m.group(1), param, v.strip(), cls))
    return hits, n


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--path"); ap.add_argument("--repo")
    a = ap.parse_args()
    roots = [r for r in (a.path, os.path.join(a.repo, "dist") if a.repo else None) if r and os.path.isdir(r)]
    bad, total = [], 0
    for r in roots:
        h, n = scan(r); bad += h; total += n
    for h in bad:
        print("FAIL behavior-patch-enum: " + h)
    if not bad:
        print("behavior-patch-enum  pass  %d state machine / blend effect nodes checked" % total)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
