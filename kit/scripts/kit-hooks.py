#!/usr/bin/env python3
"""kit-hooks.py - register this pipeline's Claude Code hooks in a settings.json (README-FOR-AI.md, section 3c).

The original generates its hook commands from its own rosters for its own machine; this is the portable form. It
knows the hooks the pipeline uses and points every command at THIS tree (the .MD folder this script sits under):

  SessionStart       resolvers\\resolve.py run session-start --print   (the rules to read, the rules version)
                     scripts\\ops\\agent-msg.py hook                     (unread messages from other sessions)
  UserPromptSubmit   scripts\\ops\\agent-msg.py hook
  PreToolUse Bash                         scripts\\bash-backslash-guard.py         (a doubled backslash in a heredoc)
  PreToolUse Bash|PowerShell              scripts\\mo2-elevated-launch-guard.py    (starting MO2 directly, elevated)
                                          scripts\\windowed-tool-while-game-guard.py (a tool window over the running game)
  PreToolUse Bash|PowerShell|Write|Edit   scripts\\root-builder-live-write-guard.py (writing into a live Root Builder deploy)

    python kit-hooks.py --print                      the hooks block for this tree, as JSON
    python kit-hooks.py --check [--settings <file>]  exit 0 when every hook above is registered, 1 when one is missing
    python kit-hooks.py --apply [--settings <file>]  merge them in: a backup of the file is written first; entries this
                                                     tool registered before (commands pointing into this tree) are
                                                     replaced, every other hook the person has is kept as it was

Default settings file: %USERPROFILE%\\.claude\\settings.json. Changing it is a persistent configuration change: the
agent asks the person before --apply. Exit 2 on a settings file that is not JSON (nothing is written then).
"""
import argparse, datetime, json, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))           # <ROOT>\.MD\scripts (or the unzipped kit's scripts)
MD = os.path.dirname(HERE)


def cmd(*rel, extra=""):
    p = os.path.join(MD, *rel).replace("\\", "/")
    return f'py -3 "{p}"' + (" " + extra if extra else "")


def wanted():
    return {
        "SessionStart": [{"hooks": [{"type": "command", "command": cmd("resolvers", "resolve.py", extra="run session-start --print")},
                                    {"type": "command", "command": cmd("scripts", "ops", "agent-msg.py", extra="hook")}]}],
        "UserPromptSubmit": [{"hooks": [{"type": "command", "command": cmd("scripts", "ops", "agent-msg.py", extra="hook")}]}],
        "PreToolUse": [
            {"matcher": "Bash", "hooks": [{"type": "command", "command": cmd("scripts", "bash-backslash-guard.py")}]},
            {"matcher": "Bash|PowerShell", "hooks": [{"type": "command", "command": cmd("scripts", "mo2-elevated-launch-guard.py")},
                                                     {"type": "command", "command": cmd("scripts", "windowed-tool-while-game-guard.py")}]},
            {"matcher": "Bash|PowerShell|Write|Edit", "hooks": [{"type": "command", "command": cmd("scripts", "root-builder-live-write-guard.py")}]},
        ],
    }


def ours(command):
    return MD.replace("\\", "/").lower() in (command or "").replace("\\", "/").lower()


def merged(settings):
    out = dict(settings); hooks = dict(out.get("hooks") or {})
    for event, groups in wanted().items():
        kept = []
        for g in hooks.get(event) or []:
            hs = [h for h in (g.get("hooks") or []) if not ours(h.get("command"))]
            if hs:
                kept.append(dict(g, hooks=hs))
        hooks[event] = kept + groups
    out["hooks"] = hooks
    return out


def missing(settings):
    have = {(e, g.get("matcher"), h.get("command")) for e, gs in (settings.get("hooks") or {}).items() for g in gs or []
            for h in g.get("hooks") or []}
    return [f"{e} {g.get('matcher') or ''} {h['command']}".replace("  ", " ") for e, gs in wanted().items() for g in gs
            for h in g["hooks"] if (e, g.get("matcher"), h["command"]) not in have]


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    m = ap.add_mutually_exclusive_group(required=True)
    m.add_argument("--print", action="store_true"); m.add_argument("--check", action="store_true"); m.add_argument("--apply", action="store_true")
    ap.add_argument("--settings", default=os.path.join(os.environ.get("USERPROFILE") or os.path.expanduser("~"), ".claude", "settings.json"))
    a = ap.parse_args(argv)
    if a.print:
        print(json.dumps({"hooks": wanted()}, indent=2)); return 0
    settings = {}
    if os.path.isfile(a.settings):
        try:
            settings = json.load(open(a.settings, encoding="utf-8-sig"))
        except ValueError as e:
            print(f"kit-hooks: {a.settings} is not JSON ({e}) - nothing written"); return 2
    if a.check:
        miss = missing(settings)
        for x in miss: print("kit-hooks: missing " + x)
        print("kit-hooks: " + ("every hook registered" if not miss else f"{len(miss)} hook(s) missing") + f" in {a.settings}")
        return 0 if not miss else 1
    new = merged(settings)
    if new == settings:
        print(f"kit-hooks: already registered in {a.settings} - nothing changed"); return 0
    os.makedirs(os.path.dirname(os.path.abspath(a.settings)), exist_ok=True)
    if os.path.isfile(a.settings):
        bak = a.settings + ".bak-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(a.settings, bak); print(f"kit-hooks: backup {bak}")
    with open(a.settings, "w", encoding="utf-8", newline="\n") as f:
        json.dump(new, f, indent=2); f.write("\n")
    miss = missing(json.load(open(a.settings, encoding="utf-8")))
    print(f"kit-hooks: registered {sum(len(g['hooks']) for gs in wanted().values() for g in gs)} hook command(s) in {a.settings}"
          + (f"; STILL MISSING {miss}" if miss else ""))
    return 0 if not miss else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
