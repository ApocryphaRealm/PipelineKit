r"""PreToolUse gate for the Bash and PowerShell tools: refuse starting Mod Organizer 2 directly.

WHY: Claude's shell runs elevated, so an MO2 started straight from it (Start-Process ModOrganizer.exe, & ...exe, cmd
start) runs as administrator, and Windows' UIPI then blocks the owner's screenshot hotkeys (Win+Shift+S, Snipping
Tool, ShareX), typing into MO2's search bar and drag-and-drop. The owner hit it on 2026-09-22 and again on 2026-09-27
("It's not letting me take screenshots of MO2 again") - the second time after three direct launches in one session,
with the mo2-launch role (mo2-launch.ps1, which launches through Explorer, unelevated) already written for exactly this.

Blocks: a command that names ModOrganizer.exe together with a way of starting it (Start-Process, start, &, Invoke-Item,
ii, explorer, or the path as the command itself) and does not go through mo2-launch.ps1. Reading about MO2 (tasklist,
Get-Process, grep of its logs, copying its files) passes. Exit 2 blocks the call and hands this message back.
"""
import json
import re
import sys

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
if data.get("tool_name") not in ("Bash", "PowerShell"):
    sys.exit(0)
cmd = (data.get("tool_input") or {}).get("command") or ""
if not re.search(r"modorganizer\.exe", cmd, re.I) or re.search(r"mo2-launch\.ps1", cmd, re.I):
    sys.exit(0)
launch = re.search(r"start-process|(^|[;&|\s(])start\s|(^|[;&|\s(])&\s*[\"']?[a-z]:|invoke-item|(^|[;&|\s(])ii\s|explorer(\.exe)?\s", cmd, re.I) \
    or re.search(r"(^|[;&|\n]\s*)[\"']?[^\s\"']*modorganizer\.exe[\"']?\s*(-p|\"|$)", cmd, re.I)
readonly = re.search(r"(tasklist|taskkill|get-process|stop-process|get-ciminstance|wmic|grep|select-string|findstr|cp |copy-item|ls |dir )", cmd, re.I)
if launch and not (readonly and not re.search(r"start-process|invoke-item", cmd, re.I)):
    sys.stderr.write(
        "BLOCKED by mo2-elevated-launch-guard: this starts ModOrganizer.exe from Claude's elevated shell, so MO2 would run "
        "as administrator and the owner's screenshot hotkeys and typing stop working in it (2026-09-22, 2026-09-27). "
        "Start it un-elevated instead: from its own shortcut, or a launcher of yours that drops elevation (the original's mo2-launch is not in the kit).\n")
    sys.exit(2)
sys.exit(0)
