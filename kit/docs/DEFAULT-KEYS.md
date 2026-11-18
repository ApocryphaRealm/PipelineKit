# Default keys registry - every default binding our mods ship

<!-- DOC-VERSION: 1.1.7 | 2026-11-09 -->
*Doc v1.1.7, revised 2026-11-09 - Unbind Vanilla Controls 1.6.0: F7 and Back+Start held 1 s (input-mode lock toggle), L3 Auto-Move in Gameplay*








The owner, 2026-09-12: *"keep a running log of default keys that we issue on the mods we make so that
other mods that we make don't have the same hotkey ... they should just come packaged with separate
keys so they don't overlap"*.

**How to use it.** Before giving any mod a default key or button, read this table, pick a value not
issued on that device, add the row, THEN write it into the code, the shipped INI and the descriptor.
No two of our mods ship the same default on the same device. **The rule is per game** (2026-09-28): rows marked Oblivion Remastered may reuse a Skyrim key, since the two games never load each other's mods; within one game the rule is unchanged. A chord a default depends on is part of
its row. Rule 28's old "every mod on K and L" is superseded by this table (the two K/L rows below are
the ones that already shipped that way).

Keyboard values are DirectInput scan codes (decimal, hex in brackets). Gamepad values are the code
the mod stores: AMF/AUO store XInput masks; Wheeler stores 266 + button index (D-pad down = 267).

## Two runtime checks every mod with a bindable key ships (the owner, 2026-09-12)

*"list it as a standard feature on any mod that we make that has a bindable key or button to check
AMF reserved key and within the mod to make sure that two separate functions cannot be bound to the
same key"* - rule 28, second amendment. This table is the design-time half; these are the run-time half.

1. **AMF reserved keys.** Resolve `SMF_GetReservedKeyCodes(int32_t* buffer, uint32_t capacity) -> count`
   from the loaded framework module (GetProcAddress, null-checked). A capture that lands on a reported
   code is refused with a message on the row; a default or INI value that collides is left unbound with
   a warning in the log. Ask at every capture so the answer follows AMF's live configuration.
   Reference implementations: Dragon's Eye Minimap 1.5.3+ (`UI.cpp` FrameworkReportsReservedKeys),
   Wheeler - Refined 1.0.5 (`AMFLaunch.cpp` RefreshReservedKeys / ApplyReservedKeyPolicy).
   AMF 1.7.6 (2026-09-13) reports the LIVE `uToggleKey` first, then Tab, Esc, arrows, Enter; F1 is
   reserved only while it is the menu key. Proven with Wheeler 1.0.6 as the consumer.
2. **One key, one action.** A capture that lands on a code another action of the same mod holds on the
   same device is refused, naming the holder (Wheeler 1.0.5: `Page.cpp` FindOtherActionOnCode). No two
   shipped defaults of one mod share a key.

## Reserved

| Key | Reserved for | Why |
|---|---|---|
| F11 (87 / 0x57) | Apocrypha Menu Framework's menu | the owner, 2026-09-12: "that's the key to open and close AMF" |
| F1 (59 / 0x3B) | Apocrypha Menu Framework's shipped `uToggleKey` | the value in `ApocryphaMenuFramework.ini`; keep clear as well |
| F5, F9 | the game | quicksave / quickload |
| F12 | Steam | screenshot |
| F10 (68 / 0x44) | Immersive Equipment Displays (third-party) in Njordlinger | its UI key, moved off Backspace (0x0E) by the `test IED Key Override` mod on 2026-09-16 because Backspace is text editing in every AMF search box |

## Issued - keyboard

| Key | Mod | Setting | Issued | Note |
|---|---|---|---|---|
| K (37 / 0x25) | Dragon's Eye Minimap | `iHideKeyCode` | before 2026-09-12 | rule 28 era |
| L (38 / 0x26) | Dragon's Eye Minimap | `iZoomToggleKeyCode` | before 2026-09-12 | rule 28 era |
| K (37 / 0x25) | **Minimap Menu - Oblivion Remastered** | `[Controls] iHideKey` | 2026-09-29 (plan) | the owner, 2026-09-29: *"Let's just call it minimap menu. And we haven't even released CCM, so we can change its camera shoulder keys. Let's use K and L"*. Tap = hide / show; hold = pan while the hold-to-pan switch is on (DEM's scheme). Same key as Dragon's Eye Minimap is allowed (per game). K was CCM's shoulder swap from 2026-09-28 until this row |
| L (38 / 0x26) | **Minimap Menu - Oblivion Remastered** | `[Controls] iZoomToggleKey` | 2026-09-29 (plan) | tap = zoom in / out; as above. L was CCM's camera-style key until this row |
| [ (26 / 0x1A) | **Camera Configuration Menu (CCM) - Oblivion Remastered** | `[Keys] iShoulderSwapKey` | 2026-09-29 (CCM unreleased) | moved off K for Minimap Menu (the owner: "we haven't even released CCM, so we can change its camera shoulder keys"). Chosen by Claude; confirmed unbound in every IMC_Game_* context on 2026-09-29 (Minimap Menu M0 probe 9 / CCM P15; K is free too, L only in the debug context) |
| ] (27 / 0x1B) | **Camera Configuration Menu (CCM) - Oblivion Remastered** | `[Keys] iCycleStyleKey` | 2026-09-29 (CCM unreleased) | moved off L; cycles the camera style; as above |
| Left Alt (56 / 0x38) | **Camera Configuration Menu (CCM) - Oblivion Remastered** | `[Keys] iLockOnKey` | 2026-10-01 (CCM 1.0.1, built) | CCM's own lock-on (the owner, 2026-09-30: CCM owns target lock-on). Left Alt is the owner's lock-on key and Ultimate Combat Redux's lock-on key too; that is allowed because UCR's lock-on ships off from 1.0.1 and CCM stands down when a player switches it back on. Rebindable on CCM's Camera page (press-to-bind) |
| Z (44 / 0x2C) | **Camera Configuration Menu (CCM) - Oblivion Remastered** | `[Keys] iPrevTargetKey` | 2026-10-01 (CCM 1.0.1, built) | the lock-on's previous target while locked - Ultimate Combat Redux's own keyboard default, carried over with its lock-on (the owner, 2026-10-01: "Literally just copy it over"); UCR's lock-on ships off. Rebindable on CCM's Camera page |
| X (45 / 0x2D) | **HUD Position Manager - Skyrim** | `[Immersive] iToggleKey` | 2026-10-04 (1.1, phase 3 build 2) | the HUD toggle (ImmersiveHUD's own default is X); inert unless `[Immersive] bEnabled=1`; controller `iToggleButton` ships unbound (0); bound on HPM's page with AMF's reserved keys refused |
| X (45 / 0x2D) | **Camera Configuration Menu (CCM) - Oblivion Remastered** | `[Keys] iNextTargetKey` | 2026-10-01 (CCM 1.0.1, built) | the lock-on's next target while locked; as above |
| G (34) | Wheeler - Refined (fork) | `InputBindings.MKB/toggleWheel` | inherited from upstream | opens the wheel |
| H (35) | Wheeler - Refined (fork) | `InputBindings.MKB/toggleEditHints` | inherited | |
| N (49) | Wheeler - Refined (fork) | `InputBindings.MKB/addWheel` | inherited | edit mode only |
| M (50) | Wheeler - Refined (fork) | `InputBindings.MKB/addEmptyEntry` | inherited | edit mode only |
| V (47) | Wheeler - Refined (fork) | `InputBindings.MKB/pickUpSlot` | 2026-09-17 (1.2.8) | edit mode only: pick the slot up, move, press again to drop. Not B: the owner's own profile has the wheel toggle on B |
| B (48 / 0x30) | Back Pocket For Controller | `[input] toggle_item_scan_code` | 2026-09-22 (1.0.0) | inherited from Back Pocket (forked, MIT); Inventory/Container/Barter/Gift menus only. The owner's own profile has the Wheeler toggle on B - in the Inventory both would act; noted, not changed |
| Tab (15) | Wheeler - Refined (fork) | `InputBindings.MKB/closeWheel` | inherited | |
| 4 (5) | Wheeler - Refined (fork) | `AmmoWheel ToggleKeyMKB` | inherited | |
| [ (26 / 0x1A) | **Camera Configuration Menu (CCM) - Witcher 3** | `[Keys] iShoulderSwapKey` | 2026-10-07 (1.0.0, unreleased) | the Oblivion CCM's shoulder key carried over (per-game rule). Unbound in the game: no IK_LeftBracket in the owner's input.settings (2026-10-07). Rebindable on CCM's Camera page; controller row ships unbound |
| ] (27 / 0x1B) | **Camera Configuration Menu (CCM) - Witcher 3** | `[Keys] iToggleKey` | 2026-10-07 (1.0.0, unreleased) | CCM on/off (W3 has no camera styles to cycle); no IK_RightBracket in the owner's input.settings; as above |
| . (52 / 0x34) | **Multi Companion - AMF page - Witcher 3** | `MultiCompanionAMF.MenuKey` (a list row; it rebinds Multi Companion Mod Remastered's own `OpenMCMMenu` action in input.settings) | 2026-10-15 (1.0.0, untested) | NOT issued fresh: the companion menu's key already in the owner's input.settings, adopted by the row (the mod ships Z, his Camera Lock). The list offers only keys unbound in every context of his input.settings on 2026-10-15 (`,` `;` `'` `/` `\` `-` `=` F2 F3 F4 F6 F7 F8 F10) plus Off; F1, F5, F9, F11, F12 left out. Controller: the mod's own hold-right-stick binding, not changed |
| T (20 / 0x14) | **Separate Swimming Controls** | `[Keys] iAscendKey` | 2026-11-03 (1.0.0, untested; moved from UVC 1.3.0's Swim Up) | hold to rise, IN WATER ONLY; the stock Wait key, which does nothing else while swimming and is left alone on land |
| Left Ctrl (29 / 0x1D) | **Separate Swimming Controls** | `[Keys] iDescendKey` | 2026-11-03 (1.0.0, untested) | hold to sink, IN WATER ONLY; the stock Sneak key, and Sneak does not sneak in water while this mod's bSwimVertical is on |
| Y (21 / 0x15) | **Separate Swimming Controls** | `[Keys] iDiveKey` | 2026-11-03 (1.0.0, untested) | dive: only with deep water just ahead or while swimming; anywhere else the key does nothing of ours |
| C (46 / 0x2E) | **World Map Selector for Controller** | `[Controls] MapMenuKey` | 2026-10-23 (1.0.0, untested) | opens the map chooser, WORLD MAP (MapMenu) ONLY - outside the map the press is left to the game. Free in the MapMenu section of the vanilla controlmap (keyboard there: Tab, Esc, P, E, L, J, WASD) and in Njordlinger's active controlmap; not issued to another of our Skyrim mods. The original mod's F10 is reserved (IED) |
| / (53 / 0x35) | **Map Marker List** | `[Keys] iToggleKey` | 2026-11-04 (1.0.0, untested) | world map only: opens and closes the panel; while open every key is the panel's search |
| F4 (62 / 0x3E) | **RaceMenu Mirrorwright** (was Likeness) | `[Controls] iSwitchKey` | 2026-11-06 (1.0.0, untested) | RACESEX MENU ONLY: switches between Likeness and RaceMenu's own interface; ignored while the console is open. The same key RaceMenu Atelier used for the same action, so players moving over keep their habit. Controller row ships unbound |
| ~~F10 (68 / 0x44)~~ RETIRED 1.1.0 | Wheeler - Refined (fork) | `Control.Wheel/SettingsPageKey` | 2026-09-12, retired 2026-09-13 | the settings live in AMF (its key, F1, opens them); the row stays as an OPTIONAL shortcut, unbound (0). F10 is free again |
| F7 (65 / 0x41) | **Unbind Vanilla Controls** - controller/keyboard lock toggle | `[InputLock] KeyboardToggle` | 2026-11-09 (1.6.0 open, untested) | flips the input-mode lock (on by default). Free in vanilla and in the owner's UVC lists; F8 is PGLite's menu key in Njordlinger, F10 IED, F11 AMF, F1 AMF menu, F4 Mirrorwright |

## Issued - gamepad

| Button | Mod | Setting | Issued | Note |
|---|---|---|---|---|
| L3 / left stick click (mask 0x0040) | **Apocrypha Menu Framework** (Skyrim) - the universal keyboard's open button | `[Input] iKeyboardOpenPad` | 2026-10-23 (2.3.0, untested) | GAME MENUS ONLY: in an item or spell list (Inventory, Container, Barter, Gift, Magic) it opens SkyUI's search box with the on-screen keyboard; in the map it opens the location finder. Not taken in gameplay or in AMF's own window (where L3 stays "favourite the highlighted mod"). Up on the first row does the same in the lists. Rebindable on AMF's Settings page (L3 / R3 / Back / None). The Phase 1 probe confirms SkyUI's item menus leave L3 free |
| Right trigger (code 0x000A) | **Separate Swimming Controls** | `[Keys] iAscendPad` | 2026-11-03 (1.0.0, untested) | the owner: R2 ascends. Hold to rise, IN WATER ONLY; on land RT keeps its layout's use |
| Left trigger (code 0x0009) | **Separate Swimming Controls** | `[Keys] iDescendPad` | 2026-11-03 (1.0.0, untested) | the owner: L2 descends. Hold to sink, IN WATER ONLY; on land LT keeps its layout's use |
| X button, Square (mask 0x4000) | **Separate Swimming Controls** | `[Keys] iDivePad` | 2026-11-03 (1.0.0, untested) | dive: only with deep water just ahead or while swimming; anywhere else it does its normal job; the owner put it on Square 2026-11-03, D-pad left is his stances |
| Y **hold** (mask 0x8000) | Back Pocket For Controller | fixed; `[General] fHoldSeconds` = 0.50 | 2026-09-22 (1.0.0) | the owner: hold Y on a favourited Inventory item to send it to Back Pocket, or on a pocketed item to take it out; a tap stays the vanilla Favourite and any other row passes Y through untouched, so no conflict with Favourite |
| Left bumper (mask 0x0100) | Dragon's Eye Minimap | `iPanHoldGamepadButton` | before 2026-09-12 | hold to pan |
| D-pad up (mask 0x0001) | **World Map Selector for Controller** | `[Controls] MapMenuButton` | 2026-10-23 (1.0.0, untested) | opens the map chooser, WORLD MAP (MapMenu) ONLY. The vanilla MapMenu gamepad column uses A, B (Cancel = Tween Menu), X, Y, Start, LT/RT and both sticks, never the D-pad; in Njordlinger, Unbind Vanilla Controls moves Tween Menu (so the map's Cancel) to Back and the zooms (Left/Right Attack) to LB/RB, which rules out Back, LB and RB. D-pad up is Simplest Horses' horse key in the owner's gameplay layout (row below; was Toggle POV until 2026-10-23) - a different context, no overlap |
| D-pad left (mask 0x0004) | **Map Marker List** | `[Keys] iTogglePad` | 2026-11-04 (1.0.0, untested) | world map only: opens and closes the panel |
| D-pad up (code 266) - **owner's Njordlinger Test layout, not a shipped default** | Simplest Horses (third-party) through Unbind Vanilla Controls' `[Functions]` row `Call Horse` -> `MCM\Settings\SimplestHorses.ini [Main] iHorse_hotkey` | the owner's live UVC INI (test UVC 1.1.3 folder) | 2026-10-23 (tested in game) | the owner, 2026-10-23: free the POV button "and instead use it for the horse button". Toggle POV is UNBOUND on the controller (UVC `[Unbound] Gameplay\|Toggle POV\|gamepad`). Tap = Simplest Horses' wait/follow (mounted: horse inventory); hold 0.7 s = call. Keyboard H no longer calls the horse (Simplest Horses keeps one key) |
| R3 (code 273) - **owner's Njordlinger Test layout, not a shipped default** | True Directional Movement (third-party) target lock | `MCM\Settings\TrueDirectionalMovement.ini` in the `test Camera Horse Settings` mod: `uTargetLockKey = 273`, `bTargetLockUsePOVSwitchGamepad = 0`, `bTargetLockUsePOVSwitchKeyboard = 1` | 2026-10-23 (tested in game) | R3 tap locks, tap again unlocks. TDM has ONE lock key, so middle mouse (258) no longer locks; on the keyboard a TAP of F (Toggle POV) locks instead, a hold of F keeps the POV switch. In dialogue, R3 is also Switch Camera During Dialogue's first/third toggle (Dialogue Menu only - no overlap with gameplay) |
| Start (mask 16 / 0x0010) | Apocrypha UI Overhaul | `uGamepadMenuButton` | before 2026-09-12 | off by default (`bGamepadMenuButton=0`) |
| Start (mask 16 / 0x0010) | Unbind Vanilla Controls | `[Bound]` line Gameplay, Pause, gamepad, Start | 2026-09-14 (1.0.5) | the owner: System Tab on the controller, Journal unbound there; takes vanilla Journal's Start. AUO's Start row above ships OFF - a player who switches AUO's gamepad menu button on gets both on Start |
| **D-pad down (Wheeler 267)** | Wheeler - Refined (fork) | `InputBindings.GamePad/toggleWheel`, chord `toggleWheelModifier = 0` | 2026-09-12 | the owner: default the controller toggle to D-pad down; SHIPPED in 1.0.5; from 1.0.6 HOLD opens the wheel and a TAP stays the game's D-pad (`DpadHoldToToggle`) |
| D-pad right (Wheeler 269) | Wheeler - Refined (fork) | `AmmoWheel ToggleKeyGamepad` | inherited, confirmed by the owner 2026-09-13 | SHIPPED everywhere in 1.1.0 (compiled default + reset buttons); Next/Previous Item share D-pad right/left legitimately - wheel-open-only vs wheel-closed-only, no overlap |
| R3 / right stick click (Wheeler 273) | Wheeler - Refined (fork) | `InputBindings.GamePad/pickUpSlot` | 2026-09-17 (1.2.8) | the owner: "click the slot with r3 and move it to the desired position then click to release"; edit mode only. Took R3 from `moveWheelForward`, which ships unbound on the controller from 1.2.8 (as does `moveWheelBack`, which collided with the L3 hints toggle) |
| (none - controller unbound) | **Minimap Menu - Oblivion Remastered** | `[Controls] iPanHoldGamepadButton` = 0, `bGamepadHideButton` = 0 | 2026-09-30 (1.0.0) | the owner, at the finalize: *"Actually, R3 is the target lock button, so don't map it to anything for now on controller."* R3 was the plan's default (2026-09-29). The controller's tap to hide / hold to pan ships unbound; any button can be bound on the page with its press-to-bind listener. R3 stays reserved for target lock in our Oblivion Remastered mods |
| R3 / right stick click (0x0080) | **Camera Configuration Menu (CCM) - Oblivion Remastered** | `[Keys] iLockOnButton` | 2026-10-01 (CCM 1.0.1, built) | the target-lock button R3 was reserved for (the owner, 2026-09-30: *"R3 is the target lock button"*) - CCM's own lock-on is that target lock. Rebindable on CCM's Camera page (press-to-bind) |
| R3 / right stick click (0x0080); right stick up / down while holding | **Apocrypha Menu Framework - Oblivion Remastered** | `[Bindings] sGrabMod`, `sGrabUp` / `sGrabDown` | 2026-10-02 (1.0.6, built) | the Skyrim framework's grab-and-move, same defaults. R3 is the target lock in gameplay, but the game takes no input while the menu is open - the owner: *"Obviously, you're not going to target lock while in the menu."* Rebindable on the Controls page |
| D-pad right, while a bow is held | **Improved Wheel Menu - Oblivion Remastered** (planned ammo wheel) | its Controls-page row (an Enhanced Input action of its own) | 2026-09-29 (plan) | the owner: "It would default to D-pad right while holding a bow" - the arrow wheel, a semi-circle on the right-hand edge, as Perfected Wheeler's ammo wheel (Wheeler's Skyrim D-pad right row above is per game, allowed). Only while a bow is held; the player rebinds it on the game's Controls page |
| Left stick right flick (Wheeler 285) | Perfected Wheeler (was Wheeler - Refined) | `InputBindings.GamePad/moveWheelForward` | 2026-09-17 (1.3.1) | the owner: "we can have the move wheel forward set to the left stick"; while the wheel is open the left stick is consumed (Left stick controls the wheel, on by default) and its four directions are buttons 282-285 (up, down, left, right). Edit mode only |
| Left stick left flick (Wheeler 284) | Perfected Wheeler (was Wheeler - Refined) | `InputBindings.GamePad/moveWheelBack` | 2026-09-17 (1.3.1) | as above; the pair had shipped unbound since 1.2.8 |
| (none - ships unbound) | Wheeler - Refined (fork) | `InputBindings.GamePad/moveEntryForward`, `moveEntryBack` | 2026-09-13 (1.0.9) | were D-pad up/down (266/267) and collided with the D-pad-down toggle; unbound, rebindable |
| (none - ships unbound) | Wheeler - Refined (fork) | `Control.Wheel/SettingsPageGamepadButton` | 2026-09-13 (1.0.7) | the settings page's gamepad row; every controller button has a vanilla gameplay meaning, and the page is also reachable from AMF's Mod Control Panel with a controller, so it ships unbound and is rebindable on the page |
| (none - ships unbound) | Wheeler - Refined (fork) | `Control.Wheel/SettingsPageGamepadButton` | 2026-09-13 (1.0.7) | the settings page's gamepad row; every controller button has a vanilla gameplay meaning, and the page is also reachable from AMF's Mod Control Panel with a controller, so it ships unbound and is rebindable on the page |
| (none - ships unbound, every device) | **Unbind Vanilla Controls** built-in rows: Call Horse (Simplest Horses, Press H to Horse), Dodge (TK Dodge RE/NG, TK Dodge RE Addon, TK Dodge AIO, DMCO), Power Attack (BFCO), Target Lock (True Directional Movement, Simple Lock-On) | `[Functions]` rows -> each mod's own setting (UVC CHANGELOG 1.2.0) | 2026-10-23 (1.2.0, untested) | no key is ISSUED: each row adopts the key its third-party mod already has and writes only what the player binds on the Controls page, so these rows can never collide with another of our defaults. The owner's own Njordlinger choices (D-pad up = Simplest Horses, R3 = TDM lock) stay personal settings, not shipped defaults |
| Back + Start **held together 1 s** (0x0020 + 0x0010) | **Unbind Vanilla Controls** - controller/keyboard lock toggle | `[InputLock] GamepadToggle`, `fGamepadToggleSeconds` | 2026-11-09 (1.6.0 open, untested) | a long press of the two; once it fires both buttons are swallowed until let go. Back and Start keep their own controls (Tween Menu / System Tab in the author's layout) for a normal press |
| L3 / left stick click (0x0040) - Gameplay | **Unbind Vanilla Controls** - Auto-Move | `[Bound]` Gameplay, Auto-Move, gamepad, LeftStick | 2026-11-09 (1.6.0 open, untested) | the owner: "I want it bound to left stick". Gameplay context only - AMF's L3 row above is game menus only. Applies once vanilla Sneak is off L3 (the owner's layout unbinds it) |

## Not yet inventoried

The scan that seeded this table read each repo's shipped INIs for `*Key*`/`*Button*` values. Mods
whose settings use other names (Local Map Upgrade, Compass Navigation Overhaul, Auto Draw, Potion of
Clarity, Character Progression Control, Custom Difficulty UI, SkyHUD Settings Menu, Souls to Perks,
Carryweight on Level Up, Lock Interaction Overhaul, Item Explorer, InputBench) still need their
defaults read from `Settings.h` and added. `pre-finalize-check.ps1`'s rule-28 check is the right
place to enforce this table once it is complete (open item in the to-do list).
