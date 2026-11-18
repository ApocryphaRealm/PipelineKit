<#
.SYNOPSIS
    Keeps "11. Nexus distro" the ONE place to post from: every mod folder there holds exactly one
    package zip per download, and it is the newest finalized version (rule 10, owner 2026-09-06:
    "only the most up-to-date file for each mod should go to the Nexus distro ... make it so I
    dont have to go to the finalize folder when posting to nexus").

.DESCRIPTION
    Walks every folder under "11. Nexus distro" that corresponds to a finalized mod (a folder or
    zip named "<mod> X.Y.Z[ FOMOD]" exists under "10. finalized mods\<the same folder name>" - the
    package folders are named like the distro folders since 2026-10-01), works out the newest
    finalized version, and checks the distro folder's zips against it:

      CURRENT  - exactly one zip of that mod, and it is the newest version (same size as the
                 authoritative copy in "10. finalized mods")
      FIXED    - the newest zip was copied in and/or older zips of that mod were removed (only
                 with -Apply; without it the line reads WOULD-FIX)
      FLAGGED  - "10. finalized mods" has no zip for the newest version (a loose folder only), so
                 nothing can be copied - the distro's own zip stays and is reported for a human
      SKIP     - a distro folder with no finalized counterpart (the request-hub guide, templates)

    When "10. finalized mods" carries both a plain zip and a FOMOD zip for the newest version,
    the FOMOD is the one that ships (it is what a player installs), so it is the one kept here.
    Older zips are only removed from the DISTRO folder; "10. finalized mods" keeps every version.

.EXAMPLE
    .\nexus-distro-sweep.ps1            # report only
    .\nexus-distro-sweep.ps1 -Apply     # copy the newest zip in and remove stale ones
#>
param(
    [switch]$Apply,
    [string]$ProjectRoot = $env:PIPELINE_ROOT
)
$ErrorActionPreference = 'Continue'
if (-not $ProjectRoot) { $_kitRoot = $PSScriptRoot; while ($_kitRoot -and (Split-Path $_kitRoot -Leaf) -ne '.MD') { $_kitRoot = Split-Path $_kitRoot -Parent }; if ($_kitRoot) { $_kitRoot = Split-Path $_kitRoot -Parent }; $ProjectRoot = $_kitRoot }   # kit: <ROOT> is the folder above the .MD this script sits under, unless PIPELINE_ROOT says otherwise
$distroRoot = Join-Path $ProjectRoot '11. Nexus distro'
# Every lookup goes through the resolver OF THIS TREE (STEPS 5.4/5.5), never the absolute <ROOT> path.
$ResolverPy = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\resolvers\resolve.py'))
function Find-Role([string]$role) {
    $p = @(& py -3 $ResolverPy find $role)
    if ($LASTEXITCODE -ne 0 -or $p.Count -eq 0 -or -not "$($p[0])".Trim()) { Write-Output "nexus-distro-sweep: cannot resolve role '$role' ($($p -join ' '))"; exit 1 }
    return "$($p[0])".Trim()
}
. (Find-Role 'distro-names')   # the folder is "<Game> - <Mod>" since 2026-09-29; never join the name yourself
$finalizedRoot = Join-Path $ProjectRoot '10. finalized mods'

function Get-Ver([string]$name, [string]$mod) {
    $m = [regex]::Match($name, '^' + [regex]::Escape($mod) + ' (\d+)\.(\d+)\.(\d+)( FOMOD)?(\.zip)?$')
    if ($m.Success) { return [version]("{0}.{1}.{2}" -f $m.Groups[1].Value, $m.Groups[2].Value, $m.Groups[3].Value) }
    return $null
}

$rows = New-Object System.Collections.Generic.List[object]
foreach ($dir in Get-ChildItem -LiteralPath $distroRoot -Directory | Where-Object { -not $_.Name.StartsWith('_') -and $_.Name -ne '1. members' }) {
    $mod = Resolve-DistroModName -Folder $dir.Name -ProjectRoot $ProjectRoot -FinalizedRoot $finalizedRoot   # the folder is "<Game> - <Mod>"; the zips carry the full name
    $game = Get-DistroFolderGame -Folder $dir.Name
    # the packages sit in "10. finalized mods\<Game> - <Mod>\" - the distro folder's own name - since 2026-10-01
    $finalized = @(Find-Packages -Root $finalizedRoot -ModName $mod -Game $game -ProjectRoot $ProjectRoot | Where-Object { (Get-Ver $_.Name $mod) -and (Test-PackageGame -PackagePath $_.FullName -FolderGame $game) })   # the same name exists for both games: the package's folder (and contents) say which
    if ($finalized.Count -eq 0) { $rows.Add([pscustomobject]@{ Mod = $mod; Status = 'SKIP'; Detail = 'no finalized counterpart' }); continue }
    $newest = ($finalized | ForEach-Object { Get-Ver $_.Name $mod } | Sort-Object -Unique -Descending | Select-Object -First 1)
    $v = $newest.ToString()
    # SEVERAL DOWNLOADS (2026-11-12): a nexus-files.json in the distro folder makes the rule "one zip per manifest
    # entry" - every "<Mod> X.Y.Z - <folder>.zip" of the newest version present and current, every other zip of the mod
    # to the Recycle Bin (role nexus-files decides; its first word is the status)
    if (Test-Path -LiteralPath (Join-Path $dir.FullName 'nexus-files.json')) {
        $finDirOf = Split-Path @($finalized | Where-Object { (Get-Ver $_.Name $mod) -eq $newest })[0].FullName -Parent
        $nfArgs = @('sweep', $dir.FullName, $finDirOf, $mod, $v); if ($Apply) { $nfArgs += '--apply' }
        $nfOut = "$(@(& python (Find-Role 'nexus-files') @nfArgs 2>&1 | ForEach-Object { "$_" }) -join ' ')".Trim()
        $nfStatus = ($nfOut -split ' ', 2)[0]; $nfDetail = if ($nfOut.Contains(' ')) { ($nfOut -split ' ', 2)[1] } else { '' }
        if ($nfStatus -notin 'CURRENT', 'FIXED', 'WOULD-FIX', 'FLAGGED') { $nfStatus = 'FLAGGED'; $nfDetail = "nexus_files.py sweep: $nfOut" }
        $rows.Add([pscustomobject]@{ Mod = $mod; Status = $nfStatus; Detail = $nfDetail }); continue
    }
    $fomod = $finalized | Where-Object { $_.Name -eq "$mod $v FOMOD.zip" } | Select-Object -First 1
    $plain = $finalized | Where-Object { $_.Name -eq "$mod $v.zip" } | Select-Object -First 1
    $authoritative = if ($fomod) { $fomod.FullName } elseif ($plain) { $plain.FullName } else { $null }
    $distroZips = @(Get-ChildItem -LiteralPath $dir.FullName -Filter '*.zip' -File | Where-Object { Get-Ver $_.Name $mod })
    if (-not $authoritative) {
        $have = if ($distroZips.Count) { [string]::Join(', ', ($distroZips | ForEach-Object Name)) } else { 'no zip at all' }
        $rows.Add([pscustomobject]@{ Mod = $mod; Status = 'FLAGGED'; Detail = "newest finalized is $v but '10. finalized mods' has no zip for it (loose folder only); distro holds: $have" })
        continue
    }
    $targetName = Split-Path $authoritative -Leaf
    $targetPath = Join-Path $dir.FullName $targetName
    $upToDate = (Test-Path -LiteralPath $targetPath) -and ((Get-Item -LiteralPath $targetPath).Length -eq (Get-Item -LiteralPath $authoritative).Length)
    $stale = @($distroZips | Where-Object { $_.FullName -ne $targetPath })
    if ($upToDate -and $stale.Count -eq 0) {
        # Content check: a README edited in the finalized FOLDER after the zip was built leaves a stale zip
        # that is the right name and version (found 2026-09-06: two zips carried READMEs from before the
        # plain-changelog rewrite). Compare the zip's entries with the loose folder by name and size.
        $loose = Join-Path (Split-Path $authoritative -Parent) ($targetName -replace '\.zip$', '')   # "<mod> X.Y.Z" or "<mod> X.Y.Z FOMOD", beside its zip
        if (Test-Path -LiteralPath $loose) {
            $onDisk = @{}
            Get-ChildItem -LiteralPath $loose -Recurse -File | ForEach-Object { $onDisk[$_.FullName.Substring($loose.Length + 1).Replace('\', '/')] = $_.Length }
            Add-Type -AssemblyName System.IO.Compression.FileSystem
            $za = [System.IO.Compression.ZipFile]::OpenRead($targetPath)
            $inZip = @{}
            foreach ($e in $za.Entries) { if ($e.Name) { $inZip[$e.FullName.Replace('\', '/')] = $e.Length } }   # some zips store backslash paths
            $za.Dispose()
            $drift = @()
            foreach ($k in $onDisk.Keys) { if (-not $inZip.ContainsKey($k)) { $drift += "missing in zip: $k" } elseif ($inZip[$k] -ne $onDisk[$k]) { $drift += "size differs: $k" } }
            foreach ($k in $inZip.Keys) { if (-not $onDisk.ContainsKey($k)) { $drift += "only in zip: $k" } }
            if ($drift.Count -gt 0) {
                $rows.Add([pscustomobject]@{ Mod = $mod; Status = 'FLAGGED'; Detail = "$targetName is the right version but its CONTENT differs from the finalized folder - rebuild the zip from the folder: " + [string]::Join('; ', $drift) }); continue
            }
        }
        # Both banner sizes must be present (rule 10: 1920x1080 and the empty 1300x372 header, every mod).
        $missingBanners = @()
        foreach ($size in @('1920x1080', '1300x372')) {
            if (-not (Get-ChildItem -LiteralPath $dir.FullName -Filter "*banner-$size*.png" -File -ErrorAction SilentlyContinue)) { $missingBanners += $size }
        }
        if ($missingBanners.Count -gt 0) {
            $rows.Add([pscustomobject]@{ Mod = $mod; Status = 'FLAGGED'; Detail = "$targetName is current, but the folder has no rendered banner for: " + [string]::Join(', ', $missingBanners) + " (copy _banner-template-<size>.html in and rasterize it)" }); continue
        }
        $rows.Add([pscustomobject]@{ Mod = $mod; Status = 'CURRENT'; Detail = $targetName }); continue
    }
    $actions = @()
    if (-not $upToDate) { $actions += "copy in $targetName" }
    foreach ($s in $stale) { $actions += "remove $($s.Name)" }
    if ($Apply) {
        if (-not $upToDate) { Copy-Item -LiteralPath $authoritative -Destination $targetPath -Force }
        # to the Recycle Bin, never Remove-Item (rule 50, 2026-10-11 - the same one-zip rule hard-deleted an optional zip)
        if ($stale.Count) { Add-Type -AssemblyName Microsoft.VisualBasic }
        foreach ($s in $stale) { [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($s.FullName, 'OnlyErrorDialogs', 'SendToRecycleBin') }
        $rows.Add([pscustomobject]@{ Mod = $mod; Status = 'FIXED'; Detail = [string]::Join('; ', $actions) })
    } else {
        $rows.Add([pscustomobject]@{ Mod = $mod; Status = 'WOULD-FIX'; Detail = [string]::Join('; ', $actions) + ' (re-run with -Apply)' })
    }
}

Write-Host "Nexus distro sweep - one zip per mod, the newest finalized one" -ForegroundColor Cyan
Write-Host ("=" * 70)
foreach ($r in $rows) {
    $color = switch ($r.Status) { 'CURRENT' { 'Green' } 'FIXED' { 'Cyan' } 'WOULD-FIX' { 'Yellow' } 'FLAGGED' { 'Yellow' } 'SKIP' { 'DarkGray' } }
    Write-Host ("[{0,-9}] {1}" -f $r.Status, $r.Mod) -ForegroundColor $color
    Write-Host "            $($r.Detail)" -ForegroundColor $color
}
$bad = @($rows | Where-Object { $_.Status -in @('WOULD-FIX', 'FLAGGED') }).Count
Write-Host ("=" * 70)
Write-Host ("SUMMARY: {0} current, {1} fixed, {2} need attention, {3} skipped" -f @($rows | Where-Object Status -eq 'CURRENT').Count, @($rows | Where-Object Status -eq 'FIXED').Count, $bad, @($rows | Where-Object Status -eq 'SKIP').Count)
exit $(if ($bad -gt 0) { 1 } else { 0 })
