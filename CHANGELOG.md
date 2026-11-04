# PipelineKit - changelog

Written as changes happen, not reconstructed afterwards (rule 61). Each version carries its
**version-ledger status**, so this file cannot quietly claim more than the ledger does:

* **working** - observed running in game
* **untested** - built and packaged, not yet confirmed
* **failed** - built but crashed or malfunctioned; the number was reclaimed
* **scratch** - a hypothesis-test build that never held a real number

## 1.1.0 - 2026-11-03 - untested

### Removed
- Gate rows naming the original's page links, rows that spelled a private identifier inside a pattern, and 13 rows whose helper script is not shipped (package-gate treats a missing helper as a failure).
- Other people's content: game-signatures.json (byte signatures), the console-command reference compiled from wikis, the record of framework licence texts, another mod's changelog used as the template's example. Promotion of outside services, and one PC's hardware and schedule, including the whole machine-health record (a short design document replaces it).
- Every tool and code path that reaches the internet: nexus-upload.py, nexus-version-audit.py, nexus-media-backup.py; the Nexus page read in version-gate.ps1; the git fetch, push and remote-tag reads in finalize-mod.ps1 and version-gate.ps1; the GitHub visibility query in pre-finalize-check.ps1. Nothing in the kit makes a network call now.

### Added
- A screening stage (kit_screen.py, build_kit.py --screen) that fails the build on a network call, direct evidence, advertising or private details in any shipped file, with a seeded self-test of its own; the leak scan also reads text with regex punctuation removed, so a name spelled as a character class is caught.
- OPTIONAL-SCRIPTS.md: for each tool left out, why it is needed, what it does, the service it talks to, what the person must supply and the pitfalls met. README-FOR-AI.md makes the agent read it and ask the person before building any of them.

### Changed
- README and NOTICE state that the kit needs a coding agent and that the person is responsible for other mods' permissions, including Nexus's Ask Me setting for AI workflows. The pre-push hook is a small local secret check; the old one called helpers the kit does not ship.
- The documents are reduced in the build: each past-mistakes entry keeps the mod's name, the issue, the fix, the problems met and the lesson; offsets, byte patterns, disassembly, code from others, record IDs and asset paths show as [... removed]. The live files are not touched. The Patreon publish channel is the neutral 'members' channel.

### Fixed
- The self-test passes against the current scripts again: the build's rewrite for pre-finalize-check.ps1 matched its new shape, session-start.py no longer asks for a role the kit does not ship, and the self-test supplies the -PriorArt note and the -Guard and -EvidenceRef values the gates now require.

## 1.0.5 - 2026-10-21 - working

### Changed
- Semantic versioning, from the live pipeline (rules 3.1.0): version-gate bump and nextnumber require -Kind patch|minor|major; the .9 roll-over is retired (1.0.9 + patch = 1.0.10); a higher-kind change withdraws an open number and re-issues it from the last posted one. Rules part 03, the digest, the entry file and the recipe (README-FOR-AI) describe it.
- The self-test calls every bump with -Kind and gains three checks: bump refuses without a kind, a minor change issues 1.1.0 and a major change issues 2.0.0 (33 checks).

### Source repository (2026-10-22, the kit's files are unchanged)
- build_kit.py names nobody: the maintainer's identity strings and machine paths it substitutes and scans for moved out of the script into a private, untracked config (role identity-patterns); the build refuses to run without it, and its default source is the tree the repository sits in (or PIPELINE_ROOT), not a fixed path. A rebuild with the config produces the same 1.0.5 kit byte for byte.
- The source repository is public from this date, as a fresh single-commit repository; the earlier history stays private.

## 1.0.4 - 2026-10-21 - working

### Added
- Ship test-build-pick.ps1 and post-release-prune.ps1 (version-gate resolves them by role) and the gate scripts banner-highlight-gate.py, theme-outline-gate.py, translation-script-gate.py; the self-test now posts the example mod (local channel) before asking for its next number (30 checks); the leak scan also catches the owner name inside any word.

### Changed
- Rebuild from the live pipeline of 2026-10-21: rules 3.0.3, the gate rules and past-mistakes library as they now stand (513 entries), plus the tooling added since 1.0.3.
- Ship BANNED-WORDS.md from the kit itself (the live file is now a pointer to an always-on memory): the mechanism and one example row.
- Ship the two reference documents from the live docs-archive folder (VERSION-RECONCILIATION.md, AI-PIPELINE-REFERENCE.md), where they now live.

## 1.0.3 - 2026-10-10 - untested

### Fixed
- Replace and leak-scan the owner's name in any capitalisation; 1.0.2 shipped it once in capitals in PAST-MISTAKES-LIBRARY.md (a review of the zip caught it). gate-rules.json gains the row shipped-text-carries-no-owner-name, so every package fails on it from now on.
- MANIFEST.json hashes every file as shipped (files), so a member can verify the download; the hashes of the live source files, taken before sanitising, move to source_sha256 and are labelled as not matching the shipped files by design.

### Changed
- Issue a new number for any rebuild that may have left the machine: 1.0.2 was rebuilt under the same number on 2026-10-10 after the 2026-10-08 build had been packaged for Patreon, so two different zips carried 1.0.2. 1.0.3 supersedes both.

## 1.0.2 - 2026-10-10 - untested

### Added
- licence-label-gate.py and its gate row: a DLL's LegalCopyright must name the same licence family as the repo's LICENSE (three GPL mods had kept an MIT label after a relicense).
- The archive sweep (README-FOR-AI 8b): session-digest.py turns each old session into a digest of what the person asked for and what was left open, redacting credentials as it writes; docs\ARCHIVE-SWEEP-INSTRUCTIONS.md is how a checking agent judges each item against the current files.
- skill-scout.py: reads the Claude Code transcripts and flags procedures repeated across sessions that no skill covers, with an ignore list for decided non-candidates (README-FOR-AI 7d).
- Nine Claude Code skills (skills\): releasing a mod, a Nexus page, an in-game test, a menu port, the modding tools (with esm_lookup.py, a FormID-by-EditorID reader), troubleshooting (falsification and adversarial mode), session records, the named commands and the skill scout - routes through the rules and scripts, loaded only when that work starts. Install by junction (README-FOR-AI 7c).
- Ship the role resolver (rule 70): resolvers\resolve.py, resolve.ps1, session-start.py (the SessionStart hook payload) and the schemas, with the rosters filtered to the roles whose files the kit ships; kit-install generates resolvers\INDEX.md and runs resolve.py check.
- Ship PAST-MISTAKES-LIBRARY.md (the renamed library of failures) beside LOGIC-LIBRARY.md, now the short catalogue of the pipeline's logics.
- Ship fomod-destinations.py and package_paths.py (package-gate and make-fomod look them up), memory-index.py, gate-rules-index.py with a generated gate-rules-INDEX.md, find-stale-paths.py, and an empty version-ledger-prerelease.json.
- Seed the Claude Code memory folder of <ROOT> at install and fill in its project name in the data roster (role memory-folder).
- Add self-test checks: no retired-path stub in the installed tree, resolve.py check, version-gate resolved inside the temp root, the past-mistakes library role, the SessionStart payload, the gate-rules index (28 checks).
- Document the layout, calling by role, the two libraries, the identity placeholders and the SessionStart hook in README-FOR-AI (sections 0b, 3b, 3c).

### Changed
- Rebuild from the live pipeline of 2026-10-09: rules 2.10.0 (70 rules), 103 gate rules, the scripts in their kind folders (scripts\gates, release, ops, plugins), mirrored in the kit's layout.
- Read each script from its real file and fail the build on a RETIRED-PATH stub or a "moved" pointer document; derive <ROOT> from the .MD folder a script sits under at any depth.
- Move FALSIFICATION-MODE, ADVERSARIAL-MODE, TESTING-PROTOCOL and SMF-CONVERSION-PLAYBOOK out of docs\ (they ship in their skills' references\) and PIPELINE-RESEARCH to docs-archive\.
- Replace the owner's donation and Discord links with placeholders in identity.json and wherever a document quotes them.
- Point the package-script-passes gate rows at the helpers' real paths (gates\...); the flat names were stubs.
- Run the self-test with USERPROFILE pointed at its temp folder, so the install's memory folder never lands in the person's own .claude.

### Fixed
- Sanitise and leak-scan the doubled-backslash form of the owner's paths (a string literal's D:\\...), Claude Code project-folder names and the owner's MO2 test instance; 1.0.2's single-backslash patterns let them through.
- Carry the RULES-VERSION marker into the kit's CLAUDE.md; rules-version.ps1 and session-start.py read it, and the kit's entry file had lost it.
- Default install-test-build.py and xinput-import-gate.py to PIPELINE_MO2_INSTANCES and the MO2 "Default" profile instead of the owner's instance.

## 1.0.1 - 2026-09-30 - untested

### Fixed
- The kit now ships distro-names.ps1, which package-gate.ps1 and prune-test-builds.ps1 have loaded since the Nexus distro folders took their '<Game> - <Mod>' names; 1.0.0 shipped without it, so those two gates could not resolve a distro folder.

### Added
- finalize-mod.ps1: one command for finalizing (gate, git tag, copy and verified zip, game-aware distro sync, re-check, prune), replacing the hand steps in the daily loop; attention-ping.ps1, the agent's 'I need you' sound.
- Posting to Nexus Mods (README-FOR-AI section 7b): nexus-upload.py posts a distro folder's newest build as the new version of the page's main file through the Nexus v3 API (no browser size limit), nexus-version-audit.py proves every page carries its newest build, nexus-media-backup.py saves a page's images before any media change, and the browser half - descriptions, requirements, permissions, tags, media - through Claude in Chrome.

### Changed
- The documents are rebuilt from the live pipeline of 2026-09-30 (rules 2.7.9, preflight 1.1.0): the Nexus page checklist (custom permissions, requirements, current banners, AI-generated content tag, page version = posted release, newest build posted, file names without a version or FOMOD), short descriptions in their own file, and the logic library's new entries.

## 1.0.0 - 2026-09-23 - untested

### Added
- First version of the Pipeline Kit: a sanitised build of the live pipeline (entry file, digest, preflight, banned words, the seven rule parts, the logic library, commands, the reasoning-mode and testing documents, the pipeline research and narrative reference), the gate scripts with every machine-specific default rewritten to an environment variable or a derived path, gate-rules.json in full with empty ledgers, the Nexus and package templates, README-FOR-AI.md (the rebuild recipe), kit-install.ps1, kit-selftest.ps1 (22 checks over a throwaway pipeline), the example mod, both licence texts.
