<#
.SYNOPSIS
    Finalize a mod in ONE command, in the owner's order - working -> gate -> finalized -> distro: git and tag, the
    distro text, the gate ONCE, move into 10. finalized mods, zip, the zip into the distro folder with a post-check.
    Rule 21 / 34 / 10 as a single sequence; the clean-up of rule 23 runs when the version is recorded posted.

.DESCRIPTION
    Written 2026-09-30 after the owner asked "why is there no finalize script?" while Simple Loadout System 1.0.1 was
    finalized by hand: the checks (pre-finalize-check.ps1) and the distro sync (sync-nexus-distro.ps1) were scripts,
    the steps between them were not, and walking them by hand cost a hand-rolled zip and a sync given the repo key
    instead of the display name - it looked for a distro folder that does not exist, called the mod's 1.0.1 its "first
    finalize" and logged a false to-do entry.

    Reordered 2026-10-13 (straight flow B, the owner's decisions of 2026-10-12): the gate ran twice per finalize - once
    before the move, allowed to fail on two distro rows, and again after the sync - so the event log showed a gate
    re-run and a distro -> gate loop on every release. Now the gate runs ONCE and records ONE gate event, and the
    events are gate -> finalized -> distro-synced.

    Order, stopping at the first real failure:
      1. Resolve the mod from version-registry.json (key, repo folder, alias or display name) and the version
         (-Version, or the ledger's newest WORKING version).
      2. Git: the working tree clean and pushed (rule 9 - the gate checks it). The tag vX.Y.Z is only CHECKED here: one
         that exists at HEAD is left alone; one on ANOTHER commit (here or on origin) REFUSES before anything is
         written - moving a tag is a deliberate step for the owner, never done here. A missing tag is created after
         the gate (step 4b), so a refused gate leaves no tag behind (2026-10-13, Fable Advisor Agent).
      3. MODS_FINALIZE_RUN=<key>:<version>:<pid> is set for this run (sync-nexus-distro's gate A lets it through) and
         sync-nexus-distro.ps1 -Part Text brings the distro TEXT up to the candidate package: page version references,
         notes counter, changelog entry, banner pill. No zip, no event.
      4. pre-finalize-check.ps1 ONCE, in full - the one gate event. Every row is judged, page-version-matches
         included, with no tolerance; the one deferred row is distro-archive-equals-finalized-folder (-DeferRows), which
         needs the finalized zip and is step 6's post-check. A FAIL stops here and nothing is moved. (A FAIL
         acknowledged in PROGRESS.md for this version is honoured, rule 15.) Exit 3 - the gate refused to run again
         on inputs unchanged since its last refusal (gate C) - stops here too. -Force -Reason passes through to it.
     4b. The tag: created (annotated) at HEAD when missing and pushed to origin - the last git step before the move.
      5. Copy the package from 7. current test builds into 10. finalized mods and zip it beside the folder: forward
         slashes, top-level files first, every entry read back and compared with the folder.
      6. Copy the zip into the distro folder; POST-CHECK: the copy's SHA-256 equals the finalized zip's, and the
         finalized zip's entries equal the package folder (the deferred row's check). A failure removes the copied zip
         (Recycle Bin), prints the row's fix line and fails the finalize - not a second gate run, not a second gate
         event. Then sync-nexus-distro.ps1 -Part Zip clears other zips of this mod out of the distro folder.
      7. Record 'finalized', then 'distro-synced' ("zip copied, hash verified").
      8. Posting (2026-10-11: a number is spent by POSTING it): a 'local' mod's posting is recorded here (finalizing is
         its release); for the others it says which step records it (nexus-upload.py, the 1. members folder, Mega).
    No clean-up here: older finalized versions and old test builds are pruned when the version is recorded POSTED
    (version-gate.ps1 -Action posted runs post-release-prune.ps1 - the current release and one previous, rule 23).
    MODS_FINALIZE_RUN is cleared when the run ends. The banner is re-rendered by step 3; look at the PNG before
    posting (rule 6).

    -DryRun stops after step 3 (git and the text sync report what they would do, nothing is written); it does not run
    the gate, because the gate records an event.

.EXAMPLE
    .\finalize-mod.ps1 -Mod SimpleLoadoutSystemOR
    .\finalize-mod.ps1 -Mod "Tween Menu" -Version 1.0.1 -DryRun
#>
param(
    [Parameter(Mandatory = $true)][string]$Mod,
    [ValidatePattern('^\d+\.\d+\.\d+$')][string]$Version,
    [string]$Root = $env:PIPELINE_ROOT,
    [switch]$DryRun,
    # gate C's override, passed through to pre-finalize-check.ps1: run the gate although its inputs are unchanged since
    # its last refusal; -Reason is mandatory with it and goes into the gate event (note and refs.override)
    [switch]$Force,
    [string]$Reason
)
if ($Force -and -not "$Reason".Trim()) { Write-Output 'FAIL  -Force needs -Reason "<why the gate must run on unchanged inputs>" - it is written into the gate event.'; exit 2 }
$ErrorActionPreference = 'Stop'
if (-not $Root) { $_kitRoot = $PSScriptRoot; while ($_kitRoot -and (Split-Path $_kitRoot -Leaf) -ne '.MD') { $_kitRoot = Split-Path $_kitRoot -Parent }; if ($_kitRoot) { $_kitRoot = Split-Path $_kitRoot -Parent }; $Root = $_kitRoot }   # kit: <ROOT> is the folder above the .MD this script sits under, unless PIPELINE_ROOT says otherwise
# Every lookup goes through the resolver OF THIS TREE (STEPS 5.4), never the absolute <ROOT> path: a copied
# tree (the golden test) then answers inside its own copy. Each role is looked up ONCE, here, at start.
$ResolverPy = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\resolvers\resolve.py'))
function Find-Role([string]$role) {
    $p = @(& py -3 $ResolverPy find $role)
    if ($LASTEXITCODE -ne 0 -or $p.Count -eq 0 -or -not "$($p[0])".Trim()) { Write-Output "finalize-mod: cannot resolve role '$role' ($($p -join ' '))"; exit 1 }
    return "$($p[0])".Trim()
}
# The scripts folder its callees live in: role md-scripts (a callee that moved still answers through its stub or role).
$scripts = Find-Role 'md-scripts'
function Step($t) { Write-Output ''; Write-Output "== $t" }
function Fail($t) { Write-Output "FAIL  $t"; exit 1 }

# ---- 1. resolve ----------------------------------------------------------------------------------------------------
Step 'resolve'
$reg = Get-Content -LiteralPath (Join-Path $scripts 'version-registry.json') -Raw | ConvertFrom-Json
$key = $null
foreach ($p in $reg.PSObject.Properties) {
    $v = $p.Value
    if ($p.Name -ieq $Mod -or $v.repo -ieq $Mod -or $v.displayName -ieq $Mod -or (@($v.aliases) -contains $Mod)) { $key = $p.Name; break }
}
if (-not $key) { Fail "'$Mod' is not in version-registry.json (key, repo, display name or alias)." }
$e = $reg.$key
$display = [string]$e.displayName
$repo = Join-Path $Root "6. current wip mods\$($e.repo)"
if (-not $display) { Fail "$key has no displayName in the registry." }
if (-not (Test-Path -LiteralPath (Join-Path $repo '.git'))) { Fail "no git repo at $repo" }
if (-not $Version) {
    $ledger = Get-Content -LiteralPath (Join-Path $scripts 'version-ledger.json') -Raw | ConvertFrom-Json
    $Version = @($ledger | Where-Object { $_.mod -eq $key -and $_.status -eq 'working' } | ForEach-Object { [version]$_.version } |
                 Sort-Object -Descending | Select-Object -First 1) -join ''
    if (-not $Version) { Fail "the ledger has no WORKING version of $key - record one (version-gate.ps1 -Action record) first." }
}
$pkgName = "$display $Version"
# Packages sit in "<stage>\<Game> - <Mod>\" since 2026-10-01 (Resolve-PackageRoot, distro-names.ps1): the game is the
# registry entry's, so the Skyrim and the Oblivion Remastered release of one name never meet.
. (Find-Role 'distro-names')
$modGame = Get-ModGame -Entry $e -ProjectRoot $Root
$src = Join-Path (Resolve-PackageRoot -Root (Join-Path $Root '7. current test builds') -ModName $display -Game $modGame -ProjectRoot $Root) $pkgName
$finDir = Resolve-PackageRoot -Root (Join-Path $Root '10. finalized mods') -ModName $display -Game $modGame -ProjectRoot $Root
$dst = Join-Path $finDir $pkgName
# A FOMOD release is packaged as "<Mod> <version> FOMOD" (tools\build-fomod.py - AMF Skyrim); it is the one that ships
# when no plain package exists (2026-10-01, AMF 2.0.0 - the first FOMOD finalize through this tool).
if (-not (Test-Path -LiteralPath $src) -and -not (Test-Path -LiteralPath $dst) -and (Test-Path -LiteralPath "$src FOMOD")) {
    $pkgName = "$pkgName FOMOD"; $src = "$src FOMOD"; $dst = "$dst FOMOD"
}
# THE TEST-BUILD PICK (2026-10-13, Main Agent; test-build-pick.ps1, shared with version-gate.ps1 and
# pre-finalize-check.ps1). A version can have several folders in 7. current test builds - "<Mod> X.Y.Z", " FOMOD", and
# either with a " (...)" suffix. Simple Loadout System for Witcher 3 1.0.1: the plain folder held the OLD 1.0.0 files
# and "(inventory start-up fix)" the tested build, and this script took the plain one. Now the folder whose artefact
# matches the ledger's recorded working hash is the source; none or several matching refuses here, before anything is
# touched - a rename is for the owner, and no test-build folder is moved, renamed or deleted. The finalized folder is
# still named "<Mod> X.Y.Z[ FOMOD]": the suffix names a test round, not the release.
. (Find-Role 'test-build-pick')
$tbCands = @(Get-TestBuildCandidates -BuildsRoot (Join-Path $Root '7. current test builds') -Display $display -Version $Version -Game $modGame -ProjectRoot $Root)
if ($tbCands.Count -gt 1 -or ($tbCands.Count -eq 1 -and $tbCands[0].Name -match '\(')) {
    $wRow = @((Get-Content -LiteralPath (Join-Path $scripts 'version-ledger.json') -Raw | ConvertFrom-Json) | Where-Object { $_.mod -eq $key -and $_.version -eq $Version } | Select-Object -First 1)
    $wHash = if ($wRow.Count) { "$($wRow[0].sha256)" } else { '' }
    $wArts = if ($wRow.Count) { @(Get-RowArtifacts $wRow[0]) } else { @() }   # every listed artefact, when the row has them (2026-10-13)
    $sel = Select-TestBuild -Candidates $tbCands -Hash $wHash -Foreign @(@($e.foreignBinaries) | Where-Object { $_ }) -Artifacts $wArts
    if ($sel.Refused) { Fail $sel.Message }
    if ($sel.Message) { Write-Output "  $($sel.Message)" }
    $pkgName = "$display $Version$(if ($sel.Pick.Name -like "$display $Version FOMOD*") { ' FOMOD' })"
    $src = $sel.Pick.FullName
    $dst = Join-Path $finDir $pkgName
}
$zip = "$dst.zip"
Write-Output "  $key  ->  '$display' $Version   (repo $($e.repo), $(Split-Path $finDir -Leaf))   package '$pkgName'"
if (-not (Test-Path -LiteralPath $src) -and -not (Test-Path -LiteralPath $dst)) { Fail "no package '$pkgName' in 7. current test builds\$(Split-Path $finDir -Leaf) (package-mod.ps1 first)." }

# THE AGENT-LOCK GATE (the owner, 2026-10-12; .MD\agent-bus\README.md): one session builds or commits a mod repo at a
# time. A free or stale lock is taken, our own is refreshed, a LIVE lock held by ANOTHER session refuses (agent-lock exit
# 3). The lock this run took is released when it ends (the token: never a lock an outer call took). A missing or failing
# lock tool only warns (fail open).
function Invoke-AgentLock([string[]]$LockArgs) {
    $script:AgentLockRc = 0
    try {
        $al = "$(@(& py -3 $ResolverPy find agent-lock 2>$null)[0])".Trim()
        if (-not $al -or -not (Test-Path -LiteralPath $al)) { Write-Output 'agent-lock: WARNING role agent-lock not found - continuing without the lock'; return }
        & py -3 $al @LockArgs | ForEach-Object { Write-Output "$_" }
        $script:AgentLockRc = $LASTEXITCODE
        if (@(0, 3, 4) -notcontains $script:AgentLockRc) { Write-Output "agent-lock: WARNING the lock tool failed (exit $($script:AgentLockRc)) - continuing without the lock"; $script:AgentLockRc = 0 }
    } catch { Write-Output "agent-lock: WARNING $($_.Exception.Message) - continuing without the lock"; $script:AgentLockRc = 0 }
}
$LockToken = [guid]::NewGuid().ToString('N')
# each acquirer is its own holder (2026-10-25): the token goes to the tools this script starts (AGENT_LOCK_TOKENS),
# so their own lock calls refresh this lock instead of being refused
$env:AGENT_LOCK_TOKENS = (@($env:AGENT_LOCK_TOKENS, $LockToken) | Where-Object { $_ }) -join ';'
$LockRepo = "$($e.repo)"
if (-not $DryRun) {
    Invoke-AgentLock @('acquire', '--repo', $LockRepo, '--purpose', "finalize-mod $key $Version", '--token', $LockToken)
    if ($script:AgentLockRc -eq 3) { Fail "agent-lock: another session holds repo:$LockRepo - not finalizing" }
}
try {

# ---- 2. git ----------------------------------------------------------------------------------------------------------
Step 'git'
Push-Location $repo
try {
    if (git status --porcelain) { Fail "uncommitted changes in $($e.repo) - commit them first (rule 9)." }
    # borrowed-art mods): it is tagged here and nothing is fetched or pushed (2026-10-01 - the fetch threw and stopped
    # the finalize under $ErrorActionPreference Stop)
    $hasOrigin = $false   # kit: this kit pushes nothing and reads no remote; publishing the repo is the person's step
    # PUSHES PAUSED (the owner, 2026-10-06 - github-pushes-paused.txt beside this script): tag locally, push nothing
    $pushesPaused = Test-Path -LiteralPath (Join-Path $scripts 'github-pushes-paused.txt')
    if ($pushesPaused -and $hasOrigin) { Write-Output "  GitHub pushes are paused (github-pushes-paused.txt) - nothing is pushed; the tag stays local"; $hasOrigin = $false }
    $tag = "v$Version"
    # THE TAG (2026-10-13, straight flow B; created AFTER the gate since straight flow C, the Fable Advisor Agent's
    # ruling): a tag that already exists is never trusted blindly. At HEAD it is left as it is; on ANOTHER commit the
    # finalize refuses here, before anything is synced, gated or moved - the old code skipped an existing tag silently,
    # so a release could ship commits its tag does not hold. Moving a tag is a deliberate step for the owner: nothing
    # here deletes, moves or force-pushes one. A MISSING tag is not created here: it is created in step 4b, after the
    # gate passes, so a refused gate (fixed by a new commit) never leaves a tag on the old HEAD behind.
    $headCommit = "$(git rev-parse HEAD)".Trim()
    $tagFix = "move or delete tag $tag, or commit on top of it"
    $tagLocal = [bool](git tag -l $tag)
    if ($tagLocal) {
        $tagCommit = "$(git rev-list -n 1 $tag)".Trim()
        if ($tagCommit -ne $headCommit) {
            Fail "tag $tag already exists on commit $tagCommit, but HEAD is $headCommit - not finalizing (nothing was moved). Moving a tag is a deliberate step for the owner; finalize never moves or deletes one. Fix: $tagFix."
        }
        Write-Output "  tag $tag already exists at HEAD ($($headCommit.Substring(0, 12))) - left as it is"
    } else { Write-Output "  tag $tag does not exist yet - it is created after the gate passes" }
    $tagRemote = $false
    Write-Output "  ok  clean (this kit pushes nothing: push the repo and its tag yourself)"
} finally { Pop-Location }

# ---- 3. distro TEXT from the candidate package (no event) -----------------------------------------------------------
# THE STRAIGHT FLOW (the owner, 2026-10-12: working -> gate -> finalized -> distro). The text is synced BEFORE the gate,
# from the candidate package, so the gate judges the page the upload will carry. MODS_FINALIZE_RUN is what lets
# sync-nexus-distro.ps1 run for a version not yet in 10. finalized mods (its gate A); -Part Text leaves the zip alone and
# records no event - 'distro-synced' is written in step 7, after the zip is copied and verified.
Step 'Nexus distro text (from the candidate package)'
$env:MODS_FINALIZE_RUN = "${key}:${Version}:$PID"
$SyncScript = Find-Role 'sync-nexus-distro'   # by role, looked up once at its step
$global:LASTEXITCODE = 0
$sync = @(& $SyncScript -ModName $display -Version $Version -RepoPath $repo -Game $modGame -ProjectRoot $Root -Part Text -PackagePath $src -DryRun:$DryRun *>&1 | ForEach-Object { "$_" })
$syncExit = $LASTEXITCODE
$sync | Where-Object { $_ -match '^\[|NEEDS-CONTENT|SUMMARY|REFUSED|FAILED' }
if ($sync -match 'NEEDS-CONTENT-PASS') { Fail "no distro folder for '$display' - a first release needs its page written (rule 10). Nothing was gated or moved." }
if ($syncExit -ne 0) { Fail "the distro text sync failed (exit $syncExit) - nothing was gated or moved." }
$syncSummary = (@($sync | Where-Object { $_ -match '^SUMMARY:' }) | Select-Object -First 1) -replace '^SUMMARY:\s*', ''
if ($DryRun) { Write-Output ''; Write-Output "DRY RUN: stopped before the gate (it records an event). A real run gates '$pkgName' once, then copies, zips and copies the zip into the distro folder."; exit 0 }

# ---- 4. the gate, ONCE ------------------------------------------------------------------------------------------------
# pre-finalize-check.ps1 runs once, in full, and records the one gate event of this finalize; a FAIL stops here and
# nothing is moved. ONE package-gate row is deferred: distro-archive-equals-finalized-folder compares the distro's zip
# with the package, and that zip is the FINALIZED zip, which does not exist until step 5 - it is step 6's post-check
# (ruled by the Fable Advisor Agent, 2026-10-13). Every other row, page-version-matches included, is judged here after
# step 3's text sync, with no tolerance.
# The registry KEY goes to the check, never the display name: Skyrim's and Oblivion's "Apocrypha Menu Framework" share
# one, and the check took the first match - the Skyrim entry, 1.9.9 (2026-09-30).
$DeferredRows = @('distro-archive-equals-finalized-folder')
Step 'pre-finalize check (once)'
$PreFinalizeCheck = Find-Role 'pre-finalize-check'
# -FromFinalize (2026-10-22): the gate event carries refs.caller "finalize-mod", and gate C compares it only with this
# caller's last refusal - a standalone pre-finalize check run earlier can never block this finalize.
$pfcArgs = @{ ModName = $key; Version = $Version; RepoPath = $repo; ProjectRoot = $Root; DeferRows = $DeferredRows; FromFinalize = $true }
if (Test-Path -LiteralPath $src) { $pfcArgs['Package'] = $src }   # the folder the test-build pick chose (above)
if ($Force) { $pfcArgs['Force'] = $true; $pfcArgs['Reason'] = $Reason }   # gate C's override, recorded by the gate
$global:LASTEXITCODE = 0
$out = @(& $PreFinalizeCheck @pfcArgs *>&1 | ForEach-Object { "$_" })
$pfcExit = $LASTEXITCODE
# GATE C (2026-10-13): exit 3 = the gate refused to run again on inputs unchanged since its last refusal. It prints no
# [FAIL] lines (no check ran), so it is caught by its exit code, never read as a pass.
if ($pfcExit -eq 3) {
    $out | Where-Object { "$_".Trim() }
    Fail 'the gate refused to run again: nothing it reads has changed since its last refusal - nothing was moved. Fix the reasons above, repackage or re-record, then finalize again.'
}
# A FAIL the rules let through: "explicitly acknowledged and justified in PROGRESS.md". Honoured only when a heading
# "## Gate acknowledgement - <display> <version>, ... "<the check's name>" ..." exists for THIS version (2026-10-01, AMF
# 2.0.1 - the standing INISettingCollection deviation had no way past this tool).
$progressPath = Join-Path $Root '.MD\PROGRESS.md'
$ackHeads = @()
if (Test-Path -LiteralPath $progressPath) {
    $ackHeads = @(Get-Content -LiteralPath $progressPath | Where-Object { $_ -like '## Gate acknowledgement - *' -and $_ -like "*$display $Version*" })
}
$fails = @($out | Where-Object { $_ -match '^\[FAIL\]' } | Where-Object {
    $name = ([regex]::Match($_, '^\[FAIL\]\s*\([^)]*\)\s*(.+?)\s*$')).Groups[1].Value
    $acked = $name -and @($ackHeads | Where-Object { $_.Contains('"' + $name + '"') }).Count -gt 0
    if ($acked) { Write-Host "  acknowledged in PROGRESS.md: $name" }
    -not $acked
})
if ($fails.Count) {
    $out | Where-Object { $_ -match '^\[(FAIL|WARN)\]|^\s*!!|^\s+FAIL' }
    Fail 'the pre-finalize check failed - nothing was moved. Fix the reasons above, then finalize again.'
}
Write-Output ("  ok  0 FAIL (deferred to the post-check: {0})" -f ($DeferredRows -join ', '))

# ---- 4b. the tag, after the gate -----------------------------------------------------------------------------------
# THE TAG AFTER THE GATE (2026-10-13, straight flow C, the Fable Advisor Agent's ruling): the last git step before the
# move. Created (annotated) at HEAD when missing and pushed to origin; one already at HEAD (checked in step 2) is left as
# it is. Never forced, moved or deleted. The commits themselves were pushed before the gate (rule 9: the gate checks it).
Step 'tag (after the gate)'
Push-Location $repo
try {
    if (-not $tagLocal) {
        git tag -a $tag -m "$display $Version"
        if ($LASTEXITCODE -ne 0) { Fail "could not create tag $tag - nothing was moved." }
        Write-Output "  created tag $tag at HEAD ($($headCommit.Substring(0, 12)))"
    }
    if ($tagLocal -and ($tagRemote -or -not $hasOrigin)) { Write-Output "  ok  $tag already at HEAD - nothing to do" }
} finally { Pop-Location }

# ---- 5. move + zip -------------------------------------------------------------------------------------------------
Step 'finalized folder + zip'
if (-not (Test-Path -LiteralPath $finDir)) { New-Item -ItemType Directory -Path $finDir | Out-Null; Write-Output "  created 10. finalized mods\$(Split-Path $finDir -Leaf)" }
if (-not (Test-Path -LiteralPath $dst)) { Copy-Item -LiteralPath $src -Destination $dst -Recurse; Write-Output "  copied -> $dst" } else { Write-Output "  $pkgName already in 10. finalized mods\$(Split-Path $finDir -Leaf)" }
$py = @'
import os, sys, zipfile, hashlib
dst, zp = sys.argv[1], sys.argv[2]
files = []
for root, _, names in os.walk(dst):
    for n in names:
        full = os.path.join(root, n)
        files.append((full, os.path.relpath(full, dst).replace(os.sep, "/")))
files.sort(key=lambda f: ("/" in f[1], f[1]))
tmp = zp + ".tmp"
with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
    for full, arc in files:
        z.write(full, arc)
with zipfile.ZipFile(tmp) as z:
    for full, arc in files:
        if hashlib.sha256(z.read(arc)).digest() != hashlib.sha256(open(full, "rb").read()).digest():
            sys.exit("entry differs from the folder: " + arc)
    if any("\\" in n for n in z.namelist()):
        sys.exit("backslash in an entry name")
os.replace(tmp, zp)
print(f"  zip: {len(files)} entries, read back and matched")
'@
$pyFile = Join-Path $env:TEMP 'finalize-mod-zip.py'
Set-Content -LiteralPath $pyFile -Value $py -Encoding UTF8
$nexusDir = Resolve-DistroFolder -ModName $display -Game $modGame -ProjectRoot $Root
# SEVERAL DOWNLOADS (2026-11-12, Truly Nordic 1.1.0's four main files): with a nexus-files.json in the distro folder,
# each manifest entry's package subfolder is zipped as "<package> - <folder>.zip" beside the finalized folder (role
# nexus-files) and read back; there is no whole-package zip. Without the manifest nothing changes.
$multi = Test-Path -LiteralPath (Join-Path $nexusDir 'nexus-files.json')
if ($multi) {
    $nfPy = Find-Role 'nexus-files'
    & python $nfPy zip $dst $finDir $nexusDir
    if ($LASTEXITCODE -ne 0) { Fail 'a manifest zip did not verify - left the finalized folder in place; nothing was copied into the distro folder.' }
} else {
& python $pyFile $dst $zip
if ($LASTEXITCODE -ne 0) { Fail 'the zip did not verify - left the finalized folder in place; nothing was copied into the distro folder.' }
}

# ---- 6. the zip into the distro folder + the post-check -------------------------------------------------------------
# The deferred row, judged now: the zip copied into the distro folder has the SAME SHA-256 as the finalized zip, and the
# finalized zip's entries equal the package folder (the candidate the gate ran on; the finalized copy when the candidate
# is gone) - names and contents. A failure removes the copied zip (Recycle Bin, rule 50), prints the row's fix line and
# fails the finalize: it is not a second gate run and records no second gate event, and no 'finalized' or
# 'distro-synced' event either.
Step 'distro zip + post-check'
if ($multi) {
    # each manifest zip copied in, its SHA-256 checked against the finalized zip and its entries against its package
    # subfolder (the deferred row, per entry); a failure sends the copies to the Recycle Bin. Then every OTHER zip of
    # this mod in the distro folder goes to the Recycle Bin ("one zip per manifest entry", rule 10).
    $pkgFolder = if (Test-Path -LiteralPath $src) { $src } else { $dst }
    & python $nfPy publish $finDir $pkgFolder $nexusDir
    if ($LASTEXITCODE -ne 0) { Fail "the post-check failed (distro-archive-equals-finalized-folder) for a manifest zip - the finalized folder and zips stay in 10. finalized mods for a look; no 'finalized' or 'distro-synced' event was recorded." }
    & python $nfPy prune $nexusDir $display $Version --apply
    if ($LASTEXITCODE -ne 0) { Fail 'the distro zip clean-up (nexus_files.py prune) failed - see above.' }
    $zip = @(Get-ChildItem -LiteralPath $finDir -Filter "$pkgName - *.zip" -File | Sort-Object Name)[0].FullName   # step 8's -File for a kept-local mod
} else {
$distroZip = Join-Path $nexusDir (Split-Path $zip -Leaf)
Copy-Item -LiteralPath $zip -Destination $distroZip -Force
Write-Output "  copied -> $distroZip"
$pkgFolder = if (Test-Path -LiteralPath $src) { $src } else { $dst }
$postCheckPy = @'
import hashlib, os, sys, zipfile
fin, copy, pkg = sys.argv[1], sys.argv[2], sys.argv[3]
ROW = "[distro-archive-equals-finalized-folder]"
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()
bad = []
a, b = sha(fin), sha(copy)
if a != b:
    bad.append("the distro copy's SHA-256 %s is not the finalized zip's %s" % (b, a))
folder = {}
for root, _, names in os.walk(pkg):
    for n in names:
        full = os.path.join(root, n)
        folder[os.path.relpath(full, pkg).replace(os.sep, "/").lower()] = full
with zipfile.ZipFile(fin) as z:
    entries = {i.filename.lower(): i for i in z.infolist() if not i.is_dir()}
    for k in sorted(set(folder) - set(entries)):
        bad.append("the finalized zip lacks " + k)
    for k in sorted(set(entries) - set(folder)):
        bad.append("the finalized zip has extra file " + k)
    for k in sorted(set(folder) & set(entries)):
        if hashlib.sha256(z.read(entries[k])).digest() != hashlib.sha256(open(folder[k], "rb").read()).digest():
            bad.append("the finalized zip's " + k + " differs from the package folder")
for line in bad:
    print("  !!    " + ROW + " " + line)
if bad:
    sys.exit(1)
print("  ok  the distro copy's SHA-256 %s... is the finalized zip's; its %d entries equal the package folder" % (a[:16], len(entries)))
'@
$pcFile = Join-Path $env:TEMP 'finalize-mod-postcheck.py'
Set-Content -LiteralPath $pcFile -Value $postCheckPy -Encoding UTF8
& python $pcFile $zip $distroZip $pkgFolder
if ($LASTEXITCODE -ne 0) {
    Add-Type -AssemblyName Microsoft.VisualBasic
    if (Test-Path -LiteralPath $distroZip) { [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($distroZip, 'OnlyErrorDialogs', 'SendToRecycleBin') }
    Write-Output "  rolled back: the copied zip went to the Recycle Bin ($distroZip)"
    $rowFix = 'the archive the owner uploads must list exactly the files of the finalized folder'
    try {
        $row = @((Get-Content -LiteralPath (Find-Role 'gate-rules') -Raw -Encoding UTF8 | ConvertFrom-Json).rules | Where-Object { $_.id -eq 'distro-archive-equals-finalized-folder' })[0]
        if ($row.fix) { $rowFix = "$($row.fix)" } elseif ($row.why) { $rowFix = "$($row.why)" }
    } catch { }
    Write-Output "  fix: $rowFix"
    Fail "the post-check failed (distro-archive-equals-finalized-folder) - the finalized folder and zip stay in 10. finalized mods for a look; no second gate was run and no 'finalized' or 'distro-synced' event was recorded."
}
# The one-zip rule (rule 10) stays in the sync: -Part Zip finds the verified zip in place and sends every other zip of
# this mod in the distro folder to the Recycle Bin (an optional download of THIS version is kept). It records nothing.
$global:LASTEXITCODE = 0
$syncZip = @(& $SyncScript -ModName $display -Version $Version -RepoPath $repo -Game $modGame -ProjectRoot $Root -Part Zip *>&1 | ForEach-Object { "$_" })
$syncZipExit = $LASTEXITCODE
$syncZip | Where-Object { $_ -match '^\[' }
if ($syncZipExit -ne 0) { Fail "the distro zip clean-up (sync -Part Zip) failed (exit $syncZipExit) - see above." }
if (-not (Test-Path -LiteralPath $distroZip) -or (Get-FileHash -LiteralPath $distroZip -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash) {
    Fail "after the zip clean-up the distro folder no longer holds the verified $(Split-Path $zip -Leaf) - see the sync lines above."
}
}   # end of the one-zip branch of step 6 (the manifest branch is above)

# ---- 6b. optional downloads of THIS version (2026-10-14, AMF-W3 1.0.6) ----------------------------------------------
# A mod may ship extra downloads beside its main file - "<Mod> X.Y.Z - <label>" folders its package tool writes into
# 7. current test builds (AMF-W3: " - No Installer", " - No dinput8 (for TW3SE)"; the owner: the TW3SE-friendly build is
# "an additional file that says the no DLL or no dinput DLL version"). Until now they reached 10. finalized mods and the
# distro folder by hand. Each is copied, zipped and read back the same way as the main package, and its zip copied into
# the distro folder with a hash check; the one-zip clean-up above already keeps an optional zip of this version, and the
# Nexus tools take the main file by its plain name. A problem here is a WARNING: the main release is already finalized.
Step 'optional downloads'
$tbRoot = Resolve-PackageRoot -Root (Join-Path $Root '7. current test builds') -ModName $display -Game $modGame -ProjectRoot $Root
$optRx = '^' + [regex]::Escape("$display $Version") + ' - [^\d].*$'
$optional = @(if (Test-Path -LiteralPath $tbRoot) { Get-ChildItem -LiteralPath $tbRoot -Directory | Where-Object { $_.Name -match $optRx } })
if (-not $optional.Count) { Write-Output "  none (no '$display $Version - <label>' folder in 7. current test builds)" }
foreach ($o in $optional) {
    $oDst = Join-Path $finDir $o.Name
    $oZip = "$oDst.zip"
    if (-not (Test-Path -LiteralPath $oDst)) { Copy-Item -LiteralPath $o.FullName -Destination $oDst -Recurse; Write-Output "  copied -> $oDst" }
    & python $pyFile $oDst $oZip
    if ($LASTEXITCODE -ne 0) { Write-Output "  WARNING: the optional download '$($o.Name)' did not zip and verify - left out of the distro folder"; continue }
    $oDistro = Join-Path $nexusDir (Split-Path $oZip -Leaf)
    Copy-Item -LiteralPath $oZip -Destination $oDistro -Force
    if ((Get-FileHash -LiteralPath $oDistro -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $oZip -Algorithm SHA256).Hash) {
        Write-Output "  WARNING: the distro copy of '$($o.Name).zip' does not match the finalized zip - check it by hand"
    } else {
        Write-Output "  ok  optional download -> $oDistro"
    }
}

# ---- 7. record: finalized, then distro-synced ---------------------------------------------------------------------
# Never allowed to fail the finalize. The log had no 'finalized' after 2026-09-22 because finalizing moved into this
# script and nothing wrote it (2026-10-10). 'distro-synced' is written here, not by the sync, since the sync's two runs
# above record nothing: one event, after the zip is verified.
$plog = "$(@(& py -3 $ResolverPy find pipeline-log 2>$null)[0])".Trim()   # not Find-Role: its exit would fail a finished finalize
if ($plog -and (Test-Path -LiteralPath $plog)) {
    try { & $plog -Action record -Stage 10 -Event 'finalized' -Mod $display -Key $key -Version $Version -Evidence "finalize-mod.ps1: gate passed once, zip verified, $pkgName in 10. finalized mods" -By 'finalize-mod.ps1' | Out-Null } catch { }
    try { & $plog -Action record -Stage 11 -Event 'distro-synced' -Mod $display -Key $key -Version $Version -Evidence "zip copied, hash verified; text: $syncSummary" -By 'finalize-mod.ps1' | Out-Null } catch { }
}
# ---- 7b. the finalized build is the ACTIVE one in the test profile (2026-10-27) ---------------------------------------
# Item Explorer 1.2.0 was finalized while 1.1.4 and 1.1.3 stayed ticked in Njordlinger Test. Role profile-version-gate
# ticks the finalized version in the old version's position and unticks the old one, then checks the mod. Never fails a
# finished finalize: a refusal (MO2 open, the instance lock held) is a WARNING, and combined-run finish runs the fix.
try {
    $pvg = "$(@(& py -3 $ResolverPy find profile-version-gate 2>$null)[0])".Trim()
    if ($pvg -and $pvg -notlike 'MISSING*' -and (Test-Path -LiteralPath $pvg) -and -not $env:VERSION_GATE_NO_PROFILE) {
        Step 'test profile: the finalized version is the active one'
        & py -3 $pvg activate --mod $key --version $Version --reason 'finalize-mod' 2>&1 | ForEach-Object { "  $_" }
        & py -3 $pvg check --mod $key 2>&1 | ForEach-Object { "  $_" }
        if ($LASTEXITCODE -ne 0) { Write-Output "  WARNING the test profile does not run $key's current version - fix with: resolve.py run profile-version-gate fix --mod $key" }
    }
} catch { Write-Output "  WARNING profile-version-gate failed: $($_.Exception.Message)" }

# ---- 7c. the package render (2026-11-12, the owner: "re-render the package before posting it as part of the
# finalization process") --------------------------------------------------------------------------------------------
# A package that ships .nif files is rendered from the FINALIZED copy: every shipped NIF with its shipped DDS, the
# standard views and close-ups, the UV-stretch, engraving-layout and surface-profile gates, the sheets and
# package-render.json in the distro folder's assets\package-renders\<ver>\ (role package-render; Truly Nordic 1.1.0
# was posted with a stretched blade nobody saw, because every picture came from work meshes). nexus-upload.py refuses a
# model mod without a current, passing render (role package-render-gate). The finalize itself is done by now, so a
# FAILED render does not undo it: it ends the run with exit 4 - finalized, NOT postable.
$renderFailed = $false
try {
    $pr = "$(@(& py -3 $ResolverPy find package-render 2>$null)[0])".Trim()
    if ($pr -and $pr -notlike 'MISSING*' -and $pr -notlike 'NO SUCH*' -and (Test-Path -LiteralPath $pr)) {
        Step 'package render (model mods: the shipped NIFs and textures, rendered and gated)'
        & py -3 $pr --mod $key --version $Version 2>&1 | ForEach-Object { "  $_" }
        if ($LASTEXITCODE -eq 1) { $renderFailed = $true }
        elseif ($LASTEXITCODE -ne 0) { Write-Output "  WARNING the package render did not run (exit $LASTEXITCODE) - posting stays refused until it does: resolve.py run package-render --mod $key --version $Version"; $renderFailed = $true }
    }
} catch { Write-Output "  WARNING package-render failed: $($_.Exception.Message)"; $renderFailed = $true }

# ---- 8. posting: where the number is spent ---------------------------------------------------------------------------
# A number is spent by POSTING it (the owner, 2026-10-11), not by finalizing it: until the posting is recorded, the next
# change still goes in under this number. Finalizing IS the release only for a mod the registry marks publishChannel
# 'local' (kept local, rule 3 as amended 2026-09-28) - that posting is recorded here. Every other channel records it at
# its own step, and this says which.
Step 'posting'
$channel = "$($e.publishChannel)"
$optF = $null
try { $optF = Get-OptionalFileInfo -ModName $display -ProjectRoot $Root } catch { }
if ($optF) {
    # an optional file of another mod's page (registry optionalFileOf, 2026-10-19): its zip is in the PARENT's distro folder
    # and is posted as a file of the parent's page, by hand and under the owner's go-ahead (nexus-upload posts the page's
    # MAIN file only). Its own changelog is $($optF.changelog); the parent's page text, banner and sticky were not touched.
    Write-Output "  optional file of '$($optF.parent)': post the zip as that page's optional file (changelog text: $($optF.changelog)); nexus-upload posts the main file only, so this is a manual, go-ahead step - stage a PENDING-POST file in the distro folder. Then record it:  version-gate.ps1 -Action posted -Mod $key -Version $Version -Channel nexus -Evidence `"<file id>`""
} elseif ($e.nexusModId) {
    Write-Output "  Nexus page $($e.nexusModId): post the zip by hand, or build the optional upload tool (OPTIONAL-SCRIPTS.md); then record it: version-gate.ps1 -Action posted -Mod $key -Version $Version -Channel nexus."
} elseif ($channel -eq 'local') {
    $vg = Find-Role 'version-gate'
    & $vg -Action posted -Mod $key -Version $Version -Channel local -File $zip -Evidence "finalize-mod.ps1: kept local - finalized as $pkgName in 10. finalized mods (its release step)" | ForEach-Object { "  $_" }
} elseif ($channel -eq 'members') {
    Write-Output "  Members: copy the zip into 11. Nexus distro\1. members - the version gate reads that folder and records $Version POSTED."
} elseif ($channel -eq 'mega') {
    Write-Output "  Mega: after the upload, record it:  version-gate.ps1 -Action posted -Mod $key -Version $Version -Channel mega -File `"$zip`" -Evidence `"<Mega link>`""
} else {
    Write-Output "  no Nexus page linked and no publish channel: after the first post, 'version-gate.ps1 -Action link -Mod $key -NexusModId <id>' records it POSTED;"
    Write-Output "  a mod released elsewhere gets 'link -Channel mega|local|members' once. Until a posting is recorded, $Version stays the open number."
}

Write-Output ''
Write-Output "DONE  '$pkgName' finalized; 11. Nexus distro holds its zip, page and banner. Look at the banner PNG before posting."
if ($renderFailed) {
    Write-Output "NOT POSTABLE  the package render FAILED or did not run (see 'package render' above): fix the model and finalize again, or have the owner review the sheets - nexus-upload refuses until then."
    $script:finalizeExit = 4
}
} finally {
    $env:MODS_FINALIZE_RUN = $null   # the sync's finalize pass ends with this run
    if (-not $DryRun) { Invoke-AgentLock @('release', '--repo', $LockRepo, '--token', $LockToken) }
}
if ($script:finalizeExit) { exit $script:finalizeExit }
