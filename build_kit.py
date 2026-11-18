#!/usr/bin/env python3
"""build_kit.py - build the Pipeline Kit from the LIVE pipeline documents and scripts.

The kit is a BUILD, not a fork (4. plans\\pipeline-kit\\PLAN.md, section 5): every time the rules, the logic
library or a gate script changes, this script regenerates dist\\ from the live files, sanitising as it goes. Nothing
under dist\\ is edited by hand.

    python build_kit.py                      # build into dist\\ from the tree this repo sits in (or PIPELINE_ROOT)
    python build_kit.py --source <root>      # another live root
    python build_kit.py --check              # build, then only report the leak scan and the screen (no dist write)
    python build_kit.py --check --out <dir>  # the same, into a scratch folder that is kept
    python build_kit.py --screen [<dir>]     # only the screening stage, over a built kit

WHAT IT DOES
  1. copies the governing documents (entry file, digest, preflight, banned words, the seven rule parts, the logic
     library, commands, the reasoning-mode documents, the pipeline reference) into dist\\, sanitised;
  2. copies the gate scripts and their data shapes (gate-rules.json in full; EMPTY ledgers), rewriting every
     machine-specific default (the project root, the MO2 instance list, the Nexus key file) to an environment
     variable or a path derived from where the script sits;
  3. adds the kit's own hand-written files from kit-src\\ (member README, the recipe README-FOR-AI.md, the install
     and self-test scripts, the example mod, the licences, pipeline.config.json);
  3b. screens for publication (kit_screen.py): network tools cut, network parts removed, documents reduced to the mod's
     name, the issue, the fix and the lesson; a --screen stage FAILS the build on a network call or evidence;
  4. scans everything written for the owner's private identifiers and FAILS the build if any survive - the kit's
     own gate, and the same class of check the package gate runs (gate rule kit-ships-no-machine-identity).
     The identifiers are read from a private, untracked config (role identity-patterns); without it the build
     refuses to run - this file names nobody (1.0.6).

LAYOUT (since the live pipeline's 2026-10-09 restructure): dist\\ mirrors <ROOT>\\.MD - the scripts sit in their kind
folders (scripts\\gates, scripts\\release, scripts\\ops, scripts\\plugins) and the role resolver sits beside them
(resolvers\\resolve.py + rosters\\), because the live scripts find each other through '..\\..\\resolvers\\resolve.py'.
The old flat paths under .MD\\scripts are RETIRED-PATH stubs that call the owner's absolute path; the build reads
the real file and fails on any stub (it also fails on a 3-line "moved" pointer document). The rosters are filtered
(build_rosters): a role ships only when what it names ships (or kit-install creates it); identity values become
placeholders the person fills in; the memory folder's Claude Code project name is filled in by kit-install.

Licences: scripts GPL-3.0-or-later; prose CC BY-SA 4.0 (see dist\\README.md).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

import kit_screen

__version__ = "1.1.0"

HERE = os.path.dirname(os.path.abspath(__file__))
KIT_SRC = os.path.join(HERE, "kit-src")
DIST = os.path.join(HERE, "dist")

# --- what is copied ---------------------------------------------------------------------------------------------

# governing documents: (live path relative to .MD, kit path relative to dist)
DOCS = [
    ("RULES-DIGEST.md", "RULES-DIGEST.md"),
    ("PREFLIGHT.md", "PREFLIGHT.md"),
    # 2026-10-09: the library of past mistakes was renamed; LOGIC-LIBRARY.md is now the short catalogue of logics
    ("PAST-MISTAKES-LIBRARY.md", "PAST-MISTAKES-LIBRARY.md"),
    ("LOGIC-LIBRARY.md", "LOGIC-LIBRARY.md"),
    ("commands.md", "commands.md"),
    ("sub-agent-routing.md", "sub-agent-routing.md"),
    ("rules/01-pipeline-topology.md", "rules/01-pipeline-topology.md"),
    ("rules/02-build-toolchain.md", "rules/02-build-toolchain.md"),
    ("rules/03-versioning-and-release.md", "rules/03-versioning-and-release.md"),
    ("rules/04-code-standards.md", "rules/04-code-standards.md"),
    ("rules/05-testing-and-mo2.md", "rules/05-testing-and-mo2.md"),
    ("rules/06-reasoning-discipline.md", "rules/06-reasoning-discipline.md"),
    ("rules/07-operations-and-machine-health.md", "rules/07-operations-and-machine-health.md"),
    # FALSIFICATION-MODE, ADVERSARIAL-MODE, TESTING-PROTOCOL and SMF-CONVERSION-PLAYBOOK moved into their skills'
    # references\ folders on 2026-10-09 and ship there, with skills\ (the .MD copies are pointers, never shipped)
    ("TRIAGE-CATEGORIES.md", "docs/TRIAGE-CATEGORIES.md"),
    ("DEFAULT-KEYS.md", "docs/DEFAULT-KEYS.md"),
    ("docs-archive/VERSION-RECONCILIATION.md", "docs/VERSION-RECONCILIATION.md"),
    ("docs-archive/PIPELINE-RESEARCH.md", "docs-archive/PIPELINE-RESEARCH.md"),
    ("docs-archive/AI-PIPELINE-REFERENCE.md", "docs/AI-PIPELINE-REFERENCE.md"),
    # 1.0.2: how a checking agent judges an archived session's digest (the archive sweep, README-FOR-AI 8b)
    ("logs/archive-sweep/INSTRUCTIONS.md", "docs/ARCHIVE-SWEEP-INSTRUCTIONS.md"),
]

# the gate scripts and their helpers: the REAL file's path relative to live .MD\scripts, which is also its path under
# dist\scripts (the kind folders are kept - the scripts find each other through the resolver of their own tree).
# Since 2026-10-09 the flat .MD\scripts\<name> of a moved script is a RETIRED-PATH stub; the build refuses one.
# Where a role exists, `resolve.py find <role>` names the real file.
SCRIPTS = [
    "gates/version-gate.ps1", "gates/package-gate.ps1", "release/pre-finalize-check.ps1",
    "release/sync-nexus-distro.ps1", "release/nexus-distro-sweep.ps1", "prune-test-builds.ps1",
    "release/changelog.ps1", "gate-ledger.ps1", "gate-sweep.ps1", "pipeline-log.ps1", "falsification-log.ps1",
    "rules-version.ps1", "docs-pipeline.ps1", "ops/prockill.ps1", "rules-digest.py", "logic-index.py",
    "plugins/esp-audit.py", "gates/swf-colour-gate.py", "check-export-parity.py", "translation-coverage.py",
    "install-test-build.py", "plugins/make-fomod.py", "plugins/make-espfe.py",
    # 1.0.1: distro-names.ps1 (package-gate and prune-test-builds dot-source it since 2026-09-29 - 1.0.0 shipped
    # without it), the one-command finalize, and the Nexus posting tools of 2026-09-30
    "distro-names.ps1", "release/finalize-mod.ps1", "ops/attention-ping.ps1",
    # 1.0.1: the helper scripts gate-rules.json rows name ("script" kind) - a row whose script is missing fails the gate
    "gates/cpp-escape-gate.py", "gates/main-thread-task-gate.py", "gates/xinput-import-gate.py",
    # 1.0.2: the licence-label gate (gate row dll-licence-label-matches-repo-licence names it), the skill scout and the
    # archive sweep's digest maker (2026-10-08)
    "gates/licence-label-gate.py", "skill-scout.py", "ops/session-digest.py",
    # 2026-10-10: package-gate now looks up fomod-destinations (role) at start, make-fomod imports package_paths; the
    # memory index (session-start.py runs its --check), the gate-rules index and the stale-path finder the docs name
    "plugins/fomod-destinations.py", "package_paths.py", "memory-index.py", "gate-rules-index.py",
    "find-stale-paths.py",
    # 1.0.4: version-gate resolves role test-build-pick (the newest-build chooser) since the 2026-10 rewrite
    "release/test-build-pick.ps1", "release/post-release-prune.ps1",
    # 1.0.4: gate rows added since 1.0.3 name these three scripts
    "gates/banner-highlight-gate.py", "gates/theme-outline-gate.py", "gates/translation-script-gate.py",
    # 1.1.0: the render work pipeline (README-FOR-AI section 7e) - the package re-render before posting and its gate,
    # the model-mod package gates (their gate-rules rows ship with them), the NIF tools, the engraving gates, the
    # feature-banner maker; and the render tools promoted into .MD\scripts\render from the Truly Nordic repos
    "release/package-render.py", "release/package_render_blender.py", "release/package_render_uv.py",
    "gates/package-render-gate.py", "gates/nif-uv-overlap-gate.py", "gates/fomod-option-image-gate.py", "gates/esp-obnd-gate.py",
    "plugins/Inspect-NifShapes.py", "plugins/Repath-NifTextures.py",
    "gates/pattern-gate.py", "gates/engraving-layout-gate.py", "gates/surface-profile-gate.py",
    "art/make-feature-banners.py",
    "render/niflib.py", "render/winding.py", "render/nif-readback.py", "render/render_lib.py", "render/before-after-sheet.py",
]
# 1.1.0: folders that ship WHOLE (every .py in them, __pycache__ left out), so a module added to one is never missed;
# an empty or missing folder stops the build like a missing listed script
SCRIPT_FOLDERS = ["art/patternlib"]


def all_scripts(md: str) -> list:
    """SCRIPTS plus every .py of every SCRIPT_FOLDERS folder (paths under .MD\\scripts, forward slashes)."""
    out = list(SCRIPTS)
    for folder in SCRIPT_FOLDERS:
        d = os.path.join(md, "scripts", folder)
        found = sorted(f for f in os.listdir(d) if f.endswith(".py")) if os.path.isdir(d) else []
        if not found:
            raise SystemExit(f"script folder missing or empty in the live tree: scripts/{folder}")
        out += [folder + "/" + f for f in found if folder + "/" + f not in out]
    return out
# the role resolver (rule 70): .MD\resolvers -> dist\resolvers. render-preamble.py (the owner's sub-agent preamble,
# test-instance-specific), render-hooks.py (the owner's settings.json guard hooks) and tests\ (fixtures of the owner's
# tree) stay out; INDEX.md is generated on the person's machine by kit-install (resolve.py index --build).
RESOLVER_FILES = ["resolve.py", "resolve.ps1", "session-start.py",
                  "schema/gate-rules.json", "schema/roster.json", "schema/version-ledger.json",
                  "schema/version-registry.json"]
# rosters that never ship: every role in them is the owner's own (MO2 instances; the test instance's one-off scripts
# roster is added from the private identity config, kitPaths.instanceRoster)
ROSTERS_DROPPED = {"games.json"}
# files kit-install creates (paths under <ROOT>); a role naming one of them ships although dist does not carry it
INSTALL_CREATES = {".MD/PROGRESS.md", ".MD/docs-archive", "2. Mod Types/to-do list/to-do-list.md", ".MD/logs",
                   # the stage folders (kit-install.ps1 $STAGES; the owner's extra folders - quarantine, playerbot sources - are not)
                   "1. mod sorter", "2. Mod Types", "3. analyze mods", "4. plans", "5. current project mod", "6. current wip mods",
                   "7. current test builds", "8. confirm compatibility", "9. patches output", "10. finalized mods", "11. Nexus distro",
                   "12. needs an update", "13. testbench"}
# a role note that names the owner's machine or people is dropped (the role itself ships)
# (the owner's MO2 instance names are added from the private identity config - ownerNotePattern)
OWNER_NOTE_RE = re.compile(r"(?i)onedrive|this pc|owner|memory [a-z-]+-[a-z-]+|step \d|phase \d|[A-Z]:\\")
DATA_FULL = ["gate-rules.json"]
DATA_EMPTY = {"version-registry.json": "{}\n", "version-ledger.json": "[]\n", "gate-ledger.json": "[]\n",
              "falsification-log.json": "[]\n",
              # the pre-release archive version-gate reads (role version-ledger-prerelease) starts empty too
              "version-ledger-prerelease.json": "[]\n",
              # 1.0.2: the skill scout's decided non-candidates start empty - the person's decisions, not the owner's
              "skill-scout-ignore.txt": "# skill-scout-ignore.txt - candidates judged NOT skill-worthy, so skill-scout.py never flags them again.\n"
                                        "# One per line: a script name, a doc path relative to <ROOT> (or \"a.ps1 + b.py\" for a chain), then  # why, date.\n"}

# 1.0.2: the Claude Code skills (.MD\skills\<name>\, junctioned into ~\.claude\skills by the person - README-FOR-AI 7c)
SKILLS_DIR = "skills"
# 1.1.0: skills that stay out whole. norse-ue4ss is the owner's route through his own NORSE (UE 5.6) repos - another game,
# its paths and plans are his, and it was still being written in another session when 1.1.0 was built
SKILLS_LEFT_OUT = {"norse-ue4ss"}

# templates from 11. Nexus distro and a finished package's document set
TEMPLATES = [
    ("11. Nexus distro/_nexus-page-template.txt", "templates/nexus-page-template.txt"),
    ("11. Nexus distro/_BANNER-DESIGN-RULES.md", "templates/banner-design-rules.md"),
    ("11. Nexus distro/_banner-template-1920x1080.html", "templates/banner-template-1920x1080.html"),
    ("11. Nexus distro/_banner-template-1300x372.html", "templates/banner-template-1300x372.html"),
    ("6. current wip mods/MO2KeywordTagger/README.txt", "templates/package-docs/README.txt"),
    ("6. current wip mods/MO2KeywordTagger/NOTICE.md", "templates/package-docs/NOTICE.md"),
    ("6. current wip mods/MO2KeywordTagger/THIRD_PARTY_NOTICES.md", "templates/package-docs/THIRD_PARTY_NOTICES.md"),
    # an EXAMPLE of a mod's changelog, so not named CHANGELOG.md: the package gate's shipped-changelog-is-the-repos
    # rule (rightly) takes any CHANGELOG.md in a package for the package's own (1.0.1)
    ("6. current wip mods/MO2KeywordTagger/CHANGELOG.md", "templates/package-docs/CHANGELOG-example.md"),
]

# --- sanitising --------------------------------------------------------------------------------------------------

# The owner's identity strings (name, email, account, home and project paths, MO2 drive paths, donation and invite
# links) are NOT written in this file (1.0.6, 2026-10-22): the repository that removes them must not carry them. They
# live in a private, untracked config - role identity-patterns, <ROOT>\.MD\private\identity-patterns.json - that
# load_identity() reads at start; the build refuses to run without it (fail closed). Keys used here:
#   kitSubstitutions  [[regex, replacement], ...] applied in order by sanitise()
#   identity, kitLeak [{"id", "pattern"}, ...] - every pattern is a leak the build fails on
#   ownerNotePattern  extra words that mark a roster note as the owner's own (dropped from the kit)
TEXT_SUBS: list = []
LEAK_PATTERNS: list = []
# generic leak patterns that name no person: an API key line, a retired-path stub
GENERIC_LEAK_RE = re.compile(r"apikey: [A-Za-z0-9+/=]{20,}|RETIRED PATH \(stub, expires \d")


# path tokens used in rewrite_script()'s patterns; load_identity() fills them from kitPaths (regex-escaped)
PATH_TOKENS: dict = {}


def expand_tokens(pattern: str) -> str:
    for k, v in PATH_TOKENS.items():
        pattern = pattern.replace("{" + k + "}", v)
    return pattern


def identity_config_path(src: str) -> str:
    """Where the private identity config is: --identity-config / PIPELINE_IDENTITY_CONFIG, else role identity-patterns
    asked of the source's resolver, else <src>/.MD/private/identity-patterns.json."""
    env = os.environ.get("PIPELINE_IDENTITY_CONFIG")
    if env:
        return env
    resolver = os.path.join(src, ".MD", "resolvers", "resolve.py")
    if os.path.isfile(resolver):
        r = subprocess.run([sys.executable, resolver, "find", "identity-patterns"], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip().splitlines()[0]
    return os.path.join(src, ".MD", "private", "identity-patterns.json")


def load_identity(path: str, src: str = "") -> str | None:
    """Fill TEXT_SUBS, LEAK_PATTERNS and OWNER_NOTE_RE from the private config. Returns an error text, or None."""
    global OWNER_NOTE_RE
    if not os.path.isfile(path):
        return f"the private identity config is missing: {path} (role identity-patterns) - the build refuses to run without it"
    try:
        cfg = json.load(open(path, encoding="utf-8-sig"))
        subs = [(re.compile(rx), rep) for rx, rep in cfg["kitSubstitutions"]]
        leaks = [(e["id"], re.compile(e["pattern"])) for e in cfg.get("identity", []) + cfg.get("kitLeak", [])]
    except (OSError, ValueError, KeyError, TypeError, re.error) as e:
        return f"the private identity config {path} does not load: {e}"
    if not subs or not leaks:
        return f"the private identity config {path} has no kitSubstitutions or no identity/kitLeak patterns"
    TEXT_SUBS[:] = subs
    LEAK_PATTERNS[:] = leaks
    kp = cfg.get("kitPaths") or {}
    missing = [k for k in ("mo2Root", "testInstance", "testProfile", "instanceRoster") if not kp.get(k)]
    if missing:
        return f"the private identity config {path} lacks kitPaths keys: {', '.join(missing)}"
    root = kp.get("root") or src
    PATH_TOKENS.update({
        "ROOT": re.escape(root).replace("\\ ", " "),
        "ROOT_DOUBLED": re.escape(root.replace("\\", "\\\\")).replace("\\ ", " "),
        "ROOT_NAME": re.escape(os.path.basename(root)).replace("\\ ", " "),
        "PROJECT_FOLDER": re.escape(re.sub(r"[^A-Za-z0-9]", "-", root)),
        "MO2": "(?i:" + re.escape(kp["mo2Root"]) + ")",
        "INSTANCE": re.escape(kp["testInstance"]),
        "TEST_PROFILE": re.escape(kp["testProfile"]).replace("\\ ", " "),
        "INSTANCE_ROSTER": re.escape(os.path.splitext(kp["instanceRoster"])[0]),
    })
    ROSTERS_DROPPED.add(kp["instanceRoster"])
    extra = cfg.get("ownerNotePattern")
    if extra:
        OWNER_NOTE_RE = re.compile(r"(?i)(?:" + extra + r")|" + OWNER_NOTE_RE.pattern.replace("(?i)", "", 1))
    return None


TEXT_EXT = {".md", ".txt", ".ps1", ".py", ".json", ".html", ".sh", ""}

# a governing document that moved leaves a short pointer at its old path ("# X.md - moved into ...") - never shipped
POINTER_RE = re.compile(r"^﻿?# \S+\.md - moved\b")


def sanitise(text: str) -> str:
    for rx, rep in TEXT_SUBS:
        text = rx.sub(rep, text)
    # an interior U+FEFF trips the package gate's no-byte-order-mark rule; the live gate-rules.json BOM patterns and
    # the library's prose about them carry it literally (2026-10-10) - ship it as the ﻿ escape, which reads the
    # same in a JSON string and in prose (only the md and json files carry one)
    return text.replace("﻿", "\\ufeff")


def py_dir_expr(rel: str, up: int) -> str:
    """A Python expression for the folder `up` levels above the script at scripts/<rel> (up=1: its own folder)."""
    return "os.path.dirname(" * up + "os.path.abspath(__file__)" + ")" * up


def py_md_expr(rel: str) -> str:
    """<ROOT>\\.MD for a script at .MD\\scripts\\<rel> (rel may carry kind folders: gates/x.py is one deeper)."""
    return py_dir_expr(rel, rel.count("/") + 2)


def py_root_expr(rel: str) -> str:
    return 'os.environ.get("PIPELINE_ROOT") or ' + py_dir_expr(rel, rel.count("/") + 3)


# PowerShell: <ROOT> is the parent of the .MD folder this script sits under, at any depth (scripts\, scripts\gates\ ...)
PS_ROOT_FROM_HERE = ("$PSScriptRoot; while ($_kitRoot -and (Split-Path $_kitRoot -Leaf) -ne '.MD') { $_kitRoot = Split-Path $_kitRoot -Parent }; "
                     "if ($_kitRoot) { $_kitRoot = Split-Path $_kitRoot -Parent }")


def rewrite_script(rel: str, text: str) -> str:
    """Machine-specific defaults -> environment or derived paths. Each rewrite asserts it matched, so a live script
    that changes shape fails the build here instead of shipping with a private path. `rel` is the path under
    .MD\\scripts (gates/version-gate.ps1), so a derived path knows how deep the script sits."""
    name = rel.split("/")[-1]

    def must(pattern, repl, s, flags=0, count=0):
        literal = repl
        pattern = expand_tokens(pattern)
        new, n = re.subn(pattern, lambda m: literal, s, count=count, flags=flags)   # literal: backslashes stay
        if n == 0:
            raise SystemExit(f"rewrite did not match in {rel}: {pattern!r}")
        return new

    nl = "\r\n" if "\r\n" in text else "\n"
    if name.endswith(".ps1") and name not in ("distro-names.ps1", "test-build-pick.ps1"):   # distro-names: function defaults, its own rule below
        m = re.search(expand_tokens(r"\[string\]\$(Root|ProjectRoot)\s*=\s*['\"]{ROOT}['\"]"), text)
        if m:
            var = m.group(1)
            # the default becomes the environment variable (may be empty); the derived path is resolved in the
            # body, because $PSScriptRoot is not populated inside a [CmdletBinding()] param block's defaults
            text = re.sub(expand_tokens(r"(\[string\]\$(?:Root|ProjectRoot)\s*=\s*)['\"]{ROOT}['\"]"),
                          lambda mm: mm.group(1) + "$env:PIPELINE_ROOT", text)
            resolve = ("if (-not $" + var + ") { $_kitRoot = " + PS_ROOT_FROM_HERE + "; $" + var + " = $_kitRoot }"
                       "   # kit: <ROOT> is the folder above the .MD this script sits under, unless PIPELINE_ROOT says otherwise" + nl)
            anchor = re.search(r"(?m)^\$ErrorActionPreference\s*=.*\r?\n", text)
            if anchor:
                text = text[:anchor.end()] + resolve + text[anchor.end():]
            else:
                pm = re.search(r"(?m)^param\(.*\)\s*\r?\n", text)   # a one-line param(...) (gate-sweep)
                if not pm:
                    pm = re.search(r"(?ms)^param\(.*?^\)\s*\r?\n", text)   # a multi-line param block without $ErrorActionPreference
                if not pm:
                    raise SystemExit("no place to resolve $" + var + " in " + rel)
                text = text[:pm.end()] + resolve + text[pm.end():]
    if name == "pre-finalize-check.ps1":
        # since 2026-10-25 the list sits inside Get-Rule29Instances, indented
        text = must(r"(?m)^    \$instances = @\(\r?\n.*?^    \)\r?\n",
                    "    # kit: the MO2 instances to check are PIPELINE_MO2_INSTANCES, a ;-separated list of <instance>\\mods folders" + nl +
                    "    $instances = @(); foreach ($p in @(($env:PIPELINE_MO2_INSTANCES -split ';') | Where-Object { $_ })) { $instances += @{ Name = (Split-Path (Split-Path $p -Parent) -Leaf); Path = $p } }" + nl,
                    text, flags=re.S, count=1)
    if name == "prune-test-builds.ps1":
        text = must(r"\[string\[\]\]\$Instances = @\([^)]*\)",
                    "[string[]]$Instances = @(($env:PIPELINE_MO2_INSTANCES -split ';') | Where-Object { $_ } | ForEach-Object { Split-Path $_ -Parent })",
                    text, flags=re.S, count=1)
    if name == "distro-names.ps1":
        # every function's ProjectRoot default: PIPELINE_ROOT, else two folders above this file (<ROOT>\.MD\scripts)
        text = must(r"'{ROOT}'",
                    "$(if ($env:PIPELINE_ROOT) { $env:PIPELINE_ROOT } else { Split-Path (Split-Path $PSScriptRoot -Parent) -Parent })",
                    text)
    if name == "test-build-pick.ps1":
        # 1.0.4: function defaults, like distro-names.ps1; this file sits in scripts\release, so <ROOT> is three folders up
        text = must(r"'{ROOT}'",
                    "$(if ($env:PIPELINE_ROOT) { $env:PIPELINE_ROOT } else { Split-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) -Parent })",
                    text)
    if name == "docs-pipeline.ps1":
        # the governed list's absolute entries are the owner's plan files and memory vocabulary - not the person's
        text = must(r"(?m)^[ \t]*\(Join-Path \$env:USERPROFILE '\.claude\\projects\\{PROJECT_FOLDER}\\memory\\topics-vocabulary\.txt'\)[ \t]*\r?\n", "", text)
        text = must(r"(?m)^[ \t]*'{ROOT}\\4\. plans\\pipeline-restructure\\[^']+'[ \t]*\r?\n", "", text)
        text = must(r"(?m)^[ \t]*'resolvers\\rosters\\(?:{INSTANCE_ROSTER}|games)\.json'.*\r?\n", "", text)   # rosters the kit drops
    if name == "skill-scout.py":
        # <ROOT> from PIPELINE_ROOT, else derived from where this file sits; the transcripts of EVERY Claude Code
        # project, since the person's project folder names are not the owner's
        text = must(r'ROOT = r"{ROOT}"', "ROOT = " + py_root_expr(rel) + "  # kit", text, count=1)
        text = must(r'PROJECTS = \[os\.path\.expanduser\(r"~\\\.claude\\projects\\[A-Z]--WINDOWS-system32"\),\s*\n\s*'
                    r'os\.path\.expanduser\(r"~\\\.claude\\projects\\{PROJECT_FOLDER}"\)\]',
                    '_PROJECTS_ROOT = os.path.expanduser(os.path.join("~", ".claude", "projects"))' + nl +
                    'PROJECTS = [os.path.join(_PROJECTS_ROOT, d) for d in (os.listdir(_PROJECTS_ROOT) if os.path.isdir(_PROJECTS_ROOT) else [])]  # kit: every project',
                    text, count=1)
    if name == "session-digest.py":
        text = must(r'OUT = os\.path\.join\(r"{ROOT}\\\.MD\\logs", "session-digests"\)',
                    'OUT = os.path.join(' + py_md_expr(rel) + ', "logs", "session-digests")  # kit: <ROOT>\\.MD\\logs',
                    text, count=1)
    if name == "translation-coverage.py":
        text = must(r'ROOT = r"{ROOT}\\6\. current wip mods"',
                    'ROOT = os.path.join(' + py_root_expr(rel) + ', "6. current wip mods")  # kit: <ROOT>\\6. current wip mods',
                    text, count=1)
    if name == "check-export-parity.py":
        text = must(r'DEFAULT_SMF = r"{ROOT}\\(2\. Mod Types)\\(Framework or Utility)\\([^\\"]+)\\([^\\"]+)"',
                    'DEFAULT_SMF = os.path.join(' + py_root_expr(rel) + ', "2. Mod Types", "Framework or Utility", '
                    '"SKSE Menu Framework (reference copy)", "SKSEMenuFramework.dll")  # kit: under <ROOT>',
                    text, count=1)
    if name == "memory-index.py":
        # Claude Code names a project's folder after its start directory, every character outside [A-Za-z0-9] a '-'
        text = must(r'DEFAULT_DIR = os\.path\.join\(os\.environ\.get\("USERPROFILE", ""\), "\.claude", "projects", "{PROJECT_FOLDER}", "memory"\)',
                    'DEFAULT_DIR = os.path.join(os.environ.get("USERPROFILE", ""), ".claude", "projects", '
                    're.sub(r"[^A-Za-z0-9]", "-", ' + py_root_expr(rel) + '), "memory")  # kit: the Claude Code project of <ROOT>',
                    text, count=1)
        text = must(r"""'`py -3 "{ROOT_DOUBLED}\\\\\.MD\\\\scripts\\\\memory-index\.py" --build`\.'""",
                    """'`py -3 "<ROOT>\\\\.MD\\\\scripts\\\\memory-index.py" --build`.'""", text, count=1)
    if name == "find-stale-paths.py":
        text = must(r'ROOT = r"{ROOT}"', "ROOT = " + py_root_expr(rel) + "  # kit", text, count=1)
        # the documents name paths under the root's own folder name, not the owner's
        text = must(r're\.compile\(r"{ROOT_NAME}\\\\\(', 're.compile(re.escape(os.path.basename(ROOT)) + r"\\\\(', text, count=1)
    if name == "xinput-import-gate.py":
        text = must(r'NJ = r"{MO2}\\{INSTANCE}"',
                    'NJ = os.path.dirname(((os.environ.get("PIPELINE_MO2_INSTANCES") or "").split(";")[0]).rstrip("\\\\/"))  # kit: the first MO2 instance',
                    text, count=1)
    if name == "install-test-build.py":
        text = must(r'else r"{MO2}\\{INSTANCE}\\mods"',
                    'else ((os.environ.get("PIPELINE_MO2_INSTANCES") or "").split(";")[0] or sys.exit("set PIPELINE_MO2_INSTANCES or pass --mods-dir"))  # kit',
                    text, count=1)
        text = must(r'aside = os\.path\.join\(r"{MO2}\\{INSTANCE}\\_removed-20260921", "locked-dlls"\) if "--mods-dir" not in sys\.argv \\\r?\n\s*else ',
                    'aside = ', text, count=1)
        text = must(r'else "{TEST_PROFILE}"', 'else "Default"  # kit: the MO2 default profile name', text, count=1)
    # 1.1.0, the render work pipeline: the programs come from the person's machine (BLENDER / TEXCONV, then PATH); the
    # docstrings that name the original's design workspace (4. plans, set2) or its upload tool say what the kit has
    if name == "package-render.py":
        # role blender is the owner's install path and is dropped from the kit's rosters (an absolute path outside <ROOT>)
        text = must(r'    for c in \(r"C:\\Program Files\\Blender Foundation\\Blender [\d.]+\\blender\.exe",\):\r?\n        if os\.path\.isfile\(c\): return c\r?\n',
                    '    c = os.environ.get("BLENDER") or shutil.which("blender")   # kit: BLENDER, then blender on PATH' + nl +
                    '    if c and os.path.isfile(c): return c' + nl, text, count=1)
        text = must(r'Blender not found \(role blender\)', 'Blender not found (set BLENDER, or put blender on PATH)', text, count=1)
        text = must(r'nexus-upload\.py runs the gate\.', 'the upload step runs the gate (the kit uploads nothing - OPTIONAL-SCRIPTS.md).', text, count=1)
    if name == "package-render-gate.py":
        text = must(r'\(nexus-upload\.py, finalize-mod\.ps1\)', '(the upload step, finalize-mod.ps1)', text, count=1)
    if name == "nif-uv-overlap-gate.py":
        text = must(r'TEXCONV = r"[^"\r\n]*texconv\.exe"',
                    'TEXCONV = os.environ.get("TEXCONV") or __import__("shutil").which("texconv")   # kit: TEXCONV, then texconv on PATH (Microsoft DirectXTex, not shipped)',
                    text, count=1)
        # without texconv no DDS is decoded: _load_tex returns None and judge() says it found no texture to judge by
        text = must(r'    if not os\.path\.exists\(png\):\r?\n        subprocess\.run\(\[TEXCONV,',
                    '    if not os.path.exists(png) and TEXCONV:' + nl + '        subprocess.run([TEXCONV,', text, count=1)
    if name == "package_render_uv.py":
        text = must(r'\(set2\\\\uv_stretch_check\.py\)', '(a design-workspace script of the original, not in the kit)', text, count=1)
    if name == "engraving-layout-gate.py":
        text = must(r'\(set2/engraving_measure\.py, fragments\(\)\)', '(patternlib.measure, fragments())', text, count=1)
        text = must(r'set2/medallion_audit\.py --write-work \(set2/medallion_measure\.py on the atlas:',
                    'a medallion measure of the maps (the original\'s design-workspace audit, not in the kit; this file\'s fields are read below):', text, count=1)
        text = must(r'# run thresholds \(set2\\engraving_measure\.py uses the same\)', '# run thresholds (patternlib.measure uses the same)', text, count=1)
        text = must(r'# the standard medallion, measured \(set2\\medallion_measure\.py uses the same numbers\)', '# the standard medallion, measured', text, count=1)
        text = must(r'MED_HOW = "set2\\\\medallion_audit\.py <out> --write-work \(add the symbol to its MEDALLIONS table\)"',
                    'MED_HOW = "a medallion measure that writes medallion_check.json beside engraving_check.json (the fields medallion_problems() reads)"',
                    text, count=1)
    if name == "surface-profile-gate.py":
        text = must(r'THE MEASURE \(set2\\\\surface_profile_measure\.py in Blender \+ set2\\\\surface_profile_analyze\.py, written to',
                    'THE MEASURE (in the original, a Blender pass and an analysis script of its design workspace, not in the kit; written to',
                    text, count=1)
    if rel == "art/patternlib/__init__.py":
        text = must(r'\(absorbed from set2 engraving_measure\)', "(absorbed from the original's design-workspace measure)", text, count=1)
    if rel == "art/patternlib/damascus.py":
        text = must(r'\(4\. plans\\\\[^\r\n]*\\\\work\\\\\r?\ndamascus_options\\\\make_options\.py, the owner chose',
                    '(the original\'s design workspace,' + nl + 'the owner chose', text, count=1)
    if rel == "art/patternlib/measure.py":
        text = must(r'ABSORBED from set2\\engraving_measure\.py \(', "ABSORBED from the original's design-workspace measure (", text, count=1)
    return text


def rewrite_resolver(rel: str, text: str) -> str:
    if rel == "resolve.py":
        # the callers check scans the memory folder of the Claude Code project named after <ROOT>
        new, n = re.subn(expand_tokens(r'os\.path\.join\(home, "\.claude", "projects", "{PROJECT_FOLDER}", "memory", "\*\.md"\)'),
                         lambda m: 'os.path.join(home, ".claude", "projects", re.sub(r"[^A-Za-z0-9]", "-", ctx.root), "memory", "*.md")',
                         text, count=1)
        if n == 0:
            raise SystemExit("rewrite did not match in resolvers/resolve.py: the memory folder of scan_targets")
        text = new
    if rel == "session-start.py":
        # the test-request tool (the original's combined test runs) is not in the kit, so its weekly line is not asked for
        new, n = re.subn(r'(?m)^[ \t]*check_line\("test-request stats",[^\n]*\n', "", text)
        if n == 0:
            raise SystemExit("rewrite did not match in resolvers/session-start.py: the test-request line")
        text = new
    return text


def rewrite_gate_rules(text: str, live_scripts: str) -> str:
    """A 'package-script-passes' row's script is joined to .MD\\scripts by package-gate; the helpers moved into
    scripts\\gates on 2026-10-09 and the flat names are stubs, which the kit does not ship - point each row at the
    real file (found by walking the live scripts folder, never a stub)."""
    data = json.loads(text)
    for r in data.get("rules", []):
        if r.get("kind") == "package-script-passes" and r.get("script"):
            leaf = r["script"].replace("/", "\\").split("\\")[-1]
            cands = []
            for d, _, fs in os.walk(live_scripts):
                if "_proposed" in d or "__pycache__" in d:
                    continue
                if leaf in fs:
                    p = os.path.join(d, leaf)
                    if "RETIRED PATH" not in read(p)[:300]:
                        cands.append(os.path.relpath(p, live_scripts))
            if len(cands) != 1:
                raise SystemExit(f"gate-rules row {r.get('id')}: script {leaf} has {len(cands)} real copies: {cands}")
            if r["script"].replace("/", "\\") != cands[0]:
                old = r["script"]
                # rewrite the one value in the text, so the file keeps its own formatting
                pat = '"script": ' + json.dumps(old)
                if text.count(pat) != 1:
                    raise SystemExit(f"gate-rules row {r.get('id')}: cannot rewrite its script value in place")
                text = text.replace(pat, '"script": ' + json.dumps(cands[0]))
    return text


def build_rosters(live_md: str, live_root: str, kit_has) -> dict:
    """{roster file name: JSON text} for the kit. A role ships when what it names ships (kit_has(<path under ROOT>))
    or is a stage folder kit-install creates; a role naming a dropped role, an absolute path or the owner's home
    (other than the Claude Code folders) is dropped; identity values become placeholders; owner notes are dropped.
    Iterates to a fixed point so nothing ships that names a role that does not."""
    sys.path.insert(0, os.path.join(live_md, "resolvers"))
    import resolve as R   # the live resolver, to expand each role exactly as the scripts will
    folder = os.path.join(live_md, "resolvers", "rosters")
    ros = R.Rosters(folder)
    home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    ctx = R.Ctx(ros, live_root, {})
    keep_home = {"claude-home", "claude-projects"}            # generic Claude Code folders every person has
    memory_roles = {"memory-folder", "memory-index", "memory-always", "memory-topics-vocabulary"}
    raw = {}
    for fn in sorted(os.listdir(folder)):
        if fn.lower().endswith(".json") and fn not in ROSTERS_DROPPED:
            raw[fn] = json.loads(read(os.path.join(folder, fn)))
    origin = {name: fn for fn, d in raw.items() for name in d.get("roles", {})}
    kept = set(origin)
    dropped_why = {}

    def refs(body):
        s = body.get("at") or body.get("find") or ""
        return set(re.findall(r"\{role:([a-z0-9-]+)\}", s)) | ({body["retired"]} if body.get("retired") else set())

    # first pass: judge each role on what it names
    for name in list(kept):
        body = raw[origin[name]]["roles"][name]
        if body.get("kind") == "value" or body.get("retired"):
            continue
        if name in memory_roles or name in keep_home:
            continue
        try:
            path, _ = ctx.resolve(name)
        except Exception as e:   # names a role of a dropped roster
            kept.discard(name); dropped_why[name] = f"unresolvable ({e})"; continue
        p = os.path.normpath(path)
        rl = os.path.normcase(p)
        if rl.startswith(os.path.normcase(os.path.normpath(home)) + os.sep):
            kept.discard(name); dropped_why[name] = "the owner's home"; continue
        if not rl.startswith(os.path.normcase(os.path.normpath(live_root)) + os.sep) and rl != os.path.normcase(os.path.normpath(live_root)):
            kept.discard(name); dropped_why[name] = "absolute path outside <ROOT>"; continue
        rel = os.path.relpath(p, live_root).replace("\\", "/")
        kind = body.get("kind")
        if kind == "dir":
            ok = rel == "." or kit_has(rel)
        elif kind in ("place", "set"):
            ok = True   # a pattern: kept when every role it names is kept (second pass)
        else:
            ok = kit_has(rel)
        if not ok:
            kept.discard(name); dropped_why[name] = f"{rel} does not ship"
    # second pass: drop whatever names a dropped role, until nothing changes
    changed = True
    while changed:
        changed = False
        for name in list(kept):
            body = raw[origin[name]]["roles"][name]
            if any(r not in kept for r in refs(body)):
                kept.discard(name); dropped_why[name] = "names a dropped role"; changed = True
    result = {}
    for fn, d in raw.items():
        roles = {}
        for name, body in d.get("roles", {}).items():
            if name not in kept:
                continue
            b = dict(body)
            if fn == "identity.json" and name in kit_screen.DROPPED_IDENTITY_ROLES:
                continue   # no donation or chat link ships, not even as a placeholder
            if name == "memory-folder":
                # kit-install replaces @PROJECT@ with the Claude Code project folder of the person's <ROOT>
                b["at"] = "{role:claude-projects}\\@PROJECT@\\memory"
                b["note"] = "Claude Code's auto-memory folder of the project started at <ROOT>; kit-install fills in @PROJECT@"
            if b.get("note") and OWNER_NOTE_RE.search(b["note"]) and not b["note"].startswith(("PLACEHOLDER", "Claude Code's")):
                del b["note"]
            roles[name] = b
        if not roles:
            continue
        out_d = {k: v for k, v in d.items() if k != "roles"}
        if fn == "scripts.json":
            out_d["_about"] = "Roles of the scripts in the kind folders (game, mo2, plugins, art, ops), one role per file."
        out_d["roles"] = roles
        result[fn] = json.dumps(out_d, indent=1, ensure_ascii=False) + "\n"
    result["_dropped"] = dropped_why
    return result


def read(p: str) -> str:
    with open(p, "r", encoding="utf-8-sig", newline="") as f:
        return f.read()


def write(p: str, text: str, *, bom: bool = False) -> None:
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8-sig" if bom else "utf-8", newline="") as f:
        f.write(text)


def sha(p: str) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def build_entry_file(live_md: str) -> str:
    """The kit's CLAUDE.md: the kit header (kit-src\\CLAUDE-header.md) followed by the live entry file from the
    'How the rules are organised' section onward - the loading table, the always-on rules and the index."""
    live = read(os.path.join(live_md, "CLAUDE.md"))
    m = re.search(r"^## How the rules are organised.*", live, flags=re.S | re.M)
    if not m:
        raise SystemExit("live CLAUDE.md has no 'How the rules are organised' section")
    body = m.group(0)
    body = body.replace("**Session start also reads `BANNED-WORDS.md`**", "**Session start also reads `BANNED-WORDS.md`**")
    ver = re.search(r"<!-- RULES-VERSION: ([^|]+)\|", live)
    marker = re.search(r"<!-- RULES-VERSION: [^>]*-->", live)
    if not marker:
        raise SystemExit("live CLAUDE.md has no <!-- RULES-VERSION: ... --> marker")
    header = read(os.path.join(KIT_SRC, "CLAUDE-header.md"))
    # the marker is what rules-version.ps1 stamps and session-start.py reads (version and rule count)
    header = (header.replace("{RULES_MARKER}", marker.group(0))
              .replace("{RULES_VERSION}", ver.group(1).strip() if ver else "?")
              .replace("{KIT_VERSION}", __version__)
              .replace("{BUILT}", _dt.date.today().isoformat()))
    return sanitise(header + "\n" + body)


def run_screen(folder: str) -> int:
    """The --screen stage: the seeded proof that the scanner bites, then every shipped file. Any hit fails the build."""
    bad = kit_screen.selftest()
    if bad:
        print("SCREEN SELF-TEST FAILED:\n  " + "\n  ".join(bad))
        return 1
    failures = kit_screen.screen_tree(folder)
    if failures:
        by = {}
        for cls, *_ in failures:
            by[cls] = by.get(cls, 0) + 1
        print(f"SCREEN FAILED: {len(failures)} hit(s): " + ", ".join(f"{k} {v}" for k, v in sorted(by.items())))
        for cls, rel, line, what in failures[:400]:
            print(f"  {rel}:{line}: [{cls}] {what!r}")
        return 1
    print("screen: clean (no network call, no evidence, no advertising, nothing private; seeded self-test passed)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    # default root: PIPELINE_ROOT, else the tree this repo sits in (<ROOT>\6. current wip mods\PipelineKit)
    ap.add_argument("--source", default=os.environ.get("PIPELINE_ROOT") or os.path.dirname(os.path.dirname(HERE)))
    ap.add_argument("--identity-config", default=None,
                    help="the private identity config (default: role identity-patterns of the source)")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--out", default=None, help="build into this folder and keep it (a scratch build); dist is left alone")
    ap.add_argument("--screen", nargs="?", const=DIST, default=None, metavar="FOLDER",
                    help="only run the screening stage over a built kit (default dist); every build runs it anyway")
    a = ap.parse_args()
    if a.screen:
        return run_screen(a.screen)
    src = a.source
    problem = load_identity(a.identity_config or identity_config_path(src), src)
    if problem:
        print("REFUSED: " + problem)
        return 2
    md = os.path.join(src, ".MD")
    if not os.path.isdir(md):
        print(f"no .MD under {src}")
        return 2

    if a.out:
        out = os.path.abspath(a.out)
    else:
        out = DIST if not a.check else os.path.join(HERE, "_check-dist")
    if os.path.isdir(out):
        shutil.rmtree(out)
    manifest = {"kit": "Pipeline Kit", "version": __version__, "built": _dt.datetime.now().isoformat(timespec="seconds"),
                "sources": {}}

    ov = kit_screen.Overrides(os.path.join(KIT_SRC, "screen", "overrides.json"))
    kit_screen.COUNTS.clear()

    def put(rel_out: str, text: str, src_path: str | None = None, bom: bool = False):
        write(os.path.join(out, rel_out), text, bom=bom)
        if src_path:
            manifest["sources"][rel_out] = {"from": os.path.relpath(src_path, src).replace("\\", "/"), "source_sha256": sha(src_path)}

    # 1. documents
    for live_rel, kit_rel in DOCS:
        p = os.path.join(md, live_rel)
        if not os.path.isfile(p):
            print(f"  skip (missing): {live_rel}")
            continue
        t = read(p)
        if POINTER_RE.match(t) and t.count("\n") < 8:
            raise SystemExit(f"{live_rel} is a 'moved' pointer, not the document - point DOCS at the real file")
        put(kit_rel, kit_screen.screen_doc(kit_rel, sanitise(t), ov), p)
    entry = kit_screen.screen_doc("CLAUDE.md", build_entry_file(md), ov)
    put("CLAUDE.md", entry, os.path.join(md, "CLAUDE.md"))
    put("AGENTS.md", entry.replace("# Pipeline Kit - entry file (CLAUDE.md)", "# Pipeline Kit - entry file (AGENTS.md, identical to CLAUDE.md)"),
        os.path.join(md, "CLAUDE.md"))

    # 2. scripts and data
    scripts_shipped = all_scripts(md)
    for s in scripts_shipped:
        p = os.path.join(md, "scripts", s)
        if not os.path.isfile(p):
            raise SystemExit(f"script missing in the live tree: scripts/{s} (moved again? `resolve.py find <role>` names it)")
        raw = read(p)
        if "RETIRED PATH" in raw[:400]:
            raise SystemExit(f"scripts/{s} is a RETIRED-PATH stub - ship the real file (`resolve.py find <role>`)")
        text = rewrite_script(s, raw)
        text = kit_screen.patch_script(s, text)
        text = sanitise(text)
        put("scripts/" + s, text, p, bom=s.endswith(".ps1"))
    for d in DATA_FULL:
        p = os.path.join(md, "scripts", d)
        if os.path.isfile(p):
            t = read(p)
            if d == "gate-rules.json":
                t = rewrite_gate_rules(t, os.path.join(md, "scripts"))
                shipped = {x.replace("\\", "/") for x in scripts_shipped}
                t, no_script = kit_screen.screen_gate_rules(t, lambda sc: sc.replace("\\", "/") in shipped, ov)
                print(f"gate rows left out because their script does not ship: {len(no_script)} ({', '.join(no_script)})")
            put("scripts/" + d, sanitise(t), p)
    for d, body in DATA_EMPTY.items():
        put("scripts/" + d, body)

    # 2a. the role resolver (rule 70) - the scripts above look everything up through it
    for r in RESOLVER_FILES:
        p = os.path.join(md, "resolvers", r)
        if not os.path.isfile(p):
            raise SystemExit(f"resolver file missing: resolvers/{r}")
        put("resolvers/" + r, kit_screen.neutral_names(sanitise(rewrite_resolver(r, read(p)))), p, bom=r.endswith(".ps1"))

    # 2b. the Claude Code skills (1.0.2): every file of every .MD\skills\<name>\, sanitised like the documents
    skills_root = os.path.join(md, SKILLS_DIR)
    for dirpath, _, files in os.walk(skills_root):
        for fn in files:
            p = os.path.join(dirpath, fn)
            rel = SKILLS_DIR + "/" + os.path.relpath(p, skills_root).replace("\\", "/")
            if rel[len(SKILLS_DIR) + 1:] in kit_screen.CUT_SKILL_FILES or rel.split("/")[1] in SKILLS_LEFT_OUT:
                continue
            if "__pycache__" in rel:
                continue
            if os.path.splitext(fn)[1].lower() in TEXT_EXT:
                t = sanitise(read(p))
                put(rel, kit_screen.screen_doc(rel, t, ov) if fn.lower().endswith(".md") else kit_screen.neutral_names(t), p)

    # 3. templates
    for live_rel, kit_rel in TEMPLATES:
        p = os.path.join(src, live_rel)
        if os.path.isfile(p):
            t = sanitise(read(p))
            put(kit_rel, kit_screen.screen_doc(kit_rel, t, ov) if kit_rel.endswith((".md", ".txt")) else t, p)

    # 4. the kit's own files (and the repo's CHANGELOG.md, written by changelog.ps1 as changes happen - rule 61)
    cl = os.path.join(HERE, "CHANGELOG.md")
    if os.path.isfile(cl):
        put("CHANGELOG.md", kit_screen.screen_doc("CHANGELOG.md", read(cl), ov))
    for dirpath, dirs, files in os.walk(KIT_SRC):
        dirs[:] = [d for d in dirs if d != "screen"]    # the screen's own override file is the build's, never shipped
        for fn in files:
            if fn == "CLAUDE-header.md":
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, KIT_SRC).replace("\\", "/")
            ext = os.path.splitext(fn)[1].lower()
            if ext in TEXT_EXT:
                text = read(p).replace("{KIT_VERSION}", __version__).replace("{BUILT}", manifest["built"][:10])
                put(rel, text, bom=(ext == ".ps1"))
            else:
                os.makedirs(os.path.dirname(os.path.join(out, rel)), exist_ok=True)
                shutil.copy2(p, os.path.join(out, rel))

    # 4b. the rosters, filtered to what this kit ships (written last: a role ships only when its file does)
    def kit_has(rel_root: str) -> bool:
        if rel_root in INSTALL_CREATES or rel_root == ".MD":
            return True
        if not rel_root.startswith(".MD/"):
            return False
        return os.path.exists(os.path.join(out, rel_root[4:]))
    rosters = build_rosters(md, src, kit_has)
    dropped = rosters.pop("_dropped")
    for fn, text in rosters.items():
        p = os.path.join(md, "resolvers", "rosters", fn)
        put("resolvers/rosters/" + fn, kit_screen.neutral_names(sanitise(text)), p)
    print(f"rosters: {len(rosters)} shipped, {len(dropped)} role(s) left out (the owner's machine, or a file the kit does not ship)")

    # 5. the indexes are regenerated over the SANITISED text. logic-index.py asks the resolver of its own tree for the
    # library, and that resolver takes <ROOT> as the folder above .MD - so it runs in a staged copy, <stage>\.MD = dist
    import tempfile
    stage = tempfile.mkdtemp(prefix="pipeline-kit-stage-")
    try:
        smd = os.path.join(stage, ".MD")
        shutil.copytree(out, smd)
        idx = os.path.join(smd, "scripts", "logic-index.py")
        r = subprocess.run([sys.executable, idx], capture_output=True, text=True)
        if r.returncode != 0:
            print("logic-index.py failed on the kit copy:\n" + r.stdout + r.stderr)
            return 1
        r = subprocess.run([sys.executable, idx, "--check"], capture_output=True, text=True)
        if r.returncode != 0:
            print("logic-index.py --check still stale after regeneration:\n" + r.stdout + r.stderr)
            return 1
        shutil.copy2(os.path.join(smd, "PAST-MISTAKES-LIBRARY.md"), os.path.join(out, "PAST-MISTAKES-LIBRARY.md"))
        print("past-mistakes library index: regenerated and current")
        # the digest is derived from the rule parts, so it is regenerated over the screened text
        r = subprocess.run([sys.executable, os.path.join(smd, "scripts", "rules-digest.py")], capture_output=True, text=True)
        if r.returncode != 0:
            print("rules-digest.py failed on the kit copy:\n" + r.stdout + r.stderr)
            return 1
        shutil.copy2(os.path.join(smd, "RULES-DIGEST.md"), os.path.join(out, "RULES-DIGEST.md"))
        r = subprocess.run([sys.executable, os.path.join(smd, "resolvers", "resolve.py"), "check", "--schema", "gate-rules",
                            "--rules-file", os.path.join(smd, "scripts", "gate-rules.json")], capture_output=True, text=True)
        if r.returncode != 0:
            print("gate-rules.json fails its schema in the kit:\n" + r.stdout + r.stderr)
            return 1
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    gri = os.path.join(out, "scripts", "gate-rules-index.py")
    r = subprocess.run([sys.executable, gri, "--build"], capture_output=True, text=True)
    if r.returncode != 0:
        print("gate-rules-index.py --build failed on the kit copy:\n" + r.stdout + r.stderr)
        return 1
    print("gate-rules index: regenerated")

    # 5b. the counts the kit's own README states are taken from what shipped, so they cannot go stale
    gate_rows = len(json.loads(read(os.path.join(out, "scripts", "gate-rules.json")))["rules"])
    rule_count = len(re.findall(r"(?m)^\*\*\d+\. ", read(os.path.join(out, "RULES-DIGEST.md"))))
    lib_entries = len(re.findall(r"(?m)^## ", read(os.path.join(out, "PAST-MISTAKES-LIBRARY.md"))))
    for rel_doc in ("README.md", "README-FOR-AI.md"):
        pd = os.path.join(out, rel_doc)
        write(pd, read(pd).replace("{GATE_ROWS}", str(gate_rows)).replace("{RULE_COUNT}", str(rule_count)).replace("{LIB_ENTRIES}", str(lib_entries)))

    # 6. the leak scan - the kit's own gate
    leaks = []
    for dirpath, _, files in os.walk(out):
        for fn in files:
            p = os.path.join(dirpath, fn)
            if os.path.splitext(fn)[1].lower() not in TEXT_EXT:
                continue
            t = read(p)
            # the second pass reads the text with regex punctuation taken out: a name spelled as [x]yz in a gate pattern
            for scan in (t, re.sub(r"[\[\]\\?()|^$]", "", t)):
                for pid, rx in LEAK_PATTERNS + [("generic", GENERIC_LEAK_RE)]:
                    for m in rx.finditer(scan):
                        line = scan.count("\n", 0, m.start()) + 1
                        leaks.append(f"{os.path.relpath(p, out)}:{line}: [{pid}] {m.group(0)!r}")
            if fn != "build_kit.py":
                for m in re.finditer(r"\{(KIT_VERSION|BUILT|RULES_VERSION|GATE_ROWS|RULE_COUNT|LIB_ENTRIES)\}", t):   # an unsubstituted placeholder is a defect too
                    line = t.count("\n", 0, m.start()) + 1
                    leaks.append(f"{os.path.relpath(p, out)}:{line}: unsubstituted {m.group(0)}")
    # 1.0.3: "files" hashes every file AS SHIPPED, so a member can verify the download; "sources" keeps the hash of the
    # live file each one was built from (before sanitising, so it differs from the shipped hash by design)
    manifest["_about"] = ("files: the SHA-256 of every file in this kit as shipped - check your download against these. "
                          "sources: the live file each kit file was built from and that file's hash BEFORE sanitising; "
                          "it does not match the shipped file, by design.")
    manifest["files"] = {os.path.relpath(os.path.join(d, f), out).replace("\\", "/"): sha(os.path.join(d, f))
                         for d, _, fs in os.walk(out) for f in fs if "__pycache__" not in d}
    write(os.path.join(out, "MANIFEST.json"), json.dumps(manifest, indent=2) + "\n")
    n_files = sum(len(f) for _, _, f in os.walk(out))
    size = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(out) for f in fs)
    print(f"kit {__version__}: {n_files} files, {size/1024:.0f} KB -> {out}")
    if leaks:
        print(f"LEAK SCAN FAILED: {len(leaks)} private identifier(s) survived sanitising:")
        for l in leaks[:40]:
            print("  " + l)
        return 1
    print("leak scan: clean")
    for s_line in ov.stale():
        print("  screen override matched nothing (stale?): " + s_line)
    print("evidence removed: " + ", ".join(f"{k} {v}" for k, v in sorted(kit_screen.COUNTS.items())))
    if run_screen(out) != 0:
        return 1
    if a.check and not a.out:
        shutil.rmtree(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
