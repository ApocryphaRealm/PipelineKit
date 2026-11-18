r"""THE UNKNOWN-ESCAPE GATE (2026-09-27). Perfected Wheeler read its debug.ini from "Data\SKSE\Plugins\wheeler\debug.ini"
written with SINGLE backslashes: C++ reads \S, \P, \w, \d as unknown escapes, the path became
"DataSKSEPluginswheelerdebug.ini", the file was never found and the log ran at trace whatever the INI said - from 1.1.4
until 1.3.8. The compiler only warns (C4129). This fails a repo whose own C++ has an ordinary string literal with a
backslash before a character C++ gives no meaning to. #include lines and raw strings R"(...)" are not checked.

Usage: python cpp-escape-gate.py --repo <repo folder> [--path <package>]   (exit 1 on any hit, 0 without a repo)
"""
import argparse, os, re, sys

SKIP = re.compile(r"[\\/](build[^\\/]*|\.git|vcpkg_installed|extern|external|third-party|lib|cimgui|imgui)[\\/]", re.I)
LIT = re.compile(r'(?<![A-Za-z0-9_R])"((?:[^"\\\n]|\\.)*)"')
VALID = set("ntr0abfv\\\"'?xuU1234567\n")


def scan(repo):
    hits = []
    for dirpath, dirs, files in os.walk(repo):
        if SKIP.search(dirpath + os.sep):
            dirs[:] = []
            continue
        for f in files:
            if not f.endswith((".cpp", ".h", ".hpp", ".cxx", ".inl")):
                continue
            p = os.path.join(dirpath, f)
            try:
                lines = open(p, encoding="utf-8", errors="replace").read().splitlines()
            except OSError:
                continue
            for n, line in enumerate(lines, 1):
                s = line.strip()
                if s.startswith(("//", "*", "#include", "# include")):
                    continue
                for m in LIT.finditer(line):
                    body, i = m.group(1), 0
                    while i < len(body):
                        if body[i] == "\\" and i + 1 < len(body):
                            if body[i + 1] not in VALID:
                                hits.append(f"{os.path.relpath(p, repo)}:{n}: {s[:120]}")
                                break
                            i += 2
                            continue
                        i += 1
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo")
    ap.add_argument("--path")
    a, _ = ap.parse_known_args()
    if not a.repo or not os.path.isdir(a.repo):
        print("cpp-escape-gate  skip  no repo")
        return 0
    hits = scan(a.repo)
    for h in hits:
        print(f"FAIL  cpp-escape-gate  {h} - a backslash before a letter C++ gives no meaning to; write paths with / or \\\\")
    if not hits:
        print("cpp-escape-gate  pass  no string literal with an unknown escape")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
