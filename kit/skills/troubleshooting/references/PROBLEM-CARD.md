# The problem card - every task starts as an equation

Rule 56 (amended 2026-11-16), logic 20. The owner, 2026-11-16 18:12: *"define the variables that take part in the
equation, define the relationships between the variables and how they interact within the equation, and then
produce the output for the equation. And it seems like we could standardize that somehow."* Approved 18:17.

Write it before any non-trivial fix, build or design task. A one-line fix whose cause you watched happen needs none.

```
resolve.py run problem-card new --task "<title>" [--area <topic>]     # skeleton in .MD\problem-cards\<date>-<slug>.md
resolve.py run problem-card check "<card>"                            # exit 0 PASS, exit 3 REFUSED
resolve.py run problem-card assumptions "<card>"                      # the list to attack first
```

`falsification-log.ps1 -Action open` refuses without `-Card "<card>"` that passes `check`.

## The five parts

| Part | What goes in it | What `check` refuses |
|---|---|---|
| **INPUTS** | each variable, one line each, with `source:` naming where its TRUE value is read: the game skeleton, not the bone guess; the shipped file, not the work folder; the live Nexus page, not the manifest | an input line with no `source:` or an empty one |
| **RELATIONSHIPS** | how the inputs constrain each other - what depends on what, what must equal what, which rule groups or orders them | an empty section |
| **OUTPUT** | what we want, said so it can be compared with the CHECK | an empty section |
| **CHECK** | what proves the output right - mechanical where possible: a gate, a hash comparison, a render, an in-game observation with an EXPECTED result | an empty section |
| **ASSUMPTIONS** | everything not yet verified. This is where bugs hide, so it is attacked FIRST: the hypothesis is usually one assumption taken as true, `-Kills` is the observation that would show it false, the other assumptions are the `-Rivals` | an empty section, or "none" with no reason after it |

`check` also refuses any `<fill: ...>` placeholder left from the skeleton, and a missing section heading.

When an assumption is verified, move it into INPUTS with its source - that is the card being solved.

## Limits

- **Design taste.** The owner's eye is the final term of any visual equation; option sheets exist so he can supply
  it. Put "the owner picks from the sheet" in CHECK rather than pretending a metric decides.
- **Unknown unknowns.** A card can only list what someone thought of. Testing and falsification flush the rest
  out; when one turns up, add it to the card and to the past-mistakes library.

## Template

```
# Problem card: <title>

## INPUTS
- <variable> - source: <where its true value is read from>

## RELATIONSHIPS
- <how the inputs constrain each other>

## OUTPUT
<what we want>

## CHECK
<what proves it - mechanical where possible>

## ASSUMPTIONS
- <what is not yet verified>
```

## Worked example 1 - the bracers placement (own-armour exercise, 2026-11-16): a misdefined input

The card below is the one that should have been written first (a reconstruction for teaching).
What happened: the bracers were placed from the NPC Hand bone's head, taken to be where the hand starts. The
visible hand starts further up the forearm - the hands mesh's wrist cuff reaches into it - so the plate's edge sat
in the wrong place and 4 hand vertices came through it at rest. The input "where the hand starts" was defined from
the wrong source.

```
# Problem card: bracers - where the plate ends at the wrist

## INPUTS
- where the visible hand starts - source: the hands mesh's wrist-cuff vertices (the vanilla 1stperson/3rd-person
  hands NIF the player wears), NOT the NPC Hand bone's head
- forearm bone positions and length - source: the game's [asset name removed] (NPC R Forearm -> NPC R Hand)
- the _0 and _1 forearm surfaces - source: the body meshes at weight 0 and 100 in the shipped body
- the clearance margin - source: the owner's sheet choice for this exercise

## RELATIONSHIPS
- the plate's lower edge = the cuff's top + the margin, along the forearm axis
- the plate must clear the body surface at both weights; _0 and _1 must share topology (vertex order, triangles)
- the plate follows the forearm bone's weighting, so its edge moves with the cuff, not with the hand bone

## OUTPUT
Bracers whose edge meets the visible hand without overlap, at _0 and _1, at rest and at the bend.

## CHECK
- the clipping check: 0 hand-mesh vertices inside the plate at rest, at both weights
- the _0/_1 index arrays are byte-identical
- in game: a bare-arm frame and a clothed frame (free camera toggled around the equip change) show the edge at
  the cuff

## ASSUMPTIONS
- the NPC Hand bone's head is where the visible hand starts   <- the one that was wrong; attacked first, it dies
  as soon as the cuff vertices are read
- the _1 body is the widest forearm case
- no worn clothing draws over the forearm in the test (sleeves hide forearm armour)
```

## Worked example 2 - the Skyforged swords that did not show (2026-11-16): an unwritten relationship

What happened: the Skyforged swords were hidden in Mod Explorer (ModEx). ModEx groups a form under the plugin that
DEFINES it, so a form whose defining plugin is not the one being browsed does not show under it. Nobody had written
that relationship down, so the swords were looked for in the wrong group. The card below is written the way it
should have been before the search (a reconstruction, not the record of that session).

```
# Problem card: Skyforged swords absent from ModEx's Truly Nordic list

## INPUTS
- the sword records our plugin ships and their FormIDs - source: the shipped .esp in the finalized package, read
  with the plugin reader (not the work folder's copy)
- which plugin DEFINES each of those FormIDs - source: the FormID's master index in the shipped .esp's header
- how ModEx groups forms - source: ModEx's own source / behaviour at the installed version
- what the running game has loaded - source: the live load order (plugins.txt of the profile that ran)

## RELATIONSHIPS
- ModEx lists a form under its DEFINING plugin (the FormID's master index), not under a plugin that edits it
- so a form defined in another plugin appears under that plugin, not under ours
- a NEW record (our plugin's own index) appears under our plugin

## OUTPUT
Know where each Skyforged sword appears in ModEx, and whether any is truly missing from the game.

## CHECK
- for each sword FormID: its master index -> the plugin ModEx should list it under; then look there
- in game: `help "<sword name>"` returns the form; spawning it shows the mesh

## ASSUMPTIONS
- ModEx lists a mod's items under that mod's plugin   <- the unwritten relationship; false for a form another
  plugin defines
- the shipped .esp is the one that loaded (check the profile's plugins.txt)
- the swords are defined in the plugin being browsed
```

The other two mistakes of that day fit the same shape: nexus-files.json "replaces" left null was a **missing
input** (the update had no file id to supersede), and package-render's output depending only on the NIF and DDS
hashes was a **known relationship nobody applied** (an unchanged mesh set could reuse its last render instead of
holding a release for hours).
