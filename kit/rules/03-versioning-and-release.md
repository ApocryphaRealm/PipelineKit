# Rules part 03 - Versioning and release

> *Kit edition: this document was reduced for publication. Tools it names that reach the internet (`nexus-upload.py`, `nexus-version-audit.py`, `nexus-media-backup.py`) are not in the kit - see `OPTIONAL-SCRIPTS.md`. Other tools it names may belong to the original pipeline only (README-FOR-AI, section 10). Where text reads `[... removed]`, direct evidence was taken out.*

<!-- RULES-PART: 03 | rules: 3,6,7,9,10,21,23,34,35,48,61 -->
*One of the seven parts of the project rules. The rules version is stamped in `CLAUDE.md`, which*
*also carries the index. Load this part when working in stages 6-7 (packaging), 10-12 (finalizing, Nexus distro, updates) and every commit.*

Repositories, version numbers, packaging, finalizing, Nexus.

**Every rule here states its complete current policy on its own.** A change is folded into the
rule it changes with a dated `> **Amended YYYY-MM-DD**` note at the top of that rule - never
appended elsewhere, never written as a new rule that corrects an old one. Rule numbers are
identifiers: they are never renumbered or reused, and an absorbed rule leaves a stub under its number.

Rules in this part: 3, 6, 7, 9, 10, 21, 23, 34, 35, 48, 61.

---

## 3. Every mod gets a public GitHub repository

> **Amended 2026-10-27 (the owner, after RaceMenu Atelier's release was blocked when an agent could not change the
> repo's visibility): making a mod's repo public is part of an owner-approved release, not a separate permission.**
> Once the owner has approved a mod's release, the agent running it may make that mod's the author repo public
> (`gh repo edit the author/<repo> --visibility public --accept-visibility-change-consequences`) without asking
> again - after first checking the full history: every author and committer is a noreply identity, no owner name or
> email, no secrets, no local user paths, no committed binaries; any hit stops the release and is reported. Read the
> visibility live  before the finalize gate's single run, never after. The
> standing permission rule for that one command (the author repos only) is in the user Claude settings
> (`permissions.allow`, added on the owner's instruction 2026-10-27); if a refusal still comes back, it is reported
> and the owner runs the command himself. A mod kept private or local-only under the 2026-09-28 amendment below is never made public by
> this.

> **Amended 2026-10-13 (straight flow, ruled with the owner's decisions of 2026-10-12): the release tag is made only
> after the finalize gate passes.** `finalize-mod` pushes the commits first, runs the gate, and only then creates the
> annotated tag vX.Y.Z (the last git step before the move) and pushes it. A refused gate therefore leaves no tag behind,
> and a fix committed after a refusal needs no tag moved by hand. A tag is never forced, moved or deleted by a tool: when
> a tag of that name already exists, finalize leaves it alone if it points at HEAD and refuses otherwise, naming both
> commits, with the fix "move or delete tag vX.Y.Z, or commit on top of it" - moving a tag is the owner's step.

> **Amended 2026-09-28 (the owner):** *"Most of the mods we make with visual assets from other users that don't have
> explicit permission will have to stay a local repo, not an official one. And we'll end up posting these files to
> Mega website for downloading with Wabajack by users later, as they won't be official files on Nexus."* So a mod that
> ships another author's visual assets (meshes, textures, UI art) WITHOUT that author's explicit permission gets a
> **local git repository only** - no GitHub repo, not public, not a fork, not uploaded to Nexus; it is distributed
> later through Mega for Wabbajack lists. A mod whose assets are ours, or used with explicit permission, keeps the
> public-repo rule below. The owner may also name a mod to keep as a PRIVATE GitHub repo instead (Wait Your Turn Redux,
> 2026-09-28: "a private repo, not an official fork"), or as local-only for now (Localized Damage, 2026-09-28).
> Before creating a public repo for any mod, check its assets' provenance; when permission is not recorded, ask.

Creating the repo and pushing is **part of finishing a mod**, not a separate favour to ask
about each time.

- **Public**, not private.
- **One repository per mod, forked from upstream** (`gh repo fork`). These are forks of
  other people's mods with their own licences and histories — Dragon's Eye Minimap is MIT,
  Wait Your Turn Redux is AGPL-3.0. Forking preserves attribution and stops licences being
  blurred together. Never collect several mods into one monorepo.
- **Commit identity is the GitHub noreply address**, so his real email never enters public
  history: `<id>+<name>@users.noreply.github.com`, name `the author`.
  The numeric ID is permanent; the username part changes if he renames.

Never commit build output. Recover real upstream history before pushing a folder that was
created by copying files rather than cloning — a flat single commit hides what changed.

---

## 6. Builds carry their own version number

> **Amended 2026-10-21 (the owner): semantic versioning.** *"Update the versioning logic to use this"* - said of a Nexus
> commenter's summary of SemVer (MAJOR.MINOR.PATCH: a bug fix with no compatibility change bumps the patch, new
> backward-compatible functionality bumps the minor, a breaking change to the public API bumps the major). So the number
> now says what KIND of change a release is, and `version-gate.ps1 -Action bump` takes it as a REQUIRED `-Kind
> patch|minor|major` - a bump without one is refused, never defaulted. There is no roll-over any more: 1.0.9 plus a fix
> is 1.0.10, and 1.9.x plus a feature is 1.10.0. The roll-over at .9 (and the 2026-10-01 amendment below that applied it
> to the minor) is retired: it made a bug fix after x.y.9 read as new functionality, which SemVer says it is not. The
> commenter also corrected the reasoning around antivirus: *"A new binary has a new hash no matter what version number
> you give it"*, and a SmartScreen low-reputation warning is not Defender's machine-learning detection - so no version
> choice (patch versus minor, or reusing a number) makes a release more or less likely to be flagged; antivirus
> false-positive submissions stand on the file hash alone. Released numbers are not renumbered.

> **Amended 2026-10-11 (the owner): a number is spent by POSTING it.** *"change the versioning logic from has to be
> proven working to get the number to has to be posted to Nexus. To get a new number."* - said when AMF for Witcher 3
> 1.0.5 had been recorded working but not posted and the next group of features was being called 1.0.6: *"We haven't
> even posted 1.0.5 yet. How can there be a 1.0.6?"* So the third component goes up once per POSTED release, not once
> per change: the next number is LAST POSTED + 1, and every change made before that number is posted goes in under it.
> Posted means the build went out as the mod's file - the Nexus upload, the Pipeline Kit's copy into
> `11. Nexus distro\1. members`, a Mega upload, or finalizing for a mod that is kept local.

> **Amended 2026-10-01 (the owner), RETIRED 2026-10-21 by semantic versioning: at x.9.9 the MAJOR rolls.** `version-gate.ps1` issued 1.10.0 after Apocrypha Menu
> Framework 1.9.9, following this rule's old line "the major version is never rolled this way", and the owner answered
> *"Wrong version number."* So the same cap applies one level up: 1.9.9 -> 2.0.0, never 1.10.0, exactly as 1.0.9 ->
> 1.1.0. The gate's `Next-Number` does this; AMF's 1.10.0 was withdrawn with `renumber` before anything shipped.

Each mod build gets a version of its own rather than inheriting the upstream mod's.
Dragon's Eye Minimap is **1.5.0** despite being based on upstream 1.1.0, because 1.5 is
where that work had reached when the owner asked for versioning.

**1.5 is that mod's number, not a shared starting point.** Other mods start from their own
number, and only the increment behaviour below is common to all of them.

**Standing default: generated content starts at version 1 (1.0.0)** unless the owner says
otherwise — no need to ask before assigning a first version. This covers more than full mod
builds: any versionable deliverable, including one-off asset-only packages (a theme, an
asset-recolor preview) that had no version at all because none had been assigned yet.

**Every POSTED release is numbered MAJOR.MINOR.PATCH by the kind of change it carries**
(semantic versioning). The kind is decided by whoever runs `bump`, from what the release does to the
people and mods that use it - never from how big the change feels or how long it took:

| Kind | When | Example |
|---|---|---|
| **patch** | Bug fixes only; nothing a user or another mod relies on changes. Crash and logic fixes, a wrong default corrected to what was documented, a missing file put back in the package, performance work with no visible change, translation fixes and added or corrected translations, UI wording and README text | 1.2.4 → 1.2.5 |
| **minor** | New functionality that stays backward compatible: a feature, a new setting or INI key whose default keeps the old behaviour, a new optional file, a new API call other mods can use (existing calls unchanged), support for another game runtime. Resets the patch to 0 | 1.2.4 → 1.3.0 |
| **major** | A breaking change to the mod's public surface: an exported API call removed, renamed or its signature/behaviour changed for the mods that call it; a save or co-save format older saves cannot load (or that cannot be rolled back); INI keys renamed or removed, or files moved, so users' settings stop applying; a runtime or game version dropped. Resets minor and patch to 0 | 1.2.4 → 2.0.0 |

A release holding several kinds takes the HIGHEST kind it holds. When it is unclear whether something
breaks a user's setup or another mod, treat it as breaking (major). A first release is always 1.0.0,
whatever the kind. No component caps or rolls over: 1.0.9 + patch = 1.0.10, 1.9.0 + minor = 1.10.0.
(1.5.0 and 1.5 are the same version; the build systems want three components.)

Run `version-gate.ps1 -Action bump -Mod <key> -Kind patch|minor|major` as part of making a change,
rather than waiting to be asked. While the last build is not posted it hands back that same number
(the open number) and the change goes in under it - as long as the change is of the same or a lower
kind than the open number. **When a change of a HIGHER kind arrives while a number is open** (a fix build
gains a feature, or a feature build gains a breaking change), `bump` withdraws the open number and
re-issues from the LAST POSTED number with the higher kind: posted 1.2.4, open 1.2.5 (a fix), a feature
is added -> 1.3.0, and 1.2.5 is recorded withdrawn. The open number's kind is read from the numbers
themselves (which component moved above the last posted one), and the CHANGELOG entries written under
the withdrawn number move to the new one (packaging refuses a version with no entry). A number already
issued is never lowered: a patch change on an open 1.3.0 goes in under 1.3.0.

**Numbers shipped before 2026-10-21 stay as they are.** Released mods are never renumbered to fit the
new meaning - 1.1.0 after 1.0.9 under the old roll-over, or Compass Navigation Overhaul's earlier
retroactive 1.0.10 -> 1.1.0, are history, and the next release counts on from the last posted number.
An open (unposted) number issued under the old roll-over also stays: a patch change goes in under it.

**Enforced where the number is issued, not at push time.** From 2026-08-26 a global `pre-push` hook
(`.MD\scripts\git-hooks\pre-push`, wired in through `git config --global core.hooksPath`) rejected
any `vX.Y.Z` tag with a patch of 10 or more, because the roll-over made that shape impossible.
Under semantic versioning it is a correct number, so that check was removed on 2026-10-21 (the hook
still runs the secret check on every push). The version gate is the enforcement: `bump` refuses
to run without a kind, issues every number, and `gate` refuses a number it did not issue.

**Renumbering a version - retroactively via this hook, or any other time a finalized mod's
version changes - also means regenerating that mod's 1920x1080 Nexus banner** (in
`11. Nexus distro\<Mod Name>\`). Its
version pill (e.g. "v1.1.0") is rendered as actual pixels into the PNG by headless Edge, not
read live from anywhere - renaming files or fixing `nexus-page.txt`'s text does nothing to
what the image itself shows. Edit the version pill text in `banner-1920x1080.html`'s CONTENT
block, re-rasterize, and visually confirm the new PNG actually shows the corrected number
before treating a renumbering as complete. The 1300x372 banner is unaffected - it's fully
empty (no text at all), so no version pill ever appears there to begin with.

Set it in the build definition, not only in documentation, so the binary reports it too —
the `VERSION` on CMake's `project()` call, or the `version` local in `xmake.lua`. Verify
the built DLL actually reports it. **Put the version at the top of the package README**,
under the title, and say which number is upstream's and which is this build's. Tag the
repository (`v1.5.0`) and push the tag.

**Retired exception: tracking another mod's version number.** This rule used to carry an
exception saying that a mod queried at runtime through
`skse->GetPluginInfo("PluginName")->version` had to track upstream's own numbering instead of
starting fresh at 1.0.0, because Dragon's Eye Minimap hard-failed the game when Local Map
Upgrade reported below `[value removed]`. **That exception no longer applies.** Dragon's Eye
Minimap now checks for the pixel-shader function pointers Local Map Upgrade actually sends,
rather than the number it reports - a capability check instead of a version check, which is
version-agnostic and survives renumbering and forks. Every mod in this project now starts at
1.0.0 and follows the ordinary scheme.

The underlying caution still stands, though: **before assigning a version to a mod that
another plugin queries at load time, check whether anything actually gates on the number**
(`grep -rn "GetPluginInfo(" "6. current wip mods"`). If something does, prefer fixing that
consumer to check a capability rather than bending this mod's numbering around it. A version
number is a poor proxy for "does this build provide the API I need", and using it as one is
what forced the original exception.

---

## 7. Version the package folder, never the DLL filename

> **Amended 2026-09-09 (the owner):** "the author" appears in NO banner title and NO mod
> folder name except the Apocrypha Menu Framework's - *"remove the 'apocrypharealm' statement from
> any banner titles and mod folder names aside from amf."* So banners are titled "Item Explorer",
> "Lock Interaction Overhaul", "Submission & Troubleshooting Guide" (plain names), and package /
> distro / MO2 folder and zip names carry the plain name too; AMF's banner stays "the author
> Menu Framework". This covers the FOMOD `moduleName`/`info.xml` Name, which is what MO2 uses as
> the installed folder name. It does NOT touch repo/binary identities (`ApocryphaItemExplorer.dll`,
> INI/log/mutex names), the GitHub account name, or historical changelog lines that recorded an
> older name.

> **Amended 2026-09-07 (the owner):** the NEXUS PAGE TITLES keep "SKSE Menu Framework" on purpose - the mods stay SMF-compatible and SMF is the better-known name.
> *"our mods are still compatible with SMF and SMF is more well known so I keep them in the title."* The plain-name
> rule below governs what this project names itself - package folders, zips, MO2 folders, the in-game
> display name - and never a live Nexus title. A page title carrying the framework name is a
> discoverability choice he makes at posting time; do not report it as an inconsistency or propose a rename.

**Converted mods carry the mod's own name only - no "- SMF Settings" suffix (the author,
2026-08-30: "it'll still be based on our AMF framework so instead of it saying SMF settings just
basically say the name of the mod only").** Display name, Nexus page title, package and zip names,
MO2 mod folder names: the plain mod name; the framework dependency (Apocrypha Menu Framework,
which answers the SKSE-Menu-Framework-compatible API) is stated in Requirements, never in the
name. Existing released pages keep their current names until the author renames them himself.


The DLL's filename stays constant across every version - always `ModName.dll`. SKSE loads
every `.dll` it finds in `SKSE/Plugins` regardless of name, and a mod manager will not
remove an old versioned DLL when a new one is installed - it just adds it alongside. Two
DLLs from the same mod loaded at once is a real crash risk. The version lives in the DLL's
own metadata (the Windows file-version resource, `SKSEPluginInfo.Version`) instead.

The packaged folder gets the version in its name - `Mod Name - Description 1.6.3`, not
`Mod Name - Description` - and since 2026-10-01 it sits inside the mod's game folder, named exactly
like the mod's `11. Nexus distro` folder: `7. current test builds\<Game> - <Mod>\Mod Name 1.6.3`
(the same in `10. finalized mods`), so a Skyrim and an Oblivion Remastered mod of one name and
version can both exist (the owner: *"so that the mod files can maintain the same name but be placed
and referenced to different folders"*). The folder comes from `Resolve-PackageRoot` in
`scripts\distro-names.ps1`, never from a hand-joined path. The owner wants to drag a new
version straight into MO2 as its own mod without overwriting the previous install, so each
release is a distinct folder. Applies to every mod's package folder, on every version, going
forward - not only the one this was raised for. Does not apply to the source repo under
`6. current wip mods`, which is versioned by its own git tags instead.

**The current version and one previous per mod** (the owner, 2026-10-12: *"we only keep 1 previous version at a time not
5 from now on"*). Packaging runs `prune-test-builds`, which keeps the new build and the one before it in
`7. current test builds`; `finalize-mod` does the same in `10. finalized mods`. Older copies go to the Recycle Bin
without asking; say what was removed when it happens. (Five until 2026-09-28, then one, then this.)

---

## 9. Always commit and push - don't wait to be asked

**This supersedes every earlier, narrower version of this rule** (a "finalize a mod" trigger,
before that "never without being asked"). The owner gave blanket standing authorization: whenever
a real, complete change is made to a mod's source repo in this project, commit it, tag it if
it's a version bump (`vX.Y.Z`), and push - to the mod's public GitHub repo
- without asking each time.

This is specific to this project's own mod repos under `6. current wip mods`. It does not
extend to unrelated repos, to force-pushing or rewriting already-pushed history (retroactively
renumbering an already-shipped version is something to do only when he raises it), or to
anything outside of `git commit`/`git push` themselves - deleting, resetting, or otherwise
destructive git operations still follow the general caution the rest of this project (and
ordinary judgement) calls for.

---

## 10. `<ROOT>\11. Nexus distro` - Nexus-ready material for every finalized mod

> **Amended 2026-11-15 (the owner): every NEW mod's release is linked in the chat server "new releases" channel.** The
> owner, 18:25: *"Make sure that whenever we release a new mod that you add its link into the new releases channel on
> my chat server."* When a mod's first Nexus page goes live (its first file posted - `version-gate -Action link` / the first
> `nexus-upload` of a new page), the same posting pass posts the mod's Nexus page link in the the author Modding Hub's
> new releases channel (Claude in Chrome on the chat server's site, the owner's signed-in account), with a one-line description of
> what the mod does, written on its own terms (no owner name). It needs no separate go-ahead: it rides on the go-ahead
> for the release. Record it in the distro folder as `new-release-posted.txt` (date, channel, message link).
> Updates to an existing mod are not new releases - they follow the update announcement format
> (`_DISCORD-TEMPLATE.txt`).

> **Amended 2026-10-24 (the owner): Nexus replies post without his consent, after a reread and the Fable review.**
> A reply to a comment passes a gate - a fresh reread of the comment, then the Fable session's review - and is then
> posted without asking him. A reply drafted from a SUMMARY of a comment had asked the commenter something they had already said . The owner, 21:02: *"add a gate so
> that the original comment has to be reread before you post a reply, and that replies can be posted without my consent
> automatically. After passing through the Fable session."* Role `nexus-reply` (`resolve.py run nexus-reply ...`,
> records in role `nexus-replies`) is that gate, and every reply on our pages goes through all five steps:
> (1) `snapshot --url <page> --comment <id>` fetches the thread fresh (plain HTTP GET of the public posts tab, the
> comment widget's pages when it is not on page 1; or `--capture <file>` with the thread's text read in Claude in
> Chrome) and prints it - the draft is written AFTER this, against this text; (2) `review-request --id <id> --draft
> <file>` refuses a snapshot older than 30 minutes, a draft file last written before the thread was read, and a draft
> carrying the owner's identity, then writes `<id>.review-request.md` (verbatim thread, draft, checklist, the exact
> verdict commands) - the drafting session sends it to the Fable session by SendMessage; (3) the Fable session runs
> `review-verdict --approve|--reject --notes ...` - accepted only from the session registered as the Fable session in
> `agent-bus\sessions.json`, never from the drafter; (4) `gate --id <id> --draft <file>` passes only on a Fable
> approval of exactly this draft's hash, given on the current snapshot, with the snapshot younger than 30 minutes -
> otherwise it reads the thread again, and a changed thread (a new reply, an edit) voids the review; (5) the reply is
> posted in Claude in Chrome with the text the gate printed, the public Posts tab is read back, and `posted --id <id>
> --link <permalink> --readback <file>` logs time, link and hashes to `post-log.jsonl`. A reply that passed the gate is
> posted without showing the owner first. Everything else public - an upload, a description save, a sticky, a new
> page or announcement - still waits for his go-ahead. No `gate-rules.json` row: the gate's artifact is the record, not
> a package. Tests: `scripts\tests\test_nexus_reply.py`.

> **Amended 2026-10-14 (the owner): hiding the description pictures from the gallery is verified from the public view, every time.**
> Loot on Hover's new page (14322) went up with its description cards VISIBLE in the gallery, although the media step
> reported them hidden. The owner: *"You need to amend the upload doctrine or rules for updating the description and
> pictures, because the agent forgot to hide the description pictures as they are visible in the gallery."* So (a) below
> now has a check: after any media upload or description save, the page's Images tab is read back from the public view
> (logged out or a private window, or the public image list), and the number of visible gallery images must equal the
> number of banners. Any other visible picture is hidden at once and the count read again. The upload step's own success
> message is never taken as proof. The report of a posting names the visible count before and after.

> **Amended 2026-10-13 (the owner, 2026-10-12: "the distro is not synced until finalize"):** the distro material of a
> version is synced only by `finalize-mod`, as one step of finalizing. `sync-nexus-distro.ps1` refuses (exit 3, naming
> this decision) unless finalize is running it for that mod and version (the `MODS_FINALIZE_RUN` mark finalize sets for
> its own process) or that version is already in `10. finalized mods` (re-editing a posted mod's page stays allowed).
> "Proved working" does not sync it, and `pre-finalize-check.ps1 -SyncNexusDistro` no longer runs the sync.

> **Amended 2026-10-11 (the owner): every update also rewrites the mod's "Recent changes" sticky on its Posts tab.**
> After AMF Skyrim's sticky was rewritten that day he said: *"let's extend the update nexus process to also update the
> sticky post to list everything in the same way that AMF's sticky post does."* So each distro folder carries
> **`sticky.txt`** beside `changelog.txt`, in the format of `11. Nexus distro\_STICKY-TEMPLATE.txt` (worked example:
> `Skyrim - Apocrypha Menu Framework\sticky.txt`): a bold first line "Recent changes - current version X.Y.Z", with
> " (X.Y.Z+1 is coming soon)" only while a next build is staged; bold theme headings on their own lines; one "- " item
> per line, never bold; a blank line between sections; everything the mod has gained so far grouped by theme, written
> from the player's view, with no personal name except credited contributors; and a closing line linking the
> the author Modding HUB with the server invite. Nexus's comment editor renders a plain line break, so the layout
> needs no tags beyond the bold and the link - a sticky with every line wrapped in `[b]` runs together into one block.
> It is written with the release's changelog entry, before finalizing: package-gate row
> `distro-sticky-starts-with-this-version` fails the finalize while `sticky.txt` is missing or its first line does not
> name the version being finalized (at packaging the row is reported, as every `distro-` row is). A mod without one gets
> it at its next release. At posting time, in the same pass and under the same go-ahead as the upload, its text is saved
> through Claude in Chrome - the live text backed up into `assets\` first, then Edit post on the "Recent changes"
> sticky, or a new comment set STICKY + LOCKED where the page has none - and the public Posts tab is read back.

> **Amended 2026-10-08 (the owner): every Nexus page follows `11. Nexus distro\_NEXUS-DESCRIPTION-LAYOUT.md`.** After
> AMF 2.1.5's page was rebuilt with him over one night, he asked for *"all of the information acquired in this session"*
> to be saved *"for the template and for making Nexus distribution pages for every future page"*. The layout file is
> the how-to and this note is the policy:
> (a) **The gallery holds banners only** - *"If it's not in a banner, it doesn't go there."* Every other picture the
> description shows is uploaded through the media step and hidden from the gallery (its URL keeps working), and the
> public Images tab is read back afterwards: the visible count must equal the banner count (2026-10-14).
> (b) **No description section repeats Nexus's own top drop-downs** - Requirements, Permissions and credits, Changelogs.
> The requirements list lives in the page's Requirements step, and only the version details it cannot show go into
> Installation. Credit stays in the description, because the custom permission text says "Credit in mod Description".
> (c) **The description is laid out like the demo he approved**, as far as Nexus can render it: drawn header cards, a
> title card per feature with the feature's `[spoiler]` under it, an at-a-glance strip, outlined full-size close-ups
> (not the titled banners) inside the drop-downs, **real drag sliders** (`[compare before=URL]URL[/compare]`) for
> before/after pairs instead of GIFs, and no strip of extra pictures at the end of a drop-down. Paragraphs stay real
> text, and **every text block sits in a `[quote]` panel** (the grey box with the orange bar). The owner, the same night:
> *"I like that"* and *"make it part of the standard template"*. `wrap-quotes.py` applies it as the last step.
> (d) **He sees a preview first**: the page's real BBCode rendered the way Nexus draws it, before anything is saved live.
> The tools and AMF's reference files are in `.MD\scripts\nexus-description\`. `_nexus-page-template.txt` is at
> 1.1.3: its Requirements section was removed, Installation gained the version-details line (1.1.2), and a layout note
> at the top names the layout file and the quote panels (1.1.3).

> **Amended 2026-10-01 (the owner): packages, test builds and finalized releases sit in a folder named like the mod's
> distro folder.** After HUD Position Manager for Oblivion Remastered reached 1.0.1 - the same number as the Skyrim
> HUD Position Manager, whose package is also named `HUD Position Manager 1.0.1` - he said: *"We should make the script
> aware of what the distro folder is called and place them based on that so that the mod files can maintain the same
> name but be placed and referenced to different folders in the distro."* He rejected renaming either game's package
> and moving the Skyrim release aside. So the layout is `7. current test builds\<Game> - <Mod>\<Mod> <version>\` and
> `10. finalized mods\<Game> - <Mod>\<Mod> <version>\` with its `.zip` beside it, where `<Game> - <Mod>` is exactly the
> mod's `11. Nexus distro` folder name (`Oblivion Remastered - HUD Position Manager`, `Skyrim - HUD Position Manager`,
> `MO2 - Custom Filters`). Package, zip and MO2 names stay the plain `<Mod> <version>`; the game folder is what keeps
> the two games apart, so `Apocrypha Menu Framework 1.0.5` (Oblivion Remastered) and `Apocrypha Menu Framework 1.9.9
> FOMOD` (Skyrim) no longer share a folder. The game is read from the version registry (`game` / `pluginDir`) or from
> what the package contains (`Get-PackageGame`), never from the name. No script joins `<stage>\<Mod> <version>`
> itself: `scripts\distro-names.ps1` holds the one resolver - `Resolve-PackageRoot` (where a mod's packages go) and
> `Find-Packages` (what a stage holds) - and the Python scripts ask it through `scripts\package_paths.py`.
> `scripts\migrate-package-folders.ps1` moved the 321 existing packages and zips the same day (moves only, after a dry
> run); Pipeline Kit and Taskbar Folders, which are for no game, stay in the stage roots. While the repos' own build
> tools (`tools\build-fomod.py`, `tools\build-package.py`, `build.ps1`) still write flat, `Find-Packages` also reads a
> package left in a stage root, and the migration is re-run to move it.

> **Amended 2026-09-30 (the owner): Claude posts the Nexus pages, and every page carries a standing checklist.** With
> Claude in Chrome connected, the owner handed the posting over - *"because you're going to be handling the Nexus pages
> from now on, there's no need to have the short description in the same file as the regular description"* - and set
> what every page must have *"on every page from now on"*:
> 1. **Permissions:** "Write your own (custom)" with his text - *Compliant with the GNU GPL v3 license (re-upload,
>    modification, conversion, asset use, earning donation points and monetization are allowed* / *Credit in mod
>    Description*. A page that already holds a custom text (Ultimate Combat Redux's credits to Kramer7046) is not
>    overwritten - read the box before typing; a mod that is not GPL is asked about, not given the GPL line.
> 2. **Requirements:** the page's files list their real requirements (from the Requirements table).
> 3. **Media:** the current banners are uploaded and outdated ones deleted (the newest 1920x1080 as the thumbnail).
> 4. **Tags:** BOTH "AI-Generated Content" and "AI Media" on every page, never "AI Assisted" (amended 2026-10-25: Nexus staff gave the account an informal warning for tagging only AI-Generated Content; checked by gate row distro-nexus-page-carries-both-ai-tags).
> 5. **General:** the mod version matches the release posted (a bare "1" is corrected to the real number).
> 6. **The newest build is posted:** the page's primary main file is the newest finalized build in its distro folder.
>    Added the same evening, after the owner found eight finalized updates still unposted following the page sweep -
>    *"I thought you already went and updated all these pages earlier. Why wasn't this done before?"* The sweep had
>    matched each page's General version to the file already on Nexus and never looked at the distro folder.
>    `resolve.py run nexus-version-audit` now compares every page with its folder (exit 1 when a page is behind, its
>    General version disagrees with its file, or a file is versioned "1"), and it is run after every posting pass.
> 7. **File names carry no version and no "FOMOD"** (the owner: *"which is what I want to be the new standard"*): a
>    file's display name is the mod's name only, the version goes in the File version field, and a FOMOD installer says
>    *FOMOD* in the file's Description (the File options box) instead - *"we can just write fomod in the file options
>    area of each mod that is a fomod"*. A zip whose name carries no version is read from inside: the DLL's version
>    resource, else the CHANGELOG/README in it.
> **Posting a file goes through the Nexus API, not the browser.** Claude in Chrome's file tool stops at 10 MB per file,
> and the Nexus page's content-security policy lets the upload form fetch from nexusmods.com only, so a big zip cannot
> reach the form (a localhost server was tried and refused). `resolve.py run nexus-upload "<distro folder>"` posts the
> folder's newest build as a new version of the page's primary main file through the v3 API - upload with md5,
> finalise, then the version with the name rule above, `update_mod_version`, primary for mod managers, the old file's
> description carried over (FOMOD added when the archive holds `fomod\ModuleConfig.xml`), and the build's section of
> `changelog.txt` as the changelog. It refuses a page not uploaded by the author, a version the page already has, and
> any registry entry carrying `nexusRemoved` (Nordic Dragonbone Armor Replacer, removed by Nexus moderation for
> permissions - never re-uploaded). The v1 API caches a page's version for minutes, so the proof of a post is the
> primary main file and the md5 lookup, not the cached page version. A Nexus changelog entry can be edited but never
> deleted or re-keyed (its version box is locked, an empty entry cannot be saved, and the API only appends), so a wrong
> one is corrected in place. Before any media delete or replace, `resolve.py run nexus-media-backup` saves the page's
> live images into the folder's `assets\`.
> The distro folder therefore holds the short description in its OWN file, `short-description.txt`, beside
> `nexus-page.txt` (which now starts at the Description heading); all 50 pages were split the same day, and
> `package-gate.ps1`'s `page-summary-fits-nexus-field` reads the new file (the old in-page block only as a fallback).
> Posting mechanics that held (Nexus's new upload form): a file goes up through "Add file" then "Update existing file"
> on the current main file, File version = the release, "Update mod version to match" ticked, the changelog typed with
> real keystrokes; the description editor is SCEditor, edited through `sceditor.instance(textarea).val()`. Anything
> public - an upload, a description save - still follows the owner's go-ahead for that batch; a reply to a comment
> goes through the `nexus-reply` gate (the 2026-10-24 amendment at the top of this rule) instead of being shown to him.

> **Amended 2026-09-29 (the owner): a distro folder is named "<Game> - <Mod>", the game first.** *"lets prefix the
> distro folders by the game they are for from now on"* and *"lets rename them to not have 'for oblivion' or 'oblivion
> remastered'"* - said after a banner pass had missed three Oblivion Remastered mods whose folder names said nothing
> about the game. The games are `Skyrim`, `Oblivion Remastered` and `MO2` (Mod Organizer 2 plugins and themes), and the
> mod part carries none of the game's own words: `Oblivion Remastered - Simple Loadout System`, `Skyrim - Dragon's Eye
> Minimap`, `MO2 - Custom Filters`, `MO2 - Vel'dun Theme`. For Skyrim and MO2 the finalized folders, zips and the
> version registry keep the mod's full name (`MO2 Custom Filters 1.0.5.zip`), and `_distro-folders.json` in the distro
> root maps each folder to that name. **An Oblivion Remastered mod's name is plain everywhere** (the owner, later that
> day: *"did you rename the Oblivion mods that had For Oblivion or For Oblivion Remastered to not have that suffix in
> the finished zip or the DLL or the mod name or anything like that?"* - and *"don't forget the banners"*): no "for
> Oblivion" / "for Oblivion Remastered" in the page text, README, NOTICE, changelog, banner or registry display name.
> **The prefix is the distro folder's alone** (the owner, once more that day: *"the prefix is the distro folder for
> organization purposes"* - a package named `Oblivion Remastered - Apocrypha Menu Framework 1.0.2.zip` was wrong):
> packages, zips, MO2 folders and registry display names are the plain `<Mod> <version>`, so `10. finalized mods`
> holds `Apocrypha Menu Framework 1.0.2` (Oblivion) beside `Apocrypha Menu Framework 1.9.9 FOMOD` (Skyrim). The
> tooling tells them apart by what the package CONTAINS (`Get-PackageGame` in `scripts\distro-names.ps1`: an
> `OblivionRemastered\` tree is Oblivion Remastered, `SKSE\` / `Data\` / `Interface\` is Skyrim), never by the name.
> Where the game must be said in a heading it is a parenthesis, `Tween Menu (Oblivion Remastered)`, never a suffix.
> The GitHub repositories keep their `...OR` names (a repository name must differ from the Skyrim mod's). No script
> joins `11. Nexus distro\<name>` itself: every one dot-sources `scripts\distro-names.ps1` and asks
> `Resolve-DistroFolder` (mod name -> folder, with the game) or `Resolve-DistroModName` (folder -> mod name). The
> Nexus pages' titles are renamed by hand on the site.

> **Amended 2026-09-29, reduced for the kit: a page may close with a plain donation link, if the person wants one and the site's rules allow it** - never a link to a paid post, file, kit or service.

> **Amended 2026-09-14 (the owner): every link on a Nexus page is a clickable BBCode link.** *"i noticed that the links in
> the nexus description are actually clickable links and not just text on nexus which is my new preference"*. A URL in a
> `nexus-page.txt` is written `[url=https://...]readable label[/url]` - Source repository and release tag, requirement rows
> (the link goes in the table's URL cell), credits, a community hub - never a bare URL and never a markdown `[text](url)`.
> All 22 distro pages were converted the same day, each with its own document-version bump.

> **Amended 2026-09-06 (the owner): `11. Nexus distro` is the ONE place to post from, and it holds ONLY
> the newest package.** *"make it the standard practice that only the most up-to-date file for each
> mod should go to the Nexus distro and cuz finalize has too many things in there I don't like to
> scroll that much so make it so I dont have to go to the finalize folder when posting to nexus."*
>
> So: each mod's distro folder carries **exactly one package zip per download - the newest finalized
> version** - beside its `nexus-page.txt`, `changelog.txt`, banners and any ready-to-post text, which
> together are everything a Nexus post needs. When a version finalizes, its zip **replaces** the
> previous one there; older zips never accumulate (they stay in `10. finalized mods`, which remains
> the archive of every version and which he should never have to open to post). When both a plain
> zip and a FOMOD zip exist for the newest version, the FOMOD is the one that ships in the distro.
> Mechanically: `sync-nexus-distro.ps1`'s zip step swaps in the newest zip and removes every other
> zip of that mod from the folder, and `nexus-distro-sweep.ps1` checks every distro folder against
> `10. finalized mods` (`-Apply` fixes) - run it before telling him something is ready to post.

For each mod in `10. finalized mods`, write a subfolder here (`Mod Name - Description\`) with a
single `nexus-page.txt` matching the real Nexus submission structure the owner provided at
`11. Nexus distro\_nexus-page-template.txt` - Short Description, Description, Main features,
Installation instructions, Debugging, Requirements (as a table), Compatibility notes, Credit, Source, in that
order (Installation BELOW Main features - the owner, 2026-09-07: *"going forward, i want the installation section
below the main features category"*; the template originally had it above), as one
flowing document (not separate files per field - an earlier version of this rule guessed at
separate description/requirements/credits files, which was wrong about how Nexus's page is
actually organized). The GitHub link lives at the bottom of that same page under a `Source`
heading - there is no separate `repository.txt`. There used to be, and it was removed as
redundant once the link moved into the page itself; do not reintroduce it.

**Page layout, per the owner:** the **repository / source links go at the very bottom of the
description**, under their own `Source` heading and after the credits and licence, not opening
the Credit section as they used to. And the **change log stays in its own `changelog.txt`**,
never folded into `nexus-page.txt` - Nexus has a separate Change log tab for it, and mixing the
two makes the description longer without helping anyone reading either. One changelog per
download, so a mod with an optional file gets two, each on its own version line.

**Nexus documents carry their own version, separate from the mod's software version.** The
mod's software version is about the DLL/package; `nexus-page.txt`'s wording,
structure, and the template it follows can all get revised independently of that (a typo
fix, a reworded feature bullet, a template-format change - none of that is a new mod build).
Same scheme as everywhere else in this project: starts at 1.0.0 (the standing default for
generated content), patch-bumps on each real revision with no roll-over (1.0.9 -> 1.0.10, the
same semantic-versioning arithmetic as the mods since 2026-10-21; a template-format change is a minor). Track it in that package's `notes.txt`, not inside `nexus-page.txt` itself - the
page content is meant to be pasted into Nexus as-is, not cluttered with an internal version
marker. `_nexus-page-template.txt` (the owner's own reference template, shared across every mod)
gets the same treatment: note its version in this rule's text when it's revised, rather than
editing a version marker into a file that's his own dropped-in content. Currently: template
at 1.1.1 (2026-10-02 - after Nexus's Donation Options & Guidelines and Anti-Solicitation Policy were read: a page may carry a donation link, never a link to paid files, updates or modding services). Before that, 1.0.8 (2026-09-08 - bullet lead-ins are BBCode `[b]...[/b]`, never markdown `**`, per the owner: *"i want
the page to be more readable by having the bullet point items be in bold text on all descriptions"*. That was not
a style preference but a RENDERING BUG: Nexus renders BBCode - which the section headers already used - and prints
markdown asterisks as literal text, so every bullet on every live page had been showing `**Themes.** Skyrim, the
default...` to visitors instead of bold. Thirteen live pages converted the same day, 205 bold runs, no wording
changed, each with its own document-version bump. **Never mix markdown into a Nexus page - if it is not BBCode,
it is literal text there.**). Before that, 1.0.7 (2026-09-07 - Installation instructions moved below Main features, per the owner; every live
`nexus-page.txt` that had it above was reordered the same day with its own document-version bump). Before that,
1.0.6 (2026-09-07 - a one-line bold "Generative AI disclosure" closes the Description body, stating that
the code, translations, page text and banners were produced with generative AI directed and tested in game by the
author and that the page is tagged accordingly; added after Nexus's File Submission Guidelines made undisclosed
generative-AI usage a moderation matter and moderators had tagged every published page, the same line then went onto
every live `nexus-page.txt` with its own document-version bump). Before that, 1.0.5 (2026-09-05 - every section header inside the Description body is now BBCode
`[size=5][b]Header[/b][/size]`, several sizes larger and bold, per the owner; the same markup went onto every
live `nexus-page.txt` with its own document-version bump). Before that, 1.0.4 (2026-09-05 - rewrote the Compatibility notes to drop the "works on whatever Skyrim
version Address Library has a database for" claim after the 28 Aug 2026 update, 1.7.99 / 1.7.104,
shipped a new Address Library format the base build cannot read; the notes now name the supported
runtimes explicitly - SE 1.5.97, AE 1.6.1170 - and state 1.7.x does not load; every SE/AE mention
carries its exact version number). Each mod's live `nexus-page.txt` document version is tracked in
that mod's own `notes.txt` counter, not here.

**A copyleft licence (GPL/LGPL) has real conditions - permissive (MIT) does not, but do not
assume either without checking which kind a mod actually is.** Confirmed on Auto Draw: MIT
just asks that the notice be preserved, which the three existing forks already do correctly
(their `LICENSE` files are alexsylex's real MIT text, verbatim). Copyleft is stricter and
these are non-negotiable if a mod is ever GPL/LGPL-licensed:

- **The fork stays under the same licence.** No relicensing to something more permissive,
  including for new files the fork adds - "AI helped write it" does not change this. A
  modified version is still a derivative work bound by the original's terms.
- **`LICENSE` must be the licence's own text, fetched verbatim, not a summary or a link to
  one.** One of GPL's own terms is that its text must not be altered, so paraphrasing it -
  however accurate - does not satisfy "provide a copy of the license." Fetch the raw text
  directly (a canonical `.txt` URL, e.g. `gnu.org/licenses/gpl-3.0.txt`) rather than
  through anything that summarizes or rewrites content - a fetch tool that runs a page through
  a model is exactly the wrong tool for text that must be reproduced exactly.
- **The copyright notice is separate from the licence text**, using the wording the licence
  itself provides for this (GPL's own "How to Apply These Terms" section carries a
  fill-in-the-blanks template) - filled in and placed in the README or a source file header,
  not edited into `LICENSE`, since baking it into the license text would itself be altering
  that text.
- **Mark files as actually changed** once real modification starts, not retroactively on the
  untouched vendored baseline commit.

**The Credit section must explicitly state the modification permission, not just name the
licence.** For whichever original mod's code this fork actually alters, after naming the
licence, add a plain sentence: "[Licence] explicitly permits modifying and redistributing this
code, which is what this fork does." Naming the licence alone ("MIT licensed") leaves the
reader to work out what that grants; state it outright.

**Only where it is actually verified true.** Check the licence before writing this - the
project's own repo's `LICENSE` file for a fork, or (when no repo exists, as with Auto Draw) the
shipped binary's own version resource (`LegalCopyright`). If a mod's licence status is not
confirmed, do not assert permission - say what is actually known and flag the gap instead.
This does not apply to a mod that is merely a dependency or a visual reference and whose code
is not being altered (Infinity UI, SKSE Menu Framework, Address Library as requirements; the
Frame Reskin Preview's visual reference to Untarnished UI's palette, which alters no code of
Untarnished UI's) - the statement is specifically about code this project modifies.

**Main features must call out any per-frame performance work.** Whenever a change reduces
per-frame polling, Scaleform calls, or other work done every frame - not just when one is
introduced for the first time - add or update a bullet under Main features saying so in plain
terms (what got cheaper, roughly how much, and that behaviour is unchanged). The owner asked for
this after Dragon's Eye Minimap 1.4.8 removed three per-frame code paths and the change was
only recorded in the changelog, not in the description a first-time visitor actually reads -
performance is something people decide to install a mod over, so it belongs in the features
list, not buried in version history.

**Every mod's page includes a Debugging section**, after Main features and Installation and before
Requirements - added to the template at 1.0.2 after the owner dropped a refined version back into
`1. mod sorter`. A short instruction to send the debug log for any bug report, plus that mod's
own log path: `Documents\My Games\Skyrim Special Edition\SKSE\<PluginName>.log`. This mirrors
the same gap that also needed fixing directly in each mod's own packaged `README.txt` - state
the exact log path in both places, not just one, since a user reads whichever one they
happen to have open when something goes wrong. Skip this section only for an asset-only
add-on with no DLL of its own (e.g. the Frame Reskin Preview) - there is no log to point to.

**Every mod's page includes a Compatibility notes section**, right after Requirements and
before Credit - added to the template at 1.0.3, replacing an earlier one-line "Compiled for
Skyrim SE/AE" claim that overstated what was actually verified. Every mod in this project
uses CommonLibSSE-NG's standard `[id removed]`/`REL::VariantID` pattern for
every address it touches - no hardcoded, version-specific addresses - so state that plainly:
"There isn't a single hardcoded, version-specific address anywhere in this plugin - every
one resolves through Address Library at load time, so it should work on whatever Skyrim
version Address Library has a database for." Follow it with the honest caveat: which version
this build was actually developed/tested against (1.5.97 SE for every mod in this project so
far), that AE (1.6.x) is expected to work by the same reasoning but has not been verified in
practice unless it genuinely has been, and that Skyrim VR needs a different build target this
project doesn't ship. Verify against that mod's own `CMakePresets.json` (or equivalent) that
the shipped preset actually keeps both `ENABLE_SKYRIM_SE`/`ENABLE_SKYRIM_AE` defined before
claiming AE compatibility at all - don't assume from the preset's name alone (a preset named
"se-only" in this project's own mods only excludes VR, not AE).

**A finalized mod that gets a real update after already having Nexus distro material gets a
`changelog.txt`** in that same `11. Nexus distro\<Mod Name>\` subfolder, separate from
`nexus-page.txt` - a running log of what changed between versions, one entry per version,
newest first. This is specifically for updating a mod already on Nexus (posting a new file
version to an existing page), not the first time a mod is finalized - the mod's own README
and `PORT-NOTES.md` already cover "what changed" for that case. Each entry: the version
number, the date if known, and a short plain-language summary of what actually changed and
why a user would care (not a raw commit-message dump) - matching Nexus's own "Change log"
tab convention, ready to paste in as-is. Create the file (backfilling every version already
shipped) the first time a finalized mod gets updated after this rule existed, then just add
a new entry per version after that - don't wait to be asked each time.

**Generate art when possible, in
the right formats for Nexus, without asking first** - there's no image-generation model
available, so this means a code-drawn banner/tile (HTML/CSS, rasterized via a headless
browser - `msedge.exe --headless --screenshot=...` is available on this machine), not
painted or photographic art; say so plainly rather than passing it off as more than it is.
**Ask for input after finishing, not before** - the owner explicitly authorized doing this whole
step without asking permission first, then reviewing the result together. If something
genuinely needs his input to proceed well (a real screenshot, a style direction) and he's
not available to ask, log it to the backlog (`2. Mod Types\to-do list\to-do-list.md`, a dated
entry under "Open") instead of blocking.

**Standing banner theme, confirmed for every future mod card unless the owner says otherwise**:
Untarnished UI's palette - black background (`#050505`), a white (`#f5f2e9`) hairline frame
around the whole banner, and any mod-specific art inside it (e.g. a minimap) using that same
black-fill/white-frame treatment. No accent color - genuinely monochrome, matching
Untarnished's own real palette (see `RESOURCES.md`/the SMF theme work). Confirmed against
Dragon's Eye Minimap's banner; reuse that same look for every mod card from here on rather
than designing a new palette per mod.

> **Amended 2026-09-29 (the owner): Oblivion Remastered mods use a different palette.** *"I want all of the Oblivion
> Remastered billboards and banners to be in the paper map white vanilla color with brown letters ... Including the
> small blank banner will be the new vanilla white color."* So every banner of a mod for Oblivion Remastered - the
> 1920x1080 and the empty 1300x372 alike - has the game's paper-map white as its field (`#e6dfd1`, sampled from the
> game's own paper textures), brown letters (`#4a3222`) and a brown hairline (`#6b4e36`); the layouts and the two
> sizes are unchanged, and any Skyrim mod keeps the Untarnished black-and-white above. The OR templates are
> `11. Nexus distro\_banner-template-1920x1080-oblivion.html` and `_banner-template-1300x372-oblivion.html`; the seven OR
> distro folders of that day were re-rendered the same day. Which folders are OR is read from each `notes.txt`'s
> "Game domain: oblivionremastered" line, never from the folder's name (three names say nothing about Oblivion).

**Always ship exactly two sizes of the banner, every mod, every time**: **1920x1080** and
**1300x372** - confirmed by the owner directly on Nexus's real upload page (2026-08-26), which is
what actually matters here. **Gotcha, same day**: a wiki search
(`wiki.nexusmods.com/index.php/Creating_a_mod_page`) claimed 1400x400 and that got used to
"correct" this value for a while - wrong. The live upload page is the source of truth for an
exact numeric UI spec like this, not a wiki/forum result found by search - don't repeat that
detour, and don't re-"correct" this back to 1400x400 without the owner confirming the live page
actually changed. Reusable templates for both live at
`11. Nexus distro\_banner-template-1920x1080.html` and `_banner-template-1300x372.html`. Don't
generate only one size or invent a third.

**The 1300x372 size is fully empty, standing rule (the owner, 2026-08-26)**: no title, no
tagline, no version pills, no icon art - just the dark background and the white outer rim,
identical across every mod. There is no per-mod CONTENT block to edit for this size any more;
copy `_banner-template-1300x372.html` as-is and rasterize it unchanged. The **1920x1080** size
is unaffected - it still carries the full title/tagline/pills/icon-art CONTENT block per mod,
copy and edit that one normally.

**The banners only get regenerated at finalize time, not on every intermediate build.** This
answers the open question that used to sit in the backlog about when Nexus distro material
gets generated at all - the owner's answer: the pictures specifically wait for a mod to actually
move to `10. finalized mods`, then regenerate every time that mod finalizes again afterward (a new
version's own title/version pill, not a stale one left over from whichever version happened to
be current the last time the banner was drawn). Don't touch the banner PNGs for a mod that's
only sitting in `7. current test builds` mid-testing - `nexus-page.txt`/`changelog.txt` content
can still be drafted or corrected any time (e.g. fixing a wrong mod's title/art baked into a
banner, which is a bug fix, not a new-version regeneration), but a routine version bump alone
is not a reason to re-render the art.

---

## 21. Finalize proactively - when the open number holds something worth publishing - but only what works

> **Amended 2026-11-12 (the owner): a model mod's finalized package is re-rendered before it is posted.** *"From now on,
> we have to re-render the package before posting it as part of the finalization process, so we don't run into the same
> issue as we did this time."* Truly Nordic Carved Weapons Replacer 1.1.0 was posted with the greatsword blade's UVs
> stretched 2-5x near the tip: every render, composite, the Sketchfab model and every check had looked at work-folder
> meshes, never at the NIF that shipped. For a package that ships any `.nif`, the last station of finalizing is role
> `package-render`: from the FINALIZED copy in `10. finalized mods` - every main-file and FOMOD option folder - it
> renders every shipped NIF with the DDS textures it ships (standard front, back, side, top and three-quarter views, a
> close-up of every surface, a UV-density view), runs the design gates on those NIFs (UV stretch: no UV island whose face
> has more than 3% of its area over 2x or under 0.5x the island's own median texel density, on a patch of at least 1% of
> the shape's surface - a smaller patch is listed as a warning; the engraving layout where the repo keeps layout records;
> the surface profile) and writes the sheets and
> `package-render.json` - the hash of every NIF and DDS - into the distro folder's `assets\package-renders\<ver>\`. The
> owner sees those sheets before the upload. Posting refuses without it: role `package-render-gate`, run by
> `nexus-upload.py` before anything is sent, refuses a model mod unless that result exists for exactly the finalized
> package's hashes and passed (a FAILED render passes only when the owner, after reviewing the sheets, accepts it in his
> own words: `package-render.py accept --reason`). A failed render does not undo the finalize; finalize ends with exit 4,
> finalized and not postable, and the model is fixed and finalized again. Composites, banners, gallery images and the
> Sketchfab model are made from the finalized package after its render, never ahead of it; the gate warns about any in
> the distro folder that are older than the render. A package with no `.nif` is not affected.

> **Amended 2026-10-13 (the owner, 2026-10-12): one straight order, each station once.** A version moves
> working -> gate -> finalized -> distro, and no station repeats before the reason it failed is fixed. `finalize-mod`
> runs it as: push the commits; sync the distro TEXT from the candidate package; run the gate ONCE (one gate event); tag;
> move into `10. finalized mods` and zip; copy the zip into the distro folder and check its hash against the finalized
> zip (a mismatch fails the finalize and takes the copy back out - a post-check, not a second gate run); record
> `finalized`, then `distro-synced`. The only stations a version may skip are the compatibility verdict (situational)
> and `installed`. A refused gate is not run again on the same inputs - the work goes back to test and fix first.

> **Amended 2026-10-11 (the owner): numbers move only when a build is posted.** *"change the versioning logic from has
> to be proven working to get the number to has to be posted to Nexus. To get a new number."* An unposted number now
> takes every change until it is posted, so the version count can no longer run five ahead of `10. finalized mods`: the
> trigger below is read as "the open number holds something worth publishing", and five versions is retired as a clock.
> Working is still the hard gate for finalizing and for posting - only the build recorded working (its hash) is
> finalized and posted. When a change made after that record is still untested, test it and record it working again,
> or finalize the build that was proven; the package and finalize gates compare hashes, so the two cannot be mixed up.

> **Amended 2026-10-06 (the owner): the game-not-installed exception.** *"We'll have to make a new rule or an exception
> to the rules that in the event that the game is not downloaded, that we'll have to forego in-game testing with a
> disclaimer in the file options."* When the game a mod is for is NOT installed on this machine (first case: Oblivion
> Remastered, uninstalled by the owner, when a player's crash report needed AMF for Oblivion 1.0.7), the in-game gate
> below is waived for that release - and only then. Everything else still has to pass: it builds, every offline check
> the mod has runs, `pre-finalize-check.ps1` and the compatibility stop. The version is recorded working with the
> evidence "NOT TESTED IN GAME - game not installed" plus the build and offline checks, never as an in-game result.
> The Nexus file's **File options** (its file description) carries the disclaimer, in plain words: *"Not tested in game:
> the game was not installed when this update was built. It was built and checked without running the game. Please
> report anything that goes wrong."* The disclaimer comes off with the next release that IS tested in game. A game that
> is installed is never treated this way; skipping a test for convenience is not this exception.

Moving a mod into `10. finalized mods` used to be the one step that waited for the owner to say so. It
no longer does. He handed the timing over: *"when you think it's appropriate, or perhaps every
five versions, just send mods to finalize."*

Finalize **whenever the open number lands something worth publishing** rather than sitting on it.
(The old clock - five versions past whatever sits in `10. finalized mods` - cannot run any more:
a number only moves when a build is posted, so changes gather under one open number until it goes out.)

**The hard gate is that it has to work.** His condition: *"it has to be at least functional so
that I can use it as an update to the Nexus page."* A finalized package is distributable
material that goes straight onto Nexus, so **functional means observed working** - a run he has
reported on, or a specific feature confirmed in game - not merely that the toolchain produced a
DLL. That is deliberately a stricter bar than `7. current test builds`, which only asks that the
build succeeded.

When the newest build is untested but an earlier one was confirmed, **finalize the confirmed
one.** Do not stall the pipeline waiting for the newest to be verified, and do not publish
something unverified to avoid stalling. The confirmed build is the one that can be defended
to a stranger downloading it.

**Before it actually moves into `10. finalized mods`, it stops in `8. confirm compatibility`
first** - checked against this project's other current mods and the frameworks/
utilities in `2. Mod Types\Framework or Utility`, not Nexus or upstream (that's `12. needs an update`'s job, and only
runs after finalizing, not before). A "compatible"/"compatible with caveats" verdict clears it
to continue; a real conflict holds it out of `10. finalized mods` until fixed, the same as the
functional-build gate above. This is a new stop in the pipeline, not a replacement for the
functional-in-game gate - both have to pass.

**It also has to clear `pre-finalize-check.ps1` first - mandatory, not optional.**
Run it against the candidate version before moving anything into `10. finalized mods`. A clean
run (no FAIL) is required to proceed; a genuine FAIL blocks the finalize until it's fixed, or
explicitly acknowledged and justified with a dated note in `PROGRESS.md`. This exists specifically
because "it has to work" (this rule's functional gate, above) and "the rest of the rules were
followed" turned out to be two different questions - the first was already being checked by
The owner's own in-game testing, the second was not being checked mechanically at all, and that gap
is exactly what shipped Compass Navigation Overhaul v1.0.10 and Dragon's Eye Minimap
v1.4.11/v1.4.12.

Finalizing still carries everything it always did: commit and tag the source repo, build the
`.zip` alongside the loose folder, refresh the Nexus distro material and changelog, and clear
out `5. current project mod` - in the order of the 2026-10-13 amendment above.

**"Refresh the Nexus distro material" is now mechanically automatic, not just documented
(2026-08-26).** the owner's own words: *"Make sure that any finalized mods have their Nexus package
automatically. Because if they are in finalized, it's assumed that they're going to go to
nexus."* The 2026-08-26 accuracy audit found this had drifted in practice (stale version
numbers, a banner never regenerated, one mod finalized - Auto Draw - with no Nexus distro
folder at all) precisely because it depended on remembering to do it, the same class of gap
`pre-finalize-check.ps1`'s mechanical gate already existed to close for everything else. `sync-nexus-distro.ps1`
(its auto-fix companion) is the fix - `finalize-mod` runs it as part of finalizing (its text before the gate, its zip
after the move); it refuses to run outside a finalize unless the version is already finalized. It auto-corrects every version reference (`nexus-page.txt`'s Source section,
`notes.txt`'s document-version counter, the banner's rendered pill - re-rasterized, not just
edited in HTML), swaps in a current package zip copy, and backfills a missing `changelog.txt`
entry from `git log`, clearly flagged as auto-generated and needing review. **It deliberately
does NOT write brand-new Description/Main features/Requirements/Credit prose for a mod
finalizing for the first time** - that's real content work, not a mechanical fix, and the
script flags a missing `11. Nexus distro\<name>\` folder plainly (console + a dated `to-do-list.md`
entry) rather than inventing placeholder text. Auto Draw hit exactly this case when the script
was first run for real - flagged, not faked; still needs a human/agent content-writing pass
before it's actually Nexus-ready.

---

## 23. "Trim the fat" - keep the current version and one previous per mod

> **Amended 2026-10-13 (Main Agent with the owner's rule that a step runs by itself, never on request): the clean-up of
> `10. finalized mods` runs after a version is POSTED, not at finalize.** The previous release is cleared only once the
> new one is live. Role `post-release-prune` keeps the posted version and one previous (plus anything finalized above
> it), sends older finalized folders and zips to the Recycle Bin, and runs `prune-test-builds` for the mod. It fires
> from the one ledger write that first records a posting for that version - whichever path records it (the Nexus upload,
> a local mod's finalize, the page sync) - and never for a posting the ledger already knew. When that
> write happens inside a read-only action (a gate run, status), the clean-up is only marked pending and runs at the next
> writing action (posted, bump, record); a check never changes the folders it is judging. Never under -WhatIf; one
> event per clean-up; a clean-up problem is a warning, not a failed post.

> **Amended 2026-10-12 (the owner):** *"we only keep 1 previous version at a time not 5 from now on"*. The cap is the
> current version plus ONE previous, in `7. current test builds` and in `10. finalized mods` (older releases live on as
> GitHub tags and on Nexus). It was five until 2026-09-28 (*"we only need to keep the current copies and not 5
> versions"*), then one. `prune-test-builds` defaults to `-Keep 2` and the post-release clean-up keeps one previous release; both
> send what they prune to the Recycle Bin. A copy an enabled MO2 profile still uses is kept until that profile stops
> using it.

A named command - full definition in `commands.md`. It runs `prune-test-builds -Apply` across every mod at once,
sorting versions numerically so `1.1.10` is newer than `1.1.9`, and says what was pruned rather than doing it silently.

**This command is a backstop, not the mechanism.** Packaging runs `prune-test-builds -Apply -ModName` at its end and
posting a version prunes `10. finalized mods` (the amendment above), so the cap is an invariant that cannot drift rather
than a sweep someone must remember to ask for.

**Why it works that way:** a cap enforced only by a human-issued command is a cleanup habit, not a cap - Local Map
Upgrade and Compass Navigation Overhaul were both keeping nine versions when this was found.

---

## 34. `pre-finalize-check.ps1` - a mandatory, mechanical gate before finalizing

> **Amended 2026-10-13 (the owner, 2026-10-12: "the gate is not the test"): a refused gate is not run again on the same
> inputs.** The gate fingerprints everything it reads - the candidate package's files, the distro folder's text, the
> repo's HEAD, its upstream and its uncommitted changes, `gate-rules.json`, the mod's ledger and registry rows, the
> compatibility verdicts, the gate acknowledgements in `PROGRESS.md`, `DEFAULT-KEYS.md` and the gate scripts themselves -
> and records the fingerprint and the list of what it covered with its gate event. When the last gate event
> for that mod and version is a refusal with the same fingerprint, it refuses at once (exit 3) and repeats the stored
> reasons: fix them, repackage or re-record, then run it again. A fix that changes nothing the gate reads was no fix. A
> wrong refusal - or a fix made outside what the gate reads, such as installing the build into MO2 (rule 29) or a GitHub
> visibility change (rule 3) - is stepped past only visibly, with `-Force -Reason "<why>"` (finalize-mod passes both
> through), which writes the reason into the event. The stand-alone package gate stays a diagnostic and records nothing.

> **Amended 2026-10-12:** shrunk to the gate that enforces it (the owner approved the simplification review's item 5);
> the list of checks lives in the tool's own header and in the rows of role `gate-rules`, and the full earlier text of
> this rule is in `rules-archive\`.

The owner: *"Automate the rule following as much as possible... so that before mods go to finalize, they have been checked
against the rules and playbook."*

**Finalizing runs `resolve.py run pre-finalize-check` and stops on any FAIL** - role `finalize-mod` runs it ONCE, before the move, and
refuses a finalize it did not clear; what it checks is its own header plus every row of role
`gate-rules`, which it evaluates through the package gate. Results are PASS / FAIL / WARN / SKIP; a SKIP is a gap, not a
pass. Why: each rule that relied on an agent remembering it at finalize time shipped a real mistake (Compass Navigation
Overhaul 1.0.10, Dragon's Eye Minimap 1.4.11 and 1.4.12) until a script checked it.

---

---

## 35. A bug report has to reach the mod's author by a route that is watched

Reports arrive on each mod's own Bugs and Posts tabs, not only on one dedicated page. The original kept a single "request hub" page with tagged submissions and a scheduled poller. Relying on it silently cost real reports: the hub page was removed by Nexus staff for not being a mod, and the poller read the placeholder that a removed page still serves as "nothing new".

- A route that is checked by a tool needs a check on the tool: zero entries from a page that had entries is a failure, not a quiet day.
- Watch the pages the reports actually arrive on, the mods' own, and read them directly whenever the queue may be stale.
- A tag on a submission's first line saves guessing its category; an untagged one still goes on the to-do list instead of being dropped.
- The poller reaches the internet, so it is not in the kit (`OPTIONAL-SCRIPTS.md`, item 8).

## 48. Version numbers are enforced by a check, not by care - and only a posted build spends one

> **Amended 2026-10-21 (the owner: "Update the versioning logic to use this", semantic versioning):** `bump` requires
> `-Kind patch|minor|major` and refuses without it; the arithmetic steps the component the kind names, with no
> roll-over; a higher-kind change on an open number withdraws it and re-issues from the last posted number. The
> per-hash antivirus reason below was dropped (a new build has a new hash whatever its number).

> **Amended 2026-10-12 (later):** the sentence on Nexus as the floor on "working", which the shrink of the same day had
> dropped, is restored below with the owner's words (memory nexus-last-upload-is-the-working-floor, retired with this).

> **Amended 2026-10-12:** shrunk to the gate that enforces it (the owner approved the simplification review's item 5); the
> full earlier text - the 2026-08-27 crash investigation that burned seven numbers in an evening, the five places a
> version lives, the 2026-10-11 move from "working" to "posted" in full - is in `rules-archive\`.

The owner, 2026-08-27: *"find a way to strictly enforce the versioning logic so that you don't keep getting it wrong."* And:
*"dysfunctional test builds should not be given a version number, only functioning builds."* 2026-09-12: *"I want the
version logic to be in one file ... tooling based only ... a logic gate where it fails if it doesn't pass the version
logic gate."* 2026-10-11: *"change the versioning logic from has to be proven working to get the number to has to be
posted to Nexus. To get a new number."*

**Every version number comes from role `version-gate`, which refuses anything it did not issue** - `bump -Kind
patch|minor|major` (no kind: refused) hands back the OPEN number until it is posted - unless the change is of a higher
kind than the open number, which is then withdrawn and re-issued from the last posted number - and otherwise issues the
LAST POSTED number stepped by the kind (semantic versioning, 2026-10-21); `record` needs in-game
evidence and the binary's SHA-256, and working is still required before finalizing and posting; `posted` spends the
number (`nexus-upload` records it after a verified upload, and a linked page's published version is recorded as
posted); `gate -Stage package|finalize` refuses a number, a location or a binary that disagrees, and a version literal
in a file the tool was not told about; there is no -Force. Documents and the rules are never posted and step once per
change, with the same arithmetic. Why: a version lives in five places that drifted apart while each was "enforced" by
care, and a number spent on an experiment or an unposted build makes the Nexus changelog meaningless. (This used to add
"and the per-hash antivirus submissions"; the 2026-10-21 correction holds that a false-positive submission is keyed by
the file hash, which changes with every build whatever its number, so the version number has no bearing on it.)

**Nexus is the floor on "working".** The owner, 2026-09-12: *"I also want to add a function here where the gate
checks the Nexus for the last uploaded version because whatever the last uploaded version was is assumed to be working
because it passed the finalized gate"*. So a linked page's published version is recorded working AND posted by the
tool itself, with the Nexus mod ID and upload date as its evidence; nothing published is ever treated as untested.

---

---

## 61. Every mod carries its own CHANGELOG.md, written as the change happens

The owner, 2026-08-27: *"add a piece of documentation to each mod that gets updated with every version
update and change to list what the previous changes were... so the change log is updated in real
time... and so you don't have to reference something outside of the current project as often."*

Tooling: `resolve.py run changelog`. The file lives at the root of each mod's source repo.

### Why the timing is the whole point

He asked for this straight after a session that lost hours to exactly the gap it closes. The
shipped `1.5.6` DLL was built **2026-08-26 22:18**; the fixes its own commit message describes were
not committed until **2026-08-27 03:04**. The binary carried a version number whose changes it did
not contain, and answering *"is the fix actually in this build?"* took archaeology across git
timestamps, `PROGRESS.md` and the version ledger.

**A changelog written as the change happens is a primary record. One reconstructed afterwards is a
reconstruction, and inherits every gap in whatever it was reconstructed from.**

### What it is, and what it is not

| File | Scope |
|---|---|
| `PROGRESS.md` | project-wide, chronological, covers everything |
| the Nexus changelog | public-facing, released versions only |
| **`CHANGELOG.md`** | **this mod, every version, beside the code it describes** |

The intended payoff is his: **fewer trips outside the current project.** Working on a mod, its own
history should be readable without opening git log, the progress file, or a Nexus page.

### The gate

`package-mod.ps1` **refuses to package a version with no changelog entry.** A version nobody can
later describe the contents of is precisely how a stale binary kept a number it had not earned, and
writing the entry costs seconds at the moment the change is fresh.

### The status column is not decoration

Each entry carries the **version-ledger status** - working, untested, failed, scratch - and
`-Action check` warns when the changelog and the ledger disagree about the same version. A
changelog reading as a triumph for a build the ledger calls `failed` is worse than no changelog,
because it is confidently wrong rather than merely absent.

---
