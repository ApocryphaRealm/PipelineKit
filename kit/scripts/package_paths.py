"""Package folder layout for the Python scripts (the owner, 2026-10-01).

Packages, test builds and finalized releases sit under a folder named like the mod's distro folder:
    7. current test builds\\<Game> - <Mod>\\<Mod> <version>[ FOMOD]
    10. finalized mods\\<Game> - <Mod>\\<Mod> <version>[ FOMOD][.zip]
The ONE resolver is .MD\\resolvers\\resolve.py (its "distro" commands, step 2.3 of the pipeline restructure); this
module calls it directly, so no Python script joins "<stage>\\<Mod> <version>" itself.

    package_root(stage, mod, game)                 -> "<stage>\\<Game> - <Mod>" (existing or not)
    find_packages(stage, mod=None, game=None, version=None, folders=False, archives=False, symbols=False)
                                                   -> [{name, path, mod, version, tail, game, flat, is_dir}, ...]
game is "Skyrim", "Oblivion Remastered", "Witcher 3", "Norse" or "MO2".
"""
import importlib.util
import os
import sys

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(SCRIPTS))
STAGE7 = os.path.join(ROOT, "7. current test builds")
STAGE10 = os.path.join(ROOT, "10. finalized mods")
RESOLVERS = os.path.join(os.path.dirname(SCRIPTS), "resolvers")

_resolve = None


def _ctx():
    global _resolve
    if _resolve is None:
        spec = importlib.util.spec_from_file_location("resolve", os.path.join(RESOLVERS, "resolve.py"))
        _resolve = importlib.util.module_from_spec(spec)
        keep, sys.dont_write_bytecode = sys.dont_write_bytecode, True   # no __pycache__ beside the rosters
        try:
            spec.loader.exec_module(_resolve)
        finally:
            sys.dont_write_bytecode = keep
    return _resolve, _resolve.Ctx(_resolve.Rosters(os.path.join(RESOLVERS, "rosters")), ROOT, {})


def _call(argv):
    mod, ctx = _ctx()
    try:
        return mod.distro_dispatch(ctx, [str(a) for a in argv])
    except Exception as e:
        raise RuntimeError(f"resolve.py distro failed: {e}")


def package_root(stage, mod, game):
    return _call(["pkgroot", stage, mod, "--game", game or ""])


def find_packages(stage, mod=None, game=None, version=None, folders=False, archives=False, symbols=False):
    argv = ["find-packages", stage, "--mod", mod or "", "--game", game or "", "--version", version or ""]
    if folders:
        argv.append("--folders")
    if archives:
        argv.append("--archives")
    if symbols:
        argv.append("--symbols")
    keys = ("name", "path", "mod", "version", "tail", "game", "flat", "is_dir")
    return [{k: p[k] for k in keys} for p in _call(argv)]
