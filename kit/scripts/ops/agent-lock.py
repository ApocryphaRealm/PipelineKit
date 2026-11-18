r"""agent-lock - one writer per resource, enforced by a lock file (the owner approved it 2026-10-12: "Yes").

Several Claude sessions share one PC. On 2026-10-11 a sub-agent saw no game and no MO2 running and launched on a
profile another session was between launches of ("nothing is running" is not "nobody holds it"). The launch, install
and release tools now take a lock through this tool before they touch an MO2 instance, a mod repo or a Nexus page:
a FREE (or stale) lock is taken, a lock the caller holds THE TOKEN of is refreshed, and any other LIVE lock makes the
tool refuse. The bus folder, the format and the stale rule are in .MD\agent-bus\README.md.

EACH ACQUIRER IS ITS OWN HOLDER (2026-10-25): holders were once told apart by session, so a second sub-agent of one
session "acquiring" a lock its sibling held silently REFRESHED it (and overwrote its purpose). Now the lock's TOKEN is
the holder: an acquire refreshes only when it presents the lock's token - its own --token, or a token inherited from an
OUTER call through the environment variable AGENT_LOCK_TOKENS ("<resource>=<token>;...", set by gate() and the
PowerShell tools for the processes they start, and by 'combined-run launch / with' for a batch's instances). Same
session or not, any other acquire of a live lock is REFUSED (or waits with --wait SECONDS). Every acquire and release
needs a token; a tokenless call is a usage error (exit 2), never a silent refresh.

  agent-lock.py acquire   <resource> --token T [--purpose TEXT] [--wait S]   take, or refresh with the lock's token;
                                                                      exit 3 when another acquirer holds it live
  agent-lock.py release   <resource> --token T                        only the lock's own token releases it; an inner
                                                                      call's token leaves its outer call's lock held
  agent-lock.py heartbeat <resource> [--token T] [--watch-pid PID]    the token holder (--token or AGENT_LOCK_TOKENS)
                                                                      refreshes; --watch-pid ties it to a game
  agent-lock.py heartbeat --watch-pid PID                             refresh every lock that game keeps (idle watchdog)
  agent-lock.py status    [<resource>] [--json]
  agent-lock.py force     <resource> --reason TEXT [--purpose TEXT]   take it whoever holds it (logged)
  agent-lock.py register  --holder NAME [--rename yes]                this session's name, against CLAUDE_CODE_SESSION_ID;
                                                                      a different name for a registered session needs
                                                                      --rename yes (a sub-agent must not rename its parent);
                                                                      renaming away from "Main Agent" also needs
                                                                      --owner-confirmed yes (sub-agents: AGENT_SESSION_NAME)
  agent-lock.py whoami

  <resource> is --resource NAME, or --instance <MO2 instance folder or name>, --repo <repo folder>, --nexus <mod key>.
  --holder NAME overrides who the caller is (else AGENT_SESSION_NAME, else the registered name, else session-<id8>).

  A bare positional instance:<Name> is a synonym for --instance <Name> on acquire, release, heartbeat, status and force
  (2026-10-27: two helpers called 'status instance:Njordlinger', got a usage error and read it as "free").

status's FIRST LINE IS THE WHOLE VERDICT (pipeline assessment item 4, 2026-10-27): 'FREE' (exit 0) or
'LOCKED <holder>[, <holder>...]' (exit 3; a corrupt lock file counts as locked, a stale one as free); --json carries the
same token in "status" and exits the same way. Parse the token or the exit code, never the prose under it.

Exit codes: 0 done (status: FREE); 3 HELD - status: LOCKED, acquire: another acquirer's live lock (callers refuse); 4 heartbeat not refreshed (not the token holder, or not held); 2 USAGE - the call was
malformed and NOTHING was checked: the first line printed starts "LOCK STATUS UNKNOWN", and a caller must never read
exit 2 as free (a missing --token included); 1 this tool failed (callers fail open with a warning - a broken lock tool
must not stop every launch). Everything is printed to stdout.
Environment for tests: AGENT_BUS_DIR (the bus folder), AGENT_LOCK_STALE_MINUTES (default 30).
"""
import atexit, ctypes, datetime, json, os, re, sys, time, uuid

STALE_MINUTES_DEFAULT = 30          # the idle watchdog's own default (policy role idle-watchdog-minutes)
HELD = 3
USAGE = 2                           # a malformed call: nothing was checked, so the lock's state is UNKNOWN
UNKNOWN_PREFIX = "LOCK STATUS UNKNOWN"
INSTANCE_ACTIONS = ("acquire", "release", "heartbeat", "status", "force")   # the subcommands that take a resource
CALLER_PID = os.getpid()            # a Python tool that imports gate(); the command line records its caller instead
INSTANCE_ALIASES = {"the witcher 3": "W3"}   # instance folder name -> resource name, where the owner uses a short one


def bus_dir():
    d = os.environ.get("AGENT_BUS_DIR")
    if d:
        return d
    # scripts\ops\agent-lock.py -> .MD\agent-bus (the bus OF THIS TREE, like every tool's resolver lookup)
    return os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "agent-bus"))


def locks_dir():
    d = os.path.join(bus_dir(), "locks")
    os.makedirs(d, exist_ok=True)
    return d


def stale_minutes():
    try:
        return float(os.environ.get("AGENT_LOCK_STALE_MINUTES", STALE_MINUTES_DEFAULT))
    except ValueError:
        return STALE_MINUTES_DEFAULT


def now():
    return datetime.datetime.now().astimezone()


def iso(t):
    return t.isoformat(timespec="seconds")


def parse(s):
    try:
        return datetime.datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


# ---- names -----------------------------------------------------------------------------------------------------------
def instance_resource(value):
    leaf = os.path.basename(os.path.normpath(value.strip().strip('"'))) or value.strip()
    return "instance:" + INSTANCE_ALIASES.get(leaf.lower(), leaf)


def resource_from(args):
    if args.get("resource"):
        return args["resource"].strip()
    if args.get("instance"):
        return instance_resource(args["instance"])
    if args.get("repo"):
        return "repo:" + os.path.basename(os.path.normpath(args["repo"].strip()))
    if args.get("nexus"):
        return "nexus:" + args["nexus"].strip()
    return None


def lock_path(resource):
    return os.path.join(locks_dir(), re.sub(r"[^A-Za-z0-9._-]", "_", resource) + ".json")


# ---- who is calling --------------------------------------------------------------------------------------------------
def sessions_file():
    return os.path.join(bus_dir(), "sessions.json")


def load_sessions():
    try:
        with open(sessions_file(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def identity(holder=None):
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID", "").strip()
    name = (holder or os.environ.get("AGENT_SESSION_NAME", "")).strip()
    if not name and sid:
        name = (load_sessions().get(sid) or {}).get("name", "")
    if not name:
        name = ("session-" + sid[:8]) if sid else "manual:" + os.environ.get("USERNAME", os.environ.get("USER", "user"))
    return name, sid


def same_holder(lock, name, sid):
    """The same SESSION (or name) - for display only. Ownership is the token (holds())."""
    if sid and lock.get("session_id") == sid:
        return True
    return (lock.get("holder") or "").lower() == name.lower()


TOKENS_ENV = "AGENT_LOCK_TOKENS"


def env_tokens(resource):
    """Tokens OUTER calls handed down: AGENT_LOCK_TOKENS="<resource>=<token>;<token>;...". The resource prefix is for
    the reader only - a token is a random 128-bit value that matches only the lock that carries it, so every inherited
    token is offered (the PowerShell tools append their bare token without spelling the resource)."""
    out = []
    for part in os.environ.get(TOKENS_ENV, "").split(";"):
        tok = part.strip().rpartition("=")[2].strip()
        if tok:
            out.append(tok)
    return out


def add_env_token(resource, token, environ=None):
    """Hand this resource's token down to the processes the caller starts (an inner tool then refreshes, never refuses)."""
    environ = os.environ if environ is None else environ
    parts = [p for p in environ.get(TOKENS_ENV, "").split(";") if p.strip()]
    entry = "%s=%s" % (resource, token)
    if entry not in parts:
        parts.append(entry)
    environ[TOKENS_ENV] = ";".join(parts)
    return environ[TOKENS_ENV]


def holds(lock, resource, token):
    """True when the caller presents the lock's own token: its own, or one inherited from an outer call."""
    t = lock.get("token")
    return bool(t) and (t == token or t in env_tokens(resource))


def own_batch_hint(resource, sid):
    """A refused acquirer in the session whose open combined-run batch holds this resource is told how to work inside it."""
    if not sid:
        return ""
    d = os.path.join(bus_dir(), "test-requests", "batches")
    try:
        names = [f for f in os.listdir(d) if f.endswith(".json")]
    except OSError:
        return ""
    for f in names:
        try:
            with open(os.path.join(d, f), encoding="utf-8") as fh:
                b = json.load(fh)
        except (OSError, ValueError):
            continue
        if (isinstance(b, dict) and b.get("state") == "open" and b.get("session_id") == sid
                and resource.lower() in [r.lower() for r in b.get("instances", [])]):
            return ("\n  This session's open combined-run batch %s holds it. Work that belongs INSIDE that batch runs "
                    "with its lock token:\n    resolve.py run combined-run with --batch %s -- <role or script> [args]"
                    % (b.get("id"), b.get("id")))
    return ""


# ---- processes (a lock lives while the game it launched runs) -----------------------------------------------------------
def process_created(pid):
    """Creation time (FILETIME as int) of a RUNNING process, or None when it is not running."""
    if not pid or os.name != "nt":
        return None
    k32 = ctypes.windll.kernel32
    h = k32.OpenProcess(0x1000, False, int(pid))   # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return None
    try:
        code = ctypes.c_ulong()
        if not k32.GetExitCodeProcess(h, ctypes.byref(code)) or code.value != 259:   # STILL_ACTIVE
            return None
        c, e, kt, ut = (ctypes.c_ulonglong() for _ in range(4))
        if not k32.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e), ctypes.byref(kt), ctypes.byref(ut)):
            return None
        return int(c.value)
    finally:
        k32.CloseHandle(h)


def watch_alive(lock):
    pid = lock.get("watch_pid")
    if not pid:
        return False
    created = process_created(pid)
    return created is not None and (not lock.get("watch_created") or int(lock["watch_created"]) == created)


def heartbeat_age_min(lock):
    hb = parse(lock.get("heartbeat"))
    return None if hb is None else (now() - hb).total_seconds() / 60.0


def is_live(lock):
    age = heartbeat_age_min(lock)
    return (age is not None and age < stale_minutes()) or watch_alive(lock)


# ---- files -----------------------------------------------------------------------------------------------------------
def read_lock(path):
    """The lock's dict, None when there is no lock, or {"_corrupt": True} when it cannot be read as JSON."""
    for _ in range(10):
        try:
            with open(path, encoding="utf-8") as f:
                txt = f.read()
        except FileNotFoundError:
            return None
        except PermissionError:
            time.sleep(0.05)
            continue
        try:
            d = json.loads(txt)
            if isinstance(d, dict):
                return d
        except ValueError:
            pass
        time.sleep(0.05)
    return {"_corrupt": True}


def write_tmp(path, data):
    tmp = "%s.%d.%s.tmp" % (path, os.getpid(), uuid.uuid4().hex[:8])
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    return tmp


def create_new(path, data):
    """Atomic create-new: True when this call created the lock, False when one already exists."""
    tmp = write_tmp(path, data)
    try:
        try:
            os.link(tmp, path)          # a hard link appears complete or not at all, and fails when the name exists
            return True
        except FileExistsError:
            return False
        except (OSError, NotImplementedError):
            try:                         # a filesystem without hard links: exclusive create, then write
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                return False
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=1)
            return True
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def replace(path, data):
    tmp = write_tmp(path, data)
    for i in range(20):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.05)
    os.remove(tmp)
    raise OSError("could not replace " + path)


def log(event, resource, **kw):
    rec = {"time": iso(now()), "event": event, "resource": resource}
    rec.update(kw)
    try:
        with open(os.path.join(locks_dir(), "lock-log.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    except OSError:
        pass


def describe(lock):
    age = heartbeat_age_min(lock)
    state = "live" if is_live(lock) else "STALE"
    w = ""
    if lock.get("watch_pid"):
        w = ", game pid %s %s" % (lock["watch_pid"], "running" if watch_alive(lock) else "gone")
    return "%s held by '%s' since %s - %s (heartbeat %s min ago%s) - %s" % (
        lock.get("resource"), lock.get("holder"), lock.get("acquired"), state,
        "?" if age is None else "%.0f" % age, w, lock.get("purpose") or "no purpose given")


def new_lock(resource, name, sid, purpose, token, took_over=None):
    t = iso(now())
    return {"resource": resource, "holder": name, "session_id": sid, "pid": CALLER_PID,
            "host": os.environ.get("COMPUTERNAME", ""), "acquired": t, "heartbeat": t, "purpose": purpose or "",
            "token": token or uuid.uuid4().hex, "watch_pid": None, "watch_created": None, "took_over": took_over}


def usage(msg):
    """(exit 2, message) for a malformed call. The first line says the lock was NOT checked, so no caller can read a
    usage error as 'free' (2026-10-27) - exit 2 is never 0, and neither this text nor the help it prints carries status's free wording."""
    return USAGE, "%s - usage error (exit %d), the lock was NOT checked; do not treat this as free\n%s" % (
        UNKNOWN_PREFIX, USAGE, msg)


# ---- actions ---------------------------------------------------------------------------------------------------------
def acquire(resource, purpose="", token=None, holder=None, force_reason=None, wait=0.0):
    """Returns (exit code, message). 0 = acquired / refreshed / took over, 3 = held live by another acquirer (same
    session or not), 2 = no token (every acquirer is its own holder and must be able to name its lock)."""
    if not token:
        if not force_reason:
            return usage("agent-lock: REFUSED (usage) - acquire %s without --token. Each acquirer is its own holder: pass "
                       "a fresh token (and keep it for the release); a call running inside an outer holder's work "
                       "inherits that holder's token through %s." % (resource, TOKENS_ENV))
        token = uuid.uuid4().hex
    name, sid = identity(holder)
    path = lock_path(resource)
    deadline = time.time() + max(0.0, float(wait or 0))
    tries = 0
    while True:
        tries += 1
        if tries > 50 and time.time() >= deadline:
            break
        if create_new(path, new_lock(resource, name, sid, purpose, token)):
            log("acquire", resource, holder=name, purpose=purpose)
            return 0, "agent-lock: ACQUIRED %s for '%s' (%s)" % (resource, name, purpose or "no purpose given")
        cur = read_lock(path)
        if cur is None:
            continue                                   # released in between: try the create again
        corrupt = cur.get("_corrupt")
        if not corrupt and holds(cur, resource, token) and not force_reason:
            own = cur.get("token") == token
            cur.update({"heartbeat": iso(now()), "pid": CALLER_PID})
            if own and purpose:                        # an inner call never rewrites its outer holder's purpose
                cur["purpose"] = purpose
            replace(path, cur)
            return 0, "agent-lock: REFRESHED %s - %s" % (
                resource, "already held with this token" if own else
                "held by the outer call '%s' this call runs inside (its token)" % cur.get("holder"))
        if not corrupt and is_live(cur) and not force_reason:
            if time.time() < deadline:
                time.sleep(min(2.0, max(0.05, deadline - time.time())))
                continue
            same = same_holder(cur, name, sid)
            log("refused", resource, holder=name, purpose=purpose, held_by=cur.get("holder"), same_session=same)
            who = ("another acquirer of THIS session holds it (each acquirer is its own holder - a sibling sub-agent's "
                   "lock is not yours)" if same else "another session holds it")
            return HELD, ("agent-lock: REFUSED - %s\n  %s. Hand the work to that holder (rule 69), wait for its "
                          "release (--wait SECONDS), or - only if it is truly abandoned - "
                          "'agent-lock force <resource> --reason ...'%s" % (describe(cur), who, own_batch_hint(resource, sid)))
        # stale, corrupt or forced: take it over through a short mutex so two take-overs cannot both win
        why = force_reason and ("forced: " + force_reason) or ("corrupt lock file" if corrupt else "stale")
        mutex = path + ".takeover"
        try:
            fd = os.open(mutex, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(mutex) > 30:
                    os.remove(mutex)                   # left by a take-over that died
            except OSError:
                pass
            time.sleep(0.1)
            continue
        try:
            again = read_lock(path)
            if again != cur:
                continue                               # it changed under us: judge it afresh
            prev = None if corrupt else {k: cur.get(k) for k in ("holder", "session_id", "acquired", "heartbeat", "purpose")}
            new = new_lock(resource, name, sid, purpose, token, took_over=dict(prev or {}, why=why))
            replace(path, new)
            log("force" if force_reason else "take-over", resource, holder=name, purpose=purpose, why=why, previous=prev)
            return 0, "agent-lock: TOOK OVER %s for '%s' (%s) - previous: %s" % (
                resource, name, why, "unreadable" if corrupt else describe(cur))
        finally:
            try:
                os.remove(mutex)
            except OSError:
                pass
    return 1, "agent-lock: could not settle %s after repeated contention" % resource


def release(resource, token=None, holder=None):
    if not token:
        return usage("agent-lock: REFUSED (usage) - release %s without --token. Only the call that took a lock (its token) "
                   "releases it; a lock nobody can name goes stale by itself %g min after its last heartbeat with its "
                   "game gone." % (resource, stale_minutes()))
    name, sid = identity(holder)
    path = lock_path(resource)
    cur = read_lock(path)
    if cur is None:
        return 0, "agent-lock: %s is not held - nothing to release" % resource
    if cur.get("_corrupt"):
        return 0, "agent-lock: %s lock file is unreadable - left for the next acquirer to take over" % resource
    if cur.get("token") != token:
        if cur.get("token") in env_tokens(resource):
            return 0, "agent-lock: %s kept - it was taken by an outer call ('%s'), which releases it" % (
                resource, cur.get("holder"))
        return 0, "agent-lock: %s is held by '%s' under another token, not this call's - left alone" % (
            resource, cur.get("holder"))
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    log("release", resource, holder=name)
    return 0, "agent-lock: RELEASED %s ('%s')" % (resource, name)


def heartbeat(resource=None, watch_pid=None, holder=None, token=None):
    if resource is None:
        if not watch_pid:
            return usage("agent-lock: heartbeat needs a resource or --watch-pid")
        n = 0
        for f in os.listdir(locks_dir()):
            if not f.endswith(".json"):
                continue
            p = os.path.join(locks_dir(), f)
            cur = read_lock(p)
            if cur and not cur.get("_corrupt") and str(cur.get("watch_pid")) == str(watch_pid):
                cur["heartbeat"] = iso(now())
                replace(p, cur)
                n += 1
        return 0, "agent-lock: heartbeat for game pid %s - %d lock(s) refreshed" % (watch_pid, n)
    name, sid = identity(holder)
    path = lock_path(resource)
    cur = read_lock(path)
    if cur is None or cur.get("_corrupt"):
        return 4, "agent-lock: %s is not held - nothing to refresh (acquire it)" % resource
    if not token and not env_tokens(resource):
        return 4, ("agent-lock: %s NOT refreshed - no token (--token or %s); only the lock's own token holder "
                   "refreshes it" % (resource, TOKENS_ENV))
    if not holds(cur, resource, token):
        return 4, "agent-lock: %s is held by '%s' under another token - not refreshed" % (resource, cur.get("holder"))
    cur["heartbeat"] = iso(now())
    if watch_pid:
        created = process_created(watch_pid)
        cur["watch_pid"], cur["watch_created"] = int(watch_pid), created
    replace(path, cur)
    return 0, "agent-lock: heartbeat %s ('%s')%s" % (resource, name, " - tied to game pid %s" % watch_pid if watch_pid else "")


def status(resource=None, as_json=False, holder=None):
    name, sid = identity(holder)
    rows = []
    paths = [lock_path(resource)] if resource else sorted(
        os.path.join(locks_dir(), f) for f in os.listdir(locks_dir()) if f.endswith(".json"))
    for p in paths:
        cur = read_lock(p)
        if cur is None:
            continue
        if cur.get("_corrupt"):
            rows.append({"file": os.path.basename(p), "state": "corrupt"})
            continue
        r = dict(cur, state="live" if is_live(cur) else "stale", mine=same_holder(cur, name, sid),
                 token_held=holds(cur, cur.get("resource") or "", None), heartbeat_age_min=heartbeat_age_min(cur))
        r.pop("token", None)                       # the token is the holder's proof - status never prints it
        rows.append(r)
    # ONE TOKEN, ONE EXIT CODE (pipeline assessment item 4, 2026-10-27): the first line is the whole verdict - 'FREE' or
    # 'LOCKED <holder>[, <holder>...]' - and the exit code says the same (0 free, 3 held; a usage error stays 2 with
    # LOCK STATUS UNKNOWN). Callers parse that token, never the prose below it. A stale lock is FREE (acquire takes it
    # over); a corrupt lock file is LOCKED (nobody can tell who holds it).
    held = []
    for r in rows:
        if r.get("state") == "corrupt":
            held.append("<corrupt lock file %s>" % r["file"])
        elif r.get("state") == "live" and r.get("holder") not in held:
            held.append(r.get("holder") or "?")
    verdict = ("LOCKED " + ", ".join(held)) if held else "FREE"
    code = HELD if held else 0
    if as_json:
        return code, json.dumps({"status": verdict, "you": name, "session_id": sid, "stale_minutes": stale_minutes(),
                                 "locks": rows}, indent=1)
    lines = [verdict, "agent-lock: you are '%s'; a lock is stale after %g min without a heartbeat and with its game gone"
             % (name, stale_minutes())]
    if not rows:
        lines.append("  %s" % ("%s has no lock" % resource if resource else "no locks held"))
    for r in rows:
        lines.append("  " + ("%s: corrupt lock file" % r["file"] if r.get("state") == "corrupt" else
                             describe(r) + ("  (your token)" if r["token_held"] else
                                            "  (your session, another acquirer)" if r["mine"] else "")))
    return code, "\n".join(lines)


def register(holder, rename=False, owner_confirmed=False):
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID", "").strip()
    if not holder:
        return usage("agent-lock: register needs --holder <session name>")
    if not sid:
        return 1, "agent-lock: no CLAUDE_CODE_SESSION_ID in this shell - set AGENT_SESSION_NAME instead"
    os.makedirs(bus_dir(), exist_ok=True)
    s = load_sessions()
    # A sub-agent shares its parent's session id, so a sub-agent's 'register' renamed its parent (2026-10-23: Main
    # Agent's session was found registered under a sub-agent's name). A different name for an already registered
    # session needs --rename yes (the owner renamed the session); the same name just refreshes.
    old = (s.get(sid) or {}).get("name", "")
    if old and old.lower() != holder.lower() and not rename:
        return HELD, ("agent-lock: REFUSED - this session (%s) is already registered as '%s'. A sub-agent shares its "
                      "parent's session and must not rename it - set AGENT_SESSION_NAME for a lock holder name instead; "
                      "if the owner renamed this session, add --rename yes" % (sid[:8], old))
    # Renaming AWAY from Main Agent ends rule 69's launcher role for this session, and a sub-agent of Main did exactly
    # that with --rename yes (2026-10-23), blocking Main's own combined run. Only the owner, or Main itself on his word,
    # moves it: --owner-confirmed yes.
    if old.lower() == "main agent" and holder.lower() != "main agent" and not owner_confirmed:
        return HELD, ("agent-lock: REFUSED - this session (%s) is Main Agent; a sub-agent of Main must never rename it. "
                      "Sub-agents set AGENT_SESSION_NAME for their lock holder name instead. Only on the owner's word: "
                      "--rename yes --owner-confirmed yes" % sid[:8])
    # rule 69's Main Agent is ONE session: registering it moves the name off any earlier session
    if holder.lower() == "main agent":
        for k, v in list(s.items()):
            if k != sid and (v or {}).get("name", "").lower() == "main agent":
                s[k] = dict(v, name="Main Agent (replaced %s)" % iso(now())[:10])
    s[sid] = {"name": holder, "registered": iso(now())}
    path = sessions_file()
    tmp = write_tmp(path, s)
    os.replace(tmp, path)
    return 0, "agent-lock: this session (%s) is '%s'" % (sid[:8], holder)


# ---- for Python tools ------------------------------------------------------------------------------------------------
def gate(resource, purpose, release_at_exit=True, wait=0.0):
    """Acquire for a Python tool with a fresh token of its own: exits 3 on a conflict (another acquirer's live lock,
    same session or not); a lock an OUTER call holds (its token in AGENT_LOCK_TOKENS) is refreshed. The token is handed
    down to the processes this tool starts, and the lock is released at exit when this call took it. A failure of the
    lock machinery itself only warns (fail open). Returns the token (None when continuing without a lock)."""
    token = uuid.uuid4().hex
    try:
        code, msg = acquire(resource, purpose, token, wait=wait)
    except Exception as e:                              # noqa: BLE001 - fail open, by design
        print("agent-lock: WARNING the lock could not be taken (%s) - continuing without it" % e)
        return None
    print(msg)
    if code == HELD:
        sys.exit(HELD)
    if code != 0:
        print("agent-lock: WARNING continuing without the lock")
        return None
    add_env_token(resource, token)
    if release_at_exit:
        atexit.register(lambda: print(release(resource, token)[1]))
    return token


# ---- command line ----------------------------------------------------------------------------------------------------
def parse_args(argv):
    """(action, args). A malformed call raises ValueError (run() turns it into a usage error, exit 2). A bare positional
    'instance:<Name>' is the same as '--instance <Name>' on the subcommands that take a resource."""
    if not argv:
        return None, {}
    action, rest, args, flags = argv[0], argv[1:], {}, {"--json"}
    pos = None
    i = 0
    while i < len(rest):
        a = rest[i]
        if a in flags:
            args[a[2:]] = True
            i += 1
        elif a.startswith("--") and i + 1 < len(rest):
            args[a[2:].replace("-", "_")] = rest[i + 1]
            i += 2
        elif action in INSTANCE_ACTIONS and a.lower().startswith("instance:") and a[len("instance:"):].strip():
            if pos is not None:
                raise ValueError("agent-lock: more than one positional instance (%r)" % a)
            pos = a[len("instance:"):].strip()
            i += 1
        else:
            raise ValueError("agent-lock: unexpected argument %r" % a)
    if pos is not None:
        if args.get("resource") or args.get("repo") or args.get("nexus"):
            raise ValueError("agent-lock: positional instance:%s and another resource option name two resources" % pos)
        if args.get("instance") and instance_resource(args["instance"]) != instance_resource(pos):
            raise ValueError("agent-lock: positional instance:%s disagrees with --instance %s" % (pos, args["instance"]))
        args["instance"] = pos
    return action, args


def main(argv):
    code, msg = run(argv)
    print(msg)
    return code


def run(argv):
    """(exit code, text) for one command line. Every malformed call goes through usage() (exit 2, LOCK STATUS UNKNOWN)."""
    try:
        action, a = parse_args(argv)
    except ValueError as e:
        return usage("%s\n%s" % (e, __doc__))
    if not action or action in ("-h", "--help", "help"):
        return usage(__doc__)
    res = resource_from(a)
    holder = a.get("holder")
    if action == "acquire":
        if not res:
            return usage("agent-lock: acquire needs a resource\n" + __doc__)
        try:
            wait = float(a.get("wait") or 0)
        except ValueError:
            return usage("agent-lock: --wait takes seconds")
        return acquire(res, a.get("purpose", ""), a.get("token"), holder, wait=wait)
    if action == "release":
        if not res:
            return usage("agent-lock: release needs a resource")
        return release(res, a.get("token"), holder)
    if action == "heartbeat":
        return heartbeat(res, a.get("watch_pid"), holder, a.get("token"))
    if action == "status":
        return status(res, bool(a.get("json")), holder)
    if action == "force":
        if not res or not a.get("reason"):
            return usage("agent-lock: force needs a resource and --reason")
        code, msg = acquire(res, a.get("purpose", ""), a.get("token"), holder, force_reason=a["reason"])
        if code == 0 and not a.get("token"):
            msg += "\n  token: %s (keep it: only it releases this lock)" % (read_lock(lock_path(res)) or {}).get("token")
        return code, msg
    if action == "register":
        return register(holder, rename=bool(a.get("rename")), owner_confirmed=bool(a.get("owner_confirmed")))
    if action == "whoami":
        name, sid = identity(holder)
        return 0, "agent-lock: you are '%s' (session %s)" % (name, sid[:8] if sid else "none")
    return usage("agent-lock: unknown action %r\n%s" % (action, __doc__))


if __name__ == "__main__":
    CALLER_PID = os.getppid()       # the shell or script that called this tool
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:                                    # noqa: BLE001
        pass
    try:
        sys.exit(main(sys.argv[1:]))
    except SystemExit:
        raise
    except Exception as e:                               # noqa: BLE001 - exit 1 = the tool failed; callers fail open
        print("agent-lock: ERROR %s: %s" % (type(e).__name__, e))
        sys.exit(1)
