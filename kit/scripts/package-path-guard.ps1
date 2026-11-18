# Dot-source this, then call Assert-PackagePath before every write, copy, zip or DELETE of a package path.
#
# Why (2026-09-28 storage audit): a package path built as "$stage\$name $ver" with empty variables is "$stage\ ", and
# Windows drops the trailing space - the path IS the stage folder (Test-Path returns True). On 2026-09-05 that zipped
# all of 7 into "7\.zip" and copied all of 7 into 10; the same shape followed by Remove-Item -Recurse -Force, which these
# packaging scripts use to clear the old package, would permanently erase 7, 10 or 11. The guard throws instead.
#
#   Assert-PackagePath $pkg (Join-Path $root '10. finalized mods')            # "<Game> - <Mod>\<Name> X.Y.Z[ FOMOD]"
#   Assert-PackagePath $dd  (Join-Path $root '11. Nexus distro') -AnyName     # a named folder, no version required
function Assert-PackagePath([string]$Path, [string]$StageRoot, [switch]$AnyName) {
    if ([string]::IsNullOrWhiteSpace($Path)) { throw "package-path-guard: empty path" }
    $leaf = Split-Path $Path -Leaf
    if ([string]::IsNullOrWhiteSpace($leaf) -or $leaf -ne $leaf.Trim() -or $leaf.StartsWith('.')) {
        throw "package-path-guard: refusing an empty or padded package name: '$Path'"
    }
    if (-not $AnyName -and $leaf -notmatch '^\S.*\s\d+\.\d+\.\d+(\s+FOMOD)?(\.zip)?$') {
        throw "package-path-guard: not a package name (<Name> X.Y.Z): '$leaf'"
    }
    $full = [IO.Path]::GetFullPath($Path).TrimEnd('\', ' ')
    $stage = [IO.Path]::GetFullPath($StageRoot).TrimEnd('\', ' ')
    if ($full -ieq $stage) { throw "package-path-guard: '$Path' resolves to the stage folder itself" }
    $parent = [IO.Path]::GetDirectoryName($full)
    # since 2026-10-01 a package sits in its game folder, "<stage>\<Game> - <Mod>\<Name> X.Y.Z" (Resolve-PackageRoot in
    # distro-names.ps1); a path directly in the stage is still accepted for the flat layout's leftovers
    $inGameFolder = ([IO.Path]::GetDirectoryName($parent) -ieq $stage) -and ((Split-Path $parent -Leaf) -match '^(Skyrim|Oblivion Remastered|MO2) - \S')
    if ($parent -ine $stage -and -not $inGameFolder) { throw "package-path-guard: '$Path' is not inside '$StageRoot' or one of its '<Game> - <Mod>' folders" }
}
