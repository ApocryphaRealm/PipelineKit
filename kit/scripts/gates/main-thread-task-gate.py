r"""THE ABANDONED-TASK GATE (2026-09-28). A DevBench tool hands work to the game thread through a helper like

    bool RunOnMainThread(std::function<void()> a_fn, int a_timeoutMs) { tasks->AddTask(...a_fn()...); return cv.wait_for(...); }

and its callers capture their locals BY REFERENCE: RunOnMainThread([&]() { out = DumpJson(); }). While the game thread
is busy (data load, a cell load) the wait times out, the caller returns, its locals die - and seconds later the game
thread runs the task and writes into the dead frame. Loading Menu Overhaul - Model Sync crashed that way on 2026-09-17
(logic library: "A task handed to the game thread that captures locals BY REFERENCE outlives its caller's timeout"), and
Unbind Vanilla Controls 1.1.1's first boot crashed the same way on 2026-09-28: std::string move-assignment inside
UnbindControls.dll, 0xc0000409, from a `dump` sent while the game was still loading data. The lesson was written down
and still shipped, so it is a gate.

A hit is:
  * a call `helper([&...` to a helper defined in the repo whose body queues the function (AddTask / AddUITask) and waits
    with a TIMEOUT (wait_for / wait_until) but never checks a cancelled/abandoned flag before running it; or
  * a direct `AddTask([&` / `AddUITask([&` - a by-reference lambda queued with nobody waiting for it at all.

A helper is safe when the task, under the lock the caller takes on timeout, skips the function once the caller has
given up (a `cancelled` / `abandoned` flag), or when it waits without a timeout.

Usage: python main-thread-task-gate.py --repo <repo folder> [--path <package>]   (exit 1 on any hit, 0 without a repo)
"""
import argparse, os, re, sys

SKIP = re.compile(r"[\\/](build[^\\/]*|\.git|vcpkg_installed|extern|external|third-party|lib|cimgui|imgui)[\\/]", re.I)
EXTS = (".cpp", ".h", ".hpp", ".cxx", ".inl")
HELPER_SIG = re.compile(r"\b(\w+)\s*\(\s*(?:const\s+)?std::function<[^>]*>\s*&?\s*\w+[^)]*\)\s*(?:const\s*)?(?:noexcept\s*)?\{")
QUEUES = re.compile(r"\bAdd(?:UI)?Task\s*\(")
TIMED_WAIT = re.compile(r"\bwait_(?:for|until)\s*\(")
GUARD = re.compile(r"\bif\s*\([^)]*\b\w*(?:cancel|abandon)\w*", re.I)
DIRECT = re.compile(r"\bAdd(?:UI)?Task\s*\(\s*\[\s*&")


def sources(repo):
    for dirpath, dirs, files in os.walk(repo):
        if SKIP.search(dirpath + os.sep):
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if not SKIP.search(os.path.join(dirpath, d) + os.sep)]
        for f in files:
            if f.endswith(EXTS):
                p = os.path.join(dirpath, f)
                try:
                    yield p, open(p, encoding="utf-8", errors="replace").read()
                except OSError:
                    pass


def body_at(text, brace):
    depth = 0
    for i in range(brace, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[brace:i + 1]
    return text[brace:]


def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def scan(repo):
    files = [(p, strip_comments(t)) for p, t in sources(repo)]
    unsafe = {}
    for p, t in files:
        for m in HELPER_SIG.finditer(t):
            body = body_at(t, m.end() - 1)
            if QUEUES.search(body) and TIMED_WAIT.search(body) and not GUARD.search(body):
                unsafe[m.group(1)] = os.path.relpath(p, repo)
    hits = []
    for p, t in files:
        rel = os.path.relpath(p, repo)
        for name, where in unsafe.items():
            for m in re.finditer(r"\b" + re.escape(name) + r"\s*\(\s*\[\s*&", t):
                line = t.count("\n", 0, m.start()) + 1
                hits.append(f"{rel}:{line}: {name}([&...]) - {name} (in {where}) waits with a timeout and then runs the task anyway")
        for m in DIRECT.finditer(t):
            line = t.count("\n", 0, m.start()) + 1
            hits.append(f"{rel}:{line}: a by-reference lambda queued straight to the task interface")
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo")
    ap.add_argument("--path")
    a, _ = ap.parse_known_args()
    if not a.repo or not os.path.isdir(a.repo):
        print("main-thread-task-gate  skip  no repo")
        return 0
    hits = scan(a.repo)
    for h in hits:
        print(f"FAIL  main-thread-task-gate  {h}")
    if hits:
        print("      fix: in the helper, run the function under the lock the caller takes on timeout and skip it once the caller"
              " has given up (a `cancelled` flag set after wait_for fails) - Unbind Vanilla Controls 1.1.1's DevBenchTool.cpp"
              " RunOnMainThread is the pattern")
    else:
        print("main-thread-task-gate  pass  no queued task can outlive its caller")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
