r"""PreToolUse gate for the Bash tool: refuse a heredoc, printf or echo -e that carries a doubled backslash.

WHY (logic library, 2026-08-29, 2026-09-20, and twice on 2026-09-26): the Bash tool delivers a heredoc body - even a
quoted <<'EOF' one - and printf's format with one level of backslashes removed. A doubled backslash written to mean a
literal backslash arrives single, and Python or printf then reads \r, \n, \a or \v as control characters. It corrupted
a plugin's source (a string literal split by a real line break), a test script, and a to-do line (\a became BEL).
Three library entries did not stop the fourth; this does (the owner, 2026-09-16: "add logic gates to close logic loops").

Blocks: the command contains a heredoc (<<), a printf, or an echo -e, AND a doubled backslash anywhere in it.
Do instead: write the script or text with the Write tool and run the file; or use single backslashes, which survive.
Exit 2 blocks the call and hands this message back to Claude. Anything unparseable passes (never block by accident).
"""
import json
import re
import sys

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
if data.get("tool_name") != "Bash":
    sys.exit(0)
cmd = (data.get("tool_input") or {}).get("command") or ""
risky = re.search(r"<<-?\s*['\"]?\w", cmd) or re.search(r"(^|[;&|\s(])printf\s", cmd) or re.search(r"(^|[;&|\s(])echo\s+-e", cmd)
if risky and "\\\\" in cmd:
    sys.stderr.write(
        "BLOCKED by bash-backslash-guard: this command sends a doubled backslash through a heredoc / printf / echo -e, "
        "and the Bash tool delivers it with one level removed (logic library: four corruptions so far). Write the script "
        "or text to a file with the Write tool and run that file instead.\n")
    sys.exit(2)
sys.exit(0)
