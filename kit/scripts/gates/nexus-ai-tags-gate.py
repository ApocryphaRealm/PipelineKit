"""THE NEXUS AI-TAGS GATE (2026-10-25).

Nexus staff warned the account on 2026-10-25 for "content classification and tag use failure": Nexus's File
Submission Guidelines ("Generative AI Tagging & Categorisation") require BOTH
  * "AI-Generated Content" - AI-generated code, UI elements, translations, in-game assets - and
  * "AI Media"             - AI page descriptions, banners, thumbnails, videos, media outside the game,
on a page whose mod and page were made with AI. Every one of our pages is both, and only the first tag had ever been
set. The tags live on the page, not in any file we ship, so this gate reads the ledger that records each live page's
tags as read back from the public page: scripts\\nexus-ai-tags.json (role-free: it sits beside version-registry.json).

For the distro folder given, every version-registry entry that maps to it (same join as nexus-version-audit.py:
_distro-folders.json, then the folder's mod part with the game words taken out; an "MO2 - " folder matches a page of
any domain) and carries a nexusModId (and is not nexusRemoved) - its main page and every additional page in its
'nexusPages' list (2026-10-25: the Modding Tools copies):
  * FAIL - the ledger has no row for '<domain>/<id>';
  * FAIL - the row lacks one of the ledger's 'required' tags;
  * FAIL - the row lists "AI Assisted" (not ours to claim: it needs evidence of human-led development).
A mod with no page yet passes (first posting is covered by the nexus-page skill's checklist).

  python nexus-ai-tags-gate.py --path <distro folder>     check one mod (package-gate kind distro-script-passes)
  python nexus-ai-tags-gate.py --all                      list every registry page missing from the ledger
Exit 1 on any FAIL.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, ".."))
GAME_DOMAIN = {"Skyrim": "skyrimspecialedition", "Oblivion Remastered": "oblivionremastered", "Witcher 3": "witcher3"}
ANY_DOMAIN = {"MO2"}


def load(path):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def norm(name):
    n = name.lower()
    for w in (" for oblivion remastered", " for oblivion", "oblivion remastered - ", "skyrim - ", " - smf settings"):
        n = n.replace(w, "")
    return re.sub(r"[^a-z0-9]+", " ", n).strip()


def domain_ok(folder, dom):
    prefix = folder.split(" - ")[0]
    return prefix in ANY_DOMAIN or GAME_DOMAIN.get(prefix) == dom


def pages(reg):
    for k, e in reg.get("mods", reg).items():
        if not isinstance(e, dict) or not e.get("nexusModId") or e.get("nexusRemoved"):
            continue
        yield k, e, (e.get("nexusDomain") or "skyrimspecialedition"), e["nexusModId"]
        # additional pages of the same mod (2026-10-25, version-gate link -Additional): the Modding Tools copies
        for p in e.get("nexusPages") or []:
            if isinstance(p, dict) and p.get("nexusModId") and p.get("nexusDomain"):
                yield k, e, p["nexusDomain"], p["nexusModId"]


def row_problems(ledger, dom, nid):
    key = f"{dom}/{nid}"
    row = ledger.get("pages", {}).get(key)
    if not row:
        return [f"{key}: no row in nexus-ai-tags.json - check the live page's tags and record them"]
    tags = row.get("tags") or []
    out = [f"{key} ({row.get('name', '')}): missing tag '{t}'" for t in ledger.get("required", []) if t not in tags]
    if "AI Assisted" in tags:
        out.append(f"{key}: 'AI Assisted' listed - our pages take AI-Generated Content + AI Media, never AI Assisted")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--registry", default=os.path.join(SCRIPTS, "version-registry.json"))   # tests point these at fixtures
    ap.add_argument("--ledger", default=os.path.join(SCRIPTS, "nexus-ai-tags.json"))
    a = ap.parse_args()
    reg = load(a.registry)
    ledger = load(a.ledger)
    fails = []
    if a.all:
        seen = list(pages(reg))
        for k, e, dom, nid in seen:
            fails += row_problems(ledger, dom, nid)
        print(f"checked {len(seen)} registry page(s), main and additional")
    elif a.path:
        distro_root, folder = os.path.split(os.path.normpath(a.path))
        try:
            dmap = load(os.path.join(distro_root, "_distro-folders.json"))
        except OSError:
            dmap = {}
        mapped = (dmap.get(folder) or "").lower()
        hit = 0
        for k, e, dom, nid in pages(reg):
            if not domain_ok(folder, dom):
                continue
            names = {k.lower(), (e.get("displayName") or "").lower(), *[x.lower() for x in e.get("aliases") or []]}
            names.discard("")
            if (mapped and mapped in names) or norm(folder.split(" - ", 1)[-1]) in {norm(n) for n in names}:
                hit += 1
                fails += row_problems(ledger, dom, nid)
        if not hit:
            print(f"PASS {folder}: no Nexus page in the version registry yet")
    else:
        ap.error("give --path <distro folder> or --all")
    for f in fails:
        print("FAIL " + f)
    if not fails:
        print("PASS AI disclosure tags recorded (AI-Generated Content + AI Media)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
