#!/usr/bin/env python3
r"""Relicense one mod to GPL-3.0-or-later, preserving the upstream's notice rather than deleting it.

WHY
    Nexus moderation removed Lock Interaction Overhaul for carrying an MIT label beside GPL
    CommonLibSSE-NG 7.2 (logic library 4694). The owner's answer was a standing rule: every mod of
    ours is GPL-3.0-or-later, and relicensing an existing one is a licence-only rebuild - no boot
    test, because the code does not change.

    An audit on 2026-09-16 found six mods still shipping an MIT LICENSE while linking
    CommonLibSSE-NG and the SKSE Menu Framework header, both GPL-3.0. Three of them were published.

WHAT IT DOES
    * moves the existing LICENSE - which is usually the UPSTREAM author's MIT, naming THEIR
      copyright - into THIRD_PARTY_NOTICES.md, under a heading that says whose it is and why it is
      still here. The obligation to keep that notice does not go away when the work as a whole
      becomes GPL; deleting it would be the opposite of compliance.
    * writes the GPL-3.0 text as LICENSE.
    * writes or updates NOTICE.md with our copyright and the GPL notice.
    * sets "license" in vcpkg.json to GPL-3.0-or-later.

WHAT IT WILL NOT DO
    * touch a repo whose LICENSE is already GPL - it reports and stops, so re-running is safe;
    * throw away an upstream notice it cannot identify - if THIRD_PARTY_NOTICES.md already mentions
      the old licence text it leaves it alone rather than duplicating it;
    * build, package or bump. Those are the version gate's job and the owner's sequence.

Usage:  python relicense-gpl3.py <repo folder> [--holder "YOUR-NEXUS-NAME"] [--dry-run]
"""
import argparse
import io
import json
import os
import re

GPL_SOURCE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "LICENSE-GPL-3.0.txt")  # kit: the GPL text kit-install puts in .MD

NOTICE = """# Notice

{name}

Copyright (C) 2026 {holder}

This program is free software: you can redistribute it and/or modify it under the terms of the GNU
General Public License as published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without
even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
General Public License for more details. You should have received a copy of the GNU General Public
License along with this program. If not, see <https://www.gnu.org/licenses/>.

## Why this mod is GPL and not something more permissive

It links **CommonLibSSE-NG** (GPL-3.0-or-later with a modding exception) and builds against the
**SKSE Menu Framework** header, which is also GPL-3.0. A work that links GPL code is GPL, whatever
its own author would have preferred, so the licence is not a choice made here - it follows from what
the binary contains.

Notices that other people's code requires us to keep are in `THIRD_PARTY_NOTICES.md`, including the
licence this mod's upstream was published under.
"""

THIRD_HEADER = """# Third-party notices

Parts of this mod come from other people's work, and their licences require their notices to travel
with it. Relicensing the whole to GPL-3.0-or-later does not remove that obligation - it is why this
file exists.

"""

UPSTREAM_BLOCK = """## Upstream: {label}

This mod began as a fork of work published under the licence below. The work as a whole is now
GPL-3.0-or-later, because it links GPL libraries; this notice is preserved because the upstream's
licence requires it.

```
{text}
```

"""


def fail(msg):
    raise SystemExit("relicense-gpl3: " + msg)


def read(p):
    # utf-8-sig, because several of these vcpkg.json files carry a byte-order mark and plain
    # utf-8 makes json.loads fail on the first character - which silently skipped the licence
    # field on five repos the first time this ran.
    return io.open(p, encoding="utf-8-sig", errors="replace").read() if os.path.isfile(p) else None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--holder", default="YOUR-NEXUS-NAME")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    repo = os.path.abspath(a.repo)
    if not os.path.isdir(repo):
        fail("no such folder: " + repo)
    name = os.path.basename(repo)

    lic_path = os.path.join(repo, "LICENSE")
    old = read(lic_path)
    if old and re.search(r"GNU GENERAL PUBLIC LICENSE", old, re.I):
        print("%s: LICENSE is already GPL - nothing to do" % name)
        return

    gpl = read(GPL_SOURCE)
    if not gpl:
        fail("no GPL-3.0 text at %s to copy from" % GPL_SOURCE)

    third_path = os.path.join(repo, "THIRD_PARTY_NOTICES.md")
    third = read(third_path) or THIRD_HEADER
    actions = []

    if old:
        label = "MIT" if re.search(r"\bMIT\b", old) else "the licence below"
        m = re.search(r"Copyright \(c\)[^\n]*", old, re.I)
        if m:
            label = "%s (%s)" % (label, m.group(0).strip())
        first = old.strip().splitlines()[0][:60]
        if first and first in third:
            actions.append("upstream notice already in THIRD_PARTY_NOTICES.md - left alone")
        else:
            third = third.rstrip() + "\n\n" + UPSTREAM_BLOCK.format(label=label, text=old.strip())
            actions.append("moved the old LICENSE into THIRD_PARTY_NOTICES.md as '%s'" % label)
    else:
        actions.append("no existing LICENSE to preserve")

    notice_path = os.path.join(repo, "NOTICE.md")
    vcpkg_path = os.path.join(repo, "vcpkg.json")
    vcpkg_changed = False
    if os.path.isfile(vcpkg_path):
        try:
            data = json.loads(read(vcpkg_path))
            if data.get("license") != "GPL-3.0-or-later":
                data["license"] = "GPL-3.0-or-later"
                vcpkg_changed = True
        except Exception as e:
            actions.append("vcpkg.json could not be parsed (%s) - left alone" % e)
            data = None
    else:
        data = None

    if not a.dry_run:
        io.open(lic_path, "w", encoding="utf-8", newline="\n").write(gpl)
        io.open(third_path, "w", encoding="utf-8", newline="\n").write(third)
        io.open(notice_path, "w", encoding="utf-8", newline="\n").write(
            NOTICE.format(name=name, holder=a.holder))
        if vcpkg_changed:
            io.open(vcpkg_path, "w", encoding="utf-8", newline="\n").write(
                json.dumps(data, indent=2) + "\n")

    actions.append("LICENSE -> GPL-3.0")
    actions.append("NOTICE.md written")
    if vcpkg_changed:
        actions.append('vcpkg.json license -> "GPL-3.0-or-later"')
    print("%s%s" % (name, "   (dry run)" if a.dry_run else ""))
    for x in actions:
        print("   " + x)


if __name__ == "__main__":
    main()
