"""Refuses an SKSE plugin DLL whose SKSEPlugin_Version data pins a list of game runtimes.

SKSE for AE (2.x) reads the SKSEPlugin_Version export of every plugin. When that data says the plugin is version
independent (the Address Library bit, or the signature-scanning bit, of versionIndependence), SKSE loads it on any
AE runtime; when it does not, SKSE loads it only on the runtimes in its compatibleVersions list and tells everyone
else the DLL is "incompatible". World Map Selector for Controller 1.2.0 declared an explicit list ending at 1.6.1170
(src/PluginVersion.cpp), so a GOG 1.6.1179 player was refused although every address it uses comes from the Address
Library (Nexus report by btach, 2026-11-08). A plugin built with CommonLibSSE-NG's add_commonlibsse_plugin()
without COMPATIBLE_RUNTIMES, or with `.RuntimeCompatibility = SKSE::VersionIndependence::AddressLibrary`, passes.

Every *.dll under --path is read; a DLL with no SKSEPlugin_Version export (an SE-only plugin, a helper DLL) is
skipped. FAIL lines name the DLL and the runtimes it is pinned to.

package-gate runs it through the gate-rules row `skse-plugin-declares-address-library-not-a-runtime-list`
(kind package-script-passes), so it is called with --path <package> [--repo <repo>].

Usage: py -3 skse-runtime-declaration-gate.py --path <package or folder> [--repo X] [--report]
       --report prints every DLL's declaration, passing ones included.
"""
import argparse
import os
import struct
import sys

try:
    import pefile
except ImportError:  # pragma: no cover
    print("skse-runtime-declaration-gate: FAIL - python module pefile is missing (py -3 -m pip install pefile)")
    sys.exit(2)

# skse64 PluginAPI.h, SKSEPluginVersionData (dataVersion 1)
OFF_PLUGIN_VERSION = 0x004
OFF_NAME = 0x008
OFF_INDEP_EX = 0x304
OFF_INDEP = 0x308
OFF_COMPAT = 0x30C
SIZE = 0x350
ADDRESS_LIBRARY = 1 << 0
SIGNATURES = 1 << 1
STRUCTS_POST629 = 1 << 2


def runtime_str(v):
    return "%d.%d.%d" % ((v >> 24) & 0xFF, (v >> 16) & 0xFF, (v >> 4) & 0xFFF)


def read_declaration(dll):
    """Returns None when the DLL has no SKSEPlugin_Version export, else a dict."""
    pe = pefile.PE(dll, fast_load=True)
    pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"]])
    exports = getattr(pe, "DIRECTORY_ENTRY_EXPORT", None)
    if not exports:
        return None
    rva = None
    for sym in exports.symbols:
        if sym.name == b"SKSEPlugin_Version":
            rva = sym.address
            break
    if rva is None:
        return None
    data = pe.get_data(rva, SIZE)
    if len(data) < SIZE:
        raise ValueError("SKSEPlugin_Version data is shorter than 0x%X bytes" % SIZE)
    data_version, plugin_version = struct.unpack_from("<II", data, 0)
    name = data[OFF_NAME:OFF_NAME + 256].split(b"\0", 1)[0].decode("utf-8", "replace")
    indep = struct.unpack_from("<I", data, OFF_INDEP)[0]
    compat = [v for v in struct.unpack_from("<16I", data, OFF_COMPAT) if v and v != 0x01000000]  # CommonLib fills unused slots with 1.0.0
    return {
        "dataVersion": data_version,
        "name": name,
        "indep": indep,
        "addressLibrary": bool(indep & ADDRESS_LIBRARY),
        "signatures": bool(indep & SIGNATURES),
        "runtimes": [runtime_str(v) for v in compat],
    }


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True)
    ap.add_argument("--repo")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args(argv)
    root = os.path.normpath(a.path)
    dlls = []
    if os.path.isfile(root) and root.lower().endswith(".dll"):
        dlls = [root]
    else:
        for d, _, files in os.walk(root):
            dlls += [os.path.join(d, f) for f in files if f.lower().endswith(".dll")]
    fails = 0
    seen = 0
    for dll in sorted(dlls):
        rel = os.path.relpath(dll, root) if dll != root else os.path.basename(dll)
        try:
            decl = read_declaration(dll)
        except Exception as e:  # a DLL pefile cannot read is reported, not passed silently
            print("skse-runtime-declaration-gate: FAIL - %s could not be read: %s" % (rel, e))
            fails += 1
            continue
        if decl is None:
            continue
        seen += 1
        if decl["addressLibrary"] or decl["signatures"]:
            if a.report:
                print("skse-runtime-declaration-gate: ok   %s (%s): version independent (%s)" % (
                    rel, decl["name"], "Address Library" if decl["addressLibrary"] else "signature scanning"))
            continue
        fails += 1
        print("skse-runtime-declaration-gate: FAIL - %s (%s) is pinned to runtimes %s; SKSE refuses every other "
              "AE runtime as incompatible. Declare .RuntimeCompatibility = SKSE::VersionIndependence::AddressLibrary "
              "(or drop COMPATIBLE_RUNTIMES from add_commonlibsse_plugin)" % (rel, decl["name"], ", ".join(decl["runtimes"]) or "(none)"))
    if fails:
        return 1
    print("skse-runtime-declaration-gate: OK - %d SKSEPlugin_Version declaration(s), none pinned to a runtime list" % seen)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
