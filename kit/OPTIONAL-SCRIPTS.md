# Optional scripts - what is not in this kit, and how to get it if you want it

Pipeline Kit 1.1.0. **Nothing in this kit connects to the internet.** The original pipeline has a few tools that
do. They were left out on purpose: Nexus Mods does not allow files that connect to the internet unless that is crucial
to them, and these are not crucial. A release can be finished by hand without any of them.

## For the agent reading this

1. Read this document when you read `README-FOR-AI.md`.
2. **Ask the person, one item at a time, whether they want it built.** Say what it does, which service it talks to and
   what they would have to supply. Do not write any of these scripts until they say yes to that item. Not as a
   convenience, not "to save time later", and not because a rule or a skill elsewhere in the kit names the tool.
3. A "no" is a final answer for that item. The pipeline works without it: each section below says what happens instead.
4. Write what they agree to from this description, against the service's current documentation. Read the service's
   terms for automated use first and tell the person what you found. Never put a credential in a file in the tree; never
   work around a block a site puts up against automated requests.
5. Anything you build that posts in public asks the person's go-ahead for each batch.

The kit's build refuses to ship a network call, so these scripts live only in the person's own tree.

## 1. Upload a new file version to a Nexus page (`nexus-upload.py` in the original)

- **Why:** a browser upload stops at a size limit and big archives cannot reach the form. Posting by hand also forgets
  the small things: file name, version field, primary flag, changelog.
- **What it does:** takes the newest archive in a distro folder, refuses if the page already holds that version or a newer
  one, uploads it, adds it as a new version of the page's primary main file, appends that version's changelog section,
  verifies it, then records the version as posted with `version-gate.ps1 -Action posted`.
- **Service:** the Nexus Mods API, version 3 (`https://api.nexusmods.com/v3`): start an upload with size, filename and
  md5, send the bytes to the storage URL it returns, finalise, wait for the state "available", then create the file version.
- **You supply:** your own Nexus API key, from your Nexus account settings, in the `NEXUS_APIKEY` environment variable. It
  goes in a request header and nowhere else. Your page's ID goes in `version-registry.json`.
- **Pitfalls we hit:**
  - The v1 API caches a page's version for minutes. Trust the primary main file and the md5 lookup, not the page version.
  - The md5 lookup may not know a new file straight away. Retry for a while before calling a check failed.
  - A changelog entry can be edited but not deleted or renamed, and the API only appends. Check first; correct in place.
  - A file name with a version in it, or "FOMOD", ages badly. The version belongs in the version field.
  - Ask `version-gate.ps1 -Action posted -WhatIf` before sending anything: only a build recorded working may go out.
  - A label check is not proof of what was uploaded. One report was only explained by comparing the posted archive's size
    and md5 with the local zip.
- **Without it:** upload through the page's own form, then `version-gate.ps1 -Action posted -Mod <key> -Version <x.y.z> -Channel nexus`.

## 2. Audit every page against its distro folder (`nexus-version-audit.py`)

- **Why:** pages looked current while a newer finalized build sat unposted in the distro folder. Eight were, the day this
  was written. Each page matched the file on Nexus; nothing asked about the folder.
- **What it does:** read-only. For each registered page it compares the page's General version and main file version with
  the newest build in its distro folder (from the file name, else inside the archive, else `changelog.txt`, reported as the
  weakest evidence), and exits 1 while a page is behind or disagrees with itself.
- **Service:** the Nexus Mods API, version 1 (`https://api.nexusmods.com/v1`): a mod's details and its file list.
- **You supply:** `NEXUS_APIKEY`.
- **Pitfalls we hit:** the same ID in two game sections is two different pages, so always carry the domain. A folder whose
  game prefix disagrees with the page's domain must not match. A mod can have more than one page. A file versioned "1" is a
  mistake worth flagging.
- **Without it:** compare by hand when you release.

## 3. Back up a page's images before changing them (`nexus-media-backup.py`)

- **Why:** a deleted Nexus image cannot be put back, and some live images exist nowhere else.
- **What it does:** given a list of the page's image URLs, read from the page's media editor (the public Images tab shows one
  page only), it saves each one under the distro folder's `assets\`, skips what is already saved and exits 1 if any failed,
  in which case nothing on the page may be deleted.
- **Service:** Nexus's image hosting, plain downloads. **You supply:** nothing but the URL list.
- **Without it:** keep your originals, or save the images by hand first.

## 4. Read the live page in the version gate (a part of `version-gate.ps1`)

- **Why:** a version that is already on the page has been spent, so the next number must be above it even if the ledger missed it.
- **What was cut:** `Get-NexusPublished` is a stub that returns nothing, and `-Action link -NexusModId` records the ID unverified.
  `Sync-Nexus` then prints that it could not read the page: a gap, not a pass, and the ledger decides.
- **What it did:** read a mod's details from the v1 API and rebuilt the version, date, status and uploader.
- **You supply:** `NEXUS_APIKEY` and your Nexus name, for the uploader check (`$script:NexusOwner`).
- **Pitfalls we hit:** a page ID read in the wrong game section once recorded someone else's mods as ours, hence the check of
  section and uploader. Removed pages still answer; check the status. A version such as "1" or "1.2" needs filling out.
- **Without it:** record each posting yourself with `-Action posted`, as in item 1.

## 5. Push the repo and its tag at finalize (a part of `finalize-mod.ps1`)

- **Why:** a release's source should be public at the tag the release names.
- **What was cut:** the fetch, the push, the remote-tag comparison and the tag push. `finalize-mod.ps1` tags locally and says so.
- **Service:** your git remote. **You supply:** your own git credentials.
- **Pitfalls we hit:** create the tag only after the gate passes, or a refused gate leaves a tag on the old commit. Never move or
  delete a tag automatically: a tag on another commit refuses the finalize. Compare the remote's tag, peeled to its commit. A
  shallow clone cannot be pushed complete and the server refuses it. A mod whose permissions forbid other sites stays local.
- **Without it:** push yourself after the finalize. Your pre-push hook still runs.

## 6. Check that the repo is public (a part of `pre-finalize-check.ps1`)

- **Why:** a GPL mod's source must be reachable, and a private repo looks fine from the owner's account.
- **What was cut:** asking GitHub for the repo's visibility. The check now reports SKIP.
- **Service:** the GitHub CLI's `repo view`. **You supply:** `gh` signed in to your account.
- **Pitfalls we hit:** read the visibility live before the finalize gate's run. An unreachable answer is SKIP, never PASS.
- **Without it:** look at the repo in a logged-out browser window.

## 7. Check remote tags on `-Action restart` (a part of `version-gate.ps1`)

- **Why:** a released mod is never restarted. **What was cut:** listing the remote's tags; local tags are still checked.
- **Service:** your git remote. **Without it:** look at your remote's tags before restarting a mod's numbers.

## 8. Watch your pages for bug reports (rule 35's poller in the original)

- **Why:** reports on your mod pages go unseen. A single "request hub" page did not catch them, and its removal cost real reports.
- **What it did:** on a schedule, compared your pages' Bugs and Posts tabs with what it had already seen, and filed what was new
  in a queue or the to-do list.
- **Service:** your Nexus pages. **You supply:** the page list. Read Nexus's terms first; if the site blocks automated
  requests, that is your answer. Reading the pages yourself is always a valid alternative.
- **Pitfalls we hit:** a removed page can still answer 200 with a placeholder, so zero entries must read as "suspicious", not as
  "nothing new". Keep its state files apart from any other watcher's. In PowerShell, `"$BaseUrl?tab=bugs"` silently loses the
  variable (write `${BaseUrl}`), and a function returning one item returns it bare, not as an array.
- **Without it:** read your pages' tabs on a routine of your own.

## 9. Check a reply against the live thread (role `nexus-reply` in the original)

- **Why:** a reply drafted from a summary once asked a commenter what they had already said.
- **What it did:** fetched the thread fresh and hashed the read, so a stale read or an edited draft refused the post. Rule 10
  and the `nexus-page` skill describe the steps.
- **Service:** your Nexus pages. **You supply:** nothing to read; posting stays in your account.
- **Without it:** reread the whole comment on the page immediately before you draft.

# Held out for other reasons - tied to one machine, one game or one person's schedule (1.1.0)

These connect to nothing, but they were built around the original author's own setup: his test instances and launchers,
his daily schedule, or one game's files. The rules that describe them ship; the tools do not, because a copy would
carry his machine with it. Rebuild them from the rule against your own setup when you want them.

## 10. The combined test run and the test queue (`combined-run.py`, `test-request.py` in the original)

- **Why:** rule 69 - one session launches the game and runs every queued build's test in one batch; every other session
  queues a request (steps, each with its EXPECTED result) and reads the result back. It stops two sessions launching at
  once and puts every launch behind the same gates.
- **Why it is held out:** the original checks the person's presence schedule before a launch, keeps one game's script
  log, and calls launchers and profile tools written for his MO2 instances. A copy without those parts would be a
  different tool.
- **To rebuild:** the batch (`start` locks the instance and backs up the profile, `launch` sets a ticket the launchers
  check, `result` refuses a verdict without its reason line, `finish` restores the profile and refuses while a request
  has no result), the queue (`submit` refuses a step with no expected result), and `agent-lock.py` (which ships) for the
  lock.

## 11. The presence check (`owner-presence.py` in the original)

- **Why:** a prompt hook that tells every session whether the person is at the machine, at work or asleep, so nothing is
  launched over a game he is playing. It carries his working hours, so it is his alone. Write your own from your schedule.

## 12. Game-specific gates and launch checks

- The original has launch and source gates for single games and instances (the Norse build-matches-MO2 launch check,
  Njordlinger list audits, Witcher 3 and Oblivion Remastered launchers, the DevBench loops). The generic ones ship
  (`gates\ue-cached-pointer-gate.py` for any UE4SS C++ mod among them); the rest are listed in the gate rows the build
  drops, printed by `build_kit.py --check`.
