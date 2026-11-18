<#
.SYNOPSIS
    The pipeline's own event log - one append-only record of what every stage actually did, with
    per-stage views generated on demand.

.DESCRIPTION
    The question this answers is "what has stage 8 been doing?", which until now meant archaeology
    across 416 KB of PROGRESS.md. The 2026-09-02 optimization sweep showed the cost: stage 1 had
    never recorded a single classification verdict and nobody had noticed for months.

    WHY ONE LOG AND NOT TWELVE DOCUMENTS
    ------------------------------------
    A document per stage was the obvious shape and it is the wrong one, for a reason this project
    has already paid to learn: anything a person or an agent has to REMEMBER to write drifts the
    moment work gets busy. That is exactly why the session journal exists as the involuntary
    counterpart to PROGRESS.md (rule 65). Twelve hand-maintained files would also make a sixth
    overlapping record next to the gate ledger, the version ledger, the falsification log,
    queue.jsonl and the journal - and the one you happen to read would be the one nobody updated.

    So the writes live in the SCRIPTS that perform each transition. A stage cannot forget to log,
    because the log line is part of the thing it does. The per-stage document is then a VIEW,
    rendered when someone asks for it, and it cannot disagree with the events it is derived from.

    WHAT COUNTS AS AN EVENT
    -----------------------
    A transition or a verdict - something that happened, at a stage, to a named thing. Not chatter.
    One line each: when, which stage, what happened, to which mod and version, and the evidence.

    NEVER BREAKS ITS CALLER
    -----------------------
    A logging failure must never fail a build, a package or a gate. -Action record swallows its own
    errors and always exits 0, printing a single warning line. The opposite failure - a log that
    silently stops recording - is caught by `summary`, which names any stage with no events at all
    rather than showing a tidy list of the stages that do work.

.PARAMETER Action
    record | view | summary | backfill

.EXAMPLE
    .\pipeline-log.ps1 -Action record -Stage 7 -Event packaged -Mod "Dragon's Eye Minimap" -Version 1.6.2 -Evidence "DLL 1.6.2.0, PDB paired"
.EXAMPLE
    .\pipeline-log.ps1 -Action view -Stage 8 -Since 7d
.EXAMPLE
    .\pipeline-log.ps1 -Action summary
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet('record','view','summary','backfill')][string]$Action,
    [ValidateRange(1, 12)][int]$Stage,
    [string]$Event,
    [string]$Mod,
    # The version-registry KEY of the mod (step 3 of the one-event-log design): -Mod stays the display name, -Key
    # becomes subject.key. Only a writer that knows the key passes it; nothing is guessed here.
    [string]$Key,
    # The watched folder an arrival came from (reconcile): carried as refs.folder so `events.py check` can compare
    # the event's stage with the folder's.
    [string]$Folder,
    # Step 4 (dual write): a ledger tool's mirror event. -Kind names the kind outright (else it is mapped from
    # -Event); -Row is the whole ledger row as JSON text; -RefsJson adds refs (refs.source "<file>#<index>" ...)
    # as JSON text. With -Kind, -Stage may be left out: the event then has no stage, and the views below skip it.
    [string]$Kind,
    [string]$Row,
    [string]$RefsJson,
    [string]$Version,
    [string]$Evidence,
    [string]$Note,
    [string]$By,
    [string]$Since = '30d',
    [string]$Root = $env:PIPELINE_ROOT,
    [int]$Tail = 40,
    # The log file. Default: the real log beside .MD. Tests point it at a copy.
    [string]$LogFile
)

$ErrorActionPreference = 'Stop'
if (-not $Root) { $_kitRoot = $PSScriptRoot; while ($_kitRoot -and (Split-Path $_kitRoot -Leaf) -ne '.MD') { $_kitRoot = Split-Path $_kitRoot -Parent }; if ($_kitRoot) { $_kitRoot = Split-Path $_kitRoot -Parent }; $Root = $_kitRoot }   # kit: <ROOT> is the folder above the .MD this script sits under, unless PIPELINE_ROOT says otherwise
$md  = Split-Path $PSScriptRoot -Parent
$log = if ($LogFile) { $LogFile } else { Join-Path $md 'pipeline-events.jsonl' }
# record delegates to role `events` (events.py) through the resolver - by role, never by path (rule 70).
$resolvePy = Join-Path $md 'resolvers\resolve.py'

# The twelve stages, so a view can name what it is showing rather than printing a bare number.
$STAGE_NAMES = @{
    1 = 'mod sorter (intake, triage)'
    2 = 'Mod Types (staging, bug reports, queue)'
    3 = 'analyze mods (research)'
    4 = 'plans'
    5 = 'current project mod'
    6 = 'current wip mods (build)'
    7 = 'current test builds (package, install)'
    8 = 'confirm compatibility (verdict)'
    9 = 'patches output'
    10 = 'finalized mods'
    11 = 'Nexus distro'
    12 = 'needs an update'
}

function Parse-Since([string]$s) {
    if (-not $s) { return [datetime]::MinValue }
    if ($s -match '^(\d+)([dhw])$') {
        $n = [int]$Matches[1]
        switch ($Matches[2]) {
            'h' { return (Get-Date).AddHours(-$n) }
            'd' { return (Get-Date).AddDays(-$n) }
            'w' { return (Get-Date).AddDays(-7 * $n) }
        }
    }
    try { return [datetime]::Parse($s) } catch { return [datetime]::MinValue }
}

function Read-Events {
    if (-not (Test-Path -LiteralPath $log)) { return @() }
    $out = New-Object System.Collections.ArrayList
    foreach ($line in [System.IO.File]::ReadAllLines($log)) {
        if (-not $line.Trim()) { continue }
        try {
            $o = $line | ConvertFrom-Json
            if ($o.v -eq 2) {
                # A v2 event with no stage (a ledger mirror, step 4) belongs to no stage view.
                if ($null -eq $o.stage) { continue }
                # A v2 event (events.py, step 1 of the one-event-log design) is shown through the v1 fields the
                # views already use: subject.display is the mod, subject.version the version, provenance
                # 'backfilled' the old backfilled flag.
                $sub = $o.subject
                $o = [pscustomobject]@{
                    ts = $o.ts; stage = $o.stage; event = $o.event
                    mod = $(if ($sub) { $sub.display } else { $null })
                    version = $(if ($sub) { $sub.version } else { $null })
                    evidence = $o.evidence; note = $o.note; by = $o.by
                    backfilled = ($o.provenance -eq 'backfilled')
                }
            }
            [void]$out.Add($o)
        }
        catch { }   # one malformed line must not hide the rest of the log
    }
    return $out
}

function Sort-Stable($items) {
    # by time, ties in the order read from the file
    $i = 0
    @($items | ForEach-Object { [pscustomobject]@{ k = [datetime]::Parse($_.ts); i = $i; e = $_ }; $i++ } |
        Sort-Object k, i | ForEach-Object { $_.e })
}

function Write-Event($obj) {
    # UTF-8 without BOM, appended as one line. .NET APIs rather than Add-Content, per rule 60's
    # encoding finding (PowerShell 5.1 reads a BOM-less UTF-8 file as cp1252 and writes the wreck
    # back). One line per event means a crash mid-write can cost the last line and nothing else.
    $json = ($obj | ConvertTo-Json -Compress -Depth 5)
    [System.IO.File]::AppendAllText($log, $json + "`r`n", (New-Object System.Text.UTF8Encoding($false)))
}

switch ($Action) {

'record' {
    try {
        if (-not $Stage -and -not $Kind) { throw '-Stage is required' }
        if (-not $Event) { throw '-Event is required' }
        $caller = if ($By) { $By } else {
            $c = (Get-PSCallStack | Where-Object { $_.ScriptName -and $_.ScriptName -ne $PSCommandPath } | Select-Object -First 1)
            if ($c) { Split-Path $c.ScriptName -Leaf } else { 'interactive' }
        }
        $v1 = [ordered]@{
            ts       = (Get-Date).ToString('o')
            stage    = $(if ($Stage) { $Stage } else { $null })
            event    = $Event
            mod      = $Mod
            version  = $Version
            evidence = $Evidence
            note     = $Note
            by       = $caller
        }
        # Delegate to events.py (role events): a v2 event, kind mapped from the label by events.py's own table
        # (--kind auto), provenance live. The fields travel in a temp JSON file, not on the command line,
        # because Windows PowerShell 5.1 mangles embedded double quotes in native arguments. If events.py
        # cannot be run at all (or refuses), the event is still kept: written the v1 way, as before.
        $delegated = $false
        $tmp = Join-Path $env:TEMP ("pipeline-log-{0}.json" -f [guid]::NewGuid().ToString('N'))
        try {
            $payload = [ordered]@{
                kind = $(if ($Kind) { $Kind } else { 'auto' }); event = $Event
                stage = $(if ($Stage) { $Stage } else { $null }); display = $Mod; version = $Version
                evidence = $Evidence; note = $Note; by = $caller; provenance = 'live'; ts = $v1.ts
            }
            if ($Key) { $payload['key'] = $Key }
            if ($Folder) { $payload['refs'] = [ordered]@{ folder = $Folder } }
            if ($Row) { $payload['row_json'] = $Row }
            if ($RefsJson) { $payload['refs_json'] = $RefsJson }
            [System.IO.File]::WriteAllText($tmp, ($payload | ConvertTo-Json -Compress -Depth 5),
                (New-Object System.Text.UTF8Encoding($false)))
            $evArgs = @($resolvePy, 'run', 'events', 'record', '--payload-file', $tmp)
            if ($LogFile) { $evArgs += @('--log', $LogFile) }
            $said = @(& py -3 @evArgs)
            $code = $LASTEXITCODE
            foreach ($l in $said) { if ("$l" -match '\[warn\]') { Write-Output "$l" } }
            if ($code -eq 0) { $delegated = $true }
            else { Write-Output ("  [warn] pipeline-log: events.py exited {0} ({1}) - recording the v1 way" -f $code, (($said | Select-Object -First 2) -join ' ')) }
        }
        catch {
            Write-Output ("  [warn] pipeline-log: events.py could not be run ({0}) - recording the v1 way" -f $_.Exception.Message)
        }
        finally {
            if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue }
        }
        if (-not $delegated) { Write-Event $v1 }
    }
    catch {
        # Deliberately soft: the caller is packaging a mod or running a gate, and a log that cannot
        # write is not a reason to fail that work. It is a reason to say so on the console.
        Write-Output ("  [warn] pipeline-log could not record this event: {0}" -f $_.Exception.Message)
    }
    exit 0
}

'view' {
    $from = Parse-Since $Since
    $rows = @(Read-Events | Where-Object {
        $ok = $true
        if ($Stage) { $ok = $ok -and ($_.stage -eq $Stage) }
        if ($Mod)   { $ok = $ok -and ($_.mod -like "*$Mod*") }
        if ($_.ts)  { $ok = $ok -and ([datetime]::Parse($_.ts) -ge $from) }
        $ok
    })
    $what = if ($Stage) { "stage $Stage - $($STAGE_NAMES[$Stage])" } else { 'all stages' }
    Write-Output ''
    Write-Output ("  PIPELINE EVENTS - {0}, since {1}" -f $what, $Since)
    Write-Output ('  ' + ('-' * 76))
    if (-not $rows.Count) {
        Write-Output '  no events recorded in this window.'
        Write-Output '  That is a finding, not an empty result: either nothing happened, or the'
        Write-Output '  script that performs this stage does not record. Check which.'
        exit 0
    }
    # Append order is not chronological: the backfill wrote one source at a time, so events
    # arrived grouped by origin rather than by when they happened. Sort on read.
    # Sort-Object is not stable: events with the same ts (the backfill wrote many) came out in a different order from
    # one run to the next. Ties now keep the file's order (2026-10-12).
    $rows = @(Sort-Stable $rows)
    foreach ($e in ($rows | Select-Object -Last $Tail)) {
        $when = ([datetime]::Parse($e.ts)).ToString('MM-dd HH:mm')
        $name = @($e.mod, $e.version | Where-Object { $_ }) -join ' '
        Write-Output ("  {0}  [{1,2}] {2,-16} {3}" -f $when, $e.stage, $e.event, $name)
        if ($e.evidence) { Write-Output ("                         {0}" -f $e.evidence) }
        if ($e.note)     { Write-Output ("                         note: {0}" -f $e.note) }
    }
    Write-Output ''
    Write-Output ("  {0} event(s); showing the last {1}. Written by: {2}" -f $rows.Count,
        [Math]::Min($Tail, $rows.Count), (($rows | ForEach-Object { $_.by } | Sort-Object -Unique) -join ', '))
}

'summary' {
    $all = @(Read-Events)
    Write-Output ''
    Write-Output '  PIPELINE EVENT LOG - what each stage has on record'
    Write-Output ('  ' + ('-' * 76))
    if (-not $all.Count) { Write-Output '  the log is empty - run -Action backfill to seed it from the existing ledgers.'; exit 0 }
    $silent = @()
    foreach ($s in 1..12) {
        $rows = @($all | Where-Object { $_.stage -eq $s })
        if (-not $rows.Count) {
            Write-Output ("  {0,2}. {1,-42} {2}" -f $s, $STAGE_NAMES[$s], 'NO EVENTS')
            $silent += $s
            continue
        }
        $last = (Sort-Stable $rows | Select-Object -Last 1)
        Write-Output ("  {0,2}. {1,-42} {2,4} event(s), last {3} ({4})" -f $s, $STAGE_NAMES[$s],
            $rows.Count, ([datetime]::Parse($last.ts)).ToString('MM-dd'), $last.event)
    }
    Write-Output ''
    if ($silent.Count) {
        Write-Output ("  Stage(s) with nothing on record: {0}." -f ($silent -join ', '))
        Write-Output '  A silent stage is either genuinely idle or not wired to record. The second'
        Write-Output '  case is invisible from any other document, which is what this log is for.'
    } else {
        Write-Output '  Every stage has events on record.'
    }
    $bf = @($all | Where-Object { $_.backfilled })
    if ($bf.Count) {
        Write-Output ("  {0} of {1} event(s) are BACKFILLED - reconstructed from other records, not observed live." -f $bf.Count, $all.Count)
    }
}

'backfill' {
    # Seeds the log from records that already exist, so the first views are not empty. Everything
    # written here is marked backfilled:true and dated from the artefact it was derived from - a
    # reconstruction inherits every gap in what it was reconstructed from (rule 61's own reasoning),
    # so it must never be mistaken for something that was observed as it happened.
    if (Test-Path -LiteralPath $log) {
        $existing = @(Read-Events | Where-Object { $_.backfilled })
        if ($existing.Count) { Write-Output ("  {0} backfilled event(s) already present - remove them first to re-seed." -f $existing.Count); exit 0 }
    }
    $added = 0

    # Stage 1 and 8 verdicts, from the gate ledger (a JSON array: id, recorded, stage, subject,
    # verdict, evidence, held, what, resolved).
    $gl = Join-Path $PSScriptRoot 'gate-ledger.json'
    if (Test-Path -LiteralPath $gl) {
        # ConvertFrom-Json in PowerShell 5.1 writes an array to the pipeline as ONE object, so
        # @( ... | ConvertFrom-Json ) is a single-element array holding an Object[]. Assign first,
        # then let foreach enumerate it.
        $verdicts = [System.IO.File]::ReadAllText($gl) | ConvertFrom-Json
        foreach ($v in $verdicts) {
            if (-not $v.stage) { continue }
            $resolution = if ($null -ne $v.resolved) { "resolved $($v.resolved): $($v.what)" } else { 'UNTESTED - proves nothing yet' }
            Write-Event ([ordered]@{
                ts = $(if ($v.recorded) { ([datetime]$v.recorded).ToString('o') } else { (Get-Date).ToString('o') })
                stage = [int]$v.stage; event = "verdict: $($v.verdict)"
                mod = $v.subject; version = ''
                evidence = $v.evidence; note = $resolution
                by = 'gate-ledger.json'; backfilled = $true
            })
            $added++
        }
    }

    # Stage 7, from the version ledger: a build that earned a status is a build that was packaged.
    $vl = Join-Path $PSScriptRoot 'version-ledger.json'
    if (Test-Path -LiteralPath $vl) {
        $builds = [System.IO.File]::ReadAllText($vl) | ConvertFrom-Json
        foreach ($e in $builds) {
            if (-not $e.version) { continue }
            Write-Event ([ordered]@{
                ts = $(if ($e.recorded) { ([datetime]$e.recorded).ToString('o') } else { (Get-Date).ToString('o') })
                stage = 6; event = "build $($e.status)"
                mod = $e.mod; version = $e.version
                evidence = $e.evidence; note = ''
                by = 'version-ledger.json'; backfilled = $true
            })
            $added++
        }
    }

    # Stage 7, from the packages actually sitting in test builds (in their "<Game> - <Mod>" folders since 2026-10-01).
    . (Join-Path $PSScriptRoot 'distro-names.ps1')
    $tb = Join-Path $Root '7. current test builds'
    if (Test-Path -LiteralPath $tb) {
        foreach ($d in @(Find-Packages -Root $tb -Folders -ProjectRoot $Root)) {
            if ($d.Name -notmatch '^(?<n>.+?) (?<v>\d+\.\d+\.\d+)$') { continue }
            Write-Event ([ordered]@{
                ts = $d.LastWriteTime.ToString('o'); stage = 7; event = 'packaged'
                mod = $Matches['n']; version = $Matches['v']
                evidence = 'package present in 7. current test builds'; note = ''
                by = 'filesystem'; backfilled = $true
            })
            $added++
        }
    }

    # Stage 11, from the distro zips that were actually built.
    $nd = Join-Path $Root '11. Nexus distro'
    if (Test-Path -LiteralPath $nd) {
        foreach ($z in (Get-ChildItem -LiteralPath $nd -Filter '*.zip' -Recurse -File -Force -ErrorAction SilentlyContinue)) {
            if ($z.BaseName -notmatch '^(?<n>.+?) (?<v>\d+\.\d+\.\d+)$') { continue }
            Write-Event ([ordered]@{
                ts = $z.LastWriteTime.ToString('o'); stage = 11; event = 'distro package built'
                mod = $Matches['n']; version = $Matches['v']
                evidence = ("{0} ({1:N1} MB)" -f $z.Name, ($z.Length / 1MB)); note = ''
                by = 'filesystem'; backfilled = $true
            })
            $added++
        }
    }

    # Stage 10, from what is actually sitting in finalized mods.
    $fin = Join-Path $Root '10. finalized mods'
    if (Test-Path -LiteralPath $fin) {
        foreach ($d in @(Find-Packages -Root $fin -Folders -ProjectRoot $Root)) {
            if ($d.Name -notmatch '^(?<n>.+?) (?<v>\d+\.\d+\.\d+)$') { continue }
            Write-Event ([ordered]@{
                ts = $d.LastWriteTime.ToString('o'); stage = 10; event = 'finalized'
                mod = $Matches['n']; version = $Matches['v']
                evidence = 'package present in 10. finalized mods'; note = ''
                by = 'filesystem'; backfilled = $true
            })
            $added++
        }
    }

    Write-Output ("  backfilled {0} event(s) into {1}" -f $added, $log)
    Write-Output '  All are marked backfilled:true - reconstructed, not observed.'
}

}
