r"""agent-msg - the sessions' message bus: a folder every Claude session can post to, whatever permission mode it runs in.

The owner (2026-11-18 04:40): "set up a multi session communication folder where different sessions can post messages
and set off a script that informs the session they are trying to contact bc i want different sessions to use different
modes while still communicating". Cross-session SendMessage is HELD for approval when the two sessions' permission
modes differ (Main Agent in bypass, the others in auto), and the hold expires undelivered. This bus does not care about
modes: a message is a file in the receiver's inbox folder, and the receiver is informed three ways -
  1. the UserPromptSubmit and SessionStart hooks run `agent-msg hook`, which lists the unread messages for THIS
     session as additional context at its next turn (nothing to arm, nothing to remember);
  2. a session that wants to be woken while idle runs `agent-msg wait` in the background (Bash run_in_background):
     it blocks until a new message lands in its inbox, prints one line per message and exits - one notification;
  3. THE WAKE STEP (the owner, 05:09: "what if the session is idle? how do they read the message?"): an idle session
     has no next prompt and may not have armed `wait`, so after `send` the SENDER wakes it through the desktop app -
     mcp__ccd_session_mgmt__send_message to the receiver's local_... session id (directory.json) with the one-line
     pointer `send` prints - which starts the receiver's turn even across permission modes (the app queues it behind a
     running turn instead of holding it). Then `agent-msg woken --id <id>` records that the wake was sent; `status`
     lists every unread message with its woken state, so an unread, unwoken message is visible to anyone.

Folder: {agent-bus}\messages\
  inbox\<Session Name>\<yyyymmdd-HHMMSS>-<from-slug>-<id>.md   unread messages for that session
  inbox\<Session Name>\read\...                                 the same files once `read` has shown them
  directory.json   {"Main Agent": {"ccd_session_id": "local_...", "note": "..."}, ...} - for the nudge only
  log.jsonl        every send and read (who, to whom, id, subject, when)

Commands (run from any folder: py -3 resolve.py run agent-msg <command> ...):
  send   --to "<Session Name>" --subject "<text>" (--body "<text>" | --file <path>) [--from "<name>"] [--reply-to <id>]
         The sender's name comes from CLAUDE_CODE_SESSION_ID via agent-bus\sessions.json (agent-lock register), else
         AGENT_SESSION_NAME, else --from. --to must be a registered or directory name (or add --new-name yes).
  inbox  [--for "<name>"]            the unread messages for this session (id, from, subject, age)
  read   --id <id> [--keep]          print a message in full and move it to read\ (--keep leaves it unread)
  wait   [--for "<name>"] [--timeout <seconds, default 1500>] [--poll <seconds, default 2>]
         block until a NEW unread message lands (one not present when the wait began), print one line per message,
         exit 0; exit 3 on timeout with nothing printed. For Bash run_in_background.
  woken  --id <id>                   record that the sender sent the wake (a Woken: line in the file, a log entry)
  status                             every unread message in every inbox: id, to, from, age, WOKEN or UNWOKEN
  hook                               for the hooks: reads the hook JSON on stdin (session_id), prints the hook JSON with
                                     an additionalContext line listing the unread messages, or nothing when there are none.
                                     Never fails the prompt: any error prints nothing and exits 0.
  whoami                             the name this shell resolves to, and how
  directory [--set "<name>" --ccd-id local_...] [--note "<text>"]   show or update the nudge directory
Exit codes: 0 ok; 1 usage or missing argument; 2 unknown name or id; 3 wait timed out.
Rule 16 of the bus (README): the id is the first 6 hex of the message sha256 - unique enough, and it never changes.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
MD = os.path.abspath(os.path.join(HERE, "..", ".."))
# AGENT_BUS_DIR is the test seam agent-lock uses too (scripts/tests): the tests never touch the real agent-bus.
BUS = os.environ.get("AGENT_BUS_DIR") or os.path.join(MD, "agent-bus")
MESSAGES = os.path.join(BUS, "messages")
INBOX = os.path.join(MESSAGES, "inbox")
DIRECTORY = os.path.join(MESSAGES, "directory.json")
LOG = os.path.join(MESSAGES, "log.jsonl")
SESSIONS = os.path.join(BUS, "sessions.json")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.()-]{0,60}$")
FILE_RE = re.compile(r"^(\d{8}-\d{6})-([a-z0-9-]+)-([0-9a-f]{6})\.md$")


def now():
    return datetime.datetime.now().astimezone()


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%S%z")[:-2] + t.strftime("%z")[-2:]


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def log(entry):
    os.makedirs(MESSAGES, exist_ok=True)
    entry = dict(entry, when=iso(now()))
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def known_names():
    """Every name a message may be addressed to: registered sessions, directory entries, existing inboxes."""
    names = {}
    for sid, v in (load_json(SESSIONS, {}) or {}).items():
        n = (v or {}).get("name", "")
        if n and not n.lower().startswith("main agent (replaced"):
            names[n.lower()] = n
    for n in (load_json(DIRECTORY, {}) or {}):
        names[n.lower()] = n
    if os.path.isdir(INBOX):
        for n in os.listdir(INBOX):
            if os.path.isdir(os.path.join(INBOX, n)):
                names[n.lower()] = n
    return names


def canonical(name):
    """The name as it is spelled in the registry, so inbox folders never fork on case."""
    return known_names().get((name or "").strip().lower())


def my_name(explicit=None, session_id=None):
    """(name, how). The session's registered name first - a sub-agent shares its parent's session id and must post as
    the parent (the same rule agent-lock register follows)."""
    if explicit:
        return explicit.strip(), "--from/--for"
    sid = (session_id or os.environ.get("CLAUDE_CODE_SESSION_ID", "")).strip()
    if sid:
        n = ((load_json(SESSIONS, {}) or {}).get(sid) or {}).get("name", "")
        if n:
            return n, "sessions.json (%s)" % sid[:8]
    env = os.environ.get("AGENT_SESSION_NAME", "").strip()
    if env:
        return env, "AGENT_SESSION_NAME"
    return "", "unregistered - run agent-lock register --holder <name>, or pass --from/--for"


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "unknown"


def inbox_dir(name):
    return os.path.join(INBOX, name)


def unread(name):
    d = inbox_dir(name)
    if not os.path.isdir(d):
        return []
    out = []
    for fn in sorted(os.listdir(d)):
        m = FILE_RE.match(fn)
        if m:
            out.append(os.path.join(d, fn))
    return out


def parse(path):
    head, body = {}, ""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    parts = text.split("\n---\n", 1)
    for line in parts[0].splitlines():
        if ":" in line and not line.startswith("#"):
            k, v = line.split(":", 1)
            head[k.strip().lower()] = v.strip()
    body = parts[1].strip() if len(parts) > 1 else ""
    return head, body


def one_line(path):
    head, body = parse(path)
    fn = os.path.basename(path)
    m = FILE_RE.match(fn)
    mid = m.group(3) if m else "?"
    try:
        sent = datetime.datetime.strptime(m.group(1) if m else "", "%Y%m%d-%H%M%S")
        age = int((datetime.datetime.now() - sent).total_seconds() // 60)
        age_s = "%d min ago" % age if age < 120 else "%d h ago" % (age // 60)
    except Exception:
        age_s = ""
    return "[%s] from %s, %s: %s" % (mid, head.get("from", "?"), age_s, head.get("subject", "(no subject)"))


# ---- commands --------------------------------------------------------------------------------------------------------

def cmd_send(a):
    sender, how = my_name(a.sender)
    if not sender:
        print("agent-msg: no sender name (%s)" % how)
        return 1
    to = canonical(a.to)
    if not to:
        if a.new_name and NAME_RE.match(a.to or ""):
            to = a.to.strip()
        else:
            print("agent-msg: unknown session name '%s' - known: %s (or --new-name yes to create its inbox)"
                  % (a.to, ", ".join(sorted(known_names().values()))))
            return 2
    if bool(a.body) == bool(a.file):
        print("agent-msg: give exactly one of --body or --file")
        return 1
    body = a.body
    if a.file:
        try:
            with open(a.file, encoding="utf-8") as f:
                body = f.read()
        except Exception as e:
            print("agent-msg: cannot read --file %s: %s" % (a.file, e))
            return 1
    body = body.strip()
    if not body:
        print("agent-msg: empty message")
        return 1
    t = now()
    text = "From: %s\nTo: %s\nSent: %s\nSubject: %s\n%s---\n%s\n" % (
        sender, to, iso(t), a.subject.strip(), ("Reply-to: %s\n" % a.reply_to) if a.reply_to else "", body)
    mid = hashlib.sha256((text + str(time.time())).encode("utf-8")).hexdigest()[:6]
    fn = "%s-%s-%s.md" % (t.strftime("%Y%m%d-%H%M%S"), slug(sender), mid)
    d = inbox_dir(to)
    os.makedirs(os.path.join(d, "read"), exist_ok=True)
    path = os.path.join(d, fn)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text.replace("Subject: %s\n" % a.subject.strip(), "Subject: %s\nId: %s\n" % (a.subject.strip(), mid)))
    log({"event": "send", "id": mid, "from": sender, "to": to, "subject": a.subject.strip(), "file": path})
    print("SENT %s to %s (from %s via %s)" % (mid, to, sender, how))
    print("  file: %s" % path)
    print("  %s sees it at its next prompt (hook), or at once if it runs 'agent-msg wait'." % to)
    entry = (load_json(DIRECTORY, {}) or {}).get(to) or {}
    ccd = entry.get("ccd_session_id")
    pointer = "agent-msg %s from %s: %s - read it with: py -3 \"%s\" run agent-msg read --id %s" % (
        mid, sender, a.subject.strip(), os.path.join(MD, "resolvers", "resolve.py"), mid)
    if ccd:
        print("  WAKE STEP (an idle session has no next prompt): call mcp__ccd_session_mgmt__send_message with session_id=%s and message='%s'"
              % (ccd, pointer))
        print("  then record it: py -3 \"%s\" run agent-msg woken --id %s" % (os.path.join(MD, "resolvers", "resolve.py"), mid))
    else:
        print("  WAKE STEP: no desktop-app session id for %s in directory.json - find it with list_sessions, store it with "
              "'agent-msg directory --set \"%s\" --ccd-id local_...', then send_message with: '%s'" % (to, to, pointer))
    return 0


def cmd_woken(a):
    name, _ = my_name()
    path = find_by_id(a.id)
    if not path:
        print("agent-msg: no message with id %s" % a.id)
        return 2
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if "\nWoken: " in text.split("\n---\n", 1)[0]:
        print("agent-msg: %s was already recorded as woken" % a.id)
        return 0
    head, body = text.split("\n---\n", 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(head + "\nWoken: %s by %s\n---\n" % (iso(now()), name or "?") + body)
    h, _ = parse(path)
    log({"event": "woken", "id": a.id, "by": name or "?", "to": h.get("to", "?")})
    print("agent-msg: %s recorded as woken (%s)" % (a.id, h.get("to", "?")))
    return 0


def cmd_status(_a):
    rows = []
    if os.path.isdir(INBOX):
        for n in sorted(os.listdir(INBOX)):
            for p in unread(n):
                h, _ = parse(p)
                rows.append((("WOKEN " if h.get("woken") else "UNWOKEN"), n, one_line(p)))
    if not rows:
        print("agent-msg: no unread messages in any inbox")
        return 0
    rows.sort(key=lambda r: r[0] != "UNWOKEN")
    print("agent-msg: %d unread message(s); UNWOKEN = the sender has not sent the wake step yet" % len(rows))
    for state, n, line in rows:
        print("  %s  to %-18s %s" % (state, n, line))
    return 0


def cmd_inbox(a):
    name, how = my_name(a.for_name)
    if not name:
        print("agent-msg: no name (%s)" % how)
        return 1
    files = unread(name)
    if not files:
        print("agent-msg: no unread messages for %s" % name)
        return 0
    print("agent-msg: %d unread for %s" % (len(files), name))
    for p in files:
        print("  " + one_line(p))
    print("  read one: py -3 resolve.py run agent-msg read --id <id>")
    return 0


def find_by_id(mid, name=None):
    roots = [inbox_dir(name)] if name else [os.path.join(INBOX, n) for n in os.listdir(INBOX)] if os.path.isdir(INBOX) else []
    for r in roots:
        for sub in ("", "read"):
            d = os.path.join(r, sub)
            if os.path.isdir(d):
                for fn in os.listdir(d):
                    m = FILE_RE.match(fn)
                    if m and m.group(3) == mid:
                        return os.path.join(d, fn)
    return None


def cmd_read(a):
    name, _ = my_name(a.for_name)
    path = find_by_id(a.id, name if name else None) or find_by_id(a.id)
    if not path:
        print("agent-msg: no message with id %s" % a.id)
        return 2
    with open(path, encoding="utf-8") as f:
        print(f.read().rstrip())
    if not a.keep and os.path.basename(os.path.dirname(path)) != "read":
        dest = os.path.join(os.path.dirname(path), "read", os.path.basename(path))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        os.replace(path, dest)
        head, _ = parse(dest)
        log({"event": "read", "id": a.id, "by": name or "?", "from": head.get("from", "?"), "to": head.get("to", "?")})
        print("\n(marked read -> %s)" % dest)
    return 0


def cmd_wait(a):
    name, how = my_name(a.for_name)
    if not name:
        print("agent-msg: no name (%s)" % how)
        return 1
    os.makedirs(os.path.join(inbox_dir(name), "read"), exist_ok=True)
    seen = set(unread(name))
    deadline = time.time() + a.timeout
    while time.time() < deadline:
        time.sleep(a.poll)
        new = [p for p in unread(name) if p not in seen]
        if new:
            for p in new:
                print("agent-msg: NEW MESSAGE for %s %s" % (name, one_line(p)))
            print("  read: py -3 \"%s\" run agent-msg read --id <id>" % os.path.join(MD, "resolvers", "resolve.py"))
            sys.stdout.flush()
            return 0
    return 3


def cmd_hook(_a):
    try:
        raw = sys.stdin.read() if not sys.stdin.isatty() else ""
        data = json.loads(raw) if raw.strip() else {}
        sid = (data.get("session_id") or "").strip()
        name, _ = my_name(None, sid or None)
        if not name:
            return 0
        files = unread(name)
        if not files:
            return 0
        event = data.get("hook_event_name") or "UserPromptSubmit"
        lines = ["AGENT BUS: %d unread message(s) for %s (this session) - another session posted them because cross-session "
                 "messages are held between permission modes:" % (len(files), name)]
        for p in files[:8]:
            lines.append("  " + one_line(p))
        if len(files) > 8:
            lines.append("  ... and %d more" % (len(files) - 8))
        lines.append("Read each with: py -3 \"%s\" run agent-msg read --id <id>  (it is then marked read). Reply with: "
                     "run agent-msg send --to \"<name>\" --subject ... --body ... --reply-to <id>."
                     % os.path.join(MD, "resolvers", "resolve.py"))
        print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": "\n".join(lines)}}))
    except Exception:
        pass
    return 0


def cmd_whoami(_a):
    name, how = my_name()
    print("agent-msg: this shell is '%s' (%s)" % (name or "?", how))
    print("  inbox: %s" % (inbox_dir(name) if name else "-"))
    return 0 if name else 1


def cmd_directory(a):
    d = load_json(DIRECTORY, {}) or {}
    if a.set_name:
        n = canonical(a.set_name) or a.set_name.strip()
        e = d.get(n) or {}
        if a.ccd_id:
            e["ccd_session_id"] = a.ccd_id.strip()
        if a.note:
            e["note"] = a.note
        e["updated"] = iso(now())
        d[n] = e
        save_json(DIRECTORY, d)
        print("agent-msg: directory %s = %s" % (n, json.dumps(e)))
        return 0
    if not d:
        print("agent-msg: directory.json is empty - set one: directory --set \"Main Agent\" --ccd-id local_...")
        return 0
    for n, e in sorted(d.items()):
        print("  %-20s ccd %-50s %s" % (n, e.get("ccd_session_id", "-"), e.get("note", "")))
    return 0


def main(argv):
    p = argparse.ArgumentParser(prog="agent-msg", description=(__doc__ or "").split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd")
    s = sub.add_parser("send"); s.add_argument("--to", required=True); s.add_argument("--subject", required=True)
    s.add_argument("--body"); s.add_argument("--file"); s.add_argument("--from", dest="sender"); s.add_argument("--reply-to")
    s.add_argument("--new-name", default=""); s.set_defaults(fn=cmd_send)
    s = sub.add_parser("inbox"); s.add_argument("--for", dest="for_name"); s.set_defaults(fn=cmd_inbox)
    s = sub.add_parser("read"); s.add_argument("--id", required=True); s.add_argument("--keep", action="store_true")
    s.add_argument("--for", dest="for_name"); s.set_defaults(fn=cmd_read)
    s = sub.add_parser("wait"); s.add_argument("--for", dest="for_name"); s.add_argument("--timeout", type=float, default=1500)
    s.add_argument("--poll", type=float, default=2); s.set_defaults(fn=cmd_wait)
    s = sub.add_parser("woken"); s.add_argument("--id", required=True); s.set_defaults(fn=cmd_woken)
    s = sub.add_parser("status"); s.set_defaults(fn=cmd_status)
    s = sub.add_parser("hook"); s.set_defaults(fn=cmd_hook)
    s = sub.add_parser("whoami"); s.set_defaults(fn=cmd_whoami)
    s = sub.add_parser("directory"); s.add_argument("--set", dest="set_name"); s.add_argument("--ccd-id"); s.add_argument("--note")
    s.set_defaults(fn=cmd_directory)
    a = p.parse_args(argv)
    if not a.cmd:
        print(__doc__)
        return 1
    if a.cmd == "send" and a.new_name and a.new_name.lower() not in ("yes", "y", "true", "1"):
        a.new_name = ""
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
