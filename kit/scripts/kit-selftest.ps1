<#
.SYNOPSIS
    The Pipeline Kit self-test: builds a throwaway pipeline in a temp folder and carries the example mod through
    register -> bump -> changelog -> package -> package gate -> record working -> finalize gate, then proves the
    package gate REFUSES a package that breaks a rule, and runs the render pipeline's checks that need no Blender (a
    missing Blender is a SKIP). Prints PASS or FAIL; exit code 0 only on PASS.
.DESCRIPTION
    Step 6 of README-FOR-AI.md. An agent must not report the pipeline as up until this passes. Nothing outside the
    temp folder is written: the environment variables are set for this process only and restored afterwards.
.PARAMETER Kit
    The kit folder (the unzipped kit, or <ROOT>\.MD after kit-install). Default: the parent of this script.
.PARAMETER KeepTemp
    Leave the temp pipeline in place for inspection.
#>
[CmdletBinding()]
param(
    [string]$Kit = '',
    [switch]$KeepTemp
)
$ErrorActionPreference = 'Continue'
if (-not $Kit) { $Kit = Split-Path $PSScriptRoot -Parent }   # not a param default: $PSScriptRoot is empty there under [CmdletBinding()]
$ps = (Get-Command powershell.exe).Source
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$tmp = Join-Path $env:TEMP "pipeline-kit-selftest-$stamp"
# the profile the test points USERPROFILE at sits BESIDE the temp root: the root holds only the stages and .MD (rule 39)
$tmpHome = "$tmp.home"
$script:results = New-Object System.Collections.Generic.List[object]
$script:log = New-Object System.Collections.Generic.List[string]

function Say($s) { Write-Host $s; $script:log.Add($s) }   # Write-Host: inside Run, Write-Output would become the return value
function Run([string]$name, [string]$file, [string[]]$argv, [int[]]$expectExit = @(0), [string]$expectText = $null, [string]$forbidText = $null) {
    # ($argv, not $args: $args is PowerShell's automatic variable and cannot be a parameter)
    $out = & $ps -NoProfile -ExecutionPolicy Bypass -File $file @argv 2>&1 | ForEach-Object { "$_" }
    $code = $LASTEXITCODE
    $text = ($out -join "`n")
    $ok = ($expectExit -contains $code)
    if ($ok -and $expectText -and ($text -notmatch $expectText)) { $ok = $false }
    if ($ok -and $forbidText -and ($text -match $forbidText)) { $ok = $false }
    $script:results.Add([pscustomobject]@{ name = $name; ok = $ok; exit = $code })
    Say ("{0}  {1}  (exit {2})" -f $(if ($ok) { '  ok' } else { 'FAIL' }), $name, $code)
    foreach ($l in $out) { Say ("        " + $l) }
    return $text
}
function PyRun([string]$name, [string[]]$argv, [int[]]$expectExit = @(0), [string]$expectText = $null, [int]$tail = 4) {
    # a Python tool, judged by its exit code and its output; only the last lines are kept (the gate self-tests print every case)
    $out = & python @argv 2>&1 | ForEach-Object { "$_" }
    $code = $LASTEXITCODE
    $text = ($out -join "`n")
    $ok = ($expectExit -contains $code) -and (-not $expectText -or ($text -match $expectText))
    $script:results.Add([pscustomobject]@{ name = $name; ok = $ok; exit = $code })
    Say ("{0}  {1}  (exit {2})" -f $(if ($ok) { '  ok' } else { 'FAIL' }), $name, $code)
    foreach ($l in @($out | Select-Object -Last $tail)) { Say ("        " + $(if ($l.Length -gt 220) { $l.Substring(0, 220) + ' ...' } else { $l })) }
    return $text
}
function Check([string]$name, [bool]$cond, [string]$detail = '') {
    $script:results.Add([pscustomobject]@{ name = $name; ok = $cond; exit = $null })
    Say ("{0}  {1}{2}" -f $(if ($cond) { '  ok' } else { 'FAIL' }), $name, $(if ($detail) { "  - $detail" } else { '' }))
}

$saved = @{ PIPELINE_ROOT = $env:PIPELINE_ROOT; PIPELINE_MO2_INSTANCES = $env:PIPELINE_MO2_INSTANCES; NEXUS_APIKEY = $env:NEXUS_APIKEY; USERPROFILE = $env:USERPROFILE }
try {
    Say "Pipeline Kit self-test  $stamp"
    Say "kit:  $Kit"
    Say "temp: $tmp"
    Say ''
    # the install seeds a Claude Code memory folder under USERPROFILE\.claude\projects, and the resolver's {home} is
    # USERPROFILE: point both at the temp folder, so the test never writes into the person's own .claude
    $env:USERPROFILE = $tmpHome
    New-Item -ItemType Directory -Force -Path $env:USERPROFILE | Out-Null

    # 1. install into the temp root
    Run 'kit-install into a temp root' (Join-Path $Kit 'scripts\kit-install.ps1') @('-Root', $tmp, '-NoEnv') | Out-Null
    $env:PIPELINE_ROOT = $tmp
    $env:PIPELINE_MO2_INSTANCES = ''
    $env:NEXUS_APIKEY = ''
    $s = Join-Path $tmp '.MD\scripts'
    Check 'stage folders present' ((Get-ChildItem -LiteralPath $tmp -Directory | Where-Object { $_.Name -match '^\d+\. ' }).Count -eq 12)
    Check 'ledgers are empty' (((Get-Content -LiteralPath (Join-Path $s 'version-ledger.json') -Raw).Trim() -eq '[]') -and ((Get-Content -LiteralPath (Join-Path $s 'version-registry.json') -Raw).Trim() -eq '{}'))

    # 1b. the layout and the role resolver (rule 70): every script sits in its kind folder, none is a retired-path
    # stub, and the resolver of THIS tree answers every role inside the temp root
    $res = Join-Path $tmp '.MD\resolvers\resolve.py'
    $stubs = @(Get-ChildItem -LiteralPath (Join-Path $tmp '.MD') -Recurse -File -Include *.ps1, *.py | Where-Object { (Get-Content -LiteralPath $_.FullName -TotalCount 3) -match '^\W*RETIRED PATH \(stub' })
    Check 'no retired-path stub in the installed tree' ($stubs.Count -eq 0) (($stubs | ForEach-Object { $_.Name }) -join ', ')
    $o = @(& py -3 $res check 2>&1 | ForEach-Object { "$_" })
    Check 'resolve.py check: every shipped role resolves to a file of this tree' ($LASTEXITCODE -eq 0) (($o | Select-Object -Last 3) -join ' | ')
    $o = @(& py -3 $res find version-gate 2>&1 | ForEach-Object { "$_" })
    Check 'resolve.py find version-gate answers inside the temp root' (($LASTEXITCODE -eq 0) -and ("$($o[0])" -like "$tmp\.MD\scripts\gates\version-gate.ps1")) "$($o[0])"
    $o = @(& py -3 $res find past-mistakes-library 2>&1 | ForEach-Object { "$_" })
    Check 'resolve.py: role past-mistakes-library is PAST-MISTAKES-LIBRARY.md' (($LASTEXITCODE -eq 0) -and ("$($o[0])" -like '*\PAST-MISTAKES-LIBRARY.md')) "$($o[0])"
    $o = (& py -3 (Join-Path $tmp '.MD\resolvers\session-start.py') --print 2>&1 | ForEach-Object { "$_" }) -join "`n"
    $ssOk = $false; try { $ss = $o | ConvertFrom-Json; $ssOk = ($ss.hookSpecificOutput.additionalContext -match 'PAST-MISTAKES-LIBRARY\.md') -and ($ss.hookSpecificOutput.additionalContext -match [regex]::Escape($tmp)) } catch { }
    Check 'session-start.py prints the SessionStart payload for this tree' $ssOk ($o.Substring(0, [Math]::Min(160, $o.Length)))

    # 2. the example mod's repo
    $repo = Join-Path $tmp '6. current wip mods\ExampleMod'
    New-Item -ItemType Directory -Force -Path $repo | Out-Null
    Get-ChildItem -LiteralPath (Join-Path $Kit 'example\ExampleMod') -File | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $repo -Force }
    & git -C $repo init -q 2>$null | Out-Null

    # 3. register, bump, current
    # a new mod needs a note of what already exists (the version gate asks for one); the example's is a line
    $prior = Join-Path $tmp '4. plans\example-prior-art.txt'
    Set-Content -LiteralPath $prior -Value 'Self-test: the example is not for release, so nothing on Nexus or GitHub was searched.' -Encoding UTF8
    Run 'version-gate register' (Join-Path $s 'gates\version-gate.ps1') @('-Action', 'register', '-Mod', 'ExampleMod', '-Repo', 'ExampleMod', '-DisplayName', 'Example Mod', '-PriorArt', $prior) 0 'location: example_mod.py __version__' | Out-Null
    $bump = Run 'version-gate bump issues 1.0.0' (Join-Path $s 'gates\version-gate.ps1') @('-Action', 'bump', '-Mod', 'ExampleMod', '-Kind', 'patch') 0 '1\.0\.0'
    $cur = Run 'version-gate current' (Join-Path $s 'gates\version-gate.ps1') @('-Action', 'current', '-Mod', 'ExampleMod') 0 '1\.0\.0'
    $ver = '1.0.0'
    Check 'bump wrote the number into the repo' (((Get-Content -LiteralPath (Join-Path $repo 'example_mod.py') -Raw) -match '__version__ = "1\.0\.0"'))

    # 4. changelog written as the change happens
    Run 'changelog add' (Join-Path $s 'release\changelog.ps1') @('-Action', 'add', '-Mod', 'ExampleMod', '-Version', $ver, '-Type', 'Added', '-Entry', 'first version: one toolbar button that says hello') | Out-Null
    Check 'CHANGELOG.md carries the entry' ((Test-Path -LiteralPath (Join-Path $repo 'CHANGELOG.md')) -and ((Get-Content -LiteralPath (Join-Path $repo 'CHANGELOG.md') -Raw) -match '1\.0\.0'))

    # 5. the package
    # 1.0.2: packages sit in "<stage>\<Game> - <Mod>\<Mod> <version>" since the live pipeline's 2026-10-01 layout, and
    # the finalize gate looks there; ask the live resolver rather than joining the path here (1.0.1's flat path made
    # the finalize step fail against the current version-gate.ps1)
    . (Join-Path $s 'distro-names.ps1')
    $pkg = Join-Path (Resolve-PackageRoot -Root (Join-Path $tmp '7. current test builds') -ModName 'Example Mod' -Game 'Skyrim' -ProjectRoot $tmp) "Example Mod $ver"   # the gate's default game
    New-Item -ItemType Directory -Force -Path (Join-Path $pkg 'plugins') | Out-Null
    Copy-Item -LiteralPath (Join-Path $repo 'example_mod.py') -Destination (Join-Path $pkg 'plugins\example_mod.py')
    Copy-Item -LiteralPath (Join-Path $Kit 'LICENSE-GPL-3.0.txt') -Destination (Join-Path $pkg 'LICENSE')
    Copy-Item -LiteralPath (Join-Path $repo 'NOTICE.md') -Destination (Join-Path $pkg 'NOTICE.md')
    Copy-Item -LiteralPath (Join-Path $repo 'CHANGELOG.md') -Destination (Join-Path $pkg 'CHANGELOG.md')
    ((Get-Content -LiteralPath (Join-Path $repo 'README.txt') -Raw) -replace 'Version \d+\.\d+\.\d+', "Version $ver") | Set-Content -LiteralPath (Join-Path $pkg 'README.txt') -Encoding UTF8
    Run 'package-gate passes the good package' (Join-Path $s 'gates\package-gate.ps1') @('-Package', $pkg, '-ModName', 'Example Mod', '-Version', $ver) 0 'every rule clear' | Out-Null

    # 6. record working with evidence and the shipped file's hash; commit and tag (rule 9); then the finalize gate
    Run 'version-gate record working' (Join-Path $s 'gates\version-gate.ps1') @('-Action', 'record', '-Mod', 'ExampleMod', '-Version', $ver, '-Status', 'working', '-Evidence', 'self-test: the example plugin loaded in a throwaway MO2 profile and its button showed the hello dialog', '-Dll', (Join-Path $pkg 'plugins\example_mod.py')) | Out-Null
    & git -C $repo add -A 2>$null | Out-Null
    & git -C $repo -c user.name=selftest -c user.email=selftest@example.invalid commit -q -m "Example Mod $ver" 2>$null | Out-Null
    & git -C $repo tag "v$ver" 2>$null | Out-Null
    Check "git commit and tag v$ver (the finalize gate requires the tag)" ((& git -C $repo tag) -contains "v$ver")
    Run 'version-gate gate -Stage finalize' (Join-Path $s 'gates\version-gate.ps1') @('-Action', 'gate', '-Mod', 'ExampleMod', '-Version', $ver, '-Stage', 'finalize') 0 'clears the finalize gate' 'GATE CLOSED' | Out-Null

    # 7. the gate refuses what the rules forbid
    $bad = Join-Path $tmp "7. current test builds\Example Mod $ver BAD"
    New-Item -ItemType Directory -Force -Path (Join-Path $bad 'scripts') | Out-Null
    Copy-Item -LiteralPath "$pkg\*" -Destination $bad -Recurse -Force
    Set-Content -LiteralPath (Join-Path $bad 'scripts\ExampleTest.pex') -Value 'not a real script' -Encoding ASCII
    Set-Content -LiteralPath (Join-Path $bad 'example.esl') -Value 'not a real plugin' -Encoding ASCII
    Set-Content -LiteralPath (Join-Path $bad 'broken.json') -Value '{ "path": "Data\Interface" }' -Encoding ASCII
    Run 'package-gate REFUSES the bad package (test script, .esl, unparseable json)' (Join-Path $s 'gates\package-gate.ps1') @('-Package', $bad, '-ModName', 'Example Mod', '-Version', $ver) @(1) 'no-test-scripts-in-packages' | Out-Null
    Remove-Item -LiteralPath $bad -Recurse -Force

    # 8. a number is reclaimed when a build fails: record 1.0.1 failed, next must be 1.0.1 again
    # 1.0.4: a working number stays OPEN until it is posted (live version-gate since 2026-10-11), so post 1.0.0 locally first
    Run 'version-gate link (local channel)' (Join-Path $s 'gates\version-gate.ps1') @('-Action', 'link', '-Mod', 'ExampleMod', '-Channel', 'local') 0 | Out-Null
    Run 'version-gate posted 1.0.0' (Join-Path $s 'gates\version-gate.ps1') @('-Action', 'posted', '-Mod', 'ExampleMod', '-Version', $ver, '-Channel', 'local', '-Evidence', 'self-test: kept local') 0 | Out-Null
    Run 'version-gate bump issues 1.0.1'(Join-Path $s 'gates\version-gate.ps1') @('-Action', 'bump', '-Mod', 'ExampleMod', '-Kind', 'patch') 0 '1\.0\.1' | Out-Null
    Run 'version-gate record 1.0.1 failed' (Join-Path $s 'gates\version-gate.ps1') @('-Action', 'record', '-Mod', 'ExampleMod', '-Version', '1.0.1', '-Status', 'failed', '-Evidence', 'self-test: pretend the build crashed') 0 'next bump reuses it' | Out-Null
    Run 'version-gate next reuses 1.0.1' (Join-Path $s 'gates\version-gate.ps1') @('-Action', 'next', '-Mod', 'ExampleMod') 0 '1\.0\.1' | Out-Null
    # 1.0.5 / SemVer (rules 3.1.0): bump needs a kind; an open number takes a higher kind by withdrawing and re-issuing
    Run 'version-gate bump refuses without -Kind' (Join-Path $s 'gates\version-gate.ps1') @('-Action', 'bump', '-Mod', 'ExampleMod') @(1) '-Kind' | Out-Null
    Run 'version-gate bump -Kind minor issues 1.1.0' (Join-Path $s 'gates\version-gate.ps1') @('-Action', 'bump', '-Mod', 'ExampleMod', '-Kind', 'minor') 0 '1\.1\.0' | Out-Null
    Run 'version-gate bump -Kind major issues 2.0.0' (Join-Path $s 'gates\version-gate.ps1') @('-Action', 'bump', '-Mod', 'ExampleMod', '-Kind', 'major') 0 '2\.0\.0' | Out-Null

    # 9. the housekeeping tools run
    Run 'prune-test-builds (dry run)' (Join-Path $s 'prune-test-builds.ps1') @('-ModName', 'Example Mod', '-SkipMO2') | Out-Null
    Run 'gate-ledger record a verdict' (Join-Path $s 'gate-ledger.ps1') @('-Action', 'record', '-Stage', '8', '-Subject', 'Example Mod', '-Verdict', 'compatible', '-Evidence', 'self-test: shares no file with any other mod', '-Guard', 'holds while no other mod ships these files', '-EvidenceRef', $prior) | Out-Null
    Run 'gate-ledger stats' (Join-Path $s 'gate-ledger.ps1') @('-Action', 'stats') | Out-Null

    # 10. python tools: the digest regenerates, the library index is current
    $py = Get-Command python -ErrorAction SilentlyContinue
    if ($py) {
        $digestBefore = Get-Content -LiteralPath (Join-Path $tmp '.MD\RULES-DIGEST.md') -Raw
        $o = & python (Join-Path $s 'rules-digest.py') 2>&1 | ForEach-Object { "$_" }
        $digestAfter = Get-Content -LiteralPath (Join-Path $tmp '.MD\RULES-DIGEST.md') -Raw
        $nBefore = ([regex]::Matches($digestBefore, '(?m)^\*\*\d+\. ')).Count
        $nAfter = ([regex]::Matches($digestAfter, '(?m)^\*\*\d+\. ')).Count
        Check "rules-digest.py regenerates the digest ($nAfter rules)" (($LASTEXITCODE -eq 0) -and ($nAfter -eq $nBefore) -and ($nAfter -ge 60)) ($o -join ' ')
        $o = & python (Join-Path $s 'logic-index.py') '--check' 2>&1 | ForEach-Object { "$_" }
        Check 'logic-index.py --check: the past-mistakes library index is current' ($LASTEXITCODE -eq 0) (($o | Select-Object -Last 1))
        $o = & python (Join-Path $s 'gate-rules-index.py') '--check' 2>&1 | ForEach-Object { "$_" }
        Check 'gate-rules-index.py --check: the gate-rules index is current' ($LASTEXITCODE -eq 0) (($o | Select-Object -Last 1))
    } else {
        Check 'python on PATH (needed by the digest, the index, the plugin audit)' $false 'python not found'
    }

    # 11. 1.1.0: the render work pipeline (README-FOR-AI 7e) - no Blender needed and no game mesh: every mesh and
    # pattern here is made up by the test (example\render-test)
    if ($py) {
        $fx = Join-Path $Kit 'example\render-test'
        $rt = Join-Path $tmp '4. plans\render-test'   # inside a stage: the root holds only the stages (root-topology-gate)
        New-Item -ItemType Directory -Force -Path $rt | Out-Null
        PyRun 'package-render: the example package ships no NIF, so it passes at once' @((Join-Path $s 'release\package-render.py'), '--mod', 'ExampleMod', '--version', $ver, '--package', $pkg) 0 'ships no \.nif' | Out-Null
        foreach ($g in @('gates\package-render-gate.py', 'gates\engraving-layout-gate.py', 'gates\fomod-option-image-gate.py', 'gates\surface-profile-gate.py', 'render\nif-readback.py', 'render\before-after-sheet.py')) {
            PyRun "$(Split-Path $g -Leaf) --self-test" @((Join-Path $s $g), '--self-test') 0 'self-test PASS' 1 | Out-Null
        }
        $cli = Join-Path $s 'art\patternlib\cli.py'
        $pg = Join-Path $s 'gates\pattern-gate.py'
        PyRun 'patternlib: a triquetra on its medallion at 80 px per unit passes its validators' @($cli, (Join-Path $fx 'triquetra.json'), (Join-Path $rt 'good')) 0 'patternlib: PASS' 1 | Out-Null
        PyRun 'pattern-gate passes the saved pattern' @($pg, (Join-Path $rt 'good')) 0 'pattern-gate: OK' 1 | Out-Null
        PyRun 'patternlib REFUSES the same triquetra at 6 px per unit (too fine for the texture)' @($cli, (Join-Path $fx 'triquetra-coarse.json'), (Join-Path $rt 'coarse')) @(2) 'REFUSED min-feature' 1 | Out-Null
        PyRun 'pattern-gate REFUSES the refused pattern' @($pg, (Join-Path $rt 'coarse')) @(1) 'pattern-gate: FAIL' 1 | Out-Null
        PyRun 'package_render_uv: an evenly mapped strip passes, the same strip squashed fails' @((Join-Path $fx 'uv-strip-test.py'), (Join-Path $s 'release')) 0 'even strip: PASS   squashed strip: FAIL' 1 | Out-Null
        # Blender finds its add-ons (PyNifly) under the person's own profile, so the probe - which only starts Blender in
        # the background with factory settings and saves nothing - runs with the real USERPROFILE, not the temp one
        $env:USERPROFILE = $saved.USERPROFILE
        $probe = (& python (Join-Path $fx 'blender-probe.py') (Join-Path $s 'render') 2>&1 | ForEach-Object { "$_" }) -join ' '
        $env:USERPROFILE = $tmpHome
        if ($probe -match 'BLENDER-OK') {
            Check 'Blender with PyNifly found - the render steps can run' $true ($probe -replace '^.*BLENDER-OK ', '')
        } else {
            # no Blender (or no PyNifly in it): a render step must say SKIP and write nothing, not fail
            PyRun 'before-after-sheet render reports SKIP without Blender / PyNifly' @((Join-Path $s 'render\before-after-sheet.py'), 'render', '--out', (Join-Path $rt 'sheet'), '--before', 'none.nif', '--before-tex', $rt, '--after', 'none.nif', '--after-tex', $rt) @(3) 'SKIP' 1 | Out-Null
        }
    }
    # 12. 1.1.0: the tools brought in from the current pipeline - the hooks, the session tools, the learning loop
    if ($py) {
        $hx = Join-Path $Kit 'example\hook-test'
        $ht = Join-Path $tmp '4. plans\hook-test'
        New-Item -ItemType Directory -Force -Path $ht | Out-Null
        function Hook([string]$name, [string]$guard, [string]$fixture, [int]$want) {
            $out = Get-Content -LiteralPath (Join-Path $hx $fixture) -Raw | & python (Join-Path $s $guard) 2>&1 | ForEach-Object { "$_" }
            $code = $LASTEXITCODE
            Check "$name (exit $code, want $want)" ($code -eq $want) ((($out | Select-Object -First 1) -as [string]))
        }
        Hook 'bash-backslash-guard REFUSES a heredoc carrying a doubled backslash' 'bash-backslash-guard.py' 'bash-heredoc-doubled-backslash.json' 2
        Hook 'bash-backslash-guard passes a plain command' 'bash-backslash-guard.py' 'bash-plain.json' 0
        Hook 'mo2-elevated-launch-guard REFUSES starting ModOrganizer.exe from the shell' 'mo2-elevated-launch-guard.py' 'mo2-start-process.json' 2
        Hook 'mo2-elevated-launch-guard passes a process listing' 'mo2-elevated-launch-guard.py' 'mo2-tasklist.json' 0
        # kit-hooks registers them in a settings.json: a person's own hook is kept, a second apply changes nothing
        $set = Join-Path $ht 'settings.json'
        Set-Content -LiteralPath $set -Value '{"theme": "dark", "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "py -3 my-own-hook.py"}]}]}}' -Encoding ASCII
        PyRun 'kit-hooks --apply registers the pipeline hooks in a settings.json' @((Join-Path $s 'kit-hooks.py'), '--apply', '--settings', $set) 0 'registered' 1 | Out-Null
        PyRun 'kit-hooks --apply a second time changes nothing' @((Join-Path $s 'kit-hooks.py'), '--apply', '--settings', $set) 0 'nothing changed' 1 | Out-Null
        PyRun 'kit-hooks --check finds every hook' @((Join-Path $s 'kit-hooks.py'), '--check', '--settings', $set) 0 'every hook registered' 1 | Out-Null
        $sj = Get-Content -LiteralPath $set -Raw
        Check "kit-hooks kept the person's own hook and settings" (($sj -match 'my-own-hook\.py') -and ($sj -match '"theme"'))
        # the problem card (rule 56): a skeleton is refused, a filled card passes
        $pc = Join-Path $s 'problem-card.py'
        $o = PyRun 'problem-card new writes a skeleton card' @($pc, 'new', '--task', 'example hello button', '--dir', $ht) 0 $null 1
        $skel = @(Get-ChildItem -LiteralPath $ht -Filter '*example-hello-button*.md' | Select-Object -First 1)
        if ($skel.Count -eq 1) { PyRun 'problem-card check REFUSES the unfilled skeleton' @($pc, 'check', $skel[0].FullName) @(3) 'REFUSED' 1 | Out-Null }
        else { Check 'problem-card new wrote a card' $false $o }
        PyRun 'problem-card check passes a filled card' @($pc, 'check', (Join-Path $hx 'problem-card-filled.md')) 0 $null 1 | Out-Null
        # the sessions' message bus: a message sent is in the receiver's inbox
        $am = Join-Path $s 'ops\agent-msg.py'
        PyRun 'agent-msg send puts a message in a session inbox' @($am, 'send', '--to', 'Selftest Session', '--subject', 'kit self-test hello', '--body', 'one line', '--from', 'Kit Selftest', '--new-name', 'yes') 0 $null 1 | Out-Null
        PyRun 'agent-msg inbox lists it' @($am, 'inbox', '--for', 'Selftest Session') 0 'kit self-test hello' 1 | Out-Null
        # ini-edit changes one key and nothing else
        $ini = Join-Path $ht 'example.ini'
        Set-Content -LiteralPath $ini -Value @('; a comment that must survive', '[General]', 'iHotkey = 37', 'bEnabled = 1') -Encoding ASCII
        PyRun 'ini-edit sets one key' @((Join-Path $s 'ini-edit.py'), $ini, '--set', 'General:iHotkey=38') 0 $null 1 | Out-Null
        $iniT = Get-Content -LiteralPath $ini -Raw
        Check 'ini-edit changed that key and kept the rest' (($iniT -match 'iHotkey = 38') -and ($iniT -match 'a comment that must survive') -and ($iniT -match 'bEnabled = 1'))
        PyRun 'fomod-repo-installer-shipped-gate.py --self-test' @((Join-Path $s 'gates\fomod-repo-installer-shipped-gate.py'), '--self-test') 0 'PASS' 1 | Out-Null
        PyRun 'root-topology-gate: the installed root is the twelve stages and the hidden .MD' @((Join-Path $s 'gates\root-topology-gate.py')) 0 $null 2 | Out-Null
        PyRun 'repeated-lesson-scan reads the library' @((Join-Path $s 'repeated-lesson-scan.py')) 0 $null 1 | Out-Null
        PyRun 'gate-catalogue --build writes the catalogue of every gate' @((Join-Path $s 'gate-catalogue.py'), '--build') 0 $null 1 | Out-Null
    }
}
finally {
    $env:PIPELINE_ROOT = $saved.PIPELINE_ROOT
    $env:PIPELINE_MO2_INSTANCES = $saved.PIPELINE_MO2_INSTANCES
    $env:NEXUS_APIKEY = $saved.NEXUS_APIKEY
    $env:USERPROFILE = $saved.USERPROFILE
}

$fails = @($script:results | Where-Object { -not $_.ok })
Say ''
if ($fails.Count -eq 0) { Say ("PASS  ({0} checks)" -f $script:results.Count) } else { Say ("FAIL  ({0} of {1}): {2}" -f $fails.Count, $script:results.Count, (($fails | ForEach-Object { $_.name }) -join '; ')) }
$outFile = Join-Path $env:TEMP "pipeline-kit-selftest-$stamp.txt"
$script:log | Set-Content -LiteralPath $outFile -Encoding UTF8
Say "output saved: $outFile"
if ($fails.Count -eq 0 -and -not $KeepTemp) { Remove-Item -LiteralPath $tmp, $tmpHome -Recurse -Force -ErrorAction SilentlyContinue }
elseif ($KeepTemp -or $fails.Count -gt 0) { Say "temp pipeline kept: $tmp" }
exit $(if ($fails.Count -eq 0) { 0 } else { 1 })
