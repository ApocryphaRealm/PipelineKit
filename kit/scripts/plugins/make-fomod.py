"""Turn a packaged two-line build (package-mod.ps1 output: shared files at the root, Line-17\\ and Line-SE-AE16\\ with
the DLLs) into the FOMOD layout our two-line mods ship: Common\\ + Line-17\\ + Line-SE-AE16\\ + fomod\\ (the layout of
Character Progression Control 1.1.9). The game-version option is RECOMMENDED by the game the installer sees
(gameDependency 1.7.0.0 - Infinity UI 2.1.2 lesson, 2026-10-22), never a fixed Recommended. For a mod's FIRST FOMOD; later versions go through repack-fomod.ps1, which needs
a previous FOMOD package. Line-17 gets the CommonLibSSE-NG 7.2 licence files (GPL-3.0 + exceptions) and a NOTICE.txt.

    python make-fomod.py "<package folder>" --name "<Display Name>" --version X.Y.Z --repo <GitHub repo name>
        [--se-note "<extra SE/AE description>"] [--l17-note "<extra 1.7 description>"]
Writes "<package folder> FOMOD" next to it and removes the flat folder once the FOMOD is complete.
"""
import os, shutil, sys
sys.stdout.reconfigure(encoding="utf-8")
src = sys.argv[1]; args = sys.argv[2:]
def opt(k, d=""):
    return args[args.index(k) + 1] if k in args else d
name, ver, repo = opt("--name"), opt("--version"), opt("--repo")
assert name and ver and repo, "--name, --version and --repo are required"
dst = src + " FOMOD"
# the reference package sits in its game folder since 2026-10-01 - asked of distro-names.ps1, never joined by hand
# package_paths stays in the core scripts folder: put it on sys.path through the resolver of THIS tree (STEPS 5.10)
import subprocess as _sp
_r = _sp.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "resolvers", "resolve.py"), "find", "md-scripts"], capture_output=True, text=True)
_md_scripts = _r.stdout.strip()
if _r.returncode != 0 or not _md_scripts: sys.exit("make-fomod: cannot resolve role 'md-scripts'")
sys.path.insert(0, _md_scripts)
from package_paths import STAGE10, package_root
TEMPLATE = os.path.join(package_root(STAGE10, "Character Progression Control", "Skyrim"), "Character Progression Control 1.1.9 FOMOD", "Line-17")
assert os.path.isdir(TEMPLATE), f"the reference package is gone: {TEMPLATE}"
if os.path.exists(dst):
    shutil.rmtree(dst)
os.makedirs(os.path.join(dst, "Common")); os.makedirs(os.path.join(dst, "fomod"))
for entry in os.listdir(src):
    s = os.path.join(src, entry)
    if entry in ("Line-17", "Line-SE-AE16"):
        shutil.copytree(s, os.path.join(dst, entry))
    elif os.path.isdir(s):
        shutil.copytree(s, os.path.join(dst, "Common", entry))
    else:
        shutil.copy2(s, os.path.join(dst, "Common", entry))
for need in ("Line-17/SKSE/Plugins", "Line-SE-AE16/SKSE/Plugins"):
    assert os.path.isdir(os.path.join(dst, need)), f"missing {need}"
# the 1.7 line's licence files: the GPL text and CommonLibSSE-NG's exceptions, verbatim from the reference package
for f in ("LICENSE-GPL-3.0.txt", "CommonLibSSE-NG-EXCEPTIONS.md"):
    shutil.copy2(os.path.join(TEMPLATE, f), os.path.join(dst, "Line-17", f))
open(os.path.join(dst, "Line-17", "NOTICE.txt"), "w", encoding="utf-8").write(
    f"{name} {ver} - Skyrim 1.7.x build line\n\n"
    "This DLL statically links CommonLibSSE-NG 7.2.0 (https://github.com/alandtse/CommonLibSSE-NG, commit\n"
    "7a60f4de794095d7b0f8928d1b930a52e9a7da83), GPL-3.0-or-later WITH Modding Exception AND GPL-3.0 Linking Exception\n"
    "(CommonLibSSE-NG-EXCEPTIONS.md in this folder).\n\n"
    f"{name} as a whole - both build lines and its source - is Copyright (C) 2026 YOUR-NEXUS-NAME and licensed\n"
    "GPL-3.0-or-later (LICENSE-GPL-3.0.txt here; LICENSE and NOTICE.md with the common files).\n"
    f"Corresponding source: https://github.com/YOUR-ACCOUNT/{repo} (tag v{ver}). Third-party notices: THIRD_PARTY_NOTICES.md.\n")
esc = lambda t: t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
se_desc = "For Skyrim Special Edition 1.5.97 and Anniversary Edition 1.6.1170. Built on CommonLibSSE-NG 3.7.0, which reads Address Library formats 1 and 2." + (" " + opt("--se-note") if opt("--se-note") else "")
l17_desc = ("For Skyrim 1.7.99 and 1.7.104. Needs SKSE 2.3.x and Address Library All-in-One v13 or newer. Built on CommonLibSSE-NG 7.2.0; "
            "this DLL is distributed under GPL-3.0-or-later (licence texts install with it).") + (" " + opt("--l17-note") if opt("--l17-note") else "")
open(os.path.join(dst, "fomod", "ModuleConfig.xml"), "w", encoding="utf-8").write(f"""<?xml version="1.0" encoding="UTF-8"?>
<config xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://qconsulting.ca/fo3/ModConfig5.0.xsd">
	<moduleName>{esc(name)}</moduleName>
	<requiredInstallFiles>
		<folder source="Common" destination="" priority="0" />
	</requiredInstallFiles>
	<installSteps order="Explicit">
		<installStep name="Which Skyrim do you have?">
			<optionalFileGroups order="Explicit">
				<group name="Game version" type="SelectExactlyOne">
					<plugins order="Explicit">
						<plugin name="Skyrim SE 1.5.97 or AE 1.6.1170">
							<description>{esc(se_desc)}</description>
							<files>
								<folder source="Line-SE-AE16" destination="" priority="0" />
							</files>
							<typeDescriptor>
								<dependencyType>
									<defaultType name="Recommended" />
									<patterns>
										<pattern>
											<dependencies operator="And"><gameDependency version="1.7.0.0" /></dependencies>
											<type name="Optional" />
										</pattern>
									</patterns>
								</dependencyType>
							</typeDescriptor>
						</plugin>
						<plugin name="Skyrim 1.7.99 / 1.7.104 (current Steam version)">
							<description>{esc(l17_desc)}</description>
							<files>
								<folder source="Line-17" destination="" priority="0" />
							</files>
							<typeDescriptor>
								<dependencyType>
									<defaultType name="Optional" />
									<patterns>
										<pattern>
											<dependencies operator="And"><gameDependency version="1.7.0.0" /></dependencies>
											<type name="Recommended" />
										</pattern>
									</patterns>
								</dependencyType>
							</typeDescriptor>
						</plugin>
					</plugins>
				</group>
			</optionalFileGroups>
		</installStep>
	</installSteps>
</config>
""")
open(os.path.join(dst, "fomod", "info.xml"), "w", encoding="utf-8").write(f"""<?xml version="1.0" encoding="UTF-8"?>
<fomod>
	<Name>{esc(name)}</Name>
	<Author>YOUR-NEXUS-NAME</Author>
	<Version>{ver}</Version>
	<Website>https://github.com/YOUR-ACCOUNT/{repo}</Website>
	<Description>Pick the build for your Skyrim version: SE 1.5.97 / AE 1.6.1170, or Skyrim 1.7.99 / 1.7.104.</Description>
</fomod>
""")
shutil.rmtree(src)
for dp, dn, fn in os.walk(dst):
    for f in fn:
        print(os.path.relpath(os.path.join(dp, f), dst))
print("->", dst)
