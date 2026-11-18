<#
.SYNOPSIS
    Records what a sub-agent step actually touched: hash every file under the watched roots BEFORE the step,
    hash again AFTER, print the difference.
.DESCRIPTION
    The pipeline-restructure step plan (4. plans\pipeline-restructure\STEPS.md) hands bounded jobs to sub-agents
    whose "may touch" list is a promise, not a guarantee (logic library, 2026-09-02: a sub-agent told "do not touch
    this" did it anyway). This tool turns the promise into an observation: the main session runs -Action before,
    dispatches the agent, runs -Action after, and compares the printed ADDED / CHANGED / REMOVED lines with the
    step's list. Anything outside the list is reverted before the step is accepted.

    Watched roots: .MD, the plan folder, settings.json, the skills folder and the memory folders - plus -ExtraRoots.
    Excluded: .git, .MD\logs (reports and this tool's own snapshots live there), the session journal, *.jsonl,
    __pycache__. Snapshots: .MD\logs\touch\<Step>.before.json / .after.json.

    .\touch-snapshot.ps1 -Action before -Step 0.2
    .\touch-snapshot.ps1 -Action after  -Step 0.2            # prints the difference; CLEAN when there is none
#>
param(
    [Parameter(Mandatory = $true)][ValidateSet('before', 'after')][string]$Action,
    [Parameter(Mandatory = $true)][string]$Step,
    [string[]]$ExtraRoots = @(),
    [string]$ProjectRoot = $env:PIPELINE_ROOT
)
$ErrorActionPreference = 'Stop'
if (-not $ProjectRoot) { $_kitRoot = $PSScriptRoot; while ($_kitRoot -and (Split-Path $_kitRoot -Leaf) -ne '.MD') { $_kitRoot = Split-Path $_kitRoot -Parent }; if ($_kitRoot) { $_kitRoot = Split-Path $_kitRoot -Parent }; $ProjectRoot = $_kitRoot }   # kit: <ROOT> is the folder above the .MD this script sits under, unless PIPELINE_ROOT says otherwise
$home_ = $env:USERPROFILE
$roots = @(
    (Join-Path $ProjectRoot '.MD'),
    (Join-Path $home_ '.claude\settings.json'),
    (Join-Path $home_ '.claude\skills'),
    (Join-Path $home_ ('.claude\projects\' + ($ProjectRoot -replace '[^A-Za-z0-9]', '-') + '\memory'))   # kit: the memory of the project started at <ROOT>
) + $ExtraRoots
$exclude = '\\\.git(\\|$)|\\\.MD\\logs(\\|$)|\\session-journal(\\|$)|\.jsonl$|\\__pycache__(\\|$)'
$outDir = Join-Path $ProjectRoot '.MD\logs\touch'
if (-not (Test-Path -LiteralPath $outDir)) { New-Item -ItemType Directory -Path $outDir | Out-Null }
$safeStep = ($Step -replace '[^A-Za-z0-9._-]', '_')
$beforeFile = Join-Path $outDir "$safeStep.before.json"
$afterFile  = Join-Path $outDir "$safeStep.after.json"

function Get-Snapshot {
    $md5 = [System.Security.Cryptography.MD5]::Create()
    $snap = @{}
    foreach ($r in $roots) {
        if (-not (Test-Path -LiteralPath $r)) { continue }
        $items = if (Test-Path -LiteralPath $r -PathType Leaf) { @(Get-Item -LiteralPath $r) }
                 else { @(Get-ChildItem -LiteralPath $r -Recurse -File -Force -ErrorAction SilentlyContinue) }
        foreach ($f in $items) {
            if ($f.FullName -match $exclude) { continue }
            try {
                $bytes = [System.IO.File]::ReadAllBytes($f.FullName)
                $snap[$f.FullName] = [BitConverter]::ToString($md5.ComputeHash($bytes)).Replace('-', '')
            } catch { $snap[$f.FullName] = 'UNREADABLE' }
        }
    }
    return $snap
}
function Save-Snapshot($snap, $path) {
    $ordered = [ordered]@{}
    foreach ($k in ($snap.Keys | Sort-Object)) { $ordered[$k] = $snap[$k] }
    $json = ($ordered | ConvertTo-Json -Depth 2)
    [System.IO.File]::WriteAllText($path, $json, (New-Object System.Text.UTF8Encoding($false)))
}

$now = Get-Snapshot
if ($Action -eq 'before') {
    Save-Snapshot $now $beforeFile
    Write-Output ("before  step {0}: {1} files hashed -> {2}" -f $Step, $now.Count, $beforeFile)
    exit 0
}
if (-not (Test-Path -LiteralPath $beforeFile)) { Write-Output "no BEFORE snapshot for step $Step - run -Action before first"; exit 1 }
$beforeJson = Get-Content -LiteralPath $beforeFile -Raw -Encoding UTF8 | ConvertFrom-Json
$before = @{}
foreach ($p in $beforeJson.PSObject.Properties) { $before[$p.Name] = [string]$p.Value }
Save-Snapshot $now $afterFile
$added = @(); $changed = @(); $removed = @()
foreach ($k in $now.Keys)    { if (-not $before.ContainsKey($k)) { $added += $k } elseif ($before[$k] -ne $now[$k]) { $changed += $k } }
foreach ($k in $before.Keys) { if (-not $now.ContainsKey($k)) { $removed += $k } }
Write-Output ("after   step {0}: {1} files hashed" -f $Step, $now.Count)
foreach ($k in ($added   | Sort-Object)) { Write-Output ("  ADDED    {0}" -f $k) }
foreach ($k in ($changed | Sort-Object)) { Write-Output ("  CHANGED  {0}" -f $k) }
foreach ($k in ($removed | Sort-Object)) { Write-Output ("  REMOVED  {0}" -f $k) }
if (-not $added -and -not $changed -and -not $removed) { Write-Output '  CLEAN - nothing under the watched roots changed' }
Write-Output ("  {0} added, {1} changed, {2} removed" -f $added.Count, $changed.Count, $removed.Count)
exit 0
