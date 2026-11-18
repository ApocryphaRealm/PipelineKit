# Build a two-line FOMOD package (Common\ + Line-17\ + Line-SE-AE16\ + fomod\) for a new version from the previous
# FOMOD package, with fresh DLL/PDB pairs from the repo's two build trees and the shipped files refreshed from the
# repo. package-mod.ps1 still cannot assemble the FOMOD layout (handoff 2026-09-16: "the packager still cannot build
# the FOMOD layout (the repack scripts ...)") and the repack script it refers to lived in a session scratchpad and is
# gone - so this one lives here (rule 5). Every step prints what it did; the DLL FileVersion of both lines is checked
# against -Version, and package-gate.ps1 runs at the end.
#
# Usage: repack-fomod.ps1 -DisplayName "Character Progression Control" -Version 1.1.9 -Repo CharacterProgressionControl
#   -Previous   the previous FOMOD package folder under "7. current test builds" (default: the newest "<DisplayName> <ver> FOMOD")
#   -Target     the DLL's base name (default: the repo folder name)
param(
    [Parameter(Mandatory = $true)][string]$DisplayName,
    [Parameter(Mandatory = $true)][string]$Version,
    [Parameter(Mandatory = $true)][string]$Repo,
    [string]$Target = '',
    [string]$Previous = '',
    [switch]$SeedOnly,   # print the seed this run would copy, then stop: no lock, nothing copied (tests)
    [string]$Root = $env:PIPELINE_ROOT
)
$ErrorActionPreference = 'Stop'
if (-not $Root) { $_kitRoot = $PSScriptRoot; while ($_kitRoot -and (Split-Path $_kitRoot -Leaf) -ne '.MD') { $_kitRoot = Split-Path $_kitRoot -Parent }; if ($_kitRoot) { $_kitRoot = Split-Path $_kitRoot -Parent }; $Root = $_kitRoot }   # kit: <ROOT> is the folder above the .MD this script sits under, unless PIPELINE_ROOT says otherwise
# Every lookup goes through the resolver OF THIS TREE (STEPS 5.4/5.10), never the absolute <ROOT> path.
$ResolverPy = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\resolvers\resolve.py'))
function Find-Role([string]$role) {
    $p = @(& py -3 $ResolverPy find $role)
    if ($LASTEXITCODE -ne 0 -or $p.Count -eq 0 -or -not "$($p[0])".Trim()) { Write-Output "repack-fomod: cannot resolve role '$role' ($($p -join ' '))"; exit 1 }
    return "$($p[0])".Trim()
}
$DistroNamesPath = Find-Role 'distro-names'
$RegistryPath = Find-Role 'version-registry'
$PackageGatePath = Find-Role 'package-gate'
if (-not $Target) { $Target = $Repo }
$stage7 = Join-Path $Root '7. current test builds'
$repoDir = Join-Path $Root "6. current wip mods\$Repo"

# THE AGENT-LOCK GATE (the owner, 2026-10-12; .MD\agent-bus\README.md): one session builds or commits a mod repo at a
# time. A free or stale lock is taken, our own is refreshed, a LIVE lock held by ANOTHER session refuses (agent-lock exit
# 3). The lock this run took is released when it ends (the token: never a lock an outer call took). A missing or failing
# lock tool only warns (fail open).
function Invoke-AgentLock([string[]]$LockArgs) {
    $script:AgentLockRc = 0
    try {
        $al = "$(@(& py -3 $ResolverPy find agent-lock 2>$null)[0])".Trim()
        if (-not $al -or -not (Test-Path -LiteralPath $al)) { Write-Output 'agent-lock: WARNING role agent-lock not found - continuing without the lock'; return }
        & py -3 $al @LockArgs | ForEach-Object { Write-Output "$_" }
        $script:AgentLockRc = $LASTEXITCODE
        if (@(0, 3, 4) -notcontains $script:AgentLockRc) { Write-Output "agent-lock: WARNING the lock tool failed (exit $($script:AgentLockRc)) - continuing without the lock"; $script:AgentLockRc = 0 }
    } catch { Write-Output "agent-lock: WARNING $($_.Exception.Message) - continuing without the lock"; $script:AgentLockRc = 0 }
}
# THE SEED is the newest EARLIER package of this mod that has the FOMOD layout (a fomod\ folder), whatever its name and
# wherever it is (2026-10-13). The old pick took only folders named "<mod> <ver> FOMOD" in the test builds, so Lock
# Interaction Overhaul's 1.0.6 repack was seeded from 1.0.3: its 1.0.5 package is a FOMOD layout named
# "Lock Interaction Overhaul 1.0.5", and the finalized copies were never looked at. A package without fomod\ is never a seed.
function Select-FomodSeed([string]$game) {
    $stage10 = Join-Path $Root '10. finalized mods'
    $cands = @()
    foreach ($r in @($stage7, $stage10)) {
        if (-not (Test-Path -LiteralPath $r)) { continue }
        $cands += @(Find-Packages -Root $r -ModName $DisplayName -Game $game -Folders -ProjectRoot $Root) |
            Where-Object { $_.PSIsContainer -and $_.PkgVersion -lt [version]$Version -and (Test-Path -LiteralPath (Join-Path $_.FullName 'fomod')) }
    }
    # newest version first; at one version the finalized copy (what was published) wins over the test build
    $prev = $cands | Sort-Object @{ Expression = { $_.PkgVersion }; Descending = $true }, @{ Expression = { if ($_.FullName.StartsWith($stage10, [System.StringComparison]::OrdinalIgnoreCase)) { 0 } else { 1 } } } | Select-Object -First 1
    if (-not $prev) { throw "no earlier '$DisplayName' package with a fomod\ folder under $stage7 or $stage10" }
    return $prev.FullName
}
function Get-RepackGame {
    $regEntry = @((Get-Content -LiteralPath $RegistryPath -Raw | ConvertFrom-Json).PSObject.Properties |
        Where-Object { $_.Value.repo -ieq $Repo } | ForEach-Object { $_.Value }) | Select-Object -First 1
    if ($regEntry) { return (Get-ModGame -Entry $regEntry -ProjectRoot $Root) } else { return 'Skyrim' }
}
if ($SeedOnly) {
    . $DistroNamesPath
    "seed: $(if ($Previous) { $Previous } else { Select-FomodSeed (Get-RepackGame) })"
    exit 0
}
# THE OPEN-REQUEST GATE (2026-10-27, same as package-mod's): a number with a test request still open (queued, or in a
# combined-run batch with no result) is never packaged again - a helper rebuilt the AMF 2.3.1 FOMOD with another fix while
# 2.3.1 was under test. The change goes on a branch until that number is posted. A broken check only warns.
try {
    $crPath = "$(@(& py -3 $ResolverPy find combined-run 2>$null)[0])".Trim()
    if ($crPath -and $crPath -notlike 'MISSING*' -and (Test-Path -LiteralPath $crPath)) {
        $global:LASTEXITCODE = 0
        $openOut = @(& py -3 $crPath open-for --mod $DisplayName --mod $Repo --version $Version 2>&1 | ForEach-Object { "$_" })
        if ($LASTEXITCODE -eq 3) { $openOut; "FAIL  $DisplayName $Version has an open test request - not packaging it again. The change goes on a branch until $Version is posted."; exit 1 }
        elseif ($LASTEXITCODE -ne 0) { "WARN  the open-request check failed (exit $LASTEXITCODE) - continuing" }
    }
} catch { "WARN  the open-request check failed: $($_.Exception.Message) - continuing" }
$LockToken = [guid]::NewGuid().ToString('N')
# each acquirer is its own holder (2026-10-25): the token goes to the tools this script starts (AGENT_LOCK_TOKENS),
# so their own lock calls refresh this lock instead of being refused
$env:AGENT_LOCK_TOKENS = (@($env:AGENT_LOCK_TOKENS, $LockToken) | Where-Object { $_ }) -join ';'
Invoke-AgentLock @('acquire', '--repo', $Repo, '--purpose', "repack-fomod $DisplayName $Version", '--token', $LockToken)
if ($script:AgentLockRc -eq 3) { "FAIL  agent-lock: another session holds repo:$Repo - not packaging"; exit 1 }
try {
# The package goes into its game folder, "7. current test builds\<Game> - <Mod>\" (2026-10-01, Resolve-PackageRoot); the
# game is the registry entry's for this repo. A two-line FOMOD (Line-17 + Line-SE-AE16) is a Skyrim layout.
. $DistroNamesPath
$regEntry = @((Get-Content -LiteralPath $RegistryPath -Raw | ConvertFrom-Json).PSObject.Properties |
    Where-Object { $_.Value.repo -ieq $Repo } | ForEach-Object { $_.Value }) | Select-Object -First 1
$game = if ($regEntry) { Get-ModGame -Entry $regEntry -ProjectRoot $Root } else { 'Skyrim' }
$builds = Resolve-PackageRoot -Root $stage7 -ModName $DisplayName -Game $game -ProjectRoot $Root
if (-not $Previous) { $Previous = Select-FomodSeed $game }
$dest = Join-Path $builds "$DisplayName $Version FOMOD"
"previous: $Previous"
# PRE-FLIGHT (2026-10-24, item 9): everything the new package needs is checked BEFORE the existing package is touched.
# Dragon's Eye Minimap 1.7.5's repack (2026-10-24) deleted the existing package and THEN found no
# DragonsEyeMinimap-SMF.dll (the DLL is DragonsEyeMinimap - a wrong -Target), and left the test build empty.
$lines = @{ 'Line-17' = 'relwithdebinfo-17'; 'Line-SE-AE16' = 'relwithdebinfo-se-only' }
$preflight = @()
if (-not (Test-Path -LiteralPath $Previous)) { $preflight += "the seed $Previous does not exist" }
$extraNames = @()
$extraListPre = Join-Path $repoDir 'fomod\extra-line-dlls.txt'
if (Test-Path -LiteralPath $extraListPre) { $extraNames = @(Get-Content -LiteralPath $extraListPre | ForEach-Object { $_.Trim() } | Where-Object { $_ -and -not $_.StartsWith('#') }) }
foreach ($line in $lines.Keys) {
    $src = Join-Path $repoDir "build\$($lines[$line])"
    foreach ($base in @($Target) + $extraNames) {
        $dllP = Join-Path $src "$base.dll"; $pdbP = Join-Path $src "$base.pdb"
        if (-not (Test-Path -LiteralPath $dllP)) {
            $have = @(Get-ChildItem -LiteralPath $src -Filter '*.dll' -File -ErrorAction SilentlyContinue | ForEach-Object { $_.BaseName })
            $preflight += "no $dllP$(if ($base -eq $Target -and $have.Count) { " (that build folder has: $($have -join ', ') - pass it as -Target)" })"
            continue
        }
        if (-not (Test-Path -LiteralPath $pdbP)) { $preflight += "no $pdbP" }
        $fvP = (Get-Item -LiteralPath $dllP).VersionInfo.FileVersion
        if (-not $fvP -or -not $fvP.StartsWith($Version)) { $preflight += "$line $base.dll FileVersion is '$fvP', not $Version - stamp and rebuild first" }
    }
}
$readmeSrc = if (Test-Path -LiteralPath (Join-Path $repoDir 'dist\README.txt')) { Join-Path $repoDir 'dist\README.txt' } else { Join-Path $repoDir 'README.md' }
if (Test-Path -LiteralPath $readmeSrc) {
    if ((Get-Content -LiteralPath $readmeSrc -Raw -Encoding UTF8) -notmatch "(?m)^Version $([regex]::Escape($Version))\s*$") { $preflight += "$readmeSrc does not carry 'Version $Version' at its top - fix the repo README first" }
}
if ($preflight.Count) {
    $preflight | ForEach-Object { "preflight: $_" }
    "FAIL  nothing was changed: the existing package (if any) is untouched"
    exit 1
}
"preflight: both lines' DLL/PDB, their FileVersion and the README are ready"

if (-not (Test-Path -LiteralPath $builds)) { New-Item -ItemType Directory -Path $builds | Out-Null; "created $builds" }
# NEVER DELETE A PACKAGE (2026-10-25, the project's never-permanently-delete rule): a package folder this script replaces
# - the existing FOMOD, the packager's flat folder, a half-built new one - is MOVED to
# <Root>\_work\superseded-packages\<date>\ (outside the test builds tree, so no packager or seed search finds it), where
# it stays until the owner clears it. Before, the old package was set aside and then Remove-Item'd.
$SupersededRoot = Join-Path $Root '_work\superseded-packages'   # fixed here: a later loop variable must never move it
function Move-Superseded([string]$Path, [string]$Why) {
    $day = Join-Path $SupersededRoot (Get-Date -Format 'yyyy-MM-dd')
    New-Item -ItemType Directory -Force $day | Out-Null
    $to = Join-Path $day ('{0} ({1} {2})' -f (Split-Path -Leaf $Path), $Why, (Get-Date -Format 'HHmmss'))
    $base = $to; $i = 2
    while (Test-Path -LiteralPath $to) { $to = "$base $i"; $i++ }
    Move-Item -LiteralPath $Path -Destination $to
    return $to
}
# The existing package is MOVED there first, and put back if anything below throws.
$aside = $null
if (Test-Path -LiteralPath $dest) {
    $aside = Move-Superseded $dest 'replaced'
    "moved the existing package aside -> $aside"
}
try {
Copy-Item -LiteralPath $Previous -Destination $dest -Recurse
"copied the previous layout -> $dest"

# The line folders hold only what THIS build supplies (2026-10-12, AMF 2.2.0): the previous package's DLLs and PDBs are
# taken out of the copy before the fresh ones go in, so a DLL a release dropped (AMF-Host-OAR, taken out of AMF 2.2.0) or
# renamed (Auto Audio Output Switch's ApocryphaAutoAudioOutputSwitch.dll) is never carried forward by the seed.
foreach ($line in @('Line-17', 'Line-SE-AE16')) {
    $seedDir = Join-Path $dest "$line\SKSE\Plugins"
    if (-not (Test-Path -LiteralPath $seedDir)) { continue }
    foreach ($old in @(Get-ChildItem -LiteralPath $seedDir -File | Where-Object { $_.Extension -in '.dll', '.pdb' })) {
        Remove-Item -LiteralPath $old.FullName -Force
        "$line : $($old.Name) from the previous package taken out of the copy (the build supplies this line's DLLs)"
    }
}

# fresh DLL/PDB pairs, both lines
$lines = @{ 'Line-17' = 'relwithdebinfo-17'; 'Line-SE-AE16' = 'relwithdebinfo-se-only' }
foreach ($line in $lines.Keys) {
    $src = Join-Path $repoDir "build\$($lines[$line])"
    $dll = Join-Path $src "$Target.dll"; $pdb = Join-Path $src "$Target.pdb"
    if (-not (Test-Path -LiteralPath $dll)) { throw "no $dll" }
    if (-not (Test-Path -LiteralPath $pdb)) { throw "no $pdb" }
    $fv = (Get-Item -LiteralPath $dll).VersionInfo.FileVersion
    if (-not $fv.StartsWith($Version)) { throw "$line DLL FileVersion is $fv, not $Version - stamp and rebuild first" }
    $dstDir = Join-Path $dest "$line\SKSE\Plugins"
    New-Item -ItemType Directory -Force $dstDir | Out-Null
    Copy-Item -LiteralPath $dll -Destination $dstDir -Force
    Copy-Item -LiteralPath $pdb -Destination $dstDir -Force
    "$line : $Target.dll + .pdb (FileVersion $fv) from $($lines[$line])"
}

# DLLs that ship beside the mod's own in each line, named one base name a line in the repo's fomod\extra-line-dlls.txt
# (2026-10-12, AMF 2.2.0's AMF-Host-OAR bridge): each with its PDB from the same build tree, stamped with the same version.
# A repo without the file is unchanged; a listed DLL that is missing or mis-stamped stops the package.
$extraList = Join-Path $repoDir 'fomod\extra-line-dlls.txt'
if (Test-Path -LiteralPath $extraList) {
    $extras = @(Get-Content -LiteralPath $extraList | ForEach-Object { $_.Trim() } | Where-Object { $_ -and -not $_.StartsWith('#') })
    foreach ($line in $lines.Keys) {
        $src = Join-Path $repoDir "build\$($lines[$line])"
        $dstDir = Join-Path $dest "$line\SKSE\Plugins"
        foreach ($x in $extras) {
            $xd = Join-Path $src "$x.dll"; $xp = Join-Path $src "$x.pdb"
            if (-not (Test-Path -LiteralPath $xd)) { throw "no $xd (named in fomod\extra-line-dlls.txt) - build it first" }
            if (-not (Test-Path -LiteralPath $xp)) { throw "no $xp (named in fomod\extra-line-dlls.txt)" }
            $xfv = (Get-Item -LiteralPath $xd).VersionInfo.FileVersion
            if (-not $xfv -or -not $xfv.StartsWith($Version)) { throw "$line $x.dll FileVersion is '$xfv', not $Version - rebuild it after the stamp" }
            Copy-Item -LiteralPath $xd -Destination $dstDir -Force
            Copy-Item -LiteralPath $xp -Destination $dstDir -Force
            "$line : $x.dll + .pdb (FileVersion $xfv) from $($lines[$line]) - fomod\extra-line-dlls.txt"
        }
    }
}

# OTHER DLLs THE BUILD PRODUCES (2026-10-24, AMF 2.3.0): a DLL the package carries OUTSIDE the two line folders - AMF's
# SKSE Menu Framework name stub in SMF-Name\ - came from the seed, so every repack shipped the previous release's copy
# (the package gate's dll-built-after-the-last-source-change refused AMF 2.3.0 over a 2026-10-21 stub). Any such DLL the
# repo's build also produces - the SE/AE tree first, as tools\build-fomod.py takes the stub - is replaced by the build's,
# with its PDB. A DLL the build does not produce (a third-party file the package ships) is left as it is.
$lineRoots = @('Line-17', 'Line-SE-AE16') | ForEach-Object { (Join-Path $dest $_) + '\' }
foreach ($pkgDll in @(Get-ChildItem -LiteralPath $dest -Recurse -File -Filter '*.dll')) {
    $inLine = $false
    foreach ($lineRoot in $lineRoots) { if ($pkgDll.FullName.StartsWith($lineRoot,[StringComparison]::OrdinalIgnoreCase)) { $inLine = $true } }
    if ($inLine) { continue }
    foreach ($tree in @('relwithdebinfo-se-only', 'relwithdebinfo-17')) {
        $built = Join-Path $repoDir "build\$tree\$($pkgDll.Name)"
        if (-not (Test-Path -LiteralPath $built)) { continue }
        Copy-Item -LiteralPath $built -Destination $pkgDll.FullName -Force
        $builtPdb = [IO.Path]::ChangeExtension($built, '.pdb')
        if (Test-Path -LiteralPath $builtPdb) { Copy-Item -LiteralPath $builtPdb -Destination ([IO.Path]::ChangeExtension($pkgDll.FullName, '.pdb')) -Force }
        "$($pkgDll.FullName.Substring($dest.Length + 1)) <- build\$tree (refreshed: the build's copy, not the seed's)"
        break
    }
}

# shared files from the repo: everything under dist\ (INI, Interface, translations ...) into Common\, README, licences
$common = Join-Path $dest 'Common'
$dist = Join-Path $repoDir 'dist'
if (Test-Path -LiteralPath $dist) {
    foreach ($f in Get-ChildItem -LiteralPath $dist -Recurse -File) {
        $rel = $f.FullName.Substring($dist.Length + 1)
        # a bare INI at dist root ships under SKSE\Plugins, where the previous package had it
        if ($rel -match '^[^\\/]+\.ini$') { $rel = "SKSE\Plugins\$rel" }
        # A FOMOD that offers languages ships only the translations its previous Common\ carried (English); the rest
        # live under Languages\ and are the installer's choice. And the repo's dist\scripts\ never ships unless the
        # previous package did (AMF 1.9.6, 2026-09-21: ten translations and a dead AMFTest.pex rode into Common\).
        if ((Test-Path -LiteralPath (Join-Path $dest 'Languages')) -and $rel -match '^Interface\\Translations\\' -and -not (Test-Path -LiteralPath (Join-Path (Join-Path $Previous 'Common') $rel))) { "skip  $rel (a language the installer offers)"; continue }
        if ($rel -match '^scripts\\' -and -not (Test-Path -LiteralPath (Join-Path (Join-Path $Previous 'Common') $rel))) { "skip  $rel (not in the previous package)"; continue }
        $to = Join-Path $common $rel
        New-Item -ItemType Directory -Force (Split-Path $to) | Out-Null
        Copy-Item -LiteralPath $f.FullName -Destination $to -Force
        "Common\$rel <- dist"
    }
}
foreach ($pair in @(@('README.md', 'README.txt'), @('NOTICE.md', 'NOTICE.md'), @('THIRD_PARTY_NOTICES.md', 'THIRD_PARTY_NOTICES.md'))) {
    # The player README is the repo's dist\README.txt when it keeps one (package-mod.ps1's rule, 2026-09-19); a repo
    # README.md is then the developer's document and must not overwrite it (Apocrypha Menu Framework 1.9.6, 2026-09-21:
    # its README.md is a 1.4.4-era developer page with no version line).
    if ($pair[1] -eq 'README.txt' -and (Test-Path -LiteralPath (Join-Path $repoDir 'dist\README.txt'))) { continue }
    $src = Join-Path $repoDir $pair[0]
    if (Test-Path -LiteralPath $src) { Copy-Item -LiteralPath $src -Destination (Join-Path $common $pair[1]) -Force; "Common\$($pair[1]) <- repo $($pair[0])" }
}
# Every CHANGELOG.md in the package (root and Common\) is the repo's, never the seeded previous release's - AMF 1.9.7's
# repack would otherwise have shipped release notes without the fix it was cut for (gate rule
# shipped-changelog-is-the-repos, 2026-09-23).
$repoLog = Join-Path $repoDir 'CHANGELOG.md'
if (Test-Path -LiteralPath $repoLog) {
    foreach ($c in @(Get-ChildItem -LiteralPath $dest -Recurse -File -Filter 'CHANGELOG.md')) {
        Copy-Item -LiteralPath $repoLog -Destination $c.FullName -Force
        "$($c.FullName.Substring($dest.Length + 1)) <- repo CHANGELOG.md"
    }
}
# A FOMOD with a Languages\ tree (Apocrypha Menu Framework) carries translation files OUTSIDE Common\; refresh every
# one of them from the repo's dist\Interface\Translations, or the previous release's text ships again (the package
# gate's shipped-translations-are-the-repos rule caught 20 stale files in AMF 1.9.6, 2026-09-21).
$langRoot = Join-Path $dest 'Languages'
$trSrc = Join-Path $repoDir 'dist\Interface\Translations'
if ((Test-Path -LiteralPath $langRoot) -and (Test-Path -LiteralPath $trSrc)) {
    foreach ($f in Get-ChildItem -LiteralPath $langRoot -Recurse -File) {
        $s2 = Join-Path $trSrc $f.Name
        if (Test-Path -LiteralPath $s2) { Copy-Item -LiteralPath $s2 -Destination $f.FullName -Force; "$($f.FullName.Substring($dest.Length + 1)) <- dist translation" }
    }
}
$readme = Join-Path $common 'README.txt'
if (Test-Path -LiteralPath $readme) {
    $t = Get-Content -LiteralPath $readme -Raw -Encoding UTF8
    if ($t -notmatch "(?m)^Version $([regex]::Escape($Version))\s*$") { throw "Common\README.txt does not carry 'Version $Version' at its top - fix the repo README first" }
}

# THE INSTALLER FROM SOURCE (2026-10-18, Compass Navigation Overhaul 1.1.7): a repo that keeps its installer in git
# - fomod\ModuleConfig.xml and fomod\info.xml, plus the files its options install under fomod\option-folders\<Name>\
# (each <Name> becomes a package-root folder the ModuleConfig names) - has the package's installer taken from the repo,
# not carried over from the seed. A repo without these files is unchanged: its installer still comes from the seed.
$repoFomod = Join-Path $repoDir 'fomod'
foreach ($xml in @('ModuleConfig.xml', 'info.xml')) {
    $srcXml = Join-Path $repoFomod $xml
    if (Test-Path -LiteralPath $srcXml) {
        New-Item -ItemType Directory -Force (Join-Path $dest 'fomod') | Out-Null
        Copy-Item -LiteralPath $srcXml -Destination (Join-Path $dest "fomod\$xml") -Force
        "fomod\$xml <- repo fomod\$xml"
    }
}
$optionRoot = Join-Path $repoFomod 'option-folders'
if (Test-Path -LiteralPath $optionRoot) {
    foreach ($opt in @(Get-ChildItem -LiteralPath $optionRoot -Directory)) {
        $optDest = Join-Path $dest $opt.Name
        if (Test-Path -LiteralPath $optDest) { Remove-Item -LiteralPath $optDest -Recurse -Force }
        Copy-Item -LiteralPath $opt.FullName -Destination $optDest -Recurse
        "$($opt.Name)\ <- repo fomod\option-folders\$($opt.Name)"
        # a file an option installs must not also ship in Common\ (an older seed carried it there): the option is then no choice
        foreach ($of in @(Get-ChildItem -LiteralPath $opt.FullName -Recurse -File)) {
            $relOpt = $of.FullName.Substring($opt.FullName.Length + 1)
            $inCommon = Join-Path (Join-Path $dest 'Common') $relOpt
            if (Test-Path -LiteralPath $inCommon) { Remove-Item -LiteralPath $inCommon -Force; "Common\$relOpt removed (the installer offers it as an option)" }
        }
    }
}

# fomod\info.xml version
$info = Join-Path $dest 'fomod\info.xml'
if (-not (Test-Path -LiteralPath $info)) { throw "no fomod\info.xml in the previous package" }
$x = Get-Content -LiteralPath $info -Raw -Encoding UTF8
$x2 = [regex]::Replace($x, '<Version>[^<]*</Version>', "<Version>$Version</Version>")
if ($x2 -eq $x -and $x -notmatch "<Version>$([regex]::Escape($Version))</Version>") { throw "fomod\info.xml has no <Version> element" }
[IO.File]::WriteAllText($info, $x2, (New-Object System.Text.UTF8Encoding($false)))
"fomod\info.xml <Version>$Version</Version>"
} catch {
    # the new package is incomplete: it goes, the old one comes back exactly as it was
    "FAIL  repack: $($_.Exception.Message)"
    if (Test-Path -LiteralPath $dest) { $half = Move-Superseded $dest 'incomplete repack'; "moved the incomplete new package out -> $half" }
    if ($aside) { Move-Item -LiteralPath $aside -Destination $dest; "restored the previous package -> $dest" }
    exit 1
}
if ($aside) { "the new package is complete: the old one stays in $aside (never deleted)" }

# prove it
$flat = Join-Path $builds "$DisplayName $Version"
if (Test-Path -LiteralPath $flat) { $flatTo = Move-Superseded $flat 'flat, the FOMOD is the package'; "moved the packager's flat '$DisplayName $Version' out (the FOMOD is the package) -> $flatTo" }
& $PackageGatePath -Package $dest -ModName $DisplayName -Version $Version -RepoPath $repoDir
exit $LASTEXITCODE
} finally {
    Invoke-AgentLock @('release', '--repo', $Repo, '--token', $LockToken)
}
