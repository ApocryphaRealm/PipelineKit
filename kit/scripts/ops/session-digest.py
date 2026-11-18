r"""session-digest.py - one short digest per Claude session transcript, so archived sessions can be checked for work
that was asked for or left open and never made it into the to-do list, a handoff or the logic library (the owner,
2026-10-08: "can we scan old archived sessions for things we missed or didnt transfer out of the session before
archiving and checking it against the current info to see if its currently resolved or still open?").

This is the MECHANICAL half: it only extracts. The judgement - is each item resolved, recorded, or lost - is made
afterwards against the current files (to-do list, handoffs, CHANGELOGs, ledger, logic library, memories), by the main
session or one sub-agent at a time (sub-agent-routing.md), and lost items are added to the to-do list.

Per session it writes .MD\logs\session-digests\<first date>_<id8>_<title>.md with:
  * the session's title / agent name, date range, size
  * EVERY message the owner typed (typed turns and mid-turn queued messages; tool output, other sessions' messages
    and system text are skipped - same filter as skill-scout.py), trimmed to 1,500 characters each
  * the session's last 8 reports (assistant text), and any earlier report that names open work
    ("still open", "not yet", "next step", "waiting on", "to-do", "left", "unfinished", "pending", "blocked")

    python session-digest.py [--exclude <session id> ...]
The current session should be excluded (it is not archived). Prints one line per digest. Read-only on transcripts.
"""
import datetime, importlib.util, json, os, re, sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
# skill-scout.py stays in the core scripts folder: asked of the resolver of THIS tree (STEPS 5.10)
import subprocess
_r = subprocess.run([sys.executable, os.path.join(HERE, "..", "..", "resolvers", "resolve.py"), "find", "skill-scout"], capture_output=True, text=True)
_scout_path = _r.stdout.strip()
if _r.returncode != 0 or not _scout_path: sys.exit("session-digest: cannot resolve role 'skill-scout'")
spec = importlib.util.spec_from_file_location("scout", _scout_path)
scout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scout)
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs", "session-digests")  # kit: <ROOT>\.MD\logs
OPEN_RE = re.compile(r"still open|not yet|next step|waiting (?:on|for)|to-do|todo|left to|unfinished|pending|blocked|"
                     r"not done|didn'?t get to|remaining|follow-?up|open item|handoff|hand-off", re.I)


# Secrets are never copied into a digest (2026-10-08: a Claude login token the owner had pasted on 2026-09-25 reached a
# digest in plain text). Anything shaped like an API key, OAuth token or JWT is replaced before it is written.
# 2026-10-08, second pass: an OAuth AUTHORIZATION CODE (pasted from a login page, often "code#state") got past the
# first patterns. So also: any credential-named query/assignment value, and any long run of mixed-case letters AND
# digits (the shape of a random secret). Lower-case hex (SHA-256 hashes, git commits) is left alone - it is evidence.
SECRET_RE = re.compile(
    r"sk-ant-[A-Za-z0-9_-]{8,}|sk-[A-Za-z0-9]{20,}|eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_.-]{10,}|"
    r"(?i:(?:api[_-]?key|token|secret|password|bearer|code|auth(?:orization)?(?:[ _-]code)?|client[_-]?secret|"
    r"refresh[_-]?token|access[_-]?token|state)[\"'\s:=]+)[A-Za-z0-9_\-.#%]{20,}|"
    r"(?=[A-Za-z0-9_\-#]*[a-z])(?=[A-Za-z0-9_\-#]*[A-Z])(?=[A-Za-z0-9_\-#]*[0-9])[A-Za-z0-9_\-#]{20,}")
REDACTED = [0]


def redact(t):
    t, n = SECRET_RE.subn("[REDACTED]", t)
    REDACTED[0] += n
    return t


def clip(t, n):
    t = redact(t.strip())
    return t if len(t) <= n else t[:n] + " [...]"


def digest(sid, files):
    title, owner, reports, first, last = "", [], [], None, None
    for f in files:
        for raw in open(f, "rb"):
            if b'"custom-title"' in raw or b'"agent-name"' in raw:
                try:
                    o = json.loads(raw)
                    title = o.get("customTitle") or o.get("agentName") or title
                except ValueError:
                    pass
                continue
            if not (b'"type":"user"' in raw or b'"queued_command"' in raw or b'"type":"assistant"' in raw):
                continue
            if b'"type":"user"' in raw and b'"tool_result"' in raw:
                continue
            try:
                o = json.loads(raw)
            except ValueError:
                continue
            if o.get("isSidechain"):
                continue                                   # sub-agent internals; their results reach the parent
            ts = (o.get("timestamp") or "")[:16].replace("T", " ")
            if ts:
                first, last = min(first or ts, ts), max(last or ts, ts)
            for t in scout.owner_texts(o):
                owner.append((ts, clip(t, 1500)))
            if o.get("type") == "assistant":
                for b in (o.get("message") or {}).get("content") or []:
                    if isinstance(b, dict) and b.get("type") == "text" and len(b.get("text", "")) > 200:
                        reports.append((ts, b["text"]))
    keep = reports[-8:]
    flagged = [r for r in reports[:-8] if OPEN_RE.search(r[1])][-12:]
    size = sum(os.path.getsize(f) for f in files)
    name = re.sub(r"[^A-Za-z0-9-]+", "-", title or "untitled").strip("-")[:40]
    path = os.path.join(OUT, f"{(first or '0000-00-00')[:10]}_{sid[:8]}_{name}.md")
    L = [f"# Session {sid}", "", f"- title: {title or '(none)'}", f"- span: {first} -> {last}",
         f"- transcript size: {size / 1e6:.1f} MB ({len(files)} files)", f"- owner messages: {len(owner)}", "",
         "## What the owner typed (in order)", ""]
    L += [f"**{ts}** - {t}\n" for ts, t in owner] or ["(none)"]
    L += ["", "## Earlier reports that mention open work", ""]
    L += [f"**{ts}**\n\n{clip(t, 2500)}\n" for ts, t in flagged] or ["(none)"]
    L += ["", "## The session's last reports", ""]
    L += [f"**{ts}**\n\n{clip(t, 4000)}\n" for ts, t in keep] or ["(none)"]
    open(path, "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
    return path, first, len(owner), size


def main():
    args = sys.argv[1:]
    exclude = set(args[args.index("--exclude") + 1:]) if "--exclude" in args else set()
    os.makedirs(OUT, exist_ok=True)
    rows = []
    for proj in scout.PROJECTS:
        if not os.path.isdir(proj):
            continue
        for entry in sorted(os.listdir(proj)):
            if not entry.endswith(".jsonl") or entry[:-6] in exclude:
                continue
            sid = entry[:-6]
            rows.append((sid, [os.path.join(proj, entry)]))
    for sid, files in rows:
        path, first, n, size = digest(sid, files)
        print(f"{(first or '?')[:10]}  {n:4d} owner msgs  {size / 1e6:7.1f} MB  {os.path.basename(path)}")
    print(f"{len(rows)} digests -> {OUT}  ({datetime.datetime.now():%Y-%m-%d %H:%M})  secrets redacted: {REDACTED[0]}")


if __name__ == "__main__":
    main()
