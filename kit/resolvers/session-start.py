#!/usr/bin/env python
"""session-start.py - the SessionStart hook payload, generated from the rosters and the rules marker.

Usage: session-start.py --print

Writes to stdout the JSON object
{"systemMessage": ..., "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ...}}.
Every path comes from  resolve.py find <role>  (subprocess); the rule count and version come from
CLAUDE.md's  <!-- RULES-VERSION: X | N rules | date -->  marker. Three live one-line checks
(resolve.py check --callers, memory-index.py --check, test-request stats - the week's test verdicts, 2026-10-27) end
the context, each with a 5-second timeout.
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RESOLVE = os.path.join(HERE, "resolve.py")
TIMEOUT = 5
HINT = " - see optimize-project.ps1 -Section resolvers"

SYSTEM_MESSAGE = ("Project rules: read CLAUDE.md, RULES-DIGEST.md and PREFLIGHT.md in {MD} "
                  "before starting work; read a rules PART in full when entering its stage.")

TEMPLATE = r"""MANDATORY FIRST ACTION FOR THIS SESSION - standing instruction from the project owner (2026-09-03, amended by him 2026-09-07 to the middle path): before doing ANY work, read THREE files in {MD}\ - (1) CLAUDE.md: the rules version ({VERSION}), the always-on rules, the index of all {COUNT} rules and the table mapping pipeline stages to the seven rule parts; (2) RULES-DIGEST.md: ONE PAGE generated from the seven parts (every rule's heading, its latest dated amendment and its opening sentences) - this replaces reading all seven parts up front; (3) PREFLIGHT.md: ONE SCREEN of WHEN/DO lines - at the moment you are about to implement anything, match what you are doing against its WHEN column; if it matches, the approach is already decided and you apply it rather than choosing one. THEN, whenever work enters a pipeline stage, read that stage's PART in full from {RULES}\ (01 pipeline topology, 02 build toolchain, 03 versioning and release, 04 code standards, 05 testing and MO2, 06 reasoning discipline, 07 operations and machine health) - a session that starts as one kind of work often turns into another, and the full part is read at the turn, not skipped. {LL} records past failures: read its index block at start, and BEFORE ACTING IN ANY AREA grep that index for the area's topics and read the entries it points to (the owner, 2026-09-12: pre-emptive, so a logged mistake is avoided rather than recognised after it repeats); symptom lookup after a failure is the second use; never read it end to end. The memory index {MEMIDX} is read the same way: grep it for the area's topics before acting there and read the memories it names (the owner, 2026-10-08); the auto-loaded MEMORY.md holds only the always-on set. Project scripts, data files and places are called by ROLE through {RESOLVE} (find / run / place), never by a remembered path - a path recalled from an earlier session is the commonest way a retired script gets called. SESSIONS TALK THROUGH THE MESSAGE BUS (the owner, 2026-11-18): at start register this session's name once ({RESOLVE} run agent-lock register --holder "<Session Name>") and check its inbox ({RESOLVE} run agent-msg inbox); send to another session with {RESOLVE} run agent-msg send --to "<Session Name>" --subject .. --body .. (the file in its inbox IS the message - its prompt hooks list it at its next turn), THEN WAKE IT, because an idle session has no next prompt: call mcp__ccd_session_mgmt__send_message to its desktop-app session id with the pointer line send prints, and record it with run agent-msg woken --id <id> (run agent-msg status shows what is still UNWOKEN); read what arrives with run agent-msg read --id <id>. A cross-session SendMessage is HELD for approval and expires undelivered when the two sessions' permission modes differ, so it is at most a nudge, never the only copy. Do not report the session as ready, and do not begin the user's task, until the three files have actually been read in this session. Sub-agents may READ the past-mistakes library but never WRITE to it (the owner, 2026-09-07); their lessons come back in their report file.
{STATUS}"""


def find(role):
    p = subprocess.run([sys.executable, RESOLVE, "find", role],
                       capture_output=True, text=True, encoding="utf-8")
    lines = [l.strip() for l in p.stdout.splitlines() if l.strip()]
    if p.returncode != 0 or len(lines) != 1:
        sys.stderr.write("resolve.py find %s failed (exit %d): %s%s\n"
                         % (role, p.returncode, p.stdout, p.stderr))
        sys.exit(2)
    return lines[0]


def check_line(label, cmd):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return "CHECK: %s did not answer in %d s" % (label, TIMEOUT)
    except OSError as e:
        return "CHECK: %s could not run (%s)%s" % (label, e, HINT)
    out = [l for l in (p.stdout or "").splitlines() if l.strip()]
    first = out[0].strip() if out else "(no output)"
    return "CHECK: " + first + (HINT if p.returncode != 0 else "")


def build():
    claude_md = find("claude-md")
    md = os.path.dirname(claude_md)
    with open(claude_md, "r", encoding="utf-8") as f:
        m = re.search(r"<!-- RULES-VERSION: (\S+) \| (\d+) rules", f.read())
    if not m:
        sys.stderr.write("no RULES-VERSION marker in %s\n" % claude_md)
        sys.exit(2)
    version, count = m.group(1), m.group(2)
    resolve_path = find("resolve")
    mem_tool = find("memory-index-tool")
    status = "\n".join([
        check_line("resolve.py check --callers", [sys.executable, resolve_path, "check", "--callers"]),
        check_line("memory-index.py --check", [sys.executable, mem_tool, "--check"]),
        # the week's test verdicts and top failure reasons (pipeline assessment item 7, 2026-10-27)
    ])
    values = {
        "MD": md,
        "RULES": find("md-rules"),
        "LL": find("past-mistakes-library"),
        "MEMIDX": find("memory-index"),
        "RESOLVE": resolve_path,
        "COUNT": count,
        "VERSION": version,
    }
    text = TEMPLATE
    for k, v in values.items():
        text = text.replace("{%s}" % k, v)
    text = text.replace("{STATUS}", status)
    return {
        "systemMessage": SYSTEM_MESSAGE.replace("{MD}", md),
        "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text},
    }


def main(argv):
    if argv != ["--print"]:
        sys.stderr.write("usage: session-start.py --print\n")
        return 2
    payload = build()
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
