# -*- coding: utf-8 -*-
"""Translation coverage across every mod repo - who has the eleven language files, and whether
the strings the CODE asks for actually reached them.

    python .MD\\scripts\\translation-coverage.py [--repo <RepoFolderName>]

With --repo it reports on that repo alone, which is how pre-finalize-check.ps1 gates a finalize.

Why this exists: a missing translation key is SILENT. TR("KEY", "English text") falls back to the
compiled English, so a string added after a language rollout draws in English in all eleven
languages and nothing anywhere reports it. Apocrypha Menu Framework 1.6.6 added a search box whose
two strings never reached a single translation file, and it took a direct question to notice.

Reports three things per mod:
  * how many of the eleven files it ships
  * keys used in code but absent from english      (a string added after the rollout)
  * keys in english but absent from another language (a rollout that stopped early)
Exit code is 1 when anything is missing, so it can gate a finalize.
"""
import io, os, re, sys, codecs, glob

ROOT = os.path.join(os.environ.get("PIPELINE_ROOT") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "6. current wip mods")  # kit: <ROOT>\6. current wip mods
LANGS = ["english", "japanese", "korean", "chinese", "russian", "german",
         "french", "spanish", "italian", "polish", "czech"]

# TR("PREFIX_Key", ...) appears in the explanatory comment at the top of every utils/Strings.h,
# and TR(key, ...) is the macro's own parameter - neither is a real key.
NOT_A_KEY = {"PREFIX_Key", "key", "KEY"}

CODE_KEY = re.compile(r'\bTRC?\s*\(\s*"([A-Za-z0-9_]+)"')


def read_translation(path):
    """SKSE translation files are UTF-16LE with a BOM; a few tools write UTF-8."""
    raw = io.open(path, "rb").read()
    if raw[:2] == codecs.BOM_UTF16_LE:
        text = raw[2:].decode("utf-16-le", "replace")
    elif raw[:3] == codecs.BOM_UTF8:
        text = raw[3:].decode("utf-8", "replace")
    else:
        text = raw.decode("utf-8", "replace")
    keys = {}
    for ln in text.replace("\r\n", "\n").split("\n"):
        if ln.startswith("$") and "\t" in ln:
            k, _, v = ln.partition("\t")
            keys[k[1:].strip()] = v.strip()
    return keys


def source_files(repo_dir):
    out = []
    # plugins/**/*.py: MO2 plugins use the same TR("KEY", "English") shape (MO2 Theme Framework, 2026-09-26)
    for pat in ("source/**/*.cpp", "source/**/*.h", "src/**/*.cpp", "src/**/*.h", "include/**/*.h", "plugins/**/*.py", "*.py"):   # "*.py": a single-file MO2 plugin keeps its code at the repo root (MO2 Modlist Manager, 2026-10-21)
        out += glob.glob(os.path.join(repo_dir, pat), recursive=True)
    return out


def main():
    only = None
    if "--repo" in sys.argv:
        only = sys.argv[sys.argv.index("--repo") + 1]

    problems = 0
    untranslated, clean, behind = [], [], []

    for repo in sorted(os.listdir(ROOT)):
        rd = os.path.join(ROOT, repo)
        if not os.path.isdir(rd) or repo.startswith("_"):
            continue
        if only and repo.lower() != only.lower():
            continue

        code_keys = set()
        for f in source_files(rd):
            try:
                code_keys |= set(CODE_KEY.findall(io.open(f, encoding="utf-8", errors="replace").read()))
            except Exception:
                pass
        code_keys -= NOT_A_KEY
        # A TR macro may add the prefix itself - `#define TR(key, english) ::strings::Get("MM_" key, english)` (Minimap
        # Menu, 2026-09-30): the code then says TR("AlwaysDraw", ...) and the files carry MM_AlwaysDraw. The prefix is read
        # from the macro, and the comment's example key ("Key") falls away with it.
        prefix = None
        for f in source_files(rd):
            try:
                m = re.search(r'#define\s+TRC?\s*\(\s*key\s*,[^)]*\)[^\n]*"([A-Za-z0-9]+_)"\s*key\b', io.open(f, encoding="utf-8", errors="replace").read())
            except Exception:
                m = None
            if m:
                prefix = m.group(1)
                break
        if prefix:
            code_keys = {k if k.startswith(prefix) else prefix + k for k in code_keys} - {prefix + "Key"}
        if not code_keys:
            continue  # no translated surface at all - nothing to be missing

        tdir = os.path.join(rd, "dist", "Interface", "Translations")
        # an Oblivion Remastered plugin keeps its eleven files beside the DLL (dist\...\OBSE\Plugins\<Mod>\Translations), 2026-09-26
        if not glob.glob(os.path.join(tdir, "*_english.txt")):   # absent, or an empty folder left behind by a move
            found = [d for d in glob.glob(os.path.join(rd, "dist", "**", "Translations"), recursive=True) if glob.glob(os.path.join(d, "*_english.txt"))]
            if found:
                tdir = found[0]
        if not os.path.isdir(tdir):
            # an MO2 plugin keeps its files beside its code: plugins\<Name>\translations\<language>.txt
            mo2 = glob.glob(os.path.join(rd, "plugins", "*", "translations")) or glob.glob(os.path.join(rd, "*_strings", "translations"))
            if mo2:
                tdir = mo2[0]
        if not os.path.isdir(tdir):
            untranslated.append((repo, len(code_keys)))
            problems += 1
            continue

        langs = {}
        for lang in LANGS:
            cand = glob.glob(os.path.join(tdir, "*_%s.txt" % lang)) or glob.glob(os.path.join(tdir, "%s.txt" % lang))
            if cand:
                langs[lang] = read_translation(cand[0])
        eng = langs.get("english", {})

        missing_from_english = sorted(code_keys - set(eng))
        gaps = []
        for lang in LANGS[1:]:
            if lang not in langs:
                gaps.append((lang, None))
            else:
                miss = sorted(set(eng) - set(langs[lang]))
                if miss:
                    gaps.append((lang, miss))

        if missing_from_english or gaps:
            behind.append((repo, len(langs), len(eng), missing_from_english, gaps))
            problems += 1
        else:
            clean.append((repo, len(langs), len(eng)))

    print("=" * 96)
    print("TRANSLATION COVERAGE")
    print("=" * 96)

    if untranslated:
        print("\nNO TRANSLATION FILES AT ALL (the page draws English in every language):")
        for repo, n in untranslated:
            print("  %-44s %d key(s) used in code" % (repo, n))

    if behind:
        print("\nBEHIND:")
        for repo, nlang, neng, missing, gaps in behind:
            print("  %s  (%d/11 files, %d english keys)" % (repo, nlang, neng))
            if missing:
                print("      used in code, NOT in english: %s" % ", ".join(missing))
            for lang, miss in gaps:
                if miss is None:
                    print("      %s: FILE MISSING" % lang)
                else:
                    print("      %s: -%d  (%s)" % (lang, len(miss), ", ".join(miss[:8]) +
                                                   (" ..." if len(miss) > 8 else "")))

    if clean:
        print("\nCOMPLETE - every code key in english, all ten languages matching it key-for-key:")
        for repo, nlang, neng in clean:
            print("  %-44s %2d/11 files, %3d keys" % (repo, nlang, neng))

    if only and not (clean or behind or untranslated):
        print("\n%s draws no translated text - nothing to check." % only)
        return 0

    print("\n%d complete, %d behind, %d with no files at all." % (len(clean), len(behind), len(untranslated)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
