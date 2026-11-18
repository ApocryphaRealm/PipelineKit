---
name: nexus-page
description: Writing, rebuilding and posting a Nexus Mods page for one of our mods - nexus-page.txt and short-description.txt in "11. Nexus distro", the standard description layout (header cards, feature cards, at-a-glance strip, quote panels, spoilers, before/after sliders), banners and the gallery, the media upload, the BBCode preview the owner reviews, and saving the description live through Claude in Chrome. Use it whenever a mod page, Nexus description, mod page text, feature list, banner, gallery image, short description, changelog tab or "the page" for a mod is written, updated, checked or posted - even when the owner only says "update the page for X" or "move X to the new layout". Also whenever a reply to a user's comment or post on a Nexus page is drafted or posted (the reply gate: reread, Fable review, then post). For posting the FILE itself, use mod-release.
---

# Nexus mod pages

> *Kit edition: this document was reduced for publication. Tools it names that reach the internet (`nexus-upload.py`, `nexus-version-audit.py`, `nexus-media-backup.py`) are not in the kit - see `OPTIONAL-SCRIPTS.md`. Other tools it names may belong to the original pipeline only (README-FOR-AI, section 10). Where text reads `[... removed]`, direct evidence was taken out.*

Policy lives in rule 10 (`<ROOT>\.MD\rules\03-versioning-and-release.md`). The layout and the posting
how-to live in **`<ROOT>\11. Nexus distro\_NEXUS-DESCRIPTION-LAYOUT.md`** - read it in full before building
or rebuilding a page; it is short and every line of it came from a correction. This skill is the route through them.
What a framework's licence requires in Credits and Requirements: read that framework's own licence file at the version you build against, before writing either section, and quote nothing you did not read.

## What a distro folder holds

`11. Nexus distro\<Game> - <Mod>\`:
- `nexus-page.txt` - the description BBCode, starting at the Description heading. Section text comes from
  `11. Nexus distro\_nexus-page-template.txt`.
- `short-description.txt` - the summary field, **350 characters at most** (Nexus's own limit).
- `changelog.txt` - one entry per version, newest first, for Nexus's Changelog tab. Never folded into the page.
- `sticky.txt` - the Posts tab's "Recent changes" sticky (see "The Recent changes sticky" below). Format and
  instructions: `11. Nexus distro\_STICKY-TEMPLATE.txt`; worked example: `Skyrim - Apocrypha Menu Framework\sticky.txt`.
- `notes.txt` - the page's own document version (separate from the mod's version) and `Game domain: ...`.
- the banners, the newest package zip, and `assets\` (backups, close-ups, superseded art).

## Writing rules that keep coming up

- **BBCode only.** Markdown prints as literal asterisks on Nexus. Bold is `[b]`, headers are drawn cards, links are
  `[url=...]label[/url]`, never bare URLs.
- **Say what the mod does, not how it is built.** A player reads the page to decide whether to install; internals,
  hook names and file layouts belong in the README or source, not the description.
- **Describe our mod on its own terms**, not as "a fork of" or "a derivative of" something; credit goes in Credit.
- **No section repeats Nexus's top drop-downs**: Requirements, Permissions, Changelogs. One Installation line covers
  what those boxes cannot show (SKSE / Address Library build per game version, what is optional).
- **Credit stays in the description** (the custom permission text says "Credit in mod Description").
- Main features calls out per-frame performance work whenever a change makes it cheaper.
- A Debugging section names the mod's exact log path (skip only for asset-only mods with no DLL).
- Close the Description with the Generative AI disclosure line. A donation link is optional; Nexus's anti-solicitation policy forbids a link to anything paid - a post, kit or service.
- Banned wording for any text the owner sees: the always-on memory `conversation-rules` (`.MD\BANNED-WORDS.md` is a pointer to it).

## Building a page in the standard layout

Tools: `<ROOT>\.MD\scripts\nexus-description\`. Worked examples to copy: `cwlu-1.0.7\` (smallest),
`cno-1.1.6\`, and `amf-2.1.5-reference\` (the original).

1. **Pictures.** Banners first (`11. Nexus distro\_BANNER-DESIGN-RULES.md`; Skyrim = Untarnished black/white,
   Oblivion Remastered = paper white `#e6dfd1` with brown). Gallery = banners only. Close-ups (gold outline, outside
   dimmed 45%) come from `pagegen.outlined()`. Before/after pairs are plain shots of the same framing, one setting
   changed. Screenshots must follow Nexus's image rules. Wheeler shots are first person.
2. **Cards.** A page script (copy `cwlu-1.0.7\gen_cwlu.py`) defines FEATURES / GLANCE / sections and calls
   `pagegen.render_cards()`; `card.html` is rendered by headless Chrome.
3. **Draft BBCode** with `{{img:key}}` tokens for pictures not yet uploaded, then `pagegen.preview()` renders it the way
   Nexus draws it.
4. **Show the owner the preview before anything goes live.** He reviews first.
5. **Archive the live page** - every image URL from the *media editor* (`/edit/media`, not the public Images tab, which
   shows one page only), then `nexus-media-backup.py "<distro folder>" urls.json`; the description with
   `backup-description.py <game domain> <mod id> "<distro folder>" <label>`.
6. **Upload** pictures in the media editor through Claude in Chrome (batches under 10 MB), then title/hide/set-primary
   through `media-editor-helpers.js` in the same session. Hidden images keep their URLs.
7. `python fill-tokens.py <draft> <out> <game id> <mod id> "<key=url-tail ...>"` - swaps tokens and checks every URL
   answers 200.
8. `python wrap-quotes.py <in> <out>` - **the last step**: every text block in a `[quote]` panel.
9. **Save** in the edit page's SCEditor (`sceditor.instance(textarea).val()` plus the React field's onChange/onBlur),
   compare the SHA-256 the scripts printed, Save, and verify by reopening `/edit/general` (the API caches).
10. Check the public page (drop-downs open, sliders render), run `nexus-version-audit.py`, and tell the owner which
    file in the distro folder is now the live text.

## The Recent changes sticky (every release)

The owner, 2026-10-11: every update also updates the sticky post, listing everything the way AMF Skyrim's does.
- **Write** `sticky.txt` with the release's `changelog.txt` entry, before finalizing: gate row
  `distro-sticky-starts-with-this-version` fails the finalize while the file is missing or its first line names
  another version. A mod without one gets it at its next release, from `_STICKY-TEMPLATE.txt`.
- **The BBCode facts** (Nexus's comment editor): a plain line break renders as a new line, so one `- ` item per line
  and a blank line between sections need no tags. Bold only the top line and the section headings - never wrap every
  line in `[b]`: the old AMF sticky did, and Nexus ran the whole post together into one block. Links are
  `[url=https://...]label[/url]`.
- **Save it at posting time**, in the same pass and under the same go-ahead as the upload, through Claude in Chrome:
  back the live text up into `assets\` (`sticky-recent-changes-before-<date>.txt`), then Edit post on the
  "Recent changes" sticky and replace its text with `sticky.txt`'s, and Save. A page with no such sticky gets it as a
  new comment, set STICKY + LOCKED. Then **read the public Posts tab back** (logged-out view or a fresh load): the lines
  break, headings are bold, items are not.

## The standing checklist for every page (rule 10)

Custom permissions text (read the box first - never overwrite an existing custom text; ask before giving a non-GPL mod
the GPL line), real requirements on the files, current banners with the newest 1920x1080 as thumbnail, BOTH AI
disclosure tags (below), General version = the posted release, the newest distro build is the primary main file,
file names carry no version and no "FOMOD" (FOMOD goes in the file's description), and the Posts tab's "Recent
changes" sticky carries `sticky.txt` for the posted release.

**AI disclosure tags - both, on every page** (Nexus warned the account on 2026-10-25 for "content classification and
tag use failure"; File Submission Guidelines, "Generative AI Tagging & Categorisation"):
- **"AI-Generated Content"** - our code, UI, translations and in-game assets are AI-made;
- **"AI Media"** - our page descriptions, banners, gallery images and thumbnails are AI-made;
- never **"AI Assisted"** - it needs evidence of human-led development and moderators replace it.

How: on the PUBLIC mod page, "Tag this mod", then, as the author, "Add this tag to your mod" on each missing one (a
tag row reads `neutral (0)` until added, `author-confirmed (99)` after). Reload the page and read both in "Tags for
this mod" - open "View more..." on a long list (the AMF pages hide tags behind it). Then record the page's row in
`.MD\scripts\nexus-ai-tags.json` (`"<domain>/<id>"`, tags, verified date; domain `site` = Modding Tools). Gate row
`distro-nexus-page-carries-both-ai-tags` fails finalize for a mod whose page has no row or lacks a tag. The guideline
also makes the author answerable for every claim on the page, AI-written text included: a performance or effect
claim (FPS, "lighter", "faster") must be true and backed by evidence or a clear technical explanation.

## Anything public waits for the owner

A description save, an upload, a delete, a sticky or a new comment that is not a reply needs the owner's go-ahead for
that batch. A REPLY to a user's comment does not - it goes through the reply gate below and is then posted without
asking him. Bump the page's document version in `notes.txt` with each real revision.

## Replying to a comment (the reply gate, role `nexus-reply`)

The owner, 2026-10-24: the original comment is reread before a reply is posted, and replies post without his consent
once the Fable session has reviewed them. A reply once asked a commenter something they had already said, because it was
drafted from a summary. Every step refuses (exit 3) until the one before it holds; `R` = `py -3 "<ROOT>\.MD\resolvers\resolve.py" run nexus-reply`.

1. **Reread.** `R snapshot --url <mod page or ?tab=posts URL> --comment <comment number>` fetches the thread fresh
   over plain HTTP (no login) and prints it, with the comment being answered marked. If the fetch fails, read the thread
   in Claude in Chrome (`get_page_text` on the Posts tab), save its text to a file and pass `--capture <file>`. Read the
   whole printout. The record id is printed (`<game>-<mod>-c<comment>`).
2. **Draft against that text**, in a file written AFTER the snapshot (a draft file older than the read is refused).
   BBCode only, no owner name or email.
3. **Ask for the review.** `R review-request --id <id> --draft <file>` writes `agent-bus\nexus-replies\<id>.review-request.md`
   (the thread verbatim, the draft, the checklist, the exact verdict commands). SendMessage the Fable session
   (Fable Agent) with that file's path. The snapshot must be under 30 minutes old here; if not, snapshot again first.
4. **The Fable session decides** by running the command from the file: `R review-verdict --id <id> --by "Fable Agent"
   --approve|--reject --draft-sha <..> --snapshot-sha <..> --notes "..."`. Only the session registered as the Fable
   session can write it, never the drafter. A rejection: revise the draft and go back to step 3.
5. **Gate.** `R gate --id <id> --draft <file>` - PASS only on an approval of exactly this draft, on the current read of
   the thread, the read under 30 minutes old (otherwise it reads again; a new reply or an edit voids the review). It
   prints the text to post. A capture-sourced record needs a fresh `--capture <file>` once stale.
6. **Post** that exact text as a reply to the comment in Claude in Chrome - no owner approval needed. Then read the
   public Posts tab back (fresh load), save the text, and run `R posted --id <id> --link <comment permalink>
   --readback <file>` (refused without a gate PASS of this draft in the last 30 minutes). It logs time, link and
   hashes to `post-log.jsonl`; a read-back that does not hold the approved text is logged as a mismatch and exits 3 -
   fix the reply on the page.

`R status` lists the records and their states.

## Saving a comment or sticky by script (WysiBB)

The Posts and Bugs tabs use WysiBB, not SCEditor, and `$(ta).bbcode(text)` and `getHTML(text)` do not set new text (2026-11-04: a save silently kept the old post). Set the visible editor instead: `ta.parentElement.querySelector('.wysibb-body').innerHTML` to the text with `[b]` and `[url]` turned into tags and line breaks into `<br>`, set `ta.value` too, check `$(ta).data('wbb').getBBCode()` equals the text, then click the form's submit button. Read the post back after a fresh load. A file's Nexus changelog is edited at the mod's edit/files page, the row's More actions, Edit changelog.
