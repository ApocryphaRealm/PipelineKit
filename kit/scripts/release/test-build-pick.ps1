# Which test-build folder IS the build of a version (2026-10-13, Main Agent's rule, built with straight flow B).
# Dot-source it (role test-build-pick); it needs distro-names.ps1 dot-sourced first (Resolve-PackageRoot).
#
# Why: Simple Loadout System for Witcher 3 1.0.1 had several folders for one version in "7. current test builds\Witcher 3 -
# Simple Loadout System" - "Simple Loadout System 1.0.1" held the OLD 1.0.0 bundle and script, "Simple Loadout System
# 1.0.1 (inventory start-up fix)" held the tested build. finalize-mod's dry run and version-gate's Find-Package both took
# the plain-named folder, and the finalize gate then (rightly) refused it on the hash. The pick itself was wrong.
#
# The rule: the folders of one version are "<Mod> <X.Y.Z>", "<Mod> <X.Y.Z> FOMOD" and either with a " (...)" suffix. One
# folder is used as it is. With more than one, the folder whose ARTEFACT matches the ledger's recorded working hash is the
# build: the DLL or ASI for a code mod (minus the registry's foreignBinaries, e.g. a dinput8.dll loader), else the
# plugin (.esp/.esl/.esm), else the asset files - version-gate.ps1's classification, which now lives here. Exactly one
# match is chosen and the others are named as passed over. None or several matching - or several folders and no hash -
# REFUSES: the candidates are listed, and renaming a folder is for the owner. Nothing here moves, renames or deletes
# a folder.
#
#   Get-TestBuildCandidates -BuildsRoot -Display -Version -Game -ProjectRoot   -> the version's folders (DirectoryInfo)
#   Get-PackagePlugins      -Path                                               -> .esp/.esl/.esm files
#   Get-PackageAssets       -Path                                               -> asset files of an art-only package
#   Get-PackageBinaries     -Path [-Foreign names]                              -> DLL/ASI files minus foreign ones
#   Get-PackageArtefacts    -Path [-Foreign names]                              -> the files a working hash is compared with
#   Get-PackageArtefactList -Path [-Foreign names]                              -> those files as { file, sha256 } rows
#   Get-RowArtifacts        -Row                                                -> a ledger row's 'artifacts' list (or none)
#   Compare-PackageArtefacts -Path -Artifacts [-Foreign names]                  -> one line per file that does not match
#   Select-TestBuild        -Candidates [-Hash] [-Artifacts list] [-Foreign]    -> { Pick, Refused, Message }
#
# EVERY ARTEFACT IN THE LEDGER ROW (2026-10-13, approved by Main Agent). A row used to carry ONE sha256, so for a mod with
# no DLL (a Witcher 3 script mod ships blob0.bundle AND a .ws script; an art-only mod ships several files) only one file
# was tied to the number and a stale .ws beside a correct bundle passed. 'version-gate record -Status working' now also
# writes 'artifacts': [{ file: <path relative to the package folder, forward slashes>, sha256: <upper hex> }] for every
# artefact Get-PackageArtefacts classifies in the package it compared with. The finalize gate, the package stage and the
# pick below use the whole list when a row has one (every listed file present with its hash, no unlisted artefact of the
# same classification); a row with only sha256 (every row written before this) is judged on the one hash, as before.

function Get-TestBuildFileSha256([string]$Path) {
    # .NET, not Get-FileHash: hashing only reads, and Get-FileHash returns nothing under a script-wide -WhatIf (2026-10-13)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $fs = [System.IO.File]::OpenRead($Path)
    try { return ([System.BitConverter]::ToString($sha.ComputeHash($fs))).Replace('-', '') } finally { $fs.Dispose(); $sha.Dispose() }
}

function Get-TestBuildCandidates([string]$BuildsRoot, [string]$Display, [string]$Version, [string]$Game, [string]$ProjectRoot = $(if ($env:PIPELINE_ROOT) { $env:PIPELINE_ROOT } else { Split-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) -Parent })) {
    if (-not (Test-Path -LiteralPath $BuildsRoot)) { return @() }
    $dir = Resolve-PackageRoot -Root $BuildsRoot -ModName $Display -Game $Game -ProjectRoot $ProjectRoot
    if (-not $dir -or -not (Test-Path -LiteralPath $dir)) { return @() }
    $rx = '^' + [regex]::Escape("$Display $Version") + '( FOMOD)?( \(.+\))?$'
    return @(Get-ChildItem -LiteralPath $dir -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -match $rx } | Sort-Object Name)
}

function Get-PackagePlugins([string]$Path) {
    return @(Get-ChildItem -LiteralPath $Path -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.Extension -match '^\.(esp|esl|esm)$' })
}

function Get-PackageAssets([string]$Path) {
    # 2026-09-29 (Oblivion Paper Theme, one INI and four PNGs): a file under a GAME tree (Data\, SKSE\, OblivionRemastered\,
    # stylesheets\, bin\, Mods\) is an asset whatever its extension - the extension list only keeps a package's own
    # documents and previews from counting. 2026-11-19: Norse (NORSE game-root packages: a data-only mod ships its table as .txt and its pack manifest as .ini).
    $full = (Get-Item -LiteralPath $Path).FullName
    return @(Get-ChildItem -LiteralPath $full -Recurse -File -ErrorAction SilentlyContinue |
             Where-Object { ($_.Extension -notmatch '^\.(txt|md|ini|json|xml|png|jpg|html)$') -or
                            ($_.FullName.Substring($full.Length) -match '^[\\/](Data|SKSE|OblivionRemastered|Norse|stylesheets|bin|Mods)[\\/]') })
}

function Get-PackageBinaries([string]$Path, [string[]]$Foreign = @()) {
    # the DLL and ASI files of a package, minus the registry's foreignBinaries; version-gate's Package-Dlls is this too
    return @(Get-ChildItem -LiteralPath $Path -Recurse -File -ErrorAction SilentlyContinue |
             Where-Object { $_.Extension -in '.dll', '.asi' } | Where-Object { $n = $_.Name; -not @($Foreign | Where-Object { $_ -ieq $n }).Count })
}

function Get-PackageArtefacts([string]$Path, [string[]]$Foreign = @()) {
    $bins = @(Get-PackageBinaries $Path $Foreign)
    if ($bins.Count) { return $bins }
    $plugins = Get-PackagePlugins $Path
    if ($plugins.Count) { return $plugins }
    return (Get-PackageAssets $Path)
}

function Get-PackageArtefactList([string]$Path, [string[]]$Foreign = @()) {
    $full = (Get-Item -LiteralPath $Path).FullName.TrimEnd('\', '/')
    return @(Get-PackageArtefacts $full $Foreign | Sort-Object FullName | ForEach-Object {
        [pscustomobject]@{ file = $_.FullName.Substring($full.Length + 1).Replace('\', '/'); sha256 = (Get-TestBuildFileSha256 $_.FullName) } })
}

function Get-RowArtifacts($Row) {
    if (-not $Row -or -not $Row.PSObject.Properties['artifacts']) { return @() }
    return @(@($Row.artifacts) | Where-Object { $_ -and $_.file })
}

function Compare-PackageArtefacts([string]$Path, [object[]]$Artifacts, [string[]]$Foreign = @()) {
    # Empty result = the package holds exactly the listed artefacts with their hashes. Each line names one file.
    $have = @{}
    foreach ($a in @(Get-PackageArtefactList $Path $Foreign)) { $have[$a.file.ToLowerInvariant()] = $a }
    $listed = @{}
    $problems = New-Object System.Collections.Generic.List[string]
    foreach ($a in @($Artifacts | Where-Object { $_ -and $_.file })) {
        $f = "$($a.file)".Replace('\', '/'); $k = $f.ToLowerInvariant(); $listed[$k] = $true
        $want = "$($a.sha256)".ToUpper(); $w8 = if ($want.Length -ge 8) { $want.Substring(0, 8) } else { $want }
        if (-not $have.ContainsKey($k)) { $problems.Add("$f is listed in the working row but is not in the package") }
        elseif ($have[$k].sha256 -ne $want) { $problems.Add("$f is not the file recorded working (sha256 $($have[$k].sha256.Substring(0, 8))... in the package, $w8... recorded)") }
    }
    foreach ($k in @($have.Keys | Sort-Object)) {
        if (-not $listed.ContainsKey($k)) { $problems.Add("$($have[$k].file) is in the package but not in the working row's artefact list - a new or renamed file that was never proven") }
    }
    return @($problems)
}

function Select-TestBuild([object[]]$Candidates, [string]$Hash, [string[]]$Foreign = @(), [object[]]$Artifacts = @()) {
    $c = @($Candidates | Where-Object { $_ })
    if ($c.Count -eq 0) { return [pscustomobject]@{ Pick = $null; Refused = $false; Message = '' } }
    if ($c.Count -eq 1) { return [pscustomobject]@{ Pick = $c[0]; Refused = $false; Message = $(if ($c[0].Name -match '\(') { "test build: '$($c[0].Name)' (the only folder of this version)" } else { '' }) } }
    $names = ($c | ForEach-Object { "'$($_.Name)'" }) -join ', '
    $owner = 'renaming or removing a test-build folder is for the owner; nothing was moved'
    $arts = @($Artifacts | Where-Object { $_ -and $_.file })
    if ($arts.Count) {
        # the row lists every artefact: a folder is the build only when ALL of them match and nothing unlisted is there
        $hits = @($c | Where-Object { @(Compare-PackageArtefacts $_.FullName $arts $Foreign).Count -eq 0 })
        if ($hits.Count -eq 1) {
            $others = ($c | Where-Object { $_.FullName -ne $hits[0].FullName } | ForEach-Object { "'$($_.Name)'" }) -join ', '
            return [pscustomobject]@{ Pick = $hits[0]; Refused = $false
                Message = "test build: '$($hits[0].Name)' - all $($arts.Count) artefact(s) of the recorded working row match; passed over $others" }
        }
        $why = if ($hits.Count -eq 0) { "none of them holds exactly the $($arts.Count) artefact(s) of the recorded working row (every listed file with its hash, nothing unlisted)" }
               else { "$($hits.Count) of them hold exactly the recorded working row's $($arts.Count) artefact(s) ($((($hits | ForEach-Object { "'$($_.Name)'" }) -join ', ')))" }
        return [pscustomobject]@{ Pick = $null; Refused = $true; Message = "$($c.Count) test-build folders for this version ($names): $why - $owner." }
    }
    if (-not $Hash) {
        # the old preference stands for the plain + FOMOD pair alone: the FOMOD is what ships when both exist
        $fom = @($c | Where-Object { $_.Name -like '* FOMOD' })
        if ($c.Count -eq 2 -and $fom.Count -eq 1 -and -not @($c | Where-Object { $_.Name -match '\(' }).Count) {
            return [pscustomobject]@{ Pick = $fom[0]; Refused = $false; Message = '' }
        }
        return [pscustomobject]@{ Pick = $null; Refused = $true; Message = "$($c.Count) test-build folders for this version ($names) and no recorded working hash to tell them apart - $owner." }
    }
    $h = $Hash.ToUpper()
    $hits = @()
    foreach ($f in $c) {
        $m = @(Get-PackageArtefacts $f.FullName $Foreign | Where-Object { (Get-TestBuildFileSha256 $_.FullName) -eq $h } | Select-Object -First 1)
        if ($m.Count) { $hits += [pscustomobject]@{ Folder = $f; File = $m[0].Name } }
    }
    if ($hits.Count -eq 1) {
        $others = ($c | Where-Object { $_.FullName -ne $hits[0].Folder.FullName } | ForEach-Object { "'$($_.Name)'" }) -join ', '
        return [pscustomobject]@{ Pick = $hits[0].Folder; Refused = $false
            Message = "test build: '$($hits[0].Folder.Name)' - its $($hits[0].File) matches the recorded working hash $($h.Substring(0, 8))...; passed over $others" }
    }
    # THE PLAIN + FOMOD PAIR BOTH HOLDING THE BUILD (2026-10-27): AMF 2.3.1's plain folder and its FOMOD both carried the
    # tested DLL, the pick refused, and 'record working' kept no artefact list - so the other build line's hashes were
    # never recorded. When the matching folders are exactly '<Mod> V' and '<Mod> V FOMOD', the FOMOD is the release that
    # ships (as in the no-hash case above) and is the pick; its artefact list holds every line.
    if ($hits.Count -gt 1) {
        $fomHits = @($hits | Where-Object { $_.Folder.Name -like '* FOMOD' })
        if ($fomHits.Count -eq 1) {
            $plainName = $fomHits[0].Folder.Name.Substring(0, $fomHits[0].Folder.Name.Length - ' FOMOD'.Length)
            $rest = @($hits | Where-Object { $_.Folder.FullName -ne $fomHits[0].Folder.FullName })
            if (@($rest | Where-Object { $_.Folder.Name -ne $plainName }).Count -eq 0) {
                return [pscustomobject]@{ Pick = $fomHits[0].Folder; Refused = $false
                    Message = "test build: '$($fomHits[0].Folder.Name)' - it and '$plainName' both hold the recorded working hash $($h.Substring(0, 8))...; the FOMOD is the release that ships" }
            }
        }
    }
    $why = if ($hits.Count -eq 0) { "none of them holds an artefact matching the recorded working hash $($h.Substring(0, 8))..." }
           else { "$($hits.Count) of them match the recorded working hash $($h.Substring(0, 8))... ($((($hits | ForEach-Object { "'$($_.Folder.Name)'" }) -join ', ')))" }
    return [pscustomobject]@{ Pick = $null; Refused = $true; Message = "$($c.Count) test-build folders for this version ($names): $why - $owner." }
}
