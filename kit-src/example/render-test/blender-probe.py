"""Self-test probe (Pipeline Kit, step 11 of kit-selftest.ps1): is Blender with PyNifly here for the renders?
Prints "BLENDER-OK <path>" or "SKIP <why>"; always exits 0 - an absent Blender is a SKIP, not a failure.

    python blender-probe.py <the kit's scripts\\render folder>
"""
import sys

sys.path.insert(0, sys.argv[1])
import render_lib  # noqa: E402

ok, why = render_lib.pynifly_ok()
print(("BLENDER-OK " + render_lib.find_blender()) if ok else ("SKIP " + why))
