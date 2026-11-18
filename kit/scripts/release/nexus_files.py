r"""Several downloads per release, from one package (2026-11-12, Truly Nordic Carved Weapons Replacer 1.1.0: four main
files, each its own FOMOD). The distro folder's nexus-files.json says which package subfolder becomes which Nexus file;
finalize-mod.ps1, sync-nexus-distro.ps1 / nexus-distro-sweep.ps1, package-gate.ps1 (distro-archive-equals-finalized-folder)
and nexus-upload.py read it through this module. A mod WITHOUT the manifest keeps the one-zip behaviour everywhere.

THE MANIFEST  <distro folder>\nexus-files.json
    {"files": [
       {"folder": "Replacer - No ESP",          the package subfolder (a top-level folder of "<Mod> X.Y.Z")
        "name": "Replacer - No ESP",            the Nexus file name: no version, no "FOMOD" (the owner, 2026-09-30)
        "category": "main",                     main | optional
        "description": "FOMOD - ...",           the Nexus file description (File options box)
        "replaces": 12345 | null,               the Nexus mod-file id this posts a NEW VERSION of; null = a new file
        "primary": true}, ...]}                 exactly one main file is the primary mod-manager download
THE ARCHIVES  "<Mod> X.Y.Z - <folder>.zip" each - the same "<package> - <name>" shape the one-zip rule already keeps
    as part of a version's post, so older tools leave them alone; each lists exactly its subfolder's files.

CLI (exit 0 ok, 1 refused; every line a check prints for a gate starts "HIT "):
    nexus_files.py validate <distro dir>
    nexus_files.py zip      <finalized package folder> <out dir> <distro dir> zip every entry's subfolder, read back
    nexus_files.py publish  <out dir> <package folder> <distro dir>           copy the zips in, post-check hash + entries
    nexus_files.py gate     <package folder> <distro dir>                     the row's check (each archive == its folder)
    nexus_files.py prune    <distro dir> <mod> <version> [--apply]            other zips of the mod -> Recycle Bin
    nexus_files.py sweep    <distro dir> <finalized dir> <mod> <version> [--apply]
"""
import hashlib, json, os, re, shutil, sys, zipfile

MANIFEST = "nexus-files.json"
NAME_OK = re.compile(r"^[a-zA-Z0-9 _'().-]+$")


def load(distro_dir):
    """The manifest's file list, validated, or None when the folder has no manifest (the one-zip behaviour)."""
    p = os.path.join(distro_dir, MANIFEST)
    if not os.path.isfile(p):
        return None
    files = json.load(open(p, encoding="utf-8-sig")).get("files")
    problems = validate(files)
    if problems:
        raise SystemExit(f"{p}: " + "; ".join(problems))
    return files


def validate(files):
    out = []
    if not isinstance(files, list) or not files:
        return ["'files' must be a non-empty list"]
    seen_f, seen_n = set(), set()
    for i, f in enumerate(files):
        w = f"file {i + 1}"
        for k in ("folder", "name", "category", "description"):
            if not isinstance(f.get(k), str) or not f[k].strip():
                out.append(f"{w}: '{k}' is missing")
        if f.get("category") not in ("main", "optional"):
            out.append(f"{w}: category must be main or optional")
        n = f.get("name") or ""
        if re.search(r"\d+\.\d+\.\d+", n) or re.search(r"\bfomod\b", n, re.I):
            out.append(f"{w}: the name '{n}' carries a version or 'FOMOD' (the owner, 2026-09-30: never in a file name)")
        if n and (not NAME_OK.match(n) or len(n) > 50):
            out.append(f"{w}: the name '{n}' does not fit Nexus's file-name pattern (50 characters, letters digits _'().-)")
        if f.get("replaces") is not None and not isinstance(f.get("replaces"), int):
            out.append(f"{w}: 'replaces' is a Nexus mod-file id (a number) or null")
        if f.get("folder") in seen_f: out.append(f"{w}: folder '{f.get('folder')}' is listed twice")
        if n in seen_n: out.append(f"{w}: name '{n}' is listed twice")
        seen_f.add(f.get("folder")); seen_n.add(n)
    prim = [f for f in files if f.get("primary")]
    if len(prim) != 1 or prim[0].get("category") != "main":
        out.append("exactly one file must be \"primary\": true, and it must be a main file")
    reps = [f["replaces"] for f in files if isinstance(f.get("replaces"), int)]
    if len(reps) != len(set(reps)):
        out.append("two files replace the same Nexus file")
    return out


def archive_name(package_leaf, entry):
    """'<Mod> X.Y.Z' + the entry's folder -> '<Mod> X.Y.Z - <folder>.zip'."""
    return f"{package_leaf} - {entry['folder']}.zip"


def folder_files(folder):
    out = {}
    for root, _, names in os.walk(folder):
        for n in names:
            full = os.path.join(root, n)
            out[os.path.relpath(full, folder).replace(os.sep, "/")] = full
    return out


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def compare(zip_path, folder):
    """Every difference between an archive and a folder: names (case-insensitive), then contents."""
    bad = []
    files = {k.lower(): v for k, v in folder_files(folder).items()}
    with zipfile.ZipFile(zip_path) as z:
        entries = {i.filename.lower(): i for i in z.infolist() if not i.is_dir()}
        if any("\\" in i.filename for i in z.infolist()):
            bad.append(f"{os.path.basename(zip_path)} has a backslash in an entry name")
        for k in sorted(set(files) - set(entries)): bad.append(f"{os.path.basename(zip_path)} lacks {k}")
        for k in sorted(set(entries) - set(files)): bad.append(f"{os.path.basename(zip_path)} has extra file {k}")
        for k in sorted(set(files) & set(entries)):
            if hashlib.sha256(z.read(entries[k])).digest() != hashlib.sha256(open(files[k], "rb").read()).digest():
                bad.append(f"{os.path.basename(zip_path)}'s {k} differs from the package folder")
    return bad


def make_zip(folder, zp):
    files = sorted(folder_files(folder).items(), key=lambda f: ("/" in f[0], f[0]))
    if not files:
        raise SystemExit(f"the package subfolder {folder} is empty or missing")
    tmp = zp + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for arc, full in files:
            z.write(full, arc)
    bad = compare(tmp, folder)
    if bad:
        os.remove(tmp); raise SystemExit("the zip did not read back: " + "; ".join(bad[:5]))
    os.replace(tmp, zp)
    return len(files)


def recycle(path):
    """To the Recycle Bin, never a hard delete (rule 50)."""
    import ctypes
    from ctypes import wintypes
    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT), ("pFrom", wintypes.LPCWSTR), ("pTo", wintypes.LPCWSTR),
                    ("fFlags", ctypes.c_uint16), ("fAnyOperationsAborted", wintypes.BOOL), ("hNameMappings", ctypes.c_void_p),
                    ("lpszProgressTitle", wintypes.LPCWSTR)]
    op = SHFILEOPSTRUCTW(None, 3, os.path.abspath(path) + "\0", None, 0x0040 | 0x0010 | 0x0004 | 0x0400, False, None, None)
    if ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op)) != 0 or os.path.exists(path):
        raise SystemExit(f"could not send {path} to the Recycle Bin")


# ---------------------------------------------------------------------------------------------------- commands
def cmd_zip(pkg, out_dir, distro):
    files = load(distro)
    if files is None: raise SystemExit(f"no {MANIFEST} in {distro}")
    leaf = os.path.basename(os.path.normpath(pkg))
    for e in files:
        zp = os.path.join(out_dir, archive_name(leaf, e))
        n = make_zip(os.path.join(pkg, e["folder"]), zp)
        print(f"  zip: {os.path.basename(zp)} - {n} entries, read back and matched")
    return 0


def cmd_publish(out_dir, pkg, distro):
    files = load(distro); leaf = os.path.basename(os.path.normpath(pkg)); bad = []
    for e in files:
        a = archive_name(leaf, e); src = os.path.join(out_dir, a); dst = os.path.join(distro, a)
        if not os.path.isfile(src):
            bad.append(f"no finalized {a}"); continue
        shutil.copy2(src, dst)
        if sha_file(src) != sha_file(dst): bad.append(f"the distro copy of {a} is not the finalized zip (SHA-256)")
        bad += compare(src, os.path.join(pkg, e["folder"]))
        print(f"  copied -> {dst}")
    for b in bad: print("  !!    [distro-archive-equals-finalized-folder] " + b)
    if bad:
        for e in files:
            p = os.path.join(distro, archive_name(leaf, e))
            if os.path.isfile(p): recycle(p)
        print("  rolled back: the copied zips went to the Recycle Bin")
        return 1
    print(f"  ok  {len(files)} distro zip(s): each SHA-256 is its finalized zip's, and each lists exactly its package subfolder")
    return 0


def cmd_gate(pkg, distro):
    files = load(distro); leaf = os.path.basename(os.path.normpath(pkg)); hits = []
    for e in files:
        a = archive_name(leaf, e); p = os.path.join(distro, a)
        if not os.path.isdir(os.path.join(pkg, e["folder"])):
            hits.append(f"the manifest names folder '{e['folder']}', which the package does not have"); continue
        if not os.path.isfile(p):
            hits.append(f"no archive {a} in the distro folder"); continue
        hits += compare(p, os.path.join(pkg, e["folder"]))
    tops = {d for d in os.listdir(pkg) if os.path.isdir(os.path.join(pkg, d))}
    for d in sorted(tops - {e["folder"] for e in files}):
        hits.append(f"package subfolder '{d}' is in no manifest entry (it would never be posted)")
    for h in hits: print("HIT " + h)
    if not hits: print(f"OK {len(files)} archive(s), each equal to its package subfolder")
    return 1 if hits else 0


def expected(distro, mod, version):
    return {f"{mod} {version} - {e['folder']}.zip" for e in load(distro)}


def stale_zips(distro, mod, version):
    keep = {n.lower() for n in expected(distro, mod, version)}
    return [os.path.join(distro, n) for n in os.listdir(distro)
            if n.lower().endswith(".zip") and n.lower().startswith(mod.lower() + " ") and n.lower() not in keep]


def cmd_prune(distro, mod, version, apply):
    st = stale_zips(distro, mod, version)
    for p in st:
        if apply: recycle(p)
        print(("  recycled " if apply else "  would recycle ") + os.path.basename(p))
    if not st: print("  no other zip of this mod in the distro folder")
    return 0


def cmd_sweep(distro, fin_dir, mod, version, apply):
    exp = sorted(expected(distro, mod, version)); acts = []
    for n in exp:
        src = os.path.join(fin_dir, n); dst = os.path.join(distro, n)
        if not os.path.isfile(src):
            print(f"FLAGGED newest finalized is {version} but '10. finalized mods' has no {n}"); return 0
        if not os.path.isfile(dst) or os.path.getsize(dst) != os.path.getsize(src):
            acts.append(("copy", src, dst))
    acts += [("recycle", p, None) for p in stale_zips(distro, mod, version)]
    if not acts:
        print(f"CURRENT {len(exp)} manifest zip(s) of {version}: " + ", ".join(exp)); return 0
    words = [f"copy in {os.path.basename(a[1])}" if a[0] == "copy" else f"remove {os.path.basename(a[1])}" for a in acts]
    if apply:
        for kind, a, b in acts:
            shutil.copy2(a, b) if kind == "copy" else recycle(a)
        print("FIXED " + "; ".join(words))
    else:
        print("WOULD-FIX " + "; ".join(words) + " (re-run with -Apply)")
    return 0


def main(argv):
    if not argv: print(__doc__); return 1
    c, a = argv[0], argv[1:]
    apply = "--apply" in a; a = [x for x in a if x != "--apply"]
    if c == "validate":
        f = load(a[0]); print("OK" if f is not None else "no manifest"); return 0
    if c == "zip": return cmd_zip(a[0], a[1], a[2])
    if c == "publish": return cmd_publish(a[0], a[1], a[2])
    if c == "gate": return cmd_gate(a[0], a[1])
    if c == "prune": return cmd_prune(a[0], a[1], a[2], apply)
    if c == "sweep": return cmd_sweep(a[0], a[1], a[2], a[3], apply)
    print(__doc__); return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
