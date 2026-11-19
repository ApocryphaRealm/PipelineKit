<#
.SYNOPSIS
    The dynamic package gate: evaluates every rule in gate-rules.json against a package and FAILS
    on any hit. Rules are data, so a new class of defect becomes a rule the day it is found.
.DESCRIPTION
    The owner, 2026-09-16, after a defect class that had already been "fixed" and written up shipped
    again: "come up with a way to dynamically add logic gates to close logic loops as needed when
    possible instead of just adding to the logic library" - and, the same night: "add any logic gates
    to the pipeline that would patch the issues in the logic library so they give a fail on a process
    when done incorrectly". The logic library records WHY; this file and gate-rules.json are the
    mechanism that stops the next package. pre-finalize-check.ps1 calls this; it can also be run by
    hand on any package folder.

    Rule kinds (the 'kind' field of a rule):
      forbid-path-regex             a relative path inside the package must not match 'pattern'
      forbid-extension              no file with 'extension' anywhere in the package
      esp-must-be-light             every .esp carries the light flag (0x200) and not the ESM bit (0x001)
      esp-form-version              every .esp's TES4 header is form version 'headerVersion' (44, SE) and
                                    no record in it is form version 0 (copied records keep their own)
      no-doubled-segment            no path has the same folder name twice in a row (Interface\Interface)
      keep-file-classes-of-previous every file class in 'classes' the PREVIOUS release shipped is still
                                    shipped (ini, esp, translations, line-17, line-se, swf, json)
      archive-matches-folder        the distro archive lists exactly the finalized folder's files
      page-text-forbid-regex        nexus-page.txt must not match 'pattern'
      page-text-require-regex       nexus-page.txt must match 'pattern' ({VERSION} and {identity:<key>} - the escaped identity.json value - are substituted)
      page-summary-max-chars        the Short Description block of nexus-page.txt (the line(s) after
                                    'Short Description:' or 'Summary (...):', up to the first blank line)
                                    is at most 'maxChars' characters; with 'forbidBBCode' it carries no
                                    BBCode tag (Nexus's summary field shows tags literally)
      esp-record-integrity          every plugin passes esp-audit.py: each COCT/LLCT/KSIZ count matches the
                                    entries that follow it, and no reference points at a record the file lacks
      json-parses                   every .json in the package parses (a lone backslash in a path is silent death)
      distro-images-are-sdr         no image in the Nexus distro folder carries an HDR (PQ) colour profile
      swf-colour-band               (rule.mods) no SWF carries a neutral colour inside lo..hi - a recolour read back
                                    from the shipped files (swf-colour-gate.py --band)
      forbid-file-content-regex     no file matching 'pathPattern' may match 'contentPattern' (the hit is quoted)
      forbid-private-identity-patterns  no file matching 'pathPattern' may match an "identity" pattern of the private
                                    config (role identity-patterns; the rule carries no pattern itself, the hit is not
                                    quoted); no such role = skip, a missing config = FAIL (2026-10-22)
      require-file-content-regex    a file matching 'pathPattern' must exist and its text must match
                                    'contentPattern' ({VERSION} substituted); 'onlyIfDll' limits it to
                                    packages that ship a DLL
      changelog-top-version         the distro changelog.txt starts with 'Version {VERSION}'
      distro-file-first-line        the distro folder's 'distroFile' exists and its first non-blank line matches
                                    'pattern' ({VERSION} substituted) - sticky.txt's "current version" line (2026-10-11)
      page-layout                   the page's live description source - the newest 'nexus-description-X.Y.Z.txt', else
                                    nexus-page.txt - is in the standard layout: at least 'minQuotes' [quote] panels,
                                    'minSpoilers' [spoiler] drop-downs and 'minImages' [img] pictures (2026-10-14)
      distro-file-max-chars         the distro folder's 'distroFile' is at most 'maxChars' characters, each line break
                                    counted as two (CRLF) - Nexus's 5,000-character comment cap for sticky.txt (2026-10-12)
      translations-complete         every <X>_<language>.txt has the same keys as <X>_english.txt
      lines-match-build-tree        if the repo has both build lines, the package ships both, each DLL
                                    byte-identical to its build tree and stamped with the version
      repo-script-passes            (rule.mods) the repo script 'script' exits 0 (the Modlist Manager's tools\selfcheck.py)
      distro-script-passes          the .MD\scripts check 'script' exits 0 when run with --path <the distro folder>
                                    (2026-10-12: gates\banner-highlight-gate.py - the banners' highlight boxes)
      distro-repo-script-passes     the same, called with --path <the distro folder> --repo <the repo>; skips when either
                                    is unknown (2026-10-22: gates\distro-licence-gate.py - a licence the banners or page
                                    text name must be the repo LICENSE's)
      dll-newer-than-sources        every packaged DLL is newer than every source file and CMakeLists
                                    in the repo (a bump-then-forgot-to-build, or a failed build, ships
                                    the previous binary under the new number); a repo that builds several DLLs may
                                    map each to its own sources in tools\dll-sources.json (2026-10-25); the
                                    top-level tools\*_check.* harnesses never count as sources (2026-10-25)
      dll-has-pdb                   every shipped .dll has a .pdb of the same name beside it (rule 43; the owner,
                                    2026-10-12: "pdb is required"); 'pathPattern' narrows which DLLs (a
                                    third-party proxy loader such as dinput8.dll is excluded there)
      launch-gate                   (2026-11-12) a LAUNCH gate's row: it is run by the launcher, not against the package;
                                    here it only proves it is still wired - 'script' exists under .MD\scripts and the
                                    launcher role 'launcher' (default game-relaunch) calls Find-Role '<role>'
    'exemptMods' lists display names / ledger keys the rule does not apply to; 'mods' limits any rule to the named ones.
    'kinds' limits a rule to mods whose version-registry.json 'kind' is listed (a mod with no kind is 'unknown' and skipped with a printed line).
    'onlyWhenFile' names a file beside this script; the rule is evaluated only while that file exists.

.PARAMETER Package     The package folder (in "7. current test builds" or "10. finalized mods").
.PARAMETER ModName     Display name (for exemptions and to find the distro folder, previous release and repo).
.PARAMETER Version     The version being packaged.
.PARAMETER DistroDir   The mod's "11. Nexus distro\<name>" folder. Optional; page/archive rules skip without it.
.PARAMETER Previous    The previous release's package folder. Optional; found automatically in "10. finalized mods".
.PARAMETER RepoPath    The repo. Optional; resolved from version-registry.json by display name.
.PARAMETER DeferRows   Row ids NOT evaluated in this run, each printed as 'defer'. Only finalize-mod.ps1 passes one (through
                       pre-finalize-check.ps1): distro-archive-equals-finalized-folder, judged by its post-check after the
                       move (2026-10-13). A stand-alone run defers nothing and evaluates every row.
#>
param(
    [Parameter(Mandatory = $true)][string]$Package,
    [string]$ModName,
    [string]$Version,
    [string]$DistroDir,
    [string]$Previous,
    [string]$RepoPath,
    [string]$Root = $env:PIPELINE_ROOT,
    [string]$RulesFile,   # the rules file; defaults to gate-rules.json beside this script (step 4.2, 2026-10-09)
    [string[]]$DeferRows  # rows the caller judges itself later (finalize-mod's post-check, 2026-10-13)
)
$ErrorActionPreference = 'Continue'
if (-not $Root) { $_kitRoot = $PSScriptRoot; while ($_kitRoot -and (Split-Path $_kitRoot -Leaf) -ne '.MD') { $_kitRoot = Split-Path $_kitRoot -Parent }; if ($_kitRoot) { $_kitRoot = Split-Path $_kitRoot -Parent }; $Root = $_kitRoot }   # kit: <ROOT> is the folder above the .MD this script sits under, unless PIPELINE_ROOT says otherwise
# Every lookup goes through the resolver OF THIS TREE (STEPS 5.4), never the absolute <ROOT> path: a copied
# tree (the golden test) then answers inside its own copy. Each role is looked up ONCE, here, at start.
$ResolverPy = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\resolvers\resolve.py'))
function Find-Role([string]$role) {
    $p = @(& py -3 $ResolverPy find $role)
    if ($LASTEXITCODE -ne 0 -or $p.Count -eq 0 -or -not "$($p[0])".Trim()) { Write-Output "package-gate: cannot resolve role '$role' ($($p -join ' '))"; exit 1 }
    return "$($p[0])".Trim()
}
$MdScripts = Find-Role 'md-scripts'    # the folder 'onlyWhenFile' and a rule's 'script' are relative to
$DistroNamesPath = Find-Role 'distro-names'
$RegistryPath = Find-Role 'version-registry'
$FomodDestinationsPath = Find-Role 'fomod-destinations'
$EspAuditPath = Find-Role 'esp-audit'
$SwfColourGatePath = Find-Role 'swf-colour-gate'
$IdentityRosterPath = Join-Path (Split-Path -Parent $ResolverPy) 'rosters\identity.json'    # a roster of this tree, beside its resolver
$rulesPath = if ($RulesFile) { $RulesFile } else { Find-Role 'gate-rules' }
# Validate the rules file this run is about to use before evaluating any rule (step 12.10, 2026-10-09): a gate that
# cannot trust its rules evaluates nothing - a gap is a gap, not a pass.
$schemaOut = @(& py -3 $ResolverPy check --schema gate-rules --rules-file $rulesPath 2>&1 | ForEach-Object { "$_" })
if ($LASTEXITCODE -ne 0) {
    foreach ($l in $schemaOut) { Write-Output $l }
    Write-Output '  FAIL  gate-rules.json does not match its schema - no rule was evaluated'
    exit 1
}
$rules = (Get-Content -LiteralPath $rulesPath -Raw -Encoding UTF8 | ConvertFrom-Json).rules
if (-not (Test-Path -LiteralPath $Package)) { Write-Output "package-gate: no such package folder: $Package"; exit 2 }
$Package = (Get-Item -LiteralPath $Package).FullName
if (-not $ModName) { $ModName = (Split-Path $Package -Leaf) -replace '\s+\d+\.\d+\.\d+.*$', '' }
if (-not $Version) { $m = [regex]::Match((Split-Path $Package -Leaf), '(\d+\.\d+\.\d+)'); if ($m.Success) { $Version = $m.Groups[1].Value } }
. $DistroNamesPath
# The package's game: the "<Game> - <Mod>" folder it sits in (2026-10-01), else its contents.
$pkgGame = Get-DistroFolderGame -Folder (Split-Path (Split-Path $Package -Parent) -Leaf)
if (-not $pkgGame) { $pkgGame = Get-PackageGame -Path $Package }
if (-not $DistroDir) {
    # "<Game> - <Mod>" since 2026-09-29, the game read from the package: the bare "11. Nexus distro\<Mod>"
    # join found nothing after the rename, so a gate run without -DistroDir skipped every page rule (found 2026-09-30)
    $c = Resolve-DistroFolder -ModName $ModName -Game $pkgGame -ProjectRoot $Root
    if ($c -and (Test-Path -LiteralPath $c)) { $DistroDir = $c }
}
# AN OPTIONAL FILE OF ANOTHER MOD'S PAGE (the owner, 2026-10-19; registry field optionalFileOf): the folder is the PARENT's
# and its page rows (version, sticky, banner, layout, links) judge the parent's page, which is gated when the parent
# finalizes - so they see no distro folder here and say so. A hand-given -DistroDir is left as given.
try {
    $optionalInfo = Get-OptionalFileInfo -ModName $ModName -ProjectRoot $Root
    if ($optionalInfo -and $DistroDir) {
        Write-Output "  note  '$ModName' is an optional file of '$($optionalInfo.parent)': the page rows judge the parent's page when the parent finalizes, so they are skipped here"
        $DistroDir = $null
    }
} catch { }
if (-not $RepoPath) {
    try {
        $reg = Get-Content -LiteralPath $RegistryPath -Raw -Encoding UTF8 | ConvertFrom-Json
        # a display name several games share (Camera Configuration Menu on Oblivion Remastered and Witcher 3, 2026-10-07):
        # the entry of THIS package's game wins - the first match had compared the Witcher 3 package with the Oblivion repo
        $hits = @($reg.PSObject.Properties | Where-Object { $_.Value.displayName -eq $ModName -or $_.Name -eq $ModName })
        if ($hits.Count -gt 1 -and $pkgGame) {
            $same = @($hits | Where-Object { (Get-ModGame -Entry $_.Value -ProjectRoot $Root) -eq $pkgGame })
            if ($same.Count -gt 0) { $hits = $same }
        }
        if ($hits.Count -gt 0) { $RepoPath = Join-Path $Root "6. current wip mods\$($hits[0].Value.repo)" }
    } catch { }
}
# The mod's registry 'kind' (skse-mod, or-mod, w3-mod, mo2-plugin, mo2-theme, skyrim-asset, tool) for a rule's 'kinds' list
# (step 4.2, 2026-10-09). Same identity as the repo lookup above: display name or key, and when several entries share the
# name the one of THIS package's game wins - never the first display-name match.
$modKind = 'unknown'
try {
    $kreg = Get-Content -LiteralPath $RegistryPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $kHits = @($kreg.PSObject.Properties | Where-Object { $_.Value.displayName -eq $ModName -or $_.Name -eq $ModName })
    if ($kHits.Count -gt 1 -and $pkgGame) {
        $kSame = @($kHits | Where-Object { (Get-ModGame -Entry $_.Value -ProjectRoot $Root) -eq $pkgGame })
        if ($kSame.Count -gt 0) { $kHits = $kSame }
    }
    if ($kHits.Count -gt 0 -and $kHits[0].Value.kind) { $modKind = [string]$kHits[0].Value.kind }
} catch { }

$files = Get-ChildItem -LiteralPath $Package -Recurse -File | ForEach-Object { $_.FullName.Substring($Package.Length + 1) }
$hasDll = @($files | Where-Object { $_ -match '\.dll$' }).Count -gt 0

# previous release: the newest folder in "10. finalized mods" for this mod with a LOWER version - of THIS package's game,
# read from its "<Game> - <Mod>" folder (2026-10-01; a name two games share used to find the other game's release)
if (-not $Previous) {
    $fin = Join-Path $Root '10. finalized mods'
    $cands = @(if ($pkgGame) { Find-Packages -Root $fin -Game $pkgGame -Folders -ProjectRoot $Root } else { Find-Packages -Root $fin -Folders -ProjectRoot $Root }) | Where-Object {
        $_.Name -like "$ModName *" -and $_.Name -match '(\d+\.\d+\.\d+)' } | ForEach-Object {
        [pscustomobject]@{ Dir = $_; Ver = [version]([regex]::Match($_.Name, '(\d+\.\d+\.\d+)').Groups[1].Value) } }
    if ($Version) { $cands = $cands | Where-Object { $_.Ver -lt [version]$Version } }
    $prev = $cands | Sort-Object Ver -Descending | Select-Object -First 1
    if ($prev) { $Previous = $prev.Dir.FullName }
}

function Classes($list) {
    $c = @{}
    foreach ($f in $list) {
        $l = $f.ToLowerInvariant()
        if ($l -match '\.ini$') { $c['ini'] = $true }
        if ($l -match '\.esp$|\.esl$') { $c['esp'] = $true }
        if ($l -match '[\\/]translations[\\/]') { $c['translations'] = $true }
        if ($l -match '(^|[\\/])line-17[\\/].*\.dll$') { $c['line-17'] = $true }
        if ($l -match '(^|[\\/])line-se[^\\/]*[\\/].*\.dll$') { $c['line-se'] = $true }
        if ($l -match '\.swf$') { $c['swf'] = $true }
        if ($l -match '\.json$') { $c['json'] = $true }
    }
    return $c
}
function Sha($p) { (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash }
# The version the REPO is at now (vcpkg.json version-string, else CMake project VERSION). The two
# build-tree rules only mean something while the repo still sits at the package's version; once it
# has been bumped past it, an older package is judged against sources that have moved on.
function RepoVersion($repo) {
    $vj = Join-Path $repo 'vcpkg.json'
    if (Test-Path -LiteralPath $vj) { $m = [regex]::Match((Get-Content -LiteralPath $vj -Raw), '"version-string"\s*:\s*"(\d+\.\d+\.\d+)"'); if ($m.Success) { return $m.Groups[1].Value } }
    $cm = Join-Path $repo 'CMakeLists.txt'
    if (Test-Path -LiteralPath $cm) { $m = [regex]::Match((Get-Content -LiteralPath $cm -Raw), '(?m)^\s*VERSION\s+(\d+\.\d+\.\d+)'); if ($m.Success) { return $m.Groups[1].Value } }
    return $null
}
# {identity:<key>} in a page-text pattern is replaced by the regex-ESCAPED "value" of that role in
# .MD\resolvers\rosters\identity.json (step 12.8, 2026-10-09). The roster JSON is read DIRECTLY, once per run, on the first
# pattern that needs it - no resolve.py subprocess per rule. An unknown key leaves the placeholder in the pattern, so the
# rule fails loudly instead of matching nothing.
$script:identityRoles = $null
# The part of a path INSIDE the repo (2026-10-12). The repo-source rows skip build output, git and vendored folders by
# matching folder names; matched against the FULL path, a folder ABOVE the repo counted too, and the old
# 'build-[^\/]+' (which excludes only '/', so it ran across backslashes) skipped every file under any '\build-...'
# parent - a repo there had every repo-source row skipped silently. Only the repo-relative part is matched now, and the
# build names are the ones the repos use: build, build17 / build<n>, build-release, build-<preset>, at any depth inside
# the repo (nested projects such as AMF's sdk\example\build have their own).
function Get-RepoRelative([string]$full) {
    if (-not $RepoPath) { return $full }
    $root = [System.IO.Path]::GetFullPath($RepoPath).TrimEnd('\', '/')
    if ($full.StartsWith($root + '\', [System.StringComparison]::OrdinalIgnoreCase) -or $full.StartsWith($root + '/', [System.StringComparison]::OrdinalIgnoreCase)) { return $full.Substring($root.Length) }
    return $full
}
function Sub($pat) {
    if ($Version) { $pat = ($pat -replace '\{VERSION\}', [regex]::Escape($Version)) }
    if ($pat -match '\{identity:[^}]+\}') {
        if ($null -eq $script:identityRoles) {
            $script:identityRoles = (Get-Content -LiteralPath $IdentityRosterPath -Raw -Encoding UTF8 | ConvertFrom-Json).roles
        }
        $pat = [regex]::Replace($pat, '\{identity:([^}]+)\}', {
            param($mm)
            $role = $script:identityRoles.PSObject.Properties[$mm.Groups[1].Value]
            if ($role -and $role.Value.value) { return [regex]::Escape([string]$role.Value.value) }
            return $mm.Value
        })
    }
    return $pat
}

$hits = [System.Collections.Generic.List[string]]::new()
$skips = [System.Collections.Generic.List[string]]::new()
$defers = [System.Collections.Generic.List[string]]::new()
$pageText = $null
if ($DistroDir -and (Test-Path -LiteralPath (Join-Path $DistroDir 'nexus-page.txt'))) { $pageText = Get-Content -LiteralPath (Join-Path $DistroDir 'nexus-page.txt') -Raw -Encoding UTF8 }

foreach ($r in $rules) {
    if ($DeferRows -and ($DeferRows -contains $r.id)) { $defers.Add("[$($r.id)] deferred by the caller - judged after the move (finalize-mod's post-check)"); continue }
    if ($r.exemptMods -and ($r.exemptMods -contains $ModName)) { continue }
    # 'kinds': the rule applies only to mods whose registry kind is listed; a mod with no kind is 'unknown' and is skipped
    # LOUDLY, never silently (step 4.2)
    if ($r.kinds -and ($r.kinds -notcontains $modKind)) {
        if ($modKind -eq 'unknown') { $skips.Add("$($r.id): mod kind unknown") }
        else { $skips.Add("$($r.id): skipped by kind - mod is '$modKind', rule applies to $(@($r.kinds) -join ', ')") }
        continue
    }
    if ($r.mods -and ($r.mods -notcontains $ModName)) { continue }   # any rule may be limited to named mods (2026-09-24)
    if ($r.onlyIfDll -and -not $hasDll) { continue }
    # 'onlyWhenFile': the rule applies only while that file (beside this script) exists - e.g. github-pushes-paused.txt (2026-10-07)
    if ($r.onlyWhenFile -and -not (Test-Path -LiteralPath (Join-Path $MdScripts $r.onlyWhenFile))) { continue }
    switch ($r.kind) {
        'forbid-path-regex' {
            foreach ($f in $files) { if ($f -match $r.pattern) { $hits.Add("[$($r.id)] $f") } }
        }
        'one-game-per-package' {
            # a package holding the 'markerPattern' tree (e.g. OblivionRemastered\) may hold no path matching 'pattern'
            # (another game's installer folders) - the two mods of one name must never share a package (2026-09-30)
            if (@($files | Where-Object { $_ -match $r.markerPattern }).Count -gt 0) {
                foreach ($f in $files) { if ($f -match $r.pattern) { $hits.Add("[$($r.id)] $f") } }
            }
        }
        'root-folder-needs-fomod' {
            # a top-level Root\ folder is Root Builder's (MO2) - Vortex deploys it as <game>\Root\..., so whatever is in
            # it never reaches the game there; such a package must be a FOMOD that places those files per manager
            # (AMF Witcher 3 1.0.2's loader, 2026-10-06)
            [string[]]$rootFiles = @($files | Where-Object { $_ -match '^Root[\\/]' })
            $fomod = @($files | Where-Object { $_ -match '(^|[\\/])fomod[\\/]ModuleConfig\.xml$' })
            if ($rootFiles.Count -gt 0 -and $fomod.Count -eq 0) {
                $hits.Add("[$($r.id)] $($rootFiles[0]) (and $($rootFiles.Count - 1) more) with no fomod\ModuleConfig.xml")
            }
        }
        'forbid-extension' {
            foreach ($f in $files) { if ($f.ToLowerInvariant().EndsWith($r.extension)) { $hits.Add("[$($r.id)] $f") } }
        }
        'esp-must-be-light' {
            foreach ($f in $files) {
                if ($f -notmatch '\.esp$') { continue }
                $b = [System.IO.File]::ReadAllBytes((Join-Path $Package $f))
                if ($b.Length -lt 12) { $hits.Add("[$($r.id)] $f is not a plugin"); continue }
                # An Oblivion-format plugin (TES4 for Oblivion / Oblivion Remastered) has a 20-byte record header, so
                # the HEDR subrecord tag sits at offset 20: no light flag exists in that format (2026-09-29, Simple
                # Loadout System for Oblivion Remastered's storage plugin).
                if ($b.Length -ge 24 -and [System.Text.Encoding]::ASCII.GetString($b, 20, 4) -eq 'HEDR') { continue }
                $flags = [BitConverter]::ToUInt32($b, 8)
                if (($flags -band 0x200) -eq 0) { $hits.Add("[$($r.id)] $f has no light flag (flags 0x{0:X8})" -f $flags) }
                if (($flags -band 0x1) -ne 0) { $hits.Add("[$($r.id)] $f carries the ESM bit (flags 0x{0:X8})" -f $flags) }
            }
        }
        'esp-form-version' {
            # The TES4 header's form version must be 'headerVersion' (44 = Skyrim SE; MO2 and LOOT
            # warn on anything lower). Then walk every record header (GRUP headers are 24 bytes and
            # nest; a record header is 24 bytes with the form version at offset 20) and report any
            # record whose form version is 0. Records are NOT required to be 44: a record copied
            # from a master keeps the master's number, and re-stamping one that carries a BODT as
            # 44 shifts every later field (Nordic Dragonbone 1.0.1 crashed on exactly that).
            $hdr = if ($r.headerVersion) { [int]$r.headerVersion } else { 44 }
            foreach ($f in $files) {
                if ($f -notmatch '\.esp$') { continue }
                $b = [System.IO.File]::ReadAllBytes((Join-Path $Package $f))
                if ($b.Length -lt 24) { $hits.Add("[$($r.id)] $f is not a plugin"); continue }
                # Oblivion-format plugin (20-byte record headers, HEDR at offset 20): no form version field (2026-09-29)
                if ([System.Text.Encoding]::ASCII.GetString($b, 20, 4) -eq 'HEDR') { continue }
                $tes4 = [BitConverter]::ToUInt16($b, 20)
                if ($tes4 -ne $hdr) { $hits.Add("[$($r.id)] $f TES4 header is form version $tes4, not $hdr") }
                $low = New-Object System.Collections.Generic.List[string]
                $stack = New-Object System.Collections.Generic.Stack[object]
                $stack.Push(@([long]0, [long]$b.Length))
                while ($stack.Count -gt 0) {
                    $range = $stack.Pop(); $pos = [long]$range[0]; $end = [long]$range[1]
                    while ($pos + 24 -le $end) {
                        $tag = [System.Text.Encoding]::ASCII.GetString($b, $pos, 4)
                        $size = [long][BitConverter]::ToUInt32($b, $pos + 4)
                        if ($tag -eq 'GRUP') {
                            if ($size -lt 24) { break }
                            $stack.Push(@([long]($pos + 24), [long]($pos + $size))); $pos += $size
                        } else {
                            $fv = [BitConverter]::ToUInt16($b, $pos + 20)
                            if ($fv -eq 0) { $low.Add("$tag") }
                            $pos += 24 + $size
                        }
                    }
                }
                if ($low.Count -gt 0) {
                    $sample = ($low | Select-Object -Unique | Select-Object -First 5) -join ', '
                    $hits.Add("[$($r.id)] $f has $($low.Count) record(s) with form version 0 ($sample)")
                }
            }
        }
        'esp-armo-modl-4-bytes' {
            # Every ARMO record's MODL subrecords (its armour-addon links) are 4 bytes each, one per
            # addon. Compressed records are inflated (zlib: skip the 2-byte header, then deflate).
            foreach ($f in $files) {
                if ($f -notmatch '\.esp$') { continue }
                $b = [System.IO.File]::ReadAllBytes((Join-Path $Package $f))
                if ($b.Length -lt 24) { continue }
                $bad = New-Object System.Collections.Generic.List[string]
                $stack = New-Object System.Collections.Generic.Stack[object]
                $stack.Push(@([long]0, [long]$b.Length))
                while ($stack.Count -gt 0) {
                    $range = $stack.Pop(); $pos = [long]$range[0]; $end = [long]$range[1]
                    while ($pos + 24 -le $end) {
                        $tag = [System.Text.Encoding]::ASCII.GetString($b, $pos, 4)
                        $size = [long][BitConverter]::ToUInt32($b, $pos + 4)
                        if ($tag -eq 'GRUP') { if ($size -lt 24) { break }; $stack.Push(@([long]($pos + 24), [long]($pos + $size))); $pos += $size; continue }
                        if ($tag -eq 'ARMO') {
                            $rflags = [BitConverter]::ToUInt32($b, $pos + 8); $fid = [BitConverter]::ToUInt32($b, $pos + 12)
                            $data = New-Object byte[] $size; [Array]::Copy($b, $pos + 24, $data, 0, $size)
                            if ($rflags -band 0x40000) {
                                $ms = New-Object System.IO.MemoryStream(,$data[6..($data.Length - 1)])
                                $ds = New-Object System.IO.Compression.DeflateStream($ms, [System.IO.Compression.CompressionMode]::Decompress)
                                $out = New-Object System.IO.MemoryStream; $ds.CopyTo($out); $data = $out.ToArray()
                            }
                            $i = 0
                            while ($i + 6 -le $data.Length) {
                                $st = [System.Text.Encoding]::ASCII.GetString($data, $i, 4); $sz = [BitConverter]::ToUInt16($data, $i + 4)
                                if ($st -eq 'MODL' -and $sz -ne 4) { $bad.Add(('ARMO {0:X8} MODL is {1} bytes' -f $fid, $sz)) }
                                $i += 6 + $sz
                            }
                        }
                        $pos += 24 + $size
                    }
                }
                if ($bad.Count -gt 0) { $hits.Add("[$($r.id)] ${f}: " + (($bad | Select-Object -First 4) -join '; ')) }
            }
        }
        'no-doubled-segment' {
            foreach ($f in $files) {
                $segs = $f -split '[\\/]'
                for ($i = 1; $i -lt $segs.Length - 1; $i++) { if ($segs[$i] -and $segs[$i] -ieq $segs[$i - 1]) { $hits.Add("[$($r.id)] $f"); break } }
            }
        }
        'package-file-matches-repo' {
            # THE STALE-CONTENT RULE (2026-09-19). A package is assembled by SEEDING from the
            # previous release and replacing the binaries, so every piece of content the assembler
            # does not explicitly refresh travels forward one version old - and a package that is
            # one version stale is indistinguishable from a correct one by eye. In one evening this
            # shipped last release's INI (compiled defaults and shipped INI disagreeing, rule 16),
            # last release's eleven translation files (a whole new page untranslated, rule 66) and
            # last release's README.
            #
            # Anything with a source of truth in the repo has to BE that file. Matched by name
            # wherever it sits in the package, because a FOMOD carries the same file several times
            # (Languages\<Lang>\, Languages\All\, Common\) and every copy must be the fresh one.
            #
            #   repoGlob     where the truth lives, relative to the repo (e.g. dist\Interface\Translations)
            #   filePattern  which package files this rule judges, by NAME
            if (-not $RepoPath -or -not (Test-Path -LiteralPath $RepoPath)) { $skips.Add("[$($r.id)] repo not resolved"); continue }
            $rv = RepoVersion $RepoPath
            if ($rv -and $Version -and $rv -ne $Version) { $skips.Add("[$($r.id)] repo is at $rv, not $Version - only the current release is judged"); continue }
            $truthDir = Join-Path $RepoPath $r.repoGlob
            if (-not (Test-Path -LiteralPath $truthDir)) { $skips.Add("[$($r.id)] repo has no $($r.repoGlob)"); continue }
            # One NAME can have several sources of truth (2026-10-08, AMF 2.1.6: themes\norden.ini and the art library's
            # assets\frames\norden.ini). The map keeps every one's hash, and a package copy passes when it is ANY of them:
            # keyed by name alone, the last one read won and the other same-named file was reported stale. A stale copy
            # still matches none of them, so nothing the rule exists to catch gets through.
            $truth = @{}
            foreach ($t in @(Get-ChildItem -LiteralPath $truthDir -Recurse -File -ErrorAction SilentlyContinue)) {
                if ($t.Name -match $r.filePattern) {
                    $k = $t.Name.ToLowerInvariant()
                    if (-not $truth.ContainsKey($k)) { $truth[$k] = @() }
                    $truth[$k] += (Sha $t.FullName)
                }
            }
            if ($truth.Count -eq 0) { $skips.Add("[$($r.id)] nothing matching $($r.filePattern) under $($r.repoGlob)"); continue }
            $checked = 0
            foreach ($rel in $files) {
                $name = Split-Path $rel -Leaf
                $key = $name.ToLowerInvariant()
                if (-not $truth.ContainsKey($key)) { continue }
                $checked++
                if ($truth[$key] -notcontains (Sha (Join-Path $Package $rel))) {
                    $hits.Add("[$($r.id)] $rel is not the repo's $($r.repoGlob)\$name - it is stale, or edited in the package instead of at its source")
                }
            }
            if ($checked -eq 0) { $skips.Add("[$($r.id)] the package ships none of those files") }
        }
        'keep-file-classes-of-previous' {
            if (-not $Previous -or -not (Test-Path -LiteralPath $Previous)) { $skips.Add("[$($r.id)] no previous release found to compare with"); continue }
            $pf = Get-ChildItem -LiteralPath $Previous -Recurse -File | ForEach-Object { $_.FullName.Substring($Previous.Length + 1) }
            $was = Classes $pf; $now = Classes $files
            foreach ($cls in $r.classes) { if ($was[$cls] -and -not $now[$cls]) { $hits.Add("[$($r.id)] previous release ($(Split-Path $Previous -Leaf)) shipped a '$cls' file; this package has none") } }
        }
        'fomod-delivers-previous-files' {
            # A FOMOD package must be able to install every game file the previous release installed (2026-09-24:
            # Norden UI - Black 1.0.3's installer had no entry for Interface\racemenu\buttonart.swf, which 1.0.2 shipped).
            # Both sides are compared as INSTALL DESTINATIONS (fomod-destinations.py); a flat previous release's
            # Common\ / Line-*\ / Languages\<x>\ prefix is dropped, and documents (readme, licence, notice, changelog,
            # fomod\, images\, meta.ini) are not game files.
            if (-not (Test-Path -LiteralPath (Join-Path $Package 'fomod\ModuleConfig.xml'))) { $skips.Add("[$($r.id)] not a FOMOD package"); continue }
            if (-not $Previous -or -not (Test-Path -LiteralPath $Previous)) { $skips.Add("[$($r.id)] no previous release found to compare with"); continue }
            $doc = '^(readme|license|licence|notice|third_party_notices|changelog)[^\\]*$|^(fomod|images)\\|^meta\.ini$|^[^\\]+\.(md|txt)$'
            $norm = { param($p) ($p -replace '^(common|line-[^\\]+|languages\\[^\\]+)\\', '') }
            $now = @{}; foreach ($d in @(& python $FomodDestinationsPath $Package)) { $now[(& $norm $d)] = $true }
            $lost = @(& python $FomodDestinationsPath $Previous | ForEach-Object { & $norm $_ } |
                Where-Object { $_ -and $_ -notmatch $doc -and -not $now[$_] } | Sort-Object -Unique)
            # RETIRED ON PURPOSE (2026-10-08): a rule row may list, per mod, install paths a release deliberately stopped
            # shipping - each with the version that retired them and why (AMF 2.1.6 moved its themes' art from
            # themes\<name>\*.png into the assets\ library). Only those paths are let through; anything else lost still fails.
            foreach ($ret in @($r.retired)) {
                if (-not $ret -or -not $ret.pattern) { continue }
                if ($ret.mod -and $ModName -and $ret.mod -ne $ModName) { continue }
                $lost = @($lost | Where-Object { $_ -notmatch $ret.pattern })
            }
            foreach ($l in $lost) { $hits.Add("[$($r.id)] previous release ($(Split-Path $Previous -Leaf)) installed $l; no entry in this installer can") }
        }
        'package-ships-repo-dist' {
            # Every file the repo keeps in dist\ has to reach the package. The packager seeds from the
            # previous release, so a NEW class of shipped file is exactly what it drops - Model Sync 1.0.3
            # absorbed Loading Menu Overhaul and packaged without its loadingmenu.swf (2026-09-19).
            # Matched by FILE NAME, wherever the package puts it, so a FOMOD's own shape still passes.
            if (-not $RepoPath -or -not (Test-Path -LiteralPath $RepoPath)) { $skips.Add("[$($r.id)] repo not resolved"); continue }
            $distDir = Join-Path $RepoPath 'dist'
            if (-not (Test-Path -LiteralPath $distDir)) { $skips.Add("[$($r.id)] repo has no dist folder"); continue }
            # 2026-11-12 (Simple Dodge 1.1.0): matching by name alone passed a package that lacked
            # magicbehavior\#sdge$97.txt because 1hm_behavior\#sdge$97.txt had the same name. A dist file now passes
            # when the package has it at its own relative path (at the root, under Common\, or under an option
            # folder), or - a FOMOD moving it on purpose - a file of that name OUTSIDE Common\.
            $relSet = @{}; $tails = New-Object System.Collections.Generic.List[string]; $nameOutsideCommon = @{}
            foreach ($f in $files) {
                $lf = $f.ToLowerInvariant().Replace('/', '\')
                $relSet[$lf] = $true; $tails.Add('\' + $lf)
                if (-not $lf.StartsWith('common\')) { $nameOutsideCommon[(Split-Path $lf -Leaf)] = $true }
            }
            foreach ($f in @(Get-ChildItem -LiteralPath $distDir -Recurse -File -Force -ErrorAction SilentlyContinue)) {
                $rel = $f.FullName.Substring($distDir.Length + 1).ToLowerInvariant()
                if ($relSet.ContainsKey($rel) -or $relSet.ContainsKey('common\' + $rel)) { continue }
                $tail = '\' + $rel
                if (@($tails | Where-Object { $_.EndsWith($tail) }).Count -gt 0) { continue }
                if ($nameOutsideCommon.ContainsKey($f.Name.ToLowerInvariant())) { continue }
                $hits.Add("[$($r.id)] the repo ships dist\$($f.FullName.Substring($distDir.Length + 1)) but the package has no file at that path")
            }
        }
        'archive-matches-folder' {
            if (-not $DistroDir) { $skips.Add("[$($r.id)] no distro folder"); continue }
            # SEVERAL DOWNLOADS (2026-11-12, nexus-files.json in the distro folder): each manifest entry's archive
            # "<package> - <folder>.zip" must list exactly that package subfolder, and every subfolder must be in an entry
            if (Test-Path -LiteralPath (Join-Path $DistroDir 'nexus-files.json')) {
                $nf = @(& python (Find-Role 'nexus-files') gate $Package $DistroDir 2>&1 | ForEach-Object { "$_" })
                foreach ($l in $nf) { if ($l -like 'HIT *') { $hits.Add("[$($r.id)] $($l.Substring(4))") } }
                if ($LASTEXITCODE -ne 0 -and -not @($nf | Where-Object { $_ -like 'HIT *' }).Count) { $hits.Add("[$($r.id)] nexus_files.py gate failed: $($nf -join ' ')") }
                continue
            }
            # The archive named for THIS package first (2026-09-29): "<Package> X.Y.Z - SDK.zip" sorts before
            # "<Package> X.Y.Z.zip" (' ' < '.'), so a bare "*X.Y.Z*" pick compared the AMF-OR SDK optional file with the
            # main folder (32 false hits) and never looked at the main archive at all.
            $cands = @(Get-ChildItem -LiteralPath $DistroDir -File | Where-Object { $_.Extension -in '.zip', '.7z' -and $_.Name -like "*$Version*" })
            $pkgLeaf = Split-Path $Package -Leaf
            $arc = $cands | Where-Object { $_.BaseName -eq $pkgLeaf } | Select-Object -First 1
            if (-not $arc) { $arc = $cands | Where-Object { $_.BaseName -notmatch '\s-\s[^\d]+$' } | Select-Object -First 1 }
            if (-not $arc) { $arc = $cands | Select-Object -First 1 }
            if (-not $arc) { $hits.Add("[$($r.id)] no archive for $Version in $DistroDir"); continue }
            $sz = 'C:\Program Files\7-Zip\7z.exe'
            # -slt prints one block per entry. Zip blocks carry "Folder = +/-"; 7z blocks carry only
            # "Attributes = D..." for a folder - so an entry is a FILE when its Attributes line does not
            # start with D, and a directory otherwise. The first block is the archive itself.
            $attrs = & $sz l -slt "$($arc.FullName)" 2>&1 | ForEach-Object { "$_" }
            $inArc = @{}
            $cur = $null
            foreach ($line in $attrs) {
                if ($line -like 'Path = *') { $cur = $line.Substring(7) }
                elseif ($line -like 'Attributes = *' -and $cur -and $cur -ne $arc.FullName) {
                    if (-not $line.Substring(13).StartsWith('D')) { $inArc[$cur.ToLowerInvariant()] = $true }
                }
            }
            $folderSet = @{}
            foreach ($f in $files) { $folderSet[$f.ToLowerInvariant()] = $true }
            foreach ($k in $folderSet.Keys) { if (-not $inArc[$k]) { $hits.Add("[$($r.id)] archive $($arc.Name) lacks $k") } }
            foreach ($k in $inArc.Keys) { if (-not $folderSet[$k]) { $hits.Add("[$($r.id)] archive $($arc.Name) has extra file $k") } }
        }
        'archive-entries-forward-slash' {
            # 7-Zip normalises separators when it lists, so archive-matches-folder cannot see this: read the zip's own
            # central directory. A backslash in an entry name is what Windows PowerShell 5.1's Compress-Archive writes,
            # and some managers extract "Common\SKSE\x.ini" as ONE file with that name instead of a folder tree.
            if (-not $DistroDir) { $skips.Add("[$($r.id)] no distro folder"); continue }
            $zips = @(Get-ChildItem -LiteralPath $DistroDir -File | Where-Object { $_.Extension -eq '.zip' -and $_.Name -like "*$Version*" })
            if (-not $zips.Count) { $skips.Add("[$($r.id)] no .zip for $Version in the distro folder"); continue }
            Add-Type -AssemblyName System.IO.Compression.FileSystem
            foreach ($z in $zips) {
                $za = [System.IO.Compression.ZipFile]::OpenRead($z.FullName)
                try {
                    $bad = @($za.Entries | Where-Object { $_.FullName.Contains('\') } | Select-Object -First 3)
                    foreach ($e in $bad) { $hits.Add("[$($r.id)] $($z.Name) entry uses backslashes: $($e.FullName)") }
                } finally { $za.Dispose() }
            }
        }
        'page-text-forbid-regex' {
            if (-not $pageText) { $skips.Add("[$($r.id)] no nexus-page.txt"); continue }
            $m = [regex]::Matches($pageText, (Sub $r.pattern))
            foreach ($x in $m) { $hits.Add("[$($r.id)] page text: '$($x.Value)'") }
        }
        'page-text-require-regex' {
            if (-not $pageText) { $skips.Add("[$($r.id)] no nexus-page.txt"); continue }
            $pat = Sub $r.pattern
            if (-not [regex]::IsMatch($pageText, $pat)) { $hits.Add("[$($r.id)] page text does not match: $pat") }
        }
        'page-layout' {
            # THE STANDARD LAYOUT (2026-10-14, the owner: "it looks like Simple Loadout System's description wasn't updated
            # with the new template like it was supposed to have been"). Every text-fact row reads nexus-page.txt; none
            # looked at the layout, so a page posted in the old plain-text format passed. The live description source is
            # the newest nexus-description-X.Y.Z.txt where the page was built in the layout (AMF and the others), else
            # nexus-page.txt. The layout's markers: quote panels round the text, drop-downs, and the drawn cards and banners.
            if (-not $DistroDir -or -not (Test-Path -LiteralPath $DistroDir)) { $skips.Add("[$($r.id)] no distro folder"); continue }
            $descs = @(Get-ChildItem -LiteralPath $DistroDir -File -Filter 'nexus-description-*.txt' -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -match '^nexus-description-(\d+)\.(\d+)\.(\d+)\.txt$' } |
                Sort-Object { [version]([regex]::Match($_.Name, '(\d+\.\d+\.\d+)').Groups[1].Value) } -Descending)
            $src = if ($descs.Count) { $descs[0].FullName } else { Join-Path $DistroDir 'nexus-page.txt' }
            if (-not (Test-Path -LiteralPath $src)) { $skips.Add("[$($r.id)] no description source"); continue }
            $txt = Get-Content -LiteralPath $src -Raw -Encoding UTF8
            $nq = ([regex]::Matches($txt, '(?i)\[quote\]')).Count
            $ns = ([regex]::Matches($txt, '(?i)\[spoiler\]')).Count
            $ni = ([regex]::Matches($txt, '(?i)\[img[\] =]')).Count
            $want = @()
            if ($nq -lt [int]$r.minQuotes) { $want += "$nq of $($r.minQuotes) [quote] panels" }
            if ($ns -lt [int]$r.minSpoilers) { $want += "$ns of $($r.minSpoilers) [spoiler] drop-downs" }
            if ($ni -lt [int]$r.minImages) { $want += "$ni of $($r.minImages) [img] pictures" }
            if ($want.Count) { $hits.Add("[$($r.id)] $(Split-Path $src -Leaf) is not in the standard layout: $($want -join ', ') - $($r.fix)") }
        }
        'page-summary-max-chars' {
            # The short description lives in short-description.txt beside nexus-page.txt since 2026-09-30 (the owner:
            # Claude posts the pages, so the summary need not share the description's file); the old in-page block is
            # still read for a folder not yet split.
            $sdFile = if ($DistroDir) { Join-Path $DistroDir 'short-description.txt' } else { $null }
            $sumBlock = $null
            if ($sdFile -and (Test-Path -LiteralPath $sdFile)) { $sumBlock = Get-Content -LiteralPath $sdFile -Raw -Encoding UTF8 }
            elseif ($pageText) {
                $sm = [regex]::Match($pageText, '(?m)^\uFEFF?(Short Description:|Summary \([^)]*\):)[ \t]*(\r?\n)+((?:[^\r\n]+(?:\r?\n)?)+)')
                if ($sm.Success) { $sumBlock = $sm.Groups[3].Value }
            }
            if (-not $sumBlock) { $skips.Add("[$($r.id)] no short-description.txt or Short Description block (optional-file page?)"); continue }
            $sumLines = @($sumBlock -split '\r?\n' | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' })
            $summary = $sumLines -join ' '
            $max = [int]$r.maxChars
            if ($summary.Length -gt $max) {
                $cut = $summary.Substring([Math]::Max(0, $max - 24), [Math]::Min(24, $max))
                $hits.Add("[$($r.id)] Short Description is $($summary.Length) chars; Nexus keeps $max and drops the rest - the live page would end at '...$cut'")
            }
            if ($r.forbidBBCode -and $summary -match '\[/?(b|i|u|url|size|color|img)(=[^\]]*)?\]') { $hits.Add("[$($r.id)] Short Description carries BBCode, which Nexus's summary field shows as literal text") }
        }
        'esp-record-integrity' {
            # 2026-09-19: two CNTO entries were removed from a container without decrementing COCT, and the game
            # died at data load inside SPID with a null form - the count is a promise the engine trusts. esp-audit.py
            # checks every count subrecord against the entries that follow it, plus own-file references.
            # 2026-10-25: a row may keep only the FAIL lines matching rule.failPattern, or drop those matching
            # rule.skipPattern, so one audit run can report under separate rows (esp-records-sit-in-their-groups takes
            # esp-audit's "group tree:" lines; esp-counts-match-entries the rest).
            foreach ($f in $files) {
                if ($f -notmatch '\.(esp|esl|esm)$') { continue }
                $o = & python $EspAuditPath (Join-Path $Package $f) 2>&1
                if ($LASTEXITCODE -ne 0) {
                    foreach ($l in @($o | Where-Object { $_ -match 'FAIL' -and $_ -notmatch 'plugin\(s\) would load a lie' })) {
                        if ($r.failPattern -and $l -notmatch $r.failPattern) { continue }
                        if ($r.skipPattern -and $l -match $r.skipPattern) { continue }
                        $hits.Add("[$($r.id)] $f $l".Trim())
                    }
                }
            }
        }
        'swf-colour-band' {
            # 2026-09-22 (Norden UI - Black): a recolour is proved on the SHIPPED file, and a flat "nothing brighter than
            # 40" check fails a menu whose white text is meant to stay white (RaceMenu's racesex_menu). The band is the
            # grey the recolour removes: any neutral inside it means a file was not recoloured or was overwritten by an
            # unrecoloured copy. rule.mods limits it to named mods; lo/hi give the band; swf-colour-gate.py does the reading.
            if ($r.mods -and ($r.mods -notcontains $ModName)) { continue }
            $swfs = @($files | Where-Object { $_ -match '\.swf$' })
            if (-not $swfs) { $hits.Add("[$($r.id)] no SWF in the package"); continue }
            $dirs = @($swfs | ForEach-Object { ($_ -split '[\\/]')[0] } | Sort-Object -Unique | ForEach-Object { Join-Path $Package $_ })
            $extra = @(); if ($r.allowGrey) { $extra = @('--allow-grey', [string]$r.allowGrey) }
            $out = & python $SwfColourGatePath @dirs --band "$($r.lo),$($r.hi)" @extra 2>&1
            if ($LASTEXITCODE -ne 0) {
                foreach ($l in ($out | Where-Object { $_ -match 'FAIL' })) { $hits.Add("[$($r.id)] $l") }
            }
        }
        'distro-images-are-sdr' {
            # 2026-09-22: the owner's Community Shaders captures are Windows HDR (PQ / BT.2020, ICC "RGB_D65_202_Rel_PeQ").
            # Used as-is in a banner they render near-black (profile honoured) or washed out (profile stripped). Every
            # image in the distro folder must be SDR; hdr-screenshot-to-sdr.py converts a capture properly.
            if (-not $DistroDir -or -not (Test-Path -LiteralPath $DistroDir)) { $skips.Add("[$($r.id)] no distro folder"); continue }
            $out = & python -c "import sys,io,glob,os`nfrom PIL import Image`nbad=[]`nfor f in glob.glob(os.path.join(sys.argv[1],'**','*.*'),recursive=True):`n  if not f.lower().endswith(('.png','.jpg','.jpeg')): continue`n  try: im=Image.open(f)`n  except Exception: continue`n  icc=im.info.get('icc_profile')`n  if not icc: continue`n  from PIL import ImageCms`n  d=ImageCms.getProfileDescription(ImageCms.ImageCmsProfile(io.BytesIO(icc)))`n  if 'PeQ' in d or 'PQ' in d.split('_') or '2084' in d: bad.append(os.path.relpath(f,sys.argv[1]))`nprint('\n'.join(bad))" $DistroDir 2>&1
            foreach ($l in @($out | Where-Object { $_ -and $_.Trim() })) { $hits.Add("[$($r.id)] $l is an HDR (PQ) image - convert it with hdr-screenshot-to-sdr.py") }
        }
        'repo-script-passes' {
            # A check that only the mod's own repo knows how to run (2026-09-24: the Modlist Manager's proposed order must
            # pass the launch audit - tools\selfcheck.py). 'script' is relative to the repo; exit 0 passes. Use 'mods'.
            if (-not $RepoPath -or -not (Test-Path -LiteralPath $RepoPath)) { $skips.Add("[$($r.id)] repo not resolved"); continue }
            $script = Join-Path $RepoPath $r.script
            if (-not (Test-Path -LiteralPath $script)) { $hits.Add("[$($r.id)] the repo has no $($r.script)"); continue }
            $out = & python $script 2>&1
            if ($LASTEXITCODE -ne 0) {
                $hits.Add("[$($r.id)] $($r.script) failed: " + ((@($out) | Where-Object { "$_" -match 'FAIL' } | Select-Object -First 4) -join ' | '))
            }
        }
        'distro-script-passes' {
            # A shared check in .MD\scripts run against the Nexus distro folder (2026-10-12: banner-highlight-gate.py -
            # make-feature-banners.py had left a template's extra highlight boxes on new banners). 'script' is relative
            # to this folder and is called with --path <distro folder>; exit 0 passes.
            if (-not $DistroDir -or -not (Test-Path -LiteralPath $DistroDir)) { $skips.Add("[$($r.id)] no distro folder"); continue }
            $script = Join-Path $MdScripts $r.script
            if (-not (Test-Path -LiteralPath $script)) { $hits.Add("[$($r.id)] missing $($r.script)"); continue }
            $out = & python $script --path $DistroDir 2>&1
            if ($LASTEXITCODE -ne 0) {
                $hits.Add("[$($r.id)] $($r.script) failed: " + ((@($out) | Where-Object { "$_" -match 'FAIL' } | Select-Object -First 4) -join ' | '))
            }
        }
        'distro-repo-script-passes' {
            # A shared check in .MD\scripts that compares the Nexus distro folder with the repo (2026-10-22:
            # distro-licence-gate.py - Lock Interaction Overhaul's banner still said "MIT, open source" a month after
            # the GPL relicence that Nexus had demanded). Called with --path <distro folder> --repo <repo>; exit 0 passes.
            if (-not $DistroDir -or -not (Test-Path -LiteralPath $DistroDir)) { $skips.Add("[$($r.id)] no distro folder"); continue }
            if (-not $RepoPath -or -not (Test-Path -LiteralPath $RepoPath)) { $skips.Add("[$($r.id)] repo not resolved"); continue }
            $script = Join-Path $MdScripts $r.script
            if (-not (Test-Path -LiteralPath $script)) { $hits.Add("[$($r.id)] missing $($r.script)"); continue }
            $out = & python $script --path $DistroDir --repo $RepoPath 2>&1
            if ($LASTEXITCODE -ne 0) {
                $hits.Add("[$($r.id)] $($r.script) failed: " + ((@($out) | Where-Object { "$_" -match 'FAIL' } | Select-Object -First 4) -join ' | '))
            }
        }
        'launch-gate' {
            # A launch gate's row (2026-11-12, pandora-output-fresh-gate): judged at launch, so here only its wiring - the
            # script exists and the launcher still resolves its role. A launch gate dropped from the launcher fails here.
            $script = Join-Path $MdScripts $r.script
            if (-not (Test-Path -LiteralPath $script)) { $hits.Add("[$($r.id)] missing $($r.script)"); continue }
            $launcherRole = if ($r.launcher) { $r.launcher } else { 'game-relaunch' }
            $launcher = "$(@(& py -3 $ResolverPy find $launcherRole 2>$null)[0])".Trim()
            if (-not $launcher -or -not (Test-Path -LiteralPath $launcher)) { $hits.Add("[$($r.id)] launcher role '$launcherRole' not found"); continue }
            if (-not (Select-String -LiteralPath $launcher -SimpleMatch -Quiet -Pattern ("Find-Role '" + $r.role + "'"))) {
                $hits.Add("[$($r.id)] $launcherRole no longer calls the launch gate '$($r.role)' - wire it back before the launch chain")
            }
        }
        'package-script-passes' {
            # A shared check in .MD\scripts run against the package folder (2026-09-27: xinput-import-gate.py). 'script' is
            # relative to this folder and is called with --path <package>, plus --repo <repo> when the repo is known
            # (cpp-escape-gate.py reads the source); exit 0 passes.
            $script = Join-Path $MdScripts $r.script
            if (-not (Test-Path -LiteralPath $script)) { $hits.Add("[$($r.id)] missing $($r.script)"); continue }
            $scriptArgs = @('--path', $Package)
            if ($RepoPath -and (Test-Path -LiteralPath $RepoPath)) { $scriptArgs += @('--repo', $RepoPath) }
            $out = & python $script @scriptArgs 2>&1
            if ($LASTEXITCODE -ne 0) {
                $hits.Add("[$($r.id)] $($r.script) failed: " + ((@($out) | Where-Object { "$_" -match 'FAIL' } | Select-Object -First 4) -join ' | '))
            }
        }
        'json-parses' {
            # 2026-09-19: a Dynamic Interface Patcher descriptor was written with a single backslash in a Windows
            # path, so the patcher rejected the whole file as invalid_escape and silently patched nothing.
            foreach ($f in $files) {
                if ($f -notmatch '\.json$') { continue }
                try { Get-Content -LiteralPath (Join-Path $Package $f) -Raw -Encoding UTF8 | ConvertFrom-Json | Out-Null }
                catch { $hits.Add("[$($r.id)] $f is not valid JSON: $($_.Exception.Message)") }
            }
        }
        'forbid-file-content-regex' {
            $fmatches = @($files | Where-Object { $_ -match $r.pathPattern })
            foreach ($f in $fmatches) {
                $t = Get-Content -LiteralPath (Join-Path $Package $f) -Raw -Encoding UTF8
                if (-not $t) { continue }
                foreach ($x in [regex]::Matches($t, (Sub $r.contentPattern))) { $hits.Add("[$($r.id)] $f says '$($x.Value)'") }
            }
        }
        'forbid-private-identity-patterns' {
            # 2026-10-22: the owner's identity (name, email, account, home path) must not ship, and the rule must not
            # carry it either - a character-class spelling in a public rules file still spells it. The patterns are read
            # from the private config at role identity-patterns ("identity" list); no file matching 'pathPattern' may
            # match one. A tree with no such role (a kit install) skips; a tree whose role names a missing or broken
            # file FAILS - the check cannot be skipped by losing its config.
            if ($null -eq $script:privateIdentity) {
                $script:privateIdentity = @()
                # PIPELINE_IDENTITY_CONFIG overrides the role (the self-test points it at made-up patterns)
                if ($env:PIPELINE_IDENTITY_CONFIG) { $ip = @($env:PIPELINE_IDENTITY_CONFIG); $global:LASTEXITCODE = 0 }
                else { $ip = @(& py -3 $ResolverPy find identity-patterns 2>&1 | ForEach-Object { "$_" }) }
                if ($LASTEXITCODE -ne 0) { $script:privateIdentityState = 'no-role' }
                elseif (-not (Test-Path -LiteralPath "$($ip[0])".Trim())) { $script:privateIdentityState = "missing: $("$($ip[0])".Trim())" }
                else {
                    try {
                        $cfg = Get-Content -LiteralPath "$($ip[0])".Trim() -Raw -Encoding UTF8 | ConvertFrom-Json
                        $script:privateIdentity = @($cfg.identity | Where-Object { $_.pattern } | ForEach-Object { [pscustomobject]@{ id = $_.id; rx = [regex]::new([string]$_.pattern) } })
                        $script:privateIdentityState = if ($script:privateIdentity.Count) { 'ok' } else { 'empty' }
                    } catch { $script:privateIdentityState = "broken: $($_.Exception.Message)" }
                }
            }
            if ($script:privateIdentityState -eq 'no-role') { $skips.Add("[$($r.id)] no identity-patterns role in this tree"); continue }
            if ($script:privateIdentityState -ne 'ok') { $hits.Add("[$($r.id)] the private identity config is $($script:privateIdentityState) - the check cannot run (role identity-patterns)"); continue }
            foreach ($f in @($files | Where-Object { $_ -match $r.pathPattern })) {
                $t = Get-Content -LiteralPath (Join-Path $Package $f) -Raw -Encoding UTF8
                if (-not $t) { continue }
                foreach ($p in $script:privateIdentity) {
                    $x = $p.rx.Match($t)
                    if ($x.Success) { $hits.Add("[$($r.id)] $f carries the owner's identity (pattern $($p.id)) at offset $($x.Index) - $($r.fix)") }
                }
            }
        }
        'dll-has-pdb' {
            # Rule 43 made a gate (the owner, 2026-10-12: "pdb is required"). package-mod.ps1 logged a missing PDB as
            # 'ABSENT' and carried on, and keep-what-the-previous-release-shipped only caught a mod that had shipped one
            # before: four Skyrim packages in 10. finalized mods carried a DLL with no PDB (2026-10-12 scan).
            $dlls = @($files | Where-Object { $_ -match '(?i)\.dll$' -and (-not $r.pathPattern -or $_ -match $r.pathPattern) })
            foreach ($d in $dlls) {
                $pdb = [System.IO.Path]::ChangeExtension($d, '.pdb')
                if (-not @($files | Where-Object { $_ -ieq $pdb }).Count) { $hits.Add("[$($r.id)] $d ships without $(Split-Path $pdb -Leaf) beside it - $($r.fix)") }
            }
        }
        'skse-log-forbid-regex' {
            # The SKSE log of the LAST RUN of this mod - the run the ledger evidence comes from - must not carry the
            # pattern. rule.mods limits it to named mods (display names); logFile is the file under
            # Documents\My Games\Skyrim Special Edition\SKSE. No log at all is a hit too: a package without a run
            # behind it has no business at this gate.
            if ($r.mods -and ($r.mods -notcontains $ModName)) { continue }
            # logFolder (optional, under Documents\My Games) serves other games: "Oblivion Remastered\OBSE\Logs"
            $docs = [Environment]::GetFolderPath('MyDocuments')
            $logFolder = if ($r.logFolder) { $r.logFolder } else { 'Skyrim Special Edition\SKSE' }
            $logPath = Join-Path $docs "My Games\$logFolder\$($r.logFile)"
            if (-not (Test-Path -LiteralPath $logPath)) { $hits.Add("[$($r.id)] no $($r.logFile) under $docs - no run to read"); continue }
            $t = Get-Content -LiteralPath $logPath -Raw -Encoding UTF8
            foreach ($x in [regex]::Matches($t, (Sub $r.contentPattern))) { $hits.Add("[$($r.id)] $($r.logFile) says '$($x.Value)'") }
        }
        'require-file-content-regex' {
            $matches = @($files | Where-Object { $_ -match $r.pathPattern })
            if ($matches.Count -eq 0) { $hits.Add("[$($r.id)] no file matching $($r.pathPattern) in the package"); continue }
            $pat = Sub $r.contentPattern
            $ok = $false
            foreach ($f in $matches) { $t = Get-Content -LiteralPath (Join-Path $Package $f) -Raw -Encoding UTF8; if ($t -and [regex]::IsMatch($t, $pat)) { $ok = $true; break } }
            if (-not $ok) { $hits.Add("[$($r.id)] none of $($matches -join ', ') matches: $pat") }
        }
        'changelog-top-version' {
            if (-not $DistroDir) { $skips.Add("[$($r.id)] no distro folder"); continue }
            $cl = Join-Path $DistroDir 'changelog.txt'
            if (-not (Test-Path -LiteralPath $cl)) { $hits.Add("[$($r.id)] no changelog.txt in $DistroDir"); continue }
            $first = (Get-Content -LiteralPath $cl -Encoding UTF8 | Where-Object { $_.Trim() } | Select-Object -First 1)
            if ($first -notmatch "^\s*(Version\s+)?$([regex]::Escape($Version))\s*$") { $hits.Add("[$($r.id)] changelog.txt starts with '$first', not 'Version $Version'") }
        }
        'distro-file-first-line' {
            # A file of the distro folder (r.distroFile) must exist and its first non-blank line match r.pattern, {VERSION}
            # substituted and escaped. Added 2026-10-11 for sticky.txt, the Posts tab's "Recent changes" sticky: its first
            # line names the version being released, so a release cannot finalize with last release's sticky.
            if (-not $DistroDir) { $skips.Add("[$($r.id)] no distro folder"); continue }
            $df = Join-Path $DistroDir $r.distroFile
            if (-not (Test-Path -LiteralPath $df)) { $hits.Add("[$($r.id)] no $($r.distroFile) in $DistroDir"); continue }
            $first = (Get-Content -LiteralPath $df -Encoding UTF8 | Where-Object { $_.Trim() } | Select-Object -First 1)
            $pat = Sub $r.pattern
            if (-not $first -or $first -notmatch $pat) { $hits.Add("[$($r.id)] $($r.distroFile) starts with '$first', not the line for $Version ($pat)") }
        }
        'distro-file-max-chars' {
            # A file of the distro folder (r.distroFile) is at most r.maxChars characters, every line break counted as TWO
            # (CRLF), the way Nexus counts a comment. Added 2026-10-12: AMF 2.1.9's sticky.txt was 5,376 and Nexus refused
            # the Posts-tab comment (cap 5,000). A missing file is the distro-file-first-line row's business, not this one's.
            if (-not $DistroDir) { $skips.Add("[$($r.id)] no distro folder"); continue }
            $df = Join-Path $DistroDir $r.distroFile
            if (-not (Test-Path -LiteralPath $df)) { $skips.Add("[$($r.id)] no $($r.distroFile)"); continue }
            $txt = ([System.IO.File]::ReadAllText($df, [System.Text.Encoding]::UTF8)).TrimStart([char]0xFEFF) -replace "`r`n", "`n" -replace "`r", "`n"
            $len = $txt.Length + ([regex]::Matches($txt, "`n")).Count
            if ($len -gt [int]$r.maxChars) { $hits.Add("[$($r.id)] $($r.distroFile) is $len characters counting CRLF line breaks - over Nexus's $($r.maxChars); $($r.fix)") }
        }
        'translations-complete' {
            $tr = @($files | Where-Object { $_ -match '[\\/]Translations[\\/][^\\/]+_english\.txt$' })
            foreach ($en in $tr) {
                $dir = Split-Path $en; $stem = (Split-Path $en -Leaf) -replace '_english\.txt$', ''
                $enKeys = @{}
                foreach ($line in (Get-Content -LiteralPath (Join-Path $Package $en) -Encoding Unicode)) { if ($line -match '^\s*(\$\S+)') { $enKeys[$matches[1]] = $true } }
                if ($enKeys.Count -eq 0) { foreach ($line in (Get-Content -LiteralPath (Join-Path $Package $en) -Encoding UTF8)) { if ($line -match '^\s*(\$\S+)') { $enKeys[$matches[1]] = $true } } }
                if ($enKeys.Count -eq 0) { $skips.Add("[$($r.id)] $en has no `$keys in either encoding"); continue }
                foreach ($other in ($files | Where-Object { $_ -like "$dir\$stem`_*.txt" -and $_ -ne $en })) {
                    $keys = @{}
                    foreach ($line in (Get-Content -LiteralPath (Join-Path $Package $other) -Encoding Unicode)) { if ($line -match '^\s*(\$\S+)') { $keys[$matches[1]] = $true } }
                    if ($keys.Count -eq 0) { foreach ($line in (Get-Content -LiteralPath (Join-Path $Package $other) -Encoding UTF8)) { if ($line -match '^\s*(\$\S+)') { $keys[$matches[1]] = $true } } }
                    $missing = @($enKeys.Keys | Where-Object { -not $keys[$_] })
                    if ($missing.Count -gt 0) { $hits.Add("[$($r.id)] $(Split-Path $other -Leaf) lacks $($missing.Count) key(s) english has, e.g. $($missing[0])") }
                }
            }
        }
        'lines-match-build-tree' {
            if (-not $hasDll) { continue }
            if (-not $RepoPath -or -not (Test-Path -LiteralPath $RepoPath)) { $skips.Add("[$($r.id)] repo not resolved"); continue }
            $rv = RepoVersion $RepoPath
            if ($rv -and $Version -and $rv -ne $Version) { $skips.Add("[$($r.id)] repo is at $rv, not $Version - build tree has moved on; only the current release is judged"); continue }
            $b17 = Join-Path $RepoPath 'build\relwithdebinfo-17'; $bse = Join-Path $RepoPath 'build\relwithdebinfo-se-only'
            # A line is BUILT when its tree holds a DLL, not when the folder exists (2026-09-23: Dragon's Eye Minimap's
            # 1.7 tree is configured groundwork that has never compiled; its empty folder read as "builds a 1.7 line").
            $has17 = (Test-Path -LiteralPath $b17) -and [bool](Get-ChildItem -LiteralPath $b17 -Filter '*.dll' -File -ErrorAction SilentlyContinue | Select-Object -First 1)
            $hasSe = (Test-Path -LiteralPath $bse) -and [bool](Get-ChildItem -LiteralPath $bse -Filter '*.dll' -File -ErrorAction SilentlyContinue | Select-Object -First 1)
            if (-not ($has17 -and $hasSe)) { $skips.Add("[$($r.id)] repo has one build line only"); continue }
            $pk17 = @($files | Where-Object { $_ -match '(^|[\\/])Line-17[\\/].*\.dll$' })
            $pkSe = @($files | Where-Object { $_ -match '(^|[\\/])Line-SE[^\\/]*[\\/].*\.dll$' })
            if ($pk17.Count -eq 0) { $hits.Add("[$($r.id)] repo builds a 1.7 line but the package has no Line-17 DLL") }
            if ($pkSe.Count -eq 0) { $hits.Add("[$($r.id)] repo builds an SE line but the package has no Line-SE-AE16 DLL") }
            foreach ($pair in @(@($pk17, $b17, 'Line-17'), @($pkSe, $bse, 'Line-SE-AE16'))) {
                foreach ($f in $pair[0]) {
                    $name = Split-Path $f -Leaf
                    $src = Get-ChildItem -LiteralPath $pair[1] -Filter $name -File -ErrorAction SilentlyContinue | Select-Object -First 1
                    if (-not $src) { $hits.Add("[$($r.id)] $f has no counterpart in $($pair[1])"); continue }
                    if ((Sha (Join-Path $Package $f)) -ne (Sha $src.FullName)) { $hits.Add("[$($r.id)] $f is not the DLL in $($pair[1]) (hash differs)") }
                    $fv = (Get-Item -LiteralPath (Join-Path $Package $f)).VersionInfo.FileVersion
                    if ($Version -and $fv -ne "$Version.0" -and $fv -ne $Version) { $hits.Add("[$($r.id)] $f is stamped $fv, not $Version") }
                }
            }
        }
        'repo-source-require-regex' {
            # A rule about the SOURCE of the mod that produced this package (2026-09-17): when the repo's
            # marker file matches markerPattern (e.g. vcpkg.json naming commonlibsse-ng), some compiled
            # source file must match contentPattern (e.g. the Address Library guard call). Skipped when
            # the repo is not resolved or the marker does not match.
            if (-not $RepoPath -or -not (Test-Path -LiteralPath $RepoPath)) { $skips.Add("[$($r.id)] repo not resolved"); continue }
            $markerFiles = @(Get-ChildItem -LiteralPath $RepoPath -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -match $r.markerFile -and (Get-RepoRelative $_.FullName) -notmatch '[\\/](build\d*|build-release|build-[^\\/]+|\.git|\.claude|vcpkg_installed|extern|external|third-party|lib|cimgui|imgui)[\\/]' })
            $marked = $false
            foreach ($mf in $markerFiles) { $t = Get-Content -LiteralPath $mf.FullName -Raw -ErrorAction SilentlyContinue; if ($t -and [regex]::IsMatch($t, $r.markerPattern)) { $marked = $true; break } }
            if (-not $marked) { $skips.Add("[$($r.id)] repo has no $($r.markerFile) matching $($r.markerPattern)"); continue }
            # the same sourceExtensions override the forbid kind honours (2026-09-23: mo2-plugin-arms-faulthandler read only .cpp/.h)
            $reqExts = if ($r.sourceExtensions) { @($r.sourceExtensions) } else { @('.cpp', '.h', '.hpp') }
            $src = @(Get-ChildItem -LiteralPath $RepoPath -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.Extension -in $reqExts -and (Get-RepoRelative $_.FullName) -notmatch '[\\/](build\d*|build-release|build-[^\\/]+|\.git|\.claude|vcpkg_installed|extern|external|third-party|lib|cimgui)[\\/]' })
            $found = $false
            foreach ($f in $src) { $t = Get-Content -LiteralPath $f.FullName -Raw -ErrorAction SilentlyContinue; if ($t -and [regex]::IsMatch($t, $r.contentPattern)) { $found = $true; break } }
            if (-not $found) { $hits.Add("[$($r.id)] no source file under $RepoPath matches $($r.contentPattern) - $($r.fix)") }
        }
        'repo-source-forbid-regex' {
            # The mirror of require (2026-09-18): when the repo's marker file matches markerPattern, NO compiled
            # source file may match contentPattern. First use: an engine-patch installer that refuses while a
            # setting is off and tells the player to "turn it on and restart" - settings from a co-save arrive
            # after the install point, so such an installer can never attach (Character Progression Control 1.1.8).
            if (-not $RepoPath -or -not (Test-Path -LiteralPath $RepoPath)) { $skips.Add("[$($r.id)] repo not resolved"); continue }
            $markerFiles = @(Get-ChildItem -LiteralPath $RepoPath -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -match $r.markerFile -and (Get-RepoRelative $_.FullName) -notmatch '[\\/](build\d*|build-release|build-[^\\/]+|\.git|\.claude|vcpkg_installed|extern|external|third-party|lib|cimgui|imgui)[\\/]' })
            $marked = $false
            foreach ($mf in $markerFiles) { $t = Get-Content -LiteralPath $mf.FullName -Raw -ErrorAction SilentlyContinue; if ($t -and [regex]::IsMatch($t, $r.markerPattern)) { $marked = $true; break } }
            if (-not $marked) { $skips.Add("[$($r.id)] repo has no $($r.markerFile) matching $($r.markerPattern)"); continue }
            # Compiled sources by default; a rule may name its own extensions instead, so the same
            # kind can police SHIPPED TEXT in the repo (dist\README.txt and the docs beside it) and
            # not only code (2026-09-19).
            $exts = if ($r.sourceExtensions) { @($r.sourceExtensions) } else { @('.cpp', '.h', '.hpp') }
            # A rule may also narrow WHERE it looks, relative to the repo. Without it this kind
            # scans every matching file in the repo, which for a text rule means changelogs and
            # port notes - where a sentence about an UPSTREAM mod's MIT licence, or a record of a
            # relicensing we already did, is correct history and not a defect (2026-09-19).
            $src = @(Get-ChildItem -LiteralPath $RepoPath -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.Extension -in $exts -and (Get-RepoRelative $_.FullName) -notmatch '[\\/](build\d*|build-release|build-[^\\/]+|\.git|\.claude|vcpkg_installed|extern|external|third-party|lib|cimgui|imgui)[\\/]' })
            foreach ($f in $src) {
                $rel = $f.FullName.Substring($RepoPath.Length + 1)
                if ($r.pathPattern -and $rel -notmatch $r.pathPattern) { continue }
                $t = Get-Content -LiteralPath $f.FullName -Raw -ErrorAction SilentlyContinue
                if ($t -and [regex]::IsMatch($t, $r.contentPattern)) { $hits.Add("[$($r.id)] $rel matches $($r.contentPattern) - $($r.fix)") }
            }
        }
        'mo2-install-matches-package' {
            # THE STALE-INSTALL RULE (2026-09-22). Back Pocket For Controller's favourite/unfavourite
            # crash was fixed, built and committed - and then the owner was asked to test, with the
            # PREVIOUS binary still sitting in the MO2 mod folder, because the install step never ran.
            # He hit the identical crash a second time (same faulting offset, +0x1140E) and an evening
            # went on a fix that was already correct. A package is only testable when the copy the
            # game will load IS this package's copy.
            #
            #   instances    MO2 mod folders to look in (e.g. <MO2>\<test instance>\mods)
            #   filePattern  which package files must match, by name (default: the DLL)
            # A mod folder that does not exist is a SKIP: not every package is installed anywhere.
            if (-not $hasDll) { continue }
            $pattern = if ($r.filePattern) { $r.filePattern } else { '\.dll$' }
            $found = $false
            # A package belongs to ONE game (2026-09-28): Apocrypha Menu Framework 1.9.9 (Skyrim, SKSE\Plugins) was judged
            # against the Oblivion Remastered instance's "test Apocrypha Menu Framework" - the OR port, same display name -
            # and failed as "never installed there". An SKSE package is looked for only in a Skyrim instance, an OBSE
            # package only in an Oblivion one.
            $pkgObse = @($files | Where-Object { $_ -match '(^|[\\/])OBSE[\\/]' }).Count -gt 0
            $pkgSkse = @($files | Where-Object { $_ -match '(^|[\\/])SKSE[\\/]' }).Count -gt 0
            # ...and a Witcher 3 package (bin\x64_dx12, no SKSE/OBSE) only in a Witcher 3 instance (2026-10-05: AMF for
            # Witcher 3 1.0.0 was judged against Njordlinger's and Oblivion's "Apocrypha Menu Framework" folders - the
            # Skyrim and OR frameworks, same display name - and failed as "never installed there").
            $pkgWitcher = @($files | Where-Object { $_ -match '(^|[\\/])bin[\\/]x64_dx12[\\/]' }).Count -gt 0
            # ...and a NORSE package (Norse\Binaries\, UE4SS) only in the Norse instance (2026-11-18)
            $pkgNorse = @($files | Where-Object { $_ -match '^Norse[\\/]Binaries[\\/]' }).Count -gt 0
            foreach ($root in @($r.instances)) {
                if (-not (Test-Path -LiteralPath $root)) { continue }
                $rootOblivion = $root -match '(?i)oblivion'
                $rootWitcher = $root -match '(?i)witcher'
                $rootNorse = $root -match '(?i)[\\/]Norse[\\/]'
                if ($rootWitcher -ne $pkgWitcher) { continue }
                if ($rootNorse -ne $pkgNorse) { continue }
                if (($rootOblivion -and $pkgSkse -and -not $pkgObse) -or (-not $rootOblivion -and $pkgObse -and -not $pkgSkse)) { continue }
                # WHICH FOLDER HOLDS THE BUILD UNDER TEST (2026-09-23). Njordlinger's convention: a build in test
                # sits in "test <Display> <X.Y.Z>" (or "test <Display>", "unpublished <Display>"), while a folder
                # named exactly "<Display>" is the PUBLISHED Nexus download and is never overwritten by a test build.
                # The old suffix match judged the published folder, missed "test Dragon's Eye Minimap 1.7.3" (it
                # ends in the version) and matched "Perfected Wheeler - Apocrypha Menu Framework" for AMF.
                $display = ((Split-Path $Package -Leaf) -replace '\s+FOMOD$', '' -replace '\s+\d+\.\d+\.\d+$', '')
                $want = @()
                foreach ($n in @($display, $ModName) | Select-Object -Unique) {
                    $want += @("test $n $Version", "test $n", "unpublished $n")
                }
                # the Norse instance names a mod folder "<Repo> <X.Y.Z>" (NorseTagger 0.1.0), the repo's own name (2026-11-18)
                if ($pkgNorse -and $RepoPath) { $want += @("$(Split-Path $RepoPath -Leaf) $Version") }
                $dirs = @(Get-ChildItem -LiteralPath $root -Directory -ErrorAction SilentlyContinue)
                $candidates = @($dirs | Where-Object { $want -contains $_.Name })
                # the exact "test <Display> <X.Y.Z>" folder is the one under test when it exists (2026-09-28)
                $exactTest = @($candidates | Where-Object { $_.Name -match (' ' + [regex]::Escape($Version) + '$') })
                if ($exactTest.Count -gt 0) { $candidates = $exactTest }
                if ($candidates.Count -eq 0) { $candidates = @($dirs | Where-Object { $_.Name -eq $display -or $_.Name -eq $ModName }) }
                foreach ($dir in $candidates) {
                    $found = $true
                    # A FOMOD package holds each build line under Line-*\ (and shared files under Common\), while an
                    # install is flat and carries ONE line (2026-09-23, Apocrypha Menu Framework 1.9.7): judge each
                    # installed path against every package copy that installs to it; it must equal one of them.
                    # 2026-10-15 (AMF 2.2.1): any other folder the installer's ModuleConfig.xml installs from (AMF's
                    # conditional SMF-Name\) is flattened the same way, or its file reads as "never installed".
                    $fomodSources = @()
                    $mc = Join-Path $Package 'fomod\ModuleConfig.xml'
                    if (Test-Path -LiteralPath $mc) {
                        try { $fomodSources = @(([xml](Get-Content -LiteralPath $mc -Raw)).SelectNodes('//folder') | ForEach-Object { $_.source } | Where-Object { $_ -and $_ -notmatch '[\\/]' }) } catch { $fomodSources = @() }
                    }
                    # 2026-10-20 (Norden UI Black 1.0.4): a FOMOD that installs a file or a NESTED folder to another place
                    # (Extras\RaceMenu Atelier\RaceMenuAtelier.dll -> SKSE\Plugins) read as "never installed" because only
                    # top-level single-name folders were flattened. Every <file>/<folder> of ModuleConfig.xml (required files,
                    # each option's files, conditional installs) is mapped source -> destination; a package file such a
                    # mapping covers is judged at its mapped destination(s), and only for the options actually installed -
                    # an option counts as installed when any file it places exists in the mod folder (install-with-choices.py
                    # infers the player's choices the same way). Files no mapping covers, and packages with no ModuleConfig.xml,
                    # are judged exactly as before.
                    $mapped = @{}      # destination -> @{ Hashes; Owners }
                    $ownerDests = @{}  # owner -> every destination it places (any file type)
                    $covered = @{}
                    if (Test-Path -LiteralPath $mc) {
                        try {
                            $mx = [xml](Get-Content -LiteralPath $mc -Raw)
                            $blocks = @()
                            foreach ($n in @($mx.SelectNodes('//requiredInstallFiles/*'))) { $blocks += [pscustomobject]@{ Owner = 'required'; Node = $n } }
                            $pi = 0
                            foreach ($pl in @($mx.SelectNodes('//plugin'))) { $pi++; foreach ($n in @($pl.SelectNodes('files/*'))) { $blocks += [pscustomobject]@{ Owner = "plugin$pi"; Node = $n } } }
                            $ci = 0
                            foreach ($pt in @($mx.SelectNodes('//conditionalFileInstalls//pattern'))) { $ci++; foreach ($n in @($pt.SelectNodes('files/*'))) { $blocks += [pscustomobject]@{ Owner = "cond$ci"; Node = $n } } }
                            foreach ($b in $blocks) {
                                $src = ([string]$b.Node.source).Trim().TrimEnd('\', '/') -replace '/', '\'
                                if (-not $src) { continue }
                                $dst = ([string]$b.Node.destination).Trim() -replace '/', '\'
                                $isFolder = $b.Node.LocalName -eq 'folder'
                                foreach ($rel in $files) {
                                    $relN = $rel -replace '/', '\'
                                    if ($isFolder) {
                                        if (-not $relN.StartsWith($src + '\', [System.StringComparison]::OrdinalIgnoreCase)) { continue }
                                        $sub = $relN.Substring($src.Length + 1)
                                        $d = if ($dst) { $dst.TrimEnd('\') + '\' + $sub } else { $sub }
                                    } else {
                                        if ($relN -ne $src) { continue }
                                        $leaf = Split-Path $src -Leaf
                                        # a file's destination is its full installed path; none, or a folder (trailing slash, or no
                                        # extension where the source has one), puts it there under its own name
                                        $d = if (-not $dst) { $leaf } elseif ($dst.EndsWith('\') -or ([System.IO.Path]::GetExtension($dst) -eq '' -and [System.IO.Path]::GetExtension($leaf) -ne '')) { $dst.TrimEnd('\') + '\' + $leaf } else { $dst }
                                    }
                                    $covered[$rel] = $true
                                    if (-not $ownerDests.ContainsKey($b.Owner)) { $ownerDests[$b.Owner] = @() }
                                    $ownerDests[$b.Owner] += $d
                                    if ((Split-Path $rel -Leaf) -notmatch $pattern) { continue }
                                    if (-not $mapped.ContainsKey($d)) { $mapped[$d] = @{ Hashes = @(); Owners = @() } }
                                    $mapped[$d].Hashes += (Sha (Join-Path $Package $rel))
                                    $mapped[$d].Owners += $b.Owner
                                }
                            }
                        } catch { $mapped = @{}; $covered = @{}; $ownerDests = @{} }
                    }
                    # Root Builder instances (Oblivion Remastered) hold the game-root files under Root\
                    $installedAt = {
                        param($dirPath, $d)
                        if (Test-Path -LiteralPath (Join-Path $dirPath $d)) { return (Join-Path $dirPath $d) }
                        $rp = Join-Path $dirPath (Join-Path 'Root' $d)
                        if (Test-Path -LiteralPath $rp) { return $rp }
                        return $null
                    }
                    if ($mapped.Count -gt 0) {
                        $installedOwners = @{ required = $true }
                        foreach ($o in $ownerDests.Keys) {
                            foreach ($d in $ownerDests[$o]) { if (& $installedAt $dir.FullName $d) { $installedOwners[$o] = $true; break } }
                        }
                        if ($installedOwners.Count -eq 1 -and -not (@($ownerDests['required']) | Where-Object { $_ -and (& $installedAt $dir.FullName $_) })) {
                            $hits.Add("[$($r.id)] '$($dir.Name)' holds none of the files the package's ModuleConfig.xml installs - the package was never installed there")
                        }
                        foreach ($d in $mapped.Keys) {
                            $installed = & $installedAt $dir.FullName $d
                            if (-not $installed) {
                                if (@($mapped[$d].Owners | Where-Object { $installedOwners.ContainsKey($_) }).Count -gt 0) {
                                    # 2026-10-23 (Norden UI Black 1.1.0): the chosen RaceMenu Atelier option's DLL sat in the test
                                    # folder as SKSE\Plugins\RaceMenuAtelier.dll.mohidden - MO2's own "hide" (the player let another
                                    # mod's copy win), byte-identical to the package's - and read as "never installed". A file that
                                    # ONLY optional options place may be hidden in MO2: its hidden copy is judged by hash instead.
                                    # A file a required block places stays strict - hidden or absent, it fails.
                                    $hidden = & $installedAt $dir.FullName ($d + '.mohidden')
                                    if ($hidden -and ($mapped[$d].Owners -notcontains 'required')) {
                                        if ($mapped[$d].Hashes -notcontains (Sha $hidden)) {
                                            $hits.Add("[$($r.id)] '$($dir.Name)' $d (hidden in MO2 as .mohidden) is NOT this package's file - install the build before it is tested (install-test-build.py)")
                                        }
                                        continue
                                    }
                                    $hits.Add("[$($r.id)] '$($dir.Name)' has no $d - the package was never installed there")
                                }
                                continue
                            }
                            if ($mapped[$d].Hashes -notcontains (Sha $installed)) {
                                $hits.Add("[$($r.id)] '$($dir.Name)' $d is NOT this package's file - install the build before it is tested (install-test-build.py)")
                            }
                        }
                    }
                    $byInstalled = @{}
                    foreach ($rel in $files) {
                        $name = Split-Path $rel -Leaf
                        if ($name -notmatch $pattern) { continue }
                        if ($covered.ContainsKey($rel)) { continue }
                        $flat = $rel -replace '^(Line-[^\\/]+|Common|Languages[\\/][^\\/]+)[\\/]', ''
                        foreach ($src in $fomodSources) { if ($flat -like "$src\*" -or $flat -like "$src/*") { $flat = $flat.Substring($src.Length + 1); break } }
                        if (-not $byInstalled.ContainsKey($flat)) { $byInstalled[$flat] = @() }
                        $byInstalled[$flat] += (Sha (Join-Path $Package $rel))
                    }
                    foreach ($flat in $byInstalled.Keys) {
                        $installed = Join-Path $dir.FullName $flat
                        # Root Builder instances (Oblivion Remastered) hold the game-root files under Root\ (2026-09-26)
                        if (-not (Test-Path -LiteralPath $installed) -and (Test-Path -LiteralPath (Join-Path $dir.FullName (Join-Path 'Root' $flat)))) { $installed = Join-Path $dir.FullName (Join-Path 'Root' $flat) }
                        if (-not (Test-Path -LiteralPath $installed)) {
                            $hits.Add("[$($r.id)] '$($dir.Name)' has no $flat - the package was never installed there")
                            continue
                        }
                        if ($byInstalled[$flat] -notcontains (Sha $installed)) {
                            $hits.Add("[$($r.id)] '$($dir.Name)' $flat is NOT this package's file - install the build before it is tested (install-test-build.py)")
                        }
                    }
                }
            }
            if (-not $found) { $skips.Add("[$($r.id)] no MO2 mod folder named for '$ModName'") }
        }
        'dll-newer-than-sources' {
            if (-not $hasDll) { continue }
            if (-not $RepoPath -or -not (Test-Path -LiteralPath $RepoPath)) { $skips.Add("[$($r.id)] repo not resolved"); continue }
            $rv = RepoVersion $RepoPath
            if ($rv -and $Version -and $rv -ne $Version) { $skips.Add("[$($r.id)] repo is at $rv, not $Version - sources have moved on; only the current release is judged"); continue }
            # -Include is unreliable with -LiteralPath, so the filter is explicit: compiled sources and the build definition only, never docs
            $srcFiles = Get-ChildItem -LiteralPath $RepoPath -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
                ($_.Extension -in '.cpp', '.h', '.hpp', '.rc', '.in' -or $_.Name -eq 'CMakeLists.txt' -or $_.Name -eq 'vcpkg.json') -and
                (Get-RepoRelative $_.FullName) -notmatch '[\\/](build\d*|build-release|build-[^\\/]+|\.git|\.claude|vcpkg_installed|extern|external|third-party|lib)[\\/]' -and
                # the off-game harnesses (top-level tools\*_check.*, never shipped) build no DLL of the package, in every
                # repo, map or no map (2026-10-25: AMF's harness edits made all three of its DLLs look stale)
                (Get-RepoRelative $_.FullName) -notmatch '^[\\/]tools[\\/][^\\/]*_check\.[^\\/]+$' }
            $srcFiles = @($srcFiles)
            if ($srcFiles.Count -eq 0) { $skips.Add("[$($r.id)] no source files found under $RepoPath"); continue }
            # Each DLL against ITS OWN sources (2026-10-25, AMF 2.3.0). A repo that builds more than one DLL may say which
            # sources build which in tools\dll-sources.json: {"dlls": [{"dll": "<file name>", "sources": "<regex over the
            # repo-relative path, '/' separators>"}]}. A DLL named there is judged only against the sources its regex
            # matches; a DLL it does not name, and every DLL of a repo without the file, is judged against every source as
            # before. Why: AMF's SMF name stub (a second, tiny DLL) is not relinked when only the framework's sources change,
            # so it tripped this row - and touching its source to relink it then made the framework's DLL look older.
            $dllMap = @{}
            $mapPath = Join-Path $RepoPath 'tools\dll-sources.json'
            if (Test-Path -LiteralPath $mapPath) {
                $mj = $null
                try { $mj = [System.IO.File]::ReadAllText($mapPath) | ConvertFrom-Json } catch { $mj = $null }
                if ($null -eq $mj -or $null -eq $mj.dlls) { $hits.Add("[$($r.id)] tools\dll-sources.json does not parse or has no 'dlls' list - fix it or remove it"); continue }
                foreach ($e in @($mj.dlls)) {
                    if (-not $e.dll -or -not $e.sources) { $hits.Add("[$($r.id)] tools\dll-sources.json has an entry without 'dll' and 'sources'"); continue }
                    $dllMap[([string]$e.dll).ToLowerInvariant()] = [string]$e.sources
                }
            }
            foreach ($f in ($files | Where-Object { $_ -match '\.dll$' })) {
                $leaf = (Split-Path $f -Leaf).ToLowerInvariant()
                $own = $srcFiles
                $scope = ''
                if ($dllMap.ContainsKey($leaf)) {
                    $rx = $dllMap[$leaf]
                    $own = @($srcFiles | Where-Object { (((Get-RepoRelative $_.FullName).TrimStart('\', '/')) -replace '\\', '/') -match $rx })
                    if ($own.Count -eq 0) { $hits.Add("[$($r.id)] $f - tools\dll-sources.json maps it to '$rx', which matches no source file"); continue }
                    $scope = ' of its own (tools\dll-sources.json)'
                }
                $newest = $own | Sort-Object LastWriteTime -Descending | Select-Object -First 1
                $dt = (Get-Item -LiteralPath (Join-Path $Package $f)).LastWriteTime
                if ($dt -lt $newest.LastWriteTime) { $hits.Add("[$($r.id)] $f ($($dt.ToString('yyyy-MM-dd HH:mm'))) is OLDER than$scope $($newest.FullName.Substring($RepoPath.Length + 1)) ($($newest.LastWriteTime.ToString('yyyy-MM-dd HH:mm'))) - built before the last source change") }
            }
        }
        default { $skips.Add("[$($r.id)] unknown kind '$($r.kind)' - add it to package-gate.ps1") }
    }
}

Write-Output ("package-gate  {0} {1}  ({2} rule(s), {3} file(s))" -f $ModName, $Version, $rules.Count, $files.Count)
Write-Output '  schema: OK'
if ($Previous) { Write-Output "  previous release ....... $(Split-Path $Previous -Leaf)" }
foreach ($s in $skips) { Write-Output "  skip  $s" }
foreach ($d in $defers) { Write-Output "  defer $d" }
if ($hits.Count -eq 0) { Write-Output "  PASS  every rule clear"; exit 0 }
foreach ($h in $hits) { Write-Output "  !!    $h" }
Write-Output ("  FAIL  {0} hit(s). Fix the package, or - if a rule is wrong - fix the rule in gate-rules.json with a dated reason. Never ship past it." -f $hits.Count)
exit 1
