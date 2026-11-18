<#
.SYNOPSIS
    Runs package-gate.ps1 over EVERY mod in "11. Nexus distro", against the newest finalized
    package of the version the distro currently holds. One command answers "is anything in the
    distro wrong?" - the question that used to be answered from memory.
.DESCRIPTION
    For each distro folder: find its newest archive, read the version from the file name, find the
    matching folder in "10. finalized mods" (a "<name> <ver> FOMOD" folder wins over a plain one),
    and gate it. Prints one line per mod plus the hits. Exit 1 if any mod has a hit.
.EXAMPLE
    .\gate-sweep.ps1
    .\gate-sweep.ps1 -Only 'Item Explorer','Wheeler - Refined'
#>
param([string[]]$Only, [string]$Root = $env:PIPELINE_ROOT)
if (-not $Root) { $_kitRoot = $PSScriptRoot; while ($_kitRoot -and (Split-Path $_kitRoot -Leaf) -ne '.MD') { $_kitRoot = Split-Path $_kitRoot -Parent }; if ($_kitRoot) { $_kitRoot = Split-Path $_kitRoot -Parent }; $Root = $_kitRoot }   # kit: <ROOT> is the folder above the .MD this script sits under, unless PIPELINE_ROOT says otherwise
$gate = "$(@(& py -3 (Join-Path $PSScriptRoot '..\resolvers\resolve.py') find package-gate)[0])".Trim()   # by role (rule 70)
$distro = Join-Path $Root '11. Nexus distro'
. "$PSScriptRoot\distro-names.ps1"   # the folder is "<Game> - <Mod>" since 2026-09-29; never join the name yourself
$fin = Join-Path $Root '10. finalized mods'
$skipNames = 'Mod Requests, Bugs & Patches Guide', 'Skyrim - Mod Requests, Bugs & Patches Guide', '_photos-2026-08-30', '1. members'   # 1. members: Members material (the Pipeline Kit), not a Nexus page (2026-09-23)
$anyHit = $false
foreach ($d in Get-ChildItem -LiteralPath $distro -Directory | Where-Object { $_.Name -notlike '_*' -and $_.Name -notin $skipNames }) {
    $modName = Resolve-DistroModName -Folder $d.Name -ProjectRoot $Root -FinalizedRoot $fin   # "<Game> - <Mod>" -> the mod's full name
    if ($Only -and ($Only -notcontains $d.Name) -and ($Only -notcontains $modName)) { continue }
    # An add-on folder is "<parent> - <add-on>", and its archive may carry the version between the two
    # halves ("Apocrypha Menu Framework 1.6.9 - Custom Menu Art Preview FOMOD.zip"), so the match is
    # by both halves rather than by prefix. A parent folder must not pick up its add-ons' archives.
    $halves = $modName -split ' - ', 2
    $arc = Get-ChildItem -LiteralPath $d.FullName -File | Where-Object {
        $_.Extension -in '.zip', '.7z' -and $_.Name -like "$($halves[0])*" -and
        ($(if ($halves.Count -gt 1) { $_.Name -like "*$($halves[1])*" } else { $_.Name -notmatch ' - (Frame Reskin|Custom Menu Art|Untarnished)' -and $_.Name -notmatch 'Item Markers' })) } |
        Sort-Object { $m = [regex]::Match($_.Name, '(\d+\.\d+\.\d+)'); if ($m.Success) { [version]$m.Groups[1].Value } else { [version]'0.0.0' } } -Descending | Select-Object -First 1
    if (-not $arc) { Write-Output ("{0,-46} no archive in the distro folder" -f $d.Name); $anyHit = $true; continue }
    $m = [regex]::Match($arc.Name, '(\d+\.\d+\.\d+)'); if (-not $m.Success) { Write-Output ("{0,-46} archive carries no version: {1}" -f $d.Name, $arc.Name); $anyHit = $true; continue }
    $ver = $m.Groups[1].Value
    $game = Get-DistroFolderGame -Folder $d.Name
    # the finalized packages sit in "10. finalized mods\<this distro folder's name>\" since 2026-10-01
    $pkg = @(Find-Packages -Root $fin -ModName $modName -Game $game -Version $ver -Folders -ProjectRoot $Root) | Where-Object { ($_.Name -eq "$modName $ver FOMOD" -or $_.Name -eq "$modName $ver") -and (Test-PackageGame -PackagePath $_.FullName -FolderGame $game) } | Sort-Object { if ($_.Name -like '* FOMOD') { 0 } else { 1 } } | Select-Object -First 1
    if (-not $pkg) { Write-Output ("{0,-46} {1}  NO FINALIZED FOLDER for the distro's archive" -f $d.Name, $ver); $anyHit = $true; continue }
    $out = @(& $gate -Package $pkg.FullName -ModName $d.Name -Version $ver -DistroDir $d.FullName 2>&1 | ForEach-Object { "$_" })
    $hits = @($out | Where-Object { $_ -match '^\s+!!' })
    if ($hits.Count -eq 0) { Write-Output ("{0,-46} {1}  PASS" -f $d.Name, $ver) }
    else {
        $anyHit = $true
        Write-Output ("{0,-46} {1}  FAIL ({2})" -f $d.Name, $ver, $hits.Count)
        $hits | Select-Object -First 6 | ForEach-Object { Write-Output ("      " + $_.Trim()) }
    }
}
if ($anyHit) { Write-Output 'SWEEP: at least one mod is not shippable as it sits in the distro.'; exit 1 }
Write-Output 'SWEEP: every distro package clears every gate rule.'
exit 0
