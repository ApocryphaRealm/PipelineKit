<#
.SYNOPSIS
    THE version tool. Every piece of version logic in this project lives here, and every consumer
    (packaging, the finalize gate, the document bumps) calls this file instead of carrying its own.

.DESCRIPTION
    The owner, 2026-09-12: "I want the version logic to be in one file ... there's no need to have
    it in several different locations and I want the version logic to be tooling based only and I
    want it to be a logic gate where it fails if it doesn't pass the version logic gate."

    Before this file the logic was spread over version-ledger.ps1 (the record), set-version.ps1
    (the writer), check-version.ps1 (the checker), package-mod.ps1 (its own FileVersion guard),
    pre-finalize-check.ps1 (its own per-location checks) and the rollover arithmetic copied into
    docs-pipeline.ps1 and rules-version.ps1. The number itself was a free-typed parameter at every
    step and the ledger only advised. That produced duplicate ledger identities (AutoDraw and
    AutoDraw-SMF), mods finalized at 0.1.0 with no ledger line, a fork recorded under its upstream's
    number, and a failed build packaged under a new number.

    THE THREE PROPERTIES
    --------------------
    ONE FILE      All arithmetic, identity, writing, checking, recording and gating is here.
    TOOLING ONLY  A number is never typed. `bump` computes it from the ledger and writes it into
                  every location. `current` hands it to the packager. Anything typed by hand is
                  wrong until this tool agrees.
    A GATE        Every action exits non-zero and writes nothing when the logic is not satisfied:
                  an unregistered mod, a number the ledger did not issue, a binary whose stamped
                  version or hash does not match, a version literal in a file this tool was not
                  told about, a bump with no change kind. There is no -Force.

    THE RULES IT ENFORCES (rules 6, 7, 21, 48 - the rule text stays in the rules; this is the mechanism)
    ----------------------------------------------------------------------------------------------
    * SEMANTIC VERSIONING, MAJOR.MINOR.PATCH (the owner, 2026-10-21: "Update the versioning logic to use
      this", on a Nexus commenter's SemVer summary). The number says what KIND of change it is, and the
      kind is a REQUIRED argument of `bump` (-Kind) - there is no default, so no number is issued
      without someone deciding what the change is:
        patch  bug fixes, no compatibility change               1.2.4 -> 1.2.5
        minor  new functionality that stays backward compatible  1.2.4 -> 1.3.0  (patch resets to 0)
        major  a breaking change to the mod's public surface     1.2.4 -> 2.0.0  (minor and patch reset)
               (its API for other mods, its save/co-save format, INI keys or file layout users rely on)
      No component caps: 1.0.9 + patch = 1.0.10 and 1.9.0 + minor = 1.10.0 (the old roll-over at .9 is
      retired - it made a bug fix look like new functionality).
    * A NUMBER IS SPENT BY POSTING IT (the owner, 2026-10-11: "change the versioning logic from has to
      be proven working to get the number to has to be posted to Nexus. To get a new number.").
      NEXT = LAST POSTED stepped by the kind. A build that is not posted - untested, failed, scratch OR
      recorded working - keeps its number, and every further change of the same or a lower kind goes in
      under it ("open"); `bump` returns the open number instead of issuing a new one. When a change of
      a HIGHER kind arrives while a number is open (a fix build gains a feature), `bump` withdraws the
      open number and re-issues from the LAST POSTED number with the higher kind (posted 1.2.4, open
      1.2.5, bump -Kind minor -> 1.3.0). The open number's kind is read from the numbers themselves
      (which component moved above the last posted one). Everything at or below the last posted number is
      spent. "Posted" is the mod's publish step: the Nexus upload (nexus-upload.py records it; a
      linked page's published version is read on every action), the Pipeline Kit's copy into
      11. Nexus distro\1. members (read on every action once the registry says publishChannel
      members), and an explicit `posted` record for Mega or local-only releases.
    * A new mod starts at 1.0.0.
    * `working` is EARNED: it needs in-game evidence and the SHA-256 of the binary that ran, and
      that hash must match the packaged DLL for that version. It is still required to finalize and
      to post; it no longer moves the counter. A rebuild packaged under an open number that had been
      recorded working goes back to untested by itself (the package gate sees the new hash).
    * One identity per mod: a registry maps ledger key <-> repo folder <-> display name <-> aliases.

    DATA
    ----
    version-registry.json   identity and the version locations of every mod (written by register)
    version-ledger.json     the record: {mod, version, status, evidence, sha256[, artifacts], recorded[, posted]}
                            artifacts = [{file, sha256}] - every artefact of the package 'record working' compared with
                            (2026-10-13); the finalize gate then checks each one. Rows without it are judged on sha256.
                            posted = {at, channel nexus|members|mega|local|modio|unknown, ref, file, sha256, evidence};
                            'unknown' was written only by the 2026-10-11 backfill, on the last working build of
                            a mod whose posting could not be determined, so nothing is ever issued twice
                            prunePending = true (2026-10-13): the posting was NEW in that ledger write and its clean-up
                            (post-release-prune) has not run yet - the next posted, bump or record of the mod runs it and
                            removes the field (THE CLEAN-UP TRIGGER, below Log-Event)

    ACTIONS
    -------
    register   -Mod KEY -Repo FOLDER -DisplayName NAME [-Alias a,b] [-Ignore file:line,..] [-NexusModId N]   create the identity; scans the repo for version locations
    register   -Mod KEY -DisplayName NAME -NoRepo -Evidence "why there is no repo, where it is built"
                                                                     (2026-10-25) a released mod with NO source repo under 6. current wip mods
                                                                     (HIMBO for Nord Hero: a generated BodySlide package). It holds no version
                                                                     locations, so bump/stamp/gate refuse it by name; its page is linked and
                                                                     audited like any other. The evidence is kept as the entry's 'noRepo' note
    unregister -Mod KEY                                                remove an identity that never issued a version (refuses if the ledger holds any)
    link       -Mod X -NexusModId N [-Domain D]                        attach OUR Nexus page; from then on its published version counts as POSTED
                                                                     (-Domain: the page's game section when the registry cannot infer it)
    link       -Mod X -NexusModId N -Domain D -Additional              (2026-10-25) a SECOND page of the same mod - the Modding Tools copy
                                                                     (site) of an MO2 plugin whose main page is in skyrimspecialedition. It
                                                                     is appended to the entry's 'nexusPages' list [{nexusDomain, nexusModId,
                                                                     linked}]: nexus-version-audit and the AI-tags gate check it as a page of
                                                                     its own; the ledger's posted floor still reads the main page only
    link       -Mod X -Channel members|mega|local                      a mod with no Nexus page: how it is published (members is read from 1. members by itself)
    nexus      [-Mod X]                                                re-read Nexus now (every action also reads it, cached for an hour)
    seed       -Mod X -Version V -Evidence "..." [-Dll path]           first WORKING entry for a mod whose working builds predate the ledger
    renumber   -Mod X -Version V -Evidence "the owner's words"        the OWNER sets the number (above the last posted one); the open number is withdrawn
    reopen     -Mod X [-Version V]                                     RETIRED 2026-10-11, kept as a no-op: an unposted number is open by itself; prints the
                                                                     open number, refuses a posted one
    restart    -Mod X -Evidence "the owner's words"                    an UNRELEASED mod's first release is 1.0.0: its pre-release ledger entries move to
                                                                     version-ledger-prerelease.json, so the next bump issues 1.0.0; refused when Nexus
                                                                     has any version of it, a version of it is recorded posted, or a vX.Y.Z tag is
                                                                     still in the repo (local or pushed)
    next       -Mod X [-Kind K]                                        print the open number, or the next number for each kind (or for K) (no write)
    bump       -Mod X -Kind patch|minor|major [-WhatIf]                the open number if there is one and K is not higher than its kind (failed/scratch ->
                                                                     untested again); else LAST POSTED stepped by K, recorded untested (a higher K
                                                                     withdraws the open number); writes EVERY location; prints it. No -Kind: refused
    current    -Mod X                                                  the open (untested or working) number the packager must use
    stamp      -Mod X [-Version V]                                     every location and the built DLL agree (and equal V if given)
    record     -Mod X -Version V -Status S [-Evidence ..] [-Sha256 ..|-Dll path]
    posted     -Mod X -Version V -Evidence "<file id / URL / link>" [-Channel C] [-FileId id] [-File archive] [-WhatIf]
                                                                     -Channel modio (2026-10-15): the mod.io file; -File (the archive uploaded to
                                                                     mod.io) is required, and the version's WORKING hash must be that archive's
                                                                     or a file inside it - a mod.io posting never carries another build's hash
                                                                     the number is SPENT: needs a WORKING record; -WhatIf checks without writing;
                                                                     a NEW posting runs the clean-up (post-release-prune) after it is recorded
                                                                     (nexus-upload.py runs it before and after an upload); -Backfill (the backfill only)
                                                                     also takes a published version the ledger never knew or holds as non-working
    retract    -Mod X -Version V -Evidence "why the posted claim is wrong" [-WhatIf]
                                                                     (2026-10-25) a row's POSTED claim was wrong (the backfill read a page version
                                                                     of '1' as 1.0.0 when the file up was 1.0.1): the claim is taken off the row and
                                                                     kept under 'retracted' [{at, evidence, was}]; the row's status is unchanged. Nexus
                                                                     is re-read first and the action refuses while the linked page publishes V.
                                                                     Event kind 'posted-retracted'; the floor is then the highest claim left
    backfill   [-From audit.json] [-WhatIf]                          mark what is already out as posted: Nexus page + main file version (the audit's
                                                                     JSON, run here when -From is not given), the members folder, posted events; where
                                                                     nothing says, the last working build is 'posted: unknown'. Never lowers a floor
    gate       -Mod X -Version V -Stage package|finalize [-Dll path]   THE GATE - exit 0 passes, anything else stops the caller; finalize
                                                                     refuses a vX.Y.Z tag that exists on another commit than HEAD
                                                                     (a missing tag is fine: finalize-mod tags after the gate)
    nextnumber -From X.Y.Z -Kind patch|minor|major                     pure arithmetic for the document tooling (docs-pipeline, rules-version)
    list | status

    EXIT CODES: 0 pass, 1 gate failed / bad input, 2 unregistered mod.
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('register','rename','unregister','link','nexus','seed','next','bump','renumber','reopen','restart','current','stamp','record','posted','retract','backfill','gate','nextnumber','list','status')]
    [string]$Action,
    [ValidateSet('nexus','members','mega','local','modio','unknown')][string]$Channel,
    [string]$FileId,
    [string]$File,
    [switch]$Backfill,
    [int]$NexusModId,
    [ValidateSet('skyrimspecialedition','oblivionremastered','witcher3','site')][string]$Domain,
    [switch]$Additional,
    [switch]$NoRepo,
    [string]$Mod,
    [string]$Version,
    [ValidateSet('working','failed','untested','scratch')][string]$Status,
    [string]$Evidence,
    # register: the prior-art search for a new mod (owner, 2026-11-01), a file naming what was searched on Nexus and GitHub
    [string]$PriorArt,
    [string]$Sha256,
    [string]$Dll,
    [string]$Repo,
    [string]$DisplayName,
    [string[]]$Alias,
    [string[]]$Ignore,
    [ValidateSet('package','finalize')][string]$Stage,
    [ValidateSet('patch','minor','major')][string]$Kind,
    [string]$From,
    [string]$Root = $env:PIPELINE_ROOT
)

$ErrorActionPreference = 'Stop'
if (-not $Root) { $_kitRoot = $PSScriptRoot; while ($_kitRoot -and (Split-Path $_kitRoot -Leaf) -ne '.MD') { $_kitRoot = Split-Path $_kitRoot -Parent }; if ($_kitRoot) { $_kitRoot = Split-Path $_kitRoot -Parent }; $Root = $_kitRoot }   # kit: <ROOT> is the folder above the .MD this script sits under, unless PIPELINE_ROOT says otherwise
# Every lookup goes through the resolver OF THIS TREE (STEPS 5.4), never the absolute <ROOT> path: a copied
# tree (the golden test) then answers inside its own copy. Each role is looked up ONCE, here, at start.
$ResolverPy = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\resolvers\resolve.py'))
# -AllowMissing: a role whose file may not exist yet (the pre-release archive, the pipeline log in a copied tree) still
# answers with its path, as the old Join-Path did; the caller already tests for the file.
function Find-Role([string]$role, [switch]$AllowMissing) {
    $p = @(& py -3 $ResolverPy find $role)
    if ($AllowMissing -and "$($p[0])" -match '^MISSING \S+ -> (.+)$') { return $Matches[1].Trim() }
    if ($LASTEXITCODE -ne 0 -or $p.Count -eq 0 -or -not "$($p[0])".Trim()) { Write-Output "version-gate: cannot resolve role '$role' ($($p -join ' '))"; exit 1 }
    return "$($p[0])".Trim()
}
$LedgerPath   = Find-Role 'version-ledger'
$RegistryPath = Find-Role 'version-registry'
$PrereleasePath = Find-Role 'version-ledger-prerelease' -AllowMissing
$DistroNamesPath = Find-Role 'distro-names'
$TestBuildPickPath = Find-Role 'test-build-pick'   # which test-build folder is the version's build (2026-10-13)
$PipelineLogPath = Find-Role 'pipeline-log' -AllowMissing
$WipRoot      = Join-Path $Root '6. current wip mods'
$BuildsRoot   = Join-Path $Root '7. current test builds'
$VERSION_RE   = '^\d+\.\d+\.\d+$'
$EXCLUDE_RE   = '\\(build[^\\]*|_build[^\\]*|out|vcpkg_installed|\.git|\.xmake|\.vs|\.claude|extern|external|deps|third_party|node_modules|_deps)\\|\.lock\\'
$script:Failures = New-Object System.Collections.Generic.List[string]

function Fail([string]$msg, [int]$code = 1) { Write-Output ("FAIL  {0}" -f $msg); exit $code }
function Ok([string]$msg)   { Write-Output ("  ok  {0}" -f $msg) }
function Note([string]$msg) { Write-Output ("      {0}" -f $msg) }
function Flag([string]$msg) { $script:Failures.Add($msg); Write-Output ("  !!  {0}" -f $msg) }

# --- data ---------------------------------------------------------------------------------------
function Load-Ledger {
    if (-not (Test-Path -LiteralPath $LedgerPath)) { return @() }
    $l = Get-Content -LiteralPath $LedgerPath -Raw | ConvertFrom-Json
    if ($null -eq $l) { return @() }
    if ($l -isnot [array]) { $l = @($l) }
    return $l
}
function Save-Ledger($data) {
    if ($PSCmdlet.ShouldProcess($LedgerPath, 'write ledger')) {
        Mark-NewPostings $data   # THE CLEAN-UP TRIGGER (2026-10-13): a posting new in this write is marked prunePending
        Write-LedgerView 'version-ledger' $LedgerPath (($data | ConvertTo-Json -Depth 5))
    }
}
# THE LOG IS THE SOURCE (step 7 of the one-event-log design, SIMPLIFY-3, switched over 2026-10-12 on the owner's second
# yes). A ledger write no longer writes the file: the rows this tool would have written go to role `events`
# (`events.py materialize`), which records one v2 event per row that changed - the whole row, refs.source =
# "<file>#<index>" - and then WRITES THE FILE FROM THE FOLD of the log, refusing unless the fold equals those rows.
# Every reader (this gate's refusals included) reads the same file as before; only its author changed.
# FALLBACK: when events.py cannot run or refuses, the file is written directly from the same text, exactly as before
# the switch-over, and a warning says so - a ledger write is never lost. `events.py check --view <view>` then shows the
# row the log is missing. ROLLBACK (to the old writers): docs-archive\event-log-baseline-2-2026-10-12\README.md.
function Write-LedgerView([string]$view, [string]$target, [string]$json) {
    $keepExit = $global:LASTEXITCODE
    $tmp = Join-Path $env:TEMP ("version-gate-proposed-{0}.json" -f [guid]::NewGuid().ToString('N'))
    try {
        Set-Content -LiteralPath $tmp -Value $json -Encoding UTF8
        $out = @()
        $code = 1
        try { $out = @(& py -3 $ResolverPy run events materialize --view $view --proposed $tmp --target $target --by version-gate 2>&1); $code = $global:LASTEXITCODE } catch { $code = 1 }
        if ($code -ne 0) {
            Copy-Item -LiteralPath $tmp -Destination $target -Force
            $said = @($out | Where-Object { "$_" -match 'materialize FAILED' })
            if ($said.Count) { Write-Warning ("event log: {0} written directly - {1}" -f $view, "$($said[0])".Trim()) }
        }
    } finally {
        if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue }
        $global:LASTEXITCODE = $keepExit
    }
}
# DUAL WRITE (step 4 of the one-event-log design, SIMPLIFY-3, 2026-10-12). Every write of the version ledger or the
# pre-release archive ALSO records, through role `events` (`events.py mirror`), one v2 event per row that changed -
# the whole row as written, refs.source = "<file>#<index>" - so `events.py fold version-ledger` rebuilds the file and
# `events.py check --view version-ledger` compares the two. The ledger is written exactly as before and stays what every
# action reads; nothing here can change a refusal, an exit code or a number. A failed mirror is silent.
function Copy-ForMirror([string]$file) {
    try {
        $copy = Join-Path $env:TEMP ("version-gate-mirror-{0}.json" -f [guid]::NewGuid().ToString('N'))
        if (Test-Path -LiteralPath $file) { Copy-Item -LiteralPath $file -Destination $copy -Force }
        return $copy   # a copy that does not exist means "the file was empty"
    } catch { return $null }
}
function Write-MirrorEvents([string]$view, [string]$before, [string]$after) {
    if (-not $before) { return }
    $keepExit = $global:LASTEXITCODE
    try { $null = @(& py -3 $ResolverPy run events mirror --view $view --before $before --after $after --by version-gate 2>$null) } catch { }
    finally {
        if (Test-Path -LiteralPath $before) { Remove-Item -LiteralPath $before -Force -ErrorAction SilentlyContinue }
        $global:LASTEXITCODE = $keepExit
    }
}
function Load-Registry {
    if (-not (Test-Path -LiteralPath $RegistryPath)) { return [pscustomobject]@{} }
    $r = Get-Content -LiteralPath $RegistryPath -Raw | ConvertFrom-Json
    if ($null -eq $r) { return [pscustomobject]@{} }
    return $r
}
function Save-Registry($reg) {
    if ($PSCmdlet.ShouldProcess($RegistryPath, 'write registry')) {
        ($reg | ConvertTo-Json -Depth 6) | Set-Content -LiteralPath $RegistryPath -Encoding UTF8
    }
}
function Registry-Keys($reg) { return @($reg.PSObject.Properties | ForEach-Object { $_.Name }) }
# A registered mod's repo folder; a -NoRepo entry (2026-10-25) is refused by name instead of joining a null path.
function Repo-Path([string]$key, $e) {
    if (-not "$($e.repo)") { Fail ("'{0}' has no source repo - nothing to bump, stamp or gate ({1})" -f $key, $(if ($e.noRepo) { $e.noRepo } else { 'registered with -NoRepo' })) }
    return (Join-Path $WipRoot $e.repo)
}
# Every Nexus page linked anywhere in the registry: the main page (nexusModId) and the additional pages (nexusPages).
function Linked-Pages($reg) {
    foreach ($k in (Registry-Keys $reg)) {
        $e = $reg.$k
        if ($e.nexusModId) { [pscustomobject]@{ key = $k; domain = (Get-NexusDomain $e); id = [int]$e.nexusModId } }
        foreach ($p in @($e.nexusPages)) { if ($p -and $p.nexusModId) { [pscustomobject]@{ key = $k; domain = "$($p.nexusDomain)"; id = [int]$p.nexusModId } } }
    }
}

# --- identity -----------------------------------------------------------------------------------
function Resolve-Key([string]$name, $reg) {
    if (-not $name) { Fail '-Mod is required.' }
    foreach ($k in (Registry-Keys $reg)) {
        $e = $reg.$k
        $hit = ($k -ieq $name) -or ($e.repo -ieq $name) -or ($e.displayName -ieq $name) -or
               (@(@($e.aliases) | Where-Object { $_ -and ($_ -ieq $name) }).Count -gt 0)
        if ($hit) { $script:ForeignBinaries = @(@($e.foreignBinaries) | Where-Object { $_ }); return $k }
    }
    Write-Output ("FAIL  '{0}' is not a registered mod. Nothing is versioned until it is registered:" -f $name)
    Write-Output ("      version-gate.ps1 -Action register -Mod <Key> -Repo <folder under 6. current wip mods> -DisplayName '<package name>'")
    exit 2
}

# --- arithmetic ---------------------------------------------------------------------------------
function Parse-Version([string]$v) {
    if (-not $v) { return $null }
    $m = [regex]::Match($v, '(\d+)\.(\d+)\.(\d+)')
    if (-not $m.Success) { return $null }
    return [version]('{0}.{1}.{2}' -f $m.Groups[1].Value, $m.Groups[2].Value, $m.Groups[3].Value)
}
function Next-Number([version]$v, [string]$kind) {
    # Rule 6, SEMANTIC VERSIONING (the owner, 2026-10-21): the KIND of change picks the component. No component caps -
    # 1.0.9 + patch = 1.0.10 (the old roll-over at .9 is retired; it made a fix look like new functionality).
    switch ($kind) {
        'major' { return [version]('{0}.0.0' -f ($v.Major + 1)) }
        'minor' { return [version]('{0}.{1}.0' -f $v.Major, ($v.Minor + 1)) }
        'patch' { return [version]('{0}.{1}.{2}' -f $v.Major, $v.Minor, ($v.Build + 1)) }
    }
    Fail ("internal: Next-Number was called without a change kind (patch|minor|major) for {0}." -f $v)
}
function Kind-Rank([string]$k) { switch ($k) { 'patch' { return 1 } 'minor' { return 2 } 'major' { return 3 } }; return 0 }
function Kind-Of($floor, [version]$v) {
    # the change kind an OPEN number carries over the last posted one, read from the numbers: which component moved.
    # Nothing posted yet: the first release covers every kind of change (it is 1.0.0, or the number already in flight).
    if ($null -eq $floor) { return 'major' }
    if ($v.Major -ne $floor.Major) { return 'major' }
    if ($v.Minor -ne $floor.Minor) { return 'minor' }
    return 'patch'
}
function Candidates-Text($floor) {
    # what each kind would issue from the last posted number - for messages where no kind was given
    if ($null -eq $floor) { return '1.0.0' }
    return ('{0} (patch) | {1} (minor) | {2} (major)' -f (Next-Number $floor 'patch'), (Next-Number $floor 'minor'), (Next-Number $floor 'major'))
}
function Require-Kind([string]$what) {
    if ($Kind) { return }
    Fail ("{0} needs -Kind patch|minor|major - there is no default (rule 6, semantic versioning):`n" -f $what +
          "      patch  bug fixes only, nothing a user or another mod relies on changes        1.2.4 -> 1.2.5`n" +
          "      minor  new functionality (a feature, a setting, an API call) - old setups keep working  1.2.4 -> 1.3.0`n" +
          "      major  a breaking change: another mod's calls, saves/co-saves, INI keys or file layout users rely on stop working  1.2.4 -> 2.0.0")
}
function Assert-Shape([string]$v) {
    if ($v -notmatch $VERSION_RE) { Fail ("'{0}' is not X.Y.Z." -f $v) }
    return [version]$v
}
function Last-Working([string]$key, $ledger) {
    $vs = @($ledger | Where-Object { $_.mod -eq $key -and $_.status -eq 'working' } | ForEach-Object { Parse-Version $_.version } | Where-Object { $_ })
    if ($vs.Count -eq 0) { return $null }
    return ($vs | Sort-Object -Descending | Select-Object -First 1)
}
# --- posted: a number is spent by POSTING it (the owner, 2026-10-11) ------------------------------
# "change the versioning logic from has to be proven working to get the number to has to be posted to Nexus. To get a
# new number." - said when AMF for Witcher 3 1.0.5 was recorded working but not posted and the next group of features
# was being called 1.0.6: "We haven't even posted 1.0.5 yet. How can there be a 1.0.6?" Before this, NEXT was LAST
# WORKING + 1 and an unposted number had to be 'reopen'ed by hand to take more changes.
function Posted-Of($row) {
    if ($row -and $row.PSObject.Properties['posted'] -and $row.posted) { return $row.posted }
    return $null
}
function Set-Posted($row, $obj) {
    if ($row.PSObject.Properties['posted']) { $row.posted = $obj } else { $row | Add-Member -NotePropertyName posted -NotePropertyValue $obj }
}
function New-Posted([string]$channel, [string]$ref, [string]$file, [string]$sha, [string]$evidence) {
    return [pscustomobject]@{
        at       = $(if ($channel -eq 'unknown') { $null } else { (Get-Date).ToString('yyyy-MM-dd HH:mm:ss') })
        channel  = $channel
        ref      = $(if ($ref) { $ref } else { $null })
        file     = $(if ($file) { $file } else { $null })
        sha256   = $(if ($sha) { $sha.ToUpper() } else { $null })
        evidence = $evidence
    }
}
function Last-Posted([string]$key, $ledger) {
    # THE FLOOR: the highest number that has left the machine - a ledger row marked posted (any channel, 'unknown'
    # included) or the version the mod's linked Nexus page publishes. A number already out is never lowered.
    $vs = @($ledger | Where-Object { $_.mod -eq $key -and (Posted-Of $_) } | ForEach-Object { Parse-Version $_.version } | Where-Object { $_ })
    if ($reg -and $reg.PSObject.Properties[$key]) { $nx = Parse-Version "$($reg.$key.nexusVersion)"; if ($nx) { $vs += $nx } }
    if ($vs.Count -eq 0) { return $null }
    return ($vs | Sort-Object -Descending | Select-Object -First 1)
}
function Floor-Is-Unknown([string]$key, $ledger, $floor) {
    # true when the floor stands only on a backfill 'posted: unknown' row (shown as '1.0.4?' by status)
    if ($null -eq $floor) { return $false }
    if ($reg -and $reg.PSObject.Properties[$key] -and (Parse-Version "$($reg.$key.nexusVersion)") -eq $floor) { return $false }
    $r = @($ledger | Where-Object { $_.mod -eq $key -and (Parse-Version $_.version) -eq $floor -and (Posted-Of $_) })
    return ($r.Count -gt 0 -and @($r | Where-Object { (Posted-Of $_).channel -ne 'unknown' }).Count -eq 0)
}
function Open-Entry([string]$key, $ledger) {
    # THE OPEN NUMBER: the highest ledger row above the last posted number that is not withdrawn - untested, failed,
    # scratch or recorded working. It keeps its number until it is posted, and every change goes in under it.
    $fl = Last-Posted $key $ledger
    $rows = @($ledger | Where-Object { $_.mod -eq $key -and $_.status -ne 'withdrawn' -and -not (Posted-Of $_) } |
              Where-Object { $v = Parse-Version $_.version; $v -and (($null -eq $fl) -or ($v -gt $fl)) })
    if ($rows.Count -eq 0) { return $null }
    return ($rows | Sort-Object { Parse-Version $_.version } -Descending | Select-Object -First 1)
}
function Expected-Number([string]$key, $ledger) {
    # the number the next build carries when no kind is needed to say it: the open one, else 1.0.0 for a mod with nothing
    # out. $null when something is posted and nothing is open - then the number depends on the change kind (bump -Kind).
    $o = Open-Entry $key $ledger
    if ($o) { return (Parse-Version $o.version) }
    $fl = Last-Posted $key $ledger
    if ($null -eq $fl) { return [version]'1.0.0' }
    return $null
}
function Expected-Text([string]$key, $ledger) {
    # for messages and tables: the open number, else 1.0.0, else what each kind would issue
    $e = Expected-Number $key $ledger
    if ($e) { return $e.ToString() }
    $fl = Last-Posted $key $ledger
    return ('{0}/{1}/{2}' -f (Next-Number $fl 'patch'), (Next-Number $fl 'minor'), (Next-Number $fl 'major'))
}
function Log-Event([int]$stage, [string]$event, [string]$key, [string]$ver, [string]$ev) {
    if ($WhatIfPreference) { return }
    $plog = $PipelineLogPath
    if ($plog -and (Test-Path -LiteralPath $plog)) { try { & $plog -Action record -Stage $stage -Event $event -Mod $key -Key $key -Version $ver -Evidence $ev -By 'version-gate.ps1' | Out-Null } catch { } }
}
# THE POST-RELEASE PRUNE (2026-10-13, straight flow B): once a posting is recorded, the clean-up finalize-mod.ps1 used
# to do runs by itself - role post-release-prune keeps the current release and one previous in 10. finalized mods
# (rule 23) and prunes the mod's test builds; it records one 'pruned' event (kind prune) naming what it kept and what
# went to the Recycle Bin. Never under -WhatIf, and it never fails the action: a problem is a WARNING. $script:PruneOk
# says whether it ran clean (a return value would carry the prune's printed lines with it).
$script:PruneOk = $false
function Invoke-PostReleasePrune([string]$key, [string]$ver) {
    $script:PruneOk = $false
    if ($WhatIfPreference) { return }
    try {
        $pp = "$(@(& py -3 $ResolverPy find post-release-prune 2>$null)[0])".Trim()
        if (-not $pp -or $pp -like 'MISSING*' -or -not (Test-Path -LiteralPath $pp)) { Write-Output "WARNING post-release-prune: the role's script was not found - nothing pruned; the posting is recorded and the clean-up of $key $ver stays pending (resolve.py explain post-release-prune)"; return }
        $global:LASTEXITCODE = 0
        & $pp -Mod $key -Version $ver -Root $Root 2>&1 | ForEach-Object { "$_" }
        if ($LASTEXITCODE -ne 0) { Write-Output "WARNING post-release-prune exited $LASTEXITCODE - the posting is recorded and the clean-up of $key $ver stays pending (the next posted, bump or record tries again)"; return }
        $script:PruneOk = $true
    } catch { Write-Output "WARNING post-release-prune failed: $($_.Exception.Message) - the posting is recorded and the clean-up of $key $ver stays pending" }
}
# THE CLEAN-UP TRIGGER (2026-10-13, ruled by the Fable Advisor Agent). The post-release prune used to run from the
# 'posted' action only, so a posting recorded any other way - Sync-Members reading 11. Nexus distro\1. members,
# Sync-Nexus reading a hand-made upload off the Nexus page - never cleaned up. The trigger is now in ONE place: the
# ledger write that first gives a (mod, version) a posting (Posted-Of goes from none to some). Save-Ledger compares the
# rows it is about to write with the ledger on disk and marks every row whose posting is new with prunePending = true,
# in that same write - so the flag is part of the row and lives in the event log as well (events.py materialize records
# the whole row). 'posted', finalize-mod's local record (which goes through 'posted'), Sync-Members and Sync-Nexus all
# reach it through that one line; a posting the ledger already held (a re-post, an 'unknown' backfill row given its
# channel) is not new and never fires it.
# Only the WRITING actions - posted, bump, record - run a clean-up: Invoke-PendingCleanups runs every pending one of
# their mod (oldest version first) and then clears the flag through another ledger write. Every other action - the
# read-only ones (gate, current, next, status, list - the finalize gate's version-gate run among them) and the rest
# (link, nexus, backfill, seed, renumber...) - records the posting and prints "clean-up pending for <mod> <version>;
# runs at the next posted or bump". Never under -WhatIf: no ledger write happens then, so nothing is marked or run.
# A clean-up that fails is a WARNING; the action's exit code is unchanged and the flag stays for the next try.
$script:WritingActions = @('posted', 'bump', 'record')
function Mark-NewPostings($data) {
    $known = @{}
    if (Test-Path -LiteralPath $LedgerPath) {
        $disk = $null
        try { $disk = Get-Content -LiteralPath $LedgerPath -Raw | ConvertFrom-Json } catch { return }
        foreach ($r in $disk) { if ($r -and (Posted-Of $r)) { $known["$($r.mod)|$($r.version)"] = $true } }
    }
    foreach ($r in @($data)) {
        if (-not $r -or -not (Posted-Of $r) -or $known.ContainsKey("$($r.mod)|$($r.version)")) { continue }
        if ($r.PSObject.Properties['prunePending']) { $r.prunePending = $true } else { $r | Add-Member -NotePropertyName prunePending -NotePropertyValue $true }
        if ($script:WritingActions -notcontains $Action) { Write-Output ("clean-up pending for {0} {1}; runs at the next posted or bump" -f $r.mod, $r.version) }
    }
}
# THE ACTIVE VERSION IN THE TEST PROFILE (2026-10-27): a build recorded working or posted becomes the version ticked in
# Njordlinger Test - in the old version's position, the old one unticked (role profile-version-gate activate), then the
# mod is checked (role profile-version-gate check). Item Explorer 1.2.0 sat unticked while 1.1.4 and 1.1.3 ran because
# nothing ever made a proven build the active one. Never under -WhatIf and never fatal: the ledger fact stands whatever
# the profile says (MO2 may be open); a failure is printed as FAIL lines, and combined-run finish runs the fix again.
# A copied tree without the role's file (the golden tests) skips it.
function Invoke-ProfileVersions([string]$key, [string]$ver, [string]$why, [string[]]$hashes = @()) {
    if ($WhatIfPreference -or $env:VERSION_GATE_NO_PROFILE) { return }
    try {
        $pg = "$(@(& py -3 $ResolverPy find profile-version-gate 2>$null)[0])".Trim()
        if (-not $pg -or $pg -like 'MISSING*' -or -not (Test-Path -LiteralPath $pg)) { return }
        $pgArgs = @('activate', '--mod', $key, '--version', $ver, '--reason', $why, '--registry', $RegistryPath, '--ledger', $LedgerPath)
        foreach ($h in @($hashes | Where-Object { $_ } | Select-Object -Unique)) { $pgArgs += @('--sha256', "$h") }
        $global:LASTEXITCODE = 0
        & py -3 $pg @pgArgs 2>&1 | ForEach-Object { "  profile: $_" }
        # exit 4 (2026-10-27): the recorded build is NOT what the test profile has installed - combined-run finish had
        # rolled AMF's shared base folder back to the older build at 07:32, and a later 'record working' said nothing
        if ($LASTEXITCODE -eq 4) { Write-Output "WARNING  $key $ver was recorded, but the test profile does NOT have that build installed (the NOT INSTALLED banner above) - install it before anyone tests or plays on it" }
        & py -3 $pg check --mod $key --registry $RegistryPath --ledger $LedgerPath 2>&1 | ForEach-Object { "  profile: $_" }
        if ($LASTEXITCODE -ne 0) { Write-Output "WARNING the test profile does not run $key's current version (above); the ledger is written - fix with: resolve.py run profile-version-gate fix --mod $key" }
    } catch { Write-Output "WARNING profile-version-gate failed: $($_.Exception.Message)" }
}
function Invoke-PendingCleanups([string]$key) {
    if ($WhatIfPreference) { return }
    $rows = @($script:ledger | Where-Object { $_ -and $_.mod -eq $key -and $_.PSObject.Properties['prunePending'] -and $_.prunePending })
    if ($rows.Count -eq 0) { return }
    $cleared = 0
    foreach ($r in @($rows | Sort-Object { Parse-Version $_.version })) {
        Invoke-PostReleasePrune $key "$($r.version)"
        if ($script:PruneOk) { $r.PSObject.Properties.Remove('prunePending'); $cleared++ }
    }
    if ($cleared -gt 0) { Save-Ledger $script:ledger }
}

# --- version locations in a repo --------------------------------------------------------------
# Every place a version is written as text. Discovered by scanning, recorded in the registry at
# register time, and re-verified on every bump/stamp/gate so a location added later cannot hide.
function Discover-Locations([string]$repoPath) {
    $locs = New-Object System.Collections.Generic.List[object]
    $add = { param($file, $label, $pattern, $replace) $locs.Add([pscustomobject]@{ file = $file; label = $label; pattern = $pattern; replace = $replace }) }

    if (Test-Path -LiteralPath (Join-Path $repoPath 'CMakeLists.txt')) {
        & $add 'CMakeLists.txt' 'CMakeLists.txt project VERSION' '(?m)^(\s*VERSION\s+)\d+\.\d+\.\d+' '${1}{V}'
    } else {
        # 2026-11-09 (Longship): a mod whose SKSE plugin sits one folder down (skse\CMakeLists.txt) beside its asset tools
        Get-ChildItem -LiteralPath $repoPath -Directory -ErrorAction SilentlyContinue | Where-Object { $_.FullName + '\' -notmatch $EXCLUDE_RE } | ForEach-Object {
            $cm = Join-Path $_.FullName 'CMakeLists.txt'
            if ((Test-Path -LiteralPath $cm) -and ((Get-Content -LiteralPath $cm -Raw) -match '(?m)^\s*VERSION\s+\d+\.\d+\.\d+')) {
                $rel = $_.Name + '\CMakeLists.txt'
                & $add $rel "$rel project VERSION" '(?m)^(\s*VERSION\s+)\d+\.\d+\.\d+' '${1}{V}'
            }
        }
    }
    if (Test-Path -LiteralPath (Join-Path $repoPath 'vcpkg.json')) {
        $t = Get-Content -LiteralPath (Join-Path $repoPath 'vcpkg.json') -Raw
        if ($t -match '"version-string"\s*:') { & $add 'vcpkg.json' 'vcpkg.json version-string' '("version-string"\s*:\s*")[^"]+(")' '${1}{V}${2}' }
    }
    # .NET / MSBuild projects (Taskbar Folders): <Version>x.y.z</Version> in the .csproj
    Get-ChildItem -LiteralPath $repoPath -Filter '*.csproj' -File -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch $EXCLUDE_RE -and $_.FullName -notmatch '\\(bin|obj)\\' } | ForEach-Object {
            $rel = $_.FullName.Substring($repoPath.Length + 1)
            $t = Get-Content -LiteralPath $_.FullName -Raw
            if ($t -match '<Version>\s*\d+\.\d+\.\d+\s*</Version>') { & $add $rel "$rel <Version>" '(<Version>\s*)\d+\.\d+\.\d+(\s*</Version>)' '${1}{V}${2}' }
        }
    Get-ChildItem -LiteralPath $repoPath -Filter 'xmake.lua' -File -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch $EXCLUDE_RE } | ForEach-Object {
            $rel = $_.FullName.Substring($repoPath.Length + 1)
            $t = Get-Content -LiteralPath $_.FullName -Raw
            if ($t -match '(?m)^local\s+version\s*=\s*"') { & $add $rel "$rel local version" '(?m)^(local\s+version\s*=\s*")[^"]+(")' '${1}{V}${2}' }
            if ($t -match 'set_version\("')                { & $add $rel "$rel set_version literal" '(set_version\(")[^"]+(")' '${1}{V}${2}' }
        }
    Get-ChildItem -LiteralPath $repoPath -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch $EXCLUDE_RE -and $_.Name -match '(?i)version' -and $_.Extension -match '^\.(h|hpp)$' } | ForEach-Object {
            $rel = $_.FullName.Substring($repoPath.Length + 1)
            $t = Get-Content -LiteralPath $_.FullName -Raw
            if ($t -match '(?m)^#define\s+\w*VERSION_MAJOR\s+\d+') {
                & $add $rel "$rel MAJOR" '(?m)^(#define\s+\w*VERSION_MAJOR\s+)\d+' '${1}{MAJOR}'
                & $add $rel "$rel MINOR" '(?m)^(#define\s+\w*VERSION_MINOR\s+)\d+' '${1}{MINOR}'
                & $add $rel "$rel PATCH" '(?m)^(#define\s+\w*VERSION_PATCH\s+)\d+' '${1}{PATCH}'
            }
        }
    # Mod Organizer 2 Python plugins (MO2 Custom Filters, 2026-09-22): __version__ = "x.y.z" in a top-level .py
    Get-ChildItem -LiteralPath $repoPath -Filter '*.py' -File -ErrorAction SilentlyContinue | ForEach-Object {
        $rel = $_.Name
        $t = Get-Content -LiteralPath $_.FullName -Raw
        if ($t -match '(?m)^__version__\s*=\s*"\d+\.\d+\.\d+"') { & $add $rel "$rel __version__" '(?m)^(__version__\s*=\s*")\d+\.\d+\.\d+(")' '${1}{V}${2}' }
    }
    # ...and MO2 package plugins (MO2 Theme Framework, 2026-09-26): plugins\<Name>\__init__.py, the folder MO2 loads
    Get-ChildItem -LiteralPath (Join-Path $repoPath 'plugins') -Filter '__init__.py' -File -Recurse -Depth 1 -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch $EXCLUDE_RE } | ForEach-Object {
            $rel = $_.FullName.Substring($repoPath.Length + 1)
            $t = Get-Content -LiteralPath $_.FullName -Raw
            if ($t -match '(?m)^__version__\s*=\s*"\d+\.\d+\.\d+"') { & $add $rel "$rel __version__" '(?m)^(__version__\s*=\s*")\d+\.\d+\.\d+(")' '${1}{V}${2}' }
        }
    # FOMOD info.xml kept in the repo (the package copy is generated from it)
    Get-ChildItem -LiteralPath $repoPath -Filter 'info.xml' -File -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch $EXCLUDE_RE -and $_.DirectoryName -match '(?i)fomod' } | ForEach-Object {
            $rel = $_.FullName.Substring($repoPath.Length + 1)
            $t = Get-Content -LiteralPath $_.FullName -Raw
            if ($t -match '<Version>\s*\d+\.\d+\.\d+\s*</Version>') { & $add $rel "$rel <Version>" '(<Version>\s*)\d+\.\d+\.\d+(\s*</Version>)' '${1}{V}${2}' }
        }
    # A plugin-only mod with no build system (Ysgramor's Armor addon, 2026-09-17): a top-level VERSION
    # file holding X.Y.Z alone, which its build.ps1 reads and stamps into the package.
    if (Test-Path -LiteralPath (Join-Path $repoPath 'VERSION')) {
        $t = Get-Content -LiteralPath (Join-Path $repoPath 'VERSION') -Raw
        if ($t -match '^\s*\d+\.\d+\.\d+\s*$') { & $add 'VERSION' 'VERSION file' '(?m)^\s*\d+\.\d+\.\d+\s*$' '{V}' }
    }
    return $locs
}

# Files that may legitimately carry a version literal. Any X.Y.Z in one of these that is not a
# registered location (or a registered ignore) FAILS - that is the "location the tool was not told
# about" gate. Wheeler's Plugin.h.in carried a hardcoded "v1.3.3" for weeks this way.
function Scan-UnknownLiterals([string]$repoPath, $locs, $ignores) {
    $unknown = New-Object System.Collections.Generic.List[string]
    $known = @{}
    foreach ($l in $locs) { $known[$l.file.ToLower()] = $true }
    $files = Get-ChildItem -LiteralPath $repoPath -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch $EXCLUDE_RE } |
        Where-Object { $_.Name -match '(?i)(\.rc$|\.rc\.in$|\.h\.in$|version|plugin\.h$|plugininfo|^info\.xml$)' -and $_.Extension -match '^\.(rc|in|h|hpp|xml|cpp)$' }
    foreach ($f in $files) {
        $rel = $f.FullName.Substring($repoPath.Length + 1)
        if ($known.ContainsKey($rel.ToLower())) { continue }
        $n = 0
        foreach ($line in (Get-Content -LiteralPath $f.FullName -ErrorAction SilentlyContinue)) {
            $n++
            if ($line -match '@\w+@|\$\{|\bVERSION_MAJOR\b|\bVERSION_MINOR\b|\bVERSION_PATCH\b|PROJECT_VERSION') { continue }   # generated from the build system - fine
            if ($line -match '^\s*(//|/\*|\*|<!--)') { continue }   # a comment is not a location
            if ($line -match '(?<![\d.])\d+\.\d+\.\d+(?![\d.])' -or $line -match '\bFILEVERSION\s+\d+\s*,\s*\d+\s*,\s*\d+') {
                $sig = ('{0}:{1}' -f $rel, $n)
                $ignored = $false
                foreach ($ig in @($ignores)) { if ($ig -and ($sig -like $ig -or $rel -like $ig)) { $ignored = $true; break } }
                if (-not $ignored) { $unknown.Add(('{0}  ->  {1}' -f $sig, $line.Trim())) }
            }
        }
    }
    return $unknown
}

function Read-Locations([string]$repoPath, $locs) {
    $vals = [ordered]@{}
    $parts = @{}
    foreach ($l in $locs) {
        $p = Join-Path $repoPath $l.file
        if (-not (Test-Path -LiteralPath $p)) { $vals[$l.label] = '(file missing)'; continue }
        $t = Get-Content -LiteralPath $p -Raw
        $m = [regex]::Match($t, $l.pattern)
        if (-not $m.Success) { $vals[$l.label] = '(pattern not found)'; continue }
        $num = [regex]::Match($m.Value, '\d+\.\d+\.\d+').Value
        if (-not $num) { $num = [regex]::Match($m.Value, '\d+\s*$').Value.Trim() }
        if ($l.replace -match '\{MAJOR\}|\{MINOR\}|\{PATCH\}') { $parts[$l.file + '|' + ($l.replace -replace '.*\{(\w+)\}.*', '$1')] = $num; continue }
        $vals[$l.label] = $num
    }
    # reassemble MAJOR/MINOR/PATCH triplets into one value per file
    $byFile = @{}
    foreach ($k in $parts.Keys) { $f, $c = $k -split '\|'; if (-not $byFile[$f]) { $byFile[$f] = @{} }; $byFile[$f][$c] = $parts[$k] }
    foreach ($f in $byFile.Keys) { $vals["$f MAJOR.MINOR.PATCH"] = ('{0}.{1}.{2}' -f $byFile[$f]['MAJOR'], $byFile[$f]['MINOR'], $byFile[$f]['PATCH']) }
    return $vals
}

function Write-Locations([string]$repoPath, $locs, [version]$v) {
    $changed = 0
    foreach ($l in $locs) {
        $p = Join-Path $repoPath $l.file
        if (-not (Test-Path -LiteralPath $p)) { Flag ("location missing: {0}" -f $l.file); continue }
        $t = (Get-Content -LiteralPath $p -Raw -Encoding UTF8).TrimStart([char]0xFEFF)
        if ($t -notmatch $l.pattern) { Flag ("pattern no longer matches in {0} ({1}) - the file changed shape; re-register" -f $l.file, $l.label); continue }
        $rep = $l.replace.Replace('{V}', $v.ToString()).Replace('{MAJOR}', "$($v.Major)").Replace('{MINOR}', "$($v.Minor)").Replace('{PATCH}', "$($v.Build)")
        $new = [regex]::Replace($t, $l.pattern, $rep)
        if ($new -eq $t) { Note ("already {0}: {1}" -f $v, $l.label); continue }
        # Keep the file's own encoding (2026-09-26): Set-Content -Encoding UTF8 on Windows PowerShell 5.1 ADDS a byte-order
        # mark, which put U+FEFF in front of every VERSION file the gate stamped - and from there into package folder
        # names and a built stylesheet's header (Njordlinger MO2 Theme 1.0.0). A BOM is written only if the file had one.
        if ($PSCmdlet.ShouldProcess($p, "set version $v")) {
            $raw = [System.IO.File]::ReadAllBytes($p)
            $hadBom = ($raw.Length -ge 3 -and $raw[0] -eq 0xEF -and $raw[1] -eq 0xBB -and $raw[2] -eq 0xBF)
            [System.IO.File]::WriteAllText($p, $new.TrimStart([char]0xFEFF), (New-Object System.Text.UTF8Encoding $hadBom))
        }
        Ok ("wrote {0} -> {1}" -f $v, $l.label); $changed++
    }
}

# --- binaries and packages --------------------------------------------------------------------
# FOREIGN BINARIES (2026-10-07, Norden UI - Black 1.0.4): a mod may SHIP a binary it did not build - Norden UI - Black's
# "RaceMenu Atelier" option carries emberchain's GPL RaceMenuAtelier.dll (FileVersion 1.0.1) beside an art-only package.
# The gate took that DLL for the mod's own build and refused 1.0.4 ("FileVersion is 1.0.1"). A registry entry's
# 'foreignBinaries' (file names) lists such binaries; Resolve-Key loads them and the two DLL lookups below skip them, so
# the mod is judged by its own artefacts (an art-only mod stays art-only). Empty for every other mod - nothing changes.
$script:ForeignBinaries = @()
function Test-Foreign($item) { return (@($script:ForeignBinaries | Where-Object { $_ -ieq $item.Name }).Count -gt 0) }
function Find-BuiltDll([string]$repoPath, [string]$given) {
    if ($given) {
        if (-not (Test-Path -LiteralPath $given)) { Fail ("-Dll '{0}' does not exist." -f $given) }
        return Get-Item -LiteralPath $given
    }
    $c = @(Get-ChildItem -LiteralPath $repoPath -Filter '*.dll' -Recurse -File -ErrorAction SilentlyContinue |
           Where-Object { $_.FullName -notmatch 'vcpkg_installed|\\deps\\|\\extern|\\_deps\\|\\obj\\' -and -not (Test-Foreign $_) } |
           Sort-Object LastWriteTime -Descending)
    if ($c.Count -eq 0) { return $null }
    # prefer the binary named after the repo (a .NET bin folder is full of dependency DLLs)
    $leaf = Split-Path -Leaf $repoPath
    $own = @($c | Where-Object { $_.BaseName -ieq $leaf -or $_.BaseName -ieq ($leaf -replace '-SMF$', '') -or $_.BaseName -ieq "!$leaf" })
    if ($own.Count -gt 0) { return $own[0] }
    return $c[0]
}
function Dll-Version($dllItem) {
    try { $fv = $dllItem.VersionInfo.FileVersion } catch { return $null }
    if (-not $fv) { return $null }
    return (Parse-Version ($fv -replace '[,\s]', '.'))
}
# File-Sha256 (2026-10-13): hashing only READS, so it runs the same with -WhatIf. Get-FileHash resolves its path through a
# step that honours the script-wide -WhatIf ('What if: Retrieve the value for property ProviderPath') and then returns
# nothing, so 'record -WhatIf' crashed on .Hash of null. .NET's SHA256 has no such step.
function File-Sha256([string]$path) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $fs = [System.IO.File]::OpenRead($path)
    try { return ([System.BitConverter]::ToString($sha.ComputeHash($fs))).Replace('-', '') } finally { $fs.Dispose(); $sha.Dispose() }
}
function Dll-Hash($dllItem) { return (File-Sha256 $dllItem.FullName) }

# Packages live in "<stage>\<Game> - <Mod>\" since 2026-10-01 (distro-names.ps1): the Skyrim and the Oblivion Remastered
# "HUD Position Manager 1.0.1" both exist, and 'record' had compared the Oblivion build with the Skyrim package's DLL.
# So every lookup carries the registry entry's GAME and reads only that game's folder.
. $DistroNamesPath
. $TestBuildPickPath
# THE TEST-BUILD PICK (2026-10-13, Main Agent; test-build-pick.ps1, shared with finalize-mod.ps1 and pre-finalize-check.ps1):
# a version can have several folders - "<Mod> X.Y.Z", " FOMOD", and either with a " (...)" suffix (Simple Loadout System
# for Witcher 3 1.0.1: the plain folder held the OLD 1.0.0 files, "(inventory start-up fix)" the tested build, and this
# function took the plain one). With more than one, the folder whose artefact matches -hash (the ledger's recorded working
# hash) is the build; none or several matching refuses (Flag) and returns $null - a rename is for the owner. Without a
# hash, only the plain + FOMOD pair is decided (the FOMOD, as before).
# Find-Package returns ONLY the folder (anything it wrote to the output would become part of its return value); the
# pick's line is printed by Show-PackagePick right after each call - a refusal as a Flag, a choice as a Note.
$script:PackagePickRefused = $false
$script:PackagePickMessage = ''
function Find-Package([string]$display, [string]$ver, [string]$game, [string]$hash, [object[]]$artifacts = @()) {
    $script:PackagePickRefused = $false
    $script:PackagePickMessage = ''
    $cands = @(Get-TestBuildCandidates -BuildsRoot $BuildsRoot -Display $display -Version $ver -Game $game -ProjectRoot $Root)
    $sel = Select-TestBuild -Candidates $cands -Hash $hash -Foreign $script:ForeignBinaries -Artifacts $artifacts
    $script:PackagePickMessage = "$($sel.Message)"
    if ($sel.Refused) { $script:PackagePickRefused = $true; return $null }
    if (-not $sel.Pick) { return $null }
    $p = $sel.Pick
    $p | Add-Member -NotePropertyName PkgRoot -NotePropertyValue $p.Parent.FullName -Force
    $p | Add-Member -NotePropertyName PkgGame -NotePropertyValue $game -Force
    return $p
}
function Show-PackagePick {
    if ($script:PackagePickRefused) { Flag $script:PackagePickMessage }
    elseif ($script:PackagePickMessage) { Note $script:PackagePickMessage }
    $script:PackagePickMessage = ''
}
function Package-Dlls($pkg) {
    # .asi too (2026-10-05): AMF for Witcher 3 is an .asi plugin beside its dinput8.dll loader, and with *.dll alone the
    # finalize gate compared the recorded hash with the loader and called the proven build a mismatch
    # -Include is ignored with -LiteralPath (it returned EVERY file of the package - 2026-10-06, found when an asset-only
    # package was counted as 22 DLLs), so the extension is filtered here
    # the filter itself lives in test-build-pick.ps1 (Get-PackageBinaries), one home for the classification (2026-10-13)
    return @(Get-PackageBinaries $pkg.FullName $script:ForeignBinaries)
}
# EVERY LISTED ARTEFACT (2026-10-13, Main Agent): a working row recorded with 'artifacts' is checked file by file - each
# listed file present in the package with its hash, and no artefact of the same classification that is not listed. Each
# failure is its own Flag naming the file. Called only when the row has a list; a row with sha256 alone keeps the
# single-hash checks. Prints through Flag/Ok and returns nothing (output inside a function would be its return value).
function Test-RowArtefacts($entry, $pkg) {
    $arts = @(Get-RowArtifacts $entry)
    $probs = @(Compare-PackageArtefacts $pkg.FullName $arts $script:ForeignBinaries)
    foreach ($p in $probs) { Flag ("package '{0}': {1}" -f $pkg.Name, $p) }
    if ($probs.Count -eq 0) { Ok ("every listed artefact matches the build recorded working ({0} file(s): {1})" -f $arts.Count, (($arts | ForEach-Object { $_.file }) -join ', ')) }
}
function Find-FinalizedPackage([string]$display, [string]$ver, [string]$game) {
    $fin = Join-Path $Root '10. finalized mods'
    if (-not (Test-Path -LiteralPath $fin)) { return $null }
    $c = @(Find-Packages -Root $fin -ModName $display -Game $game -Version $ver -Folders -ProjectRoot $Root | Where-Object { $_.Name -eq "$display $ver" -or $_.Name -eq "$display $ver FOMOD" })
    if ($c.Count -eq 0) { return $null }
    $f = @($c | Where-Object { $_.Name -like '* FOMOD' }); if ($f.Count -gt 0) { return $f[0] }
    return $c[0]
}

# --- Nexus: the last upload is the floor on "working" -------------------------------------------
# The owner, 2026-09-12: "whatever the last uploaded version was is assumed to be working because it
# passed the finalized gate". So for a mod with a linked Nexus ID, the published version is read
# from the API and, if the ledger's last working build is below it, recorded as working here - with
# the Nexus ID and date as evidence, and the finalized package's DLL hash when that package exists.
function Get-NexusDomain($e) {
    # The game section a mod's page lives in (2026-09-30: the domain was hardcoded to skyrimspecialedition, so linking the
    # Oblivion Remastered pages read SKYRIM mods 5662-5668 and recorded two of them "working" in the ledger). A registry
    # nexusDomain wins; otherwise a repo that ships an OblivionRemastered\ tree is oblivionremastered.
    if ($e.PSObject.Properties['nexusDomain'] -and $e.nexusDomain) { return [string]$e.nexusDomain }
    if ($e.repo -and (Test-Path -LiteralPath (Join-Path $Root "6. current wip mods\$($e.repo)\dist\OblivionRemastered"))) { return 'oblivionremastered' }
    return 'skyrimspecialedition'
}
$script:NexusOwner = ''
function Get-NexusPublished([int]$id, [string]$domain = '') {
    # kit: this kit makes no network call, so the live page is never read and the ledger decides.
    # OPTIONAL-SCRIPTS.md says what the original read here, if the person asks for it to be built.
    return $null
}
function Sync-Members([string]$key) {
    # THE PIPELINE KIT'S PUBLISH STEP (2026-10-11): it has no Nexus page; it is published by copying its zip into
    # 11. Nexus distro\1. members. A registry entry with publishChannel 'members' has that folder read on every action,
    # and the newest "<display name> X.Y.Z.zip" there is recorded posted - nobody has to remember a posted command.
    $e = $script:reg.$key
    if ("$($e.publishChannel)" -ne 'members') { return }
    $dir = Join-Path $Root '11. Nexus distro\1. members'
    if (-not (Test-Path -LiteralPath $dir)) { return }
    $rx = '^' + [regex]::Escape([string]$e.displayName) + ' (\d+\.\d+\.\d+)\.zip$'
    $zips = @(Get-ChildItem -LiteralPath $dir -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -match $rx } |
              Sort-Object { Parse-Version $_.Name } -Descending)
    if ($zips.Count -eq 0) { return }
    $z = $zips[0]; $zv = (Parse-Version $z.Name).ToString()
    $row = $script:ledger | Where-Object { $_.mod -eq $key -and $_.version -eq $zv } | Select-Object -First 1
    if (-not $row) { Note ("members: '{0}' is in 1. members but the ledger never issued {1} - not recorded; look at it" -f $z.Name, $zv); return }
    if (Posted-Of $row) { return }
    $h = (File-Sha256 $z.FullName)
    Set-Posted $row (New-Posted 'members' $dir $z.Name $h ("copied into 11. Nexus distro\1. members - the kit's publish step; recorded by version-gate.ps1 on reading the folder"))
    Save-Ledger $script:ledger
    Ok ("members: {0} {1} is in 1. members - recorded POSTED" -f $key, $zv)
}
function Sync-Nexus([string]$key, [switch]$Force) {
    # Updates $script:ledger in place (prints its notes). The published version is POSTED (2026-10-11): its ledger row is
    # marked so, and created (working) when Nexus is ahead of the ledger.
    Sync-Members $key
    $e = $script:reg.$key
    if (-not $e.nexusModId) { return }
    $stamp = $null
    try { if ($e.nexusChecked) { $stamp = [datetime]::ParseExact($e.nexusChecked, 'yyyy-MM-dd HH:mm:ss', $null) } } catch { }
    if (-not $Force -and $stamp -and ((Get-Date) - $stamp).TotalMinutes -lt 60) {
        Note ("nexus: {0} published {1} (checked {2})" -f $e.nexusModId, $e.nexusVersion, $e.nexusChecked)
        return
    }
    $n = Get-NexusPublished ([int]$e.nexusModId) (Get-NexusDomain $e)
    if (-not $n) { Note ("nexus: could not read mod {0} - a GAP, not a pass; the ledger decides" -f $e.nexusModId); return }
    if ($n.uploader -ne $script:NexusOwner) { Note ("nexus: {0}/{1} ('{2}') was uploaded by '{3}', not {4} - wrong ID or game section; ignored" -f $n.domain, $e.nexusModId, $n.name, $n.uploader, $script:NexusOwner); return }
    if ($n.status -ne 'published') { Note ("nexus: mod {0} is '{1}', not published - ignored" -f $e.nexusModId, $n.status); return }
    if ($e.PSObject.Properties['nexusChecked']) { $e.nexusChecked = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss') } else { $e | Add-Member -NotePropertyName nexusChecked -NotePropertyValue (Get-Date).ToString('yyyy-MM-dd HH:mm:ss') }
    if ($e.PSObject.Properties['nexusVersion']) { $e.nexusVersion = $n.version.ToString() } else { $e | Add-Member -NotePropertyName nexusVersion -NotePropertyValue $n.version.ToString() }
    Save-Registry $script:reg
    $lw = Last-Working $key $script:ledger
    $nv = $n.version.ToString()
    $url = "https://www.nexusmods.com/{0}/mods/{1}" -f $n.domain, $e.nexusModId
    $pev = ("NEXUS: the page publishes '{0}', updated {1} - recorded posted by version-gate.ps1 on reading the page" -f $n.raw, $n.updated)
    $row = $script:ledger | Where-Object { $_.mod -eq $key -and $_.version -eq $nv } | Select-Object -First 1
    if ($row) {
        if (-not (Posted-Of $row)) { Set-Posted $row (New-Posted 'nexus' $url $null $null $pev); Save-Ledger $script:ledger; Ok ("nexus: {0} published {1} - recorded POSTED" -f $e.nexusModId, $nv) }
        else { Ok ("nexus: {0} published {1}; ledger working {2} (not behind)" -f $e.nexusModId, $n.version, $lw) }
        return
    }
    if ($lw -and $lw -ge $n.version) { Ok ("nexus: {0} published {1}; ledger working {2} (not behind)" -f $e.nexusModId, $n.version, $lw); return }
    $sha = $null
    $pkg = Find-FinalizedPackage $e.displayName $nv (Get-ModGame -Entry $e -ProjectRoot $Root)
    if ($pkg) { $d = @(Package-Dlls $pkg); if ($d.Count -gt 0) { $sha = Dll-Hash $d[0] } }
    $ev = ("NEXUS: published on nexusmods.com as mod {0} version '{1}', updated {2} - it passed the finalize gate before upload (the owner, 2026-09-12); recorded by version-gate.ps1{3}" -f $e.nexusModId, $n.raw, $n.updated, $(if ($sha) { ", hash from the finalized package '$($pkg.Name)'" } else { ', no local finalized package to hash' }))
    $entry = [pscustomobject]@{ mod = $key; version = $nv; status = 'working'; evidence = $ev; sha256 = $sha; recorded = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'); posted = (New-Posted 'nexus' $url $null $null $pev) }
    $script:ledger = @($script:ledger | Where-Object { -not ($_.mod -eq $key -and $_.version -eq $nv) }) + $entry
    Save-Ledger $script:ledger
    Ok ("nexus: {0} published {1} is AHEAD of the ledger ({2}) - recorded working and POSTED from Nexus" -f $e.nexusModId, $n.version, $(if ($lw) { $lw } else { 'none' }))
    return
}

# ================================================================================================
$ledger = Load-Ledger
$reg    = Load-Registry

switch ($Action) {

    'nextnumber' {
        if (-not $From) { Fail '-From X.Y.Z is required.' }
        Require-Kind 'nextnumber'
        $pv = Assert-Shape $From
        Write-Output (Next-Number $pv $Kind).ToString()
        exit 0
    }

    'register' {
        # The owner, 2026-11-01: "Always check for precedence before making a new mod." A registered mod with no record of
        # the search is refused. A released mod being given an identity (-NoRepo) is not a new mod.
        if (-not $NoRepo) {
            if (-not $PriorArt -or -not (Test-Path -LiteralPath $PriorArt)) { Fail "a new mod needs -PriorArt <file>: search Nexus and GitHub for a mod that already does this, and write down what was searched and found. Owner, 2026-11-01." }
            $pa = Get-Content -LiteralPath $PriorArt -Raw
            if ($pa -notmatch '(?i)nexus' -or $pa -notmatch '(?i)github') { Fail "-PriorArt file '$PriorArt' must say what was searched on both Nexus and GitHub." }
        }
        if ($NoRepo) {
            # A released mod with no source repo (2026-10-25): identity and Nexus page only, with the reason recorded.
            if (-not $Mod -or -not $DisplayName -or -not $Evidence) { Fail '-NoRepo needs -Mod, -DisplayName and -Evidence (why there is no repo and how the mod is built).' }
            if ($Repo) { Fail '-NoRepo and -Repo together: a mod either has a repo folder or it does not.' }
            if ($Mod -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]*$') { Fail "key '$Mod' must be a plain identifier (letters, digits, . _ -)." }
            foreach ($k in (Registry-Keys $reg)) {
                if ($k -ieq $Mod) { Fail "key '$Mod' is already registered." }
                if ($reg.$k.displayName -ieq $DisplayName) { Fail "display name '$DisplayName' is already registered as '$k'. One identity per mod." }
            }
            $entry = [pscustomobject]@{
                repo        = $null
                displayName = $DisplayName
                aliases     = @($Alias | Where-Object { $_ })
                locations   = @()
                ignore      = @()
                nexusModId  = $null
                noRepo      = $Evidence
                registered  = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
            }
            $reg | Add-Member -NotePropertyName $Mod -NotePropertyValue $entry
            Save-Registry $reg
            Write-Output ("register  {0}   NO REPO   display '{1}'" -f $Mod, $DisplayName)
            Ok ("registered without a repo ({0}). Next: 'link -NexusModId N' for its page; bump/stamp/gate refuse it." -f $Evidence)
            exit 0
        }
        if (-not $Mod -or -not $Repo -or -not $DisplayName) { Fail '-Mod (ledger key), -Repo (folder under 6. current wip mods) and -DisplayName (package name) are all required.' }
        if ($Mod -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]*$') { Fail "key '$Mod' must be a plain identifier (letters, digits, . _ -)." }
        $repoPath = Join-Path $WipRoot $Repo
        if (-not (Test-Path -LiteralPath $repoPath -PathType Container)) { Fail "no such repo folder: $repoPath" }
        foreach ($k in (Registry-Keys $reg)) {
            $e = $reg.$k
            if ($k -ieq $Mod)                 { Fail "key '$Mod' is already registered." }
            if ($e.repo -ieq $Repo)           { Fail "repo '$Repo' is already registered as '$k'. One identity per mod." }
            if ($e.displayName -ieq $DisplayName) { Fail "display name '$DisplayName' is already registered as '$k'. One identity per mod." }
        }
        $locs = Discover-Locations $repoPath
        $ign = @($Ignore | Where-Object { $_ })
        $unknown = Scan-UnknownLiterals $repoPath $locs $ign
        $entry = [pscustomobject]@{
            repo        = $Repo
            displayName = $DisplayName
            aliases     = @($Alias | Where-Object { $_ })
            locations   = @($locs)
            ignore      = $ign
            nexusModId  = $(if ($NexusModId) { $NexusModId } else { $null })
            registered  = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
        }
        Write-Output ("register  {0}   repo '{1}'   display '{2}'" -f $Mod, $Repo, $DisplayName)
        foreach ($l in $locs) { Ok ("location: {0}" -f $l.label) }
        if ($locs.Count -eq 0) { Flag 'no version location was discovered in this repo - the build cannot stamp a version, so nothing can be gated. Add a project VERSION / version-string / set_version first.' }
        foreach ($u in $unknown) { Flag ("version literal this tool does not own: {0}" -f $u) }
        if ($unknown.Count -gt 0) { Note 'Make each of these derive from the build system (CMake configure_file / @PROJECT_VERSION@), or add an exact "file:line" glob to the registry entry''s ignore list by hand once you have confirmed it is not a version of this mod.' }
        if ($script:Failures.Count -gt 0) { Fail ("not registered: {0} problem(s) above." -f $script:Failures.Count) }
        $reg | Add-Member -NotePropertyName $Mod -NotePropertyValue $entry
        Save-Registry $reg
        Ok "registered. Next: 'seed' if working builds already exist, otherwise 'bump' issues 1.0.0."
        exit 0
    }

    'rename' {
        # Correcting an identity the registry already holds, which unregister cannot do once a version has
        # been issued (it refuses, so the ledger keeps its meaning) and which nothing else could do at all.
        # The KEY and the ledger are untouched: this only moves the display name and/or the repo folder that
        # the key points at, so every recorded version still belongs to the same mod.
        $key = Resolve-Key $Mod $reg
        if (-not $DisplayName -and -not $Repo) { Fail 'nothing to rename: pass -DisplayName, -Repo, or both.' }
        $e = $reg.$key
        foreach ($k in (Registry-Keys $reg)) {
            if ($k -ieq $key) { continue }
            # the same display name is allowed for another GAME's build (Apocrypha Menu Framework on Skyrim, Oblivion
            # Remastered and Witcher 3): the game tells them apart, as Get-ModGame does for every package path
            if ($DisplayName -and $reg.$k.displayName -ieq $DisplayName -and "$($reg.$k.game)" -ieq "$($e.game)") { Fail "display name '$DisplayName' is already registered as '$k' for the same game. One identity per mod." }
            if ($Repo -and $reg.$k.repo -ieq $Repo) { Fail "repo '$Repo' is already registered as '$k'. One identity per mod." }
        }
        if ($Repo) {
            $repoPath = Join-Path $WipRoot $Repo
            if (-not (Test-Path -LiteralPath $repoPath -PathType Container)) { Fail "no such repo folder: $repoPath" }
        }
        Write-Output ("rename  {0}" -f $key)
        if ($DisplayName) { Write-Output ("      display '{0}'  ->  '{1}'" -f $e.displayName, $DisplayName); $e.displayName = $DisplayName }
        if ($Repo)        { Write-Output ("      repo    '{0}'  ->  '{1}'" -f $e.repo, $Repo);               $e.repo = $Repo }
        if ($Repo) { $e.locations = @(Discover-Locations (Join-Path $WipRoot $e.repo)) }
        Save-Registry $reg
        Ok ("identity updated. Packages must now be named '{0} <version>'." -f $e.displayName)
        exit 0
    }

    'unregister' {
        # Removing an IDENTITY, never a version. A mod that has issued numbers keeps its entry:
        # the ledger is the record of what was built and when, and deleting the identity behind
        # live ledger rows would leave them pointing at nothing. That is why this refuses rather
        # than cascading - tidying up is not a good enough reason to break the record.
        if (-not $Mod) { Fail '-Mod (ledger key) is required.' }
        $key = (Registry-Keys $reg) | Where-Object { $_ -ieq $Mod } | Select-Object -First 1
        if (-not $key) { Fail ("'{0}' is not registered; nothing to remove." -f $Mod) 2 }
        $rows = @($ledger | Where-Object { $_.mod -eq $key })
        if ($rows.Count -gt 0) {
            Fail ("{0} has {1} ledger entr(ies); versions were issued for it. The identity stays so the record keeps its meaning." -f $key, $rows.Count)
        }
        $e = $reg.$key
        Write-Output ("unregister  {0}   repo '{1}'   display '{2}'" -f $key, $e.repo, $e.displayName)
        $reg.PSObject.Properties.Remove($key)
        Save-Registry $reg
        Ok "identity removed. That key, repo folder and display name are free for 'register' again."
        exit 0
    }

    'seed' {
        $key = Resolve-Key $Mod $reg
        if (-not $Version -or -not $Evidence) { Fail '-Version and -Evidence are required: the seed is the last build OBSERVED working before the ledger existed.' }
        $pv = Assert-Shape $Version
        if (Last-Working $key $ledger) { Fail ("{0} already has a working entry; seed is only for a mod with none. Use record." -f $key) }
        $hash = $Sha256
        if ($Dll) { $hash = Dll-Hash (Get-Item -LiteralPath $Dll) }
        if (-not $hash) {
            $pkg = Find-FinalizedPackage $reg.$key.displayName $pv.ToString() (Get-ModGame -Entry $reg.$key -ProjectRoot $Root)
            if (-not $pkg) { $pkg = Find-Package $reg.$key.displayName $pv.ToString() (Get-ModGame -Entry $reg.$key -ProjectRoot $Root) }
                Show-PackagePick
            if ($pkg) { $d = @(Package-Dlls $pkg); if ($d.Count -gt 0) { $hash = Dll-Hash $d[0]; Note ("hash taken from '{0}'" -f $pkg.Name) } }
        }
        $entry = [pscustomobject]@{ mod = $key; version = $pv.ToString(); status = 'working'; evidence = "SEED: $Evidence"; sha256 = $hash; recorded = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss') }
        $ledger = @($ledger | Where-Object { -not ($_.mod -eq $key -and $_.version -eq $pv.ToString()) }) + $entry
        Save-Ledger $ledger
        Ok ("{0} {1} = working (seed). next -> {2}" -f $key, $pv, (Candidates-Text $pv))
        exit 0
    }

    'next' {
        $key = Resolve-Key $Mod $reg
        Sync-Nexus $key
        $fl = Last-Posted $key $ledger
        $open = Open-Entry $key $ledger
        $flTxt = if ($fl) { "$fl$(if (Floor-Is-Unknown $key $ledger $fl) { ' (posted: unknown)' })" } else { '(none)' }
        if ($open) {
            $ov = Parse-Version $open.version
            $openKind = Kind-Of $fl $ov
            Write-Output ("{0}: {1} is OPEN (not posted; {2}; a {3} change over last posted {4}) - a change of that kind or lower goes in under it." -f $key, $open.version, $open.status, $openKind, $flTxt)
            if ($fl) {
                $higher = @('minor', 'major' | Where-Object { (Kind-Rank $_) -gt (Kind-Rank $openKind) -and (-not $Kind -or $_ -eq $Kind) })
                foreach ($h in $higher) { Note ("a {0} change would withdraw it and re-issue {1} (from last posted {2})" -f $h, (Next-Number $fl $h), $fl) }
            }
            exit 0
        }
        if ($null -eq $fl) { Write-Output ("{0}: nothing posted and nothing issued; 'bump' will issue 1.0.0 whatever the kind" -f $key); exit 0 }
        if ($Kind) { Write-Output ("{0}: last POSTED {1}  ->  next {2} ({3})" -f $key, $flTxt, (Next-Number $fl $Kind), $Kind) }
        else { Write-Output ("{0}: last POSTED {1}  ->  next {2}" -f $key, $flTxt, (Candidates-Text $fl)) }
        exit 0
    }

    'current' {
        # The number the packager must use: the OPEN number (untested, or recorded working and rebuilt under the same
        # number). A failed or scratch open number goes back through 'bump', which reuses it.
        $key = Resolve-Key $Mod $reg
        Sync-Nexus $key
        $open = Open-Entry $key $ledger
        if ($open -and $open.status -in 'untested','working') { Write-Output $open.version; exit 0 }
        if ($open) { Fail ("{0} {1} is recorded {2}. Run 'bump' - it reuses the number - then build and package." -f $key, $open.version, $open.status) }
        Fail ("{0} has no open number. Run 'bump' first; nothing is packaged under a number the ledger did not issue." -f $key)
    }

    'bump' {
        # THE OPEN NUMBER FIRST (the owner, 2026-10-11): a number is spent by POSTING it, so while the last build is not
        # posted - untested, failed, scratch or recorded working - bump hands back that same number and the change goes
        # in under it. Only when nothing is open does it issue LAST POSTED stepped by the kind (1.0.0 for a mod with nothing out).
        # SEMANTIC VERSIONING (the owner, 2026-10-21): -Kind is required - refusing a bump with no kind is the gate, so no
        # number is ever issued without the change being classified. A change of a HIGHER kind than the open number's
        # (a fix build gains a feature) withdraws the open number and re-issues from the last POSTED number.
        $key = Resolve-Key $Mod $reg
        Require-Kind 'bump'
        $e = $reg.$key
        $repoPath = Repo-Path $key $e
        if (-not (Test-Path -LiteralPath $repoPath)) { Fail "registered repo is gone: $repoPath" }
        Sync-Nexus $key
        Invoke-PendingCleanups $key   # a writing action: any pending clean-up of this mod runs first (2026-10-13)
        $fl = Last-Posted $key $ledger
        $open = Open-Entry $key $ledger
        $flTxt = if ($fl) { "$fl$(if (Floor-Is-Unknown $key $ledger $fl) { ' (posted: unknown)' })" } else { '(none)' }
        $reissue = $false
        if ($open) {
            $openV = Parse-Version $open.version
            $openKind = Kind-Of $fl $openV
            if ($fl -and (Kind-Rank $Kind) -gt (Kind-Rank $openKind)) {
                $target = Next-Number $fl $Kind
                $reissue = $true
                Write-Output ("bump  {0}   last posted {1}   ->   {2} was OPEN as a {3} change; a {4} change re-issues it as {5} (from the last posted number)" -f $key, $flTxt, $openV, $openKind, $Kind, $target)
            } else {
                $target = $openV
                Write-Output ("bump  {0}   last posted {1}   ->   {2} is still OPEN (not posted; {3}; a {4} change) - this {5} change goes in under it" -f $key, $flTxt, $target, $open.status, $openKind, $Kind)
            }
        } else {
            $target = if ($null -eq $fl) { [version]'1.0.0' } else { Next-Number $fl $Kind }
            Write-Output ("bump  {0}   last posted {1}   ->   {2} ({3})" -f $key, $flTxt, $target, $(if ($null -eq $fl) { 'first release' } else { $Kind }))
        }
        $locs = @($e.locations)
        $fresh = Discover-Locations $repoPath
        foreach ($f in $fresh) { if (-not ($locs | Where-Object { $_.label -eq $f.label })) { Flag ("a version location appeared since registration: {0}. Re-register (or add it to the registry) before bumping." -f $f.label) } }
        $unknown = Scan-UnknownLiterals $repoPath $locs @($e.ignore)
        foreach ($u in $unknown) { Flag ("version literal this tool does not own: {0}" -f $u) }
        if ($script:Failures.Count -gt 0) { Fail 'nothing written.' }
        Write-Locations $repoPath $locs $target
        if ($script:Failures.Count -gt 0) { Fail 'a location could not be written; the repo is now PARTIALLY stamped - fix the location and bump again.' }
        if ($reissue) {
            $ov = $open.version
            $ledger = @($ledger | ForEach-Object { if ($_.mod -eq $key -and $_.version -eq $ov -and $_.status -ne 'withdrawn') { $_.evidence = "withdrawn by bump -Kind ${Kind}: re-issued as $target; it was $($_.status): $($_.evidence)"; $_.status = 'withdrawn' }; $_ })
            $entry = [pscustomobject]@{ mod = $key; version = $target.ToString(); status = 'untested'; evidence = "issued by bump ($Kind; re-issued from open $ov)"; sha256 = $null; recorded = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss') }
            $ledger = @($ledger | Where-Object { -not ($_.mod -eq $key -and $_.version -eq $target.ToString()) }) + $entry
            Save-Ledger $ledger
            Ok ("{0} issued as UNTESTED; {1} is withdrawn. Move the CHANGELOG entries written under {1} to {0} (packaging refuses a version with no entry), then build and package." -f $target, $ov)
        } elseif (-not $open -or $open.status -in 'failed','scratch') {
            $why = if ($open) { "issued by bump ($Kind; reused: it was $($open.status) and never posted)" } else { "issued by bump ($(if ($null -eq $fl) { 'first release' } else { $Kind }))" }
            $entry = [pscustomobject]@{ mod = $key; version = $target.ToString(); status = 'untested'; evidence = $why; sha256 = $null; recorded = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss') }
            $ledger = @($ledger | Where-Object { -not ($_.mod -eq $key -and $_.version -eq $target.ToString()) }) + $entry
            Save-Ledger $ledger
            Ok ("{0} issued as UNTESTED. Build now, then package (the packager asks 'current')." -f $target)
        } else {
            Ok ("{0} stays the number until it is posted; nothing new issued. A rebuild packaged under it goes back to untested by itself - record it working again after the test." -f $target)
        }
        Write-Output $target.ToString()
        exit 0
    }
    'renumber' {
        # THE OWNER SETS A NUMBER (2026-09-26). bump hands out the open number or LAST POSTED stepped by the kind and nothing else; when the
        # owner decides a release carries a different number - AMF for Oblivion Remastered had been seeded at 0.1.0, bump
        # issued 0.1.1, and he said "1.0.1" - the number still comes through this tool: it must be above the last POSTED
        # number (2026-10-11), the evidence must quote him, and the open number it replaces is recorded as
        # withdrawn so the ledger shows what happened. Nothing is typed into a file by hand.
        $key = Resolve-Key $Mod $reg
        $e = $reg.$key
        $repoPath = Repo-Path $key $e
        if (-not (Test-Path -LiteralPath $repoPath)) { Fail "registered repo is gone: $repoPath" }
        if (-not $Version -or -not $Evidence) { Fail "-Version and -Evidence are required: the number the owner set, and his words asking for it." }
        if ($Version -notmatch $VERSION_RE) { Fail "'$Version' is not X.Y.Z." }
        $target = [version]$Version
        Sync-Nexus $key
        $fl = Last-Posted $key $ledger
        if ($fl -and $target -le $fl) { Fail ("{0} is not above the last posted number {1}; a posted number is never reused." -f $target, $fl) }
        $open = Open-Entry $key $ledger
        $higher = @($ledger | Where-Object { $_.mod -eq $key -and $_.status -ne 'withdrawn' -and -not (Posted-Of $_) -and $_ -ne $open -and (Parse-Version $_.version) -gt $target })
        if ($higher.Count -gt 0) { Fail ("{0}: the ledger holds unposted {1} above it, which would stay the open number; withdraw that first or pick a number above it." -f $target, (($higher | ForEach-Object { "$($_.version) $($_.status)" }) -join ', ')) }
        Write-Output ("renumber  {0}   last posted {1}   open {2}   ->   {3}   ({4})" -f $key, $(if ($fl) { $fl } else { '(none)' }), $(if ($open) { "$($open.version) $($open.status)" } else { '(none)' }), $target, $Evidence)
        $locs = @($e.locations)
        $unknown = Scan-UnknownLiterals $repoPath $locs @($e.ignore)
        foreach ($u in $unknown) { Flag ("version literal this tool does not own: {0}" -f $u) }
        if ($script:Failures.Count -gt 0) { Fail 'nothing written.' }
        Write-Locations $repoPath $locs $target
        if ($script:Failures.Count -gt 0) { Fail 'a location could not be written; the repo is now PARTIALLY stamped - fix the location and renumber again.' }
        if ($open -and $open.version -ne $target.ToString()) {
            $ov = $open.version
            $ledger = @($ledger | ForEach-Object { if ($_.mod -eq $key -and $_.version -eq $ov -and $_.status -ne 'withdrawn') { $_.evidence = "withdrawn by renumber to $target - $Evidence; it was $($_.status): $($_.evidence)"; $_.status = 'withdrawn' }; $_ })
        }
        $entry = [pscustomobject]@{ mod = $key; version = $target.ToString(); status = 'untested'; evidence = "issued by renumber (the owner): $Evidence"; sha256 = $null; recorded = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss') }
        $ledger = @($ledger | Where-Object { -not ($_.mod -eq $key -and $_.version -eq $target.ToString()) }) + $entry
        Save-Ledger $ledger
        Ok ("{0} issued as UNTESTED (owner-set). Build now, then package; record it working with evidence and the DLL hash." -f $target)
        Write-Output $target.ToString()
        exit 0
    }

    'restart' {
        # THE FIRST RELEASE IS 1.0.0 (the owner, 2026-10-05, AMF for Witcher 3: "don't forget that this is completely
        # unreleased. So the released version will be version 1.0.0"). Test builds of a mod nobody has downloaded took
        # 1.0.0-1.0.5 on the way; a number is spent by RELEASING it, so the first release still starts at 1.0.0. The
        # pre-release entries are kept, moved to version-ledger-prerelease.json, and the next bump issues 1.0.0 as for a
        # new mod. Refused once Nexus has any version or a version is recorded posted (a backfill 'posted: unknown' is the
        # one exception - the owner's word that it is unreleased outranks it), and while a vX.Y.Z tag remains (deleting a
        # pushed tag needs the owner's OK, and is done before this, by hand).
        $key = Resolve-Key $Mod $reg
        $e = $reg.$key
        $repoPath = Repo-Path $key $e
        if (-not (Test-Path -LiteralPath $repoPath)) { Fail "registered repo is gone: $repoPath" }
        if (-not $Evidence) { Fail "-Evidence is required: the owner's words saying the mod is unreleased and starts at 1.0.0." }
        Sync-Nexus $key -Force
        if ("$($reg.$key.nexusVersion)") { Fail ("{0} is on Nexus (published {1}); a released mod is never restarted - bump instead." -f $key, $reg.$key.nexusVersion) }
        $out = @($ledger | Where-Object { $_.mod -eq $key -and (Posted-Of $_) -and (Posted-Of $_).channel -ne 'unknown' })
        if ($out.Count -gt 0) { Fail ("{0} has posted versions ({1}); a released mod is never restarted - bump instead." -f $key, (($out | ForEach-Object { "$($_.version) $((Posted-Of $_).channel)" }) -join ', ')) }
        $localTags = @(& git -C $repoPath tag -l 'v*' 2>$null | Where-Object { $_ -match '^v\d+\.\d+\.\d+$' })
        $remoteTags = @()
        # kit: only local tags are checked; a tag already pushed is the person's to look for
        if ($localTags.Count -or $remoteTags.Count) {
            Fail ("{0}: release tags are still there (local: {1}; pushed: {2}). Delete them first, with the owner's OK - a tag cannot move." -f $key, ($localTags -join ' '), (($remoteTags | ForEach-Object { $_ -replace '^refs/tags/', '' }) -join ' '))
        }
        $mine = @($ledger | Where-Object { $_.mod -eq $key })
        if ($mine.Count -eq 0) { Fail ("{0} has no ledger entries; bump already issues 1.0.0." -f $key) }
        $archive = @()
        if (Test-Path -LiteralPath $PrereleasePath) { $a = Get-Content -LiteralPath $PrereleasePath -Raw | ConvertFrom-Json; if ($a) { $archive = @($a) } }
        $stamp = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
        foreach ($m in $mine) { $archive += [pscustomobject]@{ mod = $m.mod; version = $m.version; status = $m.status; evidence = $m.evidence; sha256 = $m.sha256; recorded = $m.recorded; posted = (Posted-Of $m); archived = $stamp; reason = "restart before the first release - $Evidence" } }
        Write-Output ("restart  {0}   {1} pre-release entr{2} ({3}) -> version-ledger-prerelease.json   ({4})" -f $key, $mine.Count, $(if ($mine.Count -eq 1) { 'y' } else { 'ies' }), (($mine | ForEach-Object { "$($_.version) $($_.status)" }) -join ', '), $Evidence)
        if ($PSCmdlet.ShouldProcess($PrereleasePath, 'write the pre-release archive')) {
            Write-LedgerView 'version-ledger-prerelease' $PrereleasePath (($archive | ConvertTo-Json -Depth 5))
        }
        Save-Ledger @($ledger | Where-Object { $_.mod -ne $key })
        Ok ("{0} restarted: 'bump' now issues 1.0.0." -f $key)
        exit 0
    }

    'reopen' {
        # RETIRED 2026-10-11, kept as a no-op so an old note or script still answers. It existed because a number used to be
        # spent by WORKING (the owner, 2026-09-28: "It's still unreleased. So keep the former version and add to the change
        # log from there"); since the owner's 2026-10-11 change a number is spent only by POSTING it, so an unposted
        # version is open by itself and 'bump' returns it. Nothing is written here.
        $key = Resolve-Key $Mod $reg
        Sync-Nexus $key
        $fl = Last-Posted $key $ledger
        if ($Version) {
            $pv = Assert-Shape $Version
            if ($fl -and $pv -le $fl) { Fail ("{0} is at or below the last posted number {1} of {2}; a posted number is never reopened - 'bump -Kind' issues {3}." -f $pv, $fl, $key, (Expected-Text $key $ledger)) }
        }
        $open = Open-Entry $key $ledger
        Write-Output ("reopen  {0}   no longer needed (2026-10-11): a number stays open until it is POSTED, and 'bump' returns it." -f $key)
        if ($open) { Note ("open now: {0} ({1}) - change it, package it, record it working again after the test." -f $open.version, $open.status) }
        else { Note ("nothing is open; 'bump -Kind' issues {0}." -f (Expected-Text $key $ledger)) }
        exit 0
    }

    'stamp' {
        $key = Resolve-Key $Mod $reg
        $e = $reg.$key
        $repoPath = Repo-Path $key $e
        $vals = Read-Locations $repoPath @($e.locations)
        $bin = Find-BuiltDll $repoPath $Dll
        if ($bin) { $dv = Dll-Version $bin; $vals["built DLL ($($bin.Name))"] = $(if ($dv) { $dv.ToString() } else { '(no VERSIONINFO)' }) }
        Write-Output ("stamp  {0}" -f $key)
        foreach ($k in $vals.Keys) { Note ("{0,-40} {1}" -f $k, $vals[$k]) }
        $distinct = @($vals.Values | Where-Object { $_ -match $VERSION_RE } | Sort-Object -Unique)
        $bad = @($vals.Values | Where-Object { $_ -notmatch $VERSION_RE })
        if ($bad.Count -gt 0) { Flag ("{0} location(s) unreadable" -f $bad.Count) }
        if ($distinct.Count -gt 1) { Flag ("locations disagree: {0}" -f ($distinct -join ', ')) }
        if ($Version) { $pv = Assert-Shape $Version; foreach ($d in $distinct) { if ($d -ne $pv.ToString()) { Flag ("expected {0}, found {1}" -f $pv, $d) } } }
        foreach ($u in (Scan-UnknownLiterals $repoPath @($e.locations) @($e.ignore))) { Flag ("version literal this tool does not own: {0}" -f $u) }
        if ($script:Failures.Count -gt 0) { Fail ("{0} problem(s)." -f $script:Failures.Count) }
        Ok ("all {0} location(s) agree on {1}" -f $vals.Count, $distinct[0])
        exit 0
    }

    'record' {
        $key = Resolve-Key $Mod $reg
        if (-not $Version -or -not $Status) { Fail '-Version and -Status are required.' }
        $pv = Assert-Shape $Version
        $e = $reg.$key
        Invoke-PendingCleanups $key   # a writing action: any pending clean-up of this mod runs first (2026-10-13)
        $existing = $ledger | Where-Object { $_.mod -eq $key -and $_.version -eq $pv.ToString() } | Select-Object -First 1
        $hash = $Sha256
        $artifacts = @()
        if (-not $existing) {
            # only a number the ledger would issue now can be recorded without a row: the open one; with nothing open, 1.0.0
            # for a mod with nothing out, else LAST POSTED stepped by one of the three kinds (semantic versioning, 2026-10-21)
            $expect = Expected-Number $key $ledger
            $flr = Last-Posted $key $ledger
            $allowed = if ($expect) { @($expect) } else { @('patch', 'minor', 'major' | ForEach-Object { Next-Number $flr $_ }) }
            if (@($allowed | Where-Object { $_ -eq $pv }).Count -eq 0) { Fail ("{0} was never issued for {1} and is not the next number ({2}). The ledger issues numbers; it does not accept them." -f $pv, $key, (Expected-Text $key $ledger)) }
        }
        $wasPosted = Posted-Of $existing
        if ($Status -eq 'working') {
            if (-not $Evidence) { Fail 'working needs -Evidence: what was OBSERVED in game, and when.' }
            if ($Dll) { $hash = Dll-Hash (Get-Item -LiteralPath $Dll) }
            if (-not $hash) { Fail 'working needs the SHA-256 of the binary that ran (-Sha256, or -Dll <path> to compute it). A number belongs to exactly one binary.' }
            $hash = $hash.ToUpper()
            $pkg = Find-Package $e.displayName $pv.ToString() (Get-ModGame -Entry $e -ProjectRoot $Root) $hash
            Show-PackagePick
            if ($pkg) {
                Note ("compared with the package {0}\{1}" -f (Split-Path $pkg.PkgRoot -Leaf), $pkg.Name)
                $pd = Package-Dlls $pkg
                $match = @($pd | Where-Object { (Dll-Hash $_) -eq $hash })
                if ($pd.Count -gt 0 -and $match.Count -eq 0) { Fail ("the packaged DLL under '{0}' is not the binary that ran (hash mismatch). The build that was observed working is not the one packaged under this number." -f $pkg.Name) }
                # EVERY ARTEFACT (2026-10-13): the row also lists every artefact of this package with its hash, so a stale
                # second file (a .ws beside a correct blob0.bundle) cannot ship under the number. Listed only when the
                # recorded hash is one of them - a list of a package that does not hold the proven file would vouch for it.
                $arts = @(Get-PackageArtefactList $pkg.FullName $script:ForeignBinaries)
                if (@($arts | Where-Object { $_.sha256 -eq $hash }).Count) {
                    $artifacts = $arts
                    Note ("artefacts recorded ({0}): {1}" -f $arts.Count, (($arts | ForEach-Object { $_.file }) -join ', '))
                } else {
                    Note ("no artefact of '{0}' has this hash, so no artefact list is recorded; the finalize gate compares the hash alone." -f $pkg.Name)
                }
            } else {
                if (-not $script:PackagePickRefused) { Note ("no package '{0} {1}' exists yet; the hash is recorded and the finalize gate will compare it to the package when one is made." -f $e.displayName, $pv) }
            }
        }
        $props = [ordered]@{ mod = $key; version = $pv.ToString(); status = $Status; evidence = $Evidence; sha256 = $hash }
        if ($artifacts.Count) { $props.artifacts = @($artifacts) }   # absent when there was no package to list (as before)
        $props.recorded = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
        $entry = [pscustomobject]$props
        if ($wasPosted) { Set-Posted $entry $wasPosted }   # a status change never un-posts a number
        if ($existing -and $existing.PSObject.Properties['prunePending'] -and $existing.prunePending) { $entry | Add-Member -NotePropertyName prunePending -NotePropertyValue $true }   # a clean-up still pending stays pending
        $ledger = @($ledger | Where-Object { -not ($_.mod -eq $key -and $_.version -eq $pv.ToString()) }) + $entry
        Save-Ledger $ledger
        Ok ("{0} {1} = {2}" -f $key, $pv, $Status)
        if ($Status -in 'failed','scratch' -and -not $wasPosted) { Note ("{0} is not posted, so it stays the open number; the next bump reuses it (rule 48)." -f $pv) }
        Log-Event 6 "build $Status" $key $pv.ToString() $Evidence
        if ($Status -eq 'working') { Invoke-ProfileVersions $key $pv.ToString() 'version-gate record working' (@($hash) + @($artifacts | ForEach-Object { $_.sha256 })) }
        exit 0
    }

    'gate' {
        # THE GATE. Called by package-mod.ps1 (-Stage package) and pre-finalize-check.ps1
        # (-Stage finalize). Exit 0 is the only pass; callers stop on anything else.
        $key = Resolve-Key $Mod $reg
        if (-not $Version -or -not $Stage) { Fail '-Version and -Stage package|finalize are required.' }
        $pv = Assert-Shape $Version
        $e = $reg.$key
        $repoPath = Repo-Path $key $e
        Write-Output ("gate  {0}  {1}  [{2}]" -f $key, $pv, $Stage)
        Sync-Nexus $key
        $entry = $ledger | Where-Object { $_.mod -eq $key -and $_.version -eq $pv.ToString() } | Select-Object -First 1

        # 1. the ledger issued this number
        if (-not $entry) { Flag ("{0} was never issued by the ledger for {1}. Run bump; do not type numbers." -f $pv, $key) }
        elseif ($entry.status -in 'failed','scratch','withdrawn') { Flag ("{0} is recorded {1}; it is not shippable (bump reuses a failed or scratch number)." -f $pv, $entry.status) }
        else { Ok ("ledger: {0} = {1}" -f $pv, $entry.status) }

        # 2. it is the right number: the OPEN one - the unposted number in flight, issued by bump as LAST POSTED stepped by the kind (2026-10-11, 2026-10-21)
        $fl = Last-Posted $key $ledger
        $expect = Expected-Number $key $ledger
        if ($Stage -eq 'package') {
            $ep = Posted-Of $entry
            if ($ep) { Flag ("{0} is already POSTED ({1}{2}); a posted number is never packaged again - bump -Kind issues {3}." -f $pv, $ep.channel, $(if ($ep.at) { " $($ep.at)" } else { '' }), (Expected-Text $key $ledger)) }
            elseif ($fl -and $pv -le $fl) { Flag ("{0} is at or below the last posted number {1}; a posted number is spent - bump -Kind issues {2}." -f $pv, $fl, (Expected-Text $key $ledger)) }
            elseif ($pv -ne $expect -and -not ($entry -and $entry.status -eq 'working')) { Flag ("{0} is not the open number (last posted {1}; the number in flight is {2})." -f $pv, $(if ($fl) { $fl } else { 'none' }), (Expected-Text $key $ledger)) }
            else { Ok ("number: {0} is open (last posted {1})" -f $pv, $(if ($fl) { $fl } else { 'none' })) }
        } else {
            if (-not ($entry -and $entry.status -eq 'working')) { Flag ("finalize needs status WORKING with evidence; {0} is {1}." -f $pv, $(if ($entry) { $entry.status } else { 'unrecorded' })) }
            else { Ok ("working: {0}" -f $entry.evidence) }
        }

        # 3. every location in the repo says so, and no literal escaped the tool
        if (Test-Path -LiteralPath $repoPath) {
            $vals = Read-Locations $repoPath @($e.locations)
            foreach ($k in $vals.Keys) { if ($vals[$k] -ne $pv.ToString()) { Flag ("{0} says {1}" -f $k, $vals[$k]) } }
            if (@($vals.Keys | Where-Object { $vals[$_] -ne $pv.ToString() }).Count -eq 0) { Ok ("all {0} repo location(s) say {1}" -f $vals.Count, $pv) }
            foreach ($u in (Scan-UnknownLiterals $repoPath @($e.locations) @($e.ignore))) { Flag ("version literal this tool does not own: {0}" -f $u) }
        } else { Flag ("repo missing: {0}" -f $repoPath) }

        # 4. the binary carries the number
        if ($Stage -eq 'package') {
            $bin = Find-BuiltDll $repoPath $Dll
            # ASSET-ONLY MOD at the package stage (2026-10-06: Unbind Vanilla Controls for Witcher 3, an input.xml, a
            # script and string tables - nothing is compiled). The finalize stage below already accepts a package with
            # no DLL and ties the number to an asset (record -Dll <asset>); the package stage refused it outright.
            # Accepted only when the repo builds no DLL AND the package for this number exists and carries none.
            $assetPkg = $null
            if (-not $bin) {
                $assetPkg = Find-Package $e.displayName $pv.ToString() (Get-ModGame -Entry $e -ProjectRoot $Root) $(if ($entry) { "$($entry.sha256)" } else { '' }) @(Get-RowArtifacts $entry)
                Show-PackagePick
                if ($assetPkg -and @(Package-Dlls $assetPkg | Where-Object { $_ }).Count -gt 0) { $assetPkg = $null }   # @($null).Count is 1
            }
            if (-not $bin -and $assetPkg) {
                Ok ("asset-only mod: no DLL in the repo or in '{0}'; 'record -Dll <asset>' ties the number to a shipped file" -f $assetPkg.Name)
                if (@(Get-RowArtifacts $entry).Count) { Test-RowArtefacts $entry $assetPkg }   # 2026-10-13: a listed row, every file
            }
            elseif (-not $bin) { Flag 'no built DLL found to verify.' }
            else {
                $dv = Dll-Version $bin
                if (-not $dv) { Flag ("{0} carries no VERSIONINFO resource; the build must stamp it." -f $bin.Name) }
                elseif ($dv -ne $pv) { Flag ("the DLL's own FileVersion is {0}, not {1}: the build for {1} did not produce this binary (build failed or was skipped)." -f $dv, $pv) }
                else { Ok ("DLL FileVersion {0}" -f $dv) }
                if ($script:Failures.Count -eq 0 -and $entry) {
                    # bind the number to this binary: the hash rides on the untested entry until 'record working' confirms the same bytes ran
                    $h = Dll-Hash $bin
                    if ($entry.status -eq 'working' -and $entry.sha256 -and $entry.sha256.ToUpper() -ne $h) {
                        # CHANGES WENT IN UNDER AN OPEN NUMBER (2026-10-11): it had been recorded working, the binary is new, so
                        # it is untested again - the automatic form of the retired 'reopen'. The proof has to be re-earned.
                        $entry.evidence = "rebuilt under the same unposted number after it was recorded working ($($bin.Name) sha256 $($h.Substring(0, 8))...); record it working again after the test. Was working on $($entry.sha256.Substring(0, 8))...: $($entry.evidence)"
                        $entry.status = 'untested'
                        $entry.recorded = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
                        Note ("{0} was recorded working on another binary; it is UNTESTED again until the new build is tested and recorded." -f $pv)
                    }
                    if ($entry.PSObject.Properties['artifacts'] -and "$($entry.sha256)".ToUpper() -ne $h) {
                        # the list described the previous binary's package (2026-10-13); 'record working' lists the new one
                        $entry.PSObject.Properties.Remove('artifacts')
                        Note 'the artefact list recorded with the previous binary is dropped; record working lists the new package.'
                    }
                    $entry.sha256 = $h
                    Save-Ledger $ledger
                    Ok ("bound to {0} (sha256 {1}...)" -f $bin.Name, $h.Substring(0, 8))
                }
            }
        } else {
            $pkg = Find-Package $e.displayName $pv.ToString() (Get-ModGame -Entry $e -ProjectRoot $Root) $(if ($entry) { "$($entry.sha256)" } else { '' }) @(Get-RowArtifacts $entry)
            Show-PackagePick
            if (-not $pkg -and -not $script:PackagePickRefused) { Flag ("no package '{0} {1}' (or FOMOD) in 7. current test builds\{2}." -f $e.displayName, $pv, (Get-PackageFolderName -ModName $e.displayName -Game (Get-ModGame -Entry $e -ProjectRoot $Root) -ProjectRoot $Root)) }
            elseif ($pkg -and @(Get-RowArtifacts $entry).Count) {
                # EVERY LISTED ARTEFACT (2026-10-13): the row names each artefact, so each one is checked - a stale .ws
                # beside the proven blob0.bundle, or an extra unlisted script, now closes the gate naming the file. A
                # code package's DLLs must still carry the number.
                Test-RowArtefacts $entry $pkg
                $pd = @(Package-Dlls $pkg)
                if ($pd.Count) {
                    $vers = @($pd | ForEach-Object { Dll-Version $_ } | Where-Object { $_ } | Sort-Object -Unique)
                    if (@($vers | Where-Object { $_ -ne $pv }).Count -gt 0) { Flag ("packaged DLL(s) report {0}, not {1}." -f ($vers -join ', '), $pv) } else { Ok ("packaged DLL FileVersion {0}" -f $pv) }
                }
            }
            else {
                # a row with sha256 alone (every row recorded before 2026-10-13): the single-hash checks, unchanged
                    $pd = Package-Dlls $pkg
                    if ($pd.Count -eq 0) {
                        # ASSET-ONLY MOD. No DLL is not automatically a broken package - a mod can be a
                        # plugin and loose files with no code at all, and this gate used to refuse every
                        # one of them (2026-09-16: Jarl Ulfric Armor Replacer). The rule it exists to
                        # enforce still holds: the number belongs to exactly one ARTEFACT. For these mods
                        # that artefact is the PLUGIN, so the recorded hash is compared against the
                        # package's .esp/.esl/.esm the same way it would be against a DLL.
                        $plugins = @(Get-PackagePlugins $pkg.FullName)   # test-build-pick.ps1: one home for the classification
                        if ($plugins.Count -eq 0) {
                            # ART-ONLY MOD (2026-09-17: Dragon's Eye Minimap - Norden UI Reskin, two SWFs and documents).
                            # No DLL and no plugin is still a package with an artefact: the shipped asset files. The
                            # number is tied to whichever asset the working entry's hash names (record -Dll <asset>),
                            # so a repackaged file cannot ship under a number that was proven with different bytes.
                            # 2026-09-29 (Oblivion Paper Theme, an AMF theme of one INI and four PNGs): a file under a GAME tree
                            # (Data\, SKSE\, OblivionRemastered\, stylesheets\) is an asset whatever its extension - the
                            # extension list below only keeps a package's own documents and previews from counting.
                            $assets = @(Get-PackageAssets $pkg.FullName)   # test-build-pick.ps1: one home for the classification
                            if ($assets.Count -eq 0) {
                                Flag ("package '{0}' holds neither a DLL, a plugin nor any asset file - there is no artefact to tie the number to." -f $pkg.Name)
                            } elseif (-not $entry -or -not $entry.sha256) {
                                Flag ("package '{0}' is art-only and the working entry carries no hash; re-record with -Dll pointing at the shipped asset that was proven." -f $pkg.Name)
                            } else {
                                $ahit = @($assets | Where-Object { (File-Sha256 $_.FullName) -eq $entry.sha256.ToUpper() })
                                if ($ahit.Count -eq 0) { Flag ("package '{0}' is art-only and none of its {1} asset file(s) matches the recorded hash {2}... - the proven file is not what is packaged." -f $pkg.Name, $assets.Count, $entry.sha256.Substring(0, 8)) }
                                else { Ok ("art-only package: {0} matches the recorded hash" -f $ahit[0].Name) }
                            }
                        } elseif (-not $entry -or -not $entry.sha256) {
                            Flag ("package '{0}' is asset-only and the working entry carries no hash, so the shipped files cannot be tied to what was observed. Re-record with -Sha256." -f $pkg.Name)
                        } else {
                            $hit = @($plugins | Where-Object { (File-Sha256 $_.FullName) -eq $entry.sha256.ToUpper() })
                            if ($hit.Count -eq 0) {
                                Flag ("asset-only package: no plugin in it matches the hash recorded as working. Checked: {0}" -f (($plugins | ForEach-Object { $_.Name }) -join ', '))
                            } else {
                                Ok ("asset-only package; the plugin '{0}' is the artefact observed working (hash match)" -f $hit[0].Name)
                            }
                        }
                    }
                    else {
                        $vers = @($pd | ForEach-Object { Dll-Version $_ } | Where-Object { $_ } | Sort-Object -Unique)
                        if (@($vers | Where-Object { $_ -ne $pv }).Count -gt 0) { Flag ("packaged DLL(s) report {0}, not {1}." -f ($vers -join ', '), $pv) } else { Ok ("packaged DLL FileVersion {0}" -f $pv) }
                        if ($entry -and $entry.sha256) {
                            $hit = @($pd | Where-Object { (Dll-Hash $_) -eq $entry.sha256.ToUpper() })
                            if ($hit.Count -eq 0) { Flag 'the packaged DLL is not the binary recorded as working (hash mismatch).' } else { Ok 'packaged DLL is the binary that was observed working (hash match)' }
                        } elseif ($entry) {
                            # No hash on the working entry. If Nexus already carries this version (or a later one),
                            # the upload is the proof (the owner, 2026-09-12: the last upload passed the finalize gate),
                            # and the packaged DLL's hash is backfilled so the tie exists from here on.
                            $nxv = Parse-Version "$($e.nexusVersion)"
                            if ($nxv -and $nxv -ge $pv) {
                                $entry.sha256 = Dll-Hash $pd[0]; Save-Ledger $ledger
                                Note ("working entry had no hash; Nexus mod {0} already publishes {1}, so the upload is the proof - hash backfilled from the package" -f $e.nexusModId, $nxv)
                            } else {
                                Flag 'the working entry carries no hash, so the shipped binary cannot be tied to the one observed. Re-record with -Dll.'
                            }
                        }
                    }
            }
            if (Test-Path -LiteralPath (Join-Path $repoPath '.git')) {
                # THE TAG IS MADE AFTER THE GATE (2026-10-13, straight flow C, the Fable Advisor Agent's ruling): finalize-mod
                # creates vX.Y.Z only once this gate has passed, so a missing tag is fine here. A tag of that name that
                # EXISTS on another commit than HEAD refuses - the release would ship commits its tag does not hold. Nothing
                # here creates, moves or deletes a tag.
                $tags = @(git -C $repoPath tag 2>$null)
                $tn = if ($tags -contains "v$pv") { "v$pv" } elseif ($tags -contains "$pv") { "$pv" } else { $null }
                if (-not $tn) { Ok ("no git tag v{0} yet - finalize-mod creates it after this gate passes" -f $pv) }
                else {
                    $tc = "$(git -C $repoPath rev-list -n 1 $tn 2>$null)".Trim()
                    $hc = "$(git -C $repoPath rev-parse HEAD 2>$null)".Trim()
                    if ($tc -and $tc -eq $hc) { Ok ("git tag {0} is at HEAD" -f $tn) }
                    else { Flag ("tag {0} exists on commit {1}, not on HEAD {2} - move or delete tag {0}, or commit on top of it" -f $tn, $tc, $hc) }
                }
            }
        }

        if ($script:Failures.Count -gt 0) { Fail ("GATE CLOSED - {0} problem(s). Nothing proceeds until every line above is clean." -f $script:Failures.Count) }
        Write-Output ("PASS  {0} {1} clears the {2} gate." -f $key, $pv, $Stage)
        exit 0
    }

    'posted' {
        # A NUMBER IS SPENT BY POSTING IT (the owner, 2026-10-11: "change the versioning logic from has to be proven working
        # to get the number to has to be posted to Nexus. To get a new number."). This records the posting: the evidence
        # names where it went (the Nexus file id or URL, the Mega link, the folder), -File hashes the archive that went up.
        # Posting still needs a WORKING record (rule 21); -WhatIf checks that without writing - nexus-upload.py runs it
        # before the upload and for real after a verified upload. A re-post of the same number (an owner-approved
        # --same-version upload) updates the record. -Backfill is the 2026-10-11 backfill's way in: it also takes a
        # published version the ledger never knew or holds as non-working, and the channel 'unknown'.
        $key = Resolve-Key $Mod $reg
        if (-not $Version) { Fail '-Version is required: the number that was posted.' }
        $pv = Assert-Shape $Version
        $e = $reg.$key
        $ch = if ($Channel) { $Channel } elseif ("$($e.publishChannel)") { "$($e.publishChannel)" } elseif ($e.nexusModId) { 'nexus' } else { $null }
        if (-not $ch) { Fail ("-Channel nexus|members|mega|local|modio is required: {0} has no Nexus page and no publish channel in the registry (link -Channel sets one)." -f $key) }
        if ($ch -eq 'unknown' -and -not $Backfill) { Fail "'unknown' is the backfill's mark for a posting nobody can determine; a real posting names its channel." }
        if (-not $Evidence -and -not $FileId) { Fail '-Evidence is required: where it was posted (Nexus file id or URL, Mega link, the folder it was copied into).' }
        $row = $ledger | Where-Object { $_.mod -eq $key -and $_.version -eq $pv.ToString() } | Select-Object -First 1
        if (-not $row) {
            if (-not $Backfill) { Fail ("{0} was never issued for {1}; only a number the ledger issued, built, tested and recorded WORKING can be posted." -f $pv, $key) }
            $row = [pscustomobject]@{ mod = $key; version = $pv.ToString(); status = 'working'; evidence = "PUBLISHED before the ledger knew it ($ch): $Evidence - a posted build passed the finalize gate (the owner, 2026-09-12); recorded by the 2026-10-11 backfill"; sha256 = $null; recorded = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss') }
            $ledger = @($ledger) + $row
            Note ("{0} had no ledger row: recorded working from its publication" -f $pv)
        } elseif ($row.status -ne 'working') {
            if (-not $Backfill) { Fail ("{0} {1} is {2}. Posting needs a WORKING record first (rule 21): test it, record it working with the binary's hash, then post." -f $key, $pv, $row.status) }
            Note ("{0} is {1} in the ledger but is already out; recorded posted, status left as it is" -f $pv, $row.status)
        }
        $prev = Posted-Of $row
        if ($prev -and $prev.channel -ne 'unknown' -and $ch -eq 'unknown') { Ok ("{0} {1} is already recorded posted ({2}); unchanged" -f $key, $pv, $prev.channel); exit 0 }
        $hash = $Sha256
        if ($File) { if (-not (Test-Path -LiteralPath $File)) { Fail "-File '$File' does not exist." }; $hash = (File-Sha256 $File) }
        # MOD.IO (2026-10-15, the owner: "teach it"). The mod.io file of a version can be a different build from the one
        # packaged for Nexus (Simple Loadout System W3: mod.io's 1.0.3 is the poll fix alone, packaged by
        # tools\package_modio.py, while the build tested next carried new features). So a mod.io posting names the
        # archive that went up (-File), and the version's WORKING record must be of THAT build: its hash is the archive's
        # own, or one file inside the archive has it. Any other hash means the working record belongs to another build,
        # and recording the posting would stamp that build's hash onto the mod.io number.
        if ($ch -eq 'modio') {
            if (-not $File) { Fail '-Channel modio needs -File <the archive uploaded to mod.io>: the posting records the hash of the file that went up.' }
            $rowHash = "$($row.sha256)".ToUpper()
            if (-not $rowHash) { Fail ("{0} {1} is working with no hash; record it working with -Dll <the mod.io archive or a file in it> first." -f $key, $pv) }
            $inArchive = $false
            if ($hash -ne $rowHash) {
                Add-Type -AssemblyName System.IO.Compression.FileSystem
                $zip = [System.IO.Compression.ZipFile]::OpenRead((Resolve-Path -LiteralPath $File).Path)
                try {
                    foreach ($ent in $zip.Entries) {
                        if ($ent.FullName.EndsWith('/')) { continue }
                        $sha = [System.Security.Cryptography.SHA256]::Create(); $st = $ent.Open()
                        try { $h = ([System.BitConverter]::ToString($sha.ComputeHash($st))).Replace('-', '') } finally { $st.Dispose(); $sha.Dispose() }
                        if ($h -eq $rowHash) { $inArchive = $true; Note ("the working hash is the archive's {0}" -f $ent.FullName); break }
                    }
                } finally { $zip.Dispose() }
                if (-not $inArchive) { Fail ("{0} {1}'s working hash {2} is neither '{3}' nor any file inside it: the working record is of another build. Record the mod.io build working (-Dll <the archive>) before recording its posting." -f $key, $pv, $rowHash.Substring(0, [Math]::Min(8, $rowHash.Length)), (Split-Path $File -Leaf)) }
            }
        }
        $obj = New-Posted $ch $FileId $(if ($File) { Split-Path $File -Leaf } else { $null }) $hash $(if ($prev -and $prev.channel -ne 'unknown') { "$Evidence (re-posted; before: $($prev.channel) $($prev.at) $($prev.ref))" } else { $Evidence })
        $fl = Last-Posted $key $ledger
        Set-Posted $row $obj
        if ($WhatIfPreference) { Ok ("{0} {1} can be recorded POSTED ({2}): it is {3}{4}." -f $key, $pv, $ch, $row.status, $(if ($prev) { ', already posted once - the record would be updated' } else { '' })); exit 0 }
        Save-Ledger $ledger
        Ok ("{0} {1} = POSTED ({2}{3}). Next number: {4}." -f $key, $pv, $ch, $(if ($FileId) { " $FileId" } else { '' }), (Expected-Text $key $ledger))
        if ($fl -and $pv -lt $fl) { Note ("{0} is below the last posted number {1}; the floor stays {1}." -f $pv, $fl) }
        Log-Event 11 'posted' $key $pv.ToString() ("{0}: {1}{2}" -f $ch, $Evidence, $(if ($hash) { " sha256 $hash" } else { '' }))
        # the clean-up (2026-10-13): Save-Ledger marked this posting prunePending if it is NEW; a re-post of a number the
        # ledger already held as posted is not new and prunes nothing. Older pending clean-ups of the mod run here too.
        Invoke-PendingCleanups $key
        Invoke-ProfileVersions $key $pv.ToString() "version-gate posted ($ch)" (@("$($row.sha256)") + @(@($row.artifacts) | Where-Object { $_ } | ForEach-Object { $_.sha256 }))
        exit 0
    }

    'retract' {
        # A POSTED CLAIM THAT WAS WRONG (2026-10-25). The 2026-10-12 Nexus read took two pages' version '1' as 1.0.0 and
        # recorded 1.0.0 posted, while the only file ever up was 1.0.1 (MO2 Pin Plugins, HUD Position Manager). There was
        # no way to take a claim back: 'posted' only adds, and a hand edit of the ledger is overwritten from the event log.
        # This takes the claim off the row and keeps it under 'retracted' (the row's whole history stays in the log as
        # event kind 'posted-retracted'); the status is left alone. Nexus is re-read first: while the linked page still
        # publishes V, the next read would record it posted again, so that is refused - correct the page first.
        $key = Resolve-Key $Mod $reg
        if (-not $Version) { Fail '-Version is required: the number whose posted claim is wrong.' }
        $pv = Assert-Shape $Version
        if (-not $Evidence) { Fail '-Evidence is required: why the claim is wrong and what is really out (file ids, API read).' }
        Sync-Nexus $key -Force
        $row = $ledger | Where-Object { $_.mod -eq $key -and $_.version -eq $pv.ToString() } | Select-Object -First 1
        if (-not $row) { Fail ("{0} {1} has no ledger row." -f $key, $pv) }
        $prev = Posted-Of $row
        if (-not $prev) { Fail ("{0} {1} is not recorded posted; nothing to retract." -f $key, $pv) }
        $e = $reg.$key
        if ($e.nexusModId -and (Parse-Version "$($e.nexusVersion)") -eq $pv) { Fail ("{0}'s Nexus page {1} publishes {2} (read {3}); the next read would record it posted again. Correct the page first." -f $key, $e.nexusModId, $pv, $e.nexusChecked) }
        $flBefore = Last-Posted $key $ledger
        $hist = @(@($row.retracted) | Where-Object { $_ }) + [pscustomobject]@{ at = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'); evidence = $Evidence; was = $prev }
        $row.PSObject.Properties.Remove('posted')
        $row.PSObject.Properties.Remove('prunePending')
        if ($row.PSObject.Properties['retracted']) { $row.retracted = $hist } else { $row | Add-Member -NotePropertyName retracted -NotePropertyValue $hist }
        $flAfter = Last-Posted $key $ledger
        if ($WhatIfPreference) { Ok ("{0} {1}'s posted claim ({2} {3}) can be retracted; last posted {4} -> {5}." -f $key, $pv, $prev.channel, $prev.at, $flBefore, $(if ($flAfter) { $flAfter } else { '(none)' })); exit 0 }
        Save-Ledger $ledger
        Ok ("{0} {1}: posted claim RETRACTED (was {2} {3}); status stays {4}. Last posted {5} -> {6}; next number: {7}." -f $key, $pv, $prev.channel, $prev.at, $row.status, $flBefore, $(if ($flAfter) { $flAfter } else { '(none)' }), (Expected-Text $key $ledger))
        Log-Event 11 'posted-retracted' $key $pv.ToString() ("was {0} {1}: {2}" -f $prev.channel, $prev.at, $Evidence)
        exit 0
    }

    'backfill' {
        # THE 2026-10-11 BACKFILL: every version already out counts as posted. Sources, strongest first: the Nexus page's
        # General version and its primary main file version (nexus-version-audit.py --json, read-only; -From takes a JSON
        # it wrote before), the registry's cached nexusVersion, the zips in 11. Nexus distro\1. members for a mod whose
        # publishChannel is members, and posted/upload events in pipeline-events.jsonl. Where nothing can tell, the last
        # WORKING build is marked 'posted: unknown', so the floor is never below what the old rule (LAST WORKING + 1)
        # would have issued and nothing is issued twice. A floor already in the ledger is never lowered. -WhatIf prints
        # the table and writes nothing.
        $auditPath = $From
        $audit = @()
        if ($auditPath -and (Test-Path -LiteralPath $auditPath)) { $audit = @(Get-Content -LiteralPath $auditPath -Raw -Encoding UTF8 | ConvertFrom-Json) }
        else { Note "no audit data; the registry's cached Nexus versions are used" }
        $eventsPath = Find-Role 'pipeline-events' -AllowMissing
        $events = @()
        if (Test-Path -LiteralPath $eventsPath) {
            $events = @(Get-Content -LiteralPath $eventsPath -Encoding UTF8 | Where-Object { $_ -match '"event"\s*:\s*"[^"]*(posted|upload)' } |
                        ForEach-Object { try { $_ | ConvertFrom-Json } catch { } } | Where-Object { $_ -and "$($_.event)" -match '^(posted|uploaded|nexus upload)' })
        }
        $membersDir = Join-Path $Root '11. Nexus distro\1. members'
        $table = New-Object System.Collections.Generic.List[object]
        foreach ($k in (Registry-Keys $reg | Sort-Object)) {
            $e = $reg.$k
            $known = $null; $ch = $null; $ref = $null; $src = @(); $odd = @()
            if ($e.nexusModId -and -not $e.nexusRemoved) {
                $dom = Get-NexusDomain $e
                $a = $audit | Where-Object { "$($_.id)" -eq "$($e.nexusModId)" -and "$($_.domain)" -eq $dom } | Select-Object -First 1
                $cands = @("$($e.nexusVersion)")
                if ($a) { $cands += @("$($a.general)") + @($a.main | ForEach-Object { "$_" }); $src += ("page {0} / main {1}" -f $a.general, (@($a.main) -join ',')); if ("$($a.general)" -ne "$(@($a.main)[0])") { $odd += "page General $($a.general) != main file $(@($a.main) -join ',')" } }
                elseif ("$($e.nexusVersion)") { $src += "registry nexusVersion $($e.nexusVersion) (no audit row)" }
                $vs = @($cands | ForEach-Object { Parse-Version $_ } | Where-Object { $_ } | Sort-Object -Descending)
                if ($vs.Count) { $known = $vs[0]; $ch = 'nexus'; $ref = "https://www.nexusmods.com/$dom/mods/$($e.nexusModId)" }
                else { $odd += 'linked page, but no version readable' }
            }
            if ("$($e.publishChannel)" -eq 'members' -and (Test-Path -LiteralPath $membersDir)) {
                $rx = '^' + [regex]::Escape([string]$e.displayName) + ' (\d+\.\d+\.\d+)\.zip$'
                $z = @(Get-ChildItem -LiteralPath $membersDir -File | Where-Object { $_.Name -match $rx } | Sort-Object { Parse-Version $_.Name } -Descending)
                if ($z.Count) { $zv = Parse-Version $z[0].Name; $src += "1. members\$($z[0].Name)"; if (-not $known -or $zv -gt $known) { $known = $zv; $ch = 'members'; $ref = $membersDir } }
            }
            $ev = @($events | Where-Object { "$($_.mod)" -ieq $k -or "$($_.mod)" -ieq "$($e.displayName)" } | ForEach-Object { Parse-Version "$($_.version)" } | Where-Object { $_ } | Sort-Object -Descending)
            if ($ev.Count) { $src += "event $($ev[0])"; if (-not $known -or $ev[0] -gt $known) { $known = $ev[0]; $ch = $(if ($ch) { $ch } else { 'nexus' }); $ref = 'pipeline-events.jsonl' } }
            $before = Last-Posted $k $ledger
            $lw = Last-Working $k $ledger
            $act = ''
            if ($known) {
                $r = $ledger | Where-Object { $_.mod -eq $k -and $_.version -eq $known.ToString() } | Select-Object -First 1
                if ($r -and (Posted-Of $r) -and (Posted-Of $r).channel -ne 'unknown') { $act = "already posted $known" }
                else {
                    $pev = "backfill 2026-10-11: out before the posted record existed - $($src -join '; ')"
                    if (-not $r) {
                        $r = [pscustomobject]@{ mod = $k; version = $known.ToString(); status = 'working'; evidence = "PUBLISHED before the ledger knew it ($ch, $($src -join '; ')) - a posted build passed the finalize gate (the owner, 2026-09-12); recorded by the 2026-10-11 backfill"; sha256 = $null; recorded = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss') }
                        $ledger = @($ledger) + $r
                        $odd += 'no ledger row for the posted version - created (working)'
                    } elseif ($r.status -ne 'working') { $odd += "the posted version is '$($r.status)' in the ledger" }
                    Set-Posted $r (New-Posted $ch $ref $null $null $pev)
                    $act = "POSTED $known ($ch)"
                }
                if ($before -and $before -gt $known) { $odd += "ledger floor $before is above the published $known - kept" }
            } else {
                $why = if ($e.nexusRemoved) { 'page removed by Nexus moderation' } elseif ("$($e.publishChannel)") { "publishChannel $($e.publishChannel), nothing found" } else { 'no Nexus page, no members zip, no posted event' }
                $src += $why
                if (-not $lw) { $act = 'nothing (no working build)' }
                elseif ($before -and $before -ge $lw) { $act = "already floored at $before" }
                else {
                    $r = $ledger | Where-Object { $_.mod -eq $k -and $_.version -eq $lw.ToString() -and $_.status -eq 'working' } | Select-Object -First 1
                    Set-Posted $r (New-Posted 'unknown' $null $null $null ("backfill 2026-10-11: $why - whether it left the machine cannot be determined, so the last WORKING build is the floor and nothing is issued twice"))
                    $act = "posted: unknown at $lw"
                }
            }
            $o = Open-Entry $k $ledger
            $table.Add([pscustomobject]@{ Mod = $k; Kind = "$($e.kind)"; Action = $act; Open = $(if ($o) { "$($o.version) $($o.status)" } else { '-' }); Next = (Expected-Text $k $ledger); Source = ($src -join '; '); Odd = ($odd -join '; ') })
        }
        $table | Format-Table Mod, Kind, Action, Open, Next, Odd -AutoSize | Out-String -Width 260 | Write-Output
        $nPosted = @($table | Where-Object { $_.Action -like 'POSTED *' }).Count
        $nAlready = @($table | Where-Object { $_.Action -like 'already*' }).Count
        $nUnknown = @($table | Where-Object { $_.Action -like 'posted: unknown*' }).Count
        $nNothing = @($table | Where-Object { $_.Action -like 'nothing*' }).Count
        $nOpen = @($table | Where-Object { $_.Open -ne '-' }).Count
        Write-Output ("backfill: {0} mod(s) - {1} posted from Nexus/members/events, {2} already posted, {3} posted: unknown, {4} with no working build; {5} have an OPEN number; {6} posted event(s) in pipeline-events.jsonl" -f $table.Count, $nPosted, $nAlready, $nUnknown, $nNothing, $nOpen, $events.Count)
        if ($WhatIfPreference) { Write-Output 'backfill: -WhatIf - nothing written.'; exit 0 }
        Save-Ledger $ledger
        Ok 'backfill written to the ledger.'
        exit 0
    }

    'link' {
        # Attach the mod's own Nexus page ID, so the gate can read the published version - or, with -Channel, say how a mod
        # with no Nexus page is published (members: the folder 11. Nexus distro\1. members is read on every action; mega and
        # local: an explicit 'posted' record at the publish step).
        $key = Resolve-Key $Mod $reg
        if (-not $NexusModId -and -not $Channel) { Fail '-NexusModId <our Nexus mod id> or -Channel members|mega|local is required.' }
        if ($Channel) {
            if ($Channel -in 'nexus','unknown','modio') { Fail "-Channel for link is members, mega or local (a Nexus page is linked with -NexusModId; a mod.io file is recorded with 'posted -Channel modio')." }
            $e = $reg.$key
            if ($e.PSObject.Properties['publishChannel']) { $e.publishChannel = $Channel } else { $e | Add-Member -NotePropertyName publishChannel -NotePropertyValue $Channel }
            Save-Registry $reg
            Ok ("{0} is published through '{1}'" -f $key, $Channel)
            if (-not $NexusModId) { Sync-Members $key; exit 0 }
        }
        $e = $reg.$key
        if ($Additional -and -not $Domain) { Fail '-Additional needs -Domain: a second page lives in another game section (site = Modding Tools).' }
        if ($Additional -and -not $e.nexusModId) { Fail ("'{0}' has no main page yet - link the main page first, without -Additional." -f $key) }
        $domain = if ($Domain) { $Domain } else { Get-NexusDomain $e }
        # a page ID means nothing without its section (past-mistakes library 8504): the same number in two sections is two pages
        foreach ($p in @(Linked-Pages $reg)) {
            if ($p.id -ne $NexusModId -or $p.domain -ne $domain) { continue }
            if ($p.key -ne $key -or $Additional) { Fail ("Nexus {0}/{1} is already linked to '{2}'." -f $domain, $NexusModId, $p.key) }
        }
        # kit: the ID is recorded unverified - this kit does not read Nexus (OPTIONAL-SCRIPTS.md)
        $n = @{ version = '(not read)'; name = '(not read)'; status = 'unverified' }
        if ($Additional) {
            $page = [pscustomobject]@{ nexusDomain = $domain; nexusModId = $NexusModId; linked = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss') }
            $list = @(@(@($e.nexusPages) | Where-Object { $_ }) + $page)
            if ($e.PSObject.Properties['nexusPages']) { $e.nexusPages = $list } else { $e | Add-Member -NotePropertyName nexusPages -NotePropertyValue $list }
            Save-Registry $reg
            Ok ("{0} <- additional Nexus page {1}/{2} '{3}' (published {4}, {5}); main page stays {6}/{7}" -f $key, $domain, $NexusModId, $n.name, $n.version, $n.status, (Get-NexusDomain $e), $e.nexusModId)
            exit 0
        }
        if ($e.PSObject.Properties['nexusModId']) { $e.nexusModId = $NexusModId } else { $e | Add-Member -NotePropertyName nexusModId -NotePropertyValue $NexusModId }
        if ($e.PSObject.Properties['nexusDomain']) { $e.nexusDomain = $domain } else { $e | Add-Member -NotePropertyName nexusDomain -NotePropertyValue $domain }
        if ($e.PSObject.Properties['nexusChecked']) { $e.nexusChecked = $null }
        Save-Registry $reg
        Ok ("{0} <- Nexus {1}/{2} '{3}' (published {4}, {5})" -f $key, $domain, $NexusModId, $n.name, $n.version, $n.status)
        Sync-Nexus $key -Force
        exit 0
    }

    'nexus' {
        # Force a fresh read for one mod, or every linked mod.
        $keys = if ($Mod) { @(Resolve-Key $Mod $reg) } else { @(Registry-Keys $reg | Where-Object { $reg.$_.nexusModId } | Sort-Object) }
        foreach ($k in $keys) { Write-Output ("nexus  {0}" -f $k); Sync-Nexus $k -Force }
        exit 0
    }

    'list' {
        $rows = if ($Mod) { $k = Resolve-Key $Mod $reg; $ledger | Where-Object { $_.mod -eq $k } } else { $ledger }
        $rows | Sort-Object mod, { $v = Parse-Version $_.version; if ($v) { $v } else { [version]'0.0.0' } } |
            Format-Table @{n='Mod';e={$_.mod}}, @{n='Ver';e={$_.version}}, @{n='Status';e={$_.status}}, @{n='Posted';e={ $p = Posted-Of $_; if ($p) { if ($p.at) { "$($p.channel) $("$($p.at)".Substring(0,10))" } else { "$($p.channel)" } } else { '' } }}, @{n='Sha';e={ if ($_.sha256) { $_.sha256.Substring(0,8) } else { '' } }}, @{n='Evidence';e={$_.evidence}} -AutoSize
        exit 0
    }

    'status' {
        $keys = Registry-Keys $reg | Sort-Object
        foreach ($k in $keys) { Sync-Nexus $k }
        Write-Output ''
        Write-Output ("{0,-36} {1,-9} {2,-9} {3,-9} {4,-18} {5,-20} {6}" -f 'Mod', 'posted', 'working', 'nexus', 'open', 'next', 'repo')
        foreach ($k in $keys) {
            $fl = Last-Posted $k $ledger; $lw = Last-Working $k $ledger; $open = Open-Entry $k $ledger
            $flTxt = if ($fl) { "$fl$(if (Floor-Is-Unknown $k $ledger $fl) { '?' })" } else { '-' }
            $openTxt = if ($open) { "$($open.version) $($open.status)" } else { '-' }
            $nx = if ($reg.$k.nexusVersion) { $reg.$k.nexusVersion } else { '-' }
            Write-Output ("{0,-36} {1,-9} {2,-9} {3,-9} {4,-18} {5,-20} {6}" -f $k, $flTxt, $(if ($lw) { $lw } else { '-' }), $nx, $openTxt, (Expected-Text $k $ledger), $reg.$k.repo)
        }
        Write-Output ''
        Write-Output "posted = the last number out (Nexus, 1. members, or a posted record; '?' = backfill 'posted: unknown'); next = the open number, else patch/minor/major from posted (bump -Kind decides)"
        $pend = @($ledger | Where-Object { $_ -and $_.PSObject.Properties['prunePending'] -and $_.prunePending } | ForEach-Object { "$($_.mod) $($_.version)" })
        if ($pend.Count -gt 0) { Write-Output ("clean-up pending (runs at the mod's next posted, bump or record): {0}" -f ($pend -join ', ')) }
        $orphans = @($ledger | Where-Object { $keys -notcontains $_.mod } | Select-Object -ExpandProperty mod -Unique)
        if ($orphans.Count -gt 0) { Write-Output ''; Write-Output ("UNREGISTERED ledger names (cannot be bumped or gated until registered): {0}" -f ($orphans -join ', ')) }
        exit 0
    }
}
