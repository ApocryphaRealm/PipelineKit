# Distro folder names (the owner, 2026-09-29): every folder under "11. Nexus distro" is "<Game> - <Mod>", the game
# first - Skyrim, Oblivion Remastered, Witcher 3, or MO2 for Mod Organizer 2 plugins and themes - and the mod part
# carries no "for Oblivion" / "Oblivion Remastered" / "MO2" of its own. The finalized folders, zips and the version
# registry keep the mod's FULL name, and packages live in "<stage>\<Game> - <Mod>\<Mod> <version>[ FOMOD][.zip]"
# (the owner, 2026-10-01).
#
# Since step 2.3 of the pipeline restructure (2026-10-09) the rules live in ONE place:
#     .MD\resolvers\resolve.py distro <sub>     (run "resolve.py distro" with no sub-command for the usage line)
# Every function below keeps its name, parameters and return type and only asks resolve.py; none has logic of its own.
#
#   ConvertTo-DistroGame    -Game <text>                                  -> 'Skyrim' | 'Oblivion Remastered' | 'MO2' | 'Witcher 3' | ''
#   Get-DistroRoot / Get-DistroMap / Set-DistroMapEntry                   -> the distro root, the folder -> mod map (hashtable)
#   ConvertTo-DistroModPart -ModName -Game                                -> the mod part of a folder name
#   Get-DistroFolderGame    -Folder                                       -> the game a distro folder is for ('' unprefixed)
#   Get-PackageGame         -Path                                         -> the game a package is for, from its contents
#   Test-PackageGame        -PackagePath -FolderGame                      -> [bool]
#   Resolve-DistroFolder    -ModName <full name> [-Game <game>]           -> the folder's full path (existing, or where a new one goes)
#   Resolve-DistroModName   -Folder <folder name> [-FinalizedRoot <p>]    -> the mod's full name
#   ConvertFrom-PackageName -Name <folder or archive name>                -> Mod, Version, Tail, Ext, Symbols (or $null)
#   Get-PackageFolderName   -ModName -Game                                -> "<Game> - <Mod>" (throws without a game)
#   Resolve-PackageRoot     -Root <stage> -ModName <plain> -Game <game>   -> "<stage>\<Game> - <Mod>" (existing or not)
#   Get-ModGame             -Entry <version-registry entry>               -> the game a registered mod is for
#   Find-Packages           -Root <stage> [-ModName] [-Game] [-Version]   -> package folders / archives, with Pkg* members
#   Get-OptionalFileInfo    -ModName <name or key>                        -> $null, or {parent, key, changelog} for an OPTIONAL FILE of another mod's page

$script:DistroNamesResolver = Join-Path (Split-Path -Parent $PSScriptRoot) 'resolvers\resolve.py'

# The one call: arguments go to "resolve.py distro --stdin" as ASCII JSON, the answer comes back as {value} or {error}.
function Invoke-DistroNamesResolver {
    param([string]$ProjectRoot, [object[]]$Argv, $Entry = $null)
    if (-not $script:DistroNamesPython) { $script:DistroNamesPython = "$(& py -3 -c 'import sys; print(sys.executable)')".Trim() }
    $req = @{ root = $ProjectRoot; argv = @($Argv | ForEach-Object { [string]$_ }) }
    if ($null -ne $Entry) { $req.entry = $Entry }
    $json = [regex]::Replace((ConvertTo-Json -InputObject $req -Depth 4 -Compress), '[^\x00-\x7F]', { param($m) '\u{0:x4}' -f [int][char]$m.Value })
    $text = (($json | & $script:DistroNamesPython $script:DistroNamesResolver distro --stdin) -join "`n")
    if (-not $text) { throw "resolve.py distro gave no answer ($($Argv -join ' '))" }
    $r = ConvertFrom-Json -InputObject $text
    if ($r.PSObject.Properties['error']) { throw [string]$r.error }
    return $r
}

function ConvertTo-DistroGame {
    param([string]$Game)
    return [string](Invoke-DistroNamesResolver -Argv @('game', $Game)).value
}

function Get-DistroRoot { param([string]$ProjectRoot = $(if ($env:PIPELINE_ROOT) { $env:PIPELINE_ROOT } else { Split-Path (Split-Path $PSScriptRoot -Parent) -Parent })) [string](Invoke-DistroNamesResolver $ProjectRoot @('root')).value }

function Get-DistroMap {
    param([string]$ProjectRoot = $(if ($env:PIPELINE_ROOT) { $env:PIPELINE_ROOT } else { Split-Path (Split-Path $PSScriptRoot -Parent) -Parent }))
    $map = @{}
    foreach ($prop in (Invoke-DistroNamesResolver $ProjectRoot @('map')).value.PSObject.Properties) { $map[$prop.Name] = [string]$prop.Value }
    return $map
}

function Set-DistroMapEntry {
    param([string]$Folder, [string]$ModName, [string]$ProjectRoot = $(if ($env:PIPELINE_ROOT) { $env:PIPELINE_ROOT } else { Split-Path (Split-Path $PSScriptRoot -Parent) -Parent }))
    $null = Invoke-DistroNamesResolver $ProjectRoot @('map-set', $Folder, $ModName)
}

function ConvertTo-DistroModPart {
    param([string]$ModName, [string]$Game)
    return [string](Invoke-DistroNamesResolver -Argv @('modpart', $ModName, $Game)).value
}

function Get-DistroFolderGame {
    param([Parameter(Mandatory = $true)][string]$Folder)
    return [string](Invoke-DistroNamesResolver -Argv @('foldergame', $Folder)).value
}

function Get-PackageGame {
    param([Parameter(Mandatory = $true)][string]$Path)
    return [string](Invoke-DistroNamesResolver -Argv @('packagegame', $Path)).value
}

function Test-PackageGame {
    param([string]$PackagePath, [string]$FolderGame)
    return [bool](Invoke-DistroNamesResolver -Argv @('testgame', $PackagePath, $FolderGame)).value
}

function Resolve-DistroFolder {
    param([Parameter(Mandatory = $true)][string]$ModName, [string]$Game = '', [string]$ProjectRoot = $(if ($env:PIPELINE_ROOT) { $env:PIPELINE_ROOT } else { Split-Path (Split-Path $PSScriptRoot -Parent) -Parent }))
    return [string](Invoke-DistroNamesResolver $ProjectRoot @('folder', $ModName, '--game', $Game)).value
}

function Resolve-DistroModName {
    param([Parameter(Mandatory = $true)][string]$Folder, [string]$ProjectRoot = $(if ($env:PIPELINE_ROOT) { $env:PIPELINE_ROOT } else { Split-Path (Split-Path $PSScriptRoot -Parent) -Parent }), [string]$FinalizedRoot = '')
    return [string](Invoke-DistroNamesResolver $ProjectRoot @('modname', $Folder, '--finalized-root', $FinalizedRoot)).value
}

function ConvertFrom-PackageName {
    param([Parameter(Mandatory = $true)][string]$Name)
    return (Invoke-DistroNamesResolver -Argv @('parse', $Name)).value
}

function Get-PackageFolderName {
    param([Parameter(Mandatory = $true)][string]$ModName, [string]$Game, [string]$ProjectRoot = $(if ($env:PIPELINE_ROOT) { $env:PIPELINE_ROOT } else { Split-Path (Split-Path $PSScriptRoot -Parent) -Parent }))
    return [string](Invoke-DistroNamesResolver $ProjectRoot @('pkgfolder', $ModName, '--game', $Game)).value
}

function Resolve-PackageRoot {
    param([Parameter(Mandatory = $true)][string]$Root, [Parameter(Mandatory = $true)][string]$ModName, [string]$Game,
          [string]$ProjectRoot = $(if ($env:PIPELINE_ROOT) { $env:PIPELINE_ROOT } else { Split-Path (Split-Path $PSScriptRoot -Parent) -Parent }))
    return [string](Invoke-DistroNamesResolver $ProjectRoot @('pkgroot', $Root, $ModName, '--game', $Game)).value
}

function Get-ModGame {
    param([Parameter(Mandatory = $true)]$Entry, [string]$ProjectRoot = $(if ($env:PIPELINE_ROOT) { $env:PIPELINE_ROOT } else { Split-Path (Split-Path $PSScriptRoot -Parent) -Parent }))
    $fields = @{ pluginDir = "$($Entry.pluginDir)"; nexusDomain = "$($Entry.nexusDomain)"; displayName = "$($Entry.displayName)" }
    if ($Entry.PSObject.Properties['game']) { $fields.game = "$($Entry.game)" }
    return [string](Invoke-DistroNamesResolver $ProjectRoot @('modgame') $fields).value
}

function Find-Packages {
    param([Parameter(Mandatory = $true)][string]$Root, [string]$ModName, [string]$Game, [string]$Version,
          [switch]$Folders, [switch]$Archives, [switch]$IncludeSymbols, [string]$ProjectRoot = $(if ($env:PIPELINE_ROOT) { $env:PIPELINE_ROOT } else { Split-Path (Split-Path $PSScriptRoot -Parent) -Parent }))
    $argv = @('find-packages', $Root, '--mod', $ModName, '--game', $Game, '--version', $Version)
    if ($Folders) { $argv += '--folders' }; if ($Archives) { $argv += '--archives' }; if ($IncludeSymbols) { $argv += '--symbols' }
    return @(foreach ($p in @((Invoke-DistroNamesResolver $ProjectRoot $argv).value)) {
        Get-Item -LiteralPath $p.path -Force | Add-Member -NotePropertyName PkgMod -NotePropertyValue $p.mod -Force -PassThru |
            Add-Member -NotePropertyName PkgVersion -NotePropertyValue ([version]$p.version) -Force -PassThru |
            Add-Member -NotePropertyName PkgTail -NotePropertyValue $p.tail -Force -PassThru |
            Add-Member -NotePropertyName PkgGame -NotePropertyValue $p.game -Force -PassThru |
            Add-Member -NotePropertyName PkgFlat -NotePropertyValue ([bool]$p.flat) -Force -PassThru |
            Add-Member -NotePropertyName PkgRoot -NotePropertyValue $p.root -Force -PassThru
    })
}

# The 'optional file of <parent>' relation (the owner, 2026-10-19: Local Map Item Markers posts as an optional file on
# Local Map Upgrade's page and has no page of its own). A version-registry entry with "optionalFileOf": "<parent display
# name>" (and optionally "optionalChangelog": "<file>") is such a file. Returns $null for any other mod, else
# {parent, key, changelog}; Resolve-DistroFolder answers the PARENT's folder for it. The rules live in resolve.py
# (distro_optional).
function Get-OptionalFileInfo {
    param([Parameter(Mandatory = $true)][string]$ModName, [string]$ProjectRoot = $(if ($env:PIPELINE_ROOT) { $env:PIPELINE_ROOT } else { Split-Path (Split-Path $PSScriptRoot -Parent) -Parent }))
    return (Invoke-DistroNamesResolver $ProjectRoot @('optional', $ModName)).value
}
