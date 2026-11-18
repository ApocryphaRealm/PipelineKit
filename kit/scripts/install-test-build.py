"""Install a packaged test build into its Njordlinger mod folder WITHOUT touching the player's settings.

The owner, 2026-09-21: "Make sure that the AMF that's called from the system row remembers any changes to its position
and size that the user makes and that its persistent when you reload the game." AMF did remember them - but a
test-build install earlier that day copied the package's default ApocryphaMenuFramework.ini over the one the game had
been writing, and the saved geometry was gone on the next launch. A mod's INI in the MO2 folder IS the player's
settings (the game rewrites it through the VFS), so an install must never overwrite one that already exists.

    python install-test-build.py "<package folder>" "<mod folder name>" [--line Line-SE-AE16] [--with-option NAME]...

A FOMOD package also gets the options its installer picks by itself (2026-10-27): every conditionalFileInstalls pattern
whose file conditions hold against the profile's enabled mods (AMF's SMF-Name stub while no SKSEMenuFramework.dll is
active), the Required / Recommended options of every group other than the build line and the language, and each
--with-option (an option's name or a source folder). An open combined-run batch that snapshotted the target folder
('backup --dir') is named in a loud warning - finish would put the old files back.

Copies Common\\ (or the package root when it has no Common\\), then the chosen build line and Languages\\All\\ when present.
An *.ini that already exists in the mod folder is KEPT only when it is a SETTINGS file; the packaged default is written
beside it as <name>.ini.default so a new setting can be merged by hand. A framework DATA INI (KID *_KID.ini, SPID
*_DISTR.ini, Base Object Swapper *_SWAP.ini, Seasons *_WIN/_SPR/_SUM/_AUT.ini, FLM *_FLM.ini, Description Framework
*_DESC.ini, Container Item Distributor *_CID.ini, anything under a SkyPatcher\\ folder) describes content, not the
player's choices, and is always REPLACED - a changed old copy is first copied to <instance>\\_install-backups\\<mod>\\<time>\\. A DLL the running game holds is renamed aside first (a loaded DLL can be renamed,
not overwritten). Prints every file it wrote or kept.

A file in the mod folder that the package does not ship (2026-10-26: an old SkyPatcher SoulStones.ini kept soul stones in
boss chests after the package dropped it) is MOVED, never deleted, into <instance>\\_install-backups\\<mod>\\<time>\\
under its path relative to the mod folder, and listed. Left in place: the player's settings INIs (the rule above), MO2's
meta.ini, a kept INI's .ini.default, MO2's .mohidden copies of package files, and a file the package's FOMOD installer
places (a chosen option) that is byte-identical to the package's copy - an option file with other bytes is an older
build's and is moved like any stale file. The read-back then FAILS unless the
folder equals the package plus those. `--verify-only` runs the read-back alone (no lock, nothing copied or moved), so
the check can be repeated at any time before a test.
"""
import os, sys, shutil, time, filecmp
sys.stdout.reconfigure(encoding="utf-8")
pkg, mod = sys.argv[1], sys.argv[2]
# A package path that doesn't exist once "installed" nothing and still read back as equal (2026-11-06, Deep Snow 1.1.0).
if not os.path.isdir(pkg) or not any(os.scandir(pkg)):
    sys.exit(f"REFUSED: the package folder does not exist or is empty: {pkg}")
line = sys.argv[sys.argv.index("--line") + 1] if "--line" in sys.argv else "Line-SE-AE16"
# --mods-dir: another instance's mods folder (2026-09-24: the Steam 1.7.104 test instance); Njordlinger by default
mods_dir = sys.argv[sys.argv.index("--mods-dir") + 1] if "--mods-dir" in sys.argv else ((os.environ.get("PIPELINE_MO2_INSTANCES") or "").split(";")[0] or sys.exit("set PIPELINE_MO2_INSTANCES or pass --mods-dir"))  # kit
# --profile: the MO2 profile whose modlist.txt decides priority (step 3.1, 2026-10-09); Njordlinger Test by default
profile = sys.argv[sys.argv.index("--profile") + 1] if "--profile" in sys.argv else "Default"  # kit: the MO2 default profile name
# A FULL PATH as the mod argument (2026-11-11, Simple Dodge 1.1.0, three times): os.path.join drops everything before an
# absolute part, so the backup folder <instance>\_install-backups\<mod>\<time> became <mod folder>\<time> - inside the
# mod, where MO2 loads it and the read-back failed on the moved files. Split a full path into its mods folder and name.
if os.path.isabs(mod):
    mods_dir, mod = os.path.dirname(os.path.normpath(mod)), os.path.basename(os.path.normpath(mod))
dst = os.path.join(mods_dir, mod)
mod_root = dst
# --verify-only: the read-back alone (no lock, no copy, no move) - fails when the folder is not the package
VERIFY = "--verify-only" in sys.argv
aside = os.path.join(os.path.dirname(os.path.normpath(mods_dir)), "_removed-locked-dlls")   # same drive: os.replace cannot cross drives
if not os.path.isdir(dst):
    sys.exit(f"no mod folder {dst}")


def agent_lock(instance_dir, purpose):
    """THE AGENT-LOCK GATE (the owner, 2026-10-12; .MD\\agent-bus\\README.md): one writer per instance. A free or stale lock
    is taken (and released when this install ends), our own is refreshed, a LIVE lock held by ANOTHER session refuses
    (exit 3). A missing or failing lock tool only warns (fail open)."""
    try:
        import importlib.util, subprocess
        rp = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "resolvers", "resolve.py"))
        r = subprocess.run([sys.executable, rp, "find", "agent-lock"], capture_output=True, text=True)
        path = r.stdout.strip().splitlines()[0] if r.returncode == 0 and r.stdout.strip() else ""
        spec = importlib.util.spec_from_file_location("agent_lock", path)
        al = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(al)
    except Exception as e:   # noqa: BLE001 - fail open, by design
        print(f"agent-lock: WARNING the lock tool is unavailable ({e}) - continuing without the lock")
        return
    al.gate(al.instance_resource(instance_dir), purpose)   # exits 3 when another session holds it; releases at exit what this call took


def snapshot_warning(folder):
    """THE SHARED-BASE-FOLDER WARNING (2026-10-27). An open combined-run batch that snapshotted this folder ('backup --dir')
    puts its old files back at finish. Souls to Perks and AMF builds installed into their shared base folders were undone
    that way, and a recorded-working build was left uninstalled. Warned loudly rather than refused: the snapshot is how
    a FAILED test undoes itself, and refusing would stop a batch mid-run; recording the build working before finish
    makes profile-version-gate mark the folder keep, and finish's fix + check catch what is left."""
    try:
        import importlib.util
        cr_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ops", "combined-run.py")
        spec = importlib.util.spec_from_file_location("combined_run_for_itb", cr_path)
        cr = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cr)
        want = os.path.normcase(os.path.normpath(folder))
        hits = [b["id"] for b in cr.batches("open") for bk in b.get("backups") or []
                if bk.get("kind") == "dir" and os.path.normcase(os.path.normpath(bk["from"])) == want]
    except Exception as e:   # noqa: BLE001 - a warning must never stop an install
        print(f"WARN  could not read the open combined-run batches ({e})")
        return
    if not hits:
        return
    import re as _re
    base = not _re.search(r"\s\d+\.\d+\.\d+(\s+FOMOD)?$", os.path.basename(folder), _re.I)
    bar = "!" * 100
    print(bar)
    print(f"WARNING  '{os.path.basename(folder)}' is {'a SHARED BASE folder (no version in its name) ' if base else ''}"
          f"snapshotted by open combined-run batch {', '.join(sorted(set(hits)))} ('backup --dir').")
    print("         'combined-run finish' will PUT THE OLD FILES BACK and undo this install. If this build passes,")
    print("         record it working BEFORE finish (version-gate record marks the folder keep), or mark it yourself with")
    print(f"         'combined-run keep --batch <B> --file \"{folder}\"'. Better: install test builds into a versioned")
    print("         'test <Mod> <version>' folder, which no restore touches.")
    print(bar)


if not VERIFY:
    agent_lock(os.path.dirname(os.path.normpath(mods_dir)), f"install-test-build {mod}")
    snapshot_warning(dst)
# Root Builder layout (2026-10-04, HUD Position Manager for Oblivion Remastered 1.0.2): an OR mod folder keeps the
# game-folder tree under Root\, the package does not - the install landed beside Root\ and the game kept loading the
# old DLL from Root\. A mod folder with Root\ and a package without it installs into Root\ (--no-root to opt out).
if "--no-root" not in sys.argv and os.path.isdir(os.path.join(dst, "Root")) and not os.path.isdir(os.path.join(pkg, "Root")):
    dst = os.path.join(dst, "Root")
    print(f"Root Builder layout: installing into {dst}")
sources = []
common = os.path.join(pkg, "Common")
sources.append(common if os.path.isdir(common) else pkg)
for extra in (os.path.join(pkg, line), os.path.join(pkg, "Languages", "All")):
    if os.path.isdir(extra):
        sources.append(extra)

# THE FOMOD'S DEFAULT OPTIONS (2026-10-27). AMF's FOMOD installs SMF-Name\ (the !ApocryphaMenuFramework-SMFName.dll
# stub) through a conditionalFileInstalls pattern - "while SKSE\Plugins\SKSEMenuFramework.dll is Missing" - and this
# tool installed only Common\ + the line + Languages\All, so every AMF install moved the old stub aside and put nothing in
# its place; it was copied in by hand each time. Now the installer's own choices are made here as a mod manager would:
#   * every conditionalFileInstalls pattern whose fileDependency conditions hold (a file is Active / Present when an
#     enabled mod of the profile, overwrite\ or Stock Game\Data holds it, Missing when none does); a pattern with any
#     other kind of dependency (a flag) is skipped and named;
#   * in every installStep group that is NOT the build-line or language choice above, the plugins typed Required or
#     Recommended;
#   * --with-option <plugin name | source folder> (repeatable): that option as well, whatever its type.
# Each source is (folder or file in the package, destination inside the mod folder).
sources = [(s, "") for s in sources]
WITH_OPTIONS = [sys.argv[i + 1] for i, v in enumerate(sys.argv[:-1]) if v == "--with-option"]


def _norm_src(s):
    return (s or "").strip().replace("/", "\\").strip("\\")


def _profile_data_has(rel, instance_dir, own_folder):
    rel = rel.replace("/", "\\").strip("\\")
    roots = [os.path.join(instance_dir, "overwrite"), os.path.join(instance_dir, "Stock Game", "Data")]
    ml = os.path.join(instance_dir, "profiles", profile, "modlist.txt")
    try:
        with open(ml, encoding="utf-8-sig", errors="replace") as fh:
            for raw in fh:
                s = raw.rstrip("\r\n")
                if s.startswith("+") and not s.endswith("_separator") and s[1:] != own_folder:
                    roots.append(os.path.join(instance_dir, "mods", s[1:]))
    except OSError:
        pass
    return any(os.path.isfile(os.path.join(r, rel)) for r in roots)


def fomod_default_sources():
    mc = os.path.join(pkg, "fomod", "ModuleConfig.xml")
    if not os.path.isfile(mc):
        return []
    try:
        import xml.etree.ElementTree as ET
        root = ET.parse(mc).getroot()
    except Exception as e:   # noqa: BLE001
        print(f"WARN  cannot read {mc} ({e}) - no FOMOD option installed beyond Common\\, the line and Languages\\All")
        return []

    def tag(el):
        return el.tag.rsplit("}", 1)[-1]

    def files_of(el):
        out = []
        for f in el.iter():
            if tag(f) in ("file", "folder") and f.get("source"):
                out.append((os.path.join(pkg, _norm_src(f.get("source"))), _norm_src(f.get("destination"))))
        return out

    chosen, said = [], []
    have = {os.path.normcase(os.path.normpath(s)) for s, _ in sources}
    instance_dir = os.path.dirname(os.path.normpath(mods_dir))
    for pat in root.iter():
        if tag(pat) != "pattern":
            continue
        deps = [d for d in pat.iter() if tag(d).endswith("Dependency")]
        if any(tag(d) != "fileDependency" for d in deps):
            said.append("skipped a conditional install with a %s (not a file condition)" %
                        ", ".join(sorted({tag(d) for d in deps if tag(d) != "fileDependency"})))
            continue
        op = next((d.get("operator") for d in pat.iter() if tag(d) == "dependencies"), "And") or "And"
        results = []
        for d in deps:
            present = _profile_data_has(d.get("file", ""), instance_dir, mod)
            st = (d.get("state") or "Active").lower()
            results.append(present if st in ("active", "inactive") else not present)
        if (all(results) if op.lower() == "and" else any(results)):
            fl = files_of(next((x for x in pat if tag(x) == "files"), pat))
            chosen += fl
            said.append("conditional install (%s): %s" % (
                " / ".join("%s %s" % (d.get("file"), d.get("state")) for d in deps),
                ", ".join(os.path.relpath(s, pkg) for s, _ in fl)))
    for grp in root.iter():
        if tag(grp) != "group":
            continue
        for plug in (p for p in grp.iter() if tag(p) == "plugin"):
            fl = files_of(next((x for x in plug if tag(x) == "files"), plug))
            srcs = {os.path.normcase(os.path.relpath(s, pkg)) for s, _ in fl}
            typ = next((t.get("name") for t in plug.iter() if tag(t) == "type"), "") or ""
            named = any(w == plug.get("name") or os.path.normcase(_norm_src(w)) in srcs for w in WITH_OPTIONS)
            line_or_lang = any(s.lower().startswith(("line-", "languages\\")) for s in srcs)
            if named or (typ in ("Required", "Recommended") and not line_or_lang):
                chosen += fl
                said.append("option '%s' (%s): %s" % (plug.get("name"), "--with-option" if named else typ,
                                                      ", ".join(os.path.relpath(s, pkg) for s, _ in fl)))
    for w in WITH_OPTIONS:
        if not any(w == p.get("name") for p in root.iter() if tag(p) == "plugin") and \
                not os.path.exists(os.path.join(pkg, _norm_src(w))):
            sys.exit(f"FAIL  --with-option '{w}' is neither an option name nor a source folder of {mc}")
        if not any(w == p.get("name") for p in root.iter() if tag(p) == "plugin"):
            chosen.append((os.path.join(pkg, _norm_src(w)), ""))
            said.append(f"--with-option source folder {w}")
    out = []
    for s, d in chosen:
        key = os.path.normcase(os.path.normpath(s))
        if key in have or not os.path.exists(s):
            continue
        have.add(key)
        out.append((s, d))
    for s in said:
        print("FOMOD  " + s)
    return out


sources += fomod_default_sources()
kept = wrote = 0
written = []


def package_owned(name):
    # 2026-09-22, Perfected Wheeler 1.3.7: Wheeler's Controls.defaults.ini (the new Q default) was KEPT as if it were
    # the player's settings, so the installed build still shipped G. A *.defaults.ini / *.factory.ini holds the
    # package's defaults - the player's own values live elsewhere (Wheeler: Controls.ini in overwrite) - so it is
    # always replaced, like a DLL.
    # 2026-09-25, AMF 1.9.8: the shipped theme INIs (SKSE\Plugins\ApocryphaMenuFramework	hemes\*.ini) were KEPT as
    # settings, so a reinstall left the previous build's theme colours in place. A theme file describes the art that ships
    # beside it; the player's theme CHOICE lives in ApocryphaMenuFramework.ini. Takes the path relative to the package.
    # 2026-10-08, AMF 2.1.6: the art library's part INIs (SKSE\Plugins\ApocryphaMenuFramework\assets\<kind>\<name>.ini) say
    # how a shipped PNG is cut - they describe the art beside them, like a theme INI, and the player's picks live in
    # User.ini. Kept as settings, a changed cut would never reach the game.
    n = name.lower().replace("\\", "/")
    return (n.endswith(".defaults.ini") or n.endswith(".factory.ini") or "/themes/" in "/" + n
            or "/apocryphamenuframework/assets/" in "/" + n)


# 2026-10-26, Njordlinger Combat Gameplay Overhaul: its NjordlingerCGO_*_KID.ini and SkyPatcher\npc\NjordlingerCGO\
# LoreTierLevels.ini were KEPT as "the player's settings", so a changed tier/distribution file never reached the game
# (past-mistakes library 7378 is the same class, fixed then for AMF's themes only). THE RULE: an INI read by a
# distribution / patching FRAMEWORK is the package's data - the framework's file-name suffix or its folder says so - and
# is always replaced (a changed old copy is backed up first). Every other existing INI (a mod's own settings such as
# SKSE\Plugins\<Mod>.ini, an OBSE plugin's INI) is the player's and is kept, as before.
DATA_INI_SUFFIXES = ("_kid.ini", "_distr.ini", "_swap.ini", "_win.ini", "_spr.ini", "_sum.ini", "_aut.ini",
                     "_flm.ini", "_desc.ini", "_cid.ini")
DATA_INI_FOLDERS = ("/skypatcher/",)


def data_ini(name):
    n = "/" + name.lower().replace(os.sep, "/").replace("\\", "/")
    return n.endswith(".ini") and (n.endswith(DATA_INI_SUFFIXES) or any(d in n for d in DATA_INI_FOLDERS))


def settings_ini(name):
    """The player's settings: any *.ini that is neither package-owned nor framework data. Kept when it exists."""
    return name.lower().endswith(".ini") and not package_owned(name) and not data_ini(name)


stamp = time.strftime("%Y%m%d-%H%M%S")
backup_dir = os.path.join(os.path.dirname(os.path.normpath(mods_dir)), "_install-backups", mod, stamp)
if os.path.normcase(os.path.normpath(backup_dir)).startswith(os.path.normcase(os.path.normpath(dst)) + os.sep):
    sys.exit(f"REFUSED: the backup folder {backup_dir} would sit inside the mod folder {dst}")


def back_up(path, rel):
    """Copy an existing file into this install's backup folder before it is replaced. Returns the backup path."""
    to = os.path.join(backup_dir, rel)
    os.makedirs(os.path.dirname(to), exist_ok=True)
    shutil.copy2(path, to)
    return to


def package_map():
    """Every file the install lays down: lower-case path relative to the target folder -> (path, package file). A later
    source (the build line, then Languages\\All) wins over Common\\, as it did when each source was copied in turn."""
    m = {}
    for src, dest in sources:
        if os.path.isfile(src):                     # a FOMOD <file> option
            leaf = os.path.basename(src)
            rel = dest if dest and os.path.splitext(dest)[1] else os.path.join(dest, leaf) if dest else leaf
            m[rel.lower()] = (rel, src)
            continue
        for dp, dn, fn in os.walk(src):
            if os.path.basename(dp).lower() == "fomod":
                continue
            for f in fn:
                full = os.path.join(dp, f)
                rel = os.path.relpath(full, src)
                if dest:
                    rel = os.path.join(dest, rel)
                m[rel.lower()] = (rel, full)
    return m


pkgmap = package_map()


def fomod_map():
    """Where the package's fomod\\ModuleConfig.xml puts each package file (required files, every option, conditional
    installs): lower-case destination -> [package files]. This tool installs Common\\ + one build line only, but a folder
    first installed from the archive also holds the options the player chose (Norden UI - Black's RaceMenuAtelier.dll from
    Extras\\, 2026-10-20); such a file still belongs to the package when its bytes are one of the package's copies."""
    mc = os.path.join(pkg, "fomod", "ModuleConfig.xml")
    if not os.path.isfile(mc):
        return {}
    try:
        import xml.etree.ElementTree as ET
        root = ET.parse(mc).getroot()
    except Exception as e:   # noqa: BLE001 - an unreadable installer only narrows what counts as the package's
        print(f"WARN  cannot read {mc} ({e}) - files its options place are judged as not in the package")
        return {}
    allfiles = []
    for dp, dn, fn in os.walk(pkg):
        for f in fn:
            allfiles.append(os.path.relpath(os.path.join(dp, f), pkg))
    m = {}
    for el in root.iter():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag not in ("file", "folder") or not el.get("source"):
            continue
        src = el.get("source").strip().replace("/", "\\").strip("\\")
        dest = (el.get("destination") or "").strip().replace("/", "\\")
        for rel in allfiles:
            if tag == "folder":
                if not rel.lower().startswith(src.lower() + "\\"):
                    continue
                sub = rel[len(src) + 1:]
                d = dest.rstrip("\\") + "\\" + sub if dest.strip("\\") else sub
            else:
                if rel.lower() != src.lower():
                    continue
                leaf = os.path.basename(src)
                if not dest:
                    d = leaf
                elif dest.endswith("\\") or (not os.path.splitext(dest)[1] and os.path.splitext(leaf)[1]):
                    d = dest.rstrip("\\") + "\\" + leaf
                else:
                    d = dest
            m.setdefault(os.path.normpath(d).lower(), []).append(os.path.join(pkg, rel))
    return m


fomodmap = fomod_map()


def installed_files():
    """Every file in the target folder, as paths relative to it."""
    out = []
    for dp, dn, fn in os.walk(dst):
        for f in fn:
            out.append(os.path.relpath(os.path.join(dp, f), dst))
    return out


def belongs(rel):
    """True when an installed file is accounted for: the package ships it, it is MO2's meta.ini at the mod folder's root,
    the packaged default (<settings>.ini.default) beside a kept settings INI, or MO2's hidden copy (.mohidden) of a
    package file."""
    k = rel.lower()
    if k in pkgmap:
        return True
    if dst == mod_root and k == "meta.ini":
        return True
    if k.endswith(".mohidden") and k[:-len(".mohidden")] in pkgmap:
        return True
    if k.endswith(".default") and k[:-len(".default")] in pkgmap and settings_ini(k[:-len(".default")]):
        return True
    # a file one of the installer's options placed, still byte-identical to the package's copy (hidden in MO2 or not)
    base = k[:-len(".mohidden")] if k.endswith(".mohidden") else k
    here = os.path.join(dst, rel)
    return any(filecmp.cmp(c, here, shallow=False) for c in fomodmap.get(os.path.normpath(base), []))


replaced_data = []
moved_stale = []      # (rel, backup path)


# THE NEWER-FILE GATE (2026-11-12, World Map Render): a full install of the package replaced the hand-smoothed map
# pictures in the test folder (copied in from C:\Builds\worldmap-render\stage\data, 11-05 08:51) with the package's older
# 02:46 copies - on 2026-11-09 (caught and restored) and again on 2026-11-10 (not caught; the owner saw the rectangular
# block and the ocean trenches come back on 11-12). The installed copy was NEWER than the package's and had other bytes:
# it came from somewhere other than this package. Such a file is not replaced unless --replace-newer is given, and then
# it is first copied to _install-backups. DLL/PDB (the binary under test) and the player's settings INIs are exempt.
NEWER_SLACK = 120   # seconds; copy2 keeps mtimes, so an install of the same file is never "newer"
if not VERIFY:
    newer = []
    for rel, full in pkgmap.values():
        to = os.path.join(dst, rel)
        if rel.lower().endswith((".dll", ".pdb")) or settings_ini(rel) or not os.path.isfile(to):
            continue
        if os.path.getmtime(to) > os.path.getmtime(full) + NEWER_SLACK and not filecmp.cmp(full, to, shallow=False):
            newer.append(rel)
    if newer and "--replace-newer" not in sys.argv:
        sys.exit(f"REFUSED: {len(newer)} file(s) in {mod} are NEWER than the package's copy and differ from it - they came "
                 f"from another build (a hand-installed stage, a later render). Installing would revert them. "
                 f"First: {', '.join(sorted(newer)[:8])}. Install only the files that changed (a staging copy holding "
                 f"just the DLL/PDB), rebuild the package from the newer data, or pass --replace-newer to replace them "
                 f"(old copies go to _install-backups).")
    for rel in newer:
        print(f"  backed up newer {rel} -> {back_up(os.path.join(dst, rel), rel)}  (--replace-newer)")


if VERIFY:
    written = [rel for rel, _ in pkgmap.values()]
    print(f"verify only: nothing is copied or moved; checking {dst} against {pkg}")
else:
    for rel, full in pkgmap.values():
        f = os.path.basename(rel)
        to = os.path.join(dst, rel)
        os.makedirs(os.path.dirname(to), exist_ok=True)
        if data_ini(rel) and os.path.exists(to) and not filecmp.cmp(full, to, shallow=False):
            b = back_up(to, rel)
            print(f"  replaced {rel}  (framework data INI, not settings; old copy -> {b})")
            replaced_data.append(rel)
        elif settings_ini(rel) and os.path.exists(to):
            shutil.copy2(full, to + ".default")
            print(f"  kept   {rel}  (the player's settings; packaged default -> {os.path.basename(to)}.default)")
            kept += 1
            continue
        if f.lower().endswith((".dll", ".pdb")) and os.path.exists(to):
            os.makedirs(aside, exist_ok=True)
            try:
                os.replace(to, os.path.join(aside, f + "." + stamp))
            except OSError as e:
                sys.exit(f"cannot move the old {rel} aside: {e}")
        shutil.copy2(full, to)
        wrote += 1
        written.append(rel)
    # 2026-10-26: STALE FILES. A file an earlier build installed and this package no longer ships stayed in the mod
    # folder and kept acting in game - an old SkyPatcher SoulStones.ini kept soul stones in boss chests after the package
    # dropped it, and an old Barter script lingered. Every such file is MOVED (never deleted) into this install's backup
    # folder under its path relative to the mod folder, and named here. Left in place: the player's settings INIs
    # (settings_ini) and MO2's meta.ini. (A *.ini.default beside a package-owned INI - litter from before 2026-09-25 -
    # is stale too, and is moved rather than removed as it used to be.)
    for rel in installed_files():
        if belongs(rel):
            continue
        if settings_ini(rel):
            print(f"  kept   {rel}  (the player's settings; the package no longer ships it)")
            continue
        src_path = os.path.join(dst, rel)
        to = os.path.join(backup_dir, os.path.relpath(src_path, mod_root))
        if os.path.exists(to):
            to += ".stale"
        os.makedirs(os.path.dirname(to), exist_ok=True)
        try:
            os.replace(src_path, to)          # same drive: a rename, which also works on a DLL the game holds
        except OSError:
            try:
                shutil.move(src_path, to)
            except OSError as e:
                sys.exit(f"FAIL  cannot move the stale {rel} out of the mod folder: {e}")
        moved_stale.append((rel, to))
        print(f"  moved  {rel}  (not in the package; -> {to})")

# Read back: the installed folder must EQUAL the package - every package file present and byte-identical (a kept
# settings INI may differ: it is the player's) - and hold no file the package lacks, except the player's settings INIs,
# MO2's meta.ini, the .ini.default beside a kept settings INI and MO2's .mohidden copies of package files.
filecmp.clear_cache()   # the data-INI check above cached "differs" by stat signature; copy2 can leave size+mtime unchanged
stale = []
for rel, full in pkgmap.values():
    to = os.path.join(dst, rel)
    if not os.path.exists(to):
        if settings_ini(rel) or not os.path.exists(to + ".mohidden"):
            stale.append(rel + " (missing)")
        continue
    if not settings_ini(rel) and not filecmp.cmp(full, to, shallow=False):
        stale.append(rel)
extra = [rel for rel in installed_files() if not belongs(rel) and not settings_ini(rel)]
if not VERIFY:
    print(f"installed {wrote} file(s) into {mod}; kept {kept} existing settings file(s); replaced {len(replaced_data)} changed "
          f"framework data INI(s); moved {len(moved_stale)} stale file(s) the package no longer ships"
          + (f" (old copies in {backup_dir})" if replaced_data or moved_stale else ""))
if stale:
    sys.exit("FAIL  file(s) in the mod folder differ from the package: " + ", ".join(stale[:8]))
if extra:
    sys.exit(f"FAIL  installed folder holds {len(extra)} file(s) the package lacks: " + ", ".join(extra[:8])
             + " - install with install-test-build.py, which moves them to _install-backups")
print("read back: the mod folder equals the package (plus the player's settings INIs"
      + (" and meta.ini)" if dst == mod_root else ")"))

# Priority gate (step 3.1): the FIRST mod line in modlist.txt is the highest priority and wins (logic library entry 20).
# An enabled mod written above ours that holds one of the files this run wrote would shadow it in the VFS.
instance = os.path.dirname(os.path.normpath(mods_dir))
modlist_path = os.path.join(instance, "profiles", profile, "modlist.txt")
if not os.path.isfile(modlist_path):
    print(f"WARN  no modlist.txt for profile {profile} - priority not checked")
    sys.exit(0)
entries = []   # (line number, enabled, name) for real mods only
with open(modlist_path, encoding="utf-8-sig") as fh:
    for i, raw in enumerate(fh, 1):
        s = raw.rstrip("\r\n")
        if not s or s[0] not in "+-" or s[1:].endswith("_separator"):
            continue
        entries.append((i, s[0] == "+", s[1:]))
mine = [e for e in entries if e[2] == mod]
if not mine or not mine[0][1]:
    sys.exit(f"FAIL  {mod} is missing from / disabled in profile {profile}")
my_line = mine[0][0]
# 2026-10-22, Perfected Wheeler 1.4.1: an enabled test dMenu folder above Wheeler carried a stale
# dMenu/customSettings/Wheeler Controls.json; it won the VFS, the new settings row never reached the DLL, and the test
# was recorded failed. A settings-page descriptor (*.json) decides what the page shows as much as the DLL does.
guarded = [r for r in written if r.lower().endswith((".dll", ".swf", ".esp", ".esl", ".pex", ".bsa", ".json"))]
rooted = os.path.basename(dst).lower() == "root"
above = [e for e in entries if e[1] and e[0] < my_line and e[2] != mod]
for ln, _, other in above:
    base = os.path.join(mods_dir, other)
    for rel in guarded:
        cands = [os.path.join(base, "Root", rel)] if rooted else []
        cands.append(os.path.join(base, rel))
        for c in cands:
            if os.path.exists(c):
                sys.exit(f"FAIL  {rel} is SHADOWED by '{other}' (line {ln} of modlist.txt, above '{mod}' at line {my_line}) - disable or move it")
print(f"priority check: '{mod}' is not shadowed in profile {profile} ({len(above)} enabled mods above it checked)")
