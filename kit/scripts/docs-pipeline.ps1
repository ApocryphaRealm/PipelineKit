<#
.SYNOPSIS
    Runs the .MD documents through the same pipeline the mods go through - versioning, a
    compatibility gate, and a version that has to be earned (rule 60).

.DESCRIPTION
    the owner, 2026-08-27: "let's apply the same versioning logic from the mods, and let's treat the
    version MD files the same way we would treat the mods - as in analysis, planning,
    compatibility and so on... treat the pipeline like the game and the rules as a mod to
    optimize the pipeline functionality."

    THE MAPPING
    -----------
      the game (Skyrim)              ->  the pipeline itself
      a mod (DLL + INI)              ->  a document that GOVERNS how the pipeline behaves
      a build that compiles          ->  an edit that passes `check`
      7. current test builds         ->  a revision that passes checks but has not been used yet
      8. confirm compatibility       ->  does this document contradict another one?
      "observed working in game"     ->  the pipeline actually ran under it and behaved correctly
      10. finalized mods             ->  a stamped, archived revision
      12. needs an update            ->  the document has drifted from what the project does

    WHICH DOCUMENTS ARE "MODS", AND WHICH ARE NOT
    ---------------------------------------------
    This is the one place the analogy has to be held rather than followed, and getting it wrong
    would manufacture ceremony:

      GOVERNING documents behave like mods. They change what the pipeline DOES, so a change to one
      changes behaviour, and behaviour changes deserve a version, a compatibility check and an
      archived predecessor.

      RECORD documents behave like SAVES. `PROGRESS.md` is a chronological log; `STORAGE-FINDINGS`
      and the research files record what was observed at a point in time. Versioning a log is
      meaningless - it is append-only by nature, every append is "correct", and there is nothing a
      compatibility gate could even check. Git already gives them history, which is all they need.

    So `check` and `bump` apply to the governing set only. Records are listed for completeness and
    explicitly marked as out of scope.

.PARAMETER Action
    status | check | bump

.EXAMPLE
    .\docs-pipeline.ps1 -Action status
    .\docs-pipeline.ps1 -Action check
    .\docs-pipeline.ps1 -Action bump -Doc FALSIFICATION-MODE.md -Note "added the adjudication rules"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet('status','check','bump')][string]$Action,
    [string]$Doc,
    [ValidateSet('major','minor','build')][string]$Level = 'build',
    [string]$Note,
    [switch]$Force
)

$ErrorActionPreference = 'Continue'
$md      = Split-Path $PSScriptRoot -Parent
$archive = Join-Path $md 'docs-archive'
$marker  = '<!-- DOC-VERSION:'

# A GOVERNING entry is one of (step 10.1):
#   a bare name                      a file at the .MD root                 (CLAUDE.md)
#   a path relative to .MD           with subfolders                        (resolvers\rosters\stages.json)
#   an absolute path                 anywhere                               (<ROOT>\4. plans\x\STEPS.md)
# The version marker depends on the extension:
#   .md    <!-- DOC-VERSION: X.Y.Z | yyyy-mm-dd -->   (within the first 14 lines)
#   .json  top-level "_version": "X.Y.Z" and "_revised": "yyyy-mm-dd" as the first keys;
#          read and rewritten BY REGEX on those two values only - the file is never re-serialised.
#   .txt   first line  # DOC-VERSION: X.Y.Z | yyyy-mm-dd
# TEST OVERRIDE: when the environment variable DOCS_PIPELINE_GOVERNING_OVERRIDE names a file, that file
# (one entry per line, blank lines and lines starting # ignored) REPLACES $GOVERNING, the RECORDS list
# and the rule-parts scan are emptied, and the archive is the 'docs-archive' folder NEXT TO THAT FILE.
# Unset (the normal case) it changes nothing. It exists only for the fixture self-test.
$overrideFile = $env:DOCS_PIPELINE_GOVERNING_OVERRIDE
$overrideOn   = [bool]$overrideFile

# GOVERNING - these change what the pipeline does. Treated as mods.
$GOVERNING = @(
    'CLAUDE.md'                    # the rules themselves - versioned by rules-version.ps1
    'commands.md'
    'TRIAGE-CATEGORIES.md'
    'MODLIST-METHODOLOGY.md'       # Wabbajack list-building methodology (the owner, 2026-09-10)
    'MACHINE-HEALTH.md'
    'PAST-MISTAKES-LIBRARY.md'
    'LOGIC-LIBRARY.md'             # the catalogue of pipeline logics (step 9.2, 2026-10-09)
    'RESOURCES.md'
    'PREFLIGHT.md'                 # read at every session start and applied at the moment of implementing (2026-09-19)
    'resolvers\rosters\stages.json'    # the resolver rosters (step 1.3, 2026-10-09): a changed role moves a caller
    'resolvers\rosters\data.json'
    'resolvers\rosters\tools.json'
    'resolvers\rosters\external.json'
    'resolvers\rosters\identity.json'  # one value per public fact (step 12.7, 2026-10-09)
    'resolvers\rosters\policy.json'    # one value per policy number (step 12.7)
    'resolvers\rosters\scripts.json'      # roles of the scripts moved into the kind folders (Phase 5)
    # Step 10.2 (2026-10-09): every remaining single home. Out-of-.MD homes are absolute entries (step 10.1).
    'scripts\gate-rules.json'
    'sub-agent-routing.md'
    # BANNED-WORDS.md became a pointer to the always-on memory conversation-rules on 2026-10-12 (memories are not versioned)
    'DEFAULT-KEYS.md'
)

# RECORDS - logs and point-in-time findings. Out of scope, deliberately.
$RECORDS = @(
    'PROGRESS.md'
    'VCPKG-SHARED-CACHE.md'    # AUTOMATION-BACKLOG, CRASH-LOGGER-CHOICE and VERSION-RECONCILIATION archived 2026-10-12 (SIMPLIFY-4)
    'skills\nexus-page\references\FRAMEWORK-LICENCE-AND-CREDITS.md','secrets.md'   # moved into the skill 2026-10-12
)

if ($overrideOn) {
    if (-not (Test-Path -LiteralPath $overrideFile)) { Write-Output "FAILED: DOCS_PIPELINE_GOVERNING_OVERRIDE names a missing file: $overrideFile"; exit 1 }
    $GOVERNING = @([System.IO.File]::ReadAllLines($overrideFile) | ForEach-Object { $_.Trim() } | Where-Object { $_ -and -not $_.StartsWith('#') })
    $RECORDS   = @()
    $archive   = Join-Path (Split-Path (Resolve-Path -LiteralPath $overrideFile).Path -Parent) 'docs-archive'
}

# Project constants with ONE canonical value. Two documents disagreeing about one of these is the
# document equivalent of two mods fighting over the same record - which is exactly what stage 8
# exists to catch.
# Step 12.8 (2026-10-09): the list is NOT hard-coded any more. Every role of kind "value" that carries a "pattern" in
# .MD\resolvers\rosters\identity.json and policy.json is a tracked constant: its "value" is the canon, its "pattern" finds
# the places that state it. A role without a pattern is a fact, not a tracked constant. When the pattern's capture is
# shorter than the value (members captures "YOUR-NEXUS-NAME", chat-invite the code), the capture is compared with the
# part of the value after its last "/".
function Get-TrackedConstants {
    $out = @()
    foreach ($rf in 'identity.json', 'policy.json') {
        $rp = Join-Path $md ('resolvers\rosters\' + $rf)
        if (-not (Test-Path -LiteralPath $rp)) { continue }
        $roster = [System.IO.File]::ReadAllText($rp) | ConvertFrom-Json
        foreach ($role in $roster.roles.PSObject.Properties) {
            $r = $role.Value
            if ($r.kind -eq 'value' -and $r.pattern) {
                $canon = [string]$r.value
                $canonCap = if ($canon -match '/') { ($canon -split '/')[-1] } else { $canon }
                $out += @{ Name = $role.Name; Canon = $canon; CanonCap = $canonCap; Pattern = [string]$r.pattern; Roster = $rf }
            }
        }
    }
    return $out
}

# ---------------------------------------------------------------------------------------------
# ENCODING. Do NOT use Get-Content/Set-Content on these documents.
#
# PowerShell 5.1's Get-Content reads a BOM-less UTF-8 file as cp1252, so every multi-byte
# character (em dashes, arrows, degree signs) is split into several single-byte ones; Set-Content
# then writes those back out as UTF-8 and the damage is permanent. This silently mangled CLAUDE.md
# and FALSIFICATION-MODE.md the first time these scripts ran - 32 and 24 corrupted sequences
# respectively - and nothing reported an error, because from PowerShell's point of view nothing
# went wrong.
#
# .NET's File.ReadAllLines/WriteAllLines default to UTF-8 and do not have this behaviour. The
# explicit UTF8Encoding($false) suppresses the BOM, matching how these files are already stored.
# ---------------------------------------------------------------------------------------------
function Read-Utf8Lines($path) {
    return [System.IO.File]::ReadAllLines($path)
}
function Write-Utf8Lines($path, $lines) {
    # Keep the file's own line endings (2026-10-09): WriteAllLines always writes CRLF, so a stamp turned an LF file
    # into CRLF and every line showed as changed (RESOURCES.md 1.0.2, LOGIC-LIBRARY.md 1.0.1).
    $enc = New-Object System.Text.UTF8Encoding($false)
    $eol = "`r`n"
    if (Test-Path -LiteralPath $path) {
        $old = [System.IO.File]::ReadAllText($path)
        if ($old.Contains("`n") -and -not $old.Contains("`r`n")) { $eol = "`n" }
    }
    [System.IO.File]::WriteAllText($path, (([string[]]$lines -join $eol) + $eol), $enc)
}
function Read-Utf8Text($path) {
    return [System.IO.File]::ReadAllText($path)
}

function Step-Version($maj, $min, $bld, $level) {
    # Rule 6, SEMANTIC VERSIONING (2026-10-21), shared by the mods and the documents: -Level build is a PATCH step
    # (1.0.9 -> 1.0.10, no roll-over), minor resets the third number, major resets both. ALL THREE levels take their
    # arithmetic from version-gate.ps1 (nextnumber -Kind) and nowhere else - the 2026-10-12 lesson (rules 2.10.0): a
    # collapse to one tool is finished only when every branch calls it.
    $kind = switch ($level) { 'major' { 'major' } 'minor' { 'minor' } default { 'patch' } }
    $vg = "$(@(& py -3 (Join-Path $PSScriptRoot '..\resolvers\resolve.py') find version-gate)[0])".Trim()   # by role (rule 70)
    $n = & $vg -Action nextnumber -From ('{0}.{1}.{2}' -f $maj, $min, $bld) -Kind $kind
    if ($LASTEXITCODE -ne 0 -or -not $n) { throw "version-gate.ps1 refused to step $maj.$min.$bld ($kind): $n" }
    $pv = [version]("$n".Trim())
    return @($pv.Major, $pv.Minor, $pv.Build)
}

function Resolve-DocPath($entry) {
    if ([System.IO.Path]::IsPathRooted($entry)) { return $entry }
    return (Join-Path $md $entry)
}

# One regex per marker kind, kept in one place so reader and writer agree.
$jsonVerRx = [regex]'("_version"\s*:\s*")(\d+)\.(\d+)\.(\d+)(")'
$jsonRevRx = [regex]'("_revised"\s*:\s*")([^"]*)(")'

function Get-DocVersion($path) {
    $ext = [System.IO.Path]::GetExtension($path).ToLowerInvariant()
    if ($ext -eq '.json') {
        $t = Read-Utf8Text $path
        $head = $t.Substring(0, [Math]::Min(600, $t.Length))   # "as its first keys"
        $m = $jsonVerRx.Match($head)
        if ($m.Success) { return [pscustomobject]@{ Major = [int]$m.Groups[2].Value; Minor = [int]$m.Groups[3].Value; Build = [int]$m.Groups[4].Value } }
        return $null
    }
    if ($ext -eq '.txt') {
        $first = @(Read-Utf8Lines $path | Select-Object -First 1)
        if ($first.Count -and $first[0] -match '^\s*#\s*DOC-VERSION:\s*(\d+)\.(\d+)\.(\d+)') {
            return [pscustomobject]@{ Major = [int]$Matches[1]; Minor = [int]$Matches[2]; Build = [int]$Matches[3] }
        }
        return $null
    }
    $head = (Read-Utf8Lines $path) | Select-Object -First 14
    $line = $head | Where-Object { $_ -like "$marker*" -or $_ -like '<!-- RULES-VERSION:*' } | Select-Object -First 1
    if ($line -and $line -match 'VERSION:\s*(\d+)\.(\d+)\.(\d+)') {
        return [pscustomobject]@{ Major = [int]$Matches[1]; Minor = [int]$Matches[2]; Build = [int]$Matches[3] }
    }
    return $null
}

# Stamp a .json or .txt file. .md is stamped by the original code in the bump branch.
function Set-NonMdStamp($path, $ext, $ver, $today) {
    $bytes  = [System.IO.File]::ReadAllBytes($path)
    $hasBom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
    $t      = [System.IO.File]::ReadAllText($path)          # strips a BOM
    $eol    = if ($t.Contains("`r`n")) { "`r`n" } else { "`n" }
    if ($ext -eq '.json') {
        if ($jsonVerRx.Match($t).Success) {
            # Already stamped: rewrite the two VALUES only, nothing else is touched.
            $t = $jsonVerRx.Replace($t, ('${1}' + $ver + '${5}'), 1)
            if ($jsonRevRx.Match($t).Success) { $t = $jsonRevRx.Replace($t, ('${1}' + $today + '${3}'), 1) }
        } else {
            $m = [regex]::Match($t, '^\s*\{')
            if (-not $m.Success) { throw "$path does not start with a JSON object" }
            $pos   = $m.Index + $m.Length
            $rest  = $t.Substring($pos)
            $empty = $rest -match '^\s*\}'
            $comma = if ($empty) { '' } else { ',' }
            $nl    = [regex]::Match($rest, '^[ \t]*\r?\n')
            if ($nl.Success) {
                $at  = $pos + $nl.Length
                $ins = ('  "_version": "{0}",{2}  "_revised": "{1}"{3}{2}' -f $ver, $today, $eol, $comma)
            } else {
                $at  = $pos
                $ins = ('{2}  "_version": "{0}",{2}  "_revised": "{1}"{3}{2}' -f $ver, $today, $eol, $comma)
            }
            $t = $t.Substring(0, $at) + $ins + $t.Substring($at)
        }
    } else {
        $stampLine = "# DOC-VERSION: $ver | $today"
        $body = [regex]::Replace($t, '^[ \t]*#\s*DOC-VERSION:[^\r\n]*(\r?\n|$)', '')
        $t = $stampLine + $eol + $body
    }
    [System.IO.File]::WriteAllText($path, $t, (New-Object System.Text.UTF8Encoding($hasBom -and $ext -eq '.json')))
}

switch ($Action) {

    'status' {
        Write-Output ''
        Write-Output '  DOCUMENT PIPELINE (rule 60) - governing documents are treated as mods'
        Write-Output ('  ' + ('-' * 76))
        Write-Output ('  {0,-34} {1,-8} {2,-12} {3}' -f 'DOCUMENT', 'VERSION', 'REVISED', 'SIZE')
        foreach ($d in $GOVERNING) {
            $p = Resolve-DocPath $d
            if (-not (Test-Path -LiteralPath $p)) { Write-Output ('  {0,-34} MISSING' -f $d); continue }
            $v = Get-DocVersion $p
            $f = Get-Item -LiteralPath $p
            $vs = if ($v) { "v$($v.Major).$($v.Minor).$($v.Build)" } else { 'UNSTAMPED' }
            Write-Output ('  {0,-34} {1,-8} {2,-12} {3,7:N0} KB' -f $d, $vs, $f.LastWriteTime.ToString('MM-dd'), ($f.Length / 1KB))
        }
        if ($RECORDS.Count) {
        Write-Output ''
        Write-Output '  RECORDS - logs and point-in-time findings. NOT versioned, deliberately:'
        Write-Output '  a log is append-only, every append is correct by construction, and there is'
        Write-Output '  nothing a compatibility gate could check. Git already gives them history.'
        }
        $shown = 0
        foreach ($d in $RECORDS) {
            $p = Join-Path $md $d
            if ((Test-Path -LiteralPath $p) -and $shown -lt 6) {
                Write-Output ('      {0}' -f $d); $shown++
            }
        }
        if ($RECORDS.Count -gt $shown) { Write-Output ('      ... and {0} more' -f ($RECORDS.Count - $shown)) }
        Write-Output ''
    }

    'check' {
        $problems = 0
        $text = @{}
        foreach ($d in $GOVERNING) {
            $p = Resolve-DocPath $d
            if (Test-Path -LiteralPath $p) { $text[$d] = Read-Utf8Text $p }
        }
        foreach ($d in $RECORDS) {
            $p = Join-Path $md $d
            if (Test-Path -LiteralPath $p) { $text[$d] = Read-Utf8Text $p }
        }
        # The seven rule parts (.MD\rules\) are checked as part of CLAUDE.md: they carry the rule text,
        # CLAUDE.md carries the stamp for the set (rules-version.ps1).
        $partsDir = Join-Path $md 'rules'
        $partFiles = if ($overrideOn) { @() } else { @(Get-ChildItem -LiteralPath $partsDir -Filter '*.md' -ErrorAction SilentlyContinue | Sort-Object Name) }
        foreach ($pf in $partFiles) {
            $text['rules\' + $pf.Name] = Read-Utf8Text $pf.FullName
        }

        # --- 1. broken rule references: pointing at a rule that does not exist -------------
        Write-Output ''
        Write-Output '  1. RULE REFERENCES'
        $rulesText = ($text.Keys | Where-Object { $_ -eq 'CLAUDE.md' -or $_ -like 'rules\*' } | ForEach-Object { $text[$_] }) -join "`n"
        $existing = @{}
        foreach ($m in [regex]::Matches($rulesText, '(?m)^## (\d+)\.')) { $existing[[int]$m.Groups[1].Value] = $true }
        $maxRule = ($existing.Keys | Measure-Object -Maximum).Maximum
        $broken = @()
        # A plan document (under '4. plans\') is governed for versioning but skips items 1 and 2: it names the files it
        # will create and the ones it retires, and quotes rule numbers from records (step 10.2, 2026-10-09).
        $isPlan = { param($doc) $doc -like '*\4. plans\*' }
        foreach ($d in $text.Keys) {
            if (& $isPlan $d) { continue }
            foreach ($m in [regex]::Matches($text[$d], '(?i)\brule\s+(\d+)\b')) {
                $n = [int]$m.Groups[1].Value
                if (-not $existing.ContainsKey($n)) { $broken += ('{0}: rule {1}' -f $d, $n) }
            }
        }
        if ($broken.Count) {
            $problems++
            Write-Output ('     BROKEN - {0} reference(s) to a rule that does not exist (highest is {1}):' -f $broken.Count, $maxRule)
            $broken | Sort-Object -Unique | Select-Object -First 10 | ForEach-Object { Write-Output ("       {0}" -f $_) }
        } else {
            if ($maxRule) { Write-Output ('     OK - every "rule N" reference resolves (1..{0})' -f $maxRule) }
            else { Write-Output '     OK - no "rule N" references in this set' }
        }

        # --- 2. broken file references ----------------------------------------------------
        Write-Output ''
        Write-Output '  2. FILE REFERENCES'
        $missing = @()
        foreach ($d in $text.Keys) {
            if (& $isPlan $d) { continue }
            foreach ($m in [regex]::Matches($text[$d], '(?i)(?:\.MD\\|scripts\\)([A-Za-z0-9._-]+\.(?:md|ps1|py|json))')) {
                $name = $m.Groups[1].Value
                $hit = @(Get-ChildItem -LiteralPath $md -Recurse -Filter $name -ErrorAction SilentlyContinue)
                if (-not $hit.Count) { $missing += ('{0}: {1}' -f $d, $name) }
            }
        }
        if ($missing.Count) {
            $problems++
            Write-Output ('     BROKEN - {0} reference(s) to a file that does not exist:' -f $missing.Count)
            $missing | Sort-Object -Unique | Select-Object -First 10 | ForEach-Object { Write-Output ("       {0}" -f $_) }
        } else {
            Write-Output '     OK - every referenced .md/.ps1/.py/.json exists'
        }

        # --- 3. COMPATIBILITY: two documents disagreeing about one constant ---------------
        Write-Output ''
        Write-Output '  3. COMPATIBILITY - do two documents contradict each other on a project constant?'
        $conflict = 0
        # Scope: the governing documents, the rule parts and the skill files - not the records (step 12.8).
        $cText = [ordered]@{}
        foreach ($d in $text.Keys) { if ($RECORDS -notcontains $d) { $cText[$d] = $text[$d] } }
        if (-not $overrideOn) {
            foreach ($sf in @(Get-ChildItem -LiteralPath (Join-Path $md 'skills') -Filter 'SKILL.md' -Recurse -ErrorAction SilentlyContinue | Sort-Object FullName)) {
                $cText['skills\' + $sf.Directory.Name + '\SKILL.md'] = Read-Utf8Text $sf.FullName
            }
        }
        foreach ($c in (Get-TrackedConstants)) {
            $drift = @()
            foreach ($d in $cText.Keys) {
                $txt = $cText[$d]
                foreach ($m in [regex]::Matches($txt, $c.Pattern)) {
                    for ($g = 1; $g -lt $m.Groups.Count; $g++) {
                        $val = $m.Groups[$g].Value
                        if ($val -and $val -ne $c.CanonCap -and $val -ne $c.Canon) {
                            $line = $txt.Substring(0, $m.Groups[$g].Index).Split("`n").Count
                            $drift += [pscustomobject]@{ File = $d; Line = $line; Value = $val }
                        }
                    }
                }
            }
            if ($drift.Count) {
                $conflict++
                Write-Output ('     CONFLICT - {0}: canonical is {1} ({2}), but {3} place(s) state another value' -f $c.Name, $c.Canon, $c.Roster, $drift.Count)
                foreach ($x in $drift) { Write-Output ('         {0}:{1}  states {2}' -f $x.File, $x.Line, $x.Value) }
            }
        }
        if (-not $conflict) { Write-Output '     OK - no document contradicts another on a tracked constant' }
        else { $problems++ }

        # --- 4. unstamped governing documents ---------------------------------------------
        Write-Output ''
        Write-Output '  4. VERSION STAMPS'
        $unstamped = @()
        foreach ($d in $GOVERNING) {
            $p = Resolve-DocPath $d
            if ((Test-Path -LiteralPath $p) -and -not (Get-DocVersion $p)) { $unstamped += $d }
        }
        if ($unstamped.Count) {
            Write-Output ('     {0} governing document(s) carry no version marker:' -f $unstamped.Count)
            $unstamped | ForEach-Object { Write-Output ("       {0}" -f $_) }
            Write-Output '     Stamp with: docs-pipeline.ps1 -Action bump -Doc <name> -Note "..."'
        } else {
            Write-Output '     OK - every governing document is stamped'
        }

        # --- 5. plan documents open with the verified present and name their measurement (step 12.14) ----
        # Applies ONLY to governing entries under '4. plans\'. Needs "State today" (heading or bold label) within the
        # first 40 lines and a "Measured" label anywhere. The check looks for the labels; the main session reads the content.
        # Plans that predate the rule (named in $planGrandfathered) are WARN until $planWarnUntil, then FAIL. WARN is not a problem area.
        $planAcceptance = [datetime]'2026-10-09'            # the acceptance date of step 12.14
        $planWarnUntil  = $planAcceptance.AddDays(30)       # 2026-11-08; after this date a grandfathered plan FAILs too
        $planGrandfathered = @('PLAN.md', 'STEPS.md', 'LOGIC-LIBRARY-SEED.md')
        Write-Output ''
        Write-Output '  5. PLAN DOCUMENTS - "State today" and "Measured"'
        $planFail = 0; $planWarn = 0; $planSeen = 0
        $labelPre = '^\s*(?:#{1,6}\s*)?(?:\*\*|__)?\s*'
        foreach ($d in $GOVERNING) {
            if (-not (& $isPlan $d)) { continue }
            $p = Resolve-DocPath $d
            if (-not (Test-Path -LiteralPath $p)) { continue }
            $planSeen++
            $pl = @(Read-Utf8Lines $p)
            $leaf = Split-Path $p -Leaf
            $planLevel = if (($planGrandfathered -contains $leaf) -and ((Get-Date) -le $planWarnUntil)) { 'WARN' } else { 'FAIL' }
            $msgs = @()
            if (-not (@($pl | Select-Object -First 40) -match ($labelPre + 'State today')).Count) { $msgs += 'no "State today" within the first 40 lines' }
            $mLines = @($pl -match ($labelPre + 'Measured'))
            if (-not $mLines.Count) { $msgs += 'no "Measured" section' }
            elseif (@($mLines -match 'Measured:\s*nothing yet - a thought experiment').Count) {
                Write-Output ('     NOTE  {0}: Measured: nothing yet - a thought experiment' -f $leaf)
            }
            if ($msgs.Count) {
                foreach ($m in $msgs) { Write-Output ('     {0}  {1}: {2}' -f $planLevel, $leaf, $m) }
                if ($planLevel -eq 'FAIL') { $planFail++ } else { $planWarn++ }
            } else {
                Write-Output ('     OK    {0}' -f $leaf)
            }
        }
        if ($planFail) { $problems++ }
        elseif ($planWarn) { Write-Output ('     {0} plan(s) predate the rule: WARN until {1}, then FAIL' -f $planWarn, $planWarnUntil.ToString('yyyy-MM-dd')) }
        elseif (-not $planSeen) { Write-Output '     OK - no plan documents in this set' }

        Write-Output ''
        if ($problems) { Write-Output ("  {0} problem area(s) found." -f $problems); exit 1 }
        Write-Output '  PASS'
        exit 0
    }

    'bump' {
        if (-not $Doc)  { Write-Output 'FAILED: -Doc is required'; exit 1 }
        if (-not $Note) { Write-Output 'FAILED: -Note is required. What changed in this revision?'; exit 1 }
        if ($GOVERNING -notcontains $Doc) {
            Write-Output ("FAILED: '{0}' is not a governing document." -f $Doc)
            Write-Output 'Only documents that change what the pipeline DOES are versioned. A log or a'
            Write-Output 'point-in-time findings file is append-only - versioning it would be ceremony.'
            Write-Output ('Governing: {0}' -f ($GOVERNING -join ', '))
            exit 1
        }
        if ($Doc -eq 'CLAUDE.md') {
            Write-Output 'CLAUDE.md is versioned by rules-version.ps1, which also enforces rule 59.'
            Write-Output 'Use:  rules-version.ps1 -Action bump -Level minor -Note "..."'
            exit 1
        }
        $p = Resolve-DocPath $Doc
        if (-not (Test-Path -LiteralPath $p)) { Write-Output "FAILED: $Doc not found"; exit 1 }
        $docExt = [System.IO.Path]::GetExtension($p).ToLowerInvariant()

        $v = Get-DocVersion $p
        if ($v) {
            $n = Step-Version $v.Major $v.Minor $v.Build $Level
            $newMajor, $newMinor, $newBuild = $n[0], $n[1], $n[2]
        } else {
            # A document's first stamp is 1.0.0. Mods start at 1.5 for historical reasons that do
            # not apply here, and inventing a matching offset would be cargo-culting the number
            # rather than the scheme.
            $newMajor, $newMinor, $newBuild = 1, 0, 0
        }

        New-Item -ItemType Directory -Path $archive -Force | Out-Null
        # The outgoing copy is always archived; a file with no marker yet is archived as <basename>-vUNSTAMPED<ext>.
        $oldTag = if ($v) { "{0}.{1}.{2}" -f $v.Major, $v.Minor, $v.Build } else { 'UNSTAMPED' }
        $dest = Join-Path $archive ("{0}-v{1}{2}" -f [IO.Path]::GetFileNameWithoutExtension($p), $oldTag, [IO.Path]::GetExtension($p))
        Copy-Item -LiteralPath $p -Destination $dest -Force
        Write-Output ("archived -> {0}" -f (Split-Path $dest -Leaf))

        $today = (Get-Date).ToString('yyyy-MM-dd')
        $stamp = "$marker {0}.{1}.{2} | {3} -->" -f $newMajor, $newMinor, $newBuild, $today
        $human = "*Doc v{0}.{1}.{2}, revised {3} - {4}*" -f $newMajor, $newMinor, $newBuild, $today, $Note

        if ($docExt -eq '.json' -or $docExt -eq '.txt') {
            Set-NonMdStamp $p $docExt ("{0}.{1}.{2}" -f $newMajor, $newMinor, $newBuild) $today
            Write-Output ("stamped {0} as v{1}.{2}.{3}" -f $Doc, $newMajor, $newMinor, $newBuild)
            return
        }

        $lines = @((Read-Utf8Lines $p) | Where-Object { $_ -notlike "$marker*" -and $_ -notlike '*Doc v*, revised *' })
        $out = New-Object System.Collections.ArrayList
        $done = $false
        foreach ($l in $lines) {
            [void]$out.Add($l)
            if (-not $done -and $l -match '^# ') { [void]$out.Add(''); [void]$out.Add($stamp); [void]$out.Add($human); $done = $true }
        }
        if (-not $done) { [void]$out.Insert(0, $human); [void]$out.Insert(0, $stamp) }
        Write-Utf8Lines $p $out
        Write-Output ("stamped {0} as v{1}.{2}.{3}" -f $Doc, $newMajor, $newMinor, $newBuild)
    }
}
