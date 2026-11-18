<#
.SYNOPSIS
    Installs the Pipeline Kit at a root: the stage folders, <ROOT>\.MD with every kit file, the empty ledgers,
    pipeline.config.json (in .MD), and (optionally) the PIPELINE_ROOT environment variable and the global git hook.
.DESCRIPTION
    Step 3 of README-FOR-AI.md. Run it from the unzipped kit; it copies the kit INTO <ROOT>\.MD so that every path
    the scripts and rosters expect is real: the scripts in their kind folders (<ROOT>\.MD\scripts\gates\version-gate.ps1,
    scripts\release\, scripts\ops\, scripts\plugins\) and the role resolver beside them (<ROOT>\.MD\resolvers\resolve.py
    with its rosters). It then names the Claude Code memory folder of <ROOT> in the data roster, seeds that folder if
    it does not exist, generates the resolver's INDEX.md and runs `resolve.py check`. Safe to rerun: it never
    overwrites a ledger that already holds entries unless -Force is given, never overwrites an existing memory file,
    and never touches the numbered stage folders' contents.
.PARAMETER Root
    The pipeline root to create or complete.
.PARAMETER Mo2Instances
    Optional: each Mod Organizer 2 instance's "mods" folder. Written to pipeline.config.json and, unless -NoEnv,
    to the PIPELINE_MO2_INSTANCES user environment variable (;-separated).
.PARAMETER SetGitHooks
    Also run `git config --global core.hooksPath <ROOT>\.MD\scripts\git-hooks` (the version-rollover pre-push hook).
    (The memory folder goes under $env:USERPROFILE\.claude\projects - the self-test points USERPROFILE at its temp
    folder so nothing of the person's is touched.)
.PARAMETER NoEnv
    Do not set user environment variables (the self-test uses this; it sets them for its own process only).
.PARAMETER Force
    Overwrite ledgers that already hold entries.
.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\kit-install.ps1 -Root D:\Pipeline -SetGitHooks
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Root,
    [string[]]$Mo2Instances = @(),
    [switch]$SetGitHooks,
    [switch]$NoEnv,
    [switch]$Force
)
$ErrorActionPreference = 'Stop'

$kit = Split-Path $PSScriptRoot -Parent            # the unzipped kit, or <ROOT>\.MD when rerun from an install
if ($Root -match '[\[\]]') { Write-Output "FAIL  the root path contains [ or ]; PowerShell treats those as wildcards in -Path/-Filter. Choose another folder."; exit 1 }
New-Item -ItemType Directory -Force -Path $Root | Out-Null
$Root = (Get-Item -LiteralPath $Root).FullName
$md = Join-Path $Root '.MD'

$STAGES = @(
    '1. mod sorter', '2. Mod Types', '2. Mod Types\to-do list', '2. Mod Types\bug reports',
    '2. Mod Types\Framework or Utility', '3. analyze mods', '4. plans', '5. current project mod',
    '6. current wip mods', '7. current test builds', '8. confirm compatibility', '9. patches output',
    '10. finalized mods', '11. Nexus distro', '12. needs an update'
)
foreach ($s in $STAGES) { New-Item -ItemType Directory -Force -Path (Join-Path $Root $s) | Out-Null }
Write-Output ("  ok  {0} stage folders under {1}" -f ($STAGES | Where-Object { $_ -notmatch '\\' }).Count, $Root)

# the ledgers: refuse to clobber real data
$LEDGERS = @('version-registry.json', 'version-ledger.json', 'version-ledger-prerelease.json', 'gate-ledger.json', 'falsification-log.json')
if (Test-Path -LiteralPath (Join-Path $md 'scripts')) {
    foreach ($l in $LEDGERS) {
        $p = Join-Path $md "scripts\$l"
        if (Test-Path -LiteralPath $p) {
            $t = (Get-Content -LiteralPath $p -Raw).Trim()
            if ($t -ne '[]' -and $t -ne '{}' -and -not $Force) {
                Write-Output "FAIL  $p already holds entries. This install would replace it with an empty ledger. Rerun with -Force only if that is what you want."
                exit 1
            }
        }
    }
}

# copy the kit into <ROOT>\.MD (unless the kit IS <ROOT>\.MD already)
if ((Get-Item -LiteralPath $kit).FullName -ieq $md) {
    Write-Output "  ok  kit already lives at $md (rerun); files not copied"
} else {
    New-Item -ItemType Directory -Force -Path $md | Out-Null
    $n = 0
    Get-ChildItem -LiteralPath $kit -Recurse -File | ForEach-Object {
        $rel = $_.FullName.Substring($kit.Length + 1)
        $dest = Join-Path $md $rel
        New-Item -ItemType Directory -Force -Path (Split-Path $dest -Parent) | Out-Null
        Copy-Item -LiteralPath $_.FullName -Destination $dest -Force
        $n++
    }
    Write-Output "  ok  $n kit files copied into $md"
}
New-Item -ItemType Directory -Force -Path (Join-Path $md 'docs-archive') | Out-Null
# rule 39 and the root-topology gate: the visible root is the twelve stages and nothing else - .MD is a tool folder,
# so it is Hidden (a person sees the stages in Explorer; the gate refuses a visible non-stage entry at the root)
$mdItem = Get-Item -LiteralPath $md -Force
if (-not ($mdItem.Attributes -band [IO.FileAttributes]::Hidden)) { $mdItem.Attributes = $mdItem.Attributes -bor [IO.FileAttributes]::Hidden }
New-Item -ItemType Directory -Force -Path (Join-Path $md 'logs') | Out-Null

# the Claude Code memory folder of this root: Claude Code names a project's folder after the directory it was started
# in, every character outside [A-Za-z0-9] replaced by '-' (D:\Pipeline -> D--Pipeline). The data roster ships with the
# placeholder @PROJECT@ in role memory-folder; it is filled in here. Start Claude Code from <ROOT> to use this folder.
$project = [regex]::Replace($Root, '[^A-Za-z0-9]', '-')
$dataRoster = Join-Path $md 'resolvers\rosters\data.json'
if (Test-Path -LiteralPath $dataRoster) {
    $dr = [IO.File]::ReadAllText($dataRoster)
    if ($dr.Contains('@PROJECT@')) {
        [IO.File]::WriteAllText($dataRoster, $dr.Replace('@PROJECT@', $project), (New-Object Text.UTF8Encoding $false))
        Write-Output "  ok  role memory-folder = {home}\.claude\projects\$project\memory"
    }
}
$memDir = Join-Path $env:USERPROFILE ".claude\projects\$project\memory"
New-Item -ItemType Directory -Force -Path $memDir | Out-Null
$vocab = Join-Path $memDir 'topics-vocabulary.txt'
if (-not (Test-Path -LiteralPath $vocab)) {
    [IO.File]::WriteAllText($vocab, "# DOC-VERSION: 1.0.0 | $((Get-Date).ToString('yyyy-MM-dd'))`nalways`n", (New-Object Text.UTF8Encoding $false))
}
$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) {
    if (-not (Test-Path -LiteralPath (Join-Path $memDir 'INDEX.md'))) {
        & py -3 (Join-Path $md 'scripts\memory-index.py') --dir $memDir --build | Out-Null
    }
    Write-Output "  ok  memory folder $memDir"
} else {
    Write-Output "WARN  the Python launcher 'py' is not on PATH: the scripts look everything up through 'py -3 resolvers\resolve.py'. Install Python 3 (python.org, with the launcher) and rerun."
}

# seed the record files the scripts append to
$seeds = @{
    (Join-Path $md 'PROGRESS.md')                          = "# Progress log`n`nChronological, project-wide, append-only (a RECORD document: git gives it history, it is not versioned).`n"
    (Join-Path $Root '2. Mod Types\to-do list\to-do-list.md') = "# Backlog - questions and decisions waiting on the owner`n`nAppend a dated entry under Open; move it to Resolved with a one-line note when decided.`n`n## Open`n`n## Resolved`n"
    (Join-Path $Root '2. Mod Types\queue.md')              = "# Work queue`n`n| # | mod | class | est. time | status |`n|---|---|---|---|---|`n"
}
foreach ($k in $seeds.Keys) { if (-not (Test-Path -LiteralPath $k)) { Set-Content -LiteralPath $k -Value $seeds[$k] -Encoding UTF8 } }

# pipeline.config.json in .MD (1.1.0: no longer at the root, which holds only the twelve stages)
$cfgPath = Join-Path $md 'pipeline.config.json'
$kitVer = ''
try { $kitVer = (Get-Content -LiteralPath (Join-Path $md 'MANIFEST.json') -Raw | ConvertFrom-Json).version } catch { }
$cfg = [ordered]@{
    _comment     = 'Written by .MD\scripts\kit-install.ps1. Every gate script finds <ROOT> from where it sits (anywhere under <ROOT>\.MD\scripts) or from the PIPELINE_ROOT environment variable, and every other file through <ROOT>\.MD\resolvers\resolve.py; this file records what was chosen. Secrets never go here - the Nexus key is the NEXUS_APIKEY environment variable.'
    kitVersion   = $kitVer
    root         = $Root
    mo2Instances = @($Mo2Instances)
    installed    = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
}
($cfg | ConvertTo-Json -Depth 3) | Set-Content -LiteralPath $cfgPath -Encoding UTF8
Write-Output "  ok  $cfgPath"

# the resolver, once every file it names exists: its INDEX.md (every role and what it resolves to on this machine),
# then its own check (a role whose file is missing fails it)
if ($py) {
    & py -3 (Join-Path $md 'resolvers\resolve.py') index --build | Out-Null
    $chk = @(& py -3 (Join-Path $md 'resolvers\resolve.py') check 2>&1 | ForEach-Object { "$_" })
    if ($LASTEXITCODE -eq 0) { Write-Output "  ok  resolve.py check: $($chk[-1])" }
    else { Write-Output "WARN  resolve.py check failed:"; $chk | ForEach-Object { Write-Output "        $_" } }
}

# environment
if (-not $NoEnv) {
    [Environment]::SetEnvironmentVariable('PIPELINE_ROOT', $Root, 'User')
    Write-Output "  ok  PIPELINE_ROOT = $Root (user environment; open a new shell to see it)"
    if ($Mo2Instances.Count -gt 0) {
        [Environment]::SetEnvironmentVariable('PIPELINE_MO2_INSTANCES', ($Mo2Instances -join ';'), 'User')
        Write-Output "  ok  PIPELINE_MO2_INSTANCES = $($Mo2Instances -join ';')"
    }
}
$env:PIPELINE_ROOT = $Root
if ($Mo2Instances.Count -gt 0) { $env:PIPELINE_MO2_INSTANCES = ($Mo2Instances -join ';') }

if ($SetGitHooks) {
    $hooks = Join-Path $md 'scripts\git-hooks'
    & git config --global core.hooksPath $hooks
    Write-Output "  ok  git core.hooksPath (global) = $hooks"
} else {
    Write-Output "      git hook not installed: run  git config --global core.hooksPath `"$md\scripts\git-hooks`"  (or rerun with -SetGitHooks)"
}

Write-Output ''
Write-Output "      Claude Code hooks not registered: run  py -3 `"$md\scripts\kit-hooks.py`" --apply  (it changes your settings.json - README-FOR-AI 3c)"
Write-Output "installed. Next: powershell -NoProfile -ExecutionPolicy Bypass -File `"$md\scripts\kit-selftest.ps1`""
exit 0
