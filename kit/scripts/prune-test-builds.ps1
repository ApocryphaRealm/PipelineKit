<#
.SYNOPSIS
    Enforces rule 7/23's cap on 7. current test builds - the current build plus one previous version per mod (the
    owner, 2026-10-12; it was five until 2026-09-28, then one) - and holds the MO2
    instances to one installed version per mod.

.DESCRIPTION
    CLAUDE.md rule 36. The cap used to be enforced only when the owner typed "trim the fat", which
    made it a cleanup habit rather than a cap - two mods (Local Map Upgrade, Compass Navigation
    Overhaul) had drifted to nine versions each before anything noticed.

    Call this at the END of packaging, with -Apply and -ModName, and the cap becomes an
    invariant that cannot drift. Called with no -ModName it sweeps every mod, which is what
    the "trim the fat" command now runs.

    Versions sort numerically via [version], so 1.1.10 is correctly newer than 1.1.9 - the
    string-sort trap rule 23 calls out by name.

    WHAT IT COUNTS AS ONE VERSION (corrected 2026-09-08)
    ----------------------------------------------------
    Until that fix the script matched only directories whose name ENDED in the version, so it
    was blind to two things and quietly reported itself satisfied while the cap was broken:
    FOMOD packages never matched at all, and the .zip beside each package was never enumerated,
    so pruning a folder orphaned its archive. Now a PACKAGE FAMILY is the base name plus an
    optional recognised variant suffix (FOMOD), and one VERSION within a family covers both its
    folder and its .zip, pruned together. Anything else after the version - "1.6.1-menumode",
    "AE test build" - is a labelled diagnostic package, is not a version, and is left alone.

    THE MO2 SWEEP (added 2026-09-08)
    --------------------------------
    The instances accumulate the same way and worse: 71 stale folders and 1.87 GB across Apostasy
    and SME, some of them still switched on in profiles that had simply never been moved forward.
    So this now also sweeps `<instance>\mods`, where the rule is different from the archive's:
    an instance needs ONE version of each mod, because 7. current test builds is the archive and
    every version is a tag in its repository as well.

    For each mod family in an instance it keeps the newest installed version and, before deleting
    anything:

      * Any profile that has an OLDER version enabled is rewritten to the newest, in place, so the
        mod keeps its priority position and exactly one version stays enabled. Two versions of one
        DLL-providing mod enabled at once is the usvfs split-brain in the logic library, so the
        rewrite removes every other line for that family rather than just flipping a flag.
      * An older folder is NOT deleted if it ships a plugin file the newest version does not - that
        would strand a plugins.txt entry. It is reported instead.
      * Modlist lines for deleted folders are removed, as are `[NoDelete]`-tagged lines pointing at
        folders that no longer exist at all.

    It refuses to touch an instance while MO2 or the game is running, because MO2 rewrites
    modlist.txt on exit and would undo the edit.

.PARAMETER ModName
    Prune one mod only, by its base name - this covers that mod's plain and FOMOD families both,
    and its installed folders in the instances. Omit to sweep everything.

.PARAMETER Game
    Prune only that game's packages (Skyrim, Oblivion Remastered, MO2) - its "<Game> - <Mod>" folder in 7. current test
    builds (2026-10-01). A game other than Skyrim also leaves the MO2 instances below alone: they are Skyrim instances,
    and a name two games share ("HUD Position Manager") must not reach the other game's installs.

.PARAMETER Apply
    Actually delete and rewrite. Without it this is a read-only report.

.PARAMETER Keep
    Versions to keep per family in 7. current test builds. Defaults to 2 - the current build and ONE previous version
    (rule 23; the owner, 2026-10-12: "we only keep 1 previous version at a time not 5 from now on"). Was 1 from
    2026-09-28 ("we only need to keep the current copies and not 5 versions").

.PARAMETER KeepInstalled
    Versions to keep per mod inside each MO2 instance. Defaults to 1.

.PARAMETER SkipMO2
    Sweep only 7. current test builds and leave the instances alone.

.EXAMPLE
    .\prune-test-builds.ps1
    .\prune-test-builds.ps1 -Apply
    .\prune-test-builds.ps1 -ModName "Local Map Upgrade" -Apply
#>
[CmdletBinding()]
param(
    [string]$Root = $env:PIPELINE_ROOT,
    [string]$ModName,
    [string]$Game,
    [switch]$Apply,
    [int]$Keep = 2,
    [int]$KeepInstalled = 1,
    [switch]$SkipMO2,
    [string[]]$Instances = @(($env:PIPELINE_MO2_INSTANCES -split ';') | Where-Object { $_ } | ForEach-Object { Split-Path $_ -Parent })
)
# Removal goes to the Recycle Bin, never a permanent delete (the owner empties the bin himself).
Add-Type -AssemblyName Microsoft.VisualBasic
# ...and only while the bin keeps what it is given (pipeline assessment item 8, 2026-10-27): role storage-sense-check
# exits 3 when Windows Storage Sense would purge it - then -Apply recycles nothing.
if ($Apply) {
    $ssResolver = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\resolvers\resolve.py'))
    $ssCheck = @(& py -3 $ssResolver find storage-sense-check 2>$null)
    if ($LASTEXITCODE -eq 0 -and $ssCheck.Count -and (Test-Path -LiteralPath "$($ssCheck[0])".Trim())) {
        $ssOut = @(& py -3 "$($ssCheck[0])".Trim())
        if ($LASTEXITCODE -eq 3) {
            Write-Output "prune-test-builds: REFUSED - nothing recycled: $($ssOut[0]). Turn Storage Sense's Recycle Bin clean-up off first."
            exit 3
        }
    }
}
function Send-ToRecycleBin([string]$Path) {
    if (Test-Path -LiteralPath $Path -PathType Container) {
        [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory($Path, 'OnlyErrorDialogs', 'SendToRecycleBin')
    } elseif (Test-Path -LiteralPath $Path) {
        [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($Path, 'OnlyErrorDialogs', 'SendToRecycleBin')
    }
}

$ErrorActionPreference = 'Stop'
if (-not $Root) { $_kitRoot = $PSScriptRoot; while ($_kitRoot -and (Split-Path $_kitRoot -Leaf) -ne '.MD') { $_kitRoot = Split-Path $_kitRoot -Parent }; if ($_kitRoot) { $_kitRoot = Split-Path $_kitRoot -Parent }; $Root = $_kitRoot }   # kit: <ROOT> is the folder above the .MD this script sits under, unless PIPELINE_ROOT says otherwise

$buildsDir    = Join-Path $Root '7. current test builds'
$finalizedDir = Join-Path $Root '10. finalized mods'

# Recognised packaging variants. A suffix NOT on this list means the entry is a labelled
# diagnostic package rather than a release package, and rule 23 says to leave those alone.
$VARIANTS = @('FOMOD')

# [optional [NoDelete] NNNN ] <base name> <X.Y.Z> [ <variant>]
$VERSION_RE = '^(?<tag>\[NoDelete\]\s+\d+\s+)?(?<name>.+?)\s+(?<ver>\d+\.\d+\.\d+)(?:\s+(?<variant>\S+))?$'

. (Join-Path $PSScriptRoot 'distro-names.ps1')   # Get-PackageGame (2026-09-29)

function Get-PackageId {
    <# Splits a folder or zip stem into its family and version, or $null if it is not a
       versioned release package. The [NoDelete] NNNN prefix is PART of the family: two mods can
       share a slot number, and an old slot number is a different install from a new one. #>
    param([string]$Stem)

    if ($Stem -notmatch $VERSION_RE) { return $null }
    $variant = $Matches['variant']
    if ($variant -and ($VARIANTS -notcontains $variant)) { return $null }

    $family = ($Matches['tag'] + $Matches['name'])
    if ($variant) { $family = "$family $variant" }

    [pscustomobject]@{
        Family  = $family
        Base    = $Matches['name']
        Version = [version]$Matches['ver']
    }
}

function Test-GameRunning {
    $p = Get-Process -Name 'ModOrganizer', 'SkyrimSE', 'skse64_loader' -ErrorAction SilentlyContinue
    return [bool]$p
}

if (-not (Test-Path -LiteralPath $buildsDir)) {
    Write-Output "7. current test builds not found at $buildsDir"
    exit 1
}

# Which version of each mod is currently finalized - reported, not protected.
# Packages sit in "<stage>\<Game> - <Mod>\" since 2026-10-01 (Find-Packages, distro-names.ps1); keyed "<base>|<game>".
$finalizedVer = @{}
if (Test-Path -LiteralPath $finalizedDir) {
    foreach ($d in @(Find-Packages -Root $finalizedDir -ModName $ModName -Game $Game -Folders -IncludeSymbols -ProjectRoot $Root)) {
        $id = Get-PackageId $d.Name
        if (-not $id) { continue }
        $fk = "$($id.Base)|$($d.PkgGame)"
        if (-not $finalizedVer.ContainsKey($fk) -or $id.Version -gt $finalizedVer[$fk]) { $finalizedVer[$fk] = $id.Version }
    }
}

$totalPruned = 0

########################################################################################
## 1. The archive: 7. current test builds, capped at -Keep versions per family
########################################################################################

Write-Output '== 7. current test builds =='

$byFamily = @{}
$entries = @(Find-Packages -Root $buildsDir -ModName $ModName -Game $Game -IncludeSymbols -ProjectRoot $Root |
             Where-Object { $_.PSIsContainer -or $_.Extension -eq '.zip' })

foreach ($e in $entries) {
    # A package's zip carries the same name as its folder; compare on the stem.
    $stem = if ($e.PSIsContainer) { $e.Name } else { $e.BaseName }
    $id = Get-PackageId $stem
    if (-not $id) { continue }
    if ($ModName -and $id.Base -ne $ModName) { continue }
    # 2026-09-29: two games' mods can share a plain name (Apocrypha Menu Framework - Oblivion Remastered 1.0.4 beside
    # Skyrim 1.8.1); the family carries the GAME - its game folder (2026-10-01), else its contents - so one never
    # prunes the other.
    $game = $e.PkgGame
    if (-not $game) { try { $game = Get-PackageGame -Path $e.FullName } catch { } }
    $id | Add-Member -NotePropertyName Game -NotePropertyValue $game -Force
    if ($game) { $id.Family = "$($id.Family) [$game]" }

    if (-not $byFamily.ContainsKey($id.Family)) { $byFamily[$id.Family] = @{} }
    $key = $id.Version.ToString()
    if (-not $byFamily[$id.Family].ContainsKey($key)) {
        $byFamily[$id.Family][$key] = [pscustomobject]@{
            Version = $id.Version; Base = $id.Base; Game = $id.Game; Items = New-Object System.Collections.ArrayList
        }
    }
    [void]$byFamily[$id.Family][$key].Items.Add($e)
}

foreach ($family in ($byFamily.Keys | Sort-Object)) {
    $versions = @($byFamily[$family].Values | Sort-Object Version -Descending)
    if ($versions.Count -le $Keep) { continue }

    $prune = $versions[$Keep..($versions.Count - 1)]
    Write-Output ("  {0}: {1} version(s), cap {2} -> pruning {3}" -f $family, $versions.Count, $Keep, $prune.Count)

    foreach ($p in $prune) {
        $note = ''
        if ($finalizedVer.ContainsKey("$($p.Base)|$($p.Game)") -and $finalizedVer["$($p.Base)|$($p.Game)"] -eq $p.Version) {
            $note = '  (finalized - preserved in 10. finalized mods)'
        }
        # The folder and its zip are one version and go together.
        foreach ($item in $p.Items) {
            if ($Apply) {
                Send-ToRecycleBin $item.FullName
                Write-Output ("      removed {0}{1}" -f $item.Name, $note)
            }
            else {
                Write-Output ("      would remove {0}{1}" -f $item.Name, $note)
            }
            $note = ''
        }
        $totalPruned++
    }

    $kept = $versions[0..([Math]::Min($Keep, $versions.Count) - 1)] | ForEach-Object { $_.Version.ToString() }
    Write-Output ("      kept: {0}" -f ($kept -join ', '))
}

if ($totalPruned -eq 0) { Write-Output '  all families within cap' }

########################################################################################
## 2. The MO2 instances: one installed version per mod, and no profile left on an old one
########################################################################################

$mo2Removed = 0
$mo2Swapped = 0

if (-not $SkipMO2) {
    Write-Output ''
    Write-Output '== MO2 instances =='

    if ($Game -and (ConvertTo-DistroGame $Game) -ne 'Skyrim') {
        Write-Output "  SKIPPED - these are Skyrim instances and -Game is $Game."
    }
    elseif (Test-GameRunning) {
        Write-Output '  SKIPPED - MO2 or the game is running. MO2 rewrites modlist.txt when it exits,'
        Write-Output '  which would undo these edits. Close it and run again.'
    }
    else {
        foreach ($inst in $Instances) {
            $modsDir  = Join-Path $inst 'mods'
            $profsDir = Join-Path $inst 'profiles'
            if (-not (Test-Path -LiteralPath $modsDir)) { continue }

            $instName = Split-Path $inst -Leaf

            # Families present in this instance
            $fam = @{}
            foreach ($d in (Get-ChildItem -LiteralPath $modsDir -Directory -Force -ErrorAction SilentlyContinue)) {
                $id = Get-PackageId $d.Name
                if (-not $id) { continue }
                if ($ModName -and $id.Base -ne $ModName) { continue }
                if (-not $fam.ContainsKey($id.Family)) { $fam[$id.Family] = New-Object System.Collections.ArrayList }
                [void]$fam[$id.Family].Add([pscustomobject]@{ Version = $id.Version; Name = $d.Name; Path = $d.FullName })
            }

            $profiles = @()
            if (Test-Path -LiteralPath $profsDir) {
                $profiles = @(Get-ChildItem -LiteralPath $profsDir -Directory -Force -ErrorAction SilentlyContinue)
            }

            $instRemoved = 0; $instSwapped = 0; $instBytes = 0
            $stranded = New-Object System.Collections.ArrayList

            foreach ($family in ($fam.Keys | Sort-Object)) {
                $versions = @($fam[$family] | Sort-Object Version -Descending)
                if ($versions.Count -le $KeepInstalled) { continue }

                $newest = $versions[0]
                $old    = $versions[$KeepInstalled..($versions.Count - 1)]

                # -- a) any profile still on an old version moves to the newest, in place --
                foreach ($prof in $profiles) {
                    $ml = Join-Path $prof.FullName 'modlist.txt'
                    if (-not (Test-Path -LiteralPath $ml)) { continue }

                    $lines = [System.IO.File]::ReadAllLines($ml)
                    $names = $versions | ForEach-Object { $_.Name }
                    $enabledOld = @($lines | Where-Object { $_.StartsWith('+') -and ($old.Name -contains $_.Substring(1)) })
                    if ($enabledOld.Count -eq 0) { continue }

                    $out = New-Object System.Collections.ArrayList
                    $placed = $false
                    foreach ($l in $lines) {
                        $bare = $l.TrimStart('+', '-')
                        if ($names -contains $bare) {
                            if (-not $placed) { [void]$out.Add('+' + $newest.Name); $placed = $true }
                            continue      # every other version's line for this family goes
                        }
                        [void]$out.Add($l)
                    }
                    if ($Apply) { [System.IO.File]::WriteAllLines($ml, $out) }
                    Write-Output ("  {0}/{1}: {2} -> {3}" -f $instName, $prof.Name,
                                  $enabledOld[0].Substring(1), $newest.Name)
                    $instSwapped++
                }

                # -- b) delete the old folders, unless one strands a plugin --
                $newestPlugins = @(Get-ChildItem -LiteralPath $newest.Path -Recurse -File -Force -ErrorAction SilentlyContinue |
                                   Where-Object { $_.Extension -match '^\.es[pml]$' } | ForEach-Object { $_.Name })
                foreach ($o in $old) {
                    $oldPlugins = @(Get-ChildItem -LiteralPath $o.Path -Recurse -File -Force -ErrorAction SilentlyContinue |
                                    Where-Object { $_.Extension -match '^\.es[pml]$' } | ForEach-Object { $_.Name })
                    $missing = @($oldPlugins | Where-Object { $newestPlugins -notcontains $_ })
                    if ($missing.Count -gt 0) {
                        [void]$stranded.Add(("{0}  (ships {1}, which {2} does not)" -f $o.Name, ($missing -join ', '), $newest.Name))
                        continue
                    }
                    $bytes = (Get-ChildItem -LiteralPath $o.Path -Recurse -File -Force -ErrorAction SilentlyContinue |
                              Measure-Object -Property Length -Sum).Sum
                    if ($null -eq $bytes) { $bytes = 0 }
                    if ($Apply) { Send-ToRecycleBin $o.Path }
                    $instRemoved++; $instBytes += $bytes
                }
            }

            # -- c) drop modlist lines for folders that no longer exist (ours only) --
            $present = @{}
            foreach ($d in (Get-ChildItem -LiteralPath $modsDir -Directory -Force -ErrorAction SilentlyContinue)) { $present[$d.Name] = $true }
            $staleDropped = 0
            foreach ($prof in $profiles) {
                $ml = Join-Path $prof.FullName 'modlist.txt'
                if (-not (Test-Path -LiteralPath $ml)) { continue }
                $lines = [System.IO.File]::ReadAllLines($ml)
                $out = New-Object System.Collections.ArrayList
                foreach ($l in $lines) {
                    $bare = $l.TrimStart('+', '-')
                    # only ever drop OUR OWN installs - the [NoDelete] NNNN convention - so a
                    # third-party line is never touched even if its folder is missing.
                    if ($bare -match '^\[NoDelete\]\s+\d+\s' -and -not $present.ContainsKey($bare)) {
                        $staleDropped++
                        continue
                    }
                    [void]$out.Add($l)
                }
                if ($staleDropped -gt 0 -and $Apply) { [System.IO.File]::WriteAllLines($ml, $out) }
            }

            if ($instRemoved -eq 0 -and $instSwapped -eq 0 -and $staleDropped -eq 0) {
                Write-Output ("  {0}: already one version per mod" -f $instName)
            }
            else {
                $verb = if ($Apply) { 'removed' } else { 'would remove' }
                Write-Output ("  {0}: {1} {2} old folder(s), {3:N0} MB; {4} profile swap(s); {5} stale line(s)" -f `
                              $instName, $verb, $instRemoved, ($instBytes / 1MB), $instSwapped, $staleDropped)
            }
            foreach ($s in $stranded) { Write-Output ("      KEPT {0}" -f $s) }

            $mo2Removed += $instRemoved; $mo2Swapped += $instSwapped
        }
    }
}

########################################################################################

if ($Apply -and ($totalPruned -gt 0 -or $mo2Removed -gt 0)) {
    $plog = Join-Path $PSScriptRoot 'pipeline-log.ps1'
    if (Test-Path -LiteralPath $plog) {
        $modLabel = if ($ModName) { $ModName } else { 'all mods' }
        try {
            & $plog -Action record -Stage 7 -Event 'pruned' -Mod $modLabel `
                -Evidence ("{0} archive version(s) and {1} installed folder(s) removed; {2} profile swap(s)" -f $totalPruned, $mo2Removed, $mo2Swapped) `
                -By 'prune-test-builds.ps1' | Out-Null
        } catch { }
    }
}

if (-not $Apply) {
    Write-Output ''
    Write-Output 'Read-only. Re-run with -Apply to actually prune.'
}

exit 0
