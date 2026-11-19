# Banner design rules - the two sizes are NOT the same design

Recorded 2026-08-27 from the author, ahead of a screenshot pass: *"continue the logic of having the
smaller banner be black with the white rim around it - we're not altering that."*

## The small banner (1300x372) - MINIMAL, and it stays that way

**Do not put screenshots or game imagery in this one.** It is deliberately austere:

```css
background: #050505;          /* near-black, NOT pure #000000 - keep this exact value */
border: 2px solid #f5f2e9;    /* the warm off-white rim */
```

That is the whole design: a black field and a thin off-white rim - **BLANK, no words**. It is the page's header
backdrop: Nexus draws the mod's title over it, so a name in the image doubles the title. (The owner, 2026-11-11, on
Truly Nordic: "the small banner that functions as a backdrop has words on it when it should be blank" - this line
used to say "and the mod's name", which is how the mistake was made.) It reads at a glance and survives being
scaled down, which a screenshot at 3.5:1 does not.

**This is settled and not up for redesign.** If a future session is tempted to "improve" it by
adding a screenshot, a gradient, or a glow - don't. The instruction was explicit.

Note the background is `#050505`, one step off true black. The framework rebuild's theme uses true
`#000000` (see `PLANNED-MODS.md`). That difference is deliberate here and should be left alone;
matching them is not an improvement anyone asked for.

## Oblivion Remastered mods: paper white and brown, both sizes - design decision, 2026-09-29

The owner: *"I want all of the Oblivion Remastered billboards and banners to be in the paper map white vanilla
color with brown letters ... Including the small blank banner will be the new vanilla white color."*

For a mod on Nexus's Oblivion Remastered section the black-and-white pairing above is replaced, in BOTH sizes:

```css
background: #e6dfd1;          /* the game's paper-map white, sampled from its own paper textures */
color: #4a3222;               /* brown letters */
border: 2px solid #6b4e36;    /* the brown hairline (3px on the large banner, as before) */
```

Everything else stands: the small banner stays empty, the large one carries the screenshots, the layouts do not
change. Start from `_banner-template-1920x1080-oblivion.html` / `_banner-template-1300x372-oblivion.html`. Skyrim
mods are untouched by this.

**Every generated picture on an Oblivion Remastered page matches the banner background** (the owner, 2026-10-11:
*"the pictures generated for Oblivion specifically need to match the banner color"*). Header cards, feature cards,
the at-a-glance strip, close-up mats and any other rendered page image use `#e6dfd1` as their background with the
brown text and hairline above - never the black `#050505` of the Skyrim cards. Screenshots themselves are untouched;
only what we draw around them follows the paper white.

## NORSE: Oath of Blood mods: charcoal and silver sampled from the game's own UI - design decision, 2026-11-18

The owner chose (2026-11-18) "colours sampled from Norse's own UI" over our Skyrim black-and-white, then approved the
sample ("use it for all 22"). Sampled from the game's Options screen and title screen (4. plans\norse-realtime-combat-20261116\distro-notes\ui-shots\):

```css
background: #141617;          /* smoky charcoal - the Options screen's background */
color: #e5e5e6;               /* soft white - the Options row labels */
border: 3px solid #a09995;    /* silver - the NORSE logo (2px on the small banner) */
/* #383838 the row separators; #a36849 ember rust (title-screen sky and shield) - accent hairlines and the version pill only */
```

Type: a classic serif like the game's menus - EB Garamond (Google Fonts). The small banner stays BLANK (charcoal field,
silver rim). The large banner carries an in-game shot in a silver-ruled frame. Every drawn page card on a Norse page uses
the same charcoal and silver. Start from `_banner-template-1920x1080-norse.html` / `_banner-template-1300x372-norse.html`;
the first set is `Norse - Tagger\`.

## The large banner (1920x1080) - where screenshots go

Game imagery belongs here and only here. This is the format with the room for it.

## Why the split matters

**1300x372 is a 3.5:1 letterbox strip.** Almost any screenshot cropped that hard loses its subject:
a minimap sits in a screen corner, and a corner is exactly what a centre-crop to 3.5:1 throws away.
The small banner is minimal because minimal is what works at that ratio, not because nobody got
round to adding art.

The palette is shared with the rest of the project - `#f5f2e9` on black is the same pairing the
Untarnished UI reskins and the framework rebuild use - so the two banners still read as one family
even though only one of them carries imagery.

---

## Naming the two looks: "Vanilla Style" vs Untarnished UI

design decision, 2026-08-27: *"when you build the banners, I want the non untarnished ui ver to be called
vanilla style."*

**Use "Vanilla Style", capitalised, as a proper label.** Not "default", not "plain", not "stock",
not "no reskin", not "unmodded".

This is not specific to one mod. Several mods here ship an Untarnished UI variant alongside a
normal one - Dragon's Eye Minimap (via the separate Frame Reskin Preview add-on), Compass
Navigation Overhaul, and Local Map Upgrade. The same pairing should read identically on every page.

**Why the wording matters.** "Vanilla" is the established Skyrim-modding term for the unmodified
game, so "Vanilla Style" needs no explanation to the audience. The alternatives each fail in a
specific way: **"default" is ambiguous** - the game's default, or the mod's? - and **"no reskin"
defines the thing by what it lacks**, which frames it as the lesser option when it is simply the
other one. A user who prefers the vanilla frame should not read the label as a downgrade.

### The trap that produced this rule

Every screenshot in the project had `+Dragon's Eye Minimap - Frame Reskin Preview 1.0.4` enabled
(line 2 of the Apostasy modlist), so the **main mod's** banners were showing an optional add-on's
appearance. the author caught it; nothing in the images themselves gave it away.

**Before building a banner from any capture, check whether a reskin was enabled when it was
taken.** `modlist.txt` is the only reliable answer - the two looks are close enough to pass
unnoticed side by side, and a wrong call here misrepresents a live Nexus page.

### Also settled here

The Frame Reskin ships **exactly one file** - `![asset path removed]` - overriding the main mod's
own copy. It is a pure art swap; the squared/round shape comes from `uShape`/`SetShape` in the main
mod's DLL. So **shape is never evidence of the reskin**, and a recolour can only be shown honestly
as a **before/after pair** with location, shape, anchor and time of day all held fixed.

---

## Full opacity only in banners - design decision, 2026-08-27

*"Disregard the screenshots with the reduced opacity. I don't think it looks as good."*

Banner plates use captures taken at **`fHUDOpacity` 1.0** only. The reduced-opacity captures are set
aside in `overwrite\Root\screenshots\_reduced-opacity-not-for-banners\` rather than deleted - the
feature works and the shots are the evidence of it, they just are not the marketing image.

**Which captures are which is decided from the log, not by eye.** The minimap logs
`Background opacity applied: fHUDOpacity <v> -> alpha <n>` and it only fires when the value
CHANGES, so a capture inherits whatever the last logged value was:

| Capture | Last logged opacity | Use |
|---|---|---|
| 08:00:51, 08:01:28, 08:01:46 | 1.0 (since 07:55:24) | yes |
| 08:02:17, 08:02:32 | 0.5 (08:02:10) | set aside |
| 08:03:41 | 1.0 (08:03:38) | yes |
| 08:04:00 | 0.5 (08:03:59) | set aside |

Judging opacity by eye on an already-dark HUD element is unreliable - the measured difference
between the pair was luminance 18.5 vs 24.5, real but easy to mistake for lighting. Read the log.

### Where ENB captures actually live

They appear in `Stock Game\screenshots\` DURING a session, but **MO2 relocates them to
`overwrite\Root\screenshots\` on exit**. A capture that seems to have vanished mid-analysis has
simply moved. Look in Overwrite first once the game has closed.

---

## The round frame is a MAIN-MOD feature banner, not a reskin banner - design decision, 2026-08-27

*"Move the 4-corners-with-circle-shapes banner to the main mod and rename it as a feature instead,
because it basically looks the same with or without the reskin - frame it as a feature example to
show that it has a circle shape mode."*

The reasoning to keep: **the reskin's visible change is ornament removal, and the round frame has
no ornament in either variant** - so a round-frame image demonstrates nothing about the reskin,
while it demonstrates a real main-mod feature (`uShape`). An image belongs on the page whose
product it shows.

Current banner inventory per page:

* **Dragon's Eye Minimap (main):** small (black/rim) + main 1920x1080 (Vanilla Style squared,
  ornamented, four corners) + `-feature-round` (round shape mode, four corners, framed as
  "Feature - Round Shape Mode").
* **Frame Reskin:** small (black/rim) + main 1920x1080 (squared no-ornament, four corners) -
  squared is the ONLY shape where the reskin is visible, so it is the only shape shown.

---

## STANDARD, settled - the Dragon's Eye Minimap banner set (design decision, 2026-08-27)

*"For this specific mod, just save this as the standard going forward unless I want to change it,
because this is the most correct we've been so far."*

The inventory in the section above IS the standard for Dragon's Eye Minimap and its Frame Reskin:
three banners on the main page (small / Vanilla Style squared four-corner / round-shape feature),
two on the reskin page (small / squared four-corner). This has the same status as the small
banner's black-with-rim design: **regenerate within this shape - new captures, updated version
pill, a different location - but never redesign it unless the author asks.** A future session tempted to
"improve" the layout, add more images, or move the round banner between pages: the current
arrangement was reached by correcting exactly those impulses, one at a time, with him.

## In-game pictures INSIDE the banners - design decision, 2026-08-30

The author: "make sure to take in-game pictures to crop inside the generated banners." The
HTML template is the FRAME; the content inside it is a real in-game screenshot of the mod
doing its thing, cropped to fit - not only CSS glyphs or drawn icons. ImGui menus need the
in-process capture (native screenshots are pre-overlay); Scaleform/HUD mods can use the
DevBench capture tool; desktop screen grabs are forbidden (one grabbed the browser once).
Embed the crop in the banner HTML (file ref or data URI), then rasterize with headless Edge.
The 1300x372 stays the empty-rim standard; this applies to the 1920x1080 feature banner and
any screenshot slots.

## Framed UI art in a banner: EXTRACT the art, do not redraw it and do not crop it - design decision, 2026-09-02

The author, twice, from two directions. On a hand-drawn border: "all you did was basically draw
lines in the shape of it instead of actually copying it." On a screen-cropped one: "would it not
be better to just recreate the art that went into creating the map border instead of cropping it
in and then just crop the mini map inside the frame." Then: "definitely record the method you
just used for future banners if they need it."

So when a banner has to show a framed or ornamented UI element - a minimap frame, a map border,
a panel with corner art - build the picture in TWO LAYERS instead of photographing it whole.

### Why a screen crop cannot work

Ornamented frames have corner pieces that overhang the frame's straight lines. A crop tight
enough to keep the game world out clips those corners; a crop loose enough to keep the corners
whole drags the scene in behind them. No rectangle gets both. This is not a matter of cropping
more carefully - it is geometry, and it will happen again on every ornamented frame.

### The method (worked on the Dragon's Eye Minimap main banner, 2026-09-02)

1. **Find where the art really lives.** Skyrim UI art is normally a shape inside a Scaleform
   `.swf` shipped in the mod's own `Interface/` tree. Do not settle for an SVG lying around the
   repo without checking what it is - the one in `swf/reskin/` looked right but was the reskin
   with the corners deliberately stripped.
2. **Export the shape as vector.** JPEXS FFDec is installed at `<HOME>\tools\ffdec`:
   `ffdec-cli -format shape:svg -export shape <outdir> <file.swf>`
   That writes every shape as SVG named by character id. Render candidates to find the right id
   (the squared minimap frame was 335, the round one 337).
3. **Keep the art, drop only what blocks the layer beneath.** These shapes usually carry a solid
   backing plate path plus the art path. Remove the plate, keep the art untouched - never
   simplify or redraw its geometry. Vector then scales to any banner size with complete corners.
4. **Capture the CONTENT separately** - the map, the page, whatever the frame surrounds - from a
   real in-game shot, cropped to the frame's INTERIOR only, with the mod at its shipped default
   look unless the banner is specifically advertising a non-default one.
5. **Layer them in the banner HTML**: content image absolutely positioned and inset by the
   frame's own inner-edge ratio, the frame SVG on top at 100%, both inside a box with a black
   background so any sub-pixel gap reads as plate rather than as a seam.

Result: complete corners, all four sides, no game world anywhere in the picture, and the frame
is genuinely the mod's art rather than a likeness of it.

The extracted asset is worth keeping beside the banner (`assets/minimap-frame.svg`) - it is also
the honest way to recolour a frame for a theme preview, as vector, instead of tinting a bitmap.

## Crop, then ENLARGE to the banner's full resolution - never shrink the whole frame (author, 2026-09-05)

The author, after the SMF-compatibility captures: *"the cropped area should be expanded to fit
the full resolution not the other way around so that it's still clear and legible."*

The rule: pick the region of the capture that carries the subject, crop to it, and scale that
crop UP to fill the banner at its full pixel size. Do not paste the whole its native resolution frame into a
1920x1080 banner and let it shrink - the text that was crisp in the capture becomes unreadable
at banner size, and unreadable text is the thing a mod-page visitor notices first. If the crop
has to be scaled up a lot, capture with the menu's own text scale raised and the window stretched
to the screen first (AMF: `fTextScale`, the window-fraction keys) so the source pixels are
already large; the SMF-compat shot in `Apocrypha Menu Framework\_photos-2026-09-04-smf-mods\`
was taken that way and reads at banner size without help.
