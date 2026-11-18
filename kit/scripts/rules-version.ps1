<#
.SYNOPSIS
    Versions `CLAUDE.md`, archives each superseded revision, and REFUSES a revision in which one
    rule amends another by reference instead of being folded into it.

.DESCRIPTION
    the owner, 2026-08-27: "maybe we should add version markers on the rule files so that the updates
    get rolled into a new file instead of referencing other rules."

    THE PROBLEM THIS SOLVES
    ----------------------
    Appending is cheaper than editing, so a correction to an existing rule kept arriving as a NEW
    rule that referenced the old one. Rule 46 said it outright - "a correction to how rule 29 was
    being applied, not a new rule" - and rule 1 carried a paragraph marked superseded by rule 21.
    Nothing was false, but the current policy on a subject stopped being readable from one place,
    and rules are consulted individually - by number, by grep, by whoever is doing one job - not
    read cover to cover.

    His fix is the right one: roll the update INTO the rule and version the file, rather than
    leaving a trail of cross-references for a reader to reassemble.

    WHY 'check' IS THE POINT AND 'bump' IS THE BOOKKEEPING
    -----------------------------------------------------
    A version number nobody enforces is a date stamp. The load-bearing action here is `check`,
    which scans for amendment language aimed at another rule and fails on it. That makes the
    convention self-policing: the next time a correction is appended rather than folded in, the
    check says so while the reasoning is still fresh.

    WHY FULL-FILE ARCHIVES RATHER THAN A DIFF
    -----------------------------------------
    `<ROOT>` is NOT a git repository - there is no history behind ~900 KB of accumulated
    project knowledge, and one bad edit loses it. A copied revision is crude but honest: it always
    opens, needs no tooling, and cannot itself be corrupted by the edit it is protecting against.
    At ~220 KB a revision, a hundred revisions is 22 MB, which is nothing next to what this project
    already stores.

    A local git repo in `.MD` would be strictly better history - but `secrets.md` lives here and
    carries live API keys, so that needs a `.gitignore` and a firm never-push, and is the owner's call
    rather than something to set up quietly.

.PARAMETER Action
    status | check | bump

.EXAMPLE
    .\rules-version.ps1 -Action status
    .\rules-version.ps1 -Action check
    .\rules-version.ps1 -Action bump -Level minor -Note "folded rule 46 into 29; taxonomy to TRIAGE-CATEGORIES.md"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet('status','check','bump')][string]$Action,
    [ValidateSet('major','minor','build')][string]$Level = 'build',
    [string]$Note,
    [switch]$Strict,
    [switch]$Force,
    # Point the read-only reports at another parts folder (test fixtures). Default: the real .MD\rules.
    [string]$RulesDir
)

$ErrorActionPreference = 'Stop'
$md       = Split-Path $PSScriptRoot -Parent
$rules    = Join-Path $md 'CLAUDE.md'
$partsDir = if ($RulesDir) { $RulesDir } else { Join-Path $md 'rules' }
# The rules live in SEVEN self-contained parts under .MD\rules\ (the owner, 2026-08-29); CLAUDE.md is the
# core (loading table, always-on reminders, index) and carries the version stamp for the SET.
$partFiles = @(Get-ChildItem -LiteralPath $partsDir -Filter '*.md' -ErrorAction SilentlyContinue | Sort-Object Name)
$archive  = Join-Path $md 'rules-archive'
$marker   = '<!-- RULES-VERSION:'


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
    $enc = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllLines($path, [string[]]$lines, $enc)
}
function Read-Utf8Text($path) {
    return [System.IO.File]::ReadAllText($path)
}

function Get-Header {
    $first = (Read-Utf8Lines $rules) | Select-Object -First 12
    $line  = $first | Where-Object { $_ -like "$marker*" } | Select-Object -First 1
    if (-not $line) { return $null }
    if ($line -match 'RULES-VERSION:\s*([\d]+)\.([\d]+)\.([\d]+)\s*\|\s*(\d+) rules\s*\|\s*([\d-]+)') {
        return [pscustomobject]@{
            Major = [int]$Matches[1]; Minor = [int]$Matches[2]; Build = [int]$Matches[3]
            Count = [int]$Matches[4]; Date  = $Matches[5]
            Text  = $line
        }
    }
    return $null
}

$coreFiles = if ($RulesDir) { @() } else { @($rules) }   # a fixture folder is read on its own
$text     = (@($coreFiles) + @($partFiles | ForEach-Object { $_.FullName }) | ForEach-Object { Read-Utf8Text $_ }) -join "`n"
$ruleNums = [regex]::Matches($text, '(?m)^## (\d+)\.') | ForEach-Object { [int]$_.Groups[1].Value }
$count    = ($ruleNums | Sort-Object -Unique).Count
$hdr      = Get-Header

switch ($Action) {

    'status' {
        Write-Output ''
        if ($hdr) {
            Write-Output ("  CLAUDE.md  v{0}.{1}.{2}   {3} rules   stamped {4}" -f $hdr.Major, $hdr.Minor, $hdr.Build, $hdr.Count, $hdr.Date)
            if ($hdr.Count -ne $count) {
                Write-Output ("  STALE STAMP: header says {0} rules, the file contains {1}. Bump it." -f $hdr.Count, $count)
            }
        } else {
            Write-Output '  CLAUDE.md carries NO version marker yet. Run -Action bump to stamp it.'
        }
        $setBytes = (Get-Item $rules).Length + (($partFiles | Measure-Object Length -Sum).Sum)
        Write-Output ("  {0} rules in {1} parts + core, {2:N0} bytes total, core {3:N0} lines" -f $count, $partFiles.Count, $setBytes, (Read-Utf8Lines $rules).Count)
        if (Test-Path $archive) {
            $revs = @(Get-ChildItem -LiteralPath $archive -Filter 'CLAUDE-v*.md' | Sort-Object Name)
            Write-Output ("  {0} archived revision(s) in rules-archive\" -f $revs.Count)
            $revs | Select-Object -Last 3 | ForEach-Object { Write-Output ("      {0}" -f $_.Name) }
        } else {
            Write-Output '  no archived revisions yet'
        }
        Write-Output ''
    }

    'check' {
        # The load-bearing action. An amendment that points at another rule instead of being
        # folded into it is exactly what the version scheme exists to stop.
        $bad = @()
        $blocks = [regex]::Matches($text, '(?ms)^## (\d+)\.(.*?)(?=^## \d+\.|\z)')
        foreach ($b in $blocks) {
            $n    = [int]$b.Groups[1].Value
            $body = $b.Groups[2].Value
            # A pointer stub is the SANCTIONED form of this - it is the resolution, not the problem.
            if ($body -match '\(folded into rule \d+') { continue }
            # A rule may declare a reference deliberate with an inline marker.
            if ($body -match '<!--\s*amend-check:\s*ok\s*-->') { continue }

            # PROXIMITY MATTERS. An early version flagged rule 35 because it contains the word
            # "supersedes" somewhere in the same sentence as "Rule 22" - but it was describing a
            # PATCH superseding a CONFLICT, and was reinforcing rule 22 rather than amending it.
            # So the amendment verb must sit close to the rule reference, not merely in the same
            # sentence. 70 characters is wide enough for "superseded by rule 21" and narrow enough
            # to exclude a clause that happens to mention both.
            $verbs = '(?i)(supersed\w*|not a new rule|a correction to how|no longer the primary|amends rule)'
            foreach ($m in [regex]::Matches($body, $verbs)) {
                $from = [Math]::Max(0, $m.Index - 70)
                $len  = [Math]::Min($body.Length - $from, $m.Length + 140)
                $win  = $body.Substring($from, $len)
                if ($win -match '(?i)rule\s+(\d+)') {
                    $target = [int]$Matches[1]
                    if ($target -ne $n) {
                        $snippet = ($win -replace '\s+', ' ').Trim()
                        $bad += [pscustomobject]@{ Rule = $n; Target = $target; Text = $snippet }
                    }
                }
            }
        }
        # SELF-CONTAINMENT census (the owner, 2026-08-29: rules must not reference one another). Counts every
        # 'rule N' inside a rule body that names a DIFFERENT rule. Reported on every check; it becomes a
        # failure once the de-referencing pass has driven it to zero (see -Strict).
        $xrefs = @()
        foreach ($b in $blocks) {
            $n = [int]$b.Groups[1].Value
            if ($b.Groups[2].Value -match '\(folded into rule \d+') { continue }
            foreach ($m in [regex]::Matches($b.Groups[2].Value, '(?i)\brules?\s+(\d+)\b')) {
                if ([int]$m.Groups[1].Value -ne $n) { $xrefs += [pscustomobject]@{ Rule = $n; Target = [int]$m.Groups[1].Value } }
            }
        }
        if ($xrefs.Count) {
            $byRule = $xrefs | Group-Object Rule | Sort-Object { [int]$_.Name }
            Write-Output ('CROSS-REFERENCES remaining: {0} (target 0) in {1} rule(s): {2}' -f $xrefs.Count, $byRule.Count, (($byRule | ForEach-Object { '{0}x{1}' -f $_.Name, $_.Count }) -join ' '))
            if ($Strict) { Write-Output 'FAIL (-Strict) - rules must be self-contained; inline the fact instead of naming the other rule.'; exit 1 }
        } else {
            Write-Output 'SELF-CONTAINED - no rule names another rule.'
        }
        # REPORT-ONLY lines (step 12.16): they never change the exit code, which the amendment check decides.
        function Write-StyleReport {
            $heads = [regex]::Matches($text, '(?m)^## (\d+)\.[ \t]*(.*)$')
            $pro = @($heads | Where-Object { $_.Groups[2].Value -match '(?i)^(never|do not|don''t|no)\b' } | ForEach-Object { [int]$_.Groups[1].Value })
            Write-Output ('prohibitions: {0} of {1} rule headings open with never / do not / no ... (a directive says what to do instead){2}' -f $pro.Count, $heads.Count, $(if ($pro.Count) { ': rule ' + ($pro -join ', ') } else { '' }))
            $hits = @()
            foreach ($b in $blocks) {
                $n = [int]$b.Groups[1].Value
                $body = $b.Groups[2].Value
                if ($body -match '\(folded into rule \d+') { continue }
                $nl = $body.IndexOf("`n")
                if ($nl -ge 0) { $body = $body.Substring($nl + 1) } else { continue }
                foreach ($m in [regex]::Matches($body, '(?i)\b(reasonable|short|soon|a while|a few|quickly|regularly)\b')) {
                    $rest = $body.Substring($m.Index + $m.Length)
                    $end  = [regex]::Match($rest, '[.!?](\s|$)')
                    $sent = if ($end.Success) { $rest.Substring(0, $end.Index) } else { $rest }
                    if ($sent -notmatch '\d') { $hits += [pscustomobject]@{ Rule = $n; Phrase = $m.Value.ToLower() } }
                }
            }
            Write-Output ('unnumbered thresholds: {0}{1}' -f $hits.Count, $(if ($hits.Count) { ': ' + (($hits | ForEach-Object { 'rule {0} "{1}"' -f $_.Rule, $_.Phrase }) -join '; ') } else { '' }))
        }
        if (-not $bad.Count) {
            Write-Output 'PASS - no rule amends another by reference. Each rule states its own current policy.'
            Write-StyleReport
            exit 0
        }
        Write-Output 'FAIL - these rules amend another rule by reference instead of being folded into it:'
        Write-Output ''
        foreach ($b in $bad) {
            Write-Output ("  rule {0} -> rule {1}" -f $b.Rule, $b.Target)
            Write-Output ("      {0}" -f $b.Text.Substring(0, [Math]::Min(160, $b.Text.Length)))
        }
        Write-Output ''
        Write-Output 'Fold the amendment into the rule it amends, leave a dated "Amended" note on that rule,'
        Write-Output 'and reduce the amending rule to a pointer stub - keep its NUMBER reserved, because'
        Write-Output 'PROGRESS.md, PAST-MISTAKES-LIBRARY.md, scripts and stored memories all cite rules by number.'
        Write-StyleReport
        exit 1
    }

    'bump' {
        if (-not $Note) { Write-Output 'FAILED: -Note is required. What changed in this revision?'; exit 1 }

        # Refuse to stamp a revision that still carries the problem, unless overridden knowingly.
        $chk = & $PSCommandPath -Action check
        if ($LASTEXITCODE -ne 0 -and -not $Force) {
            Write-Output ''
            Write-Output 'Refusing to bump: the check above failed. Fix it, or pass -Force if the remaining'
            Write-Output 'references are deliberate and you want them stamped into this revision anyway.'
            exit 1
        }

        # Rule 6, SEMANTIC VERSIONING (2026-10-21), the same scheme the mods use: -Level build is a PATCH step
        # (3.0.9 -> 3.0.10, no roll-over), minor resets the third number, major resets both. All three levels take
        # their arithmetic from version-gate.ps1 (nextnumber -Kind) and nowhere else.
        if ($hdr) {
            $kind = switch ($Level) { 'major' { 'major' } 'minor' { 'minor' } default { 'patch' } }
            $vg = "$(@(& py -3 (Join-Path $PSScriptRoot '..\resolvers\resolve.py') find version-gate)[0])".Trim()   # by role (rule 70)
            $n = & $vg -Action nextnumber -From ('{0}.{1}.{2}' -f $hdr.Major, $hdr.Minor, $hdr.Build) -Kind $kind
            if ($LASTEXITCODE -ne 0 -or -not $n) { Write-Output "version-gate.ps1 refused to step the rules version ($kind): $n"; exit 1 }
            $pv = [version]("$n".Trim()); $newMajor = $pv.Major; $newMinor = $pv.Minor; $newBuild = $pv.Build
        } else { $newMajor, $newMinor, $newBuild = 2, 0, 0 }
        $today = (Get-Date).ToString('yyyy-MM-dd')

        New-Item -ItemType Directory -Path $archive -Force | Out-Null
        if ($hdr) {
            $dest = Join-Path $archive ("CLAUDE-v{0}.{1}.{2}.md" -f $hdr.Major, $hdr.Minor, $hdr.Build)
            Copy-Item -LiteralPath $rules -Destination $dest -Force
            $partArchive = Join-Path $archive ("rules-v{0}.{1}.{2}" -f $hdr.Major, $hdr.Minor, $hdr.Build)
            if ($partFiles.Count) {
                New-Item -ItemType Directory -Path $partArchive -Force | Out-Null
                foreach ($pf in $partFiles) { Copy-Item -LiteralPath $pf.FullName -Destination (Join-Path $partArchive $pf.Name) -Force }
            }
            Write-Output ("archived the outgoing revision -> {0} (+ {1} parts)" -f (Split-Path $dest -Leaf), $partFiles.Count)
        } else {
            $dest = Join-Path $archive 'CLAUDE-v0.0-preversioning.md'
            Copy-Item -LiteralPath $rules -Destination $dest -Force
            Write-Output 'archived the pre-versioning file -> CLAUDE-v0.0-preversioning.md'
        }

        $stamp = "$marker {0}.{1}.{2} | {3} rules | {4} -->" -f $newMajor, $newMinor, $newBuild, $count, $today
        $human = "**Rules v{0}.{1}.{2}** - {3} rules, revised {4}. *{5}*" -f $newMajor, $newMinor, $newBuild, $count, $today, $Note

        $lines = Read-Utf8Lines $rules
        $lines = @($lines | Where-Object { $_ -notlike "$marker*" -and $_ -notlike '**Rules v*- * rules, revised *' })
        # Insert directly under the H1 so it is the first thing read.
        $out = New-Object System.Collections.ArrayList
        $done = $false
        $afterTitle = $false
        foreach ($l in $lines) {
            # 2026-10-12: the blank line each earlier bump put under the title survived the stamp's removal, so every bump
            # added one more (52 blank lines had built up). Blank lines directly under the title are dropped here; the one
            # inserted below is the only one.
            if ($afterTitle -and $l -match '^\s*$') { continue }
            $afterTitle = $false
            [void]$out.Add($l)
            if (-not $done -and $l -match '^# ') {
                $afterTitle = $true
                [void]$out.Add('')
                [void]$out.Add($stamp)
                [void]$out.Add($human)
                [void]$out.Add('')
                $done = $true
            }
        }
        Write-Utf8Lines $rules $out
        Write-Output ("stamped CLAUDE.md as v{0}.{1}.{2} ({3} rules)" -f $newMajor, $newMinor, $newBuild, $count)
        # The one-page session-start digest is DERIVED from the parts (the owner, 2026-09-07: the middle path);
        # regenerate it with every stamp so it can never lag the rules it summarises.
        $digest = Join-Path $PSScriptRoot 'rules-digest.py'
        if (Test-Path -LiteralPath $digest) { & python $digest }
    }
}
