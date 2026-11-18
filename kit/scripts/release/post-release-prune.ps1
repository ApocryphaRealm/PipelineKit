<#
.SYNOPSIS
    After a version is recorded POSTED: keep the current release and one previous in "10. finalized mods" (rule 23),
    send every older finalized folder and zip of that mod to the Recycle Bin, and prune its test builds.

.DESCRIPTION
    Written 2026-10-13 (straight flow, gate B). The clean-up used to be the last step of finalize-mod.ps1; it moved
    here because finalizing is not releasing - a number is spent by POSTING it (the owner, 2026-10-11), and the owner's
    rule is that steps run by themselves, never on his call. version-gate.ps1 runs this script for a posting that is
    NEW in a ledger write (2026-10-13, the clean-up trigger: 'posted' - nexus-upload.py, finalize-mod.ps1 for a 'local'
    mod, a hand record for Mega - and the postings Sync-Members and Sync-Nexus read off the 1. members folder and the
    Nexus page). A writing action (posted, bump, record) runs it at once; a read-only one leaves it pending on the
    ledger row (prunePending) for the next writing action. Never under -WhatIf; a problem here is printed as a warning
    and never fails the action.

    ONE EVENT per clean-up (2026-10-13): 'pruned' (kind prune, stage 10) through role pipeline-log, its evidence naming
    what was kept and what went to the Recycle Bin, and the test-build prune's lines. Not under -DryRun.

    What it keeps, for the mod's game only (the "<Game> - <Mod>" folder, and each item's contents read with
    Get-PackageGame - "Apocrypha Menu Framework" is a Skyrim and an Oblivion Remastered mod):
      - the posted version itself,
      - the newest finalized version below it (the "one previous" - the owner, 2026-10-12: "we only keep 1 previous
        version at a time"),
      - every finalized version ABOVE the posted one (finalized, not yet posted - never touched here).
    A version's folder ("<Mod> X.Y.Z" or "<Mod> X.Y.Z FOMOD") and its .zip count as one version. Everything older goes
    to the Recycle Bin (rule 50: never a permanent delete; the owner empties the bin himself). Then prune-test-builds.ps1
    -ModName -Game -Apply runs for 7. current test builds, as finalize-mod.ps1 ran it.

.PARAMETER Mod      Registry key, repo folder, alias or display name (version-registry.json).
.PARAMETER Version  The version just recorded posted.
.PARAMETER Root     The project root. Defaults to "<ROOT>".
.PARAMETER DryRun   Print what would go to the Recycle Bin; remove nothing and do not run prune-test-builds.

.EXAMPLE
    .\post-release-prune.ps1 -Mod SimpleLoadoutSystemOR -Version 1.0.3 -DryRun
#>
param(
    [Parameter(Mandatory = $true)][string]$Mod,
    [Parameter(Mandatory = $true)][ValidatePattern('^\d+\.\d+\.\d+$')][string]$Version,
    [string]$Root = $env:PIPELINE_ROOT,
    [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
if (-not $Root) { $_kitRoot = $PSScriptRoot; while ($_kitRoot -and (Split-Path $_kitRoot -Leaf) -ne '.MD') { $_kitRoot = Split-Path $_kitRoot -Parent }; if ($_kitRoot) { $_kitRoot = Split-Path $_kitRoot -Parent }; $Root = $_kitRoot }   # kit: <ROOT> is the folder above the .MD this script sits under, unless PIPELINE_ROOT says otherwise
# Every lookup goes through the resolver OF THIS TREE, never the absolute <ROOT> path: a copied tree (the
# tests) then answers inside its own copy.
$ResolverPy = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\resolvers\resolve.py'))
function Find-Role([string]$role) {
    $p = @(& py -3 $ResolverPy find $role)
    if ($LASTEXITCODE -ne 0 -or $p.Count -eq 0 -or -not "$($p[0])".Trim()) { Write-Output "post-release-prune: cannot resolve role '$role' ($($p -join ' '))"; exit 1 }
    return "$($p[0])".Trim()
}
. (Find-Role 'distro-names')
$reg = Get-Content -LiteralPath (Find-Role 'version-registry') -Raw | ConvertFrom-Json
$key = $null
foreach ($p in $reg.PSObject.Properties) {
    $v = $p.Value
    if ($p.Name -ieq $Mod -or $v.repo -ieq $Mod -or $v.displayName -ieq $Mod -or (@($v.aliases) -contains $Mod)) { $key = $p.Name; break }
}
if (-not $key) { Write-Output "post-release-prune: '$Mod' is not in version-registry.json - nothing pruned"; exit 1 }
$e = $reg.$key
$display = [string]$e.displayName
if (-not $display) { Write-Output "post-release-prune: $key has no displayName - nothing pruned"; exit 1 }
$modGame = Get-ModGame -Entry $e -ProjectRoot $Root
if (-not $modGame) { Write-Output "post-release-prune: cannot tell which game $key is for - nothing pruned"; exit 1 }
$finDir = Resolve-PackageRoot -Root (Join-Path $Root '10. finalized mods') -ModName $display -Game $modGame -ProjectRoot $Root
$cur = [version]$Version
Write-Output "post-release-prune  $key $Version  ($(Split-Path $finDir -Leaf); keeps $Version and one previous)"
$keptTxt = "$Version (nothing finalized here)"
$recycled = New-Object System.Collections.Generic.List[string]

# RECYCLING MUST BE REVERSIBLE (pipeline assessment item 8, 2026-10-27): while Windows Storage Sense would purge the
# Recycle Bin (role storage-sense-check exits 3), nothing is recycled - the posting this runs after is not undone.
if (-not $DryRun) {
    $ssCheck = @(& py -3 $ResolverPy find storage-sense-check 2>$null)
    if ($LASTEXITCODE -eq 0 -and $ssCheck.Count -and (Test-Path -LiteralPath "$($ssCheck[0])".Trim())) {
        $ssOut = @(& py -3 "$($ssCheck[0])".Trim())
        if ($LASTEXITCODE -eq 3) {
            Write-Output "  REFUSED to recycle - $($ssOut[0]). Nothing pruned; turn Storage Sense's Recycle Bin clean-up off and run post-release-prune again."
            exit 0
        }
    }
}
if (Test-Path -LiteralPath $finDir) {
    $rx = '^' + [regex]::Escape($display) + ' (\d+\.\d+\.\d+)( FOMOD)?(\.zip)?$'   # FOMOD releases too (2026-10-01)
    $all = @(Get-ChildItem -LiteralPath $finDir | Where-Object { $_.Name -match $rx } |
             Where-Object { (Get-PackageGame -Path $_.FullName) -eq $modGame })
    $verOf = { param($i) [version]([regex]::Match($i.Name, $rx).Groups[1].Value) }
    $below = @($all | ForEach-Object { & $verOf $_ } | Where-Object { $_ -lt $cur } | Sort-Object -Unique -Descending)
    $keepPrev = if ($below.Count) { $below[0] } else { $null }
    $old = @($all | Where-Object { $iv = & $verOf $_; $iv -lt $cur -and (-not $keepPrev -or $iv -ne $keepPrev) })
    if ($old.Count) { Add-Type -AssemblyName Microsoft.VisualBasic }
    foreach ($i in $old) {
        $rel = "10. finalized mods\$(Split-Path $finDir -Leaf)\$($i.Name)"
        if ($DryRun) { Write-Output "  would go to the Recycle Bin: $rel"; continue }
        if ($i.PSIsContainer) { [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory($i.FullName, 'OnlyErrorDialogs', 'SendToRecycleBin') }
        else { [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($i.FullName, 'OnlyErrorDialogs', 'SendToRecycleBin') }
        Write-Output "  to the Recycle Bin: $rel"
        $recycled.Add($i.Name)
    }
    Write-Output ("  kept: {0}{1}" -f $Version, $(if ($keepPrev) { " and $keepPrev" } else { ' (no earlier release)' }))
    $above = @($all | ForEach-Object { & $verOf $_ } | Where-Object { $_ -gt $cur } | Sort-Object -Unique)
    $keptTxt = "{0}{1}{2}" -f $Version, $(if ($keepPrev) { ", $keepPrev (one previous)" } else { ' (no earlier release)' }), $(if ($above.Count) { ", " + (($above | ForEach-Object { "$_" }) -join ', ') + ' (above it, not yet posted)' } else { '' })
} else {
    Write-Output "  no $(Split-Path $finDir -Leaf) folder in 10. finalized mods - nothing to keep or prune there"
}

if ($DryRun) { Write-Output '  dry run: prune-test-builds not run'; exit 0 }
$ptb = Find-Role 'prune-test-builds'
$ptbLines = @(& $ptb -Root $Root -ModName $display -Game $modGame -Apply 2>&1 | Where-Object { "$_" -match 'pruned|Recycle|removed' } | ForEach-Object { "$_".Trim() })
$ptbLines | ForEach-Object { "  $_" }

# ONE EVENT PER CLEAN-UP (2026-10-13): kind prune, the evidence naming what was kept and what went to the Recycle Bin.
# Never allowed to fail the clean-up (pipeline-log swallows its own errors; a missing role only skips the record).
$plog = "$(@(& py -3 $ResolverPy find pipeline-log 2>$null)[0])".Trim()
if ($plog -and $plog -notlike 'MISSING*' -and (Test-Path -LiteralPath $plog)) {
    $ev = "kept: $keptTxt; to the Recycle Bin: $(if ($recycled.Count) { $recycled -join ', ' } else { 'nothing' }); test builds: $(if ($ptbLines.Count) { $ptbLines -join ' | ' } else { 'nothing pruned' })"
    try { & $plog -Action record -Stage 10 -Event 'pruned' -Mod $display -Key $key -Version $Version -Evidence $ev -By 'post-release-prune.ps1' | Out-Null } catch { }
}
exit 0
