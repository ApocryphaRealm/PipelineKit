#!/usr/bin/env python3
"""kit_screen.py - the screening half of the Pipeline Kit build (2.x, for posting on Nexus Mods' Modding Tools).

Nexus's file rules, the owner's decision and this file's job, in one place:
  * nothing shipped makes a network call: the three network tools are cut (OPTIONAL-SCRIPTS.md says how to build them
    if the person asks) and the network parts of the scripts that are otherwise needed are removed (patch_script);
  * no direct evidence from other authors' mods: code, disassembly, byte signatures, offsets, record IDs, asset paths.
    Documents keep each mod's name, what the issue was, how it was fixed, what got in the way and the lesson;
  * no advertising and nothing private.

The transform runs in the build: the live documents are never edited. kit-src\\screen\\overrides.json holds the small
part that cannot be mechanical (a paragraph that has to be reworded, a whole library entry). screen_tree() is the
gate: it FAILS the build when a shipped file still carries a network call or evidence of the classes below.

WHAT COUNTS AS EVIDENCE (the stated scanner: EVIDENCE below, one regex per class)
  byte-pattern   3+ space-separated upper-case hex bytes holding a letter or a ?? wildcard; a back-ticked byte run
  disassembly    a mnemonic with register operands; a [register+...] memory operand
  module-offset  module.exe+ABC123, module.dll+0x..., bare +05F47CB, "12345+0x4B" (Address Library id plus offset)
  hex-literal    any 0x... literal in a document
  record-id      6-8 upper-case hex digits holding a digit and a letter, or 00nnnnnn; plugin.esm|123ABC; form id 12EB7
  address-id     REL::ID(n), RelocationID(n), "id 12345", "SE 12345", "AE 67890", chains "80949 <- 81006"
  source-ref     file.ws:123, file.h:12-34, file.cpp:9, file.as:5 (line references into source)
  asset-path     a folder path ending in a game asset (.nif .dds .hkx .swf .gfx .pex .psc .bsa .ba2 ...), or a bare
                 .pex .psc .nif .hkx .as name
  code-quote     (library only) a fenced block that is not our own tooling; an indented source line; an inline code span
                 with source syntax (50+ characters; 15+ for a statement); decompiler names (_loc1_); GameDelegate calls
"""
from __future__ import annotations

import json
import os
import re

# --- what is cut ---------------------------------------------------------------------------------------------------

CUT_SCRIPTS = ["release/nexus-upload.py", "release/nexus-version-audit.py", "release/nexus-media-backup.py"]
CUT_DATA = ["game-signatures.json"]              # byte signatures of a game executable, read by nothing in the kit
CUT_SKILL_FILES = {
    "in-game-test/references/SKYRIM-CONSOLE-COMMANDS.md",        # compiled from wikis and other authors' READMEs
    "nexus-page/references/FRAMEWORK-LICENCE-AND-CREDITS.md",    # quotes other projects' licence texts
}
CUT_DOCS = ["MACHINE-HEALTH.md"]                 # one PC's hardware and history; kit-src\docs has the design without it
CUT_TEMPLATES = ["11. Nexus distro/_CHANGELOG-TEMPLATE.txt"]    # another mod's changelog; kit-src\templates replaces it
DROPPED_GATE_ROWS = {
    "page-carries-the-donation-link", "page-discord-link-is-the-invite", "page-discord-link-is-an-invite",
    "page-no-own-repo-link-while-pushes-paused",
    # these two spell a private identifier inside their pattern; the kit's own leak scan does this job here
    "shipped-text-carries-no-machine-identity", "shipped-text-carries-no-owner-name",
}
DROPPED_IDENTITY_ROLES = {"patreon", "discord-invite"}

# the names a document may still mention; every document that does gets KIT_NOTE under its title
CUT_NAMES_RE = re.compile(r"nexus-upload|nexus-version-audit|nexus-media-backup|game-signatures|SKYRIM-CONSOLE-COMMANDS|"
                          r"FRAMEWORK-LICENCE-AND-CREDITS|framework-licence-credits|console-commands")
KIT_NOTE = ("> *Kit edition: this document was reduced for publication. Tools it names that reach the internet "
            "(`nexus-upload.py`, `nexus-version-audit.py`, `nexus-media-backup.py`) are not in the kit - see "
            "`OPTIONAL-SCRIPTS.md`. Other tools it names may belong to the original pipeline only (README-FOR-AI, "
            "section 10). Where text reads `[... removed]`, direct evidence was taken out.*")
LIBRARY_NOTE = ("> *Kit edition. Each entry keeps the mod's name, what the issue was, how it was fixed, what got in the way "
                "and the reasoning lesson. Direct evidence is removed by the build's stated rule (offsets, byte patterns, "
                "disassembly, record IDs, asset paths, code from other authors) and shows as `[... removed]`. Other "
                "documents' references to an entry by number predate this edition: search by heading.*")

# --- the transform -------------------------------------------------------------------------------------------------

REG = r"(?:r[abcd]x|r[sd]i|r[sb]p|r(?:8|9|1[0-5])[dwb]?|e[abcd]x|e[sd]i|xmm\d{1,2})"
MNEMONIC = r"(?:mov\w{0,3}|lea|jmp|call|cmp|push|pop|xor|addss|subss|mulss|cvttss2si|test|comiss)"
ASSET_EXT = r"(?:nif|dds|hkx|swf|gfx|pex|psc|bsa|ba2|tri|fuz|xwm|bik)"

# order matters: longest shapes first. (class, regex, placeholder)
REDACTIONS = [
    ("code-quote", re.compile(r"[^\n]*gfx\.io\.GameDelegate[^\n]*"), "[code removed]"),
    ("address-id", re.compile(r"\b\d{4,6}(?: <- \d{4,6})+\b"), "[id chain removed]"),
    ("source-reference", re.compile(r"\b[\w./-]+\.(?:ws|h|hpp|cpp|as):\d+(?:-\d+)?(?:, ?\d+-\d+)*"), "[source reference removed]"),
    ("disassembly", re.compile(r"\bVTABLE_\w+(?:\[\d+\])?"), "[vtable removed]"),
    ("disassembly", re.compile(r"\bvfunc \d+\b"), "[vfunc removed]"),
    ("module-offset", re.compile(r"\.\.\.[0-9a-f]{6,}\b"), "[offset removed]"),
    ("asset-path", re.compile(r"\b[A-Z]\w+\.as\b"), "[script name removed]"),
    ("disassembly", re.compile(MNEMONIC + r"\s+(?:(?:dword|qword|byte|word)\s+ptr\s+)?\[?" + REG + r"\b[^`\n,]*(?:,\s*[^`\s\n]+)?"), "[instruction removed]"),
    ("disassembly", re.compile(MNEMONIC + r"\s+\[[^\]\n]*\]"), "[instruction removed]"),
    ("disassembly", re.compile(r"\[(?:" + REG + r"|this|menu)\s*\+?[^\]\n]*\]"), "[operand removed]"),
    ("byte-pattern", re.compile(r"`[0-9A-F]{2}(?: [0-9A-F?]{1,2})*`"), "[bytes removed]"),
    ("byte-pattern", re.compile(r"(?<![\w#])(?:[0-9A-F]{2}|\?\??)(?: (?:[0-9A-F]{2}|\?\??)){2,}(?![\w])"), "[bytes removed]"),
    ("module-offset", re.compile(r"[\w.-]+\.(?:exe|dll)\+(?:0x)?[0-9A-Fa-f]+"), "[offset removed]"),
    ("module-offset", re.compile(r"\b\d{4,6}\+0x[0-9A-Fa-f]+"), "[offset removed]"),
    ("module-offset", re.compile(r"\+(?=[0-9A-F]*[A-F])(?=[0-9A-F]*\d)[0-9A-F]{4,8}\b"), "[offset removed]"),
    ("module-offset", re.compile(r"\bgame\+0x[0-9A-Fa-f]+"), "[offset removed]"),
    ("hex-literal", re.compile(r"[+]?\b0x[0-9A-Fa-f]+"), "[value removed]"),
    ("address-id", re.compile(r"\b(?:REL::ID|REL::RelocationID|RELOCATION_ID|RelocationID|VariantID)\s*\([^)\n]*\)"), "[id removed]"),
    ("address-id", re.compile(r"\b(?:[Ii][Dd]s?|SE|AE|VR)[ =:]+\d{4,6}\b(?!\.\d)"), "[id removed]"),
    ("record-id", re.compile(r"\.es[mpl]\s*[|~:]\s*[0-9A-Fa-f]{3,8}\b"), ".esm [id removed]"),
    ("record-id", re.compile(r"\b[Ff]orm ?[Ii][Dd]s?\s+[0-9A-Fa-f]{3,8}\b"), "form id [id removed]"),
    ("record-id", re.compile(r"(?<![#\w-])(?=[0-9A-F]*[A-F])(?=[0-9A-F]*\d)[0-9A-F]{6,8}(?![\w-])"), "[id removed]"),
    ("record-id", re.compile(r"(?<![#\w-])00\d{4,6}(?![\w-])"), "[id removed]"),
    ("asset-path", re.compile(r"(?:[\w.+'-]+[\\/]+)+[\w.+'-]+\." + ASSET_EXT + r"\b"), "[asset path removed]"),
    ("asset-path", re.compile(r"\b[\w-]+\.(?:pex|psc|nif|hkx)\b"), "[asset name removed]"),
]
INLINE_CODE_RE = re.compile(r"`([^`\n]*)`")   # left to right, so a span is always an opening and its closing back-tick
SHORT_SOURCE_RE = re.compile(r"\bif ?\(.*\)|==|\bthis\.\w+\(|;\s*$")
SOURCE_SYNTAX_RE = re.compile(r"::|->|\w\([^)\n]*\)\s*[;{]|\b(?:Function|EndFunction|Event|var|const|return|auto|template|GameDelegate)\b")
DECOMPILED_RE = re.compile(r"`[^`\n]*(?:_loc\d+_|GameDelegate\.call)[^`\n]*`")
FENCE_RE = re.compile(r"(?ms)^```(\w*)[^\n]*\n(.*?)^```[ \t]*\r?$\n?")
INDENTED_SOURCE_RE = re.compile(r"(?m)^(?:    |\t)\S[^\n]*(?:;|\{|\})[ \t]*\r?$\n?")
OWN_TOOLING_FENCES = {"powershell", "cmake", "json"}
NETWORK_IN_TEXT_RE = re.compile(r"(?i)\bcurl\b|\bwget\b|Invoke-WebRequest|Invoke-RestMethod|api\.nexusmods")
PLACEHOLDER_RE = re.compile(r"\[[a-z ]+ removed\]")

# prose, every document and script comment: no advertising. Longest first. Functional code names go through RENAME.
PROSE_SUBS = [
    (re.compile(r"\bon Discord\b"), "on a chat server"),
    (re.compile(r"\b[Aa] Discord (server|list|thread|invite)\b"), r"a chat \1"),
    (re.compile(r"\bDiscord(?!'s)\b"), "chat server"),
    (re.compile(r"\b[Aa] Patreon\b"), "a donation"),
]
RENAME = [("Patreon", "Members"), ("patreon", "members")]    # the publish channel, in scripts, schemas and documents alike
OWN_HANDLE_RE = re.compile(r"ApocryphaRealm")

COUNTS: dict = {}


def is_source_span(span: str) -> bool:
    return (len(span) >= 50 and bool(SOURCE_SYNTAX_RE.search(span))) or (len(span) >= 15 and bool(SHORT_SOURCE_RE.search(span)))


def _count(cls: str, n: int = 1) -> None:
    COUNTS[cls] = COUNTS.get(cls, 0) + n


def reduce_evidence(text: str, library: bool = False) -> str:
    """The mechanical rule. A token goes, the sentence around it stays; a line left with nothing but placeholders goes."""
    if library:
        def fence(m):
            tag, body = m.group(1).lower(), m.group(2)
            if tag in OWN_TOOLING_FENCES and not NETWORK_IN_TEXT_RE.search(body) and not _hits_evidence(body):
                return m.group(0)
            _count("code-quote (fenced block)")
            return "[code example removed; the text around it says what it showed]\n"
        text = FENCE_RE.sub(fence, text)

        def indented(m):
            _count("code-quote (indented source line)")
            return ""
        text = INDENTED_SOURCE_RE.sub(indented, text)

        def dec(m):
            _count("code-quote (inline)")
            return "[code removed]"
        text = DECOMPILED_RE.sub(dec, text)

        def inline(m):
            if is_source_span(m.group(1)):
                _count("code-quote (inline)")
                return "[code removed]"
            return m.group(0)
        text = INLINE_CODE_RE.sub(inline, text)
    for cls, rx, ph in REDACTIONS:
        text, n = rx.subn(ph, text)
        if n:
            _count(cls, n)
    out = []
    for line in text.split("\n"):
        hits = len(PLACEHOLDER_RE.findall(line))
        if hits >= 3 and not line.startswith("#"):
            rest = re.sub(r"[^A-Za-z]", "", PLACEHOLDER_RE.sub("", line))
            if len(rest) < 60:
                _count("line left with only placeholders, dropped")
                continue
        out.append(line)
    return "\n".join(out)


def _hits_evidence(text: str) -> bool:
    return any(rx.search(text) for _, rx, _ in REDACTIONS)


class Overrides:
    """kit-src\\screen\\overrides.json: { "<shipped path>": [ {"rx": regex (DOTALL, MULTILINE), "to": text} ], "*": [...] }.
    A rule that matched nothing is reported, so a stale one is seen; the scanner still catches what it was for."""

    def __init__(self, path: str):
        self.rules = {}
        self.used = set()
        for rel, rows in json.load(open(path, encoding="utf-8-sig")).items():
            if rel.startswith("_"):
                continue
            self.rules[rel] = [(i, re.compile(r["rx"], re.S | re.M), r["to"]) for i, r in enumerate(rows)]

    def apply(self, rel: str, text: str) -> str:
        for key in (rel, "*"):
            for i, rx, to in self.rules.get(key, []):
                text, n = rx.subn(lambda m: to, text)
                if n:
                    self.used.add((key, i))
        return text

    def stale(self) -> list:
        return [f"{k} rule {i}: {rx.pattern[:70]!r}" for k, rows in self.rules.items() for i, rx, _ in rows
                if (k, i) not in self.used]


def neutral_names(text: str) -> str:
    """Patreon -> the neutral channel name 'members', everywhere it is functional; no prose promotion survives it."""
    for a, b in RENAME:
        text = text.replace(a, b)
    return text


def screen_doc(rel: str, text: str, ov: Overrides) -> str:
    """One shipped document: overrides, then the prose rules, then the evidence rule."""
    library = rel == "PAST-MISTAKES-LIBRARY.md"
    text = ov.apply(rel, text)
    for rx, to in PROSE_SUBS:
        text = rx.sub(to, text)
    text = neutral_names(text)
    text = OWN_HANDLE_RE.sub("the author", text) if rel.startswith(("rules/", "skills/")) else text
    if rel not in NO_EVIDENCE_TRANSFORM:
        text = reduce_evidence(text, library=library)
    if library:
        text = re.sub(r"(?m)^# [^\n]*\n", lambda m: m.group(0) + "\n" + LIBRARY_NOTE + "\n", text, count=1)
    elif CUT_NAMES_RE.search(text):
        text = re.sub(r"(?m)^# [^\n]*\n", lambda m: m.group(0) + "\n" + KIT_NOTE + "\n", text, count=1)
    return text


# files where a hex value is our own data, not evidence: a mod's own key codes
NO_EVIDENCE_TRANSFORM = {"docs/DEFAULT-KEYS.md", "CHANGELOG.md"}

GATE_TEXT_FIELDS = ("why", "incident", "fix", "note", "amended", "exemptNote", "exemptWhy", "_about")


def screen_gate_rules(text: str, kit_has_script, ov: Overrides) -> tuple:
    """Drop the rows that advertise, that carry a private identifier or that name a script the kit does not ship (a
    missing script is a failure in package-gate); reduce the prose fields. The patterns are left alone: they are checks."""
    data = json.loads(text)
    kept, dropped_script = [], []
    for r in data["rules"]:
        if r.get("id") in DROPPED_GATE_ROWS:
            continue
        s = r.get("script")
        if s and not kit_has_script(s):
            dropped_script.append(r["id"])
            continue
        if r.get("instances"):
            r["instances"] = []     # the original's folders; README-FOR-AI section 5 says to put the person's here
        for k in GATE_TEXT_FIELDS:
            if isinstance(r.get(k), str):
                v = r[k]
                for rx, to in PROSE_SUBS:
                    v = rx.sub(to, v)
                r[k] = reduce_evidence(v)
        kept.append(r)
    data["rules"] = kept
    out = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    return neutral_names(ov.apply("scripts/gate-rules.json", out)), dropped_script


# --- the network parts of the scripts that stay ----------------------------------------------------------------------

def _must(rel: str, pattern: str, repl: str, text: str, flags: int = re.S | re.M) -> str:
    new, n = re.subn(pattern, lambda m: repl, text, flags=flags)
    if n == 0:
        raise SystemExit(f"screen: the network cut did not match in {rel}: {pattern[:80]!r} - fix kit_screen.patch_script; "
                         f"never ship the script uncut")
    return new


def patch_script(rel: str, text: str) -> str:
    name = rel.split("/")[-1]
    nl = "\r\n" if "\r\n" in text else "\n"
    if name == "version-gate.ps1":
        text = _must(rel, r"^function Get-NexusApiKey \{.*?^\}\r?\n", "", text)
        text = _must(rel, r"^function Get-NexusPublished\(.*?^\}\r?\n",
                     "function Get-NexusPublished([int]$id, [string]$domain = '') {" + nl +
                     "    # kit: this kit makes no network call, so the live page is never read and the ledger decides." + nl +
                     "    # OPTIONAL-SCRIPTS.md says what the original read here, if the person asks for it to be built." + nl +
                     "    return $null" + nl + "}" + nl, text)
        text = _must(rel, r"^        \$n = Get-NexusPublished \$NexusModId \$domain\r?\n.*?\$script:NexusOwner[^\r\n]*\r?\n",
                     "        # kit: the ID is recorded unverified - this kit does not read Nexus (OPTIONAL-SCRIPTS.md)" + nl +
                     "        $n = @{ version = '(not read)'; name = '(not read)'; status = 'unverified' }" + nl, text)
        text = _must(rel, r"^[ \t]*if \(& git -C \$repoPath remote\) \{ \$remoteTags = [^\r\n]*\r?\n",
                     "        # kit: only local tags are checked; a tag already pushed is the person's to look for" + nl, text)
        text = _must(rel, r"^        if \(-not \$auditPath\) \{.*?^        \}\r?\n", "", text)
        text = text.replace("$script:NexusOwner = 'ApocryphaRealm'", "$script:NexusOwner = ''")
    if name == "finalize-mod.ps1":
        text = _must(rel, r"\$hasOrigin = @\(git remote\) -contains 'origin'",
                     "$hasOrigin = $false   # kit: this kit pushes nothing and reads no remote; publishing the repo is the person's step", text)
        text = _must(rel, r"^    if \(\$hasOrigin\) \{\r?\n        git fetch.*?^    \}\r?\n", "", text)
        text = _must(rel, r"^    if \(\$hasOrigin\) \{\r?\n        # the remote's copy.*?^    \} else \{.*?^    \}\r?\n",
                     "    Write-Output \"  ok  clean (this kit pushes nothing: push the repo and its tag yourself)\"" + nl, text)
        text = _must(rel, r"^    if \(\$hasOrigin -and -not \$tagRemote\) \{.*?^    \}\r?\n", "", text)
        text = _must(rel, r'post with  resolve\.py run nexus-upload `"<distro folder>`"  - it records \$Version POSTED after a verified upload\.',
                     "post the zip by hand, or build the optional upload tool (OPTIONAL-SCRIPTS.md); then record it: version-gate.ps1 -Action posted -Mod $key -Version $Version -Channel nexus.",
                     text)
    if name == "pre-finalize-check.ps1":
        text = _must(rel, r"^        \$originUrl = git remote get-url origin.*?(?=^    \} finally \{ Pop-Location \}\r?\n\} else \{\r?\n    Add-Result -Rule '3' -Check 'Public GitHub remote configured')",
                     "        # kit: whether the remote is public is not asked of any server here (OPTIONAL-SCRIPTS.md)" + nl +
                     "        Add-Result -Rule '3' -Check 'Public GitHub remote configured' -Status SKIP -Detail 'This kit reads no remote: check the repository is public yourself.'" + nl,
                     text)
        text = _must(rel, r"Run git fetch --unshallow <template remote>", "Fetch the full history of the template remote", text)
    # a comment that names another author's permissions belongs to the original's own repo list
    text = re.sub(r"(?m)^[ \t]*#[^\n]*Kramer7046[^\n]*\n", "", text)
    if name.endswith((".ps1", ".py")):
        for rx, to in PROSE_SUBS:
            text = rx.sub(to, text)
        text = text.replace("discord-invite", "chat-invite")
    text = text.replace("github.com/ApocryphaRealm/", "github.com/YOUR-ACCOUNT/")
    text = text.replace("ApocryphaRealm", "YOUR-NEXUS-NAME")
    return neutral_names(text)


# --- the gate --------------------------------------------------------------------------------------------------------

CODE_EXT = {".ps1", ".py", ".sh", ".js", ".html", ".bat", ".cmd"}
DOC_EXT = {".md", ".txt"}
NETWORK_CODE = [
    ("python-http", re.compile(r"\b(?:import|from)\s+(?:urllib|requests|http\.client|httpx|aiohttp|socket|websocket|ftplib|smtplib)\b|\burllib\.(?:request|error)\b|\bwebbrowser\.open\b")),
    ("powershell-http", re.compile(r"(?i)Invoke-WebRequest|Invoke-RestMethod|\b(?:iwr|irm)\s+\S|Net\.WebClient|Net\.Http|Start-BitsTransfer|Net\.Sockets")),
    ("curl-wget", re.compile(r"(?i)\bcurl(?:\.exe)?\b|\bwget\b")),
    ("github-cli", re.compile(r"(?<![\w-])gh\s+(?:api|repo|release|auth|pr|issue|gist)\b")),
    ("git-network", re.compile(r"\bgit(?:\s+-[Cc]\s+\S+)?\s+(?:push|fetch|pull|clone|ls-remote|remote\s+update|submodule\s+update)\b")),
    ("nexus-api", re.compile(r"api\.nexusmods\.com")),
    ("url-launch", re.compile(r"(?i)Start-Process\s+['\"]?https?:")),
]
# a shipped document may describe a service; it may not hand the agent a working call, outside the one document that exists to
NETWORK_DOC = re.compile(r"(?i)api\.nexusmods\.com|\bcurl(?:\.exe)?\s+-\w|\bInvoke-(?:WebRequest|RestMethod)\s+[-$h]|\bgh\s+(?:api|repo\s+view|release)\b")
NETWORK_DOC_ALLOWED = {"OPTIONAL-SCRIPTS.md", "CHANGELOG.md"}

ADVERT_RE = re.compile(r"(?i)patreon|ko-?fi\b|buymeacoffee|paypal\.|discord\.(?:gg|com)|\bdiscord\b(?!'s)")
ADVERT_ALLOWED: set = set()

PRIVATE_RE = re.compile(r"(?i)9800X3D|7900 ?XT|990 PRO|MS-7D75|SanDisk|\bRyzen\b|\bRadeon\b|17:30|Thu-Sun|waking day|"
                        r"\bblackout\b|\bTNG\b|Max subscription|bed 8 a\.m\.|\bhe wakes\b|3200x1800|RTX \d{4}")
SKIP_ALWAYS = {"LICENSE-GPL-3.0.txt", "CC-BY-SA-4.0.txt", "MANIFEST.json"}
# the evidence rule applies to documents and gate prose. Code legitimately holds hex (a plugin's record flags), so code
# is held to the classes that cannot be innocent there.
CODE_EVIDENCE = {"byte-pattern"}
EVIDENCE_EXEMPT = {"docs/DEFAULT-KEYS.md", "CHANGELOG.md", "example/expected-selftest-output.txt"}


def strip_comment_lines(text: str) -> str:
    return "\n".join(l for l in text.split("\n") if not l.lstrip().startswith("#"))


def screen_text(rel: str, text: str) -> list:
    """Every failure for one shipped file: (class, line number, what)."""
    out = []
    base = os.path.basename(rel)
    ext = os.path.splitext(base)[1].lower()
    is_hook = rel.startswith("scripts/git-hooks/")

    def hit(cls, m, t):
        out.append((cls, t.count("\n", 0, m.start()) + 1, m.group(0)[:70].replace("\n", " ")))

    if ext in CODE_EXT or is_hook:
        # whole-line comments may talk about a service; the code may not reach one. Line numbers stay right.
        t = "\n".join("" if l.lstrip().startswith("#") else l for l in text.split("\n"))
        for cls, rx in NETWORK_CODE:
            for m in rx.finditer(t):
                hit("network:" + cls, m, t)
    elif ext in DOC_EXT and rel not in NETWORK_DOC_ALLOWED:
        for m in NETWORK_DOC.finditer(text):
            hit("network-in-doc", m, text)

    if rel not in ADVERT_ALLOWED:
        for m in ADVERT_RE.finditer(text):
            hit("advert", m, text)
    for m in PRIVATE_RE.finditer(text):
        hit("private", m, text)

    if rel in EVIDENCE_EXEMPT:
        return out
    if rel == "scripts/gate-rules.json":
        d = json.loads(text)
        for r in d.get("rules", []):
            for k in GATE_TEXT_FIELDS:
                if isinstance(r.get(k), str):
                    for cls, rx, _ in REDACTIONS:
                        m = rx.search(r[k])
                        if m:
                            out.append(("evidence:" + cls, 0, f"{r.get('id')}.{k}: {m.group(0)[:50]}"))
        return out
    if ext in DOC_EXT:
        for cls, rx, _ in REDACTIONS:
            for m in rx.finditer(text):
                hit("evidence:" + cls, m, text)
    elif ext != ".json" or "signature" in base:
        for cls, rx, _ in REDACTIONS:
            if cls in CODE_EVIDENCE:
                for m in rx.finditer(text):
                    hit("evidence:" + cls, m, text)
    if rel == "PAST-MISTAKES-LIBRARY.md":
        for m in FENCE_RE.finditer(text):
            if m.group(1).lower() not in OWN_TOOLING_FENCES:
                hit("evidence:code-quote", m, text)
        for m in INLINE_CODE_RE.finditer(text):
            if is_source_span(m.group(1)):
                hit("evidence:code-quote", m, text)
    return out


def screen_tree(root: str) -> list:
    """The stage: every shipped text file, every class. A cut file that came back fails too."""
    failures = []
    for rel in CUT_SCRIPTS:
        if os.path.exists(os.path.join(root, "scripts", rel)):
            failures.append(("cut-file-is-back", "scripts/" + rel, 0, ""))
    for rel in CUT_DATA:
        if os.path.exists(os.path.join(root, "scripts", rel)):
            failures.append(("cut-file-is-back", "scripts/" + rel, 0, ""))
    for rel in CUT_SKILL_FILES:
        if os.path.exists(os.path.join(root, "skills", rel)):
            failures.append(("cut-file-is-back", "skills/" + rel, 0, ""))
    for d, _, files in os.walk(root):
        if "__pycache__" in d:
            continue
        for fn in files:
            p = os.path.join(d, fn)
            rel = os.path.relpath(p, root).replace("\\", "/")
            if fn in SKIP_ALWAYS:
                continue
            try:
                with open(p, encoding="utf-8-sig", newline="") as f:
                    text = f.read()
            except UnicodeDecodeError:
                continue    # a binary carries no text to scan; only images ship
            for cls, line, what in screen_text(rel, text):
                failures.append((cls, rel, line, what))
    return failures


def selftest() -> list:
    """Proof the scanner bites: one seeded sample per class must fail; a clean sample must not."""
    seeded = [
        ("network:python-http", "scripts/a.py", "import urllib.request\n"),
        ("network:powershell-http", "scripts/a.ps1", "Invoke-WebRequest $u\n"),
        ("network:curl-wget", "scripts/a.ps1", "& curl.exe -s $u\n"),
        ("network:github-cli", "scripts/a.ps1", "gh repo view $x\n"),
        ("network:git-network", "scripts/a.ps1", "git push -q\n"),
        ("network:nexus-api", "scripts/a.py", 'U = "https://api.nexusmods.com/v3"\n'),
        ("network-in-doc", "docs/a.md", "run curl -s https://example.invalid\n"),
        ("advert", "docs/a.md", "support me on Patreon\n"),
        ("private", "docs/a.md", "his shift 17:30\n"),
        ("evidence:byte-pattern", "docs/a.md", "the site 48 8B 01 FF 50 18\n"),
        ("evidence:disassembly", "docs/a.md", "the crash at mov ecx, foo\n"),
        ("evidence:module-offset", "docs/a.md", "at SkyrimSE.exe+05F47CB\n"),
        ("evidence:hex-literal", "docs/a.md", "offset 0x158\n"),
        ("evidence:record-id", "docs/a.md", "the form 00012EB7 here\n"),
        ("evidence:address-id", "docs/a.md", "REL::ID(12345)\n"),
        ("evidence:asset-path", "docs/a.md", "shipped meshes\\armor\\x.nif\n"),
        ("evidence:code-quote", "PAST-MISTAKES-LIBRARY.md", "```cpp\nint x;\n```\n"),
        ("evidence:address-id", "docs/a.md", "the stack 80949 <- 81006\n"),
        ("evidence:source-reference", "docs/a.md", "see baseAction.ws:273\n"),
    ]
    bad = []
    for cls, rel, text in seeded:
        if not any(c == cls for c, _, _ in screen_text(rel, text)):
            bad.append(f"screen self-test: {cls} did not fire on {text.strip()!r}")
    clean = "A hook crashed because the plugin loaded first. The fix was to wait for data loaded (2026-10-01).\n"
    if screen_text("docs/a.md", clean):
        bad.append(f"screen self-test: a clean sentence failed: {screen_text('docs/a.md', clean)}")
    reduced = reduce_evidence("at SkyrimSE.exe+05F47CB the call `mov ecx,[rax+0x108]` crashed; byte 48 8B 01 FF\n")
    if screen_text("docs/a.md", reduced):
        bad.append(f"screen self-test: the transform leaves evidence: {reduced!r}")
    return bad
