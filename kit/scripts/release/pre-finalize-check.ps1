<#
.SYNOPSIS
    Mechanical pre-finalize gate for a Skyrim mod in this project (<ROOT>).

.DESCRIPTION
    CLAUDE.md rule 21 says a mod only moves into "10. finalized mods" once it is confirmed
    functional. That "functional" judgement call still has to be made by a human/agent - this
    script does NOT make it. What it does check, mechanically, is everything ELSE CLAUDE.md and
    SMF-CONVERSION-PLAYBOOK.md say a finalized mod must be true of, so that a finalize doesn't
    also silently ship a version-numbering mistake, an unreverted debug leftover, a missed
    compatibility gate, a stale Nexus page, or a rule-32/rule-28 regression - the exact class of
    thing that has already shipped twice (Compass Navigation Overhaul v1.0.10, Dragon's Eye
    Minimap v1.4.11/v1.4.12) because it depended on whoever was finalizing remembering correctly.

    Run this against the version about to be finalized (the newest package in
    "7. current test builds" unless -Version pins an older one) BEFORE moving it into
    "10. finalized mods". A clean PASS is required, or every individual FAIL must be explicitly
    acknowledged and justified in PROGRESS.md (per CLAUDE.md rule 15/21's updated wording) -
    never silently overridden.

    Every check is one of:
      PASS  - checked, and it's correct.
      FAIL  - checked, and it's genuinely wrong. Blocks finalizing (non-zero exit).
      WARN  - checked, correct-but-notable (e.g. Nexus material intentionally not yet updated
              to the new candidate version - that catches up as part of finalizing itself, per
              rule 10, so it is not itself a finalize blocker). Never blocks by itself.
      SKIP  - could not be checked from what's on disk (missing tool, ambiguous source, nothing
              to check e.g. no keybind setting exists in this mod at all). Never blocks - the
              whole point of separating this from FAIL is that this script must never cry wolf
              on a mod it cannot fully introspect.

.PARAMETER ModName
    The mod's package/Nexus-distro display name, e.g. "Dragon's Eye Minimap" or
    "Compass Navigation Overhaul" - i.e. the name that prefixes its folders under
    "7. current test builds", "10. finalized mods" and "11. Nexus distro".

.PARAMETER Version
    Optional. Pins the check to a specific already-packaged version (e.g. "1.5.1") instead of
    the newest one found in "7. current test builds".

.PARAMETER RepoPath
    Optional. Overrides auto-discovery of the mod's source repo under "6. current wip mods".

.PARAMETER ProjectRoot
    Optional. Defaults to "<ROOT>".

.PARAMETER SyncNexusDistro
    No longer does anything but print one line (the owner, 2026-10-12: "the distro is not synced until
    finalize" - straight flow). The distro sync runs inside finalize-mod.ps1 now, and sync-nexus-distro.ps1
    refuses a run outside it for a version not yet in "10. finalized mods". The switch is kept so existing
    command lines do not break.

.PARAMETER DeferRows
    gate-rules.json row ids package-gate.ps1 does NOT evaluate in this run, passed through to its -DeferRows; each is
    printed as deferred. Only finalize-mod.ps1 passes it (2026-10-13, straight flow B): its single gate runs before the
    move, so 'distro-archive-equals-finalized-folder' - the distro zip against the package - cannot be judged yet and
    is checked by finalize-mod's post-check after the zip is copied in. A run without -FromFinalize (by hand, or any
    caller other than finalize) defers the rows that need finalize's own output on its own (2026-10-22, see
    -FromFinalize), and adds any rows passed here.

.PARAMETER FromFinalize
    Only finalize-mod.ps1 passes it (2026-10-22). Without it the run is STANDALONE: (a) the rows that can only pass after
    finalize has written its output ($FinalizeOutputRows: distro-archive-equals-finalized-folder) are deferred and
    reported "deferred - runs inside finalize", and (b) the gate event carries refs.caller "standalone", while a
    finalize run's carries "finalize-mod". Gate C compares a run only with the last gate event of the SAME caller, so a
    standalone check can never block a later finalize (ApocryphaMenuFramework 2.2.3, 2026-10-22: a standalone run
    refused on the distro-archive row, which cannot pass before finalize, and finalize's gate C then refused finalize as
    a rerun on unchanged inputs - it needed -Force).

.PARAMETER Force
    Gate C (straight flow, 2026-10-13): run the gate although nothing it reads has changed since its last refusal
    (otherwise that is exit 3). Needs -Reason; the reason goes into the gate event's note and refs.override.

.PARAMETER Reason
    Why the gate must run on unchanged inputs. Mandatory with -Force.

.PARAMETER Package
    The candidate package folder, when the caller has already picked it (finalize-mod.ps1 passes the folder its
    test-build pick chose). Without it, a -Version with several folders ("<Mod> X.Y.Z", " FOMOD", " (...)" suffixes) is
    decided by the same pick (test-build-pick.ps1): the folder whose artefact matches the ledger's working hash, and a
    refusal when none or several match.

.EXAMPLE
    .\pre-finalize-check.ps1 -ModName "Dragon's Eye Minimap"
#>

param(
    [Parameter(Mandatory = $true)][string]$ModName,
    [string]$Version,
    [string]$RepoPath,
    [string]$ProjectRoot = $env:PIPELINE_ROOT,
    [switch]$SyncNexusDistro,
    [string[]]$DeferRows,
    [string]$Package,
    [switch]$Force,
    [string]$Reason,
    [switch]$FromFinalize
)

# 'Continue', not 'Stop': native tools (git, gh) writing to stderr - even on a clean exit -
# get wrapped as a NativeCommandError under 'Stop' and would abort the whole script over
# something as routine as "no commits yet" or "no upstream branch". Every check below already
# validates $LASTEXITCODE / return values explicitly rather than relying on exceptions for
# control flow, and the handful of spots that can genuinely throw (JSON parsing, file-version
# reads) are individually wrapped in try/catch.
$ErrorActionPreference = 'Continue'
if (-not $ProjectRoot) { $_kitRoot = $PSScriptRoot; while ($_kitRoot -and (Split-Path $_kitRoot -Leaf) -ne '.MD') { $_kitRoot = Split-Path $_kitRoot -Parent }; if ($_kitRoot) { $_kitRoot = Split-Path $_kitRoot -Parent }; $ProjectRoot = $_kitRoot }   # kit: <ROOT> is the folder above the .MD this script sits under, unless PIPELINE_ROOT says otherwise
$results = New-Object System.Collections.Generic.List[object]
$VersionArg = $Version   # gate C keys its lookup on the version asked for, even when package discovery fails
if ($Force -and -not "$Reason".Trim()) { Write-Output 'REFUSED: -Force needs -Reason "<why the gate must run on unchanged inputs>" - it is written into the gate event (gate C).'; exit 2 }
# Rows that can only pass AFTER finalize has written its output (the finalized zip copied into the distro). A standalone
# run defers them itself and says so; only finalize-mod.ps1 (-FromFinalize) judges them, in its post-check (2026-10-22).
$FinalizeOutputRows = @('distro-archive-equals-finalized-folder')
$gcCaller = if ($FromFinalize) { 'finalize-mod' } else { 'standalone' }
if (-not $FromFinalize) {
    $DeferRows = @(@($DeferRows) + $FinalizeOutputRows | Where-Object { $_ } | Select-Object -Unique)
    foreach ($id in $FinalizeOutputRows) { Write-Output "deferred - runs inside finalize: [$id] (needs finalize's own output; a standalone check never judges it)" }
}
# GATE C's input fingerprint (see the GATE C block after discovery): written to a temp file and run with Python
$GateInputsPy = @'
import hashlib, json, os, subprocess, sys
a = json.load(open(sys.argv[1], encoding="utf-8-sig"))
CAP = 200
lines, names, counts = [], [], {}
extra = {"untrackedCap": CAP, "untrackedTotal": 0, "untrackedCapped": False}
def fsha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()
def add(name, items):
    names.append(name)
    counts[name] = len(items)
    lines.append("[%s] %d" % (name, len(items)))
    lines.extend(items)
def walk(root):
    out = []
    if root and os.path.isdir(root):
        for r, _, ns in os.walk(root):
            for nm in ns:
                full = os.path.join(r, nm)
                out.append((os.path.relpath(full, root).replace(os.sep, "/"), full))
    return sorted(out)
def is_text(p):
    with open(p, "rb") as f:
        return b"\0" not in f.read(8192)
def canon(o):
    return json.dumps(o, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
def load_rows(p):
    if not p or not os.path.exists(p):
        return []
    d = json.load(open(p, encoding="utf-8-sig"))
    out = []
    for x in (d if isinstance(d, list) else [d]):
        out.extend(x if isinstance(x, list) else [x])
    return [x for x in out if isinstance(x, dict)]
add("package-files", ["%s\t%d\t%s" % (rel, os.path.getsize(f), fsha(f)) for rel, f in walk(a.get("package"))])
add("distro-text-files", ["%s\t%s" % (rel, fsha(f)) for rel, f in walk(a.get("distro")) if is_text(f)])
repo = a.get("repo") or ""
def git(*args):
    r = subprocess.run(["git", "-C", repo] + list(args), capture_output=True)
    return r.stdout if r.returncode == 0 else None
if repo and os.path.isdir(os.path.join(repo, ".git")):
    head = git("rev-parse", "HEAD")
    up = git("rev-parse", "@{u}")
    st = git("status", "--porcelain=v1", "-z", "--untracked-files=all") or b""
    diff = git("diff", "HEAD", "--no-color", "--no-ext-diff", "--binary")
    ents = [e.decode("utf-8", "replace") for e in st.split(b"\0") if e]
    untracked = sorted(e[3:] for e in ents if e.startswith("?? "))
    extra["untrackedTotal"] = len(untracked)
    extra["untrackedCapped"] = len(untracked) > CAP
    def uhash(rel):
        p = os.path.join(repo, rel)
        return fsha(p) if os.path.isfile(p) else "(not a file)"
    add("repo-head", [head.decode().strip() if head else "(no commit)"])
    add("repo-upstream", [up.decode().strip() if up else "(no upstream)"])
    add("git-status-porcelain", ents)
    add("git-diff-head", [hashlib.sha256(diff).hexdigest() if diff is not None else "(no diff)"])
    add("untracked-files", ["%s\t%s" % (u, uhash(u)) for u in untracked[:CAP]] + (["(capped at %d of %d)" % (CAP, len(untracked))] if len(untracked) > CAP else []))
else:
    for nm in ("repo-head", "repo-upstream", "git-status-porcelain", "git-diff-head", "untracked-files"):
        add(nm, ["(no git repo)"])
gr = a.get("gate_rules")
add("gate-rules", [fsha(gr) if gr and os.path.isfile(gr) else "(missing)"])
key = a.get("key") or ""
rows = [dict((k, v) for k, v in r.items() if k != "prunePending") for r in load_rows(a.get("ledger")) if str(r.get("mod", "")).lower() == key.lower()]
add("ledger-rows", [canon(r) for r in sorted(rows, key=lambda r: str(r.get("version")))])
reg = {}
if a.get("registry") and os.path.exists(a["registry"]):
    reg = json.load(open(a["registry"], encoding="utf-8-sig"))
regrow = next((v for k, v in reg.items() if k.lower() == key.lower()), None) if isinstance(reg, dict) else None
add("registry-row", [canon(dict((k, v) for k, v in regrow.items() if k != "nexusChecked")) if isinstance(regrow, dict) else "(not registered)"])
def hashed(d):
    return ["%s\t%s" % (n, fsha(p) if p and os.path.isfile(p) else "(missing)") for n, p in sorted(d.items())]
add("gate-scripts", hashed(a.get("scripts") or {}))
helpers = dict(a.get("helpers") or {})
try:
    rules = json.load(open(gr, encoding="utf-8-sig")) if gr and os.path.isfile(gr) else {}
    for r in (rules.get("rules") or []) if isinstance(rules, dict) else []:
        s = r.get("script") if isinstance(r, dict) else None
        if s:
            helpers["rule-script:" + s.replace("\\", "/")] = os.path.join(a.get("md_scripts") or "", s)
except ValueError:
    pass
add("gate-helpers", hashed(helpers))
cd = a.get("compat_dir") or ""
cn = [n.lower() for n in (a.get("compat_names") or []) if n]
comp = []
if os.path.isdir(cd):
    for nm in sorted(os.listdir(cd)):
        full = os.path.join(cd, nm)
        if os.path.isfile(full) and nm.lower().endswith(" - compatibility.txt") and any(n in nm.lower() for n in cn):
            comp.append("%s\t%s" % (nm, fsha(full)))
add("compatibility-verdicts", comp)
acks = []
pp = a.get("progress") or ""
want = ("%s %s" % (a.get("display") or "", a.get("version") or "")).strip()
if pp and os.path.isfile(pp) and want:
    for ln in open(pp, encoding="utf-8-sig", errors="replace"):
        if ln.startswith("## Gate acknowledgement - ") and want in ln:
            acks.append(ln.rstrip("\r\n"))
add("gate-acknowledgements", acks)
digest = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
out = {"sha256": digest, "names": names, "counts": counts}
out.update(extra)
print(json.dumps(out))
'@

function Add-Result {
    param([string]$Rule, [string]$Check, [ValidateSet('PASS', 'FAIL', 'WARN', 'SKIP')][string]$Status, [string]$Detail)
    $results.Add([pscustomobject]@{ Rule = $Rule; Check = $Check; Status = $Status; Detail = $Detail })
}

function Normalize-Name {
    param([string]$s)
    if (-not $s) { return '' }
    return ($s -replace '[^A-Za-z0-9]', '').ToLowerInvariant()
}

# Extract every X.Y.Z (or vX.Y.Z) version-shaped substring from a blob of text.
function Get-VersionMatches {
    param([string]$Text)
    if (-not $Text) { return @() }
    $matches = [regex]::Matches($Text, '\bv?(\d+)\.(\d+)\.(\d+)\b')
    return $matches | ForEach-Object {
        [pscustomobject]@{
            Text  = $_.Value
            Major = [int]$_.Groups[1].Value
            Minor = [int]$_.Groups[2].Value
            Patch = [int]$_.Groups[3].Value
        }
    }
}

# Rule 29's line when the exact version is not installed (2026-10-13, Main Agent: a wrong warning trains everyone to
# ignore it). The old line called whatever other build was installed "a newer build" without comparing - test build 2.0.8
# was called newer than 2.2.0 - and picked it by the FIRST X.Y.Z in the folder name. Now the version is read after the
# mod's name (prefixes "[NoDelete] n ", "test ", "unpublished " stripped), the newest installed one is chosen by a real
# version comparison, and the line says "a newer build", "an older build" or "a different build of the same version",
# with both numbers. Tested by scripts\tests\test_prefinalize_installed_wording.py.
function Get-InstalledVersionNote {
    param([string]$Version, [object[]]$Folders, [string[]]$Names)
    $wm = @(Get-VersionMatches $Version | Select-Object -First 1)
    $want = if ($wm.Count) { [version]('{0}.{1}.{2}' -f $wm[0].Major, $wm[0].Minor, $wm[0].Patch) } else { $null }
    $rows = @(foreach ($f in @($Folders | Where-Object { $_ })) {
        $name = if ($f -is [string]) { $f } else { "$($f.Name)" }
        $bare = $name -replace '^(\[NoDelete\] \d+ |test |unpublished )', ''
        $own = @($Names | Where-Object { $_ -and ($bare -like "$_ *") } | Sort-Object Length -Descending | Select-Object -First 1)
        $rest = if ($own.Count) { $bare.Substring($own[0].Length) } else { $bare }
        $m = @(Get-VersionMatches $rest | Select-Object -First 1)
        [pscustomobject]@{ Name = $name; Version = $(if ($m.Count) { [version]('{0}.{1}.{2}' -f $m[0].Major, $m[0].Minor, $m[0].Patch) } else { $null }) }
    })
    $tail = "cannot confirm THIS specific version was ever the one tested in-game from what's on disk now."
    $known = @($rows | Where-Object { $_.Version } | Sort-Object Version -Descending)
    if (-not $known.Count -or -not $want) {
        return "Exact version $Version is not installed; the installed build ($((@($rows | ForEach-Object { $_.Name })) -join ', ')) carries no version number to compare - $tail"
    }
    $top = $known[0]
    if ($top.Version -gt $want) {
        return "Exact version $Version is not installed, but a newer build ($($top.Name), version $($top.Version)) already is (rule 29 replaces on every new build, so this is expected once a later build shipped) - $tail"
    }
    if ($top.Version -lt $want) {
        return "Exact version $Version is not installed - only an older build ($($top.Name), version $($top.Version)) is, so $Version was never installed here or was replaced by an older build - $tail"
    }
    return "Exact version $Version is not installed as packaged, but a different build of the same version ($($top.Name), also $($top.Version)) is - its files are not the ones this check accepts as the package - $tail"
}

# Rule 29 for a Mod Organizer 2 PLUGIN of ours (2026-09-22, folder plugins 2026-10-25). The package ships plugins\<Name>.py
# (a single-file plugin) and/or plugins\<Name>\__init__.py plus its modules (a FOLDER plugin - MO2 Agent Control 1.0.0,
# "ApocryphaAgentControl"); both are installed in the instance's own plugins folder beside ModOrganizer.exe, never in
# mods\. Until today only the top-level *.py files were compared, so a folder plugin was never seen at all. Every file
# the package ships under plugins\ - each top-level .py and every file of each subfolder, recursively - must be present
# and byte-identical at the same relative path in the instance (__pycache__ and *.pyc are ignored on both sides; extra
# files in the instance, such as MO2's own caches, are fine). Returns $null when the package ships no MO2 plugin, else
# an object { Installed; Detail }. Tested by scripts\tests\test_prefinalize_mo2_folder_plugin.py.
function Test-Mo2PluginInstalled {
    param([string]$PkgPlugins, [string]$InstPlugins)
    if (-not $PkgPlugins -or -not (Test-Path -LiteralPath $PkgPlugins -PathType Container)) { return $null }
    $root = (Get-Item -LiteralPath $PkgPlugins).FullName.TrimEnd('\')
    $topPy = @(Get-ChildItem -LiteralPath $root -Filter '*.py' -File -ErrorAction SilentlyContinue)
    $dirs = @(Get-ChildItem -LiteralPath $root -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne '__pycache__' })
    $folderPlugins = @($dirs | Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName '__init__.py') -PathType Leaf })
    if ($topPy.Count -eq 0 -and $folderPlugins.Count -eq 0) { return $null }
    $need = @($topPy) + @(foreach ($d in $dirs) {
        Get-ChildItem -LiteralPath $d.FullName -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
            $_.Extension -ne '.pyc' -and $_.FullName.Substring($root.Length + 1) -notmatch '(^|\\)__pycache__(\\|$)' }
    })
    $bad = @(foreach ($f in $need) {
        $rel = $f.FullName.Substring($root.Length + 1)
        $inf = Join-Path $InstPlugins $rel
        if (-not (Test-Path -LiteralPath $inf -PathType Leaf)) { "$rel (missing)" }
        elseif ((Get-FileHash -LiteralPath $inf).Hash -ne (Get-FileHash -LiteralPath $f.FullName).Hash) { "$rel (different)" }
    })
    $units = @(@($topPy | ForEach-Object { $_.Name }) + @($folderPlugins | ForEach-Object { "$($_.Name)\" }))
    if ($bad.Count -eq 0) {
        return [pscustomobject]@{ Installed = $true; Detail = "$InstPlugins\$($units[0]) (MO2 plugin, all $($need.Count) packaged file(s) under plugins\ byte-identical to the package)" }
    }
    $shown = (@($bad | Select-Object -First 5) -join ', ') + $(if ($bad.Count -gt 5) { ", and $($bad.Count - 5) more" } else { '' })
    return [pscustomobject]@{ Installed = $false; Detail = "MO2 plugin ($($units -join ', ')) not installed as packaged in ${InstPlugins}: $shown" }
}

# Rule 29's instance list: which MO2 instances a package of this game is looked for in, and the install prefix there.
# Returns { Instances = @(@{ Name; Path }...); InstallPrefix }. Calls Get-ModGame (distro-names, dot-sourced before use).
# A function so scripts\tests\test_prefinalize_install_game.py can run it against the real registry in seconds instead
# of running this whole gate (2026-10-25: the whole gate took minutes and timed out the nightly suite).
function Get-Rule29Instances {
    param([string]$RegistryPath, [string]$ModName, [string]$DisplayName, [string]$InstGame, [string]$ProjectRoot)
    # kit: the MO2 instances to check are PIPELINE_MO2_INSTANCES, a ;-separated list of <instance>\mods folders
    $instances = @(); foreach ($p in @(($env:PIPELINE_MO2_INSTANCES -split ';') | Where-Object { $_ })) { $instances += @{ Name = (Split-Path (Split-Path $p -Parent) -Leaf); Path = $p } }
    # A mod registered for ANOTHER GAME names its own instances (registry: instances, installPrefix) - the Oblivion
    # Remastered framework is installed under <MO2>\Oblivion Remastered\mods with a Root\ prefix (2026-09-26).
    $prefix = ''
    try {
        if ($RegistryPath -and (Test-Path -LiteralPath $RegistryPath)) {
            $reg0 = Get-Content -LiteralPath $RegistryPath -Raw | ConvertFrom-Json
            # ONLY THIS PACKAGE'S GAME (2026-10-13): the Skyrim, Oblivion Remastered and Witcher 3 frameworks all carry the
            # display name "Apocrypha Menu Framework", and only the Oblivion entry names instances, so a Skyrim finalize
            # matched the Oblivion entry by display name and looked for the install in the Oblivion instance.
            # The name test comes FIRST (2026-10-25): Get-ModGame starts a Python process per call, and asking it for all
            # ~106 registry entries cost ~21 s per run; only the 1-3 entries of this name need their game.
            foreach ($prop in $reg0.PSObject.Properties) {
                $e0 = $prop.Value
                if (-not (($prop.Name -ieq $ModName -or $e0.repo -ieq $ModName -or $e0.displayName -ieq $ModName -or ($DisplayName -and $e0.displayName -ieq $DisplayName)) -and $e0.instances)) { continue }
                if ($InstGame -and (Get-ModGame -Entry $e0 -ProjectRoot $ProjectRoot) -ne $InstGame) { continue }
                $instances = @(); foreach ($ip in @($e0.instances)) { $instances += @{ Name = "$($e0.game) instance ($ip)"; Path = $ip } }
                if ($e0.installPrefix) { $prefix = $e0.installPrefix }
            }
        }
    } catch { }
    return [pscustomobject]@{ Instances = $instances; InstallPrefix = $prefix }
}

function VerEq {
    param([string]$a, [string]$b)
    if (-not $a -or -not $b) { return $false }
    $ma = [regex]::Match($a, '(\d+)\.(\d+)\.(\d+)')
    $mb = [regex]::Match($b, '(\d+)\.(\d+)\.(\d+)')
    if (-not $ma.Success -or -not $mb.Success) { return $false }
    return ($ma.Groups[1].Value -eq $mb.Groups[1].Value) -and ($ma.Groups[2].Value -eq $mb.Groups[2].Value) -and ($ma.Groups[3].Value -eq $mb.Groups[3].Value)
}

# ---- roles, looked up ONCE here (STEPS 5.6), through the resolver OF THIS TREE (scripts\release\ -> ..\..\resolvers) ----
# Never the absolute <ROOT> path and never the script folder variable for a sibling: a moved or copied tree answers inside itself.
$ResolverPy = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\resolvers\resolve.py'))
function Find-Role([string]$role) {
    $p = @(& py -3 $ResolverPy find $role)
    if ($LASTEXITCODE -ne 0 -or $p.Count -eq 0 -or -not "$($p[0])".Trim()) { Write-Output "pre-finalize-check: cannot resolve role '$role' ($($p -join ' '))"; exit 1 }
    return "$($p[0])".Trim()
}
$ScriptsDir = Find-Role 'md-scripts'   # the scripts folder, used only for the optional flag file
$RoleRegistry = Find-Role 'version-registry'
$RoleVersionGate = Find-Role 'version-gate'
$RolePackageGate = Find-Role 'package-gate'
$RoleParity = Find-Role 'check-export-parity'
$RoleCoverage = Find-Role 'translation-coverage'
$RolePipelineLog = Find-Role 'pipeline-log'

# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

Write-Host "Pre-finalize check for '$ModName'" -ForegroundColor Cyan
Write-Host ("=" * 70)

$baseName = ($ModName -split ' - ')[0].Trim()
$normBase = Normalize-Name $baseName

if (-not $RepoPath) {
    $wipRoot = Join-Path $ProjectRoot '6. current wip mods'
    $candidates = @(Get-ChildItem -Path $wipRoot -Directory -ErrorAction SilentlyContinue |
        Where-Object { (Normalize-Name $_.Name).StartsWith($normBase) -or (Normalize-Name $_.Name).Contains($normBase) } |
        Sort-Object { $_.Name.Length })
    if ($candidates.Count -ge 1) {
        $RepoPath = $candidates[0].FullName
    }
}
if ($RepoPath) {
    Add-Result -Rule '-' -Check 'Repo discovery' -Status PASS -Detail "Resolved source repo: $RepoPath"
} else {
    Add-Result -Rule '-' -Check 'Repo discovery' -Status SKIP -Detail "Could not find a matching repo under '6. current wip mods' for base name '$baseName'. Pass -RepoPath explicitly. Every repo-dependent check below will be SKIPped."
}

. (Find-Role 'distro-names')   # the folder is "<Game> - <Mod>" since 2026-09-29; never join the name yourself
# Packages sit in "<stage>\<Game> - <Mod>\" since 2026-10-01, so two games' mods of one name and version can both exist.
# The game comes from the mod's registry entry (key, repo, display name or alias; with -RepoPath, the entry of that repo);
# a name no entry knows reads every game folder, as the flat layout did.
$modGame = ''
try {
    $regForGame = Get-Content -LiteralPath $RoleRegistry -Raw | ConvertFrom-Json
    $gameEntries = @($regForGame.PSObject.Properties | Where-Object { $_.Name -ieq $ModName -or $_.Value.repo -ieq $ModName -or $_.Value.displayName -ieq $ModName -or (@($_.Value.aliases) -contains $ModName) })
    if ($RepoPath -and $gameEntries.Count -gt 1) { $byRepo = @($gameEntries | Where-Object { $_.Value.repo -ieq (Split-Path $RepoPath -Leaf) }); if ($byRepo.Count) { $gameEntries = $byRepo } }
    if ($gameEntries.Count -ge 1) { $modGame = Get-ModGame -Entry $gameEntries[0].Value -ProjectRoot $ProjectRoot }
} catch { }

$testBuildsRoot = Join-Path $ProjectRoot '7. current test builds'
$pkgCandidates = @(Find-Packages -Root $testBuildsRoot -Game $modGame -Folders -ProjectRoot $ProjectRoot |
    Where-Object { $_.Name -like "$ModName *" -or $_.Name -eq $ModName })

# A package folder is named by the mod's DISPLAY name ("Dragon's Eye Minimap 1.5.7"),
# while $ModName is the REPO name ("DragonsEyeMinimap-SMF"). Those are different for every mod in
# this project, so matching on $ModName alone found nothing and reported "nothing to finalize" for a
# package sitting right there. Resolve the display name the same way package-mod.ps1 does: find the
# packages that actually contain this repo's built DLL.
if (-not $pkgCandidates.Count -and $RepoPath) {
    $builtDll = Get-ChildItem -LiteralPath $RepoPath -Recurse -Filter '*.dll' -File -ErrorAction SilentlyContinue |
                Where-Object { $_.FullName -match '\\build\\' } |
                Select-Object -First 1
    if ($builtDll) {
        $targetName = $builtDll.Name
        $pkgCandidates = @(Find-Packages -Root $testBuildsRoot -Game $modGame -Folders -ProjectRoot $ProjectRoot |
            Where-Object { $_.Name -notlike '*Debug Symbols*' } |
            Where-Object {
                Get-ChildItem -LiteralPath $_.FullName -Recurse -Filter $targetName -File -ErrorAction SilentlyContinue |
                Select-Object -First 1
            })
        if ($pkgCandidates.Count) {
            Add-Result -Rule '-' -Check 'Display name resolution' -Status PASS `
                -Detail "Repo '$ModName' builds '$targetName'; matched $($pkgCandidates.Count) package(s) containing it."
        }
    }
}

# An ASSET-ONLY mod builds no DLL, so the lookup above finds nothing and every downstream check
# SKIPs while "Package discovery" FAILs on a package that is sitting right there. The version
# registry already knows this mod's display name - it is the one thing that is authoritative about
# it - so ask that. (2026-09-16: Jarl Ulfric Armor Replacer, a plugin and loose files with no code.)
if (-not $pkgCandidates.Count) {
    $regPath = $RoleRegistry
    if (Test-Path -LiteralPath $regPath) {
        $reg = Get-Content -LiteralPath $regPath -Raw | ConvertFrom-Json
        # Match on the KEY, the REPO or the DISPLAY NAME. A mod whose repo folder was renamed keeps its
        # original registry key - version-gate.ps1's 'rename' deliberately leaves the key and the ledger
        # alone so recorded versions still belong to the same mod - so looking up by key alone finds
        # nothing when -Mod was given as the new repo name. (2026-09-16: Civil War Final Battle
        # Equipment, whose key is still ApocryphaCivilWarChampion.)
        $entry = $reg.PSObject.Properties | Where-Object {
            $_.Name -ieq $ModName -or $_.Value.repo -ieq $ModName -or $_.Value.displayName -ieq $ModName
        } | Select-Object -First 1
        $display = if ($entry) { $entry.Value.displayName } else { $null }
        if ($display) {
            $pkgCandidates = @(Find-Packages -Root $testBuildsRoot -Game $modGame -Folders -ProjectRoot $ProjectRoot |
                Where-Object { $_.Name -like "$display *" -or $_.Name -eq $display })
            if ($pkgCandidates.Count) {
                Add-Result -Rule '-' -Check 'Display name resolution' -Status PASS `
                    -Detail "Repo '$ModName' builds no DLL; the version registry names it '$display', which matched $($pkgCandidates.Count) package(s)."
            }
        }
    }
}

# THE TEST-BUILD PICK (2026-10-13, test-build-pick.ps1 - shared with finalize-mod.ps1 and version-gate.ps1): several
# folders for one version (Simple Loadout System for Witcher 3 1.0.1: the plain folder held the old files, a
# "(inventory start-up fix)" folder the tested build) are decided by the ledger's working hash, never by name order.
$pickRefusal = $null
$pickPkg = $null
if ($Package) {
    if (Test-Path -LiteralPath $Package) {
        $pickPkg = Get-Item -LiteralPath $Package
        $pickPkg | Add-Member -NotePropertyName PkgGame -NotePropertyValue $modGame -Force
    } else { $pickRefusal = "-Package '$Package' does not exist." }
} elseif ($Version -and $gameEntries -and $gameEntries.Count -ge 1) {
    $tbp = "$(@(& py -3 $ResolverPy find test-build-pick 2>$null)[0])".Trim()
    $ledgerPath = "$(@(& py -3 $ResolverPy find version-ledger 2>$null)[0])".Trim()
    if ($tbp -and (Test-Path -LiteralPath $tbp)) {
        . $tbp
        $pickEntry = $gameEntries[0]
        $tbCands = @(Get-TestBuildCandidates -BuildsRoot $testBuildsRoot -Display "$($pickEntry.Value.displayName)" -Version $Version -Game $modGame -ProjectRoot $ProjectRoot)
        if ($tbCands.Count -gt 1 -or ($tbCands.Count -eq 1 -and $tbCands[0].Name -match '\(')) {
            $wHash = ''; $wArts = @()
            try {
                if ($ledgerPath -and (Test-Path -LiteralPath $ledgerPath)) {
                    $wRow = @((Get-Content -LiteralPath $ledgerPath -Raw | ConvertFrom-Json) | Where-Object { $_.mod -eq $pickEntry.Name -and $_.version -eq $Version } | Select-Object -First 1)
                    if ($wRow.Count) { $wHash = "$($wRow[0].sha256)"; $wArts = @(Get-RowArtifacts $wRow[0]) }   # every listed artefact (2026-10-13)
                }
            } catch { }
            $sel = Select-TestBuild -Candidates $tbCands -Hash $wHash -Foreign @(@($pickEntry.Value.foreignBinaries) | Where-Object { $_ }) -Artifacts $wArts
            if ($sel.Refused) { $pickRefusal = $sel.Message }
            else {
                $pickPkg = $sel.Pick
                $pickPkg | Add-Member -NotePropertyName PkgGame -NotePropertyValue $modGame -Force
                if ($sel.Message) { Add-Result -Rule '-' -Check 'Test-build pick' -Status PASS -Detail $sel.Message }
            }
        }
    }
}

if ($pickRefusal) {
    $pkg = $null
} elseif ($pickPkg) {
    $pkg = $pickPkg
} elseif ($Version) {
    # Never pick the sibling "- Debug Symbols X.Y.Z" package as the candidate (2026-08-29: it was
    # chosen for AMF 1.4.3, so every DLL check SKIPped and the gate looked cleaner than it was).
    # The version is not always the LAST thing in the folder name. FOMOD packages are named
    # "<Display Name> <X.Y.Z> FOMOD", so matching only on a TRAILING version reported "nothing to
    # finalize" for every FOMOD-packaged mod - which is most of them now (2026-09-10: it blocked
    # Item Explorer 1.0.4, whose package folder was present and correct the whole time). The
    # display-name code below already expected the suffix; this filter had not been updated to
    # match. Accept the version anywhere after a space, optionally followed by one more word.
    $pkg = $pkgCandidates | Where-Object { $_.Name -notlike '*Debug Symbols*' } |
           Where-Object { $_.Name -eq "$ModName $Version" -or $_.Name -match [regex]::Escape(" $Version") } |
           Select-Object -First 1
} else {
    $pkg = $pkgCandidates | Sort-Object { [version]((Get-VersionMatches $_.Name | Select-Object -First 1).Text -replace '^v', '') } -Descending | Select-Object -First 1
    if ($pkg) { $Version = (Get-VersionMatches $pkg.Name | Select-Object -First 1).Text -replace '^v', '' }
}

# The display name is the package folder name with the trailing version stripped. Everything
# downstream that looks for this mod ON DISK - the MO2 installs, the Nexus distro folder - is
# named by DISPLAY name, not by repo name, so they all need this rather than $ModName.
$displayName = $null
if ($pkg) {
    # The version is not always the LAST thing in a package name: FOMOD packages are named
    # "<Display Name> <X.Y.Z> FOMOD", so a trailing-version-only strip left the version (and the
    # word FOMOD) in the display name, and rule 29's install check then hunted for a folder called
    # "<Name> 1.0.3 FOMOD 1.0.3" and reported a correctly installed mod as not installed at all.
    # That is precisely the false alarm this gate must not produce.
    # and a test-build suffix " (inventory start-up fix)" is not part of the name either (2026-10-13)
    $displayName = ($pkg.Name -replace '\s+\d+\.\d+\.\d+(\s+\w+)?(\s+\(.*\))?\s*$', '').Trim()
}

if ($pkg) {
    Add-Result -Rule '-' -Check 'Package discovery' -Status PASS -Detail "Candidate package (about to be finalized): $($pkg.FullName)"
} elseif ($pickRefusal) {
    Add-Result -Rule '-' -Check 'Package discovery' -Status FAIL -Detail "Test-build pick refused: $pickRefusal"
    $Version = $null
} else {
    Add-Result -Rule '-' -Check 'Package discovery' -Status FAIL -Detail "No package folder found under '7. current test builds' matching '$ModName $Version' (or any version). Nothing to finalize - stop here."
    $Version = $null
}

$finalizedRoot = Join-Path $ProjectRoot '10. finalized mods'
$finalizedCandidates = Find-Packages -Root $finalizedRoot -Game $modGame -Folders -ProjectRoot $ProjectRoot |
    Where-Object { $_.Name -like "$ModName *" }
$finalized = $finalizedCandidates | Sort-Object { [version]((Get-VersionMatches $_.Name | Select-Object -First 1).Text -replace '^v', '') } -Descending | Select-Object -First 1
$finalizedVersion = if ($finalized) { (Get-VersionMatches $finalized.Name | Select-Object -First 1).Text -replace '^v', '' } else { $null }

# the package's game: its game folder (2026-10-01), else its contents - two games' mods can share a plain name
# (Apocrypha Menu Framework, 2026-09-29)
$pkgGame = ''
if ($pkg -and $pkg.PkgGame) { $pkgGame = $pkg.PkgGame }
elseif ($pkg) { try { $pkgGame = Get-PackageGame -Path $pkg.FullName } catch { } }
$nexusDir = Resolve-DistroFolder -ModName $ModName -Game $pkgGame -ProjectRoot $ProjectRoot
if ($displayName -and ($pkgGame -or -not (Test-Path -LiteralPath $nexusDir))) { $nexusDir = Resolve-DistroFolder -ModName $displayName -Game $pkgGame -ProjectRoot $ProjectRoot }  # distro folders use the DISPLAY name (e.g. "Apocrypha Menu Framework")
if (-not (Test-Path -LiteralPath $nexusDir)) { $nexusDir = $null }
# AN OPTIONAL FILE OF ANOTHER MOD'S PAGE (the owner, 2026-10-19; registry field optionalFileOf): the folder found above is
# the PARENT's. Its page, notes counter and changelog.txt belong to the parent and are judged when the parent finalizes -
# judging them against this file's version would fail every release - so the page checks below see no distro folder
# (package-gate does the same) and this file's own changelog is checked instead.
$optionalOf = $null
$optionalParentDir = $null
try { $optionalOf = Get-OptionalFileInfo -ModName $(if ($displayName) { $displayName } else { $ModName }) -ProjectRoot $ProjectRoot } catch { }
if ($optionalOf -and $nexusDir) { $optionalParentDir = $nexusDir; $nexusDir = $null }

# ===========================================================================
# GATE C - no gate re-run on the same inputs after a refusal (straight flow C, 2026-10-13)
# ===========================================================================
# The owner, 2026-10-12: "A refused gate is not run again until the work has gone back to test and fix" - the event log
# showed 159 refusal -> refusal re-runs of this gate, most under two minutes apart. The test for "went back and fixed" is
# an INPUT FINGERPRINT, not a timer: sha256 over a NAMED composition of everything this gate reads (ruled by the Fable
# Advisor Agent, 2026-10-13), each part written as "[name] <count>" and its lines:
#   package-files          every file in the candidate package: relative path, size, sha256 (sorted by path)
#   distro-text-files      every text file (no NUL byte in its first 8 KB) in the mod's 11. Nexus distro folder
#   repo-head              the repo's HEAD commit
#   repo-upstream          the upstream branch's commit (rule 9's "pushed" is fixed by a push, which moves only this)
#   git-status-porcelain   git status --porcelain=v1 --untracked-files=all (each untracked FILE listed, not its folder)
#   git-diff-head          sha256 of git diff HEAD (an edit that leaves the porcelain line identical still changes this)
#   untracked-files        sha256 of each untracked file listed, the first 200 (the cap and the total are recorded)
#   gate-rules             sha256 of gate-rules.json
#   ledger-rows            the version-ledger rows of this mod key (prunePending left out: a clean-up fixes no reason)
#   registry-row           the version-registry row of this mod key (nexusChecked left out: it changes every hour)
#   gate-scripts           sha256 of pre-finalize-check.ps1, version-gate.ps1, package-gate.ps1, test-build-pick.ps1
#   gate-helpers           sha256 of what the checks call or read by role: distro-names, check-export-parity,
#                          translation-coverage, fomod-destinations, esp-audit, swf-colour-gate, default-keys, the identity
#                          roster, and every gate-rules.json row's 'script'
#   compatibility-verdicts every "<name> - compatibility.txt" of this mod in 8. confirm compatibility (rule 15's fix)
#   gate-acknowledgements  the PROGRESS.md "## Gate acknowledgement - <display> <version>" headings (finalize-mod's rule 15
#                          path: an acknowledged FAIL must be able to run again and be recorded)
# The gate event records refs.inputs = {sha256, names, counts, untrackedCap, untrackedTotal, untrackedCapped}. Before any
# check runs, the LAST gate event of this (mod key, version) BY THE SAME CALLER is read (events.py last --caller; refs.caller
# is "finalize-mod" under -FromFinalize, else "standalone", and an event without one counts as standalone - 2026-10-22: a
# standalone check, which defers the finalize-output rows, must never block a later finalize); if it is a refusal and its
# refs.inputs.sha256 equals the current one, the gate refuses with exit 3 and records nothing - running it again would
# only repeat the same refusal. -Force -Reason "<why>" runs it anyway and writes the reason into the event's note and
# refs.override. Hosted HERE, not in version-gate.ps1 -Stage finalize: this script runs first in finalize-mod.ps1 (it
# calls the version gate), it is the one that records the gate event, and package-gate.ps1 run on its own stays a
# diagnostic that records nothing and is never refused.
$gcVersion = if ($Version) { $Version } else { $VersionArg }
$gcKey = if ($gameEntries -and @($gameEntries).Count -ge 1) { @($gameEntries)[0].Name } else { $ModName }
$gcDisplay = if ($gameEntries -and @($gameEntries).Count -ge 1 -and "$(@($gameEntries)[0].Value.displayName)") { "$(@($gameEntries)[0].Value.displayName)" } elseif ($displayName) { $displayName } else { $ModName }
$gcInputs = $null
$gcOverride = $null
function Find-RoleSoft([string]$role) {
    $p = "$(@(& py -3 $ResolverPy find $role 2>$null)[0])".Trim()
    if (-not $p -or $p -like 'MISSING*') { return '' }
    return $p
}
if ($gcVersion) {
    $gcCompat = @($gcKey, $gcDisplay, $baseName, $ModName)
    if ($gameEntries -and @($gameEntries).Count -ge 1) { $gcCompat += @(@(@($gameEntries)[0].Value.aliases) | Where-Object { $_ }) }
    $gcArgs = [ordered]@{
        package = $(if ($pkg) { $pkg.FullName } else { '' }); distro = $(if ($nexusDir) { $nexusDir } else { '' })
        repo = $(if ($RepoPath) { $RepoPath } else { '' }); gate_rules = (Find-RoleSoft 'gate-rules')
        ledger = (Find-RoleSoft 'version-ledger'); registry = $RoleRegistry; key = $gcKey; display = $gcDisplay; version = $gcVersion
        md_scripts = $ScriptsDir
        scripts = [ordered]@{ 'pre-finalize-check' = $PSCommandPath; 'version-gate' = $RoleVersionGate; 'package-gate' = $RolePackageGate; 'test-build-pick' = (Find-RoleSoft 'test-build-pick') }
        helpers = [ordered]@{ 'distro-names' = (Find-RoleSoft 'distro-names'); 'check-export-parity' = $RoleParity; 'translation-coverage' = $RoleCoverage
                              'fomod-destinations' = (Find-RoleSoft 'fomod-destinations'); 'esp-audit' = (Find-RoleSoft 'esp-audit'); 'swf-colour-gate' = (Find-RoleSoft 'swf-colour-gate')
                              'default-keys' = (Find-RoleSoft 'default-keys'); 'identity-roster' = (Join-Path (Split-Path -Parent $ResolverPy) 'rosters\identity.json') }
        compat_dir = (Join-Path $ProjectRoot '8. confirm compatibility'); compat_names = @($gcCompat | Where-Object { $_ } | Select-Object -Unique)
        progress = (Join-Path $ProjectRoot '.MD\PROGRESS.md')
    }
    $tmp = Join-Path $env:TEMP ("pfc-inputs-{0}" -f [guid]::NewGuid().ToString('N'))
    try {
        [System.IO.File]::WriteAllText("$tmp.json", ($gcArgs | ConvertTo-Json -Depth 5), (New-Object System.Text.UTF8Encoding($false)))
        [System.IO.File]::WriteAllText("$tmp.py", $GateInputsPy, (New-Object System.Text.UTF8Encoding($false)))
        $gcOut = @(& py -3 "$tmp.py" "$tmp.json" 2>&1 | ForEach-Object { "$_" })
        if ($LASTEXITCODE -eq 0) { $gcInputs = ($gcOut | Select-Object -Last 1) | ConvertFrom-Json }
        else { Write-Output ("WARNING gate C: the input fingerprint could not be computed - the gate runs without it ({0})" -f (($gcOut | Select-Object -Last 2) -join ' ')) }
    } catch { Write-Output "WARNING gate C: the input fingerprint could not be computed - the gate runs without it ($($_.Exception.Message))" }
    finally { Remove-Item -LiteralPath "$tmp.json", "$tmp.py" -Force -ErrorAction SilentlyContinue }
    if ($gcInputs) {
        $gcLast = $null
        try {
            $ll = @(& py -3 $ResolverPy run events last --kind gate --key $gcKey --version $gcVersion --caller $gcCaller 2>$null | Where-Object { "$_".Trim().StartsWith('{') })
            if ($ll.Count) { $gcLast = $ll[-1] | ConvertFrom-Json }
        } catch { $gcLast = $null }
        $gcSame = $gcLast -and "$($gcLast.outcome)" -eq 'fail' -and $gcLast.refs -and $gcLast.refs.inputs -and "$($gcLast.refs.inputs.sha256)" -eq "$($gcInputs.sha256)"
        if ($gcSame -and -not $Force) {
            $when = "$($gcLast.ts)"; try { $when = ([datetimeoffset]::Parse("$($gcLast.ts)")).LocalDateTime.ToString('yyyy-MM-dd HH:mm') } catch { }
            $rs = @(@($gcLast.reasons) | Where-Object { $_ })
            Write-Output ("REFUSED: refused {0} for {1} reasons and nothing it reads has changed since - fix the reasons, repackage or re-record, then run the gate again" -f $when, $rs.Count)
            foreach ($r in $rs) { Write-Output "  - $r" }
            Write-Output ("  (gate C: input fingerprint {0}... unchanged since event {1}; override only with -Force -Reason ""<why>"")" -f "$($gcInputs.sha256)".Substring(0, 16), $gcLast.id)
            exit 3
        }
        if ($Force) {
            $gcOverride = [ordered]@{ reason = $Reason; blocked = [bool]$gcSame; refusal = $(if ($gcSame) { "$($gcLast.id)" } else { $null }) }
            Write-Output ("OVERRIDE (gate C): -Force - the gate runs{0}. Reason: {1}" -f $(if ($gcSame) { ' although nothing it reads changed since its last refusal' } else { '' }), $Reason)
        }
    }
}

# ===========================================================================
# Rule 6 / rule 7 - version consistency, everywhere a version is written as text
# ===========================================================================

if ($Version) {

    # ---------------------------------------------------------------------------------------
    # THE VERSION GATE (2026-09-12, the owner: one file, tooling only, fails). Every version rule
    # is checked by version-gate.ps1 -Stage finalize and nowhere else: the ledger issued this
    # number and recorded it WORKING with evidence; every repo location carries it; the packaged
    # DLL carries it in its resource AND is the exact binary (hash) that was observed working; the
    # git tag exists; no tag or literal has a patch component of 10+. The old per-location checks
    # that lived here (CMakeLists / xmake / folder / DLL / README / tag) are gone - two copies of
    # one rule is how they drift.
    # ---------------------------------------------------------------------------------------
    $gateScript = $RoleVersionGate
    $gateOut = @(& $gateScript -Action gate -Mod $ModName -Version $Version -Stage finalize 2>&1 | ForEach-Object { "$_" })
    $gateExit = $LASTEXITCODE
    $gateDetail = [string]::Join("`n", $gateOut)
    if ($gateExit -eq 0) {
        Add-Result -Rule '48' -Check "version-gate.ps1 -Stage finalize clears $Version" -Status PASS -Detail $gateDetail
    } elseif ($gateExit -eq 2) {
        Add-Result -Rule '48' -Check 'version-gate.ps1: mod is registered' -Status FAIL -Detail $gateDetail
    } else {
        Add-Result -Rule '48' -Check "version-gate.ps1 -Stage finalize refused $Version" -Status FAIL -Detail $gateDetail
    }

    # ---------------------------------------------------------------------------------------
    # THE DYNAMIC PACKAGE GATE (2026-09-16, the owner: "come up with a way to dynamically add
    # logic gates to close logic loops as needed when possible instead of just adding to the
    # logic library"). gate-rules.json holds one row per class of defect that has shipped or
    # nearly shipped; package-gate.ps1 evaluates every row against THIS package, its distro
    # folder and its previous release. A new lesson becomes a new row, not just a diary entry.
    # ---------------------------------------------------------------------------------------
    $pgScript = $RolePackageGate
    $pgArgs = @{ Package = $pkg.FullName; ModName = $(if ($displayName) { $displayName } else { $ModName }); Version = $Version }
    if ($RepoPath -and (Test-Path -LiteralPath $RepoPath)) { $pgArgs['RepoPath'] = $RepoPath }   # never looked up by a name two games share
    if ($nexusDir -and (Test-Path -LiteralPath $nexusDir)) { $pgArgs['DistroDir'] = $nexusDir }
    if ($DeferRows) { $pgArgs['DeferRows'] = $DeferRows }   # finalize-mod.ps1 only: judged by its post-check after the move
    $pgOut = @(& $pgScript @pgArgs 2>&1 | ForEach-Object { "$_" })
    $pgExit = $LASTEXITCODE
    $pgDetail = [string]::Join("`n", $pgOut)
    if ($pgExit -eq 0) {
        Add-Result -Rule 'gate' -Check "package-gate.ps1: every gate-rules.json rule clear" -Status PASS -Detail $pgDetail
    } else {
        Add-Result -Rule 'gate' -Check "package-gate.ps1: a gate-rules.json rule hit" -Status FAIL -Detail $pgDetail
    }
    # rule 7: the DLL filename itself carries no version (a naming check, not a number check)
    # the DLL wherever the game keeps plugins (SKSE\Plugins, or OblivionRemastered\Binaries\Win64\OBSE\Plugins - 2026-09-26)
    $dll = Get-ChildItem -LiteralPath $pkg.FullName -Filter '*.dll' -File -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($dll) {
        if ($dll.Name -match '\d+\.\d+\.\d+') {
            Add-Result -Rule '7' -Check 'DLL filename carries no version' -Status FAIL -Detail "DLL is named '$($dll.Name)' - the filename must stay constant across versions (rule 7); the version belongs in the file-version resource, not the name."
        } else {
            Add-Result -Rule '7' -Check 'DLL filename carries no version' -Status PASS -Detail $dll.Name
        }
    }

    if ($nexusDir) {
        # nexus-page.txt Source-section package reference
        $nexusPageFile = Join-Path $nexusDir 'nexus-page.txt'
        if (Test-Path -LiteralPath $nexusPageFile) {
            $nexusPageText = Get-Content -LiteralPath $nexusPageFile -Raw
            $spm = [regex]::Match($nexusPageText, 'This package is\s+v?(\d+\.\d+\.\d+)')
            if ($spm.Success) {
                $refVer = $spm.Groups[1].Value
                # Compare to the FINALIZED version, not the new candidate: rule 10 updates this
                # text as part of the finalize step itself, so lagging the candidate by one
                # step is expected right up until this finalize completes. It should already
                # match whatever is currently in "10. finalized mods", though.
                if ($finalizedVersion -and -not (VerEq $refVer $finalizedVersion)) {
                    Add-Result -Rule '10' -Check 'nexus-page.txt Source reference matches currently-finalized version' -Status WARN `
                        -Detail "nexus-page.txt says v$refVer, but '10. finalized mods' currently holds v$finalizedVersion (and this check's candidate is v$Version). Stale Nexus material - update as part of this finalize (rule 10), not a version-numbering bug by itself."
                } elseif (-not (VerEq $refVer $Version)) {
                    Add-Result -Rule '10' -Check 'nexus-page.txt Source reference' -Status WARN `
                        -Detail "nexus-page.txt references v$refVer; will need updating to v$Version once this candidate finalizes (rule 10)."
                } else {
                    Add-Result -Rule '10' -Check 'nexus-page.txt Source reference' -Status PASS -Detail "v$refVer"
                }
            } else {
                Add-Result -Rule '10' -Check 'nexus-page.txt Source reference' -Status SKIP -Detail "Could not find a 'This package is vX.Y.Z' line."
            }
        } else {
            Add-Result -Rule '10' -Check 'nexus-page.txt Source reference' -Status SKIP -Detail 'No nexus-page.txt found.'
        }

        # changelog.txt - the newest version heading is
        # compared informationally against the finalized/candidate version.
        $changelogFile = Join-Path $nexusDir 'changelog.txt'
        if (Test-Path -LiteralPath $changelogFile) {
            $changelogText = Get-Content -LiteralPath $changelogFile -Raw
            $headings = @([regex]::Matches($changelogText, '(?m)^(\d+\.\d+\.\d+)\s*$') | ForEach-Object { $_.Groups[1].Value })
            if ($headings.Count -gt 0) {
                $newestHeading = ($headings | Sort-Object { [version]$_ } -Descending)[0]
                $compareAgainst = if ($finalizedVersion) { $finalizedVersion } else { $Version }
                if (-not (VerEq $newestHeading $compareAgainst)) {
                    Add-Result -Rule '10' -Check 'changelog.txt has an entry for the current version' -Status WARN `
                        -Detail "Newest changelog.txt entry is $newestHeading; currently-finalized/candidate version is $compareAgainst. Needs a new entry (rule 10) - not itself a version-numbering bug."
                } else {
                    Add-Result -Rule '10' -Check 'changelog.txt has an entry for the current version' -Status PASS -Detail "$newestHeading"
                }
            } else {
                Add-Result -Rule '10' -Check 'changelog.txt version headings' -Status SKIP -Detail 'No X.Y.Z-shaped headings found.'
            }
        } else {
            Add-Result -Rule '10' -Check 'changelog.txt' -Status SKIP -Detail 'No changelog.txt found (fine if this mod has never been updated after its first Nexus material).'
        }
    } elseif ($optionalParentDir) {
        # the file's own changelog, beside the parent page's: the newest heading must be this version (rule 10: one changelog per download)
        $ocFile = Join-Path $optionalParentDir $optionalOf.changelog
        if (Test-Path -LiteralPath $ocFile) {
            $ocHeads = @([regex]::Matches((Get-Content -LiteralPath $ocFile -Raw), '(?m)^(?:Version\s+)?(\d+\.\d+\.\d+)\s*$') | ForEach-Object { $_.Groups[1].Value })
            if ($ocHeads.Count -gt 0 -and -not (VerEq (($ocHeads | Sort-Object { [version]$_ } -Descending)[0]) $Version)) {
                Add-Result -Rule '10' -Check "$($optionalOf.changelog) has an entry for the current version" -Status FAIL -Detail "Newest entry is $(($ocHeads | Sort-Object { [version]$_ } -Descending)[0]); this candidate is v$Version. Write the entry (the file is this add-on's own changelog on '$($optionalOf.parent)''s page)."
            } elseif ($ocHeads.Count -gt 0) {
                Add-Result -Rule '10' -Check "$($optionalOf.changelog) has an entry for the current version" -Status PASS -Detail "$Version (optional file of '$($optionalOf.parent)': the page, banner and notes are the parent's)"
            } else {
                Add-Result -Rule '10' -Check "$($optionalOf.changelog) version headings" -Status FAIL -Detail 'No X.Y.Z-shaped heading found.'
            }
        } else {
            Add-Result -Rule '10' -Check "$($optionalOf.changelog)" -Status FAIL -Detail "No $($optionalOf.changelog) in '$(Split-Path $optionalParentDir -Leaf)' - an optional file needs its own changelog on the parent's page."
        }
    } else {
        Add-Result -Rule '10' -Check 'Nexus distro folder exists' -Status WARN `
            -Detail "No '11. Nexus distro\$ModName' folder found at all - this looks like a first finalize. Not itself a finalize blocker (the functional-in-game gate is what matters, rule 21), but per rule 10/21 this needs a real content-writing pass (Description/Main features/Installation/Requirements/Credit, following '_nexus-page-template.txt') before this mod is actually Nexus-ready - not something sync-nexus-distro.ps1 (run inside finalize-mod.ps1) can invent on its own. See sync-nexus-distro.ps1's own NEEDS-CONTENT-PASS flag."
    }

} else {
    Add-Result -Rule '6/7' -Check 'Version consistency' -Status SKIP -Detail 'No candidate package version resolved - see Package discovery above.'
}

# ===========================================================================
# Rule 9 - git status clean at HEAD
# ===========================================================================

if ($RepoPath -and (Test-Path -LiteralPath (Join-Path $RepoPath '.git'))) {
    Push-Location $RepoPath
    try {
        $dirty = git status --porcelain 2>$null
        if ([string]::IsNullOrWhiteSpace($dirty)) {
            Add-Result -Rule '9' -Check 'Git working tree clean at HEAD' -Status PASS -Detail 'Nothing uncommitted.'
        } else {
            $lines = ($dirty -split "`n") | Select-Object -First 10
            Add-Result -Rule '9' -Check 'Git working tree clean at HEAD' -Status FAIL -Detail "Uncommitted changes present:`n$([string]::Join("`n", $lines))"
        }
        $head = git rev-parse --short HEAD 2>$null
        $unpushed = git log '@{u}..HEAD' --oneline 2>$null
        if ($LASTEXITCODE -eq 0 -and $unpushed -and (Test-Path -LiteralPath (Join-Path $ScriptsDir 'github-pushes-paused.txt'))) {
            # the owner, 2026-10-06: no pushes until he deletes the old repos (github-pushes-paused.txt)
            Add-Result -Rule '9' -Check 'No unpushed commits' -Status WARN -Detail "GitHub pushes are paused (github-pushes-paused.txt); waiting to push:`n$unpushed"
        } elseif ($LASTEXITCODE -eq 0 -and $unpushed) {
            Add-Result -Rule '9' -Check 'No unpushed commits' -Status FAIL -Detail "Commits ahead of the tracked remote branch:`n$unpushed"
        } elseif ($LASTEXITCODE -eq 0) {
            Add-Result -Rule '9' -Check 'No unpushed commits' -Status PASS -Detail "HEAD ($head) matches the tracked remote branch."
        } else {
            Add-Result -Rule '9' -Check 'No unpushed commits' -Status SKIP -Detail 'No upstream tracking branch configured for HEAD.'
        }
        # A SHALLOW repo cannot be pushed complete (2026-09-26, AMF for Oblivion Remastered: started from a depth-limited
        # template clone, the first push was refused with "remote unpack failed ... did not receive expected object").
        # Rule 3 asks for the real upstream history before a push; this is where that is checked mechanically.
        $shallow = (git rev-parse --is-shallow-repository 2>$null)
        if ("$shallow".Trim() -eq 'true') {
            Add-Result -Rule '3' -Check 'Repo is not shallow (repo-is-not-shallow)' -Status FAIL -Detail 'The repository is a shallow clone: its history bottoms out in a graft and a push is refused by the server. Fetch the full history of the template remote and push again.'
        } else {
            Add-Result -Rule '3' -Check 'Repo is not shallow (repo-is-not-shallow)' -Status PASS -Detail 'Full history present.'
        }
    } finally { Pop-Location }
} else {
    Add-Result -Rule '9' -Check 'Git working tree clean at HEAD' -Status SKIP -Detail 'No repo resolved.'
}

# ===========================================================================
# Rule 3 - public GitHub remote
# ===========================================================================

if ($RepoPath -and (Test-Path -LiteralPath (Join-Path $RepoPath '.git'))) {
    Push-Location $RepoPath
    try {
        # kit: whether the remote is public is not asked of any server here (OPTIONAL-SCRIPTS.md)
        Add-Result -Rule '3' -Check 'Public GitHub remote configured' -Status SKIP -Detail 'This kit reads no remote: check the repository is public yourself.'
    } finally { Pop-Location }
} else {
    Add-Result -Rule '3' -Check 'Public GitHub remote configured' -Status SKIP -Detail 'No repo resolved.'
}

# ===========================================================================
# Rule 16 - compiled defaults match the shipped INI
# ===========================================================================

function Get-CppDefaults {
    param([string]$SettingsHeaderPath)
    $result = @{}
    if (-not (Test-Path -LiteralPath $SettingsHeaderPath)) { return $result }
    $text = Get-Content -LiteralPath $SettingsHeaderPath -Raw
    # Matches: inline [constexpr] <type> <name> = <value>;  (single-line declarations only -
    # arrays/std::array defaults are intentionally skipped, see rule 16's per-corner offsets).
    $pattern = 'inline\s+(?:constexpr\s+)?(?!std::array)([\w:<>, ]+?)\s+(\w+)\s*=\s*([^;{]+);'
    foreach ($m in [regex]::Matches($text, $pattern)) {
        $name = $m.Groups[2].Value
        if ($name -match '^k[A-Z]') { continue } # kFooBar-style constants, not settings
        $result[$name] = $m.Groups[3].Value.Trim()
    }
    return $result
}

function Get-IniValues {
    param([string]$IniPath)
    $result = @{}
    if (-not (Test-Path -LiteralPath $IniPath)) { return $result }
    foreach ($line in Get-Content -LiteralPath $IniPath) {
        $m = [regex]::Match($line, '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*(;.*)?$')
        if ($m.Success -and $line -notmatch '^\s*;') { $result[$m.Groups[1].Value] = $m.Groups[2].Value }
    }
    return $result
}

function Compare-DefaultValue {
    # Returns 'EQUAL', 'DIFFERENT', or 'UNCOMPARABLE'.
    param([string]$CppValue, [string]$IniValue)
    $cpp = $CppValue.Trim()
    $ini = $IniValue.Trim()

    # Booleans, normalised on BOTH sides. An INI may spell them 1/0, true/false or yes/no - this
    # project's own INISettingCollection parser accepts all three - so comparing the compiled value
    # against one hard-coded spelling reports a mismatch between two values that are equal.
    # Local Map Item Markers 1.0.0 tripped exactly that: bShowWeapons=true against a compiled
    # true, reported as "INI 'bShowWeapons'=true vs compiled 'showWeapons'=true".
    $boolWords = @{ 'true' = '1'; 'yes' = '1'; '1' = '1'; 'false' = '0'; 'no' = '0'; '0' = '0' }
    if ($cpp -match '^(true|false)$') {
        $cppBool = $boolWords[$cpp.ToLower()]
        $iniBool = $boolWords[$ini.ToLower()]
        if ($null -eq $iniBool) { return 'UNCOMPARABLE' }
        return $(if ($cppBool -eq $iniBool) { 'EQUAL' } else { 'DIFFERENT' })
    }

    $cppNum = $cpp -replace '[Ff]$', ''
    if ($cppNum -match '^0[xX][0-9A-Fa-f]+$') { $cppNum = [Convert]::ToInt64($cppNum, 16) }
    $iniNum = $ini -replace '[Ff]$', ''
    if ($iniNum -match '^0[xX][0-9A-Fa-f]+$') { $iniNum = [Convert]::ToInt64($iniNum, 16) }

    $cd = 0.0; $id = 0.0
    if ([double]::TryParse("$cppNum", [ref]$cd) -and [double]::TryParse("$iniNum", [ref]$id)) {
        return $(if ([Math]::Abs($cd - $id) -lt 0.0001) { 'EQUAL' } else { 'DIFFERENT' })
    }

    return 'UNCOMPARABLE'
}

if ($RepoPath) {
    $settingsHeader = Get-ChildItem -Path $RepoPath -Recurse -Filter 'Settings.h' -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch '\\build\\' } | Select-Object -First 1
    $shippedIni = if ($pkg) { Get-ChildItem -Path $pkg.FullName -Filter '*.ini' -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne 'meta.ini' -and $_.Directory.Name -eq 'Plugins' } | Select-Object -First 1 }

    if ($settingsHeader -and $shippedIni) {
        $cppDefaults = Get-CppDefaults $settingsHeader.FullName
        $iniValues = Get-IniValues $shippedIni.FullName

        $equal = 0; $different = @(); $uncomparable = @(); $unmatched = @()

        foreach ($iniKey in $iniValues.Keys) {
            $stripped = if ($iniKey -match '^[iufbs](.+)$') { $Matches[1] } else { $iniKey }
            $normStripped = Normalize-Name $stripped
            $cppVar = $cppDefaults.Keys | Where-Object { (Normalize-Name $_) -eq $normStripped } | Select-Object -First 1
            if (-not $cppVar) { $unmatched += $iniKey; continue }
            $cmp = Compare-DefaultValue -CppValue $cppDefaults[$cppVar] -IniValue $iniValues[$iniKey]
            switch ($cmp) {
                'EQUAL' { $equal++ }
                'DIFFERENT' { $different += "INI '$iniKey'=$($iniValues[$iniKey]) vs compiled '$cppVar'=$($cppDefaults[$cppVar])" }
                'UNCOMPARABLE' { $uncomparable += "INI '$iniKey'=$($iniValues[$iniKey]) vs compiled '$cppVar'=$($cppDefaults[$cppVar]) (non-numeric/non-bool expression, could not evaluate)" }
            }
        }

        if ($different.Count -gt 0) {
            Add-Result -Rule '16' -Check 'Compiled defaults match shipped INI' -Status FAIL `
                -Detail "$($different.Count) mismatch(es) out of $($iniValues.Count) INI key(s) checked:`n$([string]::Join("`n", $different))"
        } else {
            Add-Result -Rule '16' -Check 'Compiled defaults match shipped INI' -Status PASS `
                -Detail "$equal key(s) matched, $($uncomparable.Count) skipped as non-comparable, $($unmatched.Count) INI key(s) had no obviously-matching compiled default (array/indexed settings and similar are expected here - not itself a failure)."
        }
        if ($uncomparable.Count -gt 0) {
            Add-Result -Rule '16' -Check 'Compiled-default keys skipped (could not evaluate)' -Status SKIP -Detail ([string]::Join("`n", $uncomparable))
        }

        # Rule 16 gotcha: WritePrivateProfileString/GetPrivateProfileString must never be used
        # for a plugin's own INI (usvfs does not reliably redirect them).
        $srcFiles = Get-ChildItem -Path $RepoPath -Recurse -Include '*.cpp', '*.h' -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -notmatch '\\build\\' -and $_.FullName -notmatch '\\extern\\' -and $_.FullName -notmatch '\\deps\\' -and $_.FullName -notmatch '\\lib\\commonlibsse' }
        $badApiHits = @()
        foreach ($f in $srcFiles) {
            $m = Select-String -LiteralPath $f.FullName -Pattern '(WritePrivateProfileString|GetPrivateProfileString)\s*\(' -ErrorAction SilentlyContinue
            foreach ($hit in $m) {
                # Skip a real call site that's only being named inside a // line comment (e.g.
                # the gotcha explaining why plain file I/O is used instead).
                $beforeMatch = $hit.Line.Substring(0, $hit.Matches[0].Index)
                if ($beforeMatch -notmatch '//') { $badApiHits += "$($f.Name):$($hit.LineNumber)" }
            }
        }
        if ($badApiHits.Count -gt 0) {
            Add-Result -Rule '16' -Check 'No WritePrivateProfileString/GetPrivateProfileString usage' -Status FAIL `
                -Detail "usvfs does not reliably redirect these Win32 profile APIs (rule 16). Found at: $([string]::Join(', ', $badApiHits))"
        } else {
            Add-Result -Rule '16' -Check 'No WritePrivateProfileString/GetPrivateProfileString usage' -Status PASS -Detail 'Not used anywhere in source.'
        }
    } else {
        Add-Result -Rule '16' -Check 'Compiled defaults match shipped INI' -Status SKIP `
            -Detail "Could not locate both a Settings.h ($([bool]$settingsHeader)) and a shipped .ini ($([bool]$shippedIni)) to diff."
    }
} else {
    Add-Result -Rule '16' -Check 'Compiled defaults match shipped INI' -Status SKIP -Detail 'No repo resolved.'
}

# ===========================================================================
# Rule 28 - default keys come from the issued-keys register (DEFAULT-KEYS.md), unique per game
# ===========================================================================
# Rewritten 2026-10-12 (the owner, on the simplification review's gate defects: "do what you suggest"). The check
# had tested the rule's ORIGINAL form (every key on K / L) after the 2026-09-12 amendment moved defaults to the
# register: it failed a mod that correctly took an issued key other than K/L, and it never saw two of our mods
# shipping the same key in one game - the defect a player actually feels. Now: a default may not be a reserved key
# (Skyrim), may not be a key the register issues to ANOTHER mod of the same game, and two defaults of one mod may not
# share a key. A mod with no row in the register is a WARN (issue its keys there).

function ConvertTo-KeyName([string]$s) {
    $s = ($s -replace '\*\*', '' -replace '\([^)]*\)', '' -replace '~~[^~]*~~', '' -replace ' - (Oblivion Remastered|Witcher 3|Skyrim)\b', '')
    return ($s.ToLowerInvariant() -replace '[^a-z0-9]', '')
}
if ($RepoPath) {
    $settingsHeader = Get-ChildItem -Path $RepoPath -Recurse -Filter 'Settings.h' -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch '\\build\\' } | Select-Object -First 1
    if ($settingsHeader) {
        $text = Get-Content -LiteralPath $settingsHeader.FullName -Raw
        $keyVars = [regex]::Matches($text, 'inline\s+std::int32_t\s+(\w*[Kk]ey[Cc]ode\w*)\s*=\s*(0[xX][0-9A-Fa-f]+|\d+)\s*;')
        if ($keyVars.Count -eq 0) {
            Add-Result -Rule '28' -Check 'Default keys from DEFAULT-KEYS.md' -Status SKIP -Detail 'No *KeyCode-shaped setting found in Settings.h - this mod appears to have no bindable-key setting (rule 28 does not apply).'
        } else {
            $register = @()
            try {
                $regText = Get-Content -LiteralPath (Find-Role 'default-keys') -Raw -Encoding UTF8
                $section = ''
                foreach ($line in ($regText -split "`r?`n")) {
                    if ($line -match '^## (.+)$') { $section = $Matches[1]; continue }
                    if ($line -notmatch '^\| ' -or $line -match '^\|\s*-' -or $line -match 'RETIRED' -or $line -match '^\| (Key|Button) \|') { continue }
                    $cells = @($line.Trim('|').Split('|') | ForEach-Object { $_.Trim() })
                    $code = [regex]::Match($cells[0], '\((\d+)')
                    if (-not $code.Success) { continue }
                    $owner = ($(if ($section -like 'Reserved*') { 'RESERVED: ' + $cells[1] } else { $cells[1] })) -replace '\*\*', ''
                    $g = if ($owner -match 'Oblivion') { 'Oblivion Remastered' } elseif ($owner -match 'Witcher') { 'Witcher 3' } else { 'Skyrim' }
                    if ($section -like 'Issued - keyboard*' -or $section -like 'Reserved*') {
                        $register += [pscustomobject]@{ Code = [int]$code.Groups[1].Value; Owner = $owner; Norm = (ConvertTo-KeyName $owner); Game = $g; Reserved = ($section -like 'Reserved*') }
                    }
                }
            } catch { }
            $myNames = @($ModName)
            if ($gameEntries -and $gameEntries.Count -ge 1) { $myNames += @($gameEntries[0].Name, $gameEntries[0].Value.repo, $gameEntries[0].Value.displayName) + @($gameEntries[0].Value.aliases) }
            $myNorms = @($myNames | Where-Object { $_ } | ForEach-Object { ConvertTo-KeyName $_ } | Where-Object { $_ } | Sort-Object -Unique)
            $myGame = if ($modGame) { $modGame } else { 'Skyrim' }
            function Test-Mine($norm) { foreach ($n in $myNorms) { if ($norm -eq $n -or $norm.Contains($n) -or $n.Contains($norm)) { return $true } }; return $false }
            $bad = @(); $seen = @{}; $listed = $false
            foreach ($kv in $keyVars) {
                $name = $kv.Groups[1].Value; $rawv = $kv.Groups[2].Value
                $val = if ($rawv -match '^0[xX]') { [Convert]::ToInt32($rawv, 16) } else { [int]$rawv }
                if ($val -eq 0) { continue }   # ships unbound: rebindable on the page, nothing to collide with
                if ($seen.ContainsKey($val)) { $bad += "$name and $($seen[$val]) share $rawv (one key, one action)" } else { $seen[$val] = $name }
                foreach ($row in @($register | Where-Object { $_.Code -eq $val -and $_.Game -eq $myGame })) {
                    if ($row.Reserved) { $bad += "$name = $rawv is reserved ($($row.Owner))"; continue }
                    if (Test-Mine $row.Norm) { $listed = $true } else { $bad += "$name = $rawv is issued to $($row.Owner) in $myGame" }
                }
            }
            if (-not $listed -and @($register | Where-Object { -not $_.Reserved -and (Test-Mine $_.Norm) }).Count -gt 0) { $listed = $true }
            $summary = [string]::Join(', ', ($keyVars | ForEach-Object { "$($_.Groups[1].Value)=$($_.Groups[2].Value)" }))
            if ($register.Count -eq 0) {
                Add-Result -Rule '28' -Check 'Default keys from DEFAULT-KEYS.md' -Status SKIP -Detail 'DEFAULT-KEYS.md (role default-keys) could not be read - a gap, not a pass.'
            } elseif ($bad.Count -gt 0) {
                Add-Result -Rule '28' -Check 'Default keys from DEFAULT-KEYS.md' -Status FAIL -Detail "$([string]::Join('; ', $bad)). Rule 28: take an unissued key from DEFAULT-KEYS.md, add its row, then ship it."
            } elseif (-not $listed -and $seen.Count -gt 0) {
                Add-Result -Rule '28' -Check 'Default keys from DEFAULT-KEYS.md' -Status WARN -Detail "No collision, but $ModName has no row in DEFAULT-KEYS.md for $summary - add the rows so the next mod cannot take these keys."
            } else {
                Add-Result -Rule '28' -Check 'Default keys from DEFAULT-KEYS.md' -Status PASS -Detail "$($keyVars.Count) default(s) checked against DEFAULT-KEYS.md ($myGame): $summary"
            }
        }
    } else {
        Add-Result -Rule '28' -Check 'Default keys from DEFAULT-KEYS.md' -Status SKIP -Detail 'No Settings.h found.'
    }
} else {
    Add-Result -Rule '28' -Check 'Default keys from DEFAULT-KEYS.md' -Status SKIP -Detail 'No repo resolved.'
}

# ===========================================================================
# ===========================================================================
# Info-by-default - every mod ships uLogLevel=2 in its INI
# ===========================================================================
#
# Added 2026-08-26 (as trace-by-default) after an audit found three mods shipping with no uLogLevel key at all
# (Remember Lockpick Angle, Sure of Stealing, Wait Your Turn Redux). They inherited a different
# logging mechanism from upstream and the rule had only ever been applied to the mods built on
# this project's own spdlog/INISettingCollection pattern.
#
# CHANGED 2026-09-26: the default is INFO, not trace. The owner: "ship all innies from now on at default of
# info". A player or tester who needs more raises uLogLevel in the INI; the key must still exist and be wired to
# the mod's logger, so that is still checked.
#
# A package with no DLL is an asset-only reskin and legitimately has no INI; that is a SKIP, not
# a failure.

$pkgDlls = @(Get-ChildItem -LiteralPath $pkg.FullName -Recurse -Filter '*.dll' -ErrorAction SilentlyContinue)
$pkgInis = @(Get-ChildItem -LiteralPath $pkg.FullName -Recurse -Filter '*.ini' -ErrorAction SilentlyContinue |
             Where-Object { $_.Name -ne 'meta.ini' })

if ($pkgDlls.Count -eq 0) {
    Add-Result -Rule '-' -Check 'Ships at info (uLogLevel=2)' -Status SKIP `
        -Detail 'Asset-only package (no DLL), so it has no plugin INI and no log level. Not applicable.'
} elseif ($pkgInis.Count -eq 0) {
    Add-Result -Rule '-' -Check 'Ships at info (uLogLevel=2)' -Status FAIL `
        -Detail 'Package contains a DLL but no INI at all, so uLogLevel cannot be set. Every mod here ships info-by-default with a uLogLevel key a reporter can raise.'
} else {
    $found = $false
    $bad = @()
    foreach ($ini in $pkgInis) {
        $m = Select-String -LiteralPath $ini.FullName -Pattern '^\s*uLogLevel\s*=\s*(\d+)' -ErrorAction SilentlyContinue |
             Select-Object -First 1
        if ($m) {
            $found = $true
            $lvl = [int]$m.Matches[0].Groups[1].Value
            if ($lvl -ne 2) { $bad += "$($ini.Name) has uLogLevel=$lvl" }
            continue
        }
        # A fork of one of Seb263's mods (Localized Damage, 2026-09-24) keeps the upstream logger control, iVerboseMode:
        # 0 errors, 1 info, 2 trace. Its info level is 1.
        $v = Select-String -LiteralPath $ini.FullName -Pattern '^\s*iVerboseMode\s*=\s*(\d+)' -ErrorAction SilentlyContinue |
             Select-Object -First 1
        if ($v) {
            $found = $true
            $lvl = [int]$v.Matches[0].Groups[1].Value
            if ($lvl -ne 1) { $bad += "$($ini.Name) has iVerboseMode=$lvl (its info level is 1)" }
            continue
        }
        # Added 2026-10-23 (Main Agent, World Map Selector for Controller 1.0.0, option B): a fork that keeps its
        # upstream's TEXT log key - [General] LogLevel=Trace|Debug|Info|Warn|Err|Critical|Off, read by the mod's
        # Config.cpp and applied to its spdlog logger - honours info-by-default when the shipped value is Info.
        # Renaming it to uLogLevel would break the upstream INI players already have. Its compiled default must
        # still be info (rule 16); that is checked in the source, not here.
        $t = Select-String -LiteralPath $ini.FullName -Pattern '^\s*LogLevel\s*=\s*([A-Za-z]+)' -ErrorAction SilentlyContinue |
             Select-Object -First 1
        if ($t) {
            $found = $true
            $val = $t.Matches[0].Groups[1].Value
            if ($val -ine 'Info') { $bad += "$($ini.Name) has LogLevel=$val (ship LogLevel=Info)" }
        }
    }

    if (-not $found) {
        Add-Result -Rule '-' -Check 'Ships at info (uLogLevel=2)' -Status FAIL `
            -Detail "No uLogLevel key in any shipped INI ($(($pkgInis | ForEach-Object { $_.Name }) -join ', ')). This mod does not honour the info-by-default rule - it needs a real uLogLevel wired to its own logger, not just a key added to the INI."
    } elseif ($bad.Count -gt 0) {
        Add-Result -Rule '-' -Check 'Ships at info (uLogLevel=2)' -Status FAIL `
            -Detail "Shipped INI does not default to info: $($bad -join '; '). Ship 2."
    } else {
        Add-Result -Rule '-' -Check 'Ships at info (uLogLevel=2)' -Status PASS `
            -Detail 'Shipped INI defaults to uLogLevel=2 (info).'
    }
}

########################################################################################
## SMF EXPORT PARITY - only meaningful for the menu framework itself
##
## A mod written for SKSE Menu Framework resolves every drawing function it uses by NAME at
## runtime. A name the framework does not export comes back null, and the consumer page
## registers, appears in the list, then draws nothing - no error, no log line, nothing in a
## crash report. It is invisible from our side, which is why it was found by a user in
## Sep 2026 rather than by us, after three rounds of adding names by scanning whichever
## consumers happened to be installed. So it is checked mechanically now.
########################################################################################
$amfDll = $pkgDlls | Where-Object { $_.Name -like '*ApocryphaMenuFramework.dll' } | Select-Object -First 1
if (-not $amfDll) {
    Add-Result -Rule '-' -Check 'SMF export parity' -Status SKIP `
        -Detail 'Not the menu framework - this check applies only to the DLL that stands in for SKSE Menu Framework.'
} else {
    $parityScript = $RoleParity
    if (-not (Test-Path -LiteralPath $parityScript)) {
        Add-Result -Rule '-' -Check 'SMF export parity' -Status SKIP -Detail 'check-export-parity.py not found beside this script.'
    } else {
        $out = & python $parityScript $amfDll.FullName 2>&1
        $rc = $LASTEXITCODE
        $summary = ($out | Where-Object { $_ -match '^(PASS|FAIL|SKIP)' } | Select-Object -First 1)
        if ($rc -eq 0) {
            Add-Result -Rule '-' -Check 'SMF export parity' -Status PASS -Detail "$summary"
        } elseif ($rc -eq 2) {
            Add-Result -Rule '-' -Check 'SMF export parity' -Status SKIP `
                -Detail 'No real SKSEMenuFramework.dll on this machine to compare against.'
        } else {
            Add-Result -Rule '-' -Check 'SMF export parity' -Status FAIL `
                -Detail "$summary Any consumer calling a missing name gets a null back and that part of its page draws nothing, silently. Run check-export-parity.py for the list."
        }
    }
}

# ===========================================================================
# Rule 32 - boolean settings render as a toggle switch: enforced by gate row checkbox-is-a-toggle
# ===========================================================================
# 2026-10-12 (the owner: "enforce the no checkbox rule regardless of game"): this file's own check saw only
# ImGuiMCP::Checkbox( and ran only at finalize. The gate row checkbox-is-a-toggle (role gate-rules) matches
# ImGui::Checkbox( and ImGuiMCP::Checkbox( in every game's sources and runs at every package AND here, through the
# package gate below - one implementation (logic 4 of LOGIC-LIBRARY.md), so this copy was removed rather than widened.

# ===========================================================================
# Translations - every string the code asks for actually reached the files
# ===========================================================================
# A missing translation key is SILENT: TR("KEY", "English") falls back to the compiled English, so
# a string added after a language rollout draws English in all eleven languages and nothing reports
# it. Apocrypha Menu Framework 1.6.6 shipped a search box whose two strings never reached a single
# file and it went unnoticed for two versions. The logic lives in translation-coverage.py so there
# is one implementation of it; this just asks that script about the mod being finalized.

if ($RepoPath) {
    $covScript = $RoleCoverage
    $py = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $py) {
        Add-Result -Rule '-' -Check 'Translation coverage' -Status SKIP -Detail 'python is not on PATH, so translation-coverage.py could not be run.'
    } elseif (-not (Test-Path -LiteralPath $covScript)) {
        Add-Result -Rule '-' -Check 'Translation coverage' -Status SKIP -Detail "translation-coverage.py not found beside this script."
    } else {
        $repoLeaf = Split-Path -Leaf $RepoPath
        $covOut = & $py $covScript --repo $repoLeaf 2>&1 | Out-String
        if ($LASTEXITCODE -eq 0) {
            if ($covOut -match 'nothing to check') {
                Add-Result -Rule '-' -Check 'Translation coverage' -Status SKIP -Detail "$repoLeaf draws no translated text."
            } else {
                Add-Result -Rule '-' -Check 'Translation coverage' -Status PASS -Detail 'Every key the code asks for is in english, and all ten other languages match english key-for-key.'
            }
        } else {
            Add-Result -Rule '-' -Check 'Translation coverage' -Status FAIL `
                -Detail "Strings are missing from the shipped translation files - they will draw English in every language. Run 'python .MD\scripts\translation-coverage.py --repo $repoLeaf' for the list.`n$($covOut.Trim())"
        }
    }
} else {
    Add-Result -Rule '-' -Check 'Translation coverage' -Status SKIP -Detail 'No repo resolved.'
}

# ===========================================================================
# Rule 15 - a compatibility verdict exists for this project's own build
# ===========================================================================

$compatDir = Join-Path $ProjectRoot '8. confirm compatibility'
# game-qualified names first (a plain name can belong to two games' mods - 2026-09-29), then the registry's aliases
$compatNames = @()
if ($pkgGame -and $displayName) { $compatNames += "$displayName for $pkgGame"; $compatNames += "$pkgGame - $displayName" }
try {
    $regC = Get-Content -LiteralPath $RoleRegistry -Raw | ConvertFrom-Json
    foreach ($prop in $regC.PSObject.Properties) { if ($prop.Name -ieq $ModName -or ($RepoPath -and $prop.Value.repo -ieq (Split-Path $RepoPath -Leaf))) { foreach ($a in @($prop.Value.aliases)) { if ($a) { $compatNames += $a } } } }
} catch { }
$compatNames += $ModName
if ($displayName) { $compatNames += $displayName }
$compatNames += $baseName
$compatCandidates = @($compatNames | ForEach-Object { "$_ - compatibility.txt" }) | Select-Object -Unique
$found = $null
foreach ($c in $compatCandidates) {
    $p = Join-Path $compatDir $c
    if (Test-Path -LiteralPath $p) { $found = $p; break }
}
if ($found) {
    $verdictText = Get-Content -LiteralPath $found -Raw
    Add-Result -Rule '15' -Check 'Compatibility verdict recorded' -Status PASS -Detail "Found $found. First ~200 chars: $($verdictText.Substring(0, [Math]::Min(200, $verdictText.Length)) -replace '\s+', ' ')"
} else {
    Add-Result -Rule '15' -Check 'Compatibility verdict recorded' -Status FAIL `
        -Detail "No '<name> - compatibility.txt' found in '8. confirm compatibility' for this mod (looked for: $([string]::Join(', ', $compatCandidates))). Rule 15/21: this project's own builds go through '8. confirm compatibility' as a MANDATORY stop before finalizing - this is not the conditional third-party-mod case, it always applies to a project build."
}

# ===========================================================================
# Rule 29 - installed into both MO2 instances at the version being finalized
# ===========================================================================

$instGame = if ($pkgGame) { $pkgGame } else { $modGame }
$r29 = Get-Rule29Instances -RegistryPath $RoleRegistry -ModName $ModName -DisplayName $displayName -InstGame $instGame -ProjectRoot $ProjectRoot
$mo2Instances = @($r29.Instances)
$installPrefix = $r29.InstallPrefix
if ($Version) {
    foreach ($inst in $mo2Instances) {
        if (-not (Test-Path -LiteralPath $inst.Path)) {
            Add-Result -Rule '29' -Check "Installed in $($inst.Name)" -Status SKIP -Detail "Instance folder not found at $($inst.Path) (this machine may not have it, or it's misnamed)."
            continue
        }
        # Installed folders carry the DISPLAY name ("Dragon's Eye Minimap 1.5.7"),
        # not the repo name. Checking only $ModName reported "not installed at all" for a mod that
        # was installed and enabled, which is exactly the kind of false alarm that teaches people
        # to ignore a gate.
        $names = @($ModName)
        if ($displayName) { $names += $displayName }
        # 2026-09-17: a renamed mod (Wheeler - Refined -> Perfected Wheeler - Apocrypha Menu Framework) is still
        # installed under its old name until the next install; the registry's aliases carry the old names.
        try {
            $regPath = $RoleRegistry
            if (Test-Path -LiteralPath $regPath) {
                $reg = Get-Content -LiteralPath $regPath -Raw | ConvertFrom-Json
                foreach ($prop in $reg.PSObject.Properties) {
                    $e = $prop.Value
                    if ($prop.Name -ieq $ModName -or $e.repo -ieq $ModName -or $e.displayName -ieq $ModName -or ($displayName -and $e.displayName -ieq $displayName)) {
                        foreach ($a in @($e.aliases)) { if ($a -and ($names -notcontains $a)) { $names += $a } }
                    }
                }
            }
        } catch { }

        $exact = $null
        $pluginMiss = ''
        # A Mod Organizer 2 PLUGIN of ours (single-file plugins\<Name>.py or folder plugins\<Name>\__init__.py) is
        # installed in the instance's own plugins folder (beside ModOrganizer.exe), never in mods\ - Test-Mo2PluginInstalled
        # holds the comparison (every packaged file under plugins\ byte-identical there, folder plugins recursively).
        if ($pkg) {
            $plug = Test-Mo2PluginInstalled -PkgPlugins (Join-Path $pkg.FullName 'plugins') -InstPlugins (Join-Path (Split-Path -Parent $inst.Path) 'plugins')
            if ($plug -and $plug.Installed) { $exact = $plug.Detail }
            elseif ($plug) { $pluginMiss = " $($plug.Detail)." }
        }
        # 2026-09-26 (Njordlinger MO2 Theme): a Mod Organizer 2 THEME ships as stylesheets\<Name>.qss + stylesheets\<Name>\
        # and is installed in the instance's own stylesheets folder (beside ModOrganizer.exe), never in mods\. It is
        # "installed at this version" when every packaged stylesheets file is byte-identical there.
        if (-not $exact -and $pkg -and (Test-Path -LiteralPath (Join-Path $pkg.FullName 'stylesheets'))) {
            $pkgStyles = Join-Path $pkg.FullName 'stylesheets'
            $qssFiles = @(Get-ChildItem -LiteralPath $pkgStyles -Filter '*.qss' -File -ErrorAction SilentlyContinue)
            if ($qssFiles.Count -gt 0) {
                $mo2Styles = Join-Path (Split-Path -Parent $inst.Path) 'stylesheets'
                $missing = @(Get-ChildItem -LiteralPath $pkgStyles -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
                    $inf = Join-Path $mo2Styles $_.FullName.Substring($pkgStyles.Length + 1)
                    -not (Test-Path -LiteralPath $inf) -or (Get-FileHash -LiteralPath $inf).Hash -ne (Get-FileHash -LiteralPath $_.FullName).Hash })
                if ($missing.Count -eq 0) { $exact = "$mo2Styles\$($qssFiles[0].Name) (MO2 theme, every file byte-identical to the package)" }
            }
        }
        foreach ($n in $names) {
            if ($exact) { break }
            $candidate = Join-Path $inst.Path "$n $Version"
            if (Test-Path -LiteralPath $candidate) { $exact = $candidate; break }
            # Installed folders carry the "[NoDelete] NNNN " prefix since 2026-08-27 (the install rule),
            # so the bare name never matches any more - accept the prefixed form (2026-08-29 fix).
            # ... and test builds in Njordlinger carry the "test " prefix (the owner's placement rule, 2026-09-15).
            # ... and an UNPUBLISHED mod of ours sits as "unpublished <name>", with no version in the folder name
            # (the owner's placement rule, 2026-09-20). Its folder is only accepted when it holds this version's
            # files: every packaged file present and byte-identical (checked below).
            # ... and "unpublished <name> <version>" when a new version of an unpublished mod goes in beside the old one
            # (Norden UI - Black 1.0.3, 2026-09-24: a FOMOD installed with the owner's choices, so the versionless
            # byte-identical check below cannot apply - the folder holds the chosen subset of the installer).
            $rx = '^(\[NoDelete\] \d+ |test |unpublished )' + [regex]::Escape("$n $Version") + '$'
            $unp = Join-Path $inst.Path "unpublished $n"
            if ((Test-Path -LiteralPath $unp) -and $pkg -and (Test-Path -LiteralPath $pkg.FullName)) {
                # install-test-build.py KEEPS the player's settings INI and lays the packaged one beside it as <name>.ini.default
                # (the owner, 2026-09-21), so a packaged .ini is judged against that .default copy when one exists - the live INI
                # is the player's and is expected to differ (2026-09-22: Back Pocket 1.0.1 read as 'not installed at all').
                $diff = @(Get-ChildItem -LiteralPath $pkg.FullName -Recurse -File | Where-Object { $_.Name -notmatch '^(README\.txt|LICENSE.*|NOTICE\.md)$' } | Where-Object {
                    $rel = $_.FullName.Substring($pkg.FullName.TrimEnd('\').Length + 1); $inf = Join-Path $unp $(if ($installPrefix) { Join-Path $installPrefix $rel } else { $rel })
                    if ($rel -match '\.ini$' -and (Test-Path -LiteralPath "$inf.default")) { $inf = "$inf.default" }
                    -not (Test-Path -LiteralPath $inf) -or (Get-FileHash -LiteralPath $inf).Hash -ne (Get-FileHash -LiteralPath $_.FullName).Hash })
                if ($diff.Count -eq 0) { $exact = "$unp (every packaged file byte-identical)"; break }
            }
            $hit = @(Get-ChildItem -Path $inst.Path -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -match $rx }) | Select-Object -First 1
            if ($hit) { $exact = $hit.FullName; break }
        }
        if ($exact) {
            Add-Result -Rule '29' -Check "Installed in $($inst.Name)" -Status PASS -Detail $exact
            continue
        }
        $anyVersion = @(Get-ChildItem -Path $inst.Path -Directory -ErrorAction SilentlyContinue |
            Where-Object { $n = $_.Name -replace '^(\[NoDelete\] \d+ |test |unpublished )', ''; @($names | Where-Object { $n -like "$_ *" }).Count -gt 0 })
        if ($anyVersion.Count -gt 0) {
            Add-Result -Rule '29' -Check "Installed in $($inst.Name)" -Status WARN -Detail (Get-InstalledVersionNote -Version $Version -Folders $anyVersion -Names $names)
        } else {
            Add-Result -Rule '29' -Check "Installed in $($inst.Name)" -Status FAIL -Detail "No version of '$ModName' found installed in $($inst.Path) at all (rule 29).$pluginMiss"
        }
    }
} else {
    Add-Result -Rule '29' -Check 'Installed into both MO2 instances' -Status SKIP -Detail 'No candidate version resolved.'
}

# ===========================================================================
# Playbook conformance
# ===========================================================================

if ($RepoPath) {
    # CMake preset keeps SE/AE enabled, only VR disabled.
    $presetsFile = Join-Path $RepoPath 'CMakePresets.json'
    if (Test-Path -LiteralPath $presetsFile) {
        try {
            $presets = Get-Content -LiteralPath $presetsFile -Raw | ConvertFrom-Json
            $badPresets = @()
            foreach ($cp in $presets.configurePresets) {
                if ($cp.PSObject.Properties.Name -contains 'environment' -and $cp.environment.PSObject.Properties.Name -contains 'RUNTIME_DISABLE_FLAGS') {
                    $flags = $cp.environment.RUNTIME_DISABLE_FLAGS
                    if ($flags -match '-UENABLE_SKYRIM_SE' -or $flags -match '-UENABLE_SKYRIM_AE') {
                        if ($cp.name -notmatch 'vr') { $badPresets += "$($cp.name): $flags" }
                    }
                }
            }
            if ($badPresets.Count -gt 0) {
                Add-Result -Rule 'Playbook' -Check 'CMake preset keeps SE and AE enabled (only VR excluded)' -Status FAIL -Detail "Preset(s) undefine ENABLE_SKYRIM_SE/AE outside a VR-named preset: $([string]::Join('; ', $badPresets))"
            } else {
                Add-Result -Rule 'Playbook' -Check 'CMake preset keeps SE and AE enabled (only VR excluded)' -Status PASS -Detail 'No non-VR preset undefines ENABLE_SKYRIM_SE/AE.'
            }
        } catch {
            Add-Result -Rule 'Playbook' -Check 'CMake preset keeps SE and AE enabled (only VR excluded)' -Status SKIP -Detail "Could not parse CMakePresets.json: $($_.Exception.Message)"
        }
    } else {
        Add-Result -Rule 'Playbook' -Check 'CMake preset keeps SE and AE enabled (only VR excluded)' -Status SKIP -Detail 'No CMakePresets.json (not a CMake+vcpkg project, or xmake-based).'
    }

    # DevBench tool registration
    $srcFiles = Get-ChildItem -Path $RepoPath -Recurse -Include '*.cpp', '*.h' -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch '\\build\\' -and $_.FullName -notmatch '\\extern\\' -and $_.FullName -notmatch '\\deps\\' -and $_.FullName -notmatch '\\lib\\commonlibsse' }
    $devbenchHit = $false
    foreach ($f in $srcFiles) {
        if (Select-String -LiteralPath $f.FullName -Pattern 'RegisterTool\s*\(|GetDevBenchInterface' -ErrorAction SilentlyContinue -Quiet) { $devbenchHit = $true; break }
    }
    if ($devbenchHit) {
        Add-Result -Rule '31/Playbook' -Check 'DevBench tool registration present' -Status PASS -Detail 'RegisterTool/GetDevBenchInterface found in source.'
    } elseif (@($srcFiles).Count -eq 0) {
        # An ASSET-ONLY mod has no code at all - no DLL, nothing running, nothing for a DevBench tool
        # to observe or drive. Rule 31 exists so behaviour can be watched live instead of
        # reconstructed from logs; a mod with no runtime behaviour has none to watch. Failing it
        # forever would be a standing false alarm, which is how real findings get ignored.
        # (2026-09-16: Jarl Ulfric Armor Replacer, a plugin and loose files.)
        Add-Result -Rule '31/Playbook' -Check 'DevBench tool registration present' -Status SKIP `
            -Detail 'Asset-only mod - no .cpp/.h anywhere in the repo, so there is no runtime behaviour a DevBench tool could observe. Rule 31 does not apply.'
    } else {
        Add-Result -Rule '31/Playbook' -Check 'DevBench tool registration present' -Status FAIL `
            -Detail "No RegisterTool(...)/GetDevBenchInterface call found anywhere in source. Rule 31: a mod's first version ships real-time observability via a DevBench tool, not just logs. If this mod predates rule 31 and a retrofit is judged not worth it, acknowledge and justify that explicitly in PROGRESS.md rather than treating this as silently fine."
    }

    # INISettingCollection pattern
    $settingsCpp = Get-ChildItem -Path $RepoPath -Recurse -Filter 'Settings.cpp' -ErrorAction SilentlyContinue | Where-Object { $_.FullName -notmatch '\\build\\' } | Select-Object -First 1
    # 2026-09-29: the pattern is the Skyrim SMF conversion playbook's (utils/INISettingCollection ships with the SMF
    # menu code). An Oblivion Remastered plugin on CommonLibOB64 has no SMF menu and reads its own INI - Simple Loadout
    # System OR tripped this as a FAIL for following a rule that does not cover it. SKIP for a CommonLibOB64 repo.
    $isObse64 = $false
    foreach ($bf in @('xmake.lua', 'vcpkg.json', 'CMakeLists.txt')) {
        $bp = Join-Path $RepoPath $bf
        if ((Test-Path -LiteralPath $bp) -and (Select-String -LiteralPath $bp -Pattern 'commonlibob64' -SimpleMatch -Quiet)) { $isObse64 = $true }
    }
    # 2026-10-05: an .asi plugin (AMF for Witcher 3 - no script extender, no CommonLib, no SMF) is outside the playbook too
    $isAsi = $false
    $xm = Join-Path $RepoPath 'xmake.lua'
    if ((Test-Path -LiteralPath $xm) -and (Select-String -LiteralPath $xm -Pattern 'set_extension(".asi")' -SimpleMatch -Quiet)) { $isAsi = $true }
    # 2026-10-07: Apocrypha Menu Framework IS the menu framework - it reads its own INI layered under the player's User.ini
    # (rule 16) and was never an SMF conversion; the playbook's pattern is for mods ported onto it. Same reason as below.
    $isFramework = (Split-Path -Leaf $RepoPath) -like 'ApocryphaMenuFramework*'
    # 2026-10-19: a mod with NO in-game settings page (no SKSE Menu Framework / ImGui menu code at all - Simple Loadout
    # System for Controller, per the owner's 2026-09-27 "no in-game settings" ruling) is not an SMF conversion either;
    # its INI read is the whole settings story. SLSC 1.0.3 false-FAILed here (and probably 1.0.2 on 2026-10-04).
    $hasMenuCode = $false
    foreach ($sd in @('source', 'src', 'include')) {
        $sp = Join-Path $RepoPath $sd
        if ((Test-Path -LiteralPath $sp) -and (Get-ChildItem -LiteralPath $sp -Recurse -Include '*.cpp', '*.h', '*.hpp' -ErrorAction SilentlyContinue |
                Select-String -Pattern 'SKSEMenuFramework|ImGui::' -List -ErrorAction SilentlyContinue | Select-Object -First 1)) { $hasMenuCode = $true; break }
    }
    if ($isFramework) {
        Add-Result -Rule 'Playbook' -Check 'Settings.cpp uses the INISettingCollection pattern' -Status SKIP -Detail 'Apocrypha Menu Framework is the framework itself (its own layered INI reader), not an SMF conversion.'
    } elseif ($isObse64) {
        Add-Result -Rule 'Playbook' -Check 'Settings.cpp uses the INISettingCollection pattern' -Status SKIP -Detail 'OBSE64 plugin (CommonLibOB64) - the SMF conversion playbook''s INI pattern does not apply.'
    } elseif ($isAsi) {
        Add-Result -Rule 'Playbook' -Check 'Settings.cpp uses the INISettingCollection pattern' -Status SKIP -Detail '.asi plugin (no script extender, no CommonLib) - the SMF conversion playbook''s INI pattern does not apply.'
    } elseif ($settingsCpp -and -not $hasMenuCode) {
        Add-Result -Rule 'Playbook' -Check 'Settings.cpp uses the INISettingCollection pattern' -Status SKIP -Detail 'No in-game settings page (no SKSE Menu Framework / ImGui menu code) - not an SMF conversion, so the playbook''s INI pattern does not apply.'
    } elseif ($settingsCpp) {
        $usesCollection = Select-String -LiteralPath $settingsCpp.FullName -Pattern 'INISettingCollection' -ErrorAction SilentlyContinue -Quiet
        if ($usesCollection) {
            Add-Result -Rule 'Playbook' -Check 'Settings.cpp uses the INISettingCollection pattern' -Status PASS -Detail "$($settingsCpp.Name) references INISettingCollection."
        } else {
            Add-Result -Rule 'Playbook' -Check 'Settings.cpp uses the INISettingCollection pattern' -Status FAIL -Detail "$($settingsCpp.Name) does not reference utils::INISettingCollection - check it isn't reading its INI ad-hoc instead (playbook Part 1 step 3)."
        }
    } else {
        Add-Result -Rule 'Playbook' -Check 'Settings.cpp uses the INISettingCollection pattern' -Status SKIP -Detail 'No Settings.cpp found.'
    }
} else {
    Add-Result -Rule 'Playbook' -Check 'CMake preset / DevBench / INISettingCollection' -Status SKIP -Detail 'No repo resolved.'
}

# ===========================================================================
# Report
# ===========================================================================

Write-Host ''
Write-Host "Results for '$ModName'$(if ($Version) { " v$Version" })" -ForegroundColor Cyan
Write-Host ("=" * 70)

foreach ($r in $results) {
    $color = switch ($r.Status) {
        'PASS' { 'Green' }
        'FAIL' { 'Red' }
        'WARN' { 'Yellow' }
        'SKIP' { 'DarkGray' }
    }
    Write-Host ("[{0,-4}] (rule {1,-9}) {2}" -f $r.Status, $r.Rule, $r.Check) -ForegroundColor $color
    foreach ($line in ($r.Detail -split "`n")) {
        Write-Host "         $line" -ForegroundColor $color
    }
}

$passCount = @($results | Where-Object Status -eq 'PASS').Count
$failCount = @($results | Where-Object Status -eq 'FAIL').Count
$warnCount = @($results | Where-Object Status -eq 'WARN').Count
$skipCount = @($results | Where-Object Status -eq 'SKIP').Count

Write-Host ''
Write-Host ("=" * 70)
Write-Host "SUMMARY: $passCount PASS, $failCount FAIL, $warnCount WARN, $skipCount SKIP" -ForegroundColor $(if ($failCount -gt 0) { 'Red' } elseif ($warnCount -gt 0) { 'Yellow' } else { 'Green' })

if ($failCount -gt 0) {
    Write-Host ''
    Write-Host "BLOCKED: $failCount genuine failure(s) found. Do not finalize this mod until each is either fixed, or explicitly acknowledged and justified in PROGRESS.md (CLAUDE.md rule 15/21) - never silently overridden." -ForegroundColor Red
    $gateExit = 1
} else {
    Write-Host ''
    Write-Host 'CLEAR to finalize on mechanical grounds (WARN/SKIP items above still worth a human glance, but do not block).' -ForegroundColor Green
    $gateExit = 0
}

# ===========================================================================
# -SyncNexusDistro: a no-op since 2026-10-12 (straight flow, gate A - the distro is not synced until finalize)
# ===========================================================================

if ($SyncNexusDistro) {
    Write-Host 'the distro sync runs inside finalize-mod now (straight flow, 2026-10-12)'
}

# ---------------------------------------------------------------------------------------------
# Pipeline event log. The write lives HERE, in the script that performs the transition, so the
# stage cannot forget to record - a log an agent is trusted to remember to append to is twelve
# documents with extra syntax. It is never allowed to fail this script.
$plog = $RolePipelineLog
# The note names WHAT refused the build (2026-10-10): every 463 gate-FAIL before this carried an empty note, so the log
# could count refusals but never say which rule caught what. One token per failing check, '; '-separated:
# 'gate-rules:<id>' for each package-gate row that hit, 'rule <n>: <check>' for the script's own checks.
function Format-GateFailNote($Results) {   # tested by scripts\tests\test_gate_fail_note.py
    $tokens = New-Object System.Collections.Generic.List[string]
    foreach ($r in @($Results | Where-Object { $_.Status -eq 'FAIL' })) {
        if ($r.Rule -eq 'gate') {
            $ids = @([regex]::Matches("$($r.Detail)", '(?m)^\s*!!\s+\[([^\]]+)\]') | ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique)
            if ($ids.Count) { foreach ($id in $ids) { $tokens.Add("gate-rules:$id") } } else { $tokens.Add('gate-rules:(unparsed)') }
        } else {
            $tokens.Add("rule $($r.Rule): $($r.Check)")
        }
    }
    return (@($tokens | Select-Object -Unique) -join '; ')
}
$failNote = if ($gateExit -ne 0) { Format-GateFailNote $results } else { '' }
# gate C (2026-10-13): the event carries its input fingerprint (refs.inputs) and, under -Force, the override (refs.override
# and the note). The reason's ';' become ',' so the note's '; '-separated reason tokens stay readable.
$gcRefs = [ordered]@{ caller = $gcCaller }   # gate C compares only with the same caller's last event (2026-10-22)
if ($gcInputs) { $gcRefs['inputs'] = $gcInputs }
if ($gcOverride) {
    $gcRefs['override'] = $gcOverride
    $ovr = 'override: ' + ("$Reason" -replace ';', ',')
    $failNote = if ($failNote) { "$failNote; $ovr" } else { $ovr }
}
if (Test-Path -LiteralPath $plog) {
    $logArgs = @{ Action = 'record'; Stage = 10; Event = $(if ($gateExit -eq 0) { 'gate-pass' } else { 'gate-FAIL' }); Mod = $ModName; Key = $gcKey
                  Version = $(if ($Version) { $Version } else { $gcVersion }); Evidence = 'pre-finalize-check.ps1, the mandatory mechanical gate (rule 34)'; Note = $failNote; By = 'pre-finalize-check.ps1' }
    if ($gcRefs.Count) { $logArgs['RefsJson'] = ($gcRefs | ConvertTo-Json -Compress -Depth 6) }
    try { & $plog @logArgs | Out-Null } catch { }
}

exit $gateExit
