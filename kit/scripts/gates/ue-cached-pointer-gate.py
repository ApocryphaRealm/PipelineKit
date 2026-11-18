r"""UE4SS C++ source gate: a UObject pointer kept in a global must be checked alive before use (role ue-cached-pointer-gate).

WHY: the same crash class is in the past-mistakes library four times across two games - "A UObject pointer kept
across frames crashed the game once the game rebuilt the object" (NorseRealtimeNative 0.2.1), "A UObject pointer
cached across frames crashes once its actor is destroyed" (Norse UE4SS frameworks), "A UObject kept by object-array
slot AND pointer still went stale" (Oblivion Remastered menu), "A runtime-built UMG widget taken off the viewport is
garbage collected". A pointer stored past the frame it was found in is only safe through the slot + pointer + flags
check (Ue.hpp IndexOf / Alive).

Rule: every g_* global (or static) that holds a UObject-derived pointer - plain, or inside a std container - must be
named on some line of the same file together with Alive( / IndexOf( / IsValid( (the slot is kept and checked), or
carry one of these markers in a comment on its declaration line, each a claim a reviewer can check:
  key-only       compared, never dereferenced (a set of points used as keys)
  lives-forever  a class default object (Default__...) or a UClass - never collected while the game runs
  owned          an actor we spawned and only we destroy, cleared at map load
  alive-checked  checked through a companion slot map (name it: "alive-checked via g_xIx")
Long-lived reflection objects (UClass, UFunction, UScriptStruct, FProperty, UEnum) typed as such are exempt.

Usage: py -3 ue-cached-pointer-gate.py --repo <repo folder> [--path <ignored, package-gate passes it>]   exit 1 on a hit
"""
import argparse
import glob
import os
import re
import sys

TYPES = r"(?:UObject|AActor|APawn|ACharacter|AController|APlayerController|UUserWidget|UWidget|UActorComponent|" \
        r"USceneComponent|UWorld|ULevel|AGameModeBase|AGameStateBase|UAnimInstance|UAnimMontage|UTexture\w*|UMaterial\w*)"
DECL = re.compile(r"^\s*(?:static\s+|inline\s+)*(?:std::\w+<[^;=]*\b" + TYPES + r"\s*\*[^;=]*>|" + TYPES +
                  r"\s*\*)\s+(g_\w+)\b")
CHECK = re.compile(r"\b(?:Alive|IndexOf|IsValid|IsAlive)\s*\(")

ap = argparse.ArgumentParser()
ap.add_argument("--repo")
ap.add_argument("--path")
a = ap.parse_args()
if not a.repo or not os.path.isdir(os.path.join(a.repo, "src")):
    print("ue-cached-pointer-gate: no repo source to read - not checked")
    sys.exit(0)
files = [f for ext in ("cpp", "hpp", "h", "inl", "inc") for f in glob.glob(os.path.join(a.repo, "src", "**", "*." + ext), recursive=True)]
hits = []
for f in files:
    lines = open(f, encoding="utf-8", errors="replace").read().splitlines()
    for i, line in enumerate(lines):
        m = DECL.match(line)
        if not m or re.search(r"//.*\b(key-only|lives-forever|owned|alive-checked)\b", line):
            continue
        name = m.group(1)
        if not any(name in l and CHECK.search(l) for l in lines):
            hits.append("%s:%d  %s  - kept across frames with no Alive/IndexOf check (or mark it key-only / "
                        "lives-forever / owned / alive-checked, if true)"
                        % (os.path.relpath(f, a.repo), i + 1, name))
for h in hits:
    print("HIT  " + h)
print("ue-cached-pointer-gate: %s - %d file(s), %d unchecked cached pointer(s)" % (os.path.basename(a.repo.rstrip("\\/")),
                                                                                   len(files), len(hits)))
sys.exit(1 if hits else 0)
