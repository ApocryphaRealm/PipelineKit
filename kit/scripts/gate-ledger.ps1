<#
.SYNOPSIS
    Measures whether the pipeline's JUDGEMENT gates - stage 1 classification and stage 8
    compatibility - actually catch real problems, or merely pass everything through (rule 58).

.DESCRIPTION
    `PIPELINE-RESEARCH.md` §8: the highest-leverage step for improving a pipeline is error
    analysis on real traces - look at where it has actually gone wrong, not where it theoretically
    could - and only then decide what check would have caught each category. Nothing in this
    pipeline measured its two judgement gates at all, so neither could be known to work.

    `falsification-log.ps1` already applies exactly this discipline to troubleshooting. This is the
    same idea pointed at the gates.

    THE FAILURE MODE BEING MEASURED
    ------------------------------
    A gate that always returns the same verdict is not a gate. It is a queue with extra steps, and
    it is indistinguishable from a working gate right up until something it should have caught
    ships. As of 2026-08-27, stage 8 had issued NINE verdicts and every single one was
    "Compatible" - never a caveat, never a conflict. That is not proof it is broken (the mods may
    genuinely all be compatible), but it is exactly the distribution a rubber stamp produces, and
    it went unnoticed because nobody counted.

    WHY UNRESOLVED VERDICTS COUNT FOR NOTHING
    -----------------------------------------
    A verdict is a PREDICTION: "this will not conflict", "this is a rebuild candidate". It is only
    evidence about the gate once reality has had a chance to contradict it - the mod got built, the
    build ran in game, the bug report did or did not arrive. Until then it is unfalsified rather
    than correct, and the scorecard refuses to count it as a success. This mirrors
    version-gate.ps1's refusal to treat "built" as "working".

.PARAMETER Action
    record | resolve | stats | list

.EXAMPLE
    .\gate-ledger.ps1 -Action record -Stage 8 -Subject "HD Local Map" -Verdict compatible `
        -Evidence "no shared Scaleform path with Local Map Upgrade" `
        -Guard "keep the marker registry untouched; check again if either mod adds map markers" `
        -EvidenceRef "8. confirm compatibility\HD Local Map - compatibility.txt"
    (stage 8 compatible / compatible-with-caveats: -Guard and an -EvidenceRef that exists are REQUIRED since 2026-10-27)
    .\gate-ledger.ps1 -Action resolve -Id 3 -Held:$false -What "conflicted over the same map marker registry; found only in game"
    .\gate-ledger.ps1 -Action stats
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet('record','resolve','stats','list')][string]$Action,
    [int]$Id,
    [ValidateSet('1','8')][string]$Stage,
    [string]$Subject,
    [string]$Verdict,
    [string]$Evidence,
    [nullable[bool]]$Held,
    [string]$What,
    # Stage 8 only, optional: the constraint that answers the sceptic's strongest objection
    # (ADVERSARIAL-MODE.md "No bare PASS"). Reported on, never required.
    [string]$Guard,
    # Stage 8, required for compatible / compatible-with-caveats since 2026-10-27 (pipeline assessment item 2b): what the
    # verdict rests on - a combined-run batch id, a test-request id, or a file (absolute, or relative to the project
    # root: a compatibility.txt, a plan's notes) that must exist.
    [string]$EvidenceRef,
    # Ledger file to use. Defaults to the real one; tests point it at a copy in %TEMP%.
    [string]$Ledger,
    # Event log for a test copy's mirror events (step 4). With -Ledger and no -EventLog, no event is written at all;
    # without -Ledger the real ledger's events go to the real log.
    [string]$EventLog
)

$ErrorActionPreference = 'Stop'
$realPath = Join-Path $PSScriptRoot 'gate-ledger.json'
$path = if ($Ledger) { $Ledger } else { $realPath }

# Valid verdicts per gate. Listed here rather than in a ValidateSet because they differ by stage.
$VERDICTS = @{
    '1' = @('SMF Convertible','Framework or Utility','Rebuild Candidate','Backlog',
            'Equipment or Record Based','World Space References')
    '8' = @('compatible','compatible-with-caveats','conflict')
}
# The verdict each gate exists to be ABLE to return. If it never does, the gate is not gating.
$NEGATIVE = @{ '1' = @('Backlog'); '8' = @('conflict','compatible-with-caveats') }
$GATENAME = @{ '1' = 'STAGE 1 - classification'; '8' = 'STAGE 8 - compatibility' }

# See falsification-log.ps1 for why both directions are explicit: piping a one-element array to
# ConvertTo-Json emits a bare object, which silently nests the file on the next append.
if (Test-Path -LiteralPath $path) {
    $parsed = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
    $log = @()
    foreach ($item in @($parsed)) { if ($item -is [array]) { $log += @($item) } else { $log += $item } }
} else { $log = @() }
if ($null -eq $log) { $log = @() }

# The file or record an -EvidenceRef names, or $null when it names nothing that exists (item 2b, 2026-10-27).
function Resolve-EvidenceRef([string]$ref) {
    $r = "$ref".Trim().Trim('"')
    if (-not $r) { return $null }
    $md = Split-Path $PSScriptRoot -Parent
    $bus = if ($env:AGENT_BUS_DIR) { $env:AGENT_BUS_DIR } else { Join-Path $md 'agent-bus' }
    if ($r -match '^B-\d{8}-\d{6}-[0-9a-f]{4}$') {
        $p = Join-Path $bus "test-requests\batches\$r.json"; if (Test-Path -LiteralPath $p) { return $p }; return $null
    }
    if ($r -match '^\d{8}-\d{6}-[A-Za-z0-9-]+-[0-9a-f]{4}$') {
        $p = Join-Path $bus "test-requests\$r.json"; if (Test-Path -LiteralPath $p) { return $p }; return $null
    }
    if ([System.IO.Path]::IsPathRooted($r)) { if (Test-Path -LiteralPath $r) { return $r }; return $null }
    $p = Join-Path (Split-Path $md -Parent) $r
    if (Test-Path -LiteralPath $p) { return $p }
    return $null
}

function Save-Log($data) {
    $json = ConvertTo-Json -InputObject @($data) -Depth 6
    # THE LOG IS THE SOURCE (step 7, SIMPLIFY-3, 2026-10-12): the row event is recorded FIRST (Write-RowEvent, called
    # before Save-Log), then role `events` (`events.py materialize`) writes this file from the fold of the log and
    # refuses unless the fold equals these rows. A test copy with no -EventLog, or any refusal, writes the file directly
    # from the same text, as before the switch-over (a refusal also prints a warning). Rollback:
    # docs-archive\event-log-baseline-2-2026-10-12\README.md.
    if ($Ledger -and -not $EventLog) { Set-Content -LiteralPath $path -Value $json -Encoding UTF8; return }
    $keepExit = $global:LASTEXITCODE
    $tmp = Join-Path $env:TEMP ("gate-ledger-proposed-{0}.json" -f [guid]::NewGuid().ToString('N'))
    try {
        Set-Content -LiteralPath $tmp -Value $json -Encoding UTF8
        $resolvePyM = Join-Path (Split-Path $PSScriptRoot -Parent) 'resolvers\resolve.py'
        $mArgs = @('run', 'events', 'materialize', '--view', 'gate-ledger', '--proposed', $tmp, '--target', $path, '--by', 'gate-ledger.ps1')
        if ($Ledger) { $mArgs += @('--log', $EventLog) }
        $out = @()
        $code = 1
        try { $out = @(& py -3 $resolvePyM @mArgs 2>&1); $code = $global:LASTEXITCODE } catch { $code = 1 }
        if ($code -ne 0) {
            Copy-Item -LiteralPath $tmp -Destination $path -Force
            $said = @($out | Where-Object { "$_" -match 'materialize FAILED' })
            if ($said.Count) { Write-Warning ("event log: gate-ledger written directly - {0}" -f "$($said[0])".Trim()) }
        }
    } finally {
        if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue }
        $global:LASTEXITCODE = $keepExit
    }
}

# DUAL WRITE (step 4 of the one-event-log design, SIMPLIFY-3, 2026-10-12). Each ledger write ALSO records one v2 event
# carrying the WHOLE row as written (row) and refs.source = "gate-ledger.json#<row index>", so `events.py fold
# gate-ledger` rebuilds the file and `events.py check --view gate-ledger` compares the two. The ledger is still
# written exactly as before and stays what every reader uses. Like every log write, this never fails the action.
$resolvePy = Join-Path (Split-Path $PSScriptRoot -Parent) 'resolvers\resolve.py'
# subject.key (event log step 3, 2026-10-12): a verdict's subject is free text, often a mod that is not ours. It gets a
# key only when it IS a registry identity - version-gate's Resolve-Key rule (key, repo, display name or alias, ignoring
# case) with exactly one entry matching; otherwise none.
function Get-SubjectKey([string]$Name) {
    try {
        $regPath = "$(@(& py -3 $resolvePy find version-registry 2>$null)[0])".Trim()
        if (-not $regPath -or -not (Test-Path -LiteralPath $regPath)) { return $null }
        $regK = Get-Content -LiteralPath $regPath -Raw | ConvertFrom-Json
        $hits = @()
        foreach ($p in $regK.PSObject.Properties) {
            $ent = $p.Value
            $aliasHit = @(@($ent.aliases) | Where-Object { $_ -and ($_ -ieq $Name) }).Count -gt 0
            if (($p.Name -ieq $Name) -or ($ent.repo -ieq $Name) -or ($ent.displayName -ieq $Name) -or $aliasHit) { $hits += $p.Name }
        }
        if ($hits.Count -eq 1) { return $hits[0] }
    } catch { }
    return $null
}
function Write-RowEvent([string]$Kind, [string]$Label, $Row, [int]$Index, $EvStage, [string]$Subj, [string]$SubjKey,
                        [string]$Ev, [string]$EvNote) {
    if ($Ledger -and -not $EventLog) { return }   # a test copy with no log named writes no event
    try {
        $plogPath = "$(@(& py -3 $resolvePy find pipeline-log 2>$null)[0])".Trim()
        if (-not $plogPath -or -not (Test-Path -LiteralPath $plogPath)) { return }
        $refs = [ordered]@{ source = ('gate-ledger.json#{0}' -f $Index); verdict_id = $Row.id }
        $a = @{
            Action = 'record'; Kind = $Kind; Event = $Label; Mod = $Subj; Evidence = $Ev; Note = $EvNote
            Row = (ConvertTo-Json -InputObject $Row -Depth 5 -Compress)
            RefsJson = (ConvertTo-Json -InputObject $refs -Compress); By = 'gate-ledger.ps1'
        }
        if ($SubjKey) { $a.Key = $SubjKey }
        if ($EvStage) { $a.Stage = [int]$EvStage }
        if ($Ledger) { $a.LogFile = $EventLog }
        & $plogPath @a | Out-Null
    } catch { }
}

switch ($Action) {

    'record' {
        if (-not $Stage -or -not $Subject -or -not $Verdict) {
            Write-Output 'FAILED: -Stage, -Subject and -Verdict are required'; exit 1
        }
        if ($VERDICTS[$Stage] -notcontains $Verdict) {
            Write-Output ("FAILED: '{0}' is not a valid stage {1} verdict. Valid: {2}" -f $Verdict, $Stage, ($VERDICTS[$Stage] -join ', '))
            exit 1
        }
        if (-not $Evidence) {
            # A verdict with no stated reason cannot later be checked, which makes it unmeasurable
            # - and an unmeasurable gate is the thing this ledger exists to prevent.
            Write-Output 'FAILED: -Evidence is required. What specifically supports this verdict?'
            Write-Output 'A verdict with no stated basis cannot be reviewed later, so it can never'
            Write-Output 'be counted for or against the gate. That is how a rubber stamp hides.'
            exit 1
        }
        # A COMPATIBLE VERDICT NAMES ITS CONDITION AND ITS EVIDENCE (pipeline assessment item 2b, 2026-10-27): 102 stage-8
        # verdicts were never checked against reality and 60 of 64 "compatible" ones carried no condition - the
        # compatibility stop passed on paper. -Guard is the condition under which it holds (rule 58); -EvidenceRef is
        # the batch, request or record it was read from, and it must exist.
        if ($Stage -eq '8' -and $Verdict -in @('compatible', 'compatible-with-caveats')) {
            if (-not "$Guard".Trim()) {
                Write-Output 'FAILED: a compatible verdict needs -Guard "<the condition under which it holds>" (rule 58) - e.g.'
                Write-Output '"holds while neither mod adds map markers" - the line that tells a later reader when to look again.'
                exit 1
            }
            $refFound = Resolve-EvidenceRef $EvidenceRef
            if (-not $refFound) {
                Write-Output ("FAILED: a compatible verdict needs -EvidenceRef naming what it rests on - a combined-run batch id " +
                              "(B-yyyyMMdd-HHmmss-xxxx), a test-request id, or a file that exists (absolute or relative to " +
                              "the project root). Got: '{0}'" -f $EvidenceRef)
                exit 1
            }
        }
        $next = 1
        if ($log.Count) { $next = ([int](($log | Measure-Object -Property id -Maximum).Maximum)) + 1 }
        $log = @($log) + [pscustomobject]@{
            id       = $next
            recorded = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
            stage    = $Stage
            subject  = $Subject
            verdict  = $Verdict
            evidence = $Evidence
            guard    = $(if ($Guard) { $Guard } else { $null })
            evidence_ref = $(if ($EvidenceRef) { $EvidenceRef } else { $null })
            held     = $null     # null = not yet tested against reality
            what     = $null
            resolved = $null
        }
        # A non-default -Ledger is a test copy: it never writes to the real pipeline log (only to -EventLog, if named).
        # The event first, then the file from the log (step 7).
        if ((-not $Ledger) -or $EventLog) {
            $subjectKey = Get-SubjectKey $Subject
            $rowIndex = @($log).Count - 1
            Write-RowEvent 'verdict' "verdict: $Verdict" $log[$rowIndex] $rowIndex $Stage $Subject $subjectKey $Evidence 'UNTESTED - a prediction until reality can contradict it'
        }
        Save-Log $log
        Write-Output ("recorded #{0}  stage {1}  {2} -> {3}" -f $next, $Stage, $Subject, $Verdict)

        Write-Output 'This is a PREDICTION. It counts for nothing until reality has had a chance to'
        Write-Output 'contradict it - resolve it once the mod is built, run, or reported on.'
    }

    'resolve' {
        if (-not $Id -or $null -eq $Held) { Write-Output 'FAILED: -Id and -Held are required'; exit 1 }
        if (-not $What) { Write-Output 'FAILED: -What is required. What actually happened?'; exit 1 }
        $e = $log | Where-Object { $_.id -eq $Id } | Select-Object -First 1
        if (-not $e) { Write-Output ("FAILED: no entry with id {0}" -f $Id); exit 1 }
        $e.held     = [bool]$Held
        $e.what     = $What
        $e.resolved = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
        if ((-not $Ledger) -or $EventLog) {
            $rowIndex = 0
            for ($i = 0; $i -lt @($log).Count; $i++) { if (@($log)[$i].id -eq $Id) { $rowIndex = $i; break } }
            Write-RowEvent 'verdict-resolved' ("verdict resolved: {0}" -f $(if ($Held) { 'held' } else { 'contradicted' })) $e $rowIndex $e.stage $e.subject (Get-SubjectKey $e.subject) $e.evidence $What
        }
        Save-Log $log
        if ($Held) {
            Write-Output ("#{0} HELD - the gate's verdict survived contact with reality." -f $Id)
        } else {
            Write-Output ("#{0} CONTRADICTED - the gate got this wrong." -f $Id)
            Write-Output 'This is the most valuable entry in the ledger. Work out what evidence was'
            Write-Output 'available at verdict time that would have caught it, and make the gate look'
            Write-Output 'for that next time. A miss that changes nothing is just a miss.'
        }
    }

    'stats' {
        # NOTE: local names here must not collide with the PARAMETER names above.
        # PowerShell variables are case-insensitive, so a local `$held` IS the typed
        # [nullable[bool]]$Held parameter, and assigning an array to it throws a
        # transformation error that surfaces at the CALL SITE - which reads as a
        # parameter-binding bug in the caller rather than a name clash in here.
        Write-Output ''
        Write-Output '  GATE SCORECARD  (rule 58)'
        foreach ($st in @('1','8')) {
            $rows = @($log | Where-Object { $_.stage -eq $st })
            Write-Output ''
            Write-Output ("  {0}" -f $GATENAME[$st])
            Write-Output '  ------------------------------------------------------------------'
            if (-not $rows.Count) { Write-Output '  no verdicts recorded'; continue }

            $done = @($rows | Where-Object { $null -ne $_.held })
            $heldRows = @($done | Where-Object { $_.held -eq $true })
            $missRows = @($done | Where-Object { $_.held -eq $false })
            Write-Output ("  verdicts issued                {0}" -f $rows.Count)
            Write-Output ("  tested against reality         {0}" -f $done.Count)
            Write-Output ("    held                         {0}" -f $heldRows.Count)
            Write-Output ("    contradicted                 {0}" -f $missRows.Count)
            if ($rows.Count -gt $done.Count) {
                Write-Output ("  UNTESTED                       {0}   <- these prove nothing either way" -f ($rows.Count - $done.Count))
            }

            Write-Output '  verdict distribution:'
            $rows | Group-Object verdict | Sort-Object Count -Descending | ForEach-Object {
                $pct = [math]::Round(100.0 * $_.Count / $rows.Count, 0)
                Write-Output ("    {0,-30} {1,3}   {2,3}%" -f $_.Name, $_.Count, $pct)
            }

            # The rubber-stamp check. A gate that has never returned its negative verdict is
            # indistinguishable from one that cannot.
            $neg = @($rows | Where-Object { $NEGATIVE[$st] -contains $_.verdict })
            if ($neg.Count -eq 0 -and $rows.Count -ge 5) {
                Write-Output ''
                Write-Output ("  WARNING: {0} verdicts and NOT ONE was {1}." -f $rows.Count, ($NEGATIVE[$st] -join ' or '))
                Write-Output '  That is the distribution a rubber stamp produces. It is not proof the gate is'
                Write-Output '  broken - the cases may genuinely all be clean - but the gate cannot be shown to'
                Write-Output '  be working either, and nothing distinguishes the two from the outside.'
                Write-Output '  Re-examine the closest calls under rule 57 (advocate vs sceptic), and record'
                Write-Output '  what evidence WOULD have produced the other verdict.'
            }
            if ($st -eq '8') {
                # Reports only; never refuses. A forced guard would be a manufactured caveat.
                $okRows = @($rows | Where-Object { $_.verdict -eq 'compatible' })
                $bare = @($okRows | Where-Object { -not $_.guard })
                Write-Output ''
                Write-Output ("  bare passes at stage 8: {0} of {1} compatible verdicts carry no guard" -f $bare.Count, $okRows.Count)
            }
            if ($done.Count -ge 5) {
                $acc = [math]::Round(100.0 * $heldRows.Count / $done.Count, 1)
                Write-Output ''
                Write-Output ("  Accuracy where tested: {0}%  ({1} of {2})" -f $acc, $heldRows.Count, $done.Count)
            } elseif ($rows.Count) {
                Write-Output ''
                Write-Output ("  Too few tested ({0}) to state an accuracy. Report the count, not a rate." -f $done.Count)
            }
        }
        Write-Output ''
    }

    'list' {
        $rows = if ($Stage) { $log | Where-Object { $_.stage -eq $Stage } } else { $log }
        $rows | Sort-Object id | ForEach-Object {
            $mark = if ($null -eq $_.held) { 'UNTESTED    ' } elseif ($_.held) { 'HELD        ' } else { 'CONTRADICTED' }
            Write-Output ("{0,3}  s{1}  {2}  {3,-34} {4}" -f $_.id, $_.stage, $mark, $_.subject, $_.verdict)
            if ($_.evidence) { Write-Output ("        because: {0}" -f $_.evidence) }
            if ($_.what)     { Write-Output ("        reality: {0}" -f $_.what) }
        }
    }
}
