<#
.SYNOPSIS
    Auto-generates/updates a finalized mod's Nexus distro material as part of finalizing.

.DESCRIPTION
    CLAUDE.md rule 10 says every mod in "10. finalized mods" gets Nexus-ready material in
    "11. Nexus distro\<mod name>\", kept current as the mod's version moves on. That was documented
    intent, not a mechanical guarantee - the 2026-08-26 "Nexus distro accuracy audit" found real
    drift in 3 of 4 audited mods (stale version numbers in nexus-page.txt/changelog.txt, a stale
    zip copy, a banner that was never regenerated), and Auto Draw reached "10. finalized mods"
    with NO Nexus distro folder at all. The owner's instruction: "if they are in finalized, it's
    assumed that they're going to go to nexus" - so finalizing should automatically generate or
    update this material, not leave it to be remembered by hand.

    This script is the mechanical half of that. It does NOT write persuasive prose - description,
    Main features, Requirements, Credit are real content work (rule 10) and this script never
    invents them. What it DOES do, for a mod whose "11. Nexus distro\<name>\" folder already exists:

      - Corrects the version reference(s) in nexus-page.txt's Source section (and any other
        line that names the mod's own version alongside the word "version") to the version
        being finalized, and bumps nexus-page.txt's own document-version counter in notes.txt
        (rule 10's separate versioning scheme) when it makes a real text change.
      - Adds a minimal changelog.txt entry for the version being finalized if one is missing,
        generated from `git log <prevTag>..<newTag>` and clearly flagged as auto-generated from
        commit messages, not hand-written prose.
      - Copies the authoritative package zip (from "10. finalized mods", or "7. current test
        builds" if the mod hasn't been moved yet) over the distro folder's own zip copy if it's
        missing or a different version.
      - Re-rasterizes the 1920x1080 banner (headless Edge) if its version pill doesn't match.

    For a mod with NO "11. Nexus distro\<name>\" folder at all - i.e. finalizing for the first time -
    this script deliberately does nothing but flag it clearly (console + a dated to-do-list.md
    entry) and exits with code 2. Writing the initial page from scratch is a real content-writing
    pass, not a mechanical fix, and generating placeholder prose to satisfy this check would be
    worse than admitting the gap plainly.

    finalize-mod.ps1 runs it twice (straight flow, 2026-10-13; the owner's order is working -> gate ->
    finalized -> distro): -Part Text BEFORE the gate, from the candidate package in "7. current test
    builds", so the gate judges the page the upload will carry; then, after the move, the zip and the
    gate's post-check, -Part Zip, which only clears other zips of the mod out of the distro folder.
    Neither part records an event - finalize-mod.ps1 writes 'distro-synced' itself once the zip is
    copied and its hash verified. A plain run (-Part All, the default) is the page re-edit of a
    version already in "10. finalized mods", and records its own 'distro-synced' event.

    REFUSES (exit 3) outside finalize (the owner, 2026-10-12: "the distro is not synced until finalize"):
    it runs only when the version is already in "10. finalized mods" (a page re-edit of a posted mod), or
    when the environment variable MODS_FINALIZE_RUN is "<mod key or display name>:<version>:<pid>" for this
    mod and version and a running process - finalize-mod.ps1 sets it for its own run.

.PARAMETER Part
    All (default): every step below and the 'distro-synced' event. Text: page, notes counter, changelog and banner
    only - the zip step SKIPs and no event is recorded (finalize-mod.ps1, before its gate). Zip: the zip step only -
    copy the authoritative zip if it is missing and send other zips of this mod to the Recycle Bin - and no event
    (finalize-mod.ps1, after its post-check).

.PARAMETER ModName
    Same meaning as pre-finalize-check.ps1's -ModName - the package/Nexus-distro display name.

.PARAMETER Version
    Optional. The version being finalized. Defaults to the newest version found for this mod in
    "10. finalized mods", falling back to the newest in "7. current test builds".

.PARAMETER RepoPath
    Optional. Overrides auto-discovery of the mod's source repo (needed only for the git-log
    changelog backfill).

.PARAMETER Game
    Optional. Skyrim, Oblivion Remastered or MO2 - the game folder the packages are read from (2026-10-01: packages
    sit in "<stage>\<Game> - <Mod>\"). Without it the version registry decides, and a name two games share with
    packages in both stops the script rather than guess.

.PARAMETER ProjectRoot
    Optional. Defaults to "<ROOT>".

.PARAMETER DryRun
    Report what would change without writing/copying/rasterizing anything.

.EXAMPLE
    .\sync-nexus-distro.ps1 -ModName "Local Map Upgrade"
#>

param(
    [Parameter(Mandatory = $true)][string]$ModName,
    [string]$Version,
    [string]$RepoPath,
    [string]$Game,
    [string]$ProjectRoot = $env:PIPELINE_ROOT,
    [ValidateSet('All', 'Text', 'Zip')][string]$Part = 'All',
    # The test-build folder finalize-mod picked (test-build-pick, by the working hash). Without it the candidate had to be
    # named exactly '<mod> <version>', so a picked folder with a suffix - 'Simple Loadout System 1.0.1 (scroll bar +
    # stick nav)', 2026-10-13 - was not found and the text sync stopped with 'no package to read'.
    [string]$PackagePath,
    [switch]$DryRun
)

$ErrorActionPreference = 'Continue'
if (-not $ProjectRoot) { $_kitRoot = $PSScriptRoot; while ($_kitRoot -and (Split-Path $_kitRoot -Leaf) -ne '.MD') { $_kitRoot = Split-Path $_kitRoot -Parent }; if ($_kitRoot) { $_kitRoot = Split-Path $_kitRoot -Parent }; $ProjectRoot = $_kitRoot }   # kit: <ROOT> is the folder above the .MD this script sits under, unless PIPELINE_ROOT says otherwise
$results = New-Object System.Collections.Generic.List[object]

function Add-Result {
    param([string]$Check, [ValidateSet('CURRENT', 'FIXED', 'FLAGGED', 'SKIP')][string]$Status, [string]$Detail)
    $results.Add([pscustomobject]@{ Check = $Check; Status = $Status; Detail = $Detail })
}

function Normalize-Name {
    param([string]$s)
    if (-not $s) { return '' }
    return ($s -replace '[^A-Za-z0-9]', '').ToLowerInvariant()
}

function Get-VersionMatches {
    param([string]$Text)
    if (-not $Text) { return @() }
    $m = [regex]::Matches($Text, '\bv?(\d+)\.(\d+)\.(\d+)\b')
    return $m | ForEach-Object { $_.Value }
}

# Rule 6/10's shared version scheme (semantic versioning since 2026-10-21): a mechanical page correction is a PATCH
# step of the page's document version (1.0.9 -> 1.0.10, no roll-over). The arithmetic is version-gate.ps1's
# (nextnumber -Kind patch) - this file kept its own roll-over copy until then.
function Step-Version {
    param([string]$v)
    if ($v -notmatch '^\d+\.\d+\.\d+$') { return $null }
    $n = & (Find-Role 'version-gate') -Action nextnumber -From $v -Kind patch
    if ($LASTEXITCODE -ne 0 -or -not $n) { return $null }
    return "$(@($n)[-1])".Trim()
}

Write-Host "Nexus distro sync for '$ModName'" -ForegroundColor Cyan
Write-Host ("=" * 70)
if ($DryRun) { Write-Host "(DRY RUN - no files will be changed)" -ForegroundColor Yellow }

# ---------------------------------------------------------------------------
# Discovery - mirrors pre-finalize-check.ps1's own logic
# ---------------------------------------------------------------------------

$baseName = ($ModName -split ' - ')[0].Trim()
$normBase = Normalize-Name $baseName

if (-not $RepoPath) {
    $wipRoot = Join-Path $ProjectRoot '6. current wip mods'
    $candidates = @(Get-ChildItem -Path $wipRoot -Directory -ErrorAction SilentlyContinue |
        Where-Object { (Normalize-Name $_.Name).StartsWith($normBase) -or (Normalize-Name $_.Name).Contains($normBase) } |
        Sort-Object { $_.Name.Length })
    if ($candidates.Count -ge 1) { $RepoPath = $candidates[0].FullName }
}

$finalizedRoot = Join-Path $ProjectRoot '10. finalized mods'
$testBuildsRoot = Join-Path $ProjectRoot '7. current test builds'

# Every lookup goes through the resolver OF THIS TREE (STEPS 5.4/5.5), never the absolute <ROOT> path.
$ResolverPy = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\resolvers\resolve.py'))
function Find-Role([string]$role) {
    $p = @(& py -3 $ResolverPy find $role)
    if ($LASTEXITCODE -ne 0 -or $p.Count -eq 0 -or -not "$($p[0])".Trim()) { Write-Output "sync-nexus-distro: cannot resolve role '$role' ($($p -join ' '))"; exit 1 }
    return "$($p[0])".Trim()
}
. (Find-Role 'distro-names')   # the folder is "<Game> - <Mod>" since 2026-09-29; never join the name yourself
$RegistryPath = Find-Role 'version-registry'
$PipelineLogPath = Find-Role 'pipeline-log'
# Packages sit in "<stage>\<Game> - <Mod>\" since 2026-10-01. The game is -Game, else the registry's entries of this
# name (the one whose repo is -RepoPath when two share it), else every game folder - and packages of two games then stop
# the script below instead of one being picked.
if (-not $Game) {
    try {
        $regSync = Get-Content -LiteralPath $RegistryPath -Raw | ConvertFrom-Json
        $ents = @($regSync.PSObject.Properties | Where-Object { $_.Value.displayName -ieq $ModName -or $_.Name -ieq $ModName -or $_.Value.repo -ieq $ModName })
        # only a repo the CALLER named decides between two entries - the name-matched guess above picks the shortest repo
        if ($PSBoundParameters.ContainsKey('RepoPath') -and $ents.Count -gt 1) { $byRepo = @($ents | Where-Object { $_.Value.repo -ieq (Split-Path $RepoPath -Leaf) }); if ($byRepo.Count) { $ents = $byRepo } }
        $gs = @($ents | ForEach-Object { Get-ModGame -Entry $_.Value -ProjectRoot $ProjectRoot } | Sort-Object -Unique)
        if ($gs.Count -eq 1) { $Game = $gs[0] }
    } catch { }
}
function Stop-TwoGames([object[]]$Found, [string]$What) {
    if (@($Found | ForEach-Object { $_.PkgGame } | Sort-Object -Unique).Count -gt 1) {
        Write-Host "FAILED: '$ModName' has $What for more than one game - pass -Game." -ForegroundColor Red
        exit 1
    }
}

$finalizedPkg = $null
$testPkg = $null
$sourceState = $null  # 'finalized' or 'test-builds'

if ($Version) {
    $finalizedFound = @(Find-Packages -Root $finalizedRoot -ModName $ModName -Game $Game -Version $Version -Folders -ProjectRoot $ProjectRoot |
        Where-Object { $_.Name -eq "$ModName $Version" -or $_.Name -eq "$ModName $Version FOMOD" })
    Stop-TwoGames $finalizedFound "finalized $Version packages"
    $finalizedPkg = $finalizedFound | Sort-Object { if ($_.Name -like '* FOMOD') { 0 } else { 1 } } | Select-Object -First 1
    # 2026-09-17: a mod that ships ONLY as a FOMOD (Apocrypha Menu Framework since 1.8.8) has no plain
    # "<Mod> <Version>" folder; the " FOMOD" folder is its finalized package and is preferred when both exist.
    if ($finalizedPkg) { $sourceState = 'finalized' }
} else {
    $finalizedCandidates = @(Find-Packages -Root $finalizedRoot -ModName $ModName -Game $Game -Folders -ProjectRoot $ProjectRoot)
    Stop-TwoGames $finalizedCandidates 'finalized packages'
    $finalizedPkg = $finalizedCandidates | Sort-Object { [version]((Get-VersionMatches $_.Name | Select-Object -First 1) -replace '^v', '') } -Descending | Select-Object -First 1
    if ($finalizedPkg) {
        $Version = (Get-VersionMatches $finalizedPkg.Name | Select-Object -First 1) -replace '^v', ''
        $sourceState = 'finalized'
    }
}

if (-not $finalizedPkg) {
    # Fall back to the candidate still sitting in "7. current test builds" (pre-move state).
    $pkgCandidates = @(Find-Packages -Root $testBuildsRoot -ModName $ModName -Game $Game -Folders -ProjectRoot $ProjectRoot)
    Stop-TwoGames $pkgCandidates 'test builds'
    if ($PackagePath) {
        # Find-Packages lists only folders named '<mod> <version>[ FOMOD]', so a picked folder with a suffix is taken as
        # given - when it exists, sits under 7. current test builds and is named for this mod and version.
        $want = [System.IO.Path]::GetFullPath($PackagePath).TrimEnd('\')
        $leaf = Split-Path $want -Leaf
        $underTest = $want.StartsWith([System.IO.Path]::GetFullPath($testBuildsRoot).TrimEnd('\') + '\', [System.StringComparison]::OrdinalIgnoreCase)
        if ($Version -and $underTest -and (Test-Path -LiteralPath $want -PathType Container) -and ($leaf -eq "$ModName $Version" -or $leaf -like "$ModName $Version *")) {
            $testPkg = Get-Item -LiteralPath $want
            # its game from the "<Game> - <Mod>" folder it sits in, as Find-Packages gives it (2026-10-14): read from its
            # contents, Loot on Hover (W3) - which ships a tools/bindings.py helper - looked like an MO2 plugin
            $testPkg | Add-Member -NotePropertyName PkgGame -NotePropertyValue (Get-DistroFolderGame -Folder (Split-Path (Split-Path $want -Parent) -Leaf)) -Force
        } else {
            Write-Host "FAILED: -PackagePath '$PackagePath' is not a test-build package of '$ModName' $Version." -ForegroundColor Red; exit 1
        }
    } elseif ($Version) {
        $testPkg = $pkgCandidates | Where-Object { $_.Name -eq "$ModName $Version" } | Select-Object -First 1
    } else {
        $testPkg = $pkgCandidates | Sort-Object { [version]((Get-VersionMatches $_.Name | Select-Object -First 1) -replace '^v', '') } -Descending | Select-Object -First 1
        if ($testPkg) { $Version = (Get-VersionMatches $testPkg.Name | Select-Object -First 1) -replace '^v', '' }
    }
    if ($testPkg) { $sourceState = 'test-builds' }
}

if (-not $Version) {
    Write-Host "FAILED: could not resolve any candidate/finalized version for '$ModName' in either '10. finalized mods' or '7. current test builds'." -ForegroundColor Red
    exit 1
}

Write-Host "Syncing against version $Version (found in $(if ($sourceState -eq 'finalized') { '10. finalized mods' } else { '7. current test builds - not yet moved, zip-copy step will SKIP' }))."

# The game comes from the package being synced (2026-09-30): without it, "Apocrypha Menu Framework" 1.0.5 (Oblivion
# Remastered) resolved to the SKYRIM framework's folder - its page, notes, banner and zip were rewritten to 1.0.5 and its
# 1.9.9 FOMOD zip deleted. A package whose game cannot be read stops here rather than guess.
$pkgForGame = if ($finalizedPkg) { $finalizedPkg.FullName } elseif ($testPkg) { $testPkg.FullName } else { $null }
$pkgObj = if ($finalizedPkg) { $finalizedPkg } else { $testPkg }
$pkgGame = if ($pkgObj -and $pkgObj.PkgGame) { $pkgObj.PkgGame } elseif ($pkgForGame) { Get-PackageGame -Path $pkgForGame } else { '' }   # its game folder, else its contents
if (-not $pkgGame) {
    Write-Host "FAILED: could not tell which game '$ModName $Version' is for (no package to read) - not touching any distro folder." -ForegroundColor Red
    exit 1
}

# THE FINALIZE GATE (the owner, 2026-10-12: "the distro is not synced until finalize" - straight-flow gate A). The sync
# runs inside finalize-mod.ps1, which sets MODS_FINALIZE_RUN=<mod key or display name>:<version>:<pid> for its run, or
# for a version already in 10. finalized mods (a page re-edit of a posted mod). "Proved working" syncs nothing: a hand
# run or pre-finalize-check before the finalize is refused here, before anything is written. "This mod" and "this
# version" are the ones resolved above: -ModName (or a registry key of its entries for this package's game) and $Version;
# "already finalized" is $sourceState - a "<Mod> <Version>[ FOMOD]" folder in "10. finalized mods\<Game> - <Mod>\".
if ($sourceState -ne 'finalized') {
    $frRaw = "$env:MODS_FINALIZE_RUN"
    $frWhy = 'MODS_FINALIZE_RUN is not set'
    if ($frRaw) {
        $frParts = @($frRaw -split ':')
        if ($frParts.Count -lt 3) {
            $frWhy = "MODS_FINALIZE_RUN '$frRaw' is not <mod>:<version>:<pid>"
        } else {
            $frPid = $frParts[-1]; $frVer = $frParts[-2]; $frMod = ($frParts[0..($frParts.Count - 3)] -join ':')
            $frNames = @($ModName)
            try {
                $regGate = Get-Content -LiteralPath $RegistryPath -Raw | ConvertFrom-Json
                $frNames += @($regGate.PSObject.Properties |
                    Where-Object { ($_.Value.displayName -ieq $ModName -or $_.Name -ieq $ModName -or $_.Value.repo -ieq $ModName) -and (Get-ModGame -Entry $_.Value -ProjectRoot $ProjectRoot) -eq $pkgGame } |
                    ForEach-Object { $_.Name; "$($_.Value.displayName)" })
            } catch { }
            if (-not @($frNames | Where-Object { $_ -and $_ -ieq $frMod }).Count) { $frWhy = "MODS_FINALIZE_RUN names '$frMod', not '$ModName'" }
            elseif ($frVer -ne $Version) { $frWhy = "MODS_FINALIZE_RUN names version $frVer, not $Version" }
            elseif ($frPid -notmatch '^\d+$' -or -not (Get-Process -Id ([int]$frPid) -ErrorAction SilentlyContinue)) { $frWhy = "MODS_FINALIZE_RUN's process $frPid is not running" }
            else { $frWhy = $null }
        }
    }
    if ($frWhy) {
        Write-Host "REFUSED: the distro is not synced until finalize (the owner, 2026-10-12) - '$ModName $Version' is not in 10. finalized mods and this is not finalize-mod's run ($frWhy); finalize it with finalize-mod.ps1." -ForegroundColor Red
        exit 3
    }
    Write-Host "Finalize run: MODS_FINALIZE_RUN matches '$ModName' $Version - syncing ahead of the move."
}
$nexusDir = Resolve-DistroFolder -ModName $ModName -Game $pkgGame -ProjectRoot $ProjectRoot
Write-Host "Distro folder: $(Split-Path $nexusDir -Leaf)  (game read from the package: $pkgGame)"
# AN OPTIONAL FILE OF ANOTHER MOD'S PAGE (the owner, 2026-10-19; registry field optionalFileOf, distro-names.ps1
# Get-OptionalFileInfo): the folder above is the PARENT's, so the page text, the notes counter and the banner are the
# parent's and are left alone - rewriting them to this file's version would put a wrong number on the parent's page. What
# is this file's own: its changelog (the registry's optionalChangelog) and its zip, which the steps below handle by name.
$optInfo = $null
try { $optInfo = Get-OptionalFileInfo -ModName $ModName -ProjectRoot $ProjectRoot } catch { Write-Host "FAILED: $($_.Exception.Message)" -ForegroundColor Red; exit 1 }
if ($optInfo) { Write-Host "'$ModName' is an optional file of '$($optInfo.parent)': syncing only its own changelog ($($optInfo.changelog)) and zip; the parent's page, notes and banner are not touched." -ForegroundColor Cyan }
if ((Get-DistroFolderGame -Folder (Split-Path $nexusDir -Leaf)) -and (Get-DistroFolderGame -Folder (Split-Path $nexusDir -Leaf)) -ne $pkgGame) {
    Write-Host "FAILED: '$(Split-Path $nexusDir -Leaf)' is not a $pkgGame folder - not touching it." -ForegroundColor Red
    exit 1
}

# ===========================================================================
# Folder-existence gate: never invent prose from nothing.
# ===========================================================================

if (-not (Test-Path -LiteralPath $nexusDir)) {
    Write-Host ''
    Write-Host "NEEDS-CONTENT-PASS: no '11. Nexus distro\$ModName' folder exists." -ForegroundColor Yellow
    Write-Host "This looks like $ModName's first finalize. Initial Description / Main features /" -ForegroundColor Yellow
    Write-Host "Installation / Requirements / Credit prose is real content work (CLAUDE.md rule 10)" -ForegroundColor Yellow
    Write-Host "and this script deliberately does not invent it. Write it by hand (or a dedicated" -ForegroundColor Yellow
    Write-Host "content pass) following '11. Nexus distro\_nexus-page-template.txt', then re-run this" -ForegroundColor Yellow
    Write-Host "script to handle the mechanical parts (version refs, zip, banner, changelog)." -ForegroundColor Yellow

    if (-not $DryRun) {
        $todoFile = Join-Path $ProjectRoot '2. Mod Types\to-do list\to-do-list.md'
        if (Test-Path -LiteralPath $todoFile) {
            $date = Get-Date -Format 'yyyy-MM-dd'
            $entry = "`n- $date - **$ModName** finalized (v$Version) with no '11. Nexus distro\$ModName' folder yet - needs a real content-writing pass (Description/Main features/Installation/Requirements/Credit) per rule 10's template before it's Nexus-ready. Logged automatically by sync-nexus-distro.ps1.`n"
            Add-Content -LiteralPath $todoFile -Value $entry
            Write-Host "Logged to to-do-list.md under Open." -ForegroundColor Yellow
        }
    }
    exit 2
}

# Sections 1-3 (page, notes, changelog) and 5 (banner) are the TEXT part; section 4 is the ZIP part (-Part, 2026-10-13).
if ($Part -ne 'Zip') {
# ===========================================================================
# 1. nexus-page.txt version references
# ===========================================================================

$nexusPageFile = Join-Path $nexusDir 'nexus-page.txt'
$nexusPageChanged = $false

if ($optInfo) {
    Add-Result -Check 'nexus-page.txt version references' -Status SKIP -Detail "Optional file of '$($optInfo.parent)': the page is the parent's and carries the parent's version."
} elseif (Test-Path -LiteralPath $nexusPageFile) {
    $text = Get-Content -LiteralPath $nexusPageFile -Raw
    $original = $text

    # Anchor 1: "This package is vX.Y.Z"
    $spm = [regex]::Match($text, 'This package is\s+v?(\d+\.\d+\.\d+)')
    $oldVersion = $null
    if ($spm.Success) {
        $oldVersion = $spm.Groups[1].Value
        if ($oldVersion -ne $Version) {
            $text = [regex]::Replace($text, '(This package is\s+v?)(\d+\.\d+\.\d+)', "`${1}$Version")
        }
    }

    # Anchor 2: "releases/tag/vX.Y.Z" (the same paragraph's release link)
    $text = [regex]::Replace($text, '(releases/tag/v)(\d+\.\d+\.\d+)', "`${1}$Version")
    # Anchor 2b: the release link's LABEL ("]v1.7.0 on GitHub") - moving only the URL left the label
    # naming the previous version (DEM 1.7.3, 2026-09-24; gate rule page-release-link-label-matches-tag).
    # 2026-10-28: words may come before the label's version ("]release tag v1.0.1", RaceMenu Atelier 1.1.0) - the
    # first version number in the label is the one replaced.
    $text = [regex]::Replace($text, '(releases/tag/v\d+\.\d+\.\d+\][^\[\]\d]*)(\d+\.\d+\.\d+)', "`${1}$Version")

    # Anchor 3: any other line naming this mod's own version next to the word "version" that
    # still carries the OLD version string (e.g. a Compatibility notes sentence like "reports
    # its plugin version as 1.2.1"). Conservative: only touches the exact old-version substring,
    # only on lines that contain the word "version".
    if ($oldVersion -and $oldVersion -ne $Version) {
        $lines = $text -split "`n"
        for ($i = 0; $i -lt $lines.Length; $i++) {
            if ($lines[$i] -match '(?i)version' -and $lines[$i] -match [regex]::Escape($oldVersion)) {
                $lines[$i] = $lines[$i] -replace [regex]::Escape($oldVersion), $Version
            }
        }
        $text = $lines -join "`n"
    }

    if ($text -ne $original) {
        $nexusPageChanged = $true
        if (-not $DryRun) { Set-Content -LiteralPath $nexusPageFile -Value $text -NoNewline }
        Add-Result -Check 'nexus-page.txt version references' -Status FIXED -Detail "Corrected version reference(s) from $oldVersion to $Version (Source section + any 'version'-adjacent mentions)."
    } else {
        Add-Result -Check 'nexus-page.txt version references' -Status CURRENT -Detail "Already references v$Version."
    }
} else {
    Add-Result -Check 'nexus-page.txt version references' -Status SKIP -Detail 'No nexus-page.txt found in the distro folder.'
}

# ===========================================================================
# 2. notes.txt document-version counter + a dated auto-sync entry
# ===========================================================================

$notesFile = Join-Path $nexusDir 'notes.txt'
if ($nexusPageChanged -and (Test-Path -LiteralPath $notesFile)) {
    $notesText = Get-Content -LiteralPath $notesFile -Raw
    $docVerMatches = [regex]::Matches($notesText, 'nexus-page\.txt version:\s*(\d+\.\d+\.\d+)')
    $newDocVer = if ($docVerMatches.Count -gt 0) {
        Step-Version $docVerMatches[$docVerMatches.Count - 1].Groups[1].Value
    } else { '1.0.0' }

    $date = Get-Date -Format 'yyyy-MM-dd'
    $entry = @"


AUTOMATED SYNC - $date (sync-nexus-distro.ps1)
Mechanical version-reference correction to v$Version as part of finalizing (CLAUDE.md rule 10 /
21). Not a hand-written content revision - only the version number(s) changed. Review if a real
feature/wording update is also due.

nexus-page.txt version: $newDocVer
"@
    if (-not $DryRun) { Add-Content -LiteralPath $notesFile -Value $entry }
    Add-Result -Check 'notes.txt document-version counter' -Status FIXED -Detail "Bumped to $newDocVer and logged a dated AUTOMATED SYNC entry."
} elseif (Test-Path -LiteralPath $notesFile) {
    Add-Result -Check 'notes.txt document-version counter' -Status CURRENT -Detail 'No nexus-page.txt content change this run - counter left untouched (rule 10: only bumps on a real revision).'
} else {
    Add-Result -Check 'notes.txt document-version counter' -Status SKIP -Detail 'No notes.txt found.'
}

# ===========================================================================
# 3. changelog.txt entry for the version being finalized
# ===========================================================================

$changelogFile = Join-Path $nexusDir $(if ($optInfo) { $optInfo.changelog } else { 'changelog.txt' })   # an optional file keeps its own changelog beside the page's
if (Test-Path -LiteralPath $changelogFile) {
    $changelogText = Get-Content -LiteralPath $changelogFile -Raw
    # Two heading shapes count as "this version is already written up":
    #   1.6.3            <- the older shape this script used to write itself
    #   Version 1.6.3    <- the standing published template (11. Nexus distro\_CHANGELOG-TEMPLATE.txt,
    #                       owner 2026-09-02), which every hand-written entry now uses
    # Only matching the first meant a properly hand-written entry was invisible to this check, and
    # an auto-generated placeholder was appended underneath it on every sync (seen 2026-09-03).
    $headings = @([regex]::Matches($changelogText, '(?m)^(?:Version\s+)?(\d+\.\d+\.\d+)\s*$') | ForEach-Object { $_.Groups[1].Value })
    $hasEntry = $headings -contains $Version

    if ($hasEntry) {
        Add-Result -Check 'changelog.txt has an entry for this version' -Status CURRENT -Detail "Entry for $Version already present."
    } else {
        $newestExisting = if ($headings.Count -gt 0) { ($headings | Sort-Object { [version]$_ } -Descending)[0] } else { $null }
        $entryBody = $null

        if ($RepoPath -and (Test-Path -LiteralPath (Join-Path $RepoPath '.git')) -and $newestExisting) {
            Push-Location $RepoPath
            try {
                $oldTag = "v$newestExisting"
                $newTag = "v$Version"
                $oldTagExists = (git tag -l $oldTag 2>$null)
                $newTagExists = (git tag -l $newTag 2>$null)
                if ($oldTagExists -and $newTagExists) {
                    $log = git log "$oldTag..$newTag" --oneline --no-merges 2>$null
                    if ($log) {
                        $bullets = ($log | ForEach-Object { $_ -replace '^[0-9a-f]+\s+', '- ' })
                        $entryBody = ($bullets -join "`n")
                    }
                }
            } finally { Pop-Location }
        }

        if (-not $entryBody) {
            $entryBody = "- (auto-generated placeholder - no clean commit-message range found between the previous`n  changelog entry and this version; fill in by hand.)"
            $flagged = $true
        } else {
            $flagged = $true
        }

        $divider = '-' * 66
        $newEntry = "$Version`n$divider`n(auto-generated from commit messages by sync-nexus-distro.ps1 - review/expand before`npublishing, this is not hand-written release-note prose)`n$entryBody`n`n"

        # Insert above the first existing version heading, or append if the file has none yet.
        if ($newestExisting) {
            $insertPattern = "(?m)^$([regex]::Escape($newestExisting))\s*$"
            $newChangelogText = [regex]::Replace($changelogText, $insertPattern, { param($m) "$newEntry$($m.Value)" }, 1)
        } else {
            $newChangelogText = $changelogText.TrimEnd() + "`n`n`n$newEntry"
        }

        if (-not $DryRun) { Set-Content -LiteralPath $changelogFile -Value $newChangelogText -NoNewline }
        Add-Result -Check 'changelog.txt has an entry for this version' -Status FLAGGED -Detail "Added a minimal auto-generated entry for $Version from git log - flagged for review, not hand-written-quality prose."
    }
} else {
    Add-Result -Check 'changelog.txt has an entry for this version' -Status SKIP -Detail 'No changelog.txt found (fine for a mod that has never been updated after its first Nexus material).'
}
}   # end of the text part (sections 1-3)

# ===========================================================================
# 4. Distro folder's own package zip copy
# ===========================================================================

if ($Part -eq 'Text') {
    Add-Result -Check 'Distro package zip is the newest finalized package, and the only one' -Status SKIP -Detail 'Text part only: finalize-mod.ps1 copies the finalized zip in after the move and verifies its hash.'
} else {

# The FOMOD zip is what a player installs, so when "10. finalized mods" carries both a plain zip and a
# FOMOD zip for this version the FOMOD is the one that ships here. Rule 10 (owner, 2026-09-06): the
# distro folder holds exactly ONE zip per mod - the newest finalized version - and is the only place
# he posts from, so every other zip of this mod in the folder is removed, whatever its version.
$authoritativeZip = $null
foreach ($root in @($(if ($sourceState -eq 'finalized') { $finalizedRoot } else { $null }), $testBuildsRoot)) {
    if (-not $root) { continue }
    # this game's archives only, from its "<Game> - <Mod>" folder (2026-10-01)
    $zipsHere = @(Find-Packages -Root $root -ModName $ModName -Game $pkgGame -Version $Version -Archives -ProjectRoot $ProjectRoot)
    foreach ($suffix in @(' FOMOD.zip', '.zip')) {
        $candidate = $zipsHere | Where-Object { $_.Name -eq "$ModName $Version$suffix" } | Select-Object -First 1
        if (-not $authoritativeZip -and $candidate) { $authoritativeZip = $candidate.FullName }
    }
    if ($authoritativeZip) { break }
}

if ($authoritativeZip) {
    $existingZips = @(Get-ChildItem -Path $nexusDir -Filter "$ModName *.zip" -File -ErrorAction SilentlyContinue)
    $targetZipName = Split-Path $authoritativeZip -Leaf
    $targetZipPath = Join-Path $nexusDir $targetZipName
    $upToDate = (Test-Path -LiteralPath $targetZipPath) -and
        ((Get-Item -LiteralPath $targetZipPath).Length -eq (Get-Item -LiteralPath $authoritativeZip).Length)
    # An optional download of THIS version ("<Mod> X.Y.Z - SDK.zip", AMF for Oblivion Remastered) is part of the post, not
    # a stale main file (2026-09-30: the one-zip rule would have deleted AMF 1.0.5's SDK). Older optional zips still go.
    $optional = '^' + [regex]::Escape("$ModName $Version") + ' - [^\d].*\.zip$'
    $stale = @($existingZips | Where-Object { $_.FullName -ne $targetZipPath -and $_.Name -notmatch $optional })

    if ($upToDate -and $stale.Count -eq 0) {
        Add-Result -Check 'Distro package zip is the newest finalized package, and the only one' -Status CURRENT -Detail "$targetZipName already present, same size as the authoritative zip, no other zip of this mod beside it."
    } else {
        if (-not $DryRun) {
            # to the Recycle Bin, never Remove-Item (rule 50): a hard delete took AMF-W3's 1.0.3 No Installer zip, 2026-10-11
            if ($stale.Count) { Add-Type -AssemblyName Microsoft.VisualBasic }
            foreach ($old in $stale) { [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($old.FullName, 'OnlyErrorDialogs', 'SendToRecycleBin') }
            if (-not $upToDate) { Copy-Item -LiteralPath $authoritativeZip -Destination $targetZipPath -Force }
        }
        $what = @()
        if (-not $upToDate) { $what += "copied $authoritativeZip -> $targetZipPath" }
        if ($stale.Count -gt 0) { $what += "removed $($stale.Count) other zip(s) of this mod from the distro folder: $([string]::Join(', ', ($stale | ForEach-Object Name)))" }
        Add-Result -Check 'Distro package zip is the newest finalized package, and the only one' -Status FIXED -Detail ([string]::Join('; ', $what))
    }
} else {
    Add-Result -Check 'Distro package zip is the newest finalized package, and the only one' -Status SKIP -Detail "No authoritative .zip for v$Version found yet in '10. finalized mods' or '7. current test builds' - re-run this script after the package has been moved and zipped (nexus-distro-sweep.ps1 reports every mod's distro zip against the newest finalized version)."
}
}   # end of the zip part (section 4)

# ===========================================================================
# 5. 1920x1080 banner version pill
# ===========================================================================

if ($Part -ne 'Zip') {

$bannerHtml = Join-Path $nexusDir 'banner-1920x1080.html'
$bannerPng = Join-Path $nexusDir 'mod-page-banner-1920x1080.png'
$edgePath = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'

if ($optInfo) {
    Add-Result -Check '1920x1080 banner version pill' -Status SKIP -Detail "Optional file of '$($optInfo.parent)': the banner is the parent's."
} elseif (Test-Path -LiteralPath $bannerHtml) {
    $htmlText = Get-Content -LiteralPath $bannerHtml -Raw
    $pillMatch = [regex]::Match($htmlText, '<div class="pill">v(\d+\.\d+\.\d+)</div>')
    if ($pillMatch.Success -and $pillMatch.Groups[1].Value -ne $Version) {
        $oldPill = $pillMatch.Groups[1].Value
        $newHtml = $htmlText -replace [regex]::Escape("<div class=`"pill`">v$oldPill</div>"), "<div class=`"pill`">v$Version</div>"
        if (-not $DryRun) {
            Set-Content -LiteralPath $bannerHtml -Value $newHtml -NoNewline
            if (Test-Path -LiteralPath $edgePath) {
                & $edgePath --headless --disable-gpu --window-size=1920,1080 "--screenshot=$bannerPng" $bannerHtml 2>$null | Out-Null
            }
        }
        if ((Test-Path -LiteralPath $edgePath) -or $DryRun) {
            Add-Result -Check '1920x1080 banner version pill' -Status FIXED -Detail "Pill corrected v$oldPill -> v$Version and re-rasterized via headless Edge."
        } else {
            Add-Result -Check '1920x1080 banner version pill' -Status FLAGGED -Detail "Pill corrected in HTML (v$oldPill -> v$Version) but msedge.exe not found at $edgePath - PNG NOT re-rasterized, needs a manual re-render."
        }
    } elseif ($pillMatch.Success) {
        Add-Result -Check '1920x1080 banner version pill' -Status CURRENT -Detail "Pill already reads v$Version."
    } else {
        Add-Result -Check '1920x1080 banner version pill' -Status SKIP -Detail 'No version-pill-shaped <div class="pill">vX.Y.Z</div> found in banner-1920x1080.html.'
    }
} else {
    Add-Result -Check '1920x1080 banner version pill' -Status SKIP -Detail 'No banner-1920x1080.html found in the distro folder.'
}
}   # end of the text part (section 5)

# ===========================================================================
# Report
# ===========================================================================

Write-Host ''
Write-Host "Results for '$ModName' v$Version$(if ($Part -ne 'All') { " (part: $Part)" })" -ForegroundColor Cyan
Write-Host ("=" * 70)
foreach ($r in $results) {
    $color = switch ($r.Status) {
        'CURRENT' { 'Green' }
        'FIXED' { 'Cyan' }
        'FLAGGED' { 'Yellow' }
        'SKIP' { 'DarkGray' }
    }
    Write-Host ("[{0,-8}] {1}" -f $r.Status, $r.Check) -ForegroundColor $color
    foreach ($line in ($r.Detail -split "`n")) { Write-Host "           $line" -ForegroundColor $color }
}

$fixedCount = @($results | Where-Object Status -eq 'FIXED').Count
$flaggedCount = @($results | Where-Object Status -eq 'FLAGGED').Count
$currentCount = @($results | Where-Object Status -eq 'CURRENT').Count
$skipCount = @($results | Where-Object Status -eq 'SKIP').Count

Write-Host ''
Write-Host ("=" * 70)
Write-Host "SUMMARY: $fixedCount FIXED, $flaggedCount FLAGGED (needs a human glance), $currentCount already CURRENT, $skipCount SKIP" -ForegroundColor $(if ($flaggedCount -gt 0) { 'Yellow' } else { 'Green' })
if ($DryRun) { Write-Host "(DRY RUN - nothing above was actually written)" -ForegroundColor Yellow }

# ---------------------------------------------------------------------------------------------
# Pipeline event log. The write lives HERE, in the script that performs the transition, so the
# stage cannot forget to record - a log an agent is trusted to remember to append to is twelve
# documents with extra syntax. It is never allowed to fail this script. A -Part Text / Zip run records nothing:
# finalize-mod.ps1 writes the one 'distro-synced' event once the zip is copied and verified (2026-10-13).
if (-not $DryRun -and $Part -eq 'All') {
    # The registry KEY for the event's subject.key (event log step 3, 2026-10-12), found the way the game is found
    # above: the entries whose displayName, key or repo is -ModName, narrowed by the caller's -RepoPath, then by the
    # game. Only a single entry gives a key - two left over means the key is not known, and none is passed.
    $logKey = $null
    try {
        $regForKey = Get-Content -LiteralPath $RegistryPath -Raw | ConvertFrom-Json
        $keyEnts = @($regForKey.PSObject.Properties | Where-Object { $_.Value.displayName -ieq $ModName -or $_.Name -ieq $ModName -or $_.Value.repo -ieq $ModName })
        if ($PSBoundParameters.ContainsKey('RepoPath') -and $keyEnts.Count -gt 1) { $byRepo = @($keyEnts | Where-Object { $_.Value.repo -ieq (Split-Path $RepoPath -Leaf) }); if ($byRepo.Count) { $keyEnts = $byRepo } }
        if ($Game -and $keyEnts.Count -gt 1) { $byGame = @($keyEnts | Where-Object { (Get-ModGame -Entry $_.Value -ProjectRoot $ProjectRoot) -eq $Game }); if ($byGame.Count) { $keyEnts = $byGame } }
        if ($keyEnts.Count -eq 1) { $logKey = $keyEnts[0].Name }
    } catch { }
    $plog = $PipelineLogPath
    if (Test-Path -LiteralPath $plog) {
        try { & $plog -Action record -Stage 11 -Event 'distro-synced' -Mod $ModName -Key $logKey -Version $Version -Evidence ("{0} fixed, {1} flagged for a human, {2} already current" -f $fixedCount, $flaggedCount, $currentCount) -By 'sync-nexus-distro.ps1' | Out-Null } catch { }
    }
}

exit 0
