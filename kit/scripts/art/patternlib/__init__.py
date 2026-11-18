"""patternlib - one deterministic pattern library for the engraving on our weapons and armour (the owner, 2026-11-16
18:31: "we need a reliable way to generate art patterns reliably").

Every pattern is VECTOR first (centre lines + widths + crossings with an over and an under), then rasterised to
height / normal / masks at any pixel density; seeded and deterministic (the same inputs give the same bytes); and judged
by validators that refuse with a message (validate.py). Modules:

  geom       polygons, true offsets (insets), the Region signed distance, Hermite chains
  model      Strand, Crossing, Pattern (+ JSON and SVG)
  crossings  find crossings, alternating over-under by 2-colouring
  knot       knotwork and the weave by the tile / mirror-curve method (Mercat, Cromwell, Gerdes), fitted to any region
  braid      n-strand braids along a curve (perimeter loops, straight / tapering runs)
  symbols    triquetra (+ ring), valknut, Odin's horns - exact constructions
  runes      a rune band from our own Elder Futhark stroke font
  damascus   the forge-layer fields (raindrop = the chosen look) absorbed from the damascus study
  fit        face outline + spec -> inset, frame, braid, medallion, field; validated, fixed candidate order
  raster     Frame, render (height / masks), normals, a lit preview
  measure    the engraving-layout gate's fragment and weave-scale counting (absorbed from the original's design-workspace measure)
  validate   the validators and their refusal messages
  cli        `resolve.py run patternlib-cli <spec.json> <out dir>` - generate, validate, write; exit 2 when refused
  catalogue  PATTERNS-sheet.png: every type at three densities with the validator verdict under each
"""
VERSION = "1.0.0"
