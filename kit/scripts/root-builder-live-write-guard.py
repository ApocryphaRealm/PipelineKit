r"""PreToolUse gate for Bash, PowerShell, Write and Edit: refuse writing into a Root Builder mod's Root folder while
that instance's Root Builder deploy is live.

WHY: on game exit Root Builder copies the deployed game-folder files BACK over the mod folder. Anything written into
<instance>\mods\<mod>\Root\ while the deploy is live (game running, or exited but not yet cleaned up) is silently
reverted, and the next launch tests the OLD file. Logged three times (past-mistakes library: "Root Builder (copy mode)
copies the game folder's deployed files BACK", 2026-09-29; "A deleted test file kept changing the game", "A setting
edited in a Root Builder mod while the game ran was silently reverted", 2026-11-17) and repeated a fourth time on
2026-11-18 (a rebuilt NorseEncounters DLL copied in while the game ran; two relaunches tested the old code). Four
library entries did not stop it, so this is a gate (the owner, 2026-09-16: close loops with gates).

Live = the game of that instance is running, OR the instance's plugins\data\RootBuilder\ holds any file (Root
Builder's deploy record, emptied when its clean-up finishes). Read-only commands pass. A deliberate edit of the mod
folder during a live deploy (expecting the revert) carries the literal marker ALLOW-ROOT-WRITE-WHILE-DEPLOYED.
Exit 2 blocks the call and hands this message back.
"""
import json
import os
import re
import subprocess
import sys

GAMES = ("NorseSteam-Win64-Shipping.exe", "SkyrimSE.exe", "SkyrimVR.exe", "OblivionRemastered-Win64-Shipping.exe",
         "witcher3.exe")
ROOT_PATH = re.compile(r"([A-Za-z]:[\\/][^\"'\n]*?)[\\/]mods[\\/][^\\/\"'\n]+[\\/]Root(?:[\\/]|\b)", re.I)
WRITE_VERB = re.compile(r"(^|[\s;|&(])(cp|mv|rm|rsync|robocopy|xcopy|copy|move|del|tee|install|copy-item|move-item|"
                        r"remove-item|set-content|add-content|out-file|new-item|rename-item|sed\s+-i)\b", re.I)
# a redirect counts only when its target is inside a mod's Root folder (grep ... > elsewhere is a read)
REDIRECT_INTO_ROOT = re.compile(r">>?\s*['\"]?[A-Za-z]:[\\/][^\"'\n]*?[\\/]mods[\\/][^\\/\"'\n]+[\\/]Root[\\/]", re.I)


def drive_path(p):
    # /c/Modlists/... (Git Bash) -> <MO2>/...
    return re.sub(r"(?<![\w:])/([a-zA-Z])/", lambda m: m.group(1).upper() + ":/", p)


def deploy_live(instance):
    rb = os.path.join(instance, "plugins", "data", "RootBuilder")
    for _, _, files in os.walk(rb):
        if files:
            return "Root Builder's deploy record is still present (" + rb + ") - its exit clean-up has not finished"
    try:
        out = subprocess.run(["tasklist", "/NH"], capture_output=True, text=True, timeout=10).stdout.lower()
    except Exception:
        return None
    for g in GAMES:
        if g.lower() in out:
            return g + " is running"
    return None


try:
    data = json.loads(sys.stdin.buffer.read().decode("utf-8-sig") or "{}")
except Exception:
    sys.exit(0)
tool = data.get("tool_name")
ti = data.get("tool_input") or {}
targets = []
if tool in ("Write", "Edit"):
    p = ti.get("file_path") or ""
    m = ROOT_PATH.search(p)
    if m:
        targets.append(m.group(1))
elif tool in ("Bash", "PowerShell"):
    cmd = ti.get("command") or ""
    if "ALLOW-ROOT-WRITE-WHILE-DEPLOYED" in cmd:
        sys.exit(0)
    norm = drive_path(cmd)
    segs = [s for s in re.split(r"[;\n]|&&|\|\|", norm) if s.strip()]
    for s in segs:
        m = ROOT_PATH.search(s)
        if m and (WRITE_VERB.search(s) or REDIRECT_INTO_ROOT.search(s)):
            targets.append(m.group(1))
if not targets:
    sys.exit(0)
for inst in dict.fromkeys(t.replace("/", "\\") for t in targets):
    why = deploy_live(inst)
    if why:
        sys.stderr.write(
            "BLOCKED by root-builder-live-write-guard: this writes into a Root Builder mod folder under " + inst +
            "\\mods\\...\\Root while the deploy is live (" + why + "). On game exit Root Builder copies the deployed "
            "files back over the mod folder, so this change would be silently reverted and the next launch would test "
            "the old file (logged four times, the last on 2026-11-18). Close the game, wait until Root Builder's "
            "clean-up has finished (plugins\\data\\RootBuilder empty), then install. If the revert is intended, add the "
            "marker ALLOW-ROOT-WRITE-WHILE-DEPLOYED.\n")
        sys.exit(2)
sys.exit(0)
