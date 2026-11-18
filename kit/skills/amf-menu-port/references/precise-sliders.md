# Precise sliders - why ImGui steps wrongly, and the wrapper that fixes it

Moved here from rule 68 on 2026-10-12, when the rule was shrunk to the gate that enforces it (gate row
`sliders-are-precise`). The rule itself: a keyboard or controller nudge on any slider in any of our mods moves the value
by exactly one unit of the last digit the slider shows.

## The behaviour wanted

One nudge moves 1 for a whole number, 0.1 for one decimal, 0.01 for two. A mouse drag and a typed number are left as
they are. Holding the direction repeats the nudge.

## Why ImGui gets it wrong on its own

Dear ImGui's `SliderBehaviorT` moves a keyboard or gamepad nudge by 1% of the slider's RANGE whenever the format shows
decimals, and also for a whole-number format whose range is wider than 100. So a -150..150 slider stepped 3 per press
(Camera Configuration Menu's over-the-shoulder slider, 2026-09-29), and a 0.25..8.00 slider stepped 0.08.

## The shape

`include/PreciseSlider.h` (first in Minimap Menu and Camera Configuration Menu, 2026-09-29) is the reference:
`precise::SliderFloat` draws ImGui's own slider, and when the change came from a nudge it replaces the change with one
step in the same direction. It tells a nudge apart by the active-id source (keyboard or gamepad), and it leaves the value
alone while the slider's number is being typed in.

1. Copy the header into the mod and include it on the page.
2. Replace every `ImGui::SliderFloat(` / `SliderInt(` with `precise::SliderFloat(` / `precise::SliderInt(`.
3. A slider whose format changes with its value (CCM's "the game's" sliders) steps by the precision of the format it
   draws with.
4. A mod built on SKSE Menu Framework's `ImGuiMCP` wrapper needs the same wrapper written over its own
   `ImGuiMCP::SliderFloat`.

## When

Not as a sweep: each mod changes over the next time it is updated for any reason. The package gate fails a package whose
page source still calls a plain slider, so the update that touches a mod is the one that converts it; a package built
before the rule is not re-gated until it is rebuilt. A `//` comment line naming a slider call is not counted, and the
vendored `cimgui.cpp` binding is exempt.
