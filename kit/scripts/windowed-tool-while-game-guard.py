r"""PreToolUse gate for the Bash and PowerShell tools: refuse starting a windowed modding tool while Skyrim is running.

WHY: a tool window that opens over the running game takes the foreground from SkyrimSE. The owner, 2026-11-16 05:10,
while playing: "Pandora just popped over the game, block that kind of thing while the game is running". Earlier the
same night BodySlide windows opened by a packager stole focus twice during a test batch, so the tester lost frames and
input and the game's FPS throttled (batch B-20261116-024232-74eb).

Blocks: a command that names one of the windowed tools (or a script known to start one) while SkyrimSE.exe is running.
Read-only commands that merely mention a tool (tasklist, Get-Process, grep, cat, ls, git) pass. A deliberate exception
carries the literal marker ALLOW-WINDOW-WHILE-GAME in the command, and only when the owner has said so for that run.
Exit 2 blocks the call and hands this message back.
"""
import json
import re
import subprocess
import sys

TOOLS = (r"pandora|bodyslide|outfitstudio|outfit studio|nemesis|fnis|sseedit|xedit|tes5edit|dyndolod|texgen|xlodgen|"
         r"loot\.exe|synthesis|blender(?!.*\s-b\b)(?!.*--background)|"
         r"build-package\.py|build-fomod\.py|build3d_bodies\.py|pandora-run|bodyslide-batch")
READONLY = r"^\s*(tasklist|get-process|get-ciminstance|grep|rg|cat|head|tail|ls|dir|git|sed|awk|wc|find|select-string|echo)\b"

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
if data.get("tool_name") not in ("Bash", "PowerShell"):
    sys.exit(0)
cmd = (data.get("tool_input") or {}).get("command") or ""
if "ALLOW-WINDOW-WHILE-GAME" in cmd:
    sys.exit(0)
# text is not a launch: drop heredoc bodies, then quoted strings - except a quoted path to a program or script
# ("D:/.../build-package.py", "...\BodySlide x64.exe"), which is what a launch quotes
cmd = re.sub(r"<<-?\s*['\"]?(\w+)['\"]?.*?\n.*?\n\1\b", " ", cmd, flags=re.S)
cmd = re.sub(r"'[^'\n]*'|\"[^\"\n]*\"",
             lambda m: m.group(0) if re.search(r"\.(exe|py|ps1|bat|cmd)['\"]$", m.group(0), re.I) else " ", cmd)
if not re.search(TOOLS, cmd, re.I):
    sys.exit(0)
# every pipeline segment read-only -> pass
segs = [s for s in re.split(r"[;|&\n]+", cmd) if s.strip()]
if segs and all(re.match(READONLY, s, re.I) for s in segs):
    sys.exit(0)
try:
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq SkyrimSE.exe", "/NH"], capture_output=True, text=True,
                         timeout=10).stdout
except Exception:
    sys.exit(0)
if "SkyrimSE.exe" not in out:
    sys.exit(0)
sys.stderr.write(
    "BLOCKED by windowed-tool-while-game-guard: SkyrimSE.exe is running, and this command starts a tool with its own "
    "window (Pandora, BodySlide, Outfit Studio, xEdit, a packager that runs BodySlide, ...). Its window would pop over "
    "the game and take focus (the owner, 2026-11-16: \"block that kind of thing while the game is running\"). Wait "
    "until the game is closed, or run the tool hidden/in background mode. Only if the owner said so for this run, add "
    "the marker ALLOW-WINDOW-WHILE-GAME to the command.\n")
sys.exit(2)
