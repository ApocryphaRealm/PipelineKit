<#
.SYNOPSIS
    Derives the current state of every mod in the pipeline from the folders themselves.

.DESCRIPTION
    CLAUDE.md rule 36. Answers "what stage is mod X at, and what is blocking it" mechanically,
    instead of requiring a read of queue.md + PROGRESS.md + ten folders' membership.

    Everything here is derived from disk. Nothing is read from prose, so this cannot drift
    away from reality the way a hand-maintained status section does. Read-only - it never
    moves, deletes, or edits anything.

.PARAMETER Root
    Project root. Defaults to <ROOT>.

.PARAMETER Mod
    Report on one mod only (substring match on the mod name).

.PARAMETER Json
    Emit the mod table as JSON instead of formatted text, for another script to consume.

.EXAMPLE
    .\pipeline-status.ps1
    .\pipeline-status.ps1 -Mod "Auto Draw"
    .\pipeline-status.ps1 -Json
#>
[CmdletBinding()]
param(
    [string]$Root = $env:PIPELINE_ROOT,
    [string]$Mod,
    [switch]$Json
)

$ErrorActionPreference = 'Stop'
if (-not $Root) { $_kitRoot = $PSScriptRoot; while ($_kitRoot -and (Split-Path $_kitRoot -Leaf) -ne '.MD') { $_kitRoot = Split-Path $_kitRoot -Parent }; if ($_kitRoot) { $_kitRoot = Split-Path $_kitRoot -Parent }; $Root = $_kitRoot }   # kit: <ROOT> is the folder above the .MD this script sits under, unless PIPELINE_ROOT says otherwise

# --- constants -------------------------------------------------------------------------

$VERSION_CAP = 5          # rule 23 - versions kept per mod in 7. current test builds
$VERSION_RE  = '^(?<name>.+?)\s+(?<ver>\d+\.\d+\.\d+)$'

$PIPELINE_FOLDERS = @(
    '1. mod sorter',
    '2. Mod Types',
    '3. analyze mods',
    '4. plans',
    '5. current project mod',
    '6. current wip mods',
    '7. current test builds',
    '8. confirm compatibility',
    '9. patches output',
    '10. finalized mods',
    '11. Nexus distro',
    '12. needs an update'
)

$warnings = New-Object System.Collections.ArrayList

function Add-Warning([string]$text) { [void]$warnings.Add($text) }

function Get-Children([string]$relative) {
    $p = Join-Path $Root $relative
    if (-not (Test-Path -LiteralPath $p)) { return @() }
    return @(Get-ChildItem -LiteralPath $p -Force -ErrorAction SilentlyContinue |
        Where-Object { @('desktop.ini', 'Thumbs.db') -notcontains $_.Name })
}

# Split "Dragon's Eye Minimap 1.5.1" into name + [version].
function Split-Package([string]$folderName) {
    if ($folderName -match $VERSION_RE) {
        return [pscustomobject]@{ Name = $Matches['name']; Version = [version]$Matches['ver'] }
    }
    return $null
}

function Format-Version($v) {
    if ($null -eq $v) { return '-' }
    return $v.ToString()
}

# --- gather ----------------------------------------------------------------------------

# Packages sit in "<stage>\<Game> - <Mod>\" since 2026-10-01 (Find-Packages, distro-names.ps1), so a mod is keyed by
# that folder's name - "Skyrim - HUD Position Manager" and "Oblivion Remastered - HUD Position Manager" are two mods,
# and the key is also the mod's distro folder name. A package still flat in a stage root keys by its plain name.
. (Join-Path $PSScriptRoot 'distro-names.ps1')
$plainName = @{}
function Get-ModKey($pkg) {
    $k = if ($pkg.PkgFlat) { $pkg.PkgMod } else { Split-Path $pkg.PkgRoot -Leaf }
    $script:plainName[$k] = $pkg.PkgMod
    return $k
}

# 7. current test builds -> newest version per mod, plus how many are being kept.
$testBuilds = @{}
foreach ($d in @(Find-Packages -Root (Join-Path $Root '7. current test builds') -Folders -ProjectRoot $Root)) {
    if ($d.PkgTail) {
        Add-Warning "7. current test builds: '$($d.Name)' has no trailing X.Y.Z version (rule 7)"
        continue
    }
    $key = Get-ModKey $d
    if (-not $testBuilds.ContainsKey($key)) {
        $testBuilds[$key] = @{ Versions = New-Object System.Collections.ArrayList }
    }
    [void]$testBuilds[$key].Versions.Add($d.PkgVersion)
}

# 10. finalized mods -> newest finalized version per mod, and whether a .zip exists (rule 21).
$finalized = @{}
$finPkgs = @(Find-Packages -Root (Join-Path $Root '10. finalized mods') -ProjectRoot $Root | Where-Object { -not $_.PkgTail })
foreach ($d in @($finPkgs | Where-Object { $_.PSIsContainer })) {
    $key = Get-ModKey $d
    if (-not $finalized.ContainsKey($key)) {
        $finalized[$key] = @{ Version = $d.PkgVersion; Zip = $false }
    }
    elseif ($d.PkgVersion -gt $finalized[$key].Version) {
        $finalized[$key].Version = $d.PkgVersion
    }
}
foreach ($f in @($finPkgs | Where-Object { -not $_.PSIsContainer -and $_.Extension -eq '.zip' })) {
    $key = Get-ModKey $f
    if ($finalized.ContainsKey($key) -and $f.PkgVersion -eq $finalized[$key].Version) {
        $finalized[$key].Zip = $true
    }
}

# 8. confirm compatibility -> which mods have a verdict on record (rule 15).
$verdicts = @{}
foreach ($f in (Get-Children '8. confirm compatibility')) {
    if ($f.Name -like '*- compatibility.txt') {
        $verdicts[($f.Name -replace ' - compatibility\.txt$', '')] = $f.LastWriteTime
    }
}

# Nexus distro -> which mods have material written (rule 10).
$distro = @{}
foreach ($d in (Get-Children '11. Nexus distro')) {
    if ($d.PSIsContainer) { $distro[$d.Name] = $true }
}

# 6. current wip mods -> which mods have a live source repo.
$wip = @{}
foreach ($d in (Get-Children '6. current wip mods')) {
    if ($d.PSIsContainer) { $wip[$d.Name] = $d.FullName }
}

# 12. needs an update -> anything flagged as having drifted.
$needsUpdate = @{}
foreach ($d in (Get-Children '12. needs an update')) { $needsUpdate[$d.Name] = $true }

# --- per-mod report --------------------------------------------------------------------

# A mod is something that has actually been built. A Nexus distro folder alone doesn't make
# one - the request-hub guide page lives there too, and it is a page, not a mod.
$names = New-Object System.Collections.ArrayList
foreach ($k in $testBuilds.Keys) { if (-not $names.Contains($k)) { [void]$names.Add($k) } }
foreach ($k in $finalized.Keys)  { if (-not $names.Contains($k)) { [void]$names.Add($k) } }

$distroOnly = @($distro.Keys | Where-Object { -not $names.Contains($_) } | Sort-Object)

if ($Mod) { $names = @($names | Where-Object { $_ -like "*$Mod*" }) }

$rows = New-Object System.Collections.ArrayList

foreach ($name in ($names | Sort-Object)) {
    $latestTest = $null
    $kept = 0
    if ($testBuilds.ContainsKey($name)) {
        $sorted = @($testBuilds[$name].Versions | Sort-Object)
        $latestTest = $sorted[-1]
        $kept = $sorted.Count
    }

    $finalVer = $null
    $hasZip = $false
    if ($finalized.ContainsKey($name)) {
        $finalVer = $finalized[$name].Version
        $hasZip = $finalized[$name].Zip
    }

    $plain = if ($plainName.ContainsKey($name)) { $plainName[$name] } else { $name }   # verdicts and repos carry the plain name
    $hasVerdict = $verdicts.ContainsKey($plain)
    $hasDistro  = $distro.ContainsKey($name)

    # Stage and next blocking condition, in the order the pipeline actually gates them.
    $stage = 'unknown'
    $blocker = ''

    if ($null -eq $latestTest -and $null -eq $finalVer) {
        $stage = 'no build'
        $blocker = 'nothing packaged yet'
    }
    elseif ($null -ne $finalVer -and ($null -eq $latestTest -or $finalVer -ge $latestTest)) {
        $stage = 'finalized'
        if (-not $hasZip) {
            $blocker = "no .zip for $(Format-Version $finalVer) (rule 21)"
        }
        elseif (-not $hasDistro) {
            $blocker = 'no Nexus distro material (rule 10) - needs a content-writing pass'
        }
        elseif ($needsUpdate.ContainsKey($name)) {
            $blocker = 'dependency drift flagged (rule 1) - requeue as dep-update'
        }
        else {
            $blocker = 'none - shippable'
        }
    }
    else {
        # A test build exists that is newer than anything finalized.
        $stage = 'test build'
        $ahead = 0
        if ($null -ne $finalVer) {
            $ahead = @($testBuilds[$name].Versions | Where-Object { $_ -gt $finalVer }).Count
        }
        else {
            $ahead = $kept
        }

        if (-not $hasVerdict) {
            $blocker = "no compatibility verdict (rule 15) - $ahead version(s) past finalized"
        }
        elseif ($ahead -ge $VERSION_CAP) {
            $blocker = "$ahead versions past finalized - rule 21 says stop deferring"
        }
        else {
            $blocker = "awaiting in-game confirmation (rule 21) - $ahead version(s) past finalized"
        }
    }

    if ($kept -gt $VERSION_CAP) {
        Add-Warning "7. current test builds: '$name' keeps $kept versions, cap is $VERSION_CAP (rule 23)"
    }

    [void]$rows.Add([pscustomobject]@{
        Mod        = $name
        Stage      = $stage
        Repo       = $(if ($wip.ContainsKey($plain)) { 'yes' } else { '-' })
        TestBuild  = Format-Version $latestTest
        Kept       = $kept
        Finalized  = Format-Version $finalVer
        Zip        = $(if ($hasZip) { 'yes' } elseif ($null -ne $finalVer) { 'NO' } else { '-' })
        Verdict    = $(if ($hasVerdict) { 'yes' } else { 'NO' })
        Distro     = $(if ($hasDistro) { 'yes' } elseif ($null -ne $finalVer) { 'NO' } else { '-' })
        NextAction = $blocker
    })
}

if ($Json) {
    $rows | ConvertTo-Json -Depth 4
    exit 0
}

# --- folder occupancy ------------------------------------------------------------------

Write-Output ''
Write-Output '=== PIPELINE OCCUPANCY ==============================================='
foreach ($rel in $PIPELINE_FOLDERS) {
    $items = Get-Children $rel
    $note = ''
    switch ($rel) {
        '1. mod sorter'          { if ($items.Count -gt 0) { $note = '<- untriaged (rule 1)' } }
        '3. analyze mods'        { if ($items.Count -gt 0) { $note = '<- research in flight (rule 13)' } }
        '4. plans'               { if ($items.Count -gt 0) { $note = '<- plan written, build not started (rule 12)' } }
        '5. current project mod' { if ($items.Count -gt 1) { $note = '<- should hold ONE active project (rule 1/25)' } }
        '12. needs an update'    { if ($items.Count -gt 0) { $note = '<- drifted, needs requeue (rule 1)' } }
    }
    Write-Output ('  {0,-26} {1,4}  {2}' -f $rel, $items.Count, $note)
}

# --- mod table -------------------------------------------------------------------------

Write-Output ''
Write-Output '=== MODS ============================================================='
if ($rows.Count -eq 0) {
    Write-Output '  (no mods found)'
}
else {
    $rows | Format-Table Mod, Stage, TestBuild, Kept, Finalized, Zip, Verdict, Distro -AutoSize | Out-String -Width 200 | Write-Output
    Write-Output '--- next action per mod ---'
    foreach ($r in $rows) {
        Write-Output ('  {0,-44} {1}' -f $r.Mod, $r.NextAction)
    }
}

if ($distroOnly.Count -gt 0 -and -not $Mod) {
    Write-Output ''
    Write-Output '--- Nexus distro material with no build (pages, not mods) ---'
    foreach ($d in $distroOnly) { Write-Output ('  {0}' -f $d) }
}

# --- watcher health --------------------------------------------------------------------

Write-Output ''
Write-Output '=== WATCHER =========================================================='
foreach ($t in @('SkyrimMods-IntakeWatcher', 'SkyrimMods-Reconcile', 'SkyrimMods-RequestHubPoll', 'SkyrimMods-UpdateCheck')) {
    $task = Get-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue
    if ($null -eq $task) {
        Write-Output ('  {0,-28} NOT REGISTERED' -f $t)
        Add-Warning "scheduled task '$t' is not registered (rule 27/35)"
    }
    else {
        Write-Output ('  {0,-28} {1}' -f $t, $task.State)
    }
}

$queueFile = Join-Path $Root '.MD\watcher\queue.jsonl'
if (Test-Path -LiteralPath $queueFile) {
    $lines = @(Get-Content -LiteralPath $queueFile | Where-Object { $_.Trim() -ne '' })
    Write-Output ('  {0,-28} {1} unconsumed event(s)' -f 'queue.jsonl', $lines.Count)
    if ($lines.Count -gt 50) {
        Add-Warning "queue.jsonl has $($lines.Count) unconsumed events - run consume-queue.ps1 (rule 27)"
    }
}

$hubQueue = Join-Path $Root '.MD\watcher\request-hub-queue.jsonl'
if (Test-Path -LiteralPath $hubQueue) {
    $hubLines = @(Get-Content -LiteralPath $hubQueue | Where-Object { $_.Trim() -ne '' -and $_ -notmatch '"_header"' })
    Write-Output ('  {0,-28} {1} unconsumed submission(s)' -f 'request-hub-queue.jsonl', $hubLines.Count)
}
else {
    Write-Output ('  {0,-28} none yet' -f 'request-hub-queue.jsonl')
}

# --- warnings --------------------------------------------------------------------------

Write-Output ''
Write-Output '=== RULE VIOLATIONS =================================================='
if ($warnings.Count -eq 0) {
    Write-Output '  none'
}
else {
    foreach ($w in $warnings) { Write-Output ("  ! " + $w) }
}
Write-Output ''

if ($warnings.Count -gt 0) { exit 1 }
exit 0
