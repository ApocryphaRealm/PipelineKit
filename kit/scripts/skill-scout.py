r"""skill-scout.py - flags work we keep doing by hand that no skill covers yet (the owner, 2026-10-08: "id rather come up
with a gate or other thing that auto flags different things we do as skill worthy which im assuming would be better
that logic gates in some cases").

WHY A SCOUT AND NOT A GATE
--------------------------
A gate refuses a FACT that is checkably wrong (a version literal, a stale overwrite file). Whether a procedure deserves
a skill is a judgement, so this script never blocks and never writes a skill: it REPORTS candidates with the evidence,
the way optimize-project.ps1's REPORT sections do, and a session (or the owner) decides. Each candidate also says
which home it probably wants:
  SKILL   a multi-step procedure that needs judgement and is re-derived from docs each time
  GATE    a single checkable fact that went wrong (better caught mechanically - gate-rules.json)
  RULE    an owner preference stated as a standing instruction (rules part or memory)

WHAT IT READS - the session transcripts, which already record everything we did
-----------------------------------------------------------------------------------
~/.claude/projects/{<project-folder>,<project-folder>}/*.jsonl and each session's subagents/*.jsonl (rolled into the
parent session). Per session it extracts:
  * scripts run   - every *.ps1 / *.py named in a Bash or PowerShell command
  * docs read     - every .md/.txt/.json the Read tool opened under <ROOT>
  * chains        - scripts run within a few calls of each other (a procedure is a chain, not a single call)
  * owner words   - sentences the owner typed with a standing-instruction phrase ("from now on", "every time",
                    "standard", "going forward", "whenever", "make sure") - typed turns and mid-turn queued messages
                    only; tool output, other sessions' messages and system text are skipped
A script or doc is COVERED when its file name appears in any skill under .MD\skills (SKILL.md or its files).

A candidate needs evidence from at least --min-sessions distinct sessions (default 3): one session doing something a
lot is a task, three sessions doing it is a procedure.

DECIDING A CANDIDATE
--------------------
  * worth a skill  -> make or extend the skill (anthropic-skills:skill-creator), the scout then sees it covered
  * not worth one  -> add a line to skill-scout-ignore.txt:  <name>  # <why, date>   so it is never flagged again
New candidates (not flagged by an earlier run) are marked NEW; --todo appends them to the to-do list as one dated
entry so they are not lost.

USAGE
    python skill-scout.py                      report to the console and .MD\logs\skill-scout.md
    python skill-scout.py --todo               also log NEW candidates to the to-do list
    python skill-scout.py --days 30 --min-sessions 3
Parsed sessions are cached by size + mtime in skill-scout.state.json, so a re-run reads only new transcript data.
Exit code 0 always (it is a report, not a gate).
"""
import collections, datetime, json, os, re, sys

if sys.stdout:                          # None under pythonw (the scheduled task): print() is then a no-op
    sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.environ.get("PIPELINE_ROOT") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # kit
MD = os.path.join(ROOT, ".MD")
HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "skill-scout.state.json")
IGNORE = os.path.join(HERE, "skill-scout-ignore.txt")
REPORT = os.path.join(MD, "logs", "skill-scout.md")
TODO = os.path.join(ROOT, "2. Mod Types", "to-do list", "to-do-list.md")
SKILLS = os.path.join(MD, "skills")
_PROJECTS_ROOT = os.path.expanduser(os.path.join("~", ".claude", "projects"))
PROJECTS = [os.path.join(_PROJECTS_ROOT, d) for d in (os.listdir(_PROJECTS_ROOT) if os.path.isdir(_PROJECTS_ROOT) else [])]  # kit: every project

SCRIPT_RE = re.compile(r"([A-Za-z0-9_][A-Za-z0-9_.-]*\.(?:ps1|py))\b")
DOC_RE = re.compile(r"claude output", re.I)
PHRASE_RE = re.compile(r"\b(from now on|going forward|from here on|(?:every|each) time you|whenever you|"
                       r"make (?:it|this|that) (?:part of )?(?:the|a|our) standard|standard (?:rule|template|practice|"
                       r"feature)|standing rule|as a standard|all of our (?:mods|pages)|for every future|"
                       r"on every (?:mod|page))\b", re.I)
AGENT_TEXT = re.compile(r"\bthe owner\b|^\s*(?:task:|you are |continue |\*\*)", re.I)   # prompts another session wrote
SCAN_SKIP = {"build", "extern", "external", ".git", "node_modules", "sdk", "dist", "out", "vcpkg", "vcpkg_installed",
             "__pycache__", "_archive", "_backups", "_removed-20260927", "9. quarantine", "gamewatch-frames", ".worktrees",
             "backups"}   # .MD\backups holds the old _backups, _archive and 9. quarantine since 2026-10-27
CHAIN_WINDOW = 4          # scripts within this many script calls of each other form a chain link
NOISE = {"python.py", "setup.py", "__init__.py", "conftest.py", "skill-scout.py", "quick_validate.py"}


def scripts_on_disk():
    """file names of every script that still exists in the project - a scratchpad one-off or a retired tool is not a
    candidate, because it cannot be put in a skill"""
    names = set()
    for top in (".MD", "6. current wip mods", "11. Nexus distro", "4. plans", ".tools"):   # TestBench: .tools\testbench
        for base, dirs, files in os.walk(os.path.join(ROOT, top)):
            dirs[:] = [d for d in dirs if d.lower() not in SCAN_SKIP and not d.lower().startswith(("build", "vcpkg"))]
            names.update(f.lower() for f in files if f.endswith((".py", ".ps1")))
    return names


def ignored():
    out = set()
    if os.path.isfile(IGNORE):
        for line in open(IGNORE, encoding="utf-8"):
            name = line.split("#", 1)[0].strip().lower()
            if name:
                out.add(name)
    return out


def covered_text():
    parts = []
    for base, _, files in os.walk(SKILLS):
        for f in files:
            if f.endswith((".md", ".py", ".ps1", ".txt", ".json")):
                try:
                    parts.append(open(os.path.join(base, f), encoding="utf-8", errors="replace").read().lower())
                except OSError:
                    pass
    return "\n".join(parts)


def owner_texts(o):
    """typed text of a genuine owner turn, or [] - tool results, system text and other sessions are skipped"""
    if o.get("isSidechain") or o.get("isMeta"):
        return []
    raw = []
    if o.get("type") == "user":
        c = (o.get("message") or {}).get("content")
        if isinstance(c, str):
            raw.append(c)
        elif isinstance(c, list):
            raw += [b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text"]
    elif o.get("type") == "attachment":
        a = o.get("attachment") or {}
        if a.get("type") == "queued_command":
            p = a.get("prompt")
            if isinstance(p, str):
                raw.append(p)
            elif isinstance(p, list):
                raw += [b.get("text", "") for b in p if isinstance(b, dict) and b.get("type") == "text"]
    return [t for t in raw if t and not t.lstrip().startswith("<") and not AGENT_TEXT.search(t[:400])]


def parse_file(path, rec):
    for raw in open(path, "rb"):
        if b'"tool_use"' not in raw and b'"queued_command"' not in raw and not (
                b'"type":"user"' in raw and b'"tool_result"' not in raw):
            continue
        try:
            o = json.loads(raw)
        except ValueError:
            continue
        ts = (o.get("timestamp") or "")[:10]
        if ts:
            rec["first"] = min(rec["first"] or ts, ts)
            rec["last"] = max(rec["last"] or ts, ts)
        for text in owner_texts(o):
            for sent in re.split(r"(?<=[.!?])\s+|\n+", text):
                sent = sent.strip().lstrip("-*\"' ").rstrip("\"' ")
                if PHRASE_RE.search(sent) and 12 <= len(sent) <= 400:
                    rec["phrases"].append([ts, sent])
        if o.get("type") != "assistant":
            continue
        for b in (o.get("message") or {}).get("content") or []:
            if not isinstance(b, dict) or b.get("type") != "tool_use":
                continue
            inp = b.get("input") or {}
            if b.get("name") in ("Bash", "PowerShell"):
                for s in SCRIPT_RE.findall(inp.get("command", "")):
                    s = s.lower()
                    if s not in NOISE and not s.startswith(("tmp", "test_")):
                        rec["scripts"].append(s)
            elif b.get("name") == "Read":
                p = inp.get("file_path", "")
                if DOC_RE.search(p) and p.lower().endswith((".md", ".txt", ".json")):
                    q = p.replace("/", os.sep).lower()
                    i = q.find("claude output" + os.sep)
                    rec["docs"].append(q[i + 14:] if i >= 0 else os.path.basename(q))


def scan(cache):
    sessions = {}
    for proj in PROJECTS:
        if not os.path.isdir(proj):
            continue
        for entry in os.listdir(proj):
            if not entry.endswith(".jsonl"):
                continue
            sid = entry[:-6]
            files = [os.path.join(proj, entry)]
            sub = os.path.join(proj, sid, "subagents")
            if os.path.isdir(sub):
                files += [os.path.join(sub, f) for f in sorted(os.listdir(sub)) if f.endswith(".jsonl")]
            key = "|".join(f"{os.path.getsize(f)}:{int(os.path.getmtime(f))}" for f in files)
            hit = cache.get(sid)
            if hit and hit.get("key") == key:
                sessions[sid] = hit
                continue
            rec = {"key": key, "first": None, "last": None, "scripts": [], "docs": [], "phrases": []}
            for f in files:
                parse_file(f, rec)
            sessions[sid] = rec
    return sessions


def main():
    args = sys.argv[1:]
    days = int(args[args.index("--days") + 1]) if "--days" in args else 45
    min_s = int(args[args.index("--min-sessions") + 1]) if "--min-sessions" in args else 3
    state = json.load(open(STATE, encoding="utf-8")) if os.path.isfile(STATE) else {}
    sessions = scan(state.get("cache", {}))
    since = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    live = {k: v for k, v in sessions.items() if (v["last"] or "") >= since}
    cov, skip = covered_text(), ignored()

    def tally(field):
        n_sess, n_calls = collections.Counter(), collections.Counter()
        for rec in live.values():
            n_calls.update(rec[field])
            n_sess.update(set(rec[field]))
        return n_sess, n_calls

    s_sess, s_calls = tally("scripts")
    d_sess, d_calls = tally("docs")
    chains = collections.Counter()
    for rec in live.values():
        seq, links = rec["scripts"], set()
        for i, a in enumerate(seq):
            for b in seq[i + 1:i + 1 + CHAIN_WINDOW]:
                if a != b:
                    links.add(tuple(sorted((a, b))))
        chains.update(links)

    exists = scripts_on_disk()

    def uncovered(name):
        base = os.path.basename(name)
        return name not in skip and base not in skip and base not in cov

    def real(name):
        return name in exists

    cand = []
    for s, n in s_sess.most_common():
        if n >= min_s and real(s) and uncovered(s):
            cand.append(("script", s, n, s_calls[s]))
    for d, n in d_sess.most_common():
        if n >= min_s and uncovered(d):
            cand.append(("doc", d, n, d_calls[d]))
    # a chain is a procedure only when the two travel together: in at least half the sessions that ran the rarer one
    chain_rows = [(a, b, n) for (a, b), n in chains.most_common()
                  if n >= min_s and real(a) and real(b) and (uncovered(a) or uncovered(b))
                  and a not in skip and b not in skip and f"{a} + {b}" not in skip
                  and n >= 0.5 * min(s_sess[a], s_sess[b])]
    phrases, seen = [], set()
    for rec in live.values():
        for ts, sent in rec["phrases"]:
            k = sent.lower()[:120]
            if k not in seen:
                seen.add(k)
                phrases.append((ts, sent))
    phrases.sort(reverse=True)

    before = set(state.get("flagged", []))
    ids = [f"{k}:{n}" for k, n, *_ in cand] + [f"chain:{a} + {b}" for a, b, _ in chain_rows]
    new = [i for i in ids if i not in before]

    L = [f"# Skill scout - {datetime.date.today().isoformat()}", "",
         f"{len(live)} sessions active in the last {days} days (of {len(sessions)} on disk). A candidate needs "
         f"{min_s}+ sessions. Covered = named in a skill under .MD\\skills. Decide each: make/extend a skill, or add "
         f"it to scripts\\skill-scout-ignore.txt with the reason. Generated by scripts\\skill-scout.py.", "",
         "## Repeated procedures (script chains) - usually SKILL", "",
         "| sessions | chain | new |", "|---:|---|---|"]
    L += [f"| {n} | {a} + {b} | {'NEW' if f'chain:{a} + {b}' in new else ''} |" for a, b, n in chain_rows[:30]] or ["| | none | |"]
    L += ["", "## Scripts run by hand that no skill names - SKILL (part of a procedure) or GATE (one check)", "",
          "| sessions | calls | script | new |", "|---:|---:|---|---|"]
    L += [f"| {n} | {c} | {s} | {'NEW' if f'script:{s}' in new else ''} |" for k, s, n, c in cand if k == "script"] or ["| | | none | |"]
    L += ["", "## Docs re-read across sessions that no skill routes to - SKILL", "",
          "| sessions | reads | doc | new |", "|---:|---:|---|---|"]
    L += [f"| {n} | {c} | {s} | {'NEW' if f'doc:{s}' in new else ''} |" for k, s, n, c in cand if k == "doc"] or ["| | | none | |"]
    L += ["", "## The owner's standing-instruction phrases (newest first) - RULE / memory, or SKILL if it describes steps",
          ""]
    L += [f"- {ts}: \"{s}\"" for ts, s in phrases[:40]] or ["- none"]
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    open(REPORT, "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")

    print(f"skill-scout  {len(live)} sessions ({days}d)  candidates: {len(chain_rows)} chains, "
          f"{sum(1 for c in cand if c[0] == 'script')} scripts, {sum(1 for c in cand if c[0] == 'doc')} docs, "
          f"{len(phrases)} owner phrases  NEW: {len(new)}")
    for i in new[:15]:
        print("  NEW", i)
    print("  report:", REPORT)

    if "--todo" in args and new:
        entry = (f"\n- [ ] **Skill scout - {len(new)} new skill candidate(s) ({datetime.date.today().isoformat()})**: "
                 + "; ".join(new[:12]) + (" ..." if len(new) > 12 else "")
                 + ". Evidence and the owner phrases: `.MD\\logs\\skill-scout.md`. For each: make or extend a skill, or "
                   "add it to `.MD\\scripts\\skill-scout-ignore.txt` with the reason.\n")
        text = open(TODO, encoding="utf-8").read()
        at = text.find("\n## Resolved")
        text = text[:at] + entry + text[at:] if at > 0 else text + entry
        open(TODO, "w", encoding="utf-8", newline="").write(text)
        print("  to-do entry added")

    state = {"cache": sessions, "flagged": sorted(before | set(ids)),
             "lastRun": datetime.datetime.now().isoformat(timespec="seconds")}
    json.dump(state, open(STATE, "w", encoding="utf-8"))


if __name__ == "__main__":
    main()
