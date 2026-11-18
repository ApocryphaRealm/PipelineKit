# Rules part 02 - Build toolchain

<!-- RULES-PART: 02 | rules: 4,5,43,44,45 -->
*One of the seven parts of the project rules. The rules version is stamped in `CLAUDE.md`, which*
*also carries the index. Load this part when working in stages 5-6 (building a mod) and any dependency or compiler question.*

Reproducible builds, dependencies, and what a shipped binary may contain.

**Every rule here states its complete current policy on its own.** A change is folded into the
rule it changes with a dated `> **Amended YYYY-MM-DD**` note at the top of that rule - never
appended elsewhere, never written as a new rule that corrects an old one. Rule numbers are
identifiers: they are never renumbered or reused, and an absorbed rule leaves a stub under its number.

Rules in this part: 4, 5, 43, 44, 45.

---

## 4. Build scripts discover the toolchain; they never hardcode paths

Asked for explicitly, for streamlining and compatibility.

- `find-msvc.bat` locates Visual Studio with `vswhere.exe`, calls that install's
  `vcvars64.bat`, and prepends the CMake and Ninja that ship with Visual Studio to `PATH`.
  It deliberately does not use `setlocal`, because the caller needs the environment it
  sets up.
- `configure.bat` / `build.bat` call that helper and then only run the build.
- Installation-specific values come from environment variables — `VCPKG_ROOT` for a
  CMake/vcpkg project, `XMAKE` (falling back to `xmake` on `PATH`) for an xmake project —
  and the script fails with a clear message when a required one is unset.

These scripts are committed to public repositories, so a hardcoded `C:\Users\<name>\...`
would publish his home path.

---

## 5. Builds must be reproducible by anyone, from a persistent environment

> **Amended 2026-10-13 (the owner):** *"when building or altering mods for the Witcher 3, you should use Redkit when
> needed."* A Witcher 3 mod's assets - textures, icons, caches, bundles, DLC content and script compiles - are built with
> the official toolchain, The Witcher 3 REDkit (`D:\Steam Library\steamapps\common\The Witcher 3 REDkit`: `wcc_lite`
> cook and `buildcache`) for the current game patch, not with third-party packers alone. Assets reused from an older mod
> are re-cooked with it, because a cache or bundle cooked for an earlier patch can load wrong or not at all on the
> current one. REDkit is installed through Steam, so anyone can rebuild the same way.

Never leave a build depending on a tool unpacked into a session scratchpad directory. That
path disappears when the session ends, so it breaks immediately for him and was never
reproducible for anyone else.

- Install tooling somewhere durable — `<HOME>\tools\<tool>` — and add it to the
  **user** `PATH`, which needs no admin rights.
- Prefer a portable archive over an installer that demands elevation. The GitHub CLI MSI
  failed with error 1603 under winget for exactly this reason; the portable zip worked.
- Environment changes only reach **new** terminals. Say so rather than assuming.
- After genericising any script, **rebuild using only the persistent environment**, with no
  inline overrides, instead of assuming the discovery logic found the same toolchain.
- Document how to obtain the toolchain in the repo, so someone starting from nothing can
  build it.

---

## 43. Ship the `.pdb` with every build, beside its DLL

> **Amended 2026-10-12:** made a gate and shrunk to it (the owner: *"pdb is required"*); the full earlier text, with the
> retired split "Debug Symbols" download, is in `rules-archive\`.

The owner, 2026-08-26: *"add the PDBs from now on."*

**Every shipped DLL has its PDB beside it, inside the one package, at every stage: gate row `every-dll-ships-its-pdb`
(role `gate-rules`) refuses a package without it (a third-party proxy loader such as `dinput8.dll` is excluded by
name), and `resolve.py run package-mod` refuses a PDB it cannot prove was built with that DLL.** Why: Crash Logger reads
a PDB beside the DLL to turn a crash address into our function and line - without one a player's report is a raw
offset, and a mismatched one is worse than none. A PDB carries build paths, so gate row
`shipped-files-carry-no-user-folder` keeps the user folder out of it.

---

---

## 44. An AE-only dependency is not automatically a blocker - we can port it ourselves

The owner, 2026-08-26, about Dynamic String Distributor: *"DSD can be recompiled or converted to be
compatible with the older game version by us."*

The dual-runtime requirement (SE 1.5.97 and AE 1.6.1170, both instances) has until now been applied as a filter - a
dependency without a 1.5.97 build disqualified whatever wanted to use it. **That was too
strict.** Where a dependency is open source, recompiling or porting it to 1.5.97 is work this
project may simply do, and it should be weighed as an option rather than treated as out of
bounds.

**What makes a port cheap or expensive, and it is worth checking before promising anything:**

- **CommonLibSSE-NG based?** Then it is usually close to a rebuild - `REL::Relocation` and
  Address Library resolve per running version, so a build with SE enabled often just works.
- **Raw offsets or hardcoded addresses?** Much worse. Every address needs a 1.5.97 equivalent
  found by hand, and a wrong one is a crash rather than a compile error.
- **Its licence.** A port is a derivative work. Check the actual `LICENSE` in the upstream repo,
  not the Nexus permissions blurb - and remember they can differ (SMF is the standing example:
  the installed DLL's `LICENSE.md` is All Rights Reserved while the repo source is LGPL-2.1). A copyleft licence does
  not prevent the port; it governs how the result may be distributed and credited.

**Do not assume a dependency lacks SE support - verify from its Nexus files listing.**

**DSD specifically: CHECKED, and no port is needed.** Verified 2026-08-26 - the Nexus page states
"SE - 1.5.97" verbatim, DSD 1.4.3 is logged running against `Game version: 1-5-97-0` in the
Apostasy instance, and **one byte-identical DLL serves both instances** (no archive was ever
runtime-tagged). It is GPL-3.0, CommonLibSSE-NG based, and uses Address Library IDs throughout -
so had a port been needed it would have been the cheap kind. The rule above stands as the general
principle; this particular instance of it resolved to "already supported."

**If a mod ever does need building from source, check which branch the author actually maintains** - the default branch's tip may not be the one that works on every game version.

---

---

## 45. Never ship the build machine's absolute paths inside a DLL

> **Amended 2026-10-12 (build environment):** the fix now lives ONCE, in the shared build environment
> (`.MD\scripts\build-env\`), not in each mod: TEMP / TMP and xmake's folders outside the user profile, and a vcpkg
> overlay triplet that compiles every port trimmed. The relocation-and-recompile of CommonLibSSE-NG that was deferred
> to auto sort mode is retired - a changed triplet already forces vcpkg to recompile (measured on AMF 2.1.9: every
> dependency rebuilt from source, 265 s for the SE/AE line and 319 s for the 1.7 line, configure plus build).
>
> **Amended 2026-10-12:** two gate rows enforce this for every game (the owner: "turn it into a gate"):
> `shipped-dll-carries-no-project-root` refuses the project root in any shipped DLL or EXE (it replaced the
> Oblivion-only row), and `shipped-files-carry-no-user-folder` refuses a `Users\\<name>\\` path in ANY shipped file -
> the 2026-10-12 scan found the user folder in every shipped PDB (the linker's temp file under TEMP, and xmake's temp
> and package cache), though no DLL. Every mod's next package fails these rows until its build is fixed; that package
> is the conversion point.

The owner, 2026-08-27: *"also strip the embedded build paths"*, and *"from now on, all mods must ship with stripped
pathing"* - not per-mod discretion: a mod is not shippable with build paths in it.

**What was happening:** a released DLL contained about **thirty copies of
`<ROOT>\6. current wip mods\<Mod>\...`** - the full path of every source file, plus
the PDB path - and every PDB carried the Windows user folder. Four separate causes:

- **Our source paths.** `SKSE::log` captures `std::source_location`, so every logging call site
  embeds `__FILE__`, which is the absolute path the compiler was handed.
- **The PDB path.** The linker records the PDB's full path in the DLL's debug directory.
- **CommonLibSSE-NG's own source paths**, compiled by vcpkg inside the repo's build tree
  (`<repo>\build\<preset>\vcpkg_installed\vcpkg\blds\commonlibsse-ng\src\...`) and baked into the static library.
- **The user folder in the PDB**: the linker writes the path of its `lnk{GUID}.tmp` file under `%TEMP%` into every
  PDB; xmake adds its temp and package-cache paths, which default to the user profile.

**Why it matters, in order:** it leaks the build tree's layout and the owner's user name to every downloader for no
benefit; long absolute developer paths in an **unsigned** DLL are a plausible contributor to antivirus heuristic
scoring (the `Trojan:Win32/Wacatac.C!ml` false positive, `.MD` bug reports); and in this project's case the paths
contain the literal string `Claude output`, which reads as suspicious to anyone inspecting strings.

### Our own sources and the PDB record - stated on the target in every mod

```cmake
file(TO_NATIVE_PATH "${CMAKE_CURRENT_SOURCE_DIR}" PROJECT_NATIVE_DIR)
target_compile_options(${PROJECT_NAME} PRIVATE "/d1trimfile:${PROJECT_NATIVE_DIR}")
target_link_options(${PROJECT_NAME} PRIVATE /PDBALTPATH:%_PDB%)
```

- **`/PDBALTPATH:%_PDB%`** records only the PDB's *filename*. Safe because Crash Logger resolves symbols from the PDB
  **beside the DLL**, which is how this project ships them (the PDB in `SKSE\Plugins\` beside the DLL).
- **`/d1trimfile:`** strips a prefix from `__FILE__` at compile time. It may be given more than once (the first
  matching prefix wins) and matching ignores case and slash direction (scratch compile, 2026-10-12). The prefix must
  have **no trailing separator** - a trailing backslash before the closing quote escapes that quote.
- **xmake** spells it as a TABLE: `add_cxflags({"/d1trimfile:$(projectdir)"}, {force = true, expand = false})` and
  `add_shflags("/PDBALTPATH:%_PDB%", {force = true})` - a bare or inner-quoted string compiles and trims nothing
  (gate row `xmake-d1trimfile-reaches-cl-intact`). **MSBuild:** `<AdditionalOptions>` on `ClCompile` (strip
  `$(ProjectDir)`'s trailing backslash) and on `Link`.

### Everything else - the shared build environment, set up once for every build

`.MD\scripts\build-env\` is the one home; nothing in it names a machine-specific path (everything derives from the
file's own location):

- **`build-env.bat`** sets `TEMP` / `TMP` to `<project root>\.build-tmp`, `XMAKE_GLOBALDIR` to
  `<project root>\.build-env\xmake`, `XMAKE_TMPDIR` under `.build-tmp`, and puts `triplets\` first on
  `VCPKG_OVERLAY_TRIPLETS`. Given arguments, it runs them in that environment.
- **`triplets\x64-windows-static-md.cmake`** is the stock triplet plus `VCPKG_CHAINLOAD_TOOLCHAIN_FILE` =
  `toolchains\windows-trim-paths.cmake` and `VCPKG_LOAD_VCVARS_ENV ON` (without it a chainloaded toolchain makes
  vcpkg skip the MSVC environment and no C compiler is found).
- **`toolchains\windows-trim-paths.cmake`** includes vcpkg's own `toolchains\windows.cmake` and adds
  `/d1trimfile` for the port's build tree and for `vcpkg_installed` through `add_compile_options`. **Not
  `VCPKG_CXX_FLAGS`:** the prefix contains spaces, and vcpkg's parallel-configure ninja file cut the quoted value at
  its first space (cl received `/d1trimfile:D:\Claude`). vcpkg hashes the triplet and toolchain TEXT into the
  binary-cache key; both are the same for every repo, so `D:\vcpkg-binary-cache` stays shared across mods.
- **How a build reaches it:** the User environment variable `MODS_BUILD_ENV` names `build-env.bat`, and each CMake
  repo's `find-msvc.bat` ends with `if defined MODS_BUILD_ENV if exist "%MODS_BUILD_ENV%" call "%MODS_BUILD_ENV%"` -
  on anyone else's machine the variable is unset and the build is unchanged. A repo whose `find-msvc.bat`
  lacks the line gets it at its next build. **xmake repos** have no batch file: run `"%MODS_BUILD_ENV%" xmake build`.
- **Delete the DLL and PDB once before the first relink in the new environment.** link.exe reuses an existing PDB
  and keeps its old module records, so AMF 2.1.9's first rebuild still carried 254 user-folder strings from earlier
  links; after deleting the old PDB, 0.

### The verification is part of the standard practice, not optional

A build is only "stripped" once all of these are confirmed on the actual artefact, never on the flags:

1. The project root in the DLL's bytes = **0**, and the user folder in the DLL **and** the PDB = **0** - the patterns
   of gate rows `shipped-dll-carries-no-project-root` and `shipped-files-carry-no-user-folder`, which
   `package-gate` runs on every package.
2. The debug record's PDB path is the **bare filename** - `Get-DllCodeViewInfo` in `resolve.py run package-mod`.
3. **DLL/PDB pairing still passes** - `Test-PdbPairing` in the same script. Stripping must not cost symbol resolution.
4. A rebuilt binary is distinguishable from the one it replaces: record the new SHA-256 (an antivirus false-positive
   report is per file hash).

The PDB still carries the project root (its source and object paths, and `.build-tmp`); that is expected - no gate
row forbids it, and the PDB is what turns a crash address into a file and line.

---

---
