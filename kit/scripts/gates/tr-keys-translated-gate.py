"""THE TRANSLATED-KEYS GATE (2026-11-12, Simple Dodge 1.0.0 -> 1.1.0, rule 66).

Our settings pages draw every string through strings::TR("PREFIX_Key", "English text"); the English text is only the
fallback when no Interface\\Translations\\<stem>_<language>.txt has the key. Simple Dodge 1.0.0 passed every gate with
42 of its 83 keys - every switch and slider label and help, whose keys are passed to TR through a helper
(Switch("SDG_StepDodge", ...)) - in none of its eleven files, so those rows were English in every language. The
existing translations-complete row compares the other languages with English only, so a key missing from ALL of them,
English included, was invisible.

This gate reads the mod's C++ sources (the repo's src\\ and include\\), takes the prefixes used in TR("<P>_...")
calls, collects every string literal "<P>_<Name>" in those sources as a key, and fails for each language file in the
package (Interface\\Translations\\*_<language>.txt holding keys of that prefix) that lacks one.

Usage: python tr-keys-translated-gate.py --path <package> --repo <repo>      exit 1 on any missing key
"""
import argparse, os, re, sys

SRC_EXT = (".cpp", ".h", ".hpp", ".inl")


def source_keys(repo):
    texts = []
    for sub in ("src", "include"):
        root = os.path.join(repo, sub)
        for dp, dn, fn in os.walk(root):
            dn[:] = [d for d in dn if d not in ("build", ".git", "extern", "DevBench")]
            for f in fn:
                if f.endswith(SRC_EXT):
                    t = open(os.path.join(dp, f), encoding="utf-8", errors="replace").read()
                    t = re.sub(r"/\*.*?\*/", " ", t, flags=re.S)       # comments name example keys (PREFIX_Key)
                    t = re.sub(r'^((?:[^"\n]|"(?:[^"\\\n]|\\.)*")*?)//[^\n]*', r"\1", t, flags=re.M)
                    texts.append(t)
    allsrc = "\n".join(texts)
    prefixes = set(re.findall(r'\bTR\(\s*"([A-Z][A-Za-z0-9]{1,7})_[A-Za-z0-9]+"', allsrc))
    keys = set()
    for p in prefixes:
        keys |= set(re.findall(r'"(%s_[A-Za-z0-9]+)"' % re.escape(p), allsrc))
    return prefixes, keys


def read_keys(path):
    raw = open(path, "rb").read()
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        text = raw.decode("utf-16")
    else:
        text = raw.decode("utf-8-sig", "replace")
    out = set()
    for line in text.splitlines():
        k = line.split("\t", 1)[0].strip().lstrip("\ufeff")
        if k.startswith("$"):
            out.add(k[1:])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True)
    ap.add_argument("--repo")
    a = ap.parse_args()
    if not a.repo or not os.path.isdir(a.repo):
        print("OK: no repo given - nothing to compare")
        return 0
    prefixes, keys = source_keys(a.repo)
    if not keys:
        print("OK: the sources make no TR(\"<PREFIX>_...\") calls")
        return 0
    files = []
    for dp, dn, fn in os.walk(a.path):
        if os.path.basename(dp).lower() == "translations":
            files += [os.path.join(dp, f) for f in fn if re.search(r"_[a-z]+\.txt$", f, re.I)]
    bad = 0
    checked = 0
    for f in sorted(files):
        have = read_keys(f)
        mine = {k for k in have if k.split("_", 1)[0] in prefixes}
        if not mine:
            continue  # another mod's or framework's file
        checked += 1
        missing = sorted(keys - have)
        if missing:
            bad += 1
            print("FAIL: %s lacks %d of the %d keys the source uses: %s%s" % (
                f, len(missing), len(keys), ", ".join(missing[:12]), " ..." if len(missing) > 12 else ""))
    if checked == 0:
        print("FAIL: the source uses %d TR keys (%s) but the package has no translation file with them" % (
            len(keys), ", ".join(sorted(prefixes))))
        return 1
    if not bad:
        print("OK: %d translation files carry all %d keys (%s)" % (checked, len(keys), ", ".join(sorted(prefixes))))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
