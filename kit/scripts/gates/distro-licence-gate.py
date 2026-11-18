r"""THE DISTRO LICENCE GATE (2026-10-22): a licence named on a mod's banners or page text must be the licence in its repo.

Nexus took Lock Interaction Overhaul down on 2026-09-13 for an MIT label on a GPL build (past-mistakes library 5107).
The repo, the DLL, the README and the page text were all relicensed to GPL-3.0-or-later - but the 1920x1080 banner
kept a pill reading "MIT, open source", and it stayed the page's thumbnail and the first picture in its description
until the owner saw it on 2026-10-22 ("Fix the banner"). Nothing compared the pictures' source with the LICENSE.

    python distro-licence-gate.py --path <distro folder> --repo <repo>     (package-gate kind distro-repo-script-passes)

The repo's licence family is read from the title of its LICENSE (LICENSE / LICENSE.txt / LICENSE.md / COPYING).
Then, in the distro folder (assets\ and backups skipped):
  * picture sources - banner*/cover*/post-image*/card* .html, also inside _photos* folders - ANY licence named in
    their visible text is a claim about the mod (embedded data: URIs, <style> and <script> are not read);
  * page text - nexus-page.txt, short-description.txt, the newest nexus-description-X.Y.Z.txt and *banner*.txt -
    only a CLAIM about the mod counts ("<the mod / this mod / its name / it is> ... licensed under X",
    "Licence: X", "X, open source", "open source (X)"), so credit lines such as "Remember Lockpick Angle (MIT)" or
    "the original, published under the MIT licence" pass.
FAIL (exit 1) on a claim naming another family. SKIP (exit 0) without a repo or LICENSE.
"""
import argparse, glob, html.parser, os, re, sys

sys.stdout.reconfigure(encoding="utf-8")

# (family, pattern) - order matters: LGPL / AGPL before GPL, so "LGPL-2.1" is not read as GPL
FAMILIES = [
    ("LGPL", r"\bLGPL|LESSER GENERAL PUBLIC"),
    ("AGPL", r"\bAGPL|AFFERO GENERAL PUBLIC"),
    ("GPL", r"\bGPL|GNU GENERAL PUBLIC|(?<!LESSER )(?<!AFFERO )GENERAL PUBLIC LICEN[CS]E"),
    ("MIT", r"\bMIT\b"),
    ("Apache", r"\bAPACHE\b"),
    ("BSD", r"\bBSD\b"),
    ("MPL", r"\bMPL\b|MOZILLA PUBLIC"),
    ("CC", r"\bCC[- ]?(BY|0)\b|CREATIVE COMMONS"),
    ("Unlicense", r"\bUNLICEN[CS]E\b"),
]
LIC_TOKEN = "|".join(p for _, p in FAMILIES)


def families(text):
    t = text.upper()
    found = []
    for fam, pat in FAMILIES:
        if re.search(pat, t):
            # "LGPL" also contains the letters GPL only after an L, which \bGPL excludes; but LESSER GENERAL PUBLIC
            # contains "GENERAL PUBLIC LICENSE" - drop GPL when only the LGPL/AGPL phrase produced it
            if fam == "GPL" and ("LGPL" in found or "AGPL" in found):
                rest = re.sub(r"(LESSER|AFFERO) GENERAL PUBLIC LICEN[CS]E", "", t)
                rest = re.sub(r"\b[LA]GPL", "", rest)
                if not re.search(pat, rest):
                    continue
            found.append(fam)
    return found


def repo_family(repo):
    lic = next((os.path.join(repo, n) for n in ("LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING")
                if os.path.isfile(os.path.join(repo, n))), None)
    if not lic:
        return None, None
    head = [l for l in open(lic, encoding="utf-8", errors="replace").read(4000).splitlines() if l.strip()][:3]
    f = families("\n".join(head))
    return (f[0] if f else "other"), lic


class _Text(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []; self._skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script"): self._skip += 1
        for k, v in attrs:          # visible attribute text only
            if k in ("alt", "title") and v: self.parts.append(v)
    def handle_endtag(self, tag):
        if tag in ("style", "script") and self._skip: self._skip -= 1
    def handle_data(self, d):
        if not self._skip: self.parts.append(d)


def html_text(path):
    raw = open(path, encoding="utf-8", errors="replace").read()
    raw = re.sub(r"data:[^\"')\s]+", "", raw)          # embedded pictures are base64, never text
    p = _Text(); p.feed(raw)
    return re.sub(r"\s+", " ", " ".join(p.parts))


CLAIM = re.compile(
    r"(?P<subj>[^.\n]{0,120}?)licen[cs]ed\s+under\s+(the\s+)?(?P<a>[^.\n;]{0,80})"
    r"|licen[cs]e\s*[:=]\s*(?P<b>[^.\n;]{0,60})"
    r"|(?P<d>(" + LIC_TOKEN + r")[^.\n;]{0,20}),?\s+open[- ]source"
    r"|open[- ]source\s*\((?P<e>[^)\n]{0,40})\)", re.I)
SELF = r"\b(this|the|our)\s+(mod|build|plugin|framework|patch)\b|\bit\s+is\b|\bwhole\s+mod\b"


def claims(text, mod_name=""):
    """Claims about THE MOD, not credit lines: 'licensed under X' counts only when the mod (its name, 'this mod',
    'the mod', 'it is') is the subject of that sentence; 'Licence: X', 'X, open source', 'open source (X)' always."""
    text = re.sub(r"\[/?[a-z*]+(=[^\]]*)?\]", " ", text, flags=re.I)     # BBCode tags
    out = []
    for m in CLAIM.finditer(text):
        if m.group("a") is not None:
            subj = m.group("subj") or ""
            if not (re.search(SELF, subj, re.I) or (mod_name and mod_name.lower() in subj.lower())):
                continue
        seg = next((m.group(k) for k in "abde" if m.group(k)), "")
        fams = families(seg)
        if fams:
            out.append((fams, m.group(0).strip()[-90:]))
    return out


def scan(distro):
    base_name = os.path.basename(os.path.normpath(distro))
    mod_name = base_name.split(" - ", 1)[1] if " - " in base_name else base_name
    hits = []   # (relpath, families, quote)
    for base, dirs, files in os.walk(distro):
        dirs[:] = [d for d in dirs if d.lower() != "assets" and not d.lower().startswith(("nexus-media", "backup"))]
        for f in files:
            lf = f.lower()
            if ".bak" in lf or "before" in lf:
                continue
            p = os.path.join(base, f)
            rel = os.path.relpath(p, distro)
            if lf.endswith(".html") and re.match(r"(banner|cover|post-image|card)", lf):
                t = html_text(p)
                for fam in families(t):
                    m = re.search(dict(FAMILIES)[fam], t.upper())
                    hits.append((rel, [fam], t[max(0, m.start() - 30): m.end() + 30].strip()))
            elif lf.endswith(".txt") and base == distro and ("banner" in lf or lf in ("nexus-page.txt", "short-description.txt")):
                for fams, q in claims(open(p, encoding="utf-8", errors="replace").read(), mod_name):
                    hits.append((rel, fams, q))
    descs = glob.glob(os.path.join(distro, "nexus-description-*.txt"))
    def ver(p):
        m = re.match(r"nexus-description-(\d+)\.(\d+)\.(\d+)\.txt$", os.path.basename(p))
        return tuple(map(int, m.groups())) if m else None
    descs = sorted((d for d in descs if ver(d)), key=ver)
    if descs:
        for fams, q in claims(open(descs[-1], encoding="utf-8", errors="replace").read(), mod_name):
            hits.append((os.path.basename(descs[-1]), fams, q))
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True, help="the mod's 11. Nexus distro folder")
    ap.add_argument("--repo", help="the mod's repo (its LICENSE decides)")
    a = ap.parse_args()
    if not a.repo or not os.path.isdir(a.repo):
        print("distro-licence-gate  SKIP  no repo"); return 0
    if not os.path.isdir(a.path):
        print("distro-licence-gate  SKIP  no distro folder"); return 0
    fam, lic = repo_family(a.repo)
    if not fam:
        print("distro-licence-gate  SKIP  the repo has no LICENSE"); return 0
    bad = 0
    for rel, fams, q in scan(a.path):
        wrong = [f for f in fams if f != fam]
        bad += bool(wrong)
        print(f"distro-licence-gate  {'FAIL' if wrong else 'PASS'}  {rel}: names {'/'.join(fams)} vs LICENSE {fam} - \"{q}\"")
    if not bad:
        print(f"distro-licence-gate  PASS  no licence claim in the distro folder differs from LICENSE {fam}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
