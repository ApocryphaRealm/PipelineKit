r"""md-commit (role md-commit) - commit given paths in .MD without racing other sessions for index.lock (item 17,
2026-10-24).

Several sessions commit to .MD; each `git commit` holds .git\index.lock while the pre-commit hook runs, and a second
session's commit then dies on "index.lock: File exists" - or worse, someone deletes a lock that is not theirs. This waits
its turn instead:

  md-commit.py --paths <path> [<path> ...] (--message TEXT | --message-file FILE) [--no-push] [--wait-min 30]
               [--repo <git repo folder>]

  1. waits while .git\index.lock exists (checks every 10 s, says so once a minute) - never removes it; a lock that
     outlives --wait-min is reported with its age and the time it was made, and nothing is committed (exit 3);
  2. adds the given paths (`git add -A -- <paths>`: new files and deletions in them too) and commits ONLY those
     (`git commit -m ... -- <paths>`, the explicit pathspec - other sessions' staged files are left as they are), the
     hooks running as usual;
  3. when the commit failed because another commit took the lock in between, waits again and retries ONCE; a hook that
     REFUSED is reported and not retried (fix it first - a refused gate is never re-run unchanged);
  4. pushes (unless --no-push) and prints "COMMITTED <hash>".
Exit: 0 committed (and pushed), 1 git or the hook refused, 2 usage / nothing to commit, 3 the lock never cleared,
4 committed but the push failed.
"""
import argparse, os, subprocess, sys, time

MD = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
LOCK_RACE = ("index.lock", "Unable to create", "File exists")


def git(repo, *args):
    r = subprocess.run(["git", "-C", repo] + list(args), capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def wait_for_lock(repo, wait_min, say=print, poll=10.0):
    lock = os.path.join(repo, ".git", "index.lock")
    start = time.time()
    told = 0.0
    while os.path.exists(lock):
        waited = time.time() - start
        if waited >= wait_min * 60:
            try:
                made = time.strftime("%H:%M:%S", time.localtime(os.path.getmtime(lock)))
            except OSError:
                made = "?"
            say("md-commit: index.lock (made %s) is still there after %.0f min - another commit, or one that died and left "
                "it. Not removed: only the session that made it may remove it." % (made, waited / 60))
            return False
        if waited - told >= 60 or told == 0.0:
            say("md-commit: waiting for index.lock (another commit is running) - %.0f s so far" % waited)
            told = waited or 0.001
        time.sleep(poll)
    return True


def main(argv, say=print, poll=10.0):
    p = argparse.ArgumentParser(prog="md-commit", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("--paths", nargs="+", required=True)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--message")
    g.add_argument("--message-file")
    p.add_argument("--no-push", action="store_true")
    p.add_argument("--wait-min", type=float, default=30.0)
    p.add_argument("--repo", default=MD)
    try:
        a = p.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    message = a.message if a.message is not None else open(a.message_file, encoding="utf-8").read()
    code, out = git(a.repo, "status", "--porcelain", "--", *a.paths)
    if code:
        say(out.strip()); return 2
    if not out.strip():
        say("md-commit: nothing to commit in %s" % ", ".join(a.paths)); return 2
    for attempt in (1, 2):
        if not wait_for_lock(a.repo, a.wait_min, say, poll):
            return 3
        # a new file is unknown to `commit -- <path>` until it is added; -A takes deletions in these paths too
        code, out = git(a.repo, "add", "-A", "--", *a.paths)
        if code:
            say(out.rstrip())
            if attempt == 1 and any(s in out for s in LOCK_RACE):
                say("md-commit: another commit took the lock first - waiting and trying once more")
                continue
            return 1
        code, out = git(a.repo, "commit", "-m", message, "--", *a.paths)
        say(out.rstrip())
        if code == 0:
            break
        if attempt == 1 and any(s in out for s in LOCK_RACE) and "COMMIT REFUSED" not in out:
            say("md-commit: another commit took the lock first - waiting and trying once more")
            continue
        say("md-commit: the commit did not go in (exit %d)%s" % (code, " - the hook refused it; fix that, then commit again"
                                                                 if "REFUSED" in out else ""))
        return 1
    _, head = git(a.repo, "rev-parse", "--short", "HEAD")
    say("COMMITTED %s" % head.strip())
    if a.no_push:
        return 0
    code, out = git(a.repo, "push", "-q")
    if code:
        say(out.rstrip()); say("md-commit: committed %s but the push failed" % head.strip()); return 4
    say("pushed")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    sys.exit(main(sys.argv[1:]))
