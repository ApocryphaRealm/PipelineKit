<#
.SYNOPSIS
    Appends a timestamped progress checkpoint to the session journal - automatically, on a timer,
    with no user input.

.DESCRIPTION
    the owner, 2026-08-28: "Have a running timer for each starting session with the sanity check so that
    all progress in a session is automatically recorded without my input, durably and persistently."

    A Claude session can end or reset at any moment (context limits, a crash, the night ending), and
    anything not on disk is lost. PROGRESS.md is written deliberately at milestones; this is the
    involuntary counterpart - a timer-driven record of what ACTUALLY changed, harvested from
    objective on-disk evidence rather than from anything the session has to remember to do:

      * new git commits across .MD and every repo under `6. current wip mods` (the commit messages
        are the narrative - this project commits constantly and descriptively)
      * version-ledger changes (a build recorded working/failed/untested)
      * new or changed packages in `7. current test builds`
      * new crash logs, and whether the game / MO2 are running
      * DevBench liveness and which driving tools answered

    It is a NO-OP when nothing changed, so running it every ten minutes forever is harmless and the
    journal stays readable. State (what it has already reported) lives beside the journal.

.NOTES
    Run hidden via the wscript wrapper (standing preference: no console flash).
    Register/refresh the timer with -Install. -Start writes a session-start banner.
#>
param(
    [switch]$Install,
    [switch]$Start,
    [string]$Note,
    [string]$Root = $env:PIPELINE_ROOT
)

$ErrorActionPreference = 'Continue'
if (-not $Root) { $_kitRoot = $PSScriptRoot; while ($_kitRoot -and (Split-Path $_kitRoot -Leaf) -ne '.MD') { $_kitRoot = Split-Path $_kitRoot -Parent }; if ($_kitRoot) { $_kitRoot = Split-Path $_kitRoot -Parent }; $Root = $_kitRoot }   # kit: <ROOT> is the folder above the .MD this script sits under, unless PIPELINE_ROOT says otherwise
# Every lookup goes through the resolver OF THIS TREE (STEPS 5.4/5.10), never the absolute <ROOT> path.
$ResolverPy = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\resolvers\resolve.py'))
function Find-Role([string]$role) {
    $p = @(& py -3 $ResolverPy find $role)
    if ($LASTEXITCODE -ne 0 -or $p.Count -eq 0 -or -not "$($p[0])".Trim()) { Write-Output "session-checkpoint: cannot resolve role '$role' ($($p -join ' '))"; exit 1 }
    return "$($p[0])".Trim()
}
$DistroNamesPath = Find-Role 'distro-names'

$md        = Join-Path $Root '.MD'
$journalRt = Join-Path $md 'session-journal'
$statePath = Join-Path $journalRt '.checkpoint-state.json'
$journal   = Join-Path $journalRt ("{0}.md" -f (Get-Date -Format 'yyyy-MM-dd'))
$wipRoot   = Join-Path $Root '6. current wip mods'
$buildsRt  = Join-Path $Root '7. current test builds'
$ledger    = Join-Path $md 'scripts\version-ledger.json'

New-Item -ItemType Directory -Force $journalRt | Out-Null

# ---------------------------------------------------------------------------------------------
# -Install: register (or refresh) the hidden 10-minute timer. Idempotent.
# ---------------------------------------------------------------------------------------------
if ($Install) {
    $self = $MyInvocation.MyCommand.Path
    $vbs  = Join-Path $journalRt 'run-checkpoint-hidden.vbs'
    # wscript wrapper: powershell -WindowStyle Hidden still flashes a console (standing rule).
    $vbsBody = @"
Set sh = CreateObject("WScript.Shell")
sh.Run "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ""$self""", 0, False
"@
    [IO.File]::WriteAllText($vbs, $vbsBody, (New-Object Text.ASCIIEncoding))

    $action  = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument ('//B //Nologo "' + $vbs + '"')
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
                   -RepetitionInterval (New-TimeSpan -Minutes 10) -RepetitionDuration (New-TimeSpan -Days 3650)
    Register-ScheduledTask -TaskName 'Claude Session Checkpoint' -Action $action -Trigger $trigger -Force | Out-Null
    Write-Output "session checkpoint timer installed (every 10 min, hidden)"
    return
}

# ---------------------------------------------------------------------------------------------
# State: what has already been journalled.
# ---------------------------------------------------------------------------------------------
$state = @{ commits = @{}; ledger = ''; packages = @(); crashes = @() }
if (Test-Path -LiteralPath $statePath) {
    try {
        $loaded = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
        if ($loaded.commits) { $loaded.commits.PSObject.Properties | ForEach-Object { $state.commits[$_.Name] = $_.Value } }
        if ($loaded.ledger)   { $state.ledger   = [string]$loaded.ledger }
        if ($loaded.packages) { $state.packages = @($loaded.packages) }
        if ($loaded.crashes)  { $state.crashes  = @($loaded.crashes) }
    } catch { }
}

$lines = New-Object System.Collections.Generic.List[string]

# ---- git commits across .MD and every wip repo -----------------------------------------------
$repos = @()
if (Test-Path -LiteralPath (Join-Path $md '.git')) { $repos += ,@('.MD', $md) }
if (Test-Path -LiteralPath $wipRoot) {
    Get-ChildItem -LiteralPath $wipRoot -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        if (Test-Path -LiteralPath (Join-Path $_.FullName '.git')) { $repos += ,@($_.Name, $_.FullName) }
    }
}
foreach ($r in $repos) {
    $name = $r[0]; $path = $r[1]
    $head = (& git -C $path rev-parse HEAD 2>$null)
    if (-not $head) { continue }
    $since = $state.commits[$name]
    $range = if ($since) { "$since..HEAD" } else { '-1' }
    $log = if ($since) { & git -C $path log --oneline $range 2>$null } else { & git -C $path log --oneline -1 2>$null }
    if ($since -and $log) {
        foreach ($l in $log) { $lines.Add("- **$name**: $l") }
    }
    $state.commits[$name] = $head
}

# ---- version-ledger changes ------------------------------------------------------------------
if (Test-Path -LiteralPath $ledger) {
    $hash = (Get-FileHash -LiteralPath $ledger -Algorithm SHA1).Hash
    if ($state.ledger -and $hash -ne $state.ledger) {
        try {
            $rows = Get-Content -LiteralPath $ledger -Raw | ConvertFrom-Json
            $recent = @($rows) | Select-Object -Last 3
            foreach ($e in $recent) { $lines.Add("- **ledger**: $($e.mod) $($e.version) = $($e.status)") }
        } catch { $lines.Add('- **ledger**: changed') }
    }
    $state.ledger = $hash
}

# ---- new packages ----------------------------------------------------------------------------
if (Test-Path -LiteralPath $buildsRt) {
    # packages sit in their "<Game> - <Mod>" folders since 2026-10-01; recorded as "<Game> - <Mod>\<package>"
    . $DistroNamesPath
    $pkgs = @(Find-Packages -Root $buildsRt -Folders -IncludeSymbols -ProjectRoot $Root | ForEach-Object { if ($_.PkgFlat) { $_.Name } else { '{0}\{1}' -f (Split-Path $_.PkgRoot -Leaf), $_.Name } })
    # a state saved before the move holds no "<Game> - <Mod>\" names: re-baselined silently, not logged as ~100 new packages
    if ($state.packages.Count -gt 0 -and @($state.packages | Where-Object { "$_" -like '*\*' }).Count -gt 0) {
        $new = @($pkgs | Where-Object { $state.packages -notcontains $_ })
        foreach ($p in $new) { $lines.Add("- **packaged**: $p") }
    }
    $state.packages = $pkgs
}

# ---- new crash logs --------------------------------------------------------------------------
$skse = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'My Games\Skyrim Special Edition\SKSE'
if (Test-Path -LiteralPath $skse) {
    $cl = @(Get-ChildItem -LiteralPath $skse -Filter 'crash-*.log' -ErrorAction SilentlyContinue | ForEach-Object { $_.Name })
    if ($state.crashes.Count -gt 0) {
        foreach ($c in @($cl | Where-Object { $state.crashes -notcontains $_ })) { $lines.Add("- **CRASH**: $c") }
    }
    $state.crashes = $cl
}

# ---- explicit note (a session can drop a line in deliberately) --------------------------------
if ($Note) { $lines.Add("- $Note") }

# ---- session-start banner --------------------------------------------------------------------
$stamp = Get-Date -Format 'HH:mm'
if ($Start) {
    $game = if (Get-Process SkyrimSE -ErrorAction SilentlyContinue) { 'game RUNNING' } else { 'no game' }
    $mo2  = if (Get-Process ModOrganizer -ErrorAction SilentlyContinue) { 'MO2 running' } else { 'MO2 closed' }
    Add-Content -LiteralPath $journal -Encoding UTF8 -Value @"

## Session started $stamp  ($mo2, $game)
_Checkpoints below are written automatically every 10 minutes from on-disk evidence - commits,
ledger changes, packages, crashes - so progress survives a session reset with no user input._
"@
}

# ---- write the checkpoint (no-op when nothing changed) ---------------------------------------
if ($lines.Count -gt 0) {
    $body = "`r`n### $stamp checkpoint`r`n" + (($lines | ForEach-Object { $_ }) -join "`r`n") + "`r`n"
    Add-Content -LiteralPath $journal -Encoding UTF8 -Value $body
}

($state | ConvertTo-Json -Depth 6) | Set-Content -LiteralPath $statePath -Encoding UTF8

if ($lines.Count -gt 0) { Write-Output "checkpoint written: $($lines.Count) item(s) -> $journal" }
else { Write-Output 'no changes since the last checkpoint (no-op)' }
