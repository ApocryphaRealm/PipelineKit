<#
.SYNOPSIS
    Assembles one mod's package in "7. current test builds", with its verified .pdb inside it.

.DESCRIPTION
    Packages were assembled by hand until now, which is why almost no package before this
    script shipped a .pdb. Crash Logger (Nexus 59818) reads the PDB sitting beside the DLL and
    turns raw module+offset frames into our own function names and line numbers; without it,
    every one of this project's frames in a user-submitted crash log is an unreadable offset.

    ONE PACKAGE, WITH THE PDB INSIDE IT
    -----------------------------------
    Each run produces one folder, inside the mod's game folder (2026-10-01: named like its distro folder, so two games'
    mods of the same name and version can both exist - Resolve-PackageRoot in distro-names.ps1):

      <Game> - <Mod>/<Display Name> <X.Y.Z>/    SKSE\Plugins\<Target>.{dll,pdb}, the INI, the README.

    The separate "<Display Name> - Debug Symbols <X.Y.Z>" download was RETIRED (design
    decision, 2026-08-31). The .pdb ships in the main archive instead, so every user is
    already running the symbols at the moment they crash rather than being asked to install a
    second mod and reproduce. It also removes the failure this script was built to prevent:
    two halves shipping as separate downloads can drift apart on a user's machine, and
    symbols from another version do not half-work - they attribute frames to the wrong
    functions.

    So this script will not put a PDB in a package until it has PROVEN that the PDB belongs
    to the DLL shipping beside it.

    HOW THE DLL/PDB PAIRING IS VERIFIED
    -----------------------------------
    The strong check is implemented here in full - NOT the same-folder/timestamp fallback:

      * The DLL is parsed as a PE image. Data directory 6 (IMAGE_DIRECTORY_ENTRY_DEBUG) is
        located, its RVA translated to a file offset through the section table, and each
        28-byte IMAGE_DEBUG_DIRECTORY entry walked until one of type 2
        (IMAGE_DEBUG_TYPE_CODEVIEW) is found. That entry's raw data is an 'RSDS' record: a
        16-byte GUID, a 4-byte age, and the NUL-terminated PDB path the linker recorded.
      * The PDB is parsed as an MSF 7.00 container. The superblock gives the block size and
        the block-map address; the stream directory is reassembled from its (non-contiguous)
        blocks; stream 1 - the PDB Info stream - is located and its header read: version,
        signature, age, and its own 16-byte GUID.
      * The two GUIDs are compared byte-for-byte and the two ages numerically. Both must
        match. This is the same identity a debugger or crash logger matches on, so a PASS
        here means the crash logger will accept the pair, and a FAIL means it would have
        rejected it or - worse - attributed frames to the wrong functions.

    LIMITS OF THE CHECK
    -------------------
      * It covers PE32+/PE32 images carrying a CodeView RSDS record, which is what MSVC and
        clang-cl emit. A DLL with no CODEVIEW debug entry (stripped, or linked /DEBUG:NONE)
        is reported as exactly that and fails, rather than being guessed at.
      * It reads the PDB's IDENTITY only. It does not validate that the PDB's contents are
        internally intact, that it holds private symbols rather than public-only, or that its
        recorded source paths still resolve. A corrupt-but-correctly-signed PDB would pass.
      * MSF 2.00 ("Microsoft C/C++ program database 2.00") is not parsed. Nothing in this
        project emits it; it is reported, not silently ignored.
      * The RSDS record's embedded PDB path is shown under -Verbose for information only. It
        is never trusted for LOCATING the PDB, because it is a build-machine absolute path.

    WHAT IT ASSEMBLES
    -----------------
    Packages in this project are not uniform. Most are
        <Display Name> X.Y.Z/{README.txt, SKSE/Plugins/<Target>.{dll,ini}}
    but Wait Your Turn Redux keeps its INI at SKSE/Plugins/WaitYourTurn/Settings.ini and ships
    a LICENSE as well. Rather than impose one layout, this script SEEDS the new package from
    the newest existing package of the same mod, then replaces the DLL. Layout quirks, the
    LICENSE, the README and the INI therefore carry forward on their own - which matters,
    because for most of these mods the INI is authored in the package and does not exist in
    the source repo at all.

    Any .pdb found in the seed is dropped before the fresh one lands: a seeded PDB describes
    the PREVIOUS build, and a mismatched PDB is worse than none.

    The README's "Version X.Y.Z" line is retargeted. The REST of the README is not: a
    changelog section is a human's job, and the script says so in its closing notes.

    With no previous package to seed from, the canonical layout is built instead and the
    script reports loudly which pieces it could not supply.

.PARAMETER Mod
    The source folder under "6. current wip mods" - an exact folder name, a unique fragment of
    one, or a full path. e.g. "AutoDraw-SMF", "autodraw", or "D:\...\AutoDraw-SMF".

.PARAMETER Version
    The version for the new package, X.Y.Z.

.PARAMETER DisplayName
    The package's display name, e.g. "Auto Draw". Auto-detected from the
    existing packages that contain this mod's DLL. Must be given explicitly when a mod has
    more than one package line - Compass Navigation Overhaul and Local Map Upgrade each have
    an "- SMF Settings" and an "- Untarnished UI" line, and the script refuses to guess.

.PARAMETER Target
    Force the plugin target / DLL base name instead of auto-detecting it from the build tree.

.PARAMETER BuildDir
    Force the directory holding <Target>.dll and <Target>.pdb.

.PARAMETER IniFrom
    Optional path to an INI to place in the package, overriding the one carried forward.

.PARAMETER Force
    Overwrite the destination package folder if it already exists.

.PARAMETER NoPrune
    Skip the prune-test-builds.ps1 -Apply call that otherwise runs at the end of packaging to
    hold this mod at rule 7's five-version cap (prune-test-builds.ps1's own header asks to be
    called exactly here).

.PARAMETER AcknowledgeMissingPdb
    Build the package with no .pdb inside it. Deliberately awkward to type: the standing rule
    is that every build ships its symbols, so this exists only for a toolchain that genuinely
    cannot produce a PDB, and it stamps that fact into the console output.

.EXAMPLE
    .\package-mod.ps1 -Mod AutoDraw-SMF -Version 1.0.5

.EXAMPLE
    .\package-mod.ps1 -Mod LocalMapUpgrade -Version 1.2.6 -DisplayName "Local Map Upgrade"

.EXAMPLE
    .\package-mod.ps1 -Mod CompassNavigationOverhaul -Version 1.1.1 -WhatIf
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)][string]$Mod,
    [ValidatePattern('^\d+\.\d+\.\d+$')][string]$Version,   # omit it: the version gate supplies the ISSUED number (2026-09-12)
    [string]$DisplayName,
    [string]$Target,
    [string]$BuildDir,
    [string]$IniFrom,
    [string]$Root = $env:PIPELINE_ROOT,
    [switch]$Force,
    [switch]$NoPrune,
    [switch]$AcknowledgeMissingPdb
)

# ---- roles, looked up ONCE here (STEPS 5.6), through the resolver OF THIS TREE (scripts\release\ -> ..\..\resolvers) ----
# Never the absolute <ROOT> path and never the script folder variable for a sibling: a moved or copied tree answers inside itself.
$ResolverPy = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\resolvers\resolve.py'))
function Find-Role([string]$role) {
    $p = @(& py -3 $ResolverPy find $role)
    if ($LASTEXITCODE -ne 0 -or $p.Count -eq 0 -or -not "$($p[0])".Trim()) { Write-Output "package-mod: cannot resolve role '$role' ($($p -join ' '))"; exit 1 }
    return "$($p[0])".Trim()
}
$RoleRegistry = Find-Role 'version-registry'
$RoleVersionGate = Find-Role 'version-gate'
$RoleChangelog = Find-Role 'changelog'
$RolePruner = Find-Role 'prune-test-builds'
$RolePackageGate = Find-Role 'package-gate'
$RolePipelineLog = Find-Role 'pipeline-log'

$ErrorActionPreference = 'Stop'
if (-not $Root) { $_kitRoot = $PSScriptRoot; while ($_kitRoot -and (Split-Path $_kitRoot -Leaf) -ne '.MD') { $_kitRoot = Split-Path $_kitRoot -Parent }; if ($_kitRoot) { $_kitRoot = Split-Path $_kitRoot -Parent }; $Root = $_kitRoot }   # kit: <ROOT> is the folder above the .MD this script sits under, unless PIPELINE_ROOT says otherwise

# The number is never typed (the owner, 2026-09-12). With -Version omitted, the version gate hands
# over the number it ISSUED for this mod (bump wrote it into the repo and recorded it untested).
# A typed -Version still has to clear the gate below; it is not a bypass.
if (-not $Version) {
    $issued = & $RoleVersionGate -Action current -Mod $Mod 2>&1
    if ($LASTEXITCODE -ne 0) { Write-Output ($issued | Out-String); Write-Output "FAIL  no issued version for $Mod - run version-gate.ps1 -Action bump first."; exit 1 }
    $Version = ($issued | Select-Object -Last 1).ToString().Trim()
    Write-Output "package-mod: version $Version taken from the version gate (issued, untested)"
}

$wipRoot    = Join-Path $Root '6. current wip mods'
$buildsRoot = Join-Path $Root '7. current test builds'
# A FOMOD release's package is "<Mod> X.Y.Z FOMOD" (repack-fomod, build-fomod.py): it counts as a package of <Mod> X.Y.Z
# too (2026-10-25 - the pattern skipped it, so Dragon's Eye Minimap 1.7.6 and Unbind Vanilla Controls 1.2.0, whose last
# packages were FOMOD folders, could not be packaged and were assembled by hand). The name comes out without " FOMOD".
$VERSION_RE = '^(?<name>.+?)\s+(?<ver>\d+\.\d+\.\d+)(?<fomod>\s+FOMOD)?$'

# Build-tree noise. Dependency sources vendored into a repo also contain .dll/.pdb pairs
# (CommonLibSSE-NG's openvr_api, the SKSE64 submodule, SureOfStealing's contrib staging copy),
# and picking one of those as "the plugin" would package the wrong binary entirely.
$EXCLUDE_RE = '\\(vcpkg[^\\]*|_deps|extern|deps|CMakeFiles|packages|contrib|\.git)\\'

function Write-Ok   { param([string]$m) Write-Output "  [ok]   $m" }
function Write-Warn2 { param([string]$m) Write-Output "  [warn] $m" }
function Fail       { param([string]$m) Write-Output ''; Write-Output "FAILED: $m"; exit 1 }

########################################################################################
## PE / PDB identity
########################################################################################

function Get-DllCodeViewInfo {
    <#
        Returns [pscustomobject] @{ Guid = <byte[16]>; Age = <uint32>; PdbPath = <string> }
        for the DLL's IMAGE_DEBUG_TYPE_CODEVIEW 'RSDS' record, or $null when the image
        carries none at all.
    #>
    param([Parameter(Mandatory = $true)][string]$Path)

    $fs = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
    try {
        $br = New-Object System.IO.BinaryReader($fs)

        if ($br.ReadUInt16() -ne 0x5A4D) { throw "not a PE image (no 'MZ' signature)" }
        $fs.Position = 0x3C
        $peOffset = $br.ReadUInt32()
        $fs.Position = $peOffset
        if ($br.ReadUInt32() -ne 0x00004550) { throw "not a PE image (no 'PE\0\0' signature)" }

        # IMAGE_FILE_HEADER, 20 bytes, read in declaration order.
        $null           = $br.ReadUInt16()   # Machine
        $numSections    = $br.ReadUInt16()
        $null           = $br.ReadUInt32()   # TimeDateStamp
        $null           = $br.ReadUInt32()   # PointerToSymbolTable
        $null           = $br.ReadUInt32()   # NumberOfSymbols
        $sizeOfOptional = $br.ReadUInt16()
        $null           = $br.ReadUInt16()   # Characteristics

        $optOffset = $fs.Position
        $magic = $br.ReadUInt16()
        if     ($magic -eq 0x20B) { $ddOffset = $optOffset + 112 }   # PE32+
        elseif ($magic -eq 0x10B) { $ddOffset = $optOffset + 96  }   # PE32
        else   { throw ("unrecognised optional header magic 0x{0:X4}" -f $magic) }

        # NumberOfRvaAndSizes is the field immediately preceding the data directories.
        $fs.Position = $ddOffset - 4
        if ($br.ReadUInt32() -lt 7) { return $null }   # no debug data directory at all

        $fs.Position = $ddOffset + (6 * 8)             # IMAGE_DIRECTORY_ENTRY_DEBUG
        $debugRva  = $br.ReadUInt32()
        $debugSize = $br.ReadUInt32()
        if ($debugRva -eq 0 -or $debugSize -eq 0) { return $null }

        # Section table, for the one RVA -> file offset translation this needs.
        $sections = New-Object System.Collections.ArrayList
        $fs.Position = $optOffset + $sizeOfOptional
        for ($i = 0; $i -lt $numSections; $i++) {
            $null  = $br.ReadBytes(8)                  # Name
            $vsize = $br.ReadUInt32()
            $vaddr = $br.ReadUInt32()
            $rsize = $br.ReadUInt32()
            $raddr = $br.ReadUInt32()
            $null  = $br.ReadBytes(16)                 # relocs / line numbers / characteristics
            [void]$sections.Add([pscustomobject]@{ VSize = $vsize; VAddr = $vaddr; RSize = $rsize; RAddr = $raddr })
        }

        $debugOffset = $null
        foreach ($s in $sections) {
            $span = [Math]::Max($s.VSize, $s.RSize)
            if ($debugRva -ge $s.VAddr -and $debugRva -lt ($s.VAddr + $span)) {
                $debugOffset = [int64]$s.RAddr + ([int64]$debugRva - [int64]$s.VAddr)
                break
            }
        }
        if ($null -eq $debugOffset) { throw ("debug directory RVA 0x{0:X} falls outside every section" -f $debugRva) }

        $entryCount = [int]([Math]::Floor($debugSize / 28))
        for ($i = 0; $i -lt $entryCount; $i++) {
            $fs.Position = $debugOffset + ($i * 28)
            $null       = $br.ReadUInt32()   # Characteristics
            $null       = $br.ReadUInt32()   # TimeDateStamp
            $null       = $br.ReadUInt16()   # MajorVersion
            $null       = $br.ReadUInt16()   # MinorVersion
            $type       = $br.ReadUInt32()
            $sizeOfData = $br.ReadUInt32()
            $null       = $br.ReadUInt32()   # AddressOfRawData
            $ptrRawData = $br.ReadUInt32()

            if ($type -ne 2) { continue }               # IMAGE_DEBUG_TYPE_CODEVIEW
            if ($ptrRawData -eq 0 -or $sizeOfData -lt 24) { continue }

            $fs.Position = $ptrRawData
            if ($br.ReadUInt32() -ne 0x53445352) { continue }   # 'RSDS', little-endian
            $guid = $br.ReadBytes(16)
            $age  = $br.ReadUInt32()
            $nameBytes = $br.ReadBytes([int]$sizeOfData - 24)
            $pdbPath = [System.Text.Encoding]::UTF8.GetString($nameBytes).TrimEnd([char]0)

            return [pscustomobject]@{ Guid = $guid; Age = $age; PdbPath = $pdbPath }
        }
        return $null
    }
    finally { $fs.Dispose() }
}

function Get-PdbSignature {
    <#
        Returns [pscustomobject] @{ Guid = <byte[16]>; Age = <uint32> } read from an MSF 7.00
        PDB's stream 1, the PDB Info stream. Throws with a specific reason otherwise.
    #>
    param([Parameter(Mandatory = $true)][string]$Path)

    $MSF7 = "Microsoft C/C++ MSF 7.00`r`n" + [char]0x1A + 'DS' + [char]0 + [char]0 + [char]0

    $fs = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
    try {
        $br = New-Object System.IO.BinaryReader($fs)
        $magic = [System.Text.Encoding]::ASCII.GetString($br.ReadBytes(32))
        if ($magic -ne $MSF7) {
            if ($magic -like 'Microsoft C/C++ program database 2.00*') {
                throw 'PDB is the obsolete MSF 2.00 format, which this script does not parse'
            }
            throw 'not an MSF 7.00 PDB (unexpected superblock magic)'
        }

        $blockSize    = $br.ReadUInt32()   # 0x20
        $null         = $br.ReadUInt32()   # 0x24 FreeBlockMapBlock
        $null         = $br.ReadUInt32()   # 0x28 NumBlocks
        $numDirBytes  = $br.ReadUInt32()   # 0x2C
        $null         = $br.ReadUInt32()   # 0x30 Unknown
        $blockMapAddr = $br.ReadUInt32()   # 0x34
        if ($blockSize -eq 0) { throw 'PDB superblock reports a zero block size' }

        $numDirBlocks = [int][Math]::Ceiling($numDirBytes / [double]$blockSize)
        if ($numDirBlocks -lt 1) { throw 'PDB stream directory is empty' }

        $fs.Position = [int64]$blockMapAddr * $blockSize
        $dirBlocks = New-Object System.Collections.ArrayList
        for ($i = 0; $i -lt $numDirBlocks; $i++) { [void]$dirBlocks.Add($br.ReadUInt32()) }

        # Reassemble the stream directory from its (non-contiguous) blocks.
        $dir = New-Object byte[] ($numDirBlocks * [int]$blockSize)
        for ($i = 0; $i -lt $numDirBlocks; $i++) {
            $fs.Position = [int64]$dirBlocks[$i] * $blockSize
            $chunk = $br.ReadBytes([int]$blockSize)
            [Array]::Copy($chunk, 0, $dir, $i * [int]$blockSize, $chunk.Length)
        }

        $numStreams = [BitConverter]::ToUInt32($dir, 0)
        if ($numStreams -lt 2) { throw "PDB stream directory holds only $numStreams stream(s); there is no PDB Info stream" }

        # Stream 0's block count, so we can step past it to stream 1's first block. 0xFFFFFFFF
        # marks a nil stream, which occupies no blocks.
        $stream0Size = [BitConverter]::ToUInt32($dir, 4)
        if ($stream0Size -eq [uint32]::MaxValue) { $stream0Size = 0 }
        $stream0Blocks = [int][Math]::Ceiling($stream0Size / [double]$blockSize)

        $blockArrayStart = 4 + (4 * [int]$numStreams)
        $stream1BlockAt  = $blockArrayStart + (4 * $stream0Blocks)
        if (($stream1BlockAt + 4) -gt $dir.Length) { throw 'PDB stream directory is truncated' }
        $stream1FirstBlock = [BitConverter]::ToUInt32($dir, $stream1BlockAt)

        # The PDB Info header is 28 bytes, so it always fits inside stream 1's first block.
        $fs.Position = [int64]$stream1FirstBlock * $blockSize
        $null = $br.ReadUInt32()   # Version
        $null = $br.ReadUInt32()   # Signature (build timestamp)
        $age  = $br.ReadUInt32()
        $guid = $br.ReadBytes(16)

        return [pscustomobject]@{ Guid = $guid; Age = $age }
    }
    finally { $fs.Dispose() }
}

function Format-CvGuid {
    param([byte[]]$Bytes)
    if ($null -eq $Bytes -or $Bytes.Length -ne 16) { return '<none>' }
    return (New-Object System.Guid (, $Bytes)).ToString().ToUpperInvariant()
}

function Test-PdbPairing {
    <#
        The gate. Returns a result object rather than throwing on a plain mismatch, because
        the caller wants to print the specifics before exiting.
    #>
    param([string]$DllPath, [string]$PdbPath)

    $cv = $null
    try { $cv = Get-DllCodeViewInfo -Path $DllPath }
    catch { return [pscustomobject]@{ Ok = $false; Reason = "could not read the DLL's debug directory - $($_.Exception.Message)" } }

    if ($null -eq $cv) {
        return [pscustomobject]@{
            Ok     = $false
            Reason = 'the DLL carries no CodeView (RSDS) debug record at all - it was linked without /DEBUG, or its debug directory was stripped. No PDB can be proven to belong to it.'
        }
    }

    $pdb = $null
    try { $pdb = Get-PdbSignature -Path $PdbPath }
    catch { return [pscustomobject]@{ Ok = $false; Reason = "could not read the PDB's signature - $($_.Exception.Message)" } }

    $guidMatch = -not (Compare-Object $cv.Guid $pdb.Guid -SyncWindow 0)
    $ageMatch  = ($cv.Age -eq $pdb.Age)

    $res = [pscustomobject]@{
        Ok         = ($guidMatch -and $ageMatch)
        Reason     = ''
        DllGuid    = (Format-CvGuid $cv.Guid)
        DllAge     = $cv.Age
        PdbGuid    = (Format-CvGuid $pdb.Guid)
        PdbAge     = $pdb.Age
        LinkedPath = $cv.PdbPath
    }
    if (-not $guidMatch) {
        $res.Reason = "GUID mismatch - this DLL was built against a DIFFERENT PDB. The DLL asks for $($res.DllGuid); this PDB is $($res.PdbGuid)."
    }
    elseif (-not $ageMatch) {
        $res.Reason = "GUID matches but the age differs - the DLL asks for age $($cv.Age), this PDB is age $($pdb.Age). The PDB was relinked after this DLL, so its symbols would be wrong."
    }
    return $res
}

########################################################################################
## Discovery
########################################################################################

if (-not (Test-Path -LiteralPath $wipRoot))    { Fail "'6. current wip mods' not found at $wipRoot" }
if (-not (Test-Path -LiteralPath $buildsRoot)) { Fail "'7. current test builds' not found at $buildsRoot" }

Write-Output ''
Write-Output "package-mod  ->  $Mod  $Version"
Write-Output ('-' * 78)
Write-Output 'Resolving source'

if (Test-Path -LiteralPath $Mod -PathType Container) {
    $repo = (Resolve-Path -LiteralPath $Mod).Path
}
else {
    # The ledger KEY and the FOLDER are not the same string and are not required to be: the gate
    # refuses to change an identity once a version has been issued against it, so a renamed repo
    # keeps its old key. The registry's 'repo' field is what says where the source now lives, and
    # asking it first is the difference between packaging the right mod and failing outright.
    # (2026-09-16: thirteen repos lost their Apocrypha prefix and every one of them broke here.)
    $regPath = $RoleRegistry
    if (Test-Path -LiteralPath $regPath) {
        $reg = Get-Content -LiteralPath $regPath -Raw | ConvertFrom-Json
        $entry = $reg.PSObject.Properties | Where-Object {
            $_.Name -ieq $Mod -or $_.Value.repo -ieq $Mod -or $_.Value.displayName -ieq $Mod
        } | Select-Object -First 1
        if ($entry -and $entry.Value.repo) {
            $cand = Join-Path $wipRoot $entry.Value.repo
            if (Test-Path -LiteralPath $cand -PathType Container) {
                $repo = (Resolve-Path -LiteralPath $cand).Path
                Write-Output ("      registry: '$Mod' -> " + $entry.Value.repo)
            }
        }
    }
}
if (-not $repo) {
    $exact = @(Get-ChildItem -LiteralPath $wipRoot -Directory -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name -eq $Mod })
    if ($exact.Count -eq 1) { $repo = $exact[0].FullName }
    else {
        $key = ($Mod -replace '[^A-Za-z0-9]', '')
        $fuzzy = @(Get-ChildItem -LiteralPath $wipRoot -Directory -Recurse -Depth 1 -Force -ErrorAction SilentlyContinue |
                   Where-Object { ($_.Name -replace '[^A-Za-z0-9]', '') -like "*$key*" })
        if ($fuzzy.Count -eq 1) { $repo = $fuzzy[0].FullName }
        elseif ($fuzzy.Count -gt 1) {
            Fail ("'$Mod' matches more than one source folder: " + (($fuzzy | ForEach-Object { $_.Name }) -join ', ') + '. Pass an exact name or a full path.')
        }
        else { Fail "No source folder under '6. current wip mods' matches '$Mod'." }
    }
}
Write-Ok "source repo: $repo"

# A NORSE (UE4SS) MOD IS ASSEMBLED BY ROLE package-norse (2026-11-18). This script seeds from the previous package and
# drops one <Target>.dll into pluginDir; a Norse mod's layout is a rule (dlls\main.dll + enabled.txt, ue4ss\NorsePacks,
# data-only mods, the licence in the mod folder), computed from the repo by package-norse.py, which runs the same gates
# (version gate, changelog, pdb pairing, prune, package-gate). The registry's game decides, never the name.
try {
    $regNorse = Get-Content -LiteralPath $RoleRegistry -Raw | ConvertFrom-Json
    $norseProp = @($regNorse.PSObject.Properties | Where-Object { $_.Value.repo -ieq (Split-Path $repo -Leaf) -and "$($_.Value.game)" -ieq 'Norse' }) | Select-Object -First 1
} catch { $norseProp = $null }
if ($norseProp) {
    $norseArgs = @('run', 'package-norse', '--mod', $norseProp.Name, '--version', $Version)
    if ($Force) { $norseArgs += '--force' }
    if ($NoPrune) { $norseArgs += '--no-prune' }
    if ($WhatIfPreference) { $norseArgs += '--dry-run' }
    Write-Ok "game: Norse - handing over to role package-norse"
    & py -3 $ResolverPy @norseArgs
    exit $LASTEXITCODE
}

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
$LockToken = [guid]::NewGuid().ToString('N')
# each acquirer is its own holder (2026-10-25): the token goes to the tools this script starts (AGENT_LOCK_TOKENS),
# so their own lock calls refresh this lock instead of being refused
$env:AGENT_LOCK_TOKENS = (@($env:AGENT_LOCK_TOKENS, $LockToken) | Where-Object { $_ }) -join ';'
$LockRepo = Split-Path $repo -Leaf
Invoke-AgentLock @('acquire', '--repo', $LockRepo, '--purpose', "package-mod $Mod $Version", '--token', $LockToken)
if ($script:AgentLockRc -eq 3) { Fail "agent-lock: another session holds repo:$LockRepo - not packaging" }
try {

# THE GAME, from the registry entry of this repo (2026-10-01): the package goes into "7. current test builds\<Game> - <Mod>\",
# the folder named like the mod's distro folder, so the Skyrim and the Oblivion Remastered "HUD Position Manager 1.0.1"
# can both exist. Seeds and the prune are looked for in that folder only.
. (Find-Role 'distro-names')
$regEntry = $null
$regKey = $null   # the registry KEY of the same entry - the pipeline event's subject.key (event log step 3, 2026-10-12)
try {
    $regGame = Get-Content -LiteralPath $RoleRegistry -Raw | ConvertFrom-Json
    $regProp = @($regGame.PSObject.Properties | Where-Object { $_.Value.repo -ieq (Split-Path $repo -Leaf) }) | Select-Object -First 1
    if ($regProp) { $regEntry = $regProp.Value; $regKey = $regProp.Name }
} catch { }
if (-not $regEntry) { Fail "no version-registry entry has repo '$(Split-Path $repo -Leaf)', so the game (and the package folder) cannot be told. Register the mod first." }
$game = Get-ModGame -Entry $regEntry -ProjectRoot $Root
Write-Ok "game: $game"

# THE OPEN-REQUEST GATE (2026-10-27). A helper repackaged AMF 2.3.1 with a different fix while 2.3.1 was mid-test: the
# package was replaced, the ledger hash of the open number rebound, and one SE regression ran on the wrong DLL. A number
# with a test request still open (queued, or in a combined-run batch with no result) is never packaged again - the
# change goes on a branch until that number is posted. Asked of role combined-run ('open-for'); -Force does not bypass
# it. A broken tool only warns (fail open, like the lock): a missing queue must not stop every package.
$openNames = @($regEntry.displayName, $regKey, $regEntry.repo, $DisplayName) + @($regEntry.aliases) | Where-Object { $_ }
try {
    $crPath = "$(@(& py -3 $ResolverPy find combined-run 2>$null)[0])".Trim()
    if ($crPath -and $crPath -notlike 'MISSING*' -and (Test-Path -LiteralPath $crPath)) {
        $crArgs = @('open-for', '--version', $Version)
        foreach ($n in $openNames) { $crArgs += @('--mod', "$n") }
        $global:LASTEXITCODE = 0
        $openOut = @(& py -3 $crPath @crArgs 2>&1 | ForEach-Object { "$_" })
        $openRc = $LASTEXITCODE
        if ($openRc -eq 3) { $openOut | ForEach-Object { Write-Output "        $_" }; Fail ("{0} {1} has an open test request - not packaging it again. The change goes on a branch until {1} is posted." -f $Mod, $Version) }
        elseif ($openRc -ne 0) { Write-Warn2 ("the open-request check failed (exit {0}): {1} - continuing" -f $openRc, ($openOut -join ' ')) }
        else { Write-Ok "no open test request for $Mod $Version" }
    } else { Write-Warn2 'role combined-run not found - the open-request check was skipped' }
} catch { Write-Warn2 "the open-request check failed: $($_.Exception.Message) - continuing" }

# The plugin binary: the newest .dll in the tree that has a same-named .pdb beside it, once
# vendored dependency trees are excluded.
if ($BuildDir) {
    if (-not (Test-Path -LiteralPath $BuildDir -PathType Container)) { Fail "-BuildDir '$BuildDir' does not exist." }
    $searchRoot = (Resolve-Path -LiteralPath $BuildDir).Path
}
else { $searchRoot = $repo }

$dllCandidates = @(Get-ChildItem -LiteralPath $searchRoot -Filter '*.dll' -Recurse -File -Force -ErrorAction SilentlyContinue |
                   Where-Object { $_.FullName -notmatch $EXCLUDE_RE })
if ($Target) { $dllCandidates = @($dllCandidates | Where-Object { $_.BaseName -eq $Target }) }
if ($dllCandidates.Count -eq 0) {
    $forWhat = if ($Target) { " for target '$Target'" } else { '' }
    Fail "No built plugin DLL found under '$searchRoot'$forWhat. Build the mod first, or pass -BuildDir / -Target."
}

$withPdb = @($dllCandidates | Where-Object { Test-Path -LiteralPath (Join-Path $_.DirectoryName ($_.BaseName + '.pdb')) })
if ($withPdb.Count -gt 0) { $dll = @($withPdb       | Sort-Object LastWriteTime -Descending)[0] }
else                     { $dll = @($dllCandidates  | Sort-Object LastWriteTime -Descending)[0] }

$targetName = $dll.BaseName
$pdbPath    = Join-Path $dll.DirectoryName ($targetName + '.pdb')

Write-Ok "target: $targetName"
Write-Ok ('dll:    {0}' -f $dll.FullName)
Write-Ok ('        {0:N0} bytes, built {1:yyyy-MM-dd HH:mm}' -f $dll.Length, $dll.LastWriteTime)

# VERSION GATE (2026-09-12, the owner: one tool, tooling only, a gate that fails). Every version
# rule - the ledger issued this number, it is LAST WORKING + 1, every repo location carries it, the
# DLL's own FileVersion carries it, no version literal escaped the tool - is checked by
# version-gate.ps1 and nowhere else. Its exit code is the decision; -Force does not bypass it.
# (Before this, the FileVersion guard lived here: a failed build had left the PREVIOUS binary in the
# tree and this script packaged it under the NEW number - DEM 1.5.9, 2026-08-29.)
$gate = $RoleVersionGate
& $gate -Action gate -Mod $Mod -Version $Version -Stage package -Dll $dll.FullName | ForEach-Object { Write-Output "        $_" }
if ($LASTEXITCODE -ne 0) { Fail ("version-gate.ps1 refused {0} {1} (exit {2}). Nothing is packaged under a number the gate did not clear." -f $Mod, $Version, $LASTEXITCODE) }
if ($dllCandidates.Count -gt 1) {
    Write-Warn2 "$($dllCandidates.Count) candidate DLLs in this tree; chose the newest one with a PDB beside it."
    foreach ($c in $dllCandidates) { if ($c.FullName -ne $dll.FullName) { Write-Output "         not chosen: $($c.FullName)" } }
    Write-Output '         Pass -Target / -BuildDir if that is the wrong one.'
}

########################################################################################
## The PDB gate
########################################################################################

Write-Output 'Verifying debug symbols'
$havePdb = $false

if (-not (Test-Path -LiteralPath $pdbPath)) {
    Write-Output ''
    Write-Output "  No PDB beside the DLL. Expected: $pdbPath"
    Write-Output '  Every build in this project ships its .pdb so Crash Logger (Nexus 59818) can resolve'
    Write-Output '  our frames to function names and line numbers. Rebuild with debug info:'
    Write-Output '    CMake   - the relwithdebinfo-* preset (or release-msvc, which passes /DEBUG:FULL)'
    Write-Output '    MSBuild - DebugInformationFormat=ProgramDatabase + GenerateDebugInformation=true'
    Write-Output '    xmake   - the releasedbg mode'
    if (-not $AcknowledgeMissingPdb) { Fail 'no PDB, so the package cannot ship its symbols.' }
    Write-Warn2 'The package will be built WITHOUT its .pdb, because -AcknowledgeMissingPdb was passed.'
    Write-Warn2 'Crash logs from this build will show raw offsets, not function names.'
}
else {
    $pdbFile = Get-Item -LiteralPath $pdbPath
    Write-Ok ('pdb:    {0}' -f $pdbFile.FullName)
    Write-Ok ('        {0:N1} MB, built {1:yyyy-MM-dd HH:mm}' -f ($pdbFile.Length / 1MB), $pdbFile.LastWriteTime)

    $pair = Test-PdbPairing -DllPath $dll.FullName -PdbPath $pdbPath
    if (-not $pair.Ok) {
        Write-Output ''
        Write-Output '  PDB/DLL PAIRING REJECTED'
        Write-Output "    $($pair.Reason)"
        Write-Output '  A mismatched PDB is worse than none: the crash logger will either refuse it or'
        Write-Output '  attribute frames to the wrong functions. Rebuild so that the DLL and the PDB'
        Write-Output '  come out of the same link.'
        Fail 'the PDB does not belong to this DLL.'
    }
    Write-Ok "pairing verified: CodeView GUID $($pair.DllGuid), age $($pair.DllAge) - the PDB matches exactly"
    if ($pair.LinkedPath) { Write-Verbose "linker recorded PDB path: $($pair.LinkedPath)" }
    $havePdb = $true
}

########################################################################################
## Display name and seed package
########################################################################################

Write-Output 'Resolving package'

$existing = New-Object System.Collections.ArrayList
# this game's packages only, from their "<Game> - <Mod>" folders (Find-Packages, distro-names.ps1)
foreach ($d in @(Find-Packages -Root $buildsRoot -Game $game -Folders -ProjectRoot $Root)) {
    if ($d.Name -notmatch $VERSION_RE) { continue }
    $n = $Matches['name']; $v = [version]$Matches['ver']; $isF = [bool]$Matches['fomod']
    $hasDll = Get-ChildItem -LiteralPath $d.FullName -Filter ($targetName + '.dll') -Recurse -File -Force -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $hasDll) { continue }
    [void]$existing.Add([pscustomobject]@{ Name = $n; Version = $v; Path = $d.FullName; FolderName = $d.Name; IsFomod = $isF })
}

if (-not $DisplayName) {
    $lines = @($existing | Select-Object -ExpandProperty Name -Unique)
    if ($lines.Count -eq 1) {
        $DisplayName = $lines[0]
        Write-Ok "display name (inferred from existing packages): $DisplayName"
    }
    elseif ($lines.Count -gt 1) {
        Fail ("'$targetName' ships under more than one package line: " + ($lines -join '  |  ') + '. Pass -DisplayName to say which one this build is.')
    }
    else {
        Fail "No existing package contains $targetName.dll, so the display name cannot be inferred. Pass -DisplayName."
    }
}
else { Write-Ok "display name: $DisplayName" }

# The seed is the previous package whose README and layout this one carries forward. It must
# EXCLUDE the version being packaged: with -Force the destination is deleted just below, and if
# the seed were that same folder the copy would then fail with "cannot find path" - which is
# exactly what happened repackaging 1.5.7 over itself on 2026-08-27. Excluding it also makes
# -Force genuinely idempotent instead of working only on the first run.
# The seed must also be the SAME GAME's package (2026-09-30): the Oblivion Remastered "HUD Position Manager" 1.0.0 was
# seeded from the Skyrim mod of the same name (1.0.1) and came out with that mod's FOMOD (Common\, Line-17\, fomod\)
# beside its own OblivionRemastered\ tree. A mod whose registry entry carries an Oblivion Remastered pluginDir / game
# seeds only from a package holding an OblivionRemastered\ tree, and any other mod only from one without.
$seedWantsOR = $false
try {
    $regSeed = Get-Content -LiteralPath $RoleRegistry -Raw | ConvertFrom-Json
    foreach ($prop in $regSeed.PSObject.Properties) {
        if ($prop.Value.repo -ieq (Split-Path $repo -Leaf) -and (($prop.Value.game -eq 'OblivionRemastered') -or ("$($prop.Value.pluginDir)" -like 'OblivionRemastered*'))) { $seedWantsOR = $true }
    }
} catch { }
$seed = @($existing |
    Where-Object { $_.Name -eq $DisplayName -and $_.Version -ne $Version } |
    Where-Object { (Test-Path -LiteralPath (Join-Path $_.Path 'OblivionRemastered')) -eq $seedWantsOR } |
    Sort-Object @{ Expression = 'Version'; Descending = $true }, @{ Expression = 'IsFomod'; Descending = $true } |
    Select-Object -First 1)   # of a flat and a FOMOD folder of one version, the FOMOD is the release that shipped
$seed = if ($seed.Count -gt 0) { $seed[0] } else { $null }

$destName = "$DisplayName $Version"
$pkgRoot  = Resolve-PackageRoot -Root $buildsRoot -ModName $DisplayName -Game $game -ProjectRoot $Root
$dest     = Join-Path $pkgRoot $destName
Write-Ok ("package folder: {0}\{1}" -f (Split-Path $pkgRoot -Leaf), $destName)

if (Test-Path -LiteralPath $dest) {
    if (-not $Force) { Fail "'$destName' already exists. Pass -Force to overwrite it." }
    Write-Warn2 "'$destName' exists and will be overwritten (-Force)."
}
if ($seed -and $seed.Version -ge [version]$Version) {
    Write-Warn2 "the newest existing package is $($seed.Version), which is not older than the requested $Version. Check the version number (rule 6: the patch component rolls the minor at 9)."
}

########################################################################################
## Assemble
########################################################################################

if (-not $PSCmdlet.ShouldProcess($dest, 'assemble package')) {
    Write-Output ''
    Write-Output 'WhatIf - nothing written. Would have assembled:'
    Write-Output "  $destName\"
    Write-Output ("    seeded from     : {0}" -f $(if ($seed) { $seed.FolderName } else { '<no previous package - canonical layout>' }))
    Write-Output "    SKSE\Plugins\$targetName.dll"
    if ($havePdb) {
        Write-Output ('    SKSE\Plugins\{0}.pdb  ({1:N1} MB)' -f $targetName, ((Get-Item -LiteralPath $pdbPath).Length / 1MB))
    }
    else { Write-Output '    <no .pdb - crash logs from this build would not resolve>' }
    exit 0
}

# Rule 61: a version with no recorded change is a version nobody can later tell the contents of -
# which is precisely how a stale 1.5.6 binary kept a version number whose fixes it did not contain.
# Refuse here, where writing the entry is cheap, rather than discovering the gap months later.
$changelogScript = $RoleChangelog
if (Test-Path -LiteralPath $changelogScript) {
    & $changelogScript -Action check -Mod $Mod -Version $Version | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Fail ("CHANGELOG.md has no entry for $Version (rule 61). Add one first:`n" +
              "    changelog.ps1 -Action add -Mod $Mod -Version $Version -Type Fixed -Entry '...'")
    }
    Write-Ok "changelog: $Version is described in CHANGELOG.md"
}

Write-Output 'Assembling'
$notes = New-Object System.Collections.ArrayList

# a package of the same name being rebuilt goes to the Recycle Bin, never Remove-Item (rule 50, 2026-10-11)
if (Test-Path -LiteralPath $dest) { Add-Type -AssemblyName Microsoft.VisualBasic; [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory($dest, 'OnlyErrorDialogs', 'SendToRecycleBin') }
if (-not (Test-Path -LiteralPath $pkgRoot)) { New-Item -ItemType Directory -Path $pkgRoot | Out-Null; Write-Ok "created $(Split-Path $pkgRoot -Leaf)\" }

if ($seed) {
    # Copy-Item -Recurse onto a NON-existent destination reproduces the tree under that name,
    # which is what we want. Creating $dest first would nest the seed inside it instead.
    Copy-Item -LiteralPath $seed.Path -Destination $dest -Recurse -Force
    Write-Ok "seeded from $($seed.FolderName)"
    # The seed's own binaries are stale by definition - drop them before the new one lands,
    # and drop the seed's .pdb with them: it describes the PREVIOUS build, and the fresh,
    # verified one is copied in below.
    # NOTE: -Include is silently IGNORED alongside -LiteralPath, so it matches nothing and
    # every file comes back. Filter in the pipeline instead; the earlier -Include form here
    # emptied the whole seeded package.
    Get-ChildItem -LiteralPath $dest -Recurse -File -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Extension -in '.dll', '.pdb' } |
        Remove-Item -Force -ErrorAction SilentlyContinue   # in-assembly: the seed's copies inside the package being built
    # THE INSTALLER'S VERSION IS THIS PACKAGE'S (2026-11-07). The seed's fomod\info.xml carries the PREVIOUS number
    # (QuickLoot Container Merge 1.1.0 and Unbind Vanilla Controls 1.5.0 shipped it). The repo's own fomod\info.xml,
    # stamped by version-gate, wins; without one, the seeded file's <Version> is set to this package's.
    # Gate row fomod-info-version-is-the-package-version refuses a package where they still differ.
    $seedInfo = Join-Path $dest 'fomod\info.xml'
    $repoInfo = Join-Path $repo 'fomod\info.xml'
    if (Test-Path -LiteralPath $repoInfo) {
        if (-not (Test-Path -LiteralPath (Join-Path $dest 'fomod'))) { New-Item -ItemType Directory -Path (Join-Path $dest 'fomod') -Force | Out-Null }
        Copy-Item -LiteralPath $repoInfo -Destination $seedInfo -Force
        Write-Ok "fomod\info.xml from the repo"
    }
    elseif (Test-Path -LiteralPath $seedInfo) {
        $infoText = [System.IO.File]::ReadAllText($seedInfo)
        $newInfo = [regex]::Replace($infoText, '(<Version[^>]*>)\s*[^<]*?\s*(</Version>)', ('${1}' + $Version + '${2}'))
        if ($newInfo -ne $infoText) {
            [System.IO.File]::WriteAllText($seedInfo, $newInfo, (New-Object System.Text.UTF8Encoding($false)))
            Write-Ok "fomod\info.xml <Version> set to $Version"
        }
    }
}
else {
    New-Item -ItemType Directory -Path $dest -Force | Out-Null
    [void]$notes.Add('No previous package existed, so only the canonical layout was created. README.txt was NOT written - add one by hand, with the version at the top (rule 8).')
    [void]$notes.Add("No INI was carried forward. If this mod ships one, add SKSE\Plugins\$targetName.ini.")
}

# THE PLUGIN FOLDER IS THE GAME'S (2026-09-26). Skyrim's is SKSE\Plugins; an Oblivion Remastered mod ships game-root
# relative, OblivionRemastered\Binaries\Win64\OBSE\Plugins. The registry entry says which (pluginDir); Skyrim's is the default.
$pluginRel = 'SKSE\Plugins'
try {
    $regAll = Get-Content -LiteralPath $RoleRegistry -Raw | ConvertFrom-Json
    foreach ($prop in $regAll.PSObject.Properties) {
        if ($prop.Value.repo -ieq (Split-Path $repo -Leaf) -and $prop.Value.pluginDir) { $pluginRel = $prop.Value.pluginDir }
    }
} catch { }
$pluginDir = Join-Path $dest $pluginRel
if (-not (Test-Path -LiteralPath $pluginDir)) { New-Item -ItemType Directory -Path $pluginDir -Force | Out-Null }

Copy-Item -LiteralPath $dll.FullName -Destination (Join-Path $pluginDir ($targetName + '.dll')) -Force
Write-Ok "$destName\$pluginRel\$targetName.dll"
# The .pdb ships IN the package (design decision 2026-08-30) and, since the separate symbols
# download was retired on 2026-08-31, this is the only place it ships. Crash Logger resolves symbol
# names from a sibling .pdb, so every user's crash log names our functions with nothing extra installed.
if ($havePdb) {
    # Re-verify against the DLL AS IT NOW SITS IN THE PACKAGE rather than against the build tree:
    # what has to be proven is that the exact bytes being shipped are the ones this PDB describes.
    $shippedDll = Join-Path $pluginDir ($targetName + '.dll')
    $finalPair  = Test-PdbPairing -DllPath $shippedDll -PdbPath $pdbPath
    if (-not $finalPair.Ok) {
        Write-Output ''
        Write-Output '  PDB REJECTED'
        Write-Output "    $($finalPair.Reason)"
        Fail 'the PDB does not match the DLL that was just packaged.'
    }
    Copy-Item -LiteralPath $pdbPath -Destination (Join-Path $pluginDir ($targetName + '.pdb')) -Force
    Write-Ok ('{0}\{3}\{1}.pdb  ({2:N1} MB, for Crash Logger)' -f $destName, $targetName, ((Get-Item -LiteralPath $pdbPath).Length / 1MB), $pluginRel)
}

# ---------------------------------------------------------------------------------------------
# TWO BUILD LINES, TWO FOLDERS (2026-09-19). A mod whose repo builds both `relwithdebinfo-17` (the
# Skyrim 1.7 / CommonLibSSE-NG 7.x line) and `relwithdebinfo-se-only` (SE 1.5.97 / AE 1.6.1170)
# ships BOTH, in Line-17\ and Line-SE-AE16\, and the FOMOD picks one. Until now this script wrote a
# single flat SKSE\Plugins\ from whichever DLL happened to be newest, which silently dropped one
# line and left the FOMOD pointing at folders that were not there - it happened twice to Item
# Explorer 1.1.1 in one evening, and `both-build-lines-match-the-build-tree` in gate-rules.json is
# the rule that caught it. This is the fix on the producing side.
$lineDirs = @(
    @{ Folder = 'Line-17';       Build = (Join-Path $repo 'build\relwithdebinfo-17') },
    @{ Folder = 'Line-SE-AE16';  Build = (Join-Path $repo 'build\relwithdebinfo-se-only') }
)
$haveBothLines = $true
foreach ($ld in $lineDirs) { if (-not (Test-Path -LiteralPath $ld.Build)) { $haveBothLines = $false } }
# -BuildDir names the ONE line to ship (2026-09-23: Dragon's Eye Minimap 1.7.3 - its 1.7 line is groundwork that does
# not build yet, and the refusal below told the caller to pass -BuildDir, which this branch then ignored).
if ($BuildDir) { $haveBothLines = $false }

if ($haveBothLines) {
    Write-Output ''
    Write-Output 'Two build lines'
    foreach ($ld in $lineDirs) {
        $lineDll = Join-Path $ld.Build ($targetName + '.dll')
        $linePdb = Join-Path $ld.Build ($targetName + '.pdb')
        if (-not (Test-Path -LiteralPath $lineDll)) {
            Fail ("$($ld.Folder): the repo has $($ld.Build) but no $targetName.dll in it. Build that line, or pass -BuildDir for a single-line package.")
        }
        $lineOut = Join-Path $dest (Join-Path $ld.Folder 'SKSE\Plugins')
        if (-not (Test-Path -LiteralPath $lineOut)) { New-Item -ItemType Directory -Path $lineOut -Force | Out-Null }
        Copy-Item -LiteralPath $lineDll -Destination (Join-Path $lineOut ($targetName + '.dll')) -Force

        # Each line's FileVersion is checked here: a line that failed to rebuild leaves the previous
        # binary in its tree, and shipping it under the new number is the defect the version gate
        # exists to stop - it only ever saw the ONE DLL this script chose.
        $lineFv = (Get-Item -LiteralPath (Join-Path $lineOut ($targetName + '.dll'))).VersionInfo.FileVersion
        if ($lineFv -ne "$Version.0" -and $lineFv -ne $Version) {
            Fail ("$($ld.Folder): $targetName.dll is stamped $lineFv, not $Version - that line was not rebuilt.")
        }

        if (Test-Path -LiteralPath $linePdb) {
            $linePair = Test-PdbPairing -DllPath (Join-Path $lineOut ($targetName + '.dll')) -PdbPath $linePdb
            if (-not $linePair.Ok) { Fail ("$($ld.Folder): the PDB does not match that line's DLL - $($linePair.Reason)") }
            Copy-Item -LiteralPath $linePdb -Destination (Join-Path $lineOut ($targetName + '.pdb')) -Force
            Write-Ok ('{0}\{1}\SKSE\Plugins\{2}.dll + .pdb  (FileVersion {3}, pairing verified)' -f $destName, $ld.Folder, $targetName, $lineFv)
        }
        else {
            [void]$notes.Add("$($ld.Folder) has no $targetName.pdb - crash logs from that line will not resolve to function names.")
            Write-Ok ('{0}\{1}\SKSE\Plugins\{2}.dll  (FileVersion {3}, NO pdb)' -f $destName, $ld.Folder, $targetName, $lineFv)
        }
    }

    # The flat copy written above belongs to a one-line package. Leaving it beside the two line
    # folders is worse than useless: the FOMOD never installs it, and it is the stale one.
    Remove-Item -LiteralPath (Join-Path $pluginDir ($targetName + '.dll')) -Force -ErrorAction SilentlyContinue   # in-assembly
    Remove-Item -LiteralPath (Join-Path $pluginDir ($targetName + '.pdb')) -Force -ErrorAction SilentlyContinue   # in-assembly
    if (@(Get-ChildItem -LiteralPath $pluginDir -Force -ErrorAction SilentlyContinue).Count -eq 0) {
        Remove-Item -LiteralPath $pluginDir -Recurse -Force -ErrorAction SilentlyContinue   # in-assembly: empty after the move
        $pluginParent = Split-Path $pluginDir -Parent
        if ($pluginParent -ne $dest -and (Test-Path -LiteralPath $pluginParent) -and @(Get-ChildItem -LiteralPath $pluginParent -Force -ErrorAction SilentlyContinue).Count -eq 0) {
            Remove-Item -LiteralPath $pluginParent -Force -ErrorAction SilentlyContinue   # in-assembly: the empty SKSE\ left above it
        }
    }
    Write-Ok 'the flat SKSE\Plugins copy was removed - the FOMOD installs one of the two lines above'
}

# ---------------------------------------------------------------------------------------------
# THE SHIPPED TRANSLATIONS ARE THE REPO'S, NOT THE SEED'S (2026-09-19). Same failure as the INI
# below, and worse, because a FOMOD ships each language twice - once under Languages\<Lang>\ and
# once under Languages\All\ - plus English under Common\. Seeding from the previous package
# carried the PREVIOUS release's strings into all of them, so a version that added text to a page
# would ship with that text missing in every language (rule 66) while the repo's files were right.
# Matched by FILE NAME wherever it sits in the package, so this works whatever shape the FOMOD is.
# ... from ANY Translations folder under dist (2026-09-26): the Oblivion Remastered framework keeps its eleven files
# beside the plugin (OBSE\Plugins\<Mod>\Translations), not under Interface\Translations.
$repoTranslations = Join-Path $repo 'dist'
if (Test-Path -LiteralPath $repoTranslations) {
    $fresh = @{}
    foreach ($f in @(Get-ChildItem -LiteralPath $repoTranslations -Recurse -File -Force -ErrorAction SilentlyContinue | Where-Object { $_.Extension -eq '.txt' -and $_.Directory.Name -eq 'Translations' })) {
        $fresh[$f.Name] = $f.FullName
    }
    $refreshed = 0
    foreach ($inPackage in @(Get-ChildItem -LiteralPath $dest -Filter '*.txt' -Recurse -File -Force -ErrorAction SilentlyContinue)) {
        if ($fresh.ContainsKey($inPackage.Name)) {
            Copy-Item -LiteralPath $fresh[$inPackage.Name] -Destination $inPackage.FullName -Force
            $refreshed++
        }
    }
    if ($refreshed -gt 0) { Write-Ok "$refreshed translation file(s) refreshed from the repo's dist\Interface\Translations" }
}

# ---------------------------------------------------------------------------------------------
# EVERYTHING THE REPO'S dist\ HOLDS SHIPS (2026-09-19). Seeding from the previous release carries
# forward the file CLASSES that release had, so a version that adds a NEW kind of file - Loading
# Menu Overhaul Model Sync 1.0.3 adding Interface\loadingmenu.swf when it absorbed that mod - packaged
# without it and would have been installed and tested with the feature simply absent. The translations
# and the INI above have their own, more careful rules; everything else in dist\ is copied to the
# same relative path unless a file of that name is already in the package (a FOMOD moves files about,
# and those shapes are deliberate).
$repoDist = Join-Path $repo 'dist'
if (Test-Path -LiteralPath $repoDist) {
    # Names of the files a FOMOD keeps OUTSIDE Common\ (its option folders: Line-17\, Line-SE-AE16\, ...). 2026-11-12
    # (Simple Dodge 1.1.0): the skip used every name in the package, so the new magicbehavior\#sdge$97.txt was dropped
    # because Common\...\1hm_behavior\#sdge$97.txt - another file in Common\ itself - had the same name; the magic graph's
    # selectors then named a node the package did not carry. A file moved into an option folder is still skipped.
    $inPackageByName = @{}
    $commonPrefix = (Join-Path $dest 'Common').TrimEnd('\') + '\'
    foreach ($f in @(Get-ChildItem -LiteralPath $dest -Recurse -File -Force -ErrorAction SilentlyContinue)) {
        if ($f.FullName.StartsWith($commonPrefix, [System.StringComparison]::OrdinalIgnoreCase)) { continue }
        $inPackageByName[$f.Name.ToLowerInvariant()] = $true
    }
    $shipped = 0
    # A FOMOD package installs only the folders its ModuleConfig names; its root is never installed. When the package
    # has fomod\ and Common\ (the folder every option installs), a new dist file lands under Common\ (2026-10-13:
    # Simple Loadout System for Controller 1.0.3 was seeded from 1.0.1, which predates its Interface\Translations, and
    # the eleven files landed at the package root where the installer never reaches them - gate row
    # fomod-delivers-every-file-of-previous caught it).
    $distRoot = $dest
    if ((Test-Path -LiteralPath (Join-Path $dest 'fomod\ModuleConfig.xml')) -and (Test-Path -LiteralPath (Join-Path $dest 'Common'))) {
        $distRoot = Join-Path $dest 'Common'
    }
    foreach ($f in @(Get-ChildItem -LiteralPath $repoDist -Recurse -File -Force -ErrorAction SilentlyContinue)) {
        $rel = $f.FullName.Substring($repoDist.Length + 1)
        $target = Join-Path $distRoot $rel
        # 2026-11-09 (Longship 1.0.0): a seeded file at the SAME path as its dist\ source is the previous release's copy -
        # the new plugin went unshipped and the gate's shipped-plugin-is-the-repos row caught it. It is refreshed from dist\.
        if (Test-Path -LiteralPath $target) {
            if ((Get-FileHash -LiteralPath $target).Hash -ne (Get-FileHash -LiteralPath $f.FullName).Hash) {
                Copy-Item -LiteralPath $f.FullName -Destination $target -Force
                Write-Ok "refreshed from the repo's dist: $rel"
            }
            continue
        }
        # The by-name skip is for FOMOD packages only (they move files about on purpose). 2026-11-11 (Simple Dodge
        # 1.1.0): a plain package lost its OAR unarmed clips - dist\...\OpenAnimationReplacer\...\Unarmed\dodgeleft.hkx
        # was skipped because the armed dodgeleft.hkx (same NAME, other folder) was already in the package.
        if ($distRoot -ne $dest -and $inPackageByName.ContainsKey($f.Name.ToLowerInvariant())) { continue }
        $dir = Split-Path $target -Parent
        if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        Copy-Item -LiteralPath $f.FullName -Destination $target -Force
        Write-Ok "shipped from the repo's dist: $rel"
        $shipped++
    }
}

# ---------------------------------------------------------------------------------------------
# THE REPO'S OWN INSTALLER SHIPS (2026-11-12, Simple Dodge 1.2.0). A repo may keep its FOMOD installer in fomod\
# (ModuleConfig.xml) and the files of its install options in fomod-options\<Option>\ - each option folder sits at the
# package root beside Common\, as the installer's <folder source="<Option>"> names it. Until now only fomod\info.xml
# came from the repo, so the package shipped the PREVIOUS release's installer: Simple Dodge 1.2.0 would have gone out
# without its "Step distance" step and without the Step-Shorter folder. Done after the dist\ copy so an option file
# that shares a name with a dist file never hides it from the by-name rule above. Gate row repo-fomod-installer-ships.
$repoModuleConfig = Join-Path $repo 'fomod\ModuleConfig.xml'
if (Test-Path -LiteralPath $repoModuleConfig) {
    $pkgFomod = Join-Path $dest 'fomod'
    if (-not (Test-Path -LiteralPath $pkgFomod)) { New-Item -ItemType Directory -Path $pkgFomod -Force | Out-Null }
    Copy-Item -LiteralPath $repoModuleConfig -Destination (Join-Path $pkgFomod 'ModuleConfig.xml') -Force
    Write-Ok "fomod\ModuleConfig.xml from the repo"
}
$repoFomodOptions = Join-Path $repo 'fomod-options'
if (Test-Path -LiteralPath $repoFomodOptions) {
    foreach ($opt in @(Get-ChildItem -LiteralPath $repoFomodOptions -Directory -Force)) {
        $optDest = Join-Path $dest $opt.Name
        # the option folder IS the repo's: a seeded copy is replaced whole, so a file the repo dropped does not linger
        if (Test-Path -LiteralPath $optDest) { Remove-Item -LiteralPath $optDest -Recurse -Force }   # in-assembly: the package being built
        Copy-Item -LiteralPath $opt.FullName -Destination $optDest -Recurse -Force
        $n = @(Get-ChildItem -LiteralPath $optDest -Recurse -File -Force).Count
        Write-Ok "installer option $($opt.Name)\ from the repo's fomod-options ($n files)"
    }
}

# ---------------------------------------------------------------------------------------------
# A REPO THAT SHIPS FROM Data\ IS REFRESHED FROM Data\ (2026-09-20). The dist\ rules above cover the
# repos that keep their shipped files there; Perfected Wheeler keeps its INIs, its settings-page
# descriptors and its eleven translation files under Data\ instead, so it had NO source of truth as
# far as the packager was concerned and every one of them came from the previous release. 1.3.5
# changed four default bindings, a default toggle and two pieces of wording, and the package carried
# none of it. Matched by RELATIVE PATH under Data\, which is the path the game uses, so a file lands
# exactly where the mod expects it.
$repoData = Join-Path $repo 'Data'
if ((Test-Path -LiteralPath $repoData) -and -not (Test-Path -LiteralPath (Join-Path $repo 'dist'))) {
    $refreshedData = 0
    $addedData = 0
    foreach ($f in @(Get-ChildItem -LiteralPath $repoData -Recurse -File -Force -ErrorAction SilentlyContinue)) {
        $rel = $f.FullName.Substring($repoData.Length + 1)
        $target = Join-Path $dest $rel
        if (Test-Path -LiteralPath $target) {
            if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash) {
                Copy-Item -LiteralPath $f.FullName -Destination $target -Force
                $refreshedData++
            }
        } else {
            $dir = Split-Path $target -Parent
            if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
            Copy-Item -LiteralPath $f.FullName -Destination $target -Force
            $addedData++
        }
    }
    if ($refreshedData -gt 0 -or $addedData -gt 0) {
        Write-Ok "$refreshedData file(s) refreshed and $addedData added from the repo's Data\ tree"
    }
}

# ---------------------------------------------------------------------------------------------
# THE SHIPPED INI IS THE REPO'S, NOT THE SEED'S (2026-09-19). Compiled defaults and the shipped INI
# have to agree (rule 16), and the repo's dist\ copy is the one kept in step with the source. The
# seed's INI is the PREVIOUS release's, so carrying it forward quietly ships last version's
# defaults - which is exactly what happened when Item Explorer's preview pane got new defaults.
if (-not $IniFrom) {
    # Looked for ANYWHERE under dist\, by name: repos differ on where they keep it - most use
    # dist\SKSE\Plugins\, Apocrypha Menu Framework keeps it at dist\<Target>.ini - and looking in one
    # place only meant AMF shipped a seeded INI two versions stale, missing whole sections (2026-09-19).
    $repoIni = Join-Path $repo ('dist\SKSE\Plugins\' + $targetName + '.ini')
    if (-not (Test-Path -LiteralPath $repoIni)) {
        $distDirForIni = Join-Path $repo 'dist'
        if (Test-Path -LiteralPath $distDirForIni) {
            # The DLL may carry a load-order prefix the INI does not: Apocrypha Menu Framework builds
            # !ApocryphaMenuFramework.dll beside ApocryphaMenuFramework.ini. Both spellings are tried.
            foreach ($iniName in @(($targetName + '.ini'), (($targetName -replace '^[!_]+', '') + '.ini'))) {
                $anyIni = @(Get-ChildItem -LiteralPath $distDirForIni -Filter $iniName -Recurse -File -Force -ErrorAction SilentlyContinue) | Select-Object -First 1
                if ($anyIni) { $repoIni = $anyIni.FullName; break }
            }
        }
    }
    if (Test-Path -LiteralPath $repoIni) {
        $iniInPackage = @(Get-ChildItem -LiteralPath $dest -Filter '*.ini' -Recurse -File -Force -ErrorAction SilentlyContinue) | Select-Object -First 1
        if ($iniInPackage) { $IniFrom = $repoIni }
    }
}

if ($IniFrom) {
    if (-not (Test-Path -LiteralPath $IniFrom)) { Fail "-IniFrom '$IniFrom' does not exist." }
    # The package INI with the SAME NAME, never "the first *.ini": Dragon's Eye Minimap 1.7.3 carries a second INI
    # (DragonsEyeMinimap-TimeWidget.ini), which sorted first and was overwritten with the main INI's text while
    # the stale main INI shipped untouched (2026-09-23; gate rule shipped-ini-is-the-repos caught it).
    $iniInPackage = Get-ChildItem -LiteralPath $dest -Filter (Split-Path $IniFrom -Leaf) -Recurse -File -Force -ErrorAction SilentlyContinue | Select-Object -First 1
    $iniDest = if ($iniInPackage) { $iniInPackage.FullName } else { Join-Path $pluginDir ($targetName + '.ini') }
    Copy-Item -LiteralPath $IniFrom -Destination $iniDest -Force
    Write-Ok "ini replaced from -IniFrom: $($iniDest.Substring($dest.Length + 1))"
}
else {
    $carried = @(Get-ChildItem -LiteralPath $dest -Filter '*.ini' -Recurse -File -Force -ErrorAction SilentlyContinue)
    foreach ($i in $carried) { Write-Ok ('ini carried forward: ' + $i.FullName.Substring($dest.Length + 1)) }
    if ($carried.Count -eq 0 -and $seed) {
        [void]$notes.Add('The seed package had no INI, so this one has none either. Confirm that is correct.')
    }
}

# THE SHIPPED README IS THE REPO'S, WHEN THE REPO KEEPS ONE (2026-09-19). Same failure as the INI and
# the translations above, and the most dangerous of the three: the seeded README carries the PREVIOUS
# release's text, and Apocrypha Menu Framework's still called the mod "MIT-licensed" six days after the
# GPL relicence - beside a shipped LICENSE file that says GPL-3.0. That exact contradiction is what
# Nexus took Lock Interaction Overhaul down for. The repo's dist\README.txt is the one kept in step
# with the mod, so it wins; the version line is retargeted afterwards as before.
$repoReadme = Join-Path $repo 'dist\README.txt'
if (Test-Path -LiteralPath $repoReadme) {
    $inPackage = @(Get-ChildItem -LiteralPath $dest -Filter 'README.txt' -Recurse -File -Force -ErrorAction SilentlyContinue) | Select-Object -First 1
    $target = if ($inPackage) { $inPackage.FullName } else { Join-Path $dest 'README.txt' }
    Copy-Item -LiteralPath $repoReadme -Destination $target -Force
    Write-Ok "README.txt taken from the repo's dist\README.txt"
}

# EVERY CHANGELOG.md IN THE PACKAGE IS THE REPO'S (2026-09-24). repack-fomod.ps1 has done this since
# 2026-09-23; this packager still carried the seed's copy forward, so Local Map Upgrade 1.3.2 packaged
# with 1.3.1's changelog on top (gate rule shipped-changelog-is-the-repos caught it).
$repoLog = Join-Path $repo 'CHANGELOG.md'
if (Test-Path -LiteralPath $repoLog) {
    $logs = @(Get-ChildItem -LiteralPath $dest -Recurse -File -Filter 'CHANGELOG.md' -ErrorAction SilentlyContinue)
    foreach ($c in $logs) { Copy-Item -LiteralPath $repoLog -Destination $c.FullName -Force }
    if ($logs.Count -gt 0) { Write-Ok "$($logs.Count) CHANGELOG.md cop(ies) taken from the repo" }
}

# README: retarget the version line only. The body is a human's job.
# Looked for ANYWHERE in the package, not only at its root: a FOMOD puts the shared files under
# Common\, so this found nothing and silently skipped the retarget for every FOMOD-shaped package -
# which then failed the gate's readme-carries-the-version rule (Item Explorer, 2026-09-19).
$readme = Join-Path $dest 'README.txt'
if (-not (Test-Path -LiteralPath $readme)) {
    $found = @(Get-ChildItem -LiteralPath $dest -Filter 'README.txt' -Recurse -File -Force -ErrorAction SilentlyContinue) | Select-Object -First 1
    if ($found) { $readme = $found.FullName }
}
if (Test-Path -LiteralPath $readme) {
    $lines = @(Get-Content -LiteralPath $readme)
    $hit = $false
    for ($i = 0; $i -lt [Math]::Min($lines.Count, 12); $i++) {
        if ($lines[$i] -match '^\s*Version\s+\d+\.\d+\.\d+\s*$') {
            $lines[$i] = "Version $Version"
            $hit = $true
            break
        }
    }
    # A README whose first line is "<Display Name> X.Y.Z" rather than "Version X.Y.Z" was left
    # untouched, so the package shipped the PREVIOUS version's number at the top and the gate's
    # readme-carries-the-version rule failed every time (Item Explorer, 2026-09-19). Both headings
    # are accepted now; only the number is rewritten, never the wording around it.
    if (-not $hit) {
        for ($i = 0; $i -lt [Math]::Min($lines.Count, 12); $i++) {
            if ($lines[$i] -match ('^\s*' + [regex]::Escape($DisplayName) + '\s+\d+\.\d+\.\d+\s*$')) {
                $lines[$i] = "$DisplayName $Version"
                $hit = $true
                break
            }
        }
    }
    if ($hit) {
        Set-Content -LiteralPath $readme -Value $lines -Encoding UTF8
        Write-Ok "README.txt version line set to $Version"
        if ($seed) {
            [void]$notes.Add("README.txt carried forward from $($seed.FolderName) with only its version line changed - its body still describes the PREVIOUS version. Update the description/changelog before this build is finalized. Write its 'WHAT CHANGED' section in the standing changelog template (11. Nexus distro\_CHANGELOG-TEMPLATE.txt, author 2026-09-02): a bare 'Version X.Y.Z' line, one plain verb-first sentence per change, no dates, no headings, no design reasoning - the same voice already used for the distro changelog.txt, so the shipped README and the Nexus page read as one text.")
        }
    }
    else {
        [void]$notes.Add('README.txt has no "Version X.Y.Z" line in its first 12 lines, so nothing was retargeted. Check it by hand.')
    }
}
elseif ($seed) {
    [void]$notes.Add('The seed package had no README.txt. Rule 8 wants one, with the version at the top.')
}

########################################################################################
## Report
########################################################################################

$total = (Get-ChildItem -LiteralPath $dest -Recurse -File -Force | Measure-Object -Property Length -Sum).Sum
Write-Output ''
Write-Output "Packaged: $destName"
Write-Output ('  {0}' -f $dest)
Write-Output ('  {0:N1} MB on disk' -f ($total / 1MB))

if (-not $havePdb) {
    Write-Output ''
    Write-Output '  NO .pdb IN THIS PACKAGE - crash logs from this build will not resolve to function names.'
}

if ($notes.Count -gt 0) {
    Write-Output ''
    Write-Output 'Still to do by hand:'
    foreach ($n in $notes) { Write-Output "  - $n" }
}

if (-not $NoPrune) {
    $pruner = $RolePruner
    if (Test-Path -LiteralPath $pruner) {
        Write-Output ''
        Write-Output 'Enforcing the five-version cap (rule 7/36)'
        & $pruner -Root $Root -ModName $DisplayName -Game $game -Apply
    }
    else { Write-Warn2 'prune-test-builds.ps1 not found beside this script; the five-version cap was NOT enforced.' }
}

# ---------------------------------------------------------------------------------------------
# THE PACKAGE GATE RUNS HERE, NOT ONLY AT FINALIZE (2026-09-19). `gate-rules.json` already held
# `both-build-lines-match-the-build-tree`, and it is exactly the rule that catches this script
# writing a flat SKSE\Plugins where a two-build-line mod needs Line-17 and Line-SE-AE16 - but the
# only caller was pre-finalize-check.ps1, so the defect shipped into a test build twice in one
# evening (Item Explorer 1.1.1, both times repaired by hand). A rule nothing runs at the moment the
# mistake is made is a diary entry; running it here is what makes it a gate.
#
# Distro and page rules cannot pass for a build that has not been finalized yet, so their hits are
# reported rather than fatal; anything else fails this script.
$gate = $RolePackageGate
if (Test-Path -LiteralPath $gate) {
    Write-Output ''
    Write-Output 'Package gate (gate-rules.json)'
    # the repo is passed (2026-09-29): by display name alone the gate found the Skyrim framework's repo for the Oblivion one
    $gateOut = & $gate -Package $dest -RepoPath $repo 2>&1
    $gateOut | ForEach-Object { Write-Output ("  " + $_) }
    $fatal = @($gateOut | Where-Object { $_ -match '^\s*!!' -and $_ -notmatch 'distro-|page-' })
    if ($fatal.Count -gt 0) {
        Write-Output ''
        Write-Output "FAIL  the package gate found $($fatal.Count) problem(s) that are not distro/page text. The package is NOT fit to install or test."
        exit 1
    }
}
else { Write-Warn2 'package-gate.ps1 not found beside this script; the package was NOT gated.' }

# ---------------------------------------------------------------------------------------------
# Pipeline event log. The write lives HERE, in the script that performs the transition, so the
# stage cannot forget to record - a log an agent is trusted to remember to append to is twelve
# documents with extra syntax. It is never allowed to fail this script.
$plog = $RolePipelineLog
if (Test-Path -LiteralPath $plog) {
    try { & $plog -Action record -Stage 7 -Event 'packaged' -Mod $DisplayName -Key $regKey -Version $Version -Evidence ("{0}, pdb {1}" -f $targetName, $(if ($havePdb) { 'included and paired' } else { 'ABSENT' })) -By 'package-mod.ps1' | Out-Null } catch { }
}

exit 0
} finally {
    Invoke-AgentLock @('release', '--repo', $LockRepo, '--token', $LockToken)
}
