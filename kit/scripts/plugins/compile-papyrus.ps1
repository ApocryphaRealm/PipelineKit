<#
compile-papyrus.ps1 - compile a Papyrus script with the Creation Kit's own compiler (rule 4: the
toolchain is discovered, never hard-coded; rule 5: the vanilla headers are cached in a persistent
folder, never a session scratchpad).

    compile-papyrus.ps1 -Source <file.psc> -OutDir <dir> [-Optimize] [-Import <dir>,<dir>]

-Import adds source folders searched after the script's own folder and BEFORE the vanilla headers
(SKSE's Scripts\Source, a dependency's .psc folder), so a script calling SKSE or another mod's
natives compiles. Added 2026-10-25 for Custom - Always Winter.

Finds PapyrusCompiler.exe under any Skyrim SE install that ships it, extracts Data\Scripts.zip
(the vanilla script sources) once into %USERPROFILE%\tools\papyrus-headers, and compiles the
script against them. Exits non-zero on any compiler error.
#>
param(
    [Parameter(Mandatory = $true)][string]$Source,
    [Parameter(Mandatory = $true)][string]$OutDir,
    [switch]$Optimize,
    [string[]]$Import = @()
)
$ErrorActionPreference = 'Stop'

function Find-Compiler {
    $roots = @('C:\MO2\Skyrim Special Edition', 'C:\MO2\vanilla skyrim game')
    foreach ($lib in @('C:\SteamLibrary', 'D:\SteamLibrary', 'C:\Program Files (x86)\Steam', 'D:\Steam')) {
        $roots += (Join-Path $lib 'steamapps\common\Skyrim Special Edition')
    }
    try {
        $steam = (Get-ItemProperty 'HKCU:\Software\Valve\Steam' -ErrorAction Stop).SteamPath
        if ($steam) { $roots += (Join-Path $steam 'steamapps\common\Skyrim Special Edition') }
    } catch {}
    foreach ($r in $roots) {
        $c = Join-Path $r 'Papyrus Compiler\PapyrusCompiler.exe'
        $z = Join-Path $r 'Data\Scripts.zip'
        if ((Test-Path -LiteralPath $c) -and (Test-Path -LiteralPath $z)) { return @{ Exe = $c; Zip = $z } }
    }
    throw 'PapyrusCompiler.exe with Data\Scripts.zip not found under any known Skyrim SE install'
}

$tc = Find-Compiler
$headers = Join-Path $env:USERPROFILE 'tools\papyrus-headers'
$headerSrc = Join-Path $headers 'Source\Scripts'
if (-not (Test-Path -LiteralPath (Join-Path $headerSrc 'ObjectReference.psc'))) {
    Write-Host "extracting vanilla script sources from $($tc.Zip) -> $headers"
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    New-Item -ItemType Directory -Force -Path $headers | Out-Null
    [System.IO.Compression.ZipFile]::ExtractToDirectory($tc.Zip, $headers)
}
$flags = Join-Path $headerSrc 'TESV_Papyrus_Flags.flg'
if (-not (Test-Path -LiteralPath $flags)) { throw "flags file missing: $flags" }

$src = (Resolve-Path -LiteralPath $Source).Path
$srcDir = Split-Path -Parent $src
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$imports = @($srcDir) + @($Import | ForEach-Object { $_ -split '[,;]' } | Where-Object { $_ } | ForEach-Object { (Resolve-Path -LiteralPath $_).Path }) + @($headerSrc)
$args = @($src, "-f=$flags", "-i=$($imports -join ';')", "-o=$OutDir")
if ($Optimize) { $args += '-op' }
Write-Host "compiler: $($tc.Exe)"
& $tc.Exe @args
if ($LASTEXITCODE -ne 0) { throw "PapyrusCompiler exited $LASTEXITCODE" }
$pex = Join-Path $OutDir ([IO.Path]::GetFileNameWithoutExtension($src) + '.pex')
if (-not (Test-Path -LiteralPath $pex)) { throw "compiler reported success but $pex is missing" }
# The compiler writes the account and machine name into the header (gate row shipped-pex-carries-no-build-identity,
# 2026-10-26): blank them on every compile, by role, so no package has to remember to.
$scrub = "$(@(& py -3 (Join-Path $PSScriptRoot '..\..\resolvers\resolve.py') find pex-scrub)[0])".Trim()
& py -3 $scrub $pex
if ($LASTEXITCODE -ne 0) { throw "pex-scrub failed on $pex ($LASTEXITCODE)" }
Write-Host "wrote $pex ($((Get-Item -LiteralPath $pex).Length) bytes)"
