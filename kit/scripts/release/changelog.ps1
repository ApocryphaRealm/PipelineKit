<#
.SYNOPSIS
    Maintains a per-mod CHANGELOG.md, written as changes happen rather than reconstructed later
    (rule 61).

.DESCRIPTION
    the owner, 2026-08-27: "add a piece of documentation to each mod that gets updated with every
    version update and change to list what the previous changes were... so the change log is
    updated in real time... and so you don't have to reference something outside of the current
    project as often."

    WHY THE TIMING IS THE POINT
    --------------------------
    He raised this straight after a session where the version number and the shipped binary had
    drifted apart: a DLL built at 22:18 carried a version whose fixes were not committed until
    03:04 the next morning. Nothing recorded what was actually IN a given build, so answering
    "does this binary contain the fix" took archaeology across git timestamps, PROGRESS.md and the
    version ledger.

    A changelog written as the change happens is a PRIMARY record. One reconstructed afterwards is
    a reconstruction, and inherits every gap in whatever it was reconstructed from.

    HOW IT DIFFERS FROM WHAT ALREADY EXISTS
    ---------------------------------------
      PROGRESS.md          project-wide, chronological, covers everything
      the Nexus changelog  public-facing, released versions only
      CHANGELOG.md         this mod, every version, living beside the code it describes

    THE STATUS COLUMN IS NOT DECORATION
    -----------------------------------
    Each entry carries the version-ledger status (working / untested / failed / scratch). A
    changelog that reads as a triumph for a version the ledger calls `failed` is worse than no
    changelog, so `check` compares the two and complains when they disagree.

.PARAMETER Action
    add | check | show | status

.EXAMPLE
    .\changelog.ps1 -Action add -Mod DragonsEyeMinimap-SMF -Version 1.5.7 -Type Fixed `
        -Entry "settings reload read through PrivateProfileRedirector's cache and returned defaults"
    .\changelog.ps1 -Action check -Mod DragonsEyeMinimap-SMF -Version 1.5.7
    .\changelog.ps1 -Action show  -Mod DragonsEyeMinimap-SMF
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet('add','check','show','status')][string]$Action,
    [string]$Mod,
    [string]$Version,
    [ValidateSet('Added','Changed','Fixed','Removed','Known')][string]$Type = 'Changed',
    [string]$Entry,
    [string]$Root = $env:PIPELINE_ROOT
)

$ErrorActionPreference = 'Stop'
if (-not $Root) { $_kitRoot = $PSScriptRoot; while ($_kitRoot -and (Split-Path $_kitRoot -Leaf) -ne '.MD') { $_kitRoot = Split-Path $_kitRoot -Parent }; if ($_kitRoot) { $_kitRoot = Split-Path $_kitRoot -Parent }; $Root = $_kitRoot }   # kit: <ROOT> is the folder above the .MD this script sits under, unless PIPELINE_ROOT says otherwise
# Every lookup goes through the resolver OF THIS TREE (STEPS 5.4/5.5), never the absolute <ROOT> path.
$ResolverPy = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\resolvers\resolve.py'))
function Find-Role([string]$role) {
    $p = @(& py -3 $ResolverPy find $role)
    if ($LASTEXITCODE -ne 0 -or $p.Count -eq 0 -or -not "$($p[0])".Trim()) { Write-Output "changelog: cannot resolve role '$role' ($($p -join ' '))"; exit 1 }
    return "$($p[0])".Trim()
}
$RegistryPath = Find-Role 'version-registry'
$LedgerPath = Find-Role 'version-ledger'
$wip = Join-Path $Root '6. current wip mods'

function Repo($mod) {
    $p = Join-Path $wip $mod
    if (Test-Path -LiteralPath $p) { return $p }
    # The same loose match package-mod.ps1 uses (letters and digits only), so a ledger name such as TKDodgeAIO
    # finds the TK-Dodge-AIO repo instead of failing the package gate with a misleading "no entry" message.
    $key = ($mod -replace '[^A-Za-z0-9]', '')
    $hits = @(Get-ChildItem -LiteralPath $wip -Directory -Force -ErrorAction SilentlyContinue |
        Where-Object { ($_.Name -replace '[^A-Za-z0-9]', '') -eq $key })
    if ($hits.Count -eq 1) { return $hits[0].FullName }
    # Still nothing: a ledger key is often the repo name WITHOUT its suffix - the ledger says
    # 'DragonsEyeMinimap' where the repo is 'DragonsEyeMinimap-SMF'. The equality match above
    # cannot see that, so package-mod.ps1's rule-61 gate failed with "no entry for 1.6.6" on a
    # mod whose entry was sitting in the file all along (2026-09-15). Accept a UNIQUE prefix
    # match; ambiguity still fails, because guessing between two repos is worse than stopping.
    $pref = @(Get-ChildItem -LiteralPath $wip -Directory -Force -ErrorAction SilentlyContinue |
        Where-Object { ($_.Name -replace '[^A-Za-z0-9]', '').StartsWith($key, [System.StringComparison]::OrdinalIgnoreCase) })
    if ($pref.Count -eq 1) { return $pref[0].FullName }
    if ($pref.Count -gt 1) {
        Write-Output ("FAILED: '$mod' matches more than one repo: " + (($pref | ForEach-Object { $_.Name }) -join ', '))
        exit 1
    }
    # The ledger KEY and the FOLDER are different strings: the version gate refuses to change an
    # identity once a version has been issued against it, so a renamed repo keeps its old key. The
    # registry's 'repo' field is what says where the source lives now.
    # (2026-09-16: thirteen repos lost their Apocrypha prefix and broke every tool that guessed.)
    $regPath = $RegistryPath
    if (Test-Path -LiteralPath $regPath) {
        $reg = Get-Content -LiteralPath $regPath -Raw | ConvertFrom-Json
        $entry = $reg.PSObject.Properties | Where-Object {
            $_.Name -ieq $mod -or $_.Value.repo -ieq $mod -or $_.Value.displayName -ieq $mod
        } | Select-Object -First 1
        if ($entry -and $entry.Value.repo) {
            $cand = Join-Path $wip $entry.Value.repo
            if (Test-Path -LiteralPath $cand -PathType Container) { return (Resolve-Path -LiteralPath $cand).Path }
        }
    }
    Write-Output "FAILED: no repo at $p"; exit 1
}
function Path-Changelog($mod) { return (Join-Path (Repo $mod) 'CHANGELOG.md') }

function Read-Utf8($p) { if (Test-Path -LiteralPath $p) { return [System.IO.File]::ReadAllText($p) } return '' }
function Write-Utf8($p, $t) {
    # PowerShell 5.1's Set-Content would mangle any non-ASCII here; see rule 60.
    [System.IO.File]::WriteAllText($p, $t, (New-Object System.Text.UTF8Encoding($false)))
}

function Get-LedgerStatus($mod, $version) {
    $lp = $LedgerPath
    if (-not (Test-Path -LiteralPath $lp)) { return $null }
    $rows = Get-Content -LiteralPath $lp -Raw | ConvertFrom-Json
    $e = @($rows) | Where-Object { $_.mod -eq $mod -and $_.version -eq $version } | Select-Object -First 1
    if ($e) { return $e.status }
    return $null
}

switch ($Action) {

    'add' {
        if (-not $Mod -or -not $Version -or -not $Entry) {
            Write-Output 'FAILED: -Mod, -Version and -Entry are required'; exit 1
        }
        $file = Path-Changelog $Mod
        $text = Read-Utf8 $file
        $today = (Get-Date).ToString('yyyy-MM-dd')
        $status = Get-LedgerStatus $Mod $Version
        if (-not $status) { $status = 'untested' }

        if (-not $text) {
            $text = @"
# $Mod - changelog

Written as changes happen, not reconstructed afterwards (rule 61). Each version carries its
**version-ledger status**, so this file cannot quietly claim more than the ledger does:

* **working** - observed running in game
* **untested** - built and packaged, not yet confirmed
* **failed** - built but crashed or malfunctioned; the number was reclaimed
* **scratch** - a hypothesis-test build that never held a real number

"@
        }

        $header = "## $Version - $today - $status"
        if ($text -notmatch [regex]::Escape("## $Version ")) {
            # New version: insert directly beneath the preamble so the newest is always on top.
            $idx = $text.IndexOf("`n## ")
            $bullet = "$header`n`n### $Type`n- $Entry`n"
            if ($idx -lt 0) { $text = $text.TrimEnd() + "`n`n" + $bullet }
            else { $text = $text.Substring(0, $idx + 1) + $bullet + "`n" + $text.Substring($idx + 1) }
        }
        else {
            # Existing version: append under the right Type heading, creating it if needed.
            $lines = $text -split "`r?`n"
            $out = New-Object System.Collections.ArrayList
            $inVer = $false; $placed = $false; $seenType = $false
            for ($i = 0; $i -lt $lines.Count; $i++) {
                $l = $lines[$i]
                if ($l -like "## $Version *") { $inVer = $true }
                elseif ($l -like '## *' -and $inVer -and -not $placed) {
                    if (-not $seenType) { [void]$out.Add("### $Type"); [void]$out.Add("- $Entry"); [void]$out.Add('') }
                    $inVer = $false; $placed = $true
                }
                if ($inVer -and $l -eq "### $Type") { $seenType = $true; [void]$out.Add($l); [void]$out.Add("- $Entry"); $placed = $true; $inVer = $false; continue }
                if ($l -like '## *' -and -not ($l -like "## $Version *")) { $inVer = $false }
                [void]$out.Add($l)
            }
            if (-not $placed) { [void]$out.Add("### $Type"); [void]$out.Add("- $Entry") }
            $text = ($out -join "`n")
        }

        Write-Utf8 $file $text
        Write-Output ("{0} {1} [{2}] {3}" -f $Mod, $Version, $Type, $Entry)
        Write-Output ("  -> {0}" -f $file)
    }

    'check' {
        if (-not $Mod -or -not $Version) { Write-Output 'FAILED: -Mod and -Version are required'; exit 1 }
        $file = Path-Changelog $Mod
        if (-not (Test-Path -LiteralPath $file)) {
            Write-Output ("FAIL: {0} has no CHANGELOG.md. Rule 61: every mod carries its own history." -f $Mod)
            Write-Output ("  changelog.ps1 -Action add -Mod {0} -Version {1} -Type Fixed -Entry '...'" -f $Mod, $Version)
            exit 1
        }
        $text = Read-Utf8 $file
        if ($text -notmatch [regex]::Escape("## $Version ")) {
            Write-Output ("FAIL: CHANGELOG.md has no entry for {0}." -f $Version)
            Write-Output '  A version with no recorded change is a version nobody can later tell the contents of -'
            Write-Output '  which is exactly how a stale binary kept a version number it had not earned.'
            exit 1
        }
        $status = Get-LedgerStatus $Mod $Version
        if ($status) {
            if ($text -match "## $([regex]::Escape($Version)) - \d{4}-\d{2}-\d{2} - (\w+)") {
                $claimed = $Matches[1]
                if ($claimed -ne $status) {
                    Write-Output ("WARN: changelog says '{0}' but the version ledger says '{1}' for {2}." -f $claimed, $status, $Version)
                    Write-Output '  Update the changelog heading - the ledger is the authority on whether a build worked.'
                }
            }
        }
        Write-Output ("OK: {0} {1} is described in CHANGELOG.md" -f $Mod, $Version)
        exit 0
    }

    'show' {
        if (-not $Mod) { Write-Output 'FAILED: -Mod is required'; exit 1 }
        $file = Path-Changelog $Mod
        if (-not (Test-Path -LiteralPath $file)) { Write-Output "no CHANGELOG.md for $Mod"; exit 1 }
        Get-Content -LiteralPath $file | Select-Object -First 40
    }

    'status' {
        Write-Output ''
        Write-Output '  CHANGELOG COVERAGE (rule 61)'
        Write-Output ('  ' + ('-' * 62))
        foreach ($d in (Get-ChildItem -LiteralPath $wip -Directory | Sort-Object Name)) {
            if ($d.Name -like '_*') { continue }
            $f = Join-Path $d.FullName 'CHANGELOG.md'
            if (Test-Path -LiteralPath $f) {
                $n = @([regex]::Matches((Read-Utf8 $f), '(?m)^## \d')).Count
                Write-Output ('  {0,-34} {1} version(s)' -f $d.Name, $n)
            } else {
                Write-Output ('  {0,-34} MISSING' -f $d.Name)
            }
        }
        Write-Output ''
    }
}
