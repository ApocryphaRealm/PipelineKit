"""THE TRANSLATION SCRIPT GATE (2026-10-12, AMF 2.1.9).

AMF's Russian file carried two values written in Latin transliteration ("Chernyy ekran, poka ne gotovo glavnoe
menyu") - the page-capture run showed the Black-screen option and its help in Latin letters under Cyrillic headings,
and it read as a font problem. The font had every Cyrillic glyph; the text itself was not Cyrillic. Nothing checked it.

Every value in a Russian, Japanese, Chinese or Korean translation file must carry that language's script. A value with
none of it and a run of three lowercase Latin words is transliterated or untranslated, and fails. (Names, numbers and
short Latin tokens such as "DevBench" or "A-Z" pass.)

Usage:
  python translation-script-gate.py --path <package or folder> [--repo <repo>]
Exit 1 on any hit; each hit is printed as a FAIL line.
"""
import argparse, os, re, sys

SCRIPTS = {
    'russian': r'[Ѐ-ӿ]',
    'japanese': r'[぀-ヿ一-鿿]',
    'chinese': r'[一-鿿]',
    'korean': r'[가-힯]',
}
LATIN_RUN = re.compile(r'[a-z]{3,} [a-z]{3,} [a-z]{3,}')


def read_text(p):
    b = open(p, 'rb').read()
    if b[:2] in (b'\xff\xfe', b'\xfe\xff'):
        return b.decode('utf-16')
    return b.decode('utf-8-sig', errors='replace')


def check(root):
    hits = []
    for dp, _, files in os.walk(root):
        if os.sep + '.git' in dp:
            continue
        for f in files:
            m = re.search(r'_(russian|japanese|chinese|korean)\.txt$', f, re.I)
            if not m or 'translations' not in dp.lower():
                continue
            rx = re.compile(SCRIPTS[m.group(1).lower()])
            p = os.path.join(dp, f)
            for line in read_text(p).splitlines():
                if '\t' not in line:
                    continue
                k, v = line.split('\t', 1)
                if not rx.search(v) and LATIN_RUN.search(v):
                    hits.append(f'FAIL {os.path.relpath(p, root)}: {k} is not in its language\'s script: {v[:80]}')
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--path', required=True)
    ap.add_argument('--repo')
    a = ap.parse_args()
    hits = check(a.path)
    for h in hits:
        print(h)
    print(f'translation-script-gate: {len(hits)} hit(s) under {a.path}')
    return 1 if hits else 0


if __name__ == '__main__':
    sys.exit(main())
