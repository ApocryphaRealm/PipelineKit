r"""THE SCALEFORM-THREAD GATE, ONE CALL DEEP (2026-10-25). Dragon's Eye Minimap 1.7.5 crashed when a settings slider was
held: every change queued ApplyDisplaySettings through SKSE's AddTask, and ApplyDisplaySettings set members, read
getBounds and re-initialised the map on the HUD movie. On SE 1.5.97 AddTask's queue runs as its own BSJobs job beside the
UI job that advances menu movies, so those Scaleform calls raced the movie's own Advance on another thread (crashes
2026-10-25 17:02 inside the HUD advance and 19:55 inside getBounds). Fixed in DEM 1.7.6, commit c23a199: the settings page
only raises a flag (RequestDisplayApply), the minimap applies it from its own Advance() on the HUD thread, and every other
task that touches Scaleform goes through AddUITask.

Gate row scaleform-calls-only-on-the-ui-thread (a regex) refuses a Scaleform call written INSIDE an AddTask lambda. DEM's
own calls were one step away - the lambda called a helper of the mod's, and the helper made the calls - so the regex would
have passed 1.7.5. This script is the second half (row scaleform-helpers-only-on-the-ui-thread). A hit is:
  * an AddTask lambda, or an AddTask(Function) reference, that calls a function of the same repo whose body makes
    Scaleform calls; or
  * a lambda handed to a WRAPPER of the repo's (a function that forwards a callable parameter to AddTask, like DEM's old
    OnMainThread) that makes Scaleform calls itself or calls such a function.
One call deep only. A helper counts as a Scaleform helper when EVERY definition of its name in the repo makes Scaleform
calls outside an AddUITask lambda and none is an 'override' (handlers the movie calls itself, like GFxFunctionHandler::Call
or AdvanceMovie, are already on the UI thread) - a name shared with an unrelated function is left alone rather than guessed.

Usage: python scaleform-ui-thread-gate.py --repo <repo folder> [--path <package>]   (exit 1 on any hit, 0 without a repo)
"""
import argparse, os, re, sys

SKIP = re.compile(r"[\\/](build[^\\/]*|\.git|\.claude|vcpkg_installed|extern|external|third-party|lib|cimgui|imgui)[\\/]", re.I)
EXTS = (".cpp", ".h", ".hpp", ".cxx", ".inl")
# the same tokens as the regex row
GFX = re.compile(r"\.Invoke\(|->Invoke\(|\bSetMember\(|\bGetMember\(|\bSetVariable\(|\bGetVariable\(|\bGotoAndPlay|\bloadClip\b"
                 r"|\bGFx(?:Value|Movie\w*)\b|\buiMovie->|\bgetBounds\b")
KEYWORDS = {"if", "for", "while", "switch", "return", "catch", "sizeof", "decltype", "static_cast", "reinterpret_cast",
            "const_cast", "dynamic_cast", "alignof", "noexcept", "requires", "else", "do", "try", "new", "delete"}
FUNC = re.compile(r"(?:(\w+)::)?(~?\w+)\s*\(([^;{}()]*(?:\([^()]*\)[^;{}()]*)*)\)\s*((?:const|noexcept|override|final|\s)*)"
                  r"(?:->\s*[\w:<>*&\s]+)?\{")
LAMBDA_HEAD = r"\s*\(\s*\[[^\]\n]*\]\s*(?:\([^)]*\))?[^{;)]*\{"
ADDTASK_LAMBDA = re.compile(r"\bAddTask" + LAMBDA_HEAD)
ADDTASK_REF = re.compile(r"\bAddTask\s*\(\s*&?(?:\w+::)*(\w+)\s*\)")
ADDUITASK_LAMBDA = re.compile(r"\bAddUITask" + LAMBDA_HEAD)
CALL = re.compile(r"(?:(?<![\w.>])|->|\.)(\w+)\s*\(")


def strip(t):
    """Blank comments and string / char literals, keeping every offset and newline."""
    out = list(t)
    i, n = 0, len(t)

    def blank(a, b):
        for k in range(a, min(b, n)):
            if out[k] != "\n":
                out[k] = " "
    while i < n:
        c = t[i]
        if t.startswith("//", i):
            j = t.find("\n", i)
            j = n if j < 0 else j
            blank(i, j)
            i = j
        elif t.startswith("/*", i):
            j = t.find("*/", i + 2)
            j = n if j < 0 else j + 2
            blank(i, j)
            i = j
        elif t.startswith('R"', i) and (i == 0 or not (t[i - 1].isalnum() or t[i - 1] == "_")):
            m = re.match(r'R"([^(\s"]*)\(', t[i:i + 20])
            if m:
                end = t.find(")" + m.group(1) + '"', i)
                end = n if end < 0 else end + len(m.group(1)) + 2
                blank(i + 1, end)
                i = end
            else:
                i += 1
        elif c == '"' or (c == "'" and not (i > 0 and t[i - 1].isalnum())):
            j = i + 1
            while j < n and t[j] != c and t[j] != "\n":
                j += 2 if t[j] == "\\" else 1
            blank(i + 1, j)
            i = j + 1
        else:
            i += 1
    return "".join(out)


def close_of(s, i, o="{", c="}"):
    d = 0
    for k in range(i, len(s)):
        if s[k] == o:
            d += 1
        elif s[k] == c:
            d -= 1
            if d == 0:
                return k
    return len(s) - 1


def without_uitask_bodies(body):
    """A helper that queues its own Scaleform work through AddUITask is safe to call from anywhere."""
    out, pos = [], 0
    for m in ADDUITASK_LAMBDA.finditer(body):
        if m.start() < pos:
            continue
        out.append(body[pos:m.end()])
        pos = close_of(body, m.end() - 1)
    out.append(body[pos:])
    return "".join(out)


def is_skse_repo(repo):
    for name in ("CMakeLists.txt", "xmake.lua", "vcpkg.json"):
        p = os.path.join(repo, name)
        if os.path.isfile(p):
            try:
                if re.search(r"(?i)commonlib|skse", open(p, encoding="utf-8", errors="replace").read()):
                    return True
            except OSError:
                pass
    return False


def load(repo):
    files = {}
    for dirpath, dirs, names in os.walk(repo):
        if SKIP.search(dirpath + os.sep):
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if not SKIP.search(os.path.join(dirpath, d) + os.sep)]
        for f in names:
            if f.endswith(EXTS):
                p = os.path.join(dirpath, f)
                try:
                    files[p] = strip(open(p, encoding="utf-8", errors="replace").read())
                except OSError:
                    pass
    return files


def scan(repo):
    files = load(repo)
    defs = {}        # name -> [(file, line, makes_gfx, is_override)]
    wrappers = set()
    for p, s in files.items():
        for m in FUNC.finditer(s):
            name = m.group(2)
            if name in KEYWORDS or name.startswith("~"):
                continue
            ob = m.end() - 1
            body = s[ob:close_of(s, ob)]
            line = s.count("\n", 0, m.start()) + 1
            defs.setdefault(name, []).append((p, line, bool(GFX.search(without_uitask_bodies(body))), "override" in m.group(4)))
            params = m.group(3)
            if re.search(r"std::function|\bauto\b|&&|\bFn\b|\bF\b|\bFunc\b|\bCallable\b", params):
                pnames = [x for x in re.findall(r"(\w+)\s*(?:=[^,]*)?(?:,|$)", params) if x not in ("const", "auto")]
                for t in re.finditer(r"\bAddTask\s*\(", body):
                    args = body[t.end() - 1:close_of(body, t.end() - 1, "(", ")") + 1]
                    if any(re.search(r"\b" + re.escape(pn) + r"\b", args) for pn in pnames):
                        wrappers.add(name)
    helpers = {n: d for n, d in defs.items() if all(x[2] and not x[3] for x in d)}

    def helper_calls(body):
        return sorted({c for c in CALL.findall(body) if c in helpers})

    def where(n):
        return f"{os.path.relpath(helpers[n][0][0], repo)}:{helpers[n][0][1]}"

    hits = []
    sites = [(ADDTASK_LAMBDA, "AddTask", False)]
    if wrappers:
        sites.append((re.compile(r"(?<![\w:])(?:\w+::)*(?:" + "|".join(map(re.escape, sorted(wrappers))) + r")" + LAMBDA_HEAD),
                      "wrapper", True))
    for p, s in files.items():
        rel = os.path.relpath(p, repo)
        for rx, via, direct_counts in sites:
            for m in rx.finditer(s):
                ob = m.end() - 1
                body = s[ob:close_of(s, ob)]
                line = s.count("\n", 0, m.start()) + 1
                head = re.match(r"(?:\w+::)*(\w+)", m.group(0)).group(1)
                if GFX.search(without_uitask_bodies(body)):
                    if direct_counts:   # an AddTask lambda's own calls are the regex row's business
                        hits.append(f"{rel}:{line}: a lambda handed to {head}() (it forwards to AddTask) makes Scaleform calls itself")
                    continue
                called = helper_calls(without_uitask_bodies(body))
                if called:
                    what = "an AddTask lambda" if via == "AddTask" else f"a lambda handed to {head}() (it forwards to AddTask)"
                    hits.append(f"{rel}:{line}: {what} calls " + ", ".join(f"{c} ({where(c)})" for c in called)
                                + ", which make(s) Scaleform calls")
        for m in ADDTASK_REF.finditer(s):
            if m.group(1) in helpers:
                hits.append(f"{rel}:{s.count(chr(10), 0, m.start()) + 1}: AddTask({m.group(1)}) queues {m.group(1)} "
                            f"({where(m.group(1))}), which makes Scaleform calls")
    return sorted(set(hits))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo")
    ap.add_argument("--path")
    a, _ = ap.parse_known_args()
    if not a.repo or not os.path.isdir(a.repo):
        print("scaleform-ui-thread-gate  skip  no repo")
        return 0
    if not is_skse_repo(a.repo):
        print("scaleform-ui-thread-gate  skip  not an SKSE repo")
        return 0
    hits = scan(a.repo)
    for h in hits:
        print(f"FAIL  scaleform-ui-thread-gate  {h} - queue it with AddUITask, or raise a flag the menu serves from its own "
              f"AdvanceMovie/ProcessMessage (DEM c23a199: RequestDisplayApply + Advance())")
    if not hits:
        print("scaleform-ui-thread-gate  pass  no AddTask work reaches Scaleform one call deep")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
