<#
.SYNOPSIS
    "Project optimization mode" - one sweep that runs every self-check this project has, reports
    what it found, and fixes only what is mechanical.

.DESCRIPTION
    the owner, 2026-08-27: "let's write a project optimization mode command that incorporates all the
    recent logic for optimization of the different parts of these directory."

    The checks already existed; they were just scattered across a dozen scripts that each had to be
    remembered and run by hand. A check nobody remembers to run is a check that does not exist, so
    this collects them behind one command.

    THE ONE DESIGN RULE: REPORT, FIX ONLY WHAT IS MECHANICAL
    -------------------------------------------------------
    Every section is either a FIX (deterministic, no judgement - a stale path, an unapplied icon)
    or a REPORT (a judgement call - is this gate rubber-stamping, is this backlog still real).
    Nothing in the second class is ever changed automatically, because a sweep that silently
    "optimises" a judgement call is how a pipeline loses information nobody noticed it had.

    This mirrors rule 58's own design: the gate ledger reports and refuses, it does not decide.

    WHAT IT WILL NOT DO
    -------------------
    * Never deletes anything (rule 50 - storage findings are recommendations, deletions need the owner).
    * Never rewrites a rule (rules 56/57 - reorganising something that works, on a tidiness
      argument, is the move those rules exist to discourage).
    * Never touches `PROGRESS.md` history. It is a chronological log; its repetition is the point.

.PARAMETER Apply
    Perform the mechanical fixes. Without it, everything is reported and nothing is written.

.PARAMETER Section
    Run one section only: staleness | rules | icons | gates | versions | storage | docs | health | events | skills

.EXAMPLE
    .\optimize-project.ps1                     # full sweep, read-only
    .\optimize-project.ps1 -Apply              # full sweep, mechanical fixes applied
    .\optimize-project.ps1 -Section gates      # just the judgement-gate scorecards
#>
[CmdletBinding()]
param(
    [string]$Root = $env:PIPELINE_ROOT,
    [switch]$Apply,
    # measure storage again instead of reusing the census cached within the last 12 hours (2026-10-27)
    [switch]$FreshStorage,
    [ValidateSet('staleness','rules','icons','gates','versions','storage','docs','health','events','skills','resolvers','tests')][string]$Section
)

$ErrorActionPreference = 'Continue'
if (-not $Root) { $_kitRoot = $PSScriptRoot; while ($_kitRoot -and (Split-Path $_kitRoot -Leaf) -ne '.MD') { $_kitRoot = Split-Path $_kitRoot -Parent }; if ($_kitRoot) { $_kitRoot = Split-Path $_kitRoot -Parent }; $Root = $_kitRoot }   # kit: <ROOT> is the folder above the .MD this script sits under, unless PIPELINE_ROOT says otherwise
$scripts = $PSScriptRoot
# Tools that moved into kind folders are found by role through this tree's resolver (rule 70), never by path.
$ResolverPy = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\resolvers\resolve.py'))
function Find-Role([string]$role) { return "$(@(& py -3 $ResolverPy find $role)[0])".Trim() }
$findings = New-Object System.Collections.ArrayList

function Head($n, $title, $kind) {
    Write-Output ''
    Write-Output ('=' * 78)
    Write-Output ("  {0}. {1}   [{2}]" -f $n, $title, $kind)
    Write-Output ('=' * 78)
}
function Note($sev, $text) {
    [void]$findings.Add([pscustomobject]@{ Severity = $sev; Text = $text })
}
function Run($label, $block) {
    # Every step is isolated: one section failing must never cost the sections after it. Anything
    # piping another script's output through Select-Object renders it with Out-String -Stream first
    # (a Format-* stream sliced by Select-Object throws at render time, outside this catch).
    try { & $block }
    catch { Write-Output ("  step failed: {0} - {1}" -f $label, $_.Exception.Message); Note 'ERROR' "$label failed" }
}
function Want($s) { return (-not $Section) -or ($Section -eq $s) }

Write-Output ''
Write-Output '  PROJECT OPTIMIZATION MODE'
Write-Output ("  {0}   mode: {1}" -f $Root, $(if ($Apply) { 'APPLY - mechanical fixes will be written' } else { 'REPORT ONLY - nothing will be written' }))

# ---------------------------------------------------------------------------------------------
if (Want 'staleness') {
    Head 1 'Stale path references' 'FIX'
    Run 'find-stale-paths' {
        $py = Join-Path $scripts 'find-stale-paths.py'
        if (Test-Path $py) {
            $env:PYTHONIOENCODING = 'utf-8'
            $out = & python $py 2>&1
            $out | ForEach-Object { Write-Output ("  {0}" -f $_) }
            if ($out -match '0 stale reference') { Note 'OK' 'no stale paths' }
            else { Note 'FIX' 'stale paths found - a folder was renamed and references were not updated' }
        } else { Write-Output '  find-stale-paths.py missing' }
    }
    Write-Output ''
    Write-Output '  Note: this catches renamed FOLDERS. It cannot catch a stale CLAIM about how a tool'
    Write-Output '  behaves, which is what actually cost this project weeks (LOGIC-LIBRARY entry 16).'
}

# ---------------------------------------------------------------------------------------------
if (Want 'rules') {
    Head 2 'Rules: amendment-by-reference, and version stamp' 'REPORT'
    Run 'rules-version' {
        & (Join-Path $scripts 'rules-version.ps1') -Action check
        if ($LASTEXITCODE -ne 0) { Note 'DECIDE' 'a rule amends another by reference - fold it in (see rule 56 discipline)' }
        else { Note 'OK' 'every rule states its own current policy' }
        & (Join-Path $scripts 'rules-version.ps1') -Action status
    }
}

# ---------------------------------------------------------------------------------------------
if (Want 'icons') {
    Head 3 'Folder icons (rule 55)' 'FIX'
    Run 'icon audit' {
        & (Find-Role 'set-folder-icons') -Audit
        if ($LASTEXITCODE -ne 0) {
            Note 'FIX' 'folders missing or not carrying their icon'
            if ($Apply) {
                Write-Output '  applying...'
                & (Find-Role 'set-folder-icons') | Out-String -Stream | Select-Object -Last 3
            }
        } else { Note 'OK' 'every structural folder carries its icon' }
    }
}

# ---------------------------------------------------------------------------------------------
if (Want 'gates') {
    Head 4 'Judgement gates - are they actually catching anything? (rules 56/57/58)' 'REPORT'
    Run 'gate-ledger' { & (Join-Path $scripts 'gate-ledger.ps1') -Action stats }
    Run 'falsification' { & (Join-Path $scripts 'falsification-log.ps1') -Action stats }
    Write-Output '  A gate that has never returned its negative verdict is indistinguishable from one'
    Write-Output '  that cannot. That is a judgement call, so it is reported and never auto-resolved.'
    Note 'DECIDE' 'review any gate flagged as never having returned its negative verdict'
}

# ---------------------------------------------------------------------------------------------
if (Want 'versions') {
    Head 5 'Version drift and test-build cap (rules 6/7/23/48)' 'FIX'
    Run 'prune' {
        # Splat a HASHTABLE, never an array: array splatting passes its elements as POSITIONAL
        # arguments, so @('-Root', $Root) bound the literal string '-Root' to prune's -Root and
        # the real path to -ModName. It then reported "7. current test builds not found at
        # -Root\7. current test builds" and the cap went unchecked on every sweep. And never name
        # a variable $args - it is the automatic argument array of the enclosing scriptblock.
        $pruneArgs = @{ Root = $Root }
        if ($Apply) { $pruneArgs['Apply'] = $true }
        & (Join-Path $scripts 'prune-test-builds.ps1') @pruneArgs | Out-String -Stream | Select-Object -Last 12
    }
    Run 'ledger' { & (Find-Role 'version-gate') -Action status | Out-String -Stream | Select-Object -Last 40 }
}

# ---------------------------------------------------------------------------------------------
if (Want 'docs') {
    Head 6 'Document redundancy' 'REPORT'
    Run 'docs' {
        $md = Join-Path $Root '.MD'
        $files = Get-ChildItem -LiteralPath $md -Filter '*.md' | Sort-Object Length -Descending
        Write-Output ("  {0} documents, {1:N0} KB total" -f $files.Count, (($files | Measure-Object Length -Sum).Sum / 1KB))
        Write-Output ''
        Write-Output '  largest:'
        $files | Select-Object -First 5 | ForEach-Object {
            Write-Output ("    {0,-34} {1,7:N0} KB   last touched {2}" -f $_.Name, ($_.Length / 1KB), $_.LastWriteTime.ToString('yyyy-MM-dd'))
        }
        # The logic library is navigated through its generated index, so a stale index is a
        # silently wrong map: each line number still points at a real line, saying something else.
        $idx = Join-Path $scripts 'logic-index.py'
        if (Test-Path -LiteralPath $idx) {
            $env:PYTHONIOENCODING = 'utf-8'
            $idxOut = & python $idx --check 2>&1
            Write-Output ''
            Write-Output ("  {0}" -f ($idxOut -join ' '))
            if ($LASTEXITCODE -ne 0) {
                Note 'FIX' 'PAST-MISTAKES-LIBRARY.md index is stale - run scripts\logic-index.py'
                if ($Apply) {
                    Write-Output '  regenerating...'
                    & python $idx | ForEach-Object { Write-Output ("  {0}" -f $_) }
                }
            }
        }

        # Files untouched for a fortnight are candidates for merging or retiring - not proof of
        # anything, since a settled decision document SHOULD stop changing.
        $stale = $files | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-14) }
        if ($stale) {
            Write-Output ''
            Write-Output '  untouched for 14+ days (candidates to merge or retire - check, do not assume):'
            $stale | ForEach-Object { Write-Output ("    {0,-34} {1}" -f $_.Name, $_.LastWriteTime.ToString('yyyy-MM-dd')) }
            Note 'DECIDE' ("{0} document(s) untouched for 14+ days" -f @($stale).Count)
        }
    }
}

# ---------------------------------------------------------------------------------------------
if (Want 'storage') {
    Head 7 'Storage (rule 50 - recommend, never delete)' 'REPORT'
    Run 'restore drill' {
        # Step 12.3 (2026-10-09): the off-machine copy is only proven by restoring it. Warn past 90 days.
        $drill = Join-Path $Root '.MD\state\last-restore-drill.txt'
        if (-not (Test-Path -LiteralPath $drill)) { Note 'REPORT' 'no restore drill recorded - clone the pipeline repo and run its checks (STEPS 12.3)' }
        else {
            $d = [datetime]::ParseExact(((Get-Content -LiteralPath $drill -TotalCount 1) -split '\s')[0], 'yyyy-MM-dd', $null)
            $age = [int]((Get-Date) - $d).TotalDays
            "    last restore drill: $($d.ToString('yyyy-MM-dd')) ($age days ago)"
            if ($age -gt 90) { Note 'REPORT' "the last restore drill was $age days ago - run it again (STEPS 12.3)" }
            else { Note 'OK' "restore drill $age days ago" }
        }
    }
    # THE STORAGE CENSUS IS CACHED (pipeline assessment tier 2 item 20, 2026-10-27): it took about eight of the read-only
    # run's ten-plus minutes. Its first lines are kept in .MD\state\storage-report-cache.txt and reused for 12 hours;
    # -FreshStorage measures again. (The census writes its own history file anyway; the cache is beside it in state.)
    Run 'storage' {
        $cache = if ($env:OPTIMIZE_STORAGE_CACHE) { $env:OPTIMIZE_STORAGE_CACHE } else { Join-Path $Root '.MD\state\storage-report-cache.txt' }
        $ageH = if (Test-Path -LiteralPath $cache) { ((Get-Date) - (Get-Item -LiteralPath $cache).LastWriteTime).TotalHours } else { [double]::MaxValue }
        if (-not $FreshStorage -and $ageH -lt 12) {
            "    (storage census from the cache, {0:N1} h old - -FreshStorage measures again)" -f $ageH
            Get-Content -LiteralPath $cache -Encoding UTF8
        } else {
            $out = @(& (Find-Role 'storage-report') -SkipProject | Out-String -Stream | Select-Object -First 18)
            try {
                New-Item -ItemType Directory -Force -Path (Split-Path $cache -Parent) | Out-Null
                Set-Content -LiteralPath $cache -Value $out -Encoding UTF8
            } catch { "    (the storage cache could not be written: $($_.Exception.Message))" }
            $out
        }
    }
    Note 'DECIDE' 'storage reclaim needs the owner approval per deletion (rule 50)'
}

# ---------------------------------------------------------------------------------------------
if (Want 'health') {
    Head 8 'Machine health (rule 53)' 'REPORT'
    Run 'health' { & (Find-Role 'health-gate') -Operation any | Out-String -Stream | Select-Object -First 14 }
}

# ---------------------------------------------------------------------------------------------
if (Want 'events') {
    Head 9 'Pipeline event log - what each stage has actually recorded' 'REPORT'
    Run 'events' {
        & (Join-Path $scripts 'pipeline-log.ps1') -Action summary | Out-String -Stream
        Note 'DECIDE' 'any stage reporting NO EVENTS is either idle or not wired to record - check which'
    }
}

# ---------------------------------------------------------------------------------------------
if (Want 'skills') {
    # The owner, 2026-10-08: flag what we keep doing by hand as skill-worthy. A judgement, so REPORT only - the scout
    # never writes a skill; each candidate is made into one or put in skill-scout-ignore.txt with the reason.
    Head 10 'Skill candidates - procedures repeated across sessions that no skill covers' 'REPORT'
    Run 'skills' {
        $env:PYTHONIOENCODING = 'utf-8'
        & python -I (Join-Path $scripts 'skill-scout.py') | Out-String -Stream | Select-Object -First 12
        Note 'DECIDE' 'skill candidates in .MD\logs\skill-scout.md - make a skill or add to skill-scout-ignore.txt'
    }
    # 2026-11-18: a lesson the library held three times was repeated a fourth - the third entry is the trigger for a
    # gate. REPORT the subject terms in 3+ headings that no gate names (repeated-lesson-scan; a cluster is read, never
    # gated blindly: gate it, or put it in repeated-lesson-scan-ignore.txt with why).
    Run 'repeated lessons' {
        $env:PYTHONIOENCODING = 'utf-8'
        & python -I (Join-Path $scripts 'repeated-lesson-scan.py') | Out-String -Stream | Where-Object { $_ -notmatch '^\s+- ' } | Select-Object -First 20
        Note 'DECIDE' 'each NO GATE term: a gate row / hook, or a line in scripts\repeated-lesson-scan-ignore.txt'
    }
}

# ---------------------------------------------------------------------------------------------
if (Want 'resolvers') {
    Head 11 'Resolvers - every roster role resolves, every caller names a defined role' 'FIX'
    Run 'resolver check' {
        $env:PYTHONIOENCODING = 'utf-8'
        & py -3 (Join-Path $Root '.MD\resolvers\resolve.py') check --callers 2>&1 | Out-String -Stream | Select-Object -First 40
        if ($LASTEXITCODE -ne 0) { Note 'FIX' 'a roster role is missing, ambiguous or archived, or a caller names an undefined role' }
        else { Note 'OK' 'every role resolves and every caller names a defined role' }
    }
    Run 'hooks render check' {
        & py -3 (Join-Path $Root '.MD\resolvers\render-hooks.py') --check 2>&1 | Out-String -Stream | Select-Object -First 10
        if ($LASTEXITCODE -ne 0) { Note 'FIX' 'settings.json hooks differ from what the rosters render - render-hooks.py --apply' }
        else { Note 'OK' 'hooks match the rosters' }
    }
    Run 'skills linked' {
        # One copy of the skills (step 7.7, 2026-10-09): every folder in the home skills folder is a junction into .MD\skills,
        # and every .MD skill has one - a skill made in one place only is a second copy waiting to drift.
        $skillHome = Join-Path $env:USERPROFILE '.claude\skills'; $md = Join-Path $Root '.MD\skills'; $bad = @()
        foreach ($d in @(Get-ChildItem -LiteralPath $skillHome -Directory -Force | Where-Object Name -ne 'synced')) {
            if ($d.LinkType -ne 'Junction' -or (($d.Target -join '') -ne (Join-Path $md $d.Name))) { $bad += "$($d.Name): not a junction into .MD\skills" }
        }
        foreach ($d in @(Get-ChildItem -LiteralPath $md -Directory)) {
            if (-not (Test-Path -LiteralPath (Join-Path $skillHome $d.Name))) { $bad += "$($d.Name): no junction in the home skills folder" }
        }
        $bad | ForEach-Object { "    $_" }
        if ($bad.Count) { Note 'FIX' 'a skill exists in one place only - make the home folder entry a junction into .MD\skills' }
        else { Note 'OK' 'every skill is one copy (.MD\skills, junctioned into the home folder)' }
    }
    Run 'environment line check' {
        & py -3 (Join-Path $Root '.MD\resolvers\render-preamble.py') --check 2>&1 | Out-String -Stream | Select-Object -First 10
        if ($LASTEXITCODE -ne 0) { Note 'FIX' 'the sub-agent environment line is stale - paste render-preamble.py --print between the ENV markers (STEPS.md PREAMBLE, sub-agent-routing.md)' }
        else { Note 'OK' 'the sub-agent environment line matches the rosters' }
    }
    Run 'memory index' {
        & py -3 (Join-Path $Root '.MD\scripts\memory-index.py') --check 2>&1 | Out-String -Stream | Select-Object -First 20
        if ($LASTEXITCODE -ne 0) { Note 'FIX' 'memory index stale, a memory without topics, or a possible duplicate - memory-index.py --build, or resolve the pair' }
        else { Note 'OK' 'memory index current, every memory tagged' }
    }
    Run 'home indexes' {
        $env:PYTHONIOENCODING = 'utf-8'
        foreach ($h in @(@('docs-archive', (Join-Path $Root '.MD\docs-archive')), @('handoffs', (Join-Path $Root '.MD\handoffs')))) {
            & py -3 (Join-Path $scripts 'home-index.py') --dir $h[1] --check 2>&1 | Out-String -Stream | Select-Object -First 3
            if ($LASTEXITCODE -ne 0) { Note 'FIX' ("{0}\INDEX.md is stale or missing - home-index.py --build" -f $h[0]) }
        }
        & py -3 (Join-Path $Root '.MD\resolvers\resolve.py') index --check 2>&1 | Out-String -Stream | Select-Object -First 3
        if ($LASTEXITCODE -ne 0) { Note 'FIX' 'resolvers\INDEX.md is stale or missing - resolve.py index --build' }
        & py -3 (Join-Path $scripts 'gate-rules-index.py') --check 2>&1 | Out-String -Stream | Select-Object -First 3
        if ($LASTEXITCODE -ne 0) { Note 'FIX' 'gate-rules-INDEX.md is stale or missing - gate-rules-index.py --build' }
        & py -3 (Join-Path $scripts 'todo-view.py') --check 2>&1 | Out-String -Stream | Select-Object -First 3
        if ($LASTEXITCODE -ne 0) { Note 'FIX' 'to-do VIEW.md is stale or missing - todo-view.py --build' }
        if (-not ($findings | Where-Object { $_.Severity -eq 'FIX' -and $_.Text -match 'INDEX|VIEW' })) { Note 'OK' 'every single home is indexed and current' }
    }
}

# ---------------------------------------------------------------------------------------------
if (Want 'tests') {
    Head 12 'Tests - every test under scripts\tests and resolvers\tests passes' 'FIX'
    Run 'run-all tests' {
        & py -3 (Join-Path $Root '.MD\scripts\tests\run-all.py') 2>&1 | Out-String -Stream | Select-Object -Last 8
        if ($LASTEXITCODE -ne 0) { Note 'FIX' 'a test failed - python .MD\scripts\tests\run-all.py names it; fix the cause, or re-record with test_golden_tools.py --record only when the output change is intended' }
        else { Note 'OK' 'every test passes' }
    }
}

# ---------------------------------------------------------------------------------------------
Write-Output ''
Write-Output ('=' * 78)
Write-Output '  SUMMARY'
Write-Output ('=' * 78)
foreach ($g in @('ERROR','FIX','DECIDE','OK')) {
    $rows = @($findings | Where-Object { $_.Severity -eq $g })
    if (-not $rows.Count) { continue }
    Write-Output ''
    Write-Output ("  {0}:" -f $g)
    $rows | ForEach-Object { Write-Output ("    - {0}" -f $_.Text) }
}
Write-Output ''
if (-not $Apply) {
    Write-Output '  Read-only. Re-run with -Apply to perform the mechanical fixes (FIX items only).'
    Write-Output '  DECIDE items are never applied automatically - they need a judgement call.'
}
Write-Output ''
