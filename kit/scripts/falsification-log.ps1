<#
.SYNOPSIS
    The record of hypotheses, the attempts made to destroy them, and whether the survivors were
    actually right - which is the only way to know whether this method works (rule 56).

.DESCRIPTION
    the owner, 2026-08-27: "add a troubleshooting mode where you use reasoning from analysis and create
    a hypothesis for the issue, and you try to disprove your own hypothesis, and log how effective
    this process is in actually resolving an issue."

    The second half of that instruction is the part that gives the first half teeth. A
    self-critique step that is never scored decays into theatre - a paragraph that performs
    scepticism, followed by doing exactly what was planned anyway. Logging predictions and
    outcomes is what makes the difference between those two things visible from outside.

    THE ONE HARD GATE
    -----------------
    'open' REFUSES without -Kills: a statement of what observable result would prove the
    hypothesis wrong. This is not paperwork. If no such result can be named, the idea is not yet
    a hypothesis - it is a description that fits the facts, and it will keep fitting them no
    matter what happens next. Naming the killing condition BEFORE the test also stops the usual
    quiet failure, where a result arrives and the criterion is adjusted to accommodate it.

    WHAT THE SCORECARD MEASURES, AND WHY THE THIRD NUMBER IS THE IMPORTANT ONE
    -------------------------------------------------------------------------
      killed      died during refutation, before any fix was built. A CHEAP SAVE - the whole
                  point of the method. Costs minutes; would have cost a build-test cycle.
      confirmed   survived refutation, fix built, PROBLEM ACTUALLY WENT AWAY. A true positive.
      false       survived refutation, fix built, PROBLEM REMAINED. The dangerous case.

    'false' is the honest test of the method. If hypotheses routinely survive refutation and are
    wrong anyway, then the refutation is too soft and the ritual is being trusted in place of the
    reasoning. The response to a rising 'false' count is to attack harder - not to keep score
    more carefully.

    A method that only ever recorded its successes would be measuring its own marketing.

.PARAMETER Action
    open | refute | close | stats | list

.EXAMPLE
    .\falsification-log.ps1 -Action open -Issue "DEM crashes on load" `
        -Hypothesis "the MGEF archetype lookup runs before forms are loaded" `
        -Kills "if it still crashes with the lookup removed entirely, the archetype is not the cause" `
        -Walked "read DEM.cpp line 212 and crash log line 40: the lookup receives a null form pointer" `
        -Radius "src/Lookup.cpp","src/Lookup.h" `
        -Rivals "layout-sensitive latent corruption; a bug in a third-party DLL"

    -Card, -Walked and -Radius are mandatory for 'open' (waived for -Baseline). -Card names the episode's
    PROBLEM CARD (role problem-card, rule 56 amended 2026-11-16: inputs with their source of truth,
    relationships, output, check, assumptions); open runs `problem-card check` on it and refuses unless
    it passes. The card's ASSUMPTIONS are where -Kills and -Rivals come from. -RootCause is mandatory for
    'close -Outcome resolved'. -Repo names the git repo whose HEAD is recorded at open (default: the
    current directory's repo). -Ledger points at another ledger file (tests use a %TEMP% copy).

    .\falsification-log.ps1 -Action refute -Id 7 -Test "stub the lookup to a constant and run" `
        -Result "still crashed, same address" -Verdict killed

    .\falsification-log.ps1 -Action close -Id 7 -Outcome not-resolved -Evidence "cause found elsewhere"
    .\falsification-log.ps1 -Action close -Id 8 -Outcome resolved -Evidence "no crash in 5 loads" `
        -RootCause "no gate checked that the lookup runs after forms are loaded"
    .\falsification-log.ps1 -Action stats
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet('open','refute','close','contest','stats','list')][string]$Action,
    [int]$Id,
    [string]$Issue,
    [string]$Hypothesis,
    [string]$Kills,
    [string]$Rivals,
    [string]$Test,
    [string]$Result,
    [ValidateSet('survived','killed')][string]$Verdict,
    [ValidateSet('resolved','not-resolved','abandoned')][string]$Outcome,
    [string]$Evidence,
    [string]$Mod,
    [switch]$Baseline,
    [string]$Advocate,
    [string]$Skeptic,
    [ValidateSet('advocate','skeptic','neither')][string]$Winner,
    [string]$Walked,
    [string[]]$Radius,
    [string]$RootCause,
    [string]$Repo,
    [string]$Card,
    [string]$Ledger,
    # Event log for a test copy's mirror events (step 4 of the one-event-log design). With -Ledger and no -EventLog,
    # no event is written; without -Ledger the real ledger's events go to the real pipeline log.
    [string]$EventLog
)

# BASELINE entries record episodes from BEFORE this mode existed - hypotheses that were acted on
# without ever being attacked. They are kept apart from live episodes in the scorecard, and that
# separation is the point: counting them as failures of the method would blame it for outcomes it
# was not present for, while leaving them out would throw away the only "before" measurement there
# is. A method claiming to help needs something to be better THAN.

$ErrorActionPreference = 'Stop'
# -Ledger points the script at another ledger file (the tests use a copy in %TEMP%); by default
# it is the real one beside this script.
$path = if ($Ledger) { $Ledger } else { Join-Path $PSScriptRoot 'falsification-log.json' }

# PS 5.1 JSON round-tripping has one sharp edge that silently corrupts a ledger, and it cost a
# debugging detour here: piping a ONE-element array to ConvertTo-Json emits a bare object rather
# than an array. Read that back, append, save again, and the file can end up NESTED - [[{..}]] -
# after which every property access returns System.Object[] instead of a value. The failure is
# quiet: the file still parses, so nothing complains until a property is used.
#
# Both directions are therefore made explicit. -InputObject @(...) always writes a real array,
# even for one entry, and the read flattens defensively in case an older nested file exists.
if (Test-Path -LiteralPath $path) {
    $parsed = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
    $log = @()
    foreach ($item in @($parsed)) {
        if ($item -is [array]) { $log += @($item) } else { $log += $item }
    }
} else {
    $log = @()
}
if ($null -eq $log) { $log = @() }

function Save-Log($data) {
    $json = ConvertTo-Json -InputObject @($data) -Depth 6
    # THE LOG IS THE SOURCE (step 7, SIMPLIFY-3, 2026-10-12): the row event is recorded FIRST (Write-RowEvent, called
    # before Save-Log), then role `events` (`events.py materialize`) writes this file from the fold of the log and
    # refuses unless the fold equals these rows. A test copy with no -EventLog, or any refusal, writes the file directly
    # from the same text, as before the switch-over (a refusal also prints a warning). Rollback:
    # docs-archive\event-log-baseline-2-2026-10-12\README.md.
    if ($Ledger -and -not $EventLog) { Set-Content -LiteralPath $path -Value $json -Encoding UTF8; return }
    $keepExit = $global:LASTEXITCODE
    $tmp = Join-Path $env:TEMP ("falsification-log-proposed-{0}.json" -f [guid]::NewGuid().ToString('N'))
    try {
        Set-Content -LiteralPath $tmp -Value $json -Encoding UTF8
        $resolvePyM = Join-Path (Split-Path $PSScriptRoot -Parent) 'resolvers\resolve.py'
        $mArgs = @('run', 'events', 'materialize', '--view', 'falsification-log', '--proposed', $tmp, '--target', $path, '--by', 'falsification-log.ps1')
        if ($Ledger) { $mArgs += @('--log', $EventLog) }
        $out = @()
        $code = 1
        try { $out = @(& py -3 $resolvePyM @mArgs 2>&1); $code = $global:LASTEXITCODE } catch { $code = 1 }
        if ($code -ne 0) {
            Copy-Item -LiteralPath $tmp -Destination $path -Force
            $said = @($out | Where-Object { "$_" -match 'materialize FAILED' })
            if ($said.Count) { Write-Warning ("event log: falsification-log written directly - {0}" -f "$($said[0])".Trim()) }
        }
    } finally {
        if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue }
        $global:LASTEXITCODE = $keepExit
    }
}

# DUAL WRITE (step 4 of the one-event-log design, SIMPLIFY-3, 2026-10-12). Each write of an episode ALSO records one v2
# event carrying the WHOLE episode as written (row) and refs.source = "falsification-log.json#<index>" (refs.episode_id
# = its id), so `events.py fold falsification-log` rebuilds the file and `events.py check --view falsification-log`
# compares the two. Kinds: open -> episode-open, refute and contest -> episode-attempt (a contest is an attempt with
# contest: true), close -> episode-close. Episodes belong to no pipeline stage, so the event has none. The ledger is
# still written exactly as before; like every log write, this never fails the action.
function Write-RowEvent([string]$Kind, [string]$Label, $Episode, [switch]$IsContest) {
    if ($Ledger -and -not $EventLog) { return }   # a test copy with no log named writes no event
    try {
        $resolvePy = Join-Path (Split-Path $PSScriptRoot -Parent) 'resolvers\resolve.py'
        $plogPath = "$(@(& py -3 $resolvePy find pipeline-log 2>$null)[0])".Trim()
        if (-not $plogPath -or -not (Test-Path -LiteralPath $plogPath)) { return }
        $index = 0
        $all = @($log)
        for ($i = 0; $i -lt $all.Count; $i++) { if ($all[$i].id -eq $Episode.id) { $index = $i; break } }
        $refs = [ordered]@{ source = ('falsification-log.json#{0}' -f $index); episode_id = $Episode.id }
        if ($IsContest) { $refs['contest'] = $true }
        $a = @{
            Action = 'record'; Kind = $Kind; Event = $Label; Evidence = "$($Episode.evidence)"
            Note = "$($Episode.hypothesis)"
            Row = (ConvertTo-Json -InputObject $Episode -Depth 5 -Compress)
            RefsJson = (ConvertTo-Json -InputObject $refs -Compress); By = 'falsification-log.ps1'
        }
        if ($Episode.mod) { $a.Mod = "$($Episode.mod)" }
        if ($Ledger) { $a.LogFile = $EventLog }
        & $plogPath @a | Out-Null
    } catch { }
}
function Get-GitText($repoDir, [string[]]$gitArgs) {
    $out = & git -C $repoDir @gitArgs 2>$null
    if ($LASTEXITCODE -ne 0) { return $null }
    return @($out)
}
function Test-InRadius([string]$file, $radius) {
    $f = ($file -replace '\\', '/')
    while ($f.StartsWith('./')) { $f = $f.Substring(2) }
    foreach ($r in @($radius)) {
        $g = (([string]$r) -replace '\\', '/').Trim()
        while ($g.StartsWith('./')) { $g = $g.Substring(2) }
        if (-not $g) { continue }
        if ($f -like $g) { return $true }
        if ($g.EndsWith('/') -and $f.StartsWith($g, [System.StringComparison]::OrdinalIgnoreCase)) { return $true }
        if ($g -notmatch '[*?\[]' -and $f.StartsWith($g + '/', [System.StringComparison]::OrdinalIgnoreCase)) { return $true }
    }
    return $false
}
function Get-Episode($n) {
    $e = $log | Where-Object { $_.id -eq $n } | Select-Object -First 1
    if (-not $e) { Write-Output ("FAILED: no episode with id {0}" -f $n); exit 1 }
    return $e
}

switch ($Action) {

    'open' {
        if (-not $Issue -or -not $Hypothesis) { Write-Output 'FAILED: -Issue and -Hypothesis are required'; exit 1 }
        # G0 (rule 56, amended 2026-11-16 - the owner: "define the variables ... define the relationships ... and then
        # produce the output"): the PROBLEM CARD comes first and must pass `problem-card check`. Waived for -Baseline,
        # like every other open gate: those episodes are retrospective.
        $cardPath = $null
        if (-not $Baseline) {
            if (-not $Card -or -not $Card.Trim()) {
                Write-Output 'FAILED: -Card is required. Write the problem card first and pass its path:'
                Write-Output '  resolve.py run problem-card new --task "<the issue>" [--area <topic>]'
                Write-Output 'Fill INPUTS (each with its source of truth), RELATIONSHIPS, OUTPUT, CHECK and ASSUMPTIONS,'
                Write-Output 'then open again with -Card <path>. The card''s ASSUMPTIONS are what this episode attacks:'
                Write-Output 'the hypothesis is usually one of them taken as true, -Kills is the observation that would'
                Write-Output 'show it false, and the other assumptions are the -Rivals.'
                exit 1
            }
            if (-not (Test-Path -LiteralPath $Card)) { Write-Output ("FAILED: -Card names a file that does not exist: {0}" -f $Card); exit 1 }
            $cardPath = (Resolve-Path -LiteralPath $Card).Path
            $resolvePyC = Join-Path (Split-Path $PSScriptRoot -Parent) 'resolvers\resolve.py'
            $cardOut = @(); $cardCode = 1
            try { $cardOut = @(& py -3 $resolvePyC run problem-card check $cardPath 2>&1); $cardCode = $global:LASTEXITCODE }
            catch { $cardOut = @("problem-card check could not run: $_"); $cardCode = 1 }
            if ($cardCode -ne 0) {
                Write-Output ("FAILED: the problem card does not pass its check (exit {0}):" -f $cardCode)
                $cardOut | ForEach-Object { Write-Output ("  {0}" -f $_) }
                Write-Output 'Fix the card, then open again. Its ASSUMPTIONS feed -Kills and -Rivals: an episode built on a'
                Write-Output 'card with unnamed sources or unlisted assumptions attacks the wrong thing.'
                exit 1
            }
        }
        if (-not $Kills -and -not $Baseline) {
            # The gate. See the header - this is the whole mechanism, not a formality.
            # Waived for -Baseline, because the defining feature of those episodes is that nobody
            # asked the question at the time. Demanding it retroactively would invent a rigour
            # that was not there and quietly flatter the record.
            Write-Output 'FAILED: -Kills is required. State the observable result that would prove this hypothesis WRONG.'
            Write-Output ''
            Write-Output 'If you cannot name one, you do not have a hypothesis yet - you have a description that'
            Write-Output 'fits the facts, and it will go on fitting them whatever happens. Keep analysing instead:'
            Write-Output '  * what does this explanation FORBID? if nothing, it predicts nothing'
            Write-Output '  * what would the world look like if it were false, and does it already look like that?'
            exit 1
        }
        # G1 and G2 (step 12.11): the data-path walk and the blast radius, both stated BEFORE
        # the first test. Waived for -Baseline for the same reason -Kills is: those episodes
        # are retrospective and nobody walked or bounded anything at the time.
        # With -File, "a","b" can arrive as the single string "a,b"; split on commas so both forms work.
        $radiusList = @($Radius | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ })
        if (-not $Baseline) {
            if (-not $Walked -or -not $Walked.Trim()) {
                Write-Output 'FAILED: -Walked is required. State what you read BY HAND before forming this hypothesis: the header, the struct, the log line, and the value it carried.'
                Write-Output ''
                Write-Output 'A hypothesis built on what a call is believed to receive, rather than what it was seen'
                Write-Output 'to receive, is the commonest way to spend a build-test cycle on nothing:'
                Write-Output '  * which file or log line did you open, and what exactly did it say?'
                Write-Output '  * what is the real type and value at the point of failure?'
                exit 1
            }
            if ($radiusList.Count -eq 0) {
                Write-Output 'FAILED: -Radius is required. Name the repo-relative paths or globs the fix may touch, BEFORE editing.'
                Write-Output ''
                Write-Output 'A fix that grows past its stated radius is a second hypothesis smuggled in without a'
                Write-Output 'killing condition. If you cannot bound the fix, the hypothesis is not yet specific enough.'
                exit 1
            }
        }
        $repoRoot = $null; $headAtOpen = $null
        $repoDir = if ($Repo) { $Repo } else { (Get-Location).Path }
        if (Test-Path -LiteralPath $repoDir) {
            # @() around each call: a one-line result comes back as a bare string, and $x[0] would be its first character.
            $top = @(Get-GitText $repoDir @('rev-parse','--show-toplevel'))
            if ($top.Count -and $top[0]) {
                $repoRoot = ([string]$top[0]).Trim()
                $h = @(Get-GitText $repoRoot @('rev-parse','HEAD'))
                if ($h.Count -and $h[0]) { $headAtOpen = ([string]$h[0]).Trim() }
            }
        }
        $next = 1
        if ($log.Count) { $next = ([int](($log | Measure-Object -Property id -Maximum).Maximum)) + 1 }
        $entry = [pscustomobject]@{
            id         = $next
            opened     = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
            baseline   = [bool]$Baseline
            mod        = $Mod
            issue      = $Issue
            hypothesis = $Hypothesis
            kills      = $Kills
            rivals     = $Rivals
            walked     = $Walked
            radius     = @($radiusList)
            repo       = $repoRoot
            head       = $headAtOpen
            card       = $cardPath
            rootCause  = $null
            attempts   = @()
            status     = 'open'
            outcome    = $null
            evidence   = $null
            closed     = $null
        }
        $log = @($log) + $entry
        Write-RowEvent 'episode-open' 'episode open' $entry
        Save-Log $log
        Write-Output ("opened episode {0}: {1}" -f $next, $Hypothesis)
        Write-Output ("  falsified by: {0}" -f $Kills)
        if ($Rivals) { Write-Output ("  rivals: {0}" -f $Rivals) }
        if ($Walked) { Write-Output ("  walked: {0}" -f $Walked) }
        if ($radiusList.Count) { Write-Output ("  radius: {0}" -f ($radiusList -join ', ')) }
        if ($cardPath) { Write-Output ("  card: {0} (passed problem-card check)" -f $cardPath) }
        if (-not $Baseline -and -not $headAtOpen) { Write-Output '  WARN  no git repo found at open; the radius cannot be compared at close (pass -Repo <path>)' }
        Write-Output ''
        Write-Output 'Now run the CHEAPEST test that discriminates. A test whose result is the same whether'
        Write-Output 'the hypothesis is true or false has told you nothing, however much work it was.'
    }

    'refute' {
        if (-not $Id -or -not $Test -or -not $Verdict) { Write-Output 'FAILED: -Id, -Test and -Verdict are required'; exit 1 }
        $e = Get-Episode $Id
        $e.attempts = @($e.attempts) + [pscustomobject]@{
            at      = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
            test    = $Test
            result  = $Result
            verdict = $Verdict
        }
        if ($Verdict -eq 'killed') {
            $e.status  = 'closed'
            $e.outcome = 'killed'
            $e.closed  = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
            $e.evidence = $Result
            Write-Output ("episode {0} KILLED before any fix was built - that is the method working, not failing." -f $Id)
            Write-Output 'Form the next hypothesis from what the test actually showed, not from the wreckage of this one.'
        } else {
            $e.status = 'survived'
            Write-Output ("episode {0}: hypothesis SURVIVED attempt {1}." -f $Id, @($e.attempts).Count)
            Write-Output 'Surviving one attack is weak evidence. Is there a cheaper test that could still kill it?'
            Write-Output 'If a rival explanation also survives this test, the test did not discriminate.'
        }
        Write-RowEvent 'episode-attempt' ("episode attempt: {0}" -f $Verdict) $e
        Save-Log $log
    }

    'close' {
        if (-not $Id -or -not $Outcome) { Write-Output 'FAILED: -Id and -Outcome are required'; exit 1 }
        $e = Get-Episode $Id
        if ($e.outcome -eq 'killed') { Write-Output ("episode {0} was already killed during refutation" -f $Id); exit 0 }
        if ($Outcome -eq 'resolved' -and -not $Evidence) {
            Write-Output 'FAILED: -Evidence is required for -Outcome resolved. What was OBSERVED to change?'
            exit 1
        }
        if ($Outcome -eq 'resolved' -and (-not $RootCause -or -not $RootCause.Trim())) {
            Write-Output 'FAILED: -RootCause is required for -Outcome resolved. State the LAST why: the cause behind the cause you fixed.'
            Write-Output ''
            Write-Output 'A fix that removes the symptom but not the reason it could happen comes back. Ask why until'
            Write-Output 'the answer is something a change to the process, a gate or a design would prevent.'
            exit 1
        }
        # G2 at close: compare what the fix really touched with the radius declared at open.
        $outside = @()
        $radiusNote = $null
        if ($Outcome -eq 'resolved') {
            $decl = @($e.radius | Where-Object { $_ })
            if ($decl.Count -and $e.repo -and $e.head -and (Test-Path -LiteralPath $e.repo)) {
                $touched = @()
                $committed = Get-GitText $e.repo @('diff','--name-only',("{0}..HEAD" -f $e.head))
                $working   = Get-GitText $e.repo @('diff','--name-only','HEAD')
                $untracked = Get-GitText $e.repo @('ls-files','--others','--exclude-standard')
                foreach ($x in @($committed) + @($working) + @($untracked)) { if ($x) { $touched += ([string]$x).Trim() } }
                $touched = @($touched | Sort-Object -Unique)
                $outside = @($touched | Where-Object { -not (Test-InRadius $_ $decl) })
            } elseif ($decl.Count) {
                $radiusNote = 'WARN  the radius was not compared (no repo or HEAD recorded at open)'
            }
        }
        $e.status   = 'closed'
        $e.outcome  = if ($outside.Count) { 'resolved-outside-radius' } else { $Outcome }
        $e.evidence = $Evidence
        if ($Outcome -eq 'resolved') { Add-Member -InputObject $e -NotePropertyName rootCause -NotePropertyValue $RootCause -Force }
        $e.closed   = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
        Write-RowEvent 'episode-close' ("episode close: {0}" -f $e.outcome) $e
        Save-Log $log
        if ($outside.Count) {
            foreach ($o in $outside) { Write-Output ("FAIL  the fix touched {0}, outside its declared radius" -f $o) }
            Write-Output ("episode {0} closed: resolved-outside-radius" -f $Id)
            Write-Output 'The problem may be fixed, but the fix grew past what the hypothesis covered, so the result cannot be'
            Write-Output 'attributed to the hypothesis alone. It is counted on its own line, not as a clean confirmation.'
            exit 1
        }
        if ($radiusNote) { Write-Output $radiusNote }
        Write-Output ("episode {0} closed: {1}" -f $Id, $Outcome)
        if ($Outcome -eq 'not-resolved') {
            Write-Output ''
            Write-Output 'This is a FALSE SURVIVOR: it withstood refutation and was wrong anyway. The refutation'
            Write-Output 'was too soft. Before the next hypothesis, work out which attack should have caught it -'
            Write-Output 'that missing attack is worth more than the next guess.'
        }
    }

    'contest' {
        # Records the outcome of a DUAL-TRACK contest (rule 57): an advocate and a sceptic argued
        # the same hypothesis independently, and a third pass judged between them.
        #
        # 'neither' is a first-class verdict, not a cop-out. Forcing a winner from two weak cases
        # manufactures confidence that neither case earned, and that is the specific way an
        # adversarial setup goes wrong - it always produces a winner, even when the honest answer
        # is that nobody knows yet.
        if (-not $Id -or -not $Winner) { Write-Output 'FAILED: -Id and -Winner are required'; exit 1 }
        if (-not $Advocate -or -not $Skeptic) {
            Write-Output 'FAILED: -Advocate and -Skeptic are both required. A contest with only one'
            Write-Output 'side recorded is not a contest, and would score as though it had been one.'
            exit 1
        }
        $e = Get-Episode $Id
        Add-Member -InputObject $e -NotePropertyName contest -NotePropertyValue ([pscustomobject]@{
            at       = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
            advocate = $Advocate
            skeptic  = $Skeptic
            winner   = $Winner
            why      = $Evidence
        }) -Force
        if ($Winner -eq 'skeptic') {
            $e.status   = 'closed'
            $e.outcome  = 'killed'
            $e.closed   = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
            $e.evidence = $Skeptic
        } elseif ($Winner -eq 'advocate') {
            $e.status = 'survived'
        }
        Write-RowEvent 'episode-attempt' ("episode contest: {0}" -f $Winner) $e -IsContest
        Save-Log $log

        switch ($Winner) {
            'advocate' {
                Write-Output ("episode {0}: the ADVOCATE won. The hypothesis survived an independent attempt to" -f $Id)
                Write-Output 'destroy it, which is the strongest evidence this process produces. Build the fix.'
            }
            'skeptic' {
                Write-Output ("episode {0}: the SCEPTIC won - killed before a fix was built." -f $Id)
                Write-Output 'Form the next hypothesis from what the sceptic actually demonstrated.'
            }
            'neither' {
                Write-Output ("episode {0}: NEITHER case was strong enough. This is a real result, not a failure." -f $Id)
                Write-Output 'Do not build on it and do not pick a winner to make progress. Go get the evidence'
                Write-Output 'that would separate them - the adjudication named what is missing.'
            }
        }
    }

    'stats' {
        # Builds its report into a list and returns it, rather than writing as it goes. In
        # PowerShell a function's output is EVERYTHING it emits, so `$b = Get-Block ...` would
        # capture the report text along with the return value and print nothing at all - which is
        # exactly what happened the first time this was written.
        function Get-Block($rows, $title, $isBaseline) {
            $lines     = New-Object System.Collections.ArrayList
            $closed    = @($rows | Where-Object { $_.status -eq 'closed' })
            $killed    = @($closed | Where-Object { $_.outcome -eq 'killed' })
            $confirmed = @($closed | Where-Object { $_.outcome -eq 'resolved' })
            $wrong     = @($closed | Where-Object { $_.outcome -eq 'not-resolved' })
            $abandoned = @($closed | Where-Object { $_.outcome -eq 'abandoned' })
            $outRadius = @($closed | Where-Object { $_.outcome -eq 'resolved-outside-radius' })
            $unclosed  = @($rows | Where-Object { $_.status -ne 'closed' })
            $built     = $confirmed.Count + $wrong.Count

            [void]$lines.Add('')
            [void]$lines.Add(("  {0}" -f $title))
            [void]$lines.Add('  ------------------------------------------------------------------')
            [void]$lines.Add(("  episodes                       {0}" -f @($rows).Count))
            if (-not $isBaseline) {
                [void]$lines.Add(("  killed during refutation       {0}   (cheap saves - no fix was built)" -f $killed.Count))
            }
            [void]$lines.Add(("  fix built, problem went away   {0}" -f $confirmed.Count))
            $tail = if ($isBaseline) { '' } else { '   <- the number that judges the method' }
            [void]$lines.Add(("  fix built, problem REMAINED    {0}{1}" -f $wrong.Count, $tail))
            if (-not $isBaseline) {
                [void]$lines.Add(("  resolved, outside its radius   {0}   (fix grew past what the hypothesis covered; not in the hit rate)" -f $outRadius.Count))
            }
            if ($abandoned.Count) { [void]$lines.Add(("  abandoned                      {0}" -f $abandoned.Count)) }
            if ($unclosed.Count)  { [void]$lines.Add(("  still open                     {0}" -f $unclosed.Count)) }

            $prec = $null
            if ($built -gt 0) {
                $prec = [math]::Round(100.0 * $confirmed.Count / $built, 1)
                [void]$lines.Add('')
                [void]$lines.Add(("  Hit rate once a fix was built: {0}%  ({1} of {2})" -f $prec, $confirmed.Count, $built))
            }
            return [pscustomobject]@{
                Lines = $lines; Precision = $prec; Killed = $killed.Count
                Total = @($rows).Count; Built = $built
            }
        }

        $baseRows = @($log | Where-Object { $_.baseline -eq $true })
        $liveRows = @($log | Where-Object { $_.baseline -ne $true })

        Write-Output ''
        Write-Output '  FALSIFICATION SCORECARD  (rule 56)'

        $b = $null
        if (@($baseRows).Count) {
            $b = Get-Block $baseRows 'BASELINE - hypotheses acted on WITHOUT being attacked first' $true
            $b.Lines | ForEach-Object { Write-Output $_ }
        }
        $l = Get-Block $liveRows 'UNDER THE METHOD - hypotheses attacked before any fix was built' $false
        $l.Lines | ForEach-Object { Write-Output $_ }

        Write-Output ''
        Write-Output '  ------------------------------------------------------------------'
        if ($l.Built -eq 0) {
            Write-Output '  No hypothesis has yet survived refutation AND had a fix built, so the method has no'
            Write-Output '  hit rate of its own to report. Until it does the baseline stands unchallenged, and'
            Write-Output '  nothing here should be read as evidence that the method works.'
        } else {
            if ($null -ne $b -and $null -ne $b.Precision) {
                $delta = [math]::Round($l.Precision - $b.Precision, 1)
                $dir = if ($delta -ge 0) { 'ROSE' } else { 'FELL' }
                Write-Output ("  Hit rate {0} from {1}% to {2}% once hypotheses had to survive an attack first." -f $dir, $b.Precision, $l.Precision)
                if ($l.Built -lt 5) {
                    Write-Output ("  CAUTION: only {0} fix(es) built under the method - far too few to mean anything." -f $l.Built)
                    Write-Output '  Report it as a number, not as a result. Do not let a small sample argue for itself.'
                }
            }
            if ($l.Precision -lt 60) {
                Write-Output '  BELOW 60% - refutation is too soft. Hypotheses are passing that should not.'
                Write-Output '  Attack harder before building: name a cheaper discriminating test each time.'
            } elseif ($l.Precision -ge 80 -and $l.Built -ge 5) {
                Write-Output '  Surviving refutation is a strong signal here. The method is earning its cost.'
            }
        }

        $contested = @($log | Where-Object { $null -ne $_.contest })
        if ($contested.Count) {
            $advWin = @($contested | Where-Object { $_.contest.winner -eq 'advocate' }).Count
            $skpWin = @($contested | Where-Object { $_.contest.winner -eq 'skeptic'  }).Count
            $none   = @($contested | Where-Object { $_.contest.winner -eq 'neither'  }).Count
            Write-Output ''
            Write-Output '  DUAL-TRACK CONTESTS (rule 57)'
            Write-Output '  ------------------------------------------------------------------'
            Write-Output ("  advocate won   {0}    (hypothesis survived an independent attack)" -f $advWin)
            Write-Output ("  sceptic won    {0}    (killed before a fix was built)" -f $skpWin)
            Write-Output ("  neither        {0}    (evidence was insufficient - correctly refused)" -f $none)

            # Both extremes are failure signals, and they fail in opposite directions. A sceptic
            # that never loses means hypotheses are being formed too loosely to be worth testing;
            # an advocate that never loses means the sceptic is not really trying. Either way the
            # contest has stopped discriminating, which is the only thing it is for.
            if ($contested.Count -ge 6) {
                if ($skpWin -eq 0) {
                    Write-Output '  The sceptic has never won. Either hypotheses are unusually good, or - far more'
                    Write-Output '  likely - the sceptic track is not attacking hard enough to be worth running.'
                } elseif ($advWin -eq 0) {
                    Write-Output '  The advocate has never won. Hypotheses are reaching the contest under-formed;'
                    Write-Output '  spend longer on analysis before opening an episode.'
                }
                if ($none -eq 0) {
                    Write-Output '  "Neither" has never been returned. A judge that always picks a winner is not'
                    Write-Output '  judging - check that adjudication is genuinely allowed to refuse.'
                }
            }
        }

        if ($l.Killed -gt 0) {
            Write-Output ''
            Write-Output ("  {0} fix(es) were never built because the hypothesis died first. Each is a build-test" -f $l.Killed)
            Write-Output '  cycle not spent, and a version number not burned on a dysfunctional build (rule 48).'
            $rate = [math]::Round(100.0 * $l.Killed / [math]::Max(1, $l.Total), 1)
            Write-Output ("  Kill rate: {0}% of hypotheses did not survive their own author's attack." -f $rate)
            if ($rate -lt 15 -and $l.Total -ge 8) {
                Write-Output '  A very low kill rate usually means the attacks are gentle, not that the hypotheses'
                Write-Output '  are good. Genuine refutation kills a substantial share of its own ideas.'
            }
        }
        Write-Output ''
    }

    'list' {
        $rows = if ($Mod) { $log | Where-Object { $_.mod -eq $Mod } } else { $log }
        $rows | Sort-Object id | ForEach-Object {
            $mark = switch ($_.outcome) {
                'killed'       { 'KILLED   ' }
                'resolved'     { 'CONFIRMED' }
                'not-resolved' { 'FALSE    ' }
                'abandoned'    { 'ABANDONED' }
                'resolved-outside-radius' { 'OUTSIDE  ' }
                default        { 'OPEN     ' }
            }
            Write-Output ("{0,3}  {1}  {2}" -f $_.id, $mark, $_.hypothesis)
            if ($_.issue)    { Write-Output ("      issue:    {0}" -f $_.issue) }
            if ($_.kills)    { Write-Output ("      falsifier: {0}" -f $_.kills) }
            foreach ($a in @($_.attempts)) {
                Write-Output ("      test:     {0}  ->  {1} [{2}]" -f $a.test, $a.result, $a.verdict)
            }
            if ($_.evidence) { Write-Output ("      outcome:  {0}" -f $_.evidence) }
            Write-Output ''
        }
    }
}
