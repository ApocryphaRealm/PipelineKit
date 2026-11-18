---
name: amf-menu-port
description: Giving a Skyrim SKSE mod a settings page inside the Apocrypha Menu Framework (AMF, our SKSE Menu Framework-compatible menu) - porting a mod's settings from an INI, FLICK, SkyUI MCM / MCM Helper, or PrismaUI to an AMF/SMF page in C++, or building the settings page of a new mod of ours. Covers the vendored header and export probing, the settings model, toggles, precise sliders, keybinds, the eleven languages, the scrutiny checkpoints and the stripped-path build flags. Use it whenever a mod's menu, settings page, MCM or config window is being ported, converted, rebuilt or added - "put X's settings in AMF", "convert X's MCM", "make an AMF page for X" - even if the word "port" is never used.
---

# Porting a mod's settings into AMF

The full procedure is this skill's **`references\SMF-CONVERSION-PLAYBOOK.md`** (`<ROOT>\.MD\skills\amf-menu-port\references\SMF-CONVERSION-PLAYBOOK.md`) - read it before starting; it was
distilled from real ports and every section exists because something went wrong without it. It was written while the
target was SKSE Menu Framework. AMF answers the same API (a mod registers with it exactly as an SMF consumer), so
the playbook applies unchanged. Where this skill and the playbook differ, the later house rules below win.

Code rules: `<ROOT>\.MD\rules\04-code-standards.md` (14, 16, 17, 28, 31, 32, 64, 66, 68). Build rules:
`rules\02-build-toolchain.md`. Grep the logic-library index for `cpp`, `ui`, `settings`, `crash` before writing code.

## Decide the shape first

- **Our own mod (Nexus):** settings live as a mod menu inside AMF, drawn with AMF's exported ImGui functions in AMF's
  context and theme. Never a second ImGui window of the mod's own, even if the mod draws gameplay UI in its own context.
- **A feature that needs AMF's renderer, present hook or settings surface anyway:** build it into AMF as a setting,
  not as a new plugin.
- **Another author's MCM mod in Njordlinger:** these AMF conversions are list-only - they ship with Njordlinger, not
  on Nexus, so the Nexus release pipeline doesn't apply. AMF's own converted-menus feature (MCM / FLICK / Prisma pages)
  may already cover it - check before writing a port.
- Check the licence before reading or changing someone else's code. Prefer the permissive base; rebuild copyleft
  features from descriptions (rule 62).
- If there is nothing meaningful to configure, say so instead of porting a stub.

## Which case (playbook Part 2)

| Old settings surface | Case | The work |
|---|---|---|
| INI only / no menu | A | Purely additive - the page edits the same file the mod reads. |
| Linked C++ framework (FLICK NG...) | B | Remove the header, includes and build dependency; README says it is no longer required. |
| SkyUI MCM / MCM Helper (Papyrus) | B2 | Remove the `.psc`/`.pex`, `MCM\Config` JSON and quest wiring; check native-function bindings explicitly. |
| PrismaUI / PMCM web view | C | Rewrite the bridge as ImGui calls; keep the same keys, defaults and ranges. Scope to the settings page. |

## The core, in order (playbook Part 1)

1. **Vendor the header** (`SKSEMenuFramework.h`) unmodified into `include/`; no link-time dependency.
2. **`HasRequiredExports()`** probes the exact exported name of every widget used - varargs widgets resolve to the
   `...V` names (`igTextDisabledV`, not `igTextDisabled`). The header does not null-check, so a missing export is a
   jump to address zero. If anything is missing, log it and keep the mod working without the menu.
3. **Settings model**: `Init` / `Save` (back to the original store) / `Reload` / `RestoreDefaults` (in memory, from the
   defaults captured at Init). Register settings through a checked helper - a type/prefix mismatch gives a null-named
   setting that crashes at load. Compiled defaults must match the shipped INI (rule 16). Never use
   `WritePrivateProfileString` - under MO2's VFS it reports success and writes nothing.
4. **The page**: register on `kPostPostLoad`; mirror the existing settings 1:1 before improving anything; changes
   **apply live**, not only after Save.
   - Booleans are on/off switches (`ImGuiMCP::Toggle` from the vendored `utils/Toggle.h`), never `Checkbox`.
     Groups of related toggles sit in a three-wide table.
   - Every slider is precise: one unit of the shown digit per nudge (rule 68).
   - Keybinds: defaults from `.MD\DEFAULT-KEYS.md`, unique across our mods; never take AMF's reserved keys
     (`SMF_GetReservedKeyCodes`, asked at each capture); one key, one action; keyboard and gamepad rows.
   - Mod keys do not fire while the AMF menu is open. Controller Y opens the same context menu as a right-click.
     The D-pad never switches tabs.
   - Every string of ours goes through `TR()` into all eleven language files (`translations-check.py`,
     `translation-coverage.py`). Text read from another author's settings data stays in their language.
5. **Logging and null checks together** everywhere (rule 14); log level ships at INFO; retry lookups that can fail
   because something is not loaded yet (rule 17).
6. **A TestBench driving tool** so the page can be pushed in game without a human (rule 64), and a state tool from the
   first version (rule 31).
7. **Ask the object** (playbook section 7): log once what each foreign object really provides (`GetProcAddress`,
   `HasMember`) instead of trusting the source that appears to declare it.

## Build flags from the first build (playbook Part 4)

`/Zi`, `/DEBUG:FULL /OPT:REF /OPT:ICF`, `/d1trimfile:<project dir>` and `/PDBALTPATH:%_PDB%` on the target, the vcpkg
residue cleared (two steps), then the four artefact checks: no "Claude output" bytes in the DLL, bare PDB filename in
the debug record, DLL/PDB pairing passes, new version and hash.

## Before calling a version done

Run the playbook's Part 3 checkpoints with a fresh reviewer against the source (type-prefix safety, old-framework
residue, live-apply completeness, graceful degradation without AMF, README requirements = reality), report each as
pass/fail with file and line. Then package and version through the `mod-release` skill, test through `in-game-test`,
and update the playbook itself when the port taught something it got wrong or missed.
