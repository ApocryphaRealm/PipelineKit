r"""Make a mod's 1920x1080 Nexus feature banners from in-game screenshots, each one HIGHLIGHTING what its line is about.

The owner, 2026-10-05, on AMF's reshoot banners: put "a highlight over an area to emphasize what it's referring to in the
banner" - "the categories the sort makes ... looks identical to a different banner but it doesn't emphasize what it's
talking about which is the left pane separators." So every banner names its subject on the picture, and this tool
REFUSES a banner that does not: each spec entry carries a highlight region, or says "whole": true when the subject really
is the whole screen (memory banners-highlight-what-they-show).

    python make-feature-banners.py "<distro folder>" <spec.json> [--template <banner html>] [--only <slug>]

spec.json:
    { "pill": "v2.1.1",
      "banners": [
        { "src": "<screenshot path>", "slug": "categories-folded",
          "feature": "2.1.0 - The categories the sort makes",
          "tagline": "Combat, Interface, Gameplay ... fold a category to one line with a count of what it holds.",
          "highlight": [x0, y0, x1, y1],            # in the screenshot's own pixels; or a list of such boxes
          "dim": 0.45 },                            # optional: how much the rest darkens (0 = not at all) - keep it
                                                    # light when the picture behind IS the point (a see-through menu)
        { ..., "whole": true } ] }

Layout (the approved one): the WHOLE screenshot, uncropped, in a 16:9 pane; feature line and tagline below; pills.
The template is any earlier banner of the same layout (its <!-- Real in-game picture ... --> pane is replaced); by
default the first banner-1920x1080-*.html in the folder that has one. Output: banner-1920x1080-<slug>.html and
mod-page-banner-1920x1080-<slug>.png in the distro folder; the screenshot is copied to assets\.

The pane is found by PARSING the template (html.parser), not by a regex (2026-10-12): the old pattern stopped at the
first "</div>" after the comment, which is the template's first highlight box - so a template with two or more boxes
left the extra ones, and the pane's own closing tag, on the new banner as stray boxes. The whole pane is now replaced,
every highlight the template carries is removed, and the result is checked before it is written: exactly the spec's
boxes, all inside the pane, which declares its count in data-highlights (gate row distro-banner-highlights-match-their-spec).
"""
import html
import json
import os
import re
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from typing import NoReturn

from PIL import Image

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PANE_W, PANE_H, PANE_TOP = 1136, 639, 176
PANE_MARK = "<!-- Real in-game picture"


def die(msg) -> NoReturn:
    print("STOP: " + msg)
    sys.exit(1)


class _Divs(HTMLParser):
    """Every <div> of a document as [start, end, is_highlight, depth], end being the offset just past its matching
    </div> (None while unclosed), plus the offsets of </div> tags that close nothing."""

    def __init__(self, text):
        super().__init__(convert_charrefs=False)
        self.text = text
        self.line_starts = [0] + [i + 1 for i, ch in enumerate(text) if ch == "\n"]
        self.divs, self.stack, self.orphans = [], [], []
        self.feed(text)
        self.close()

    def _offset(self):
        line, col = self.getpos()
        return self.line_starts[line - 1] + col

    def handle_starttag(self, tag, attrs):
        if tag != "div":
            return
        classes = (dict(attrs).get("class") or "").split()
        d = [self._offset(), None, "hl" in classes, len(self.stack)]
        self.divs.append(d)
        self.stack.append(d)

    def handle_endtag(self, tag):
        if tag != "div":
            return
        at = self._offset()
        end = self.text.index(">", at) + 1
        if self.stack:
            self.stack.pop()[1] = end
        else:
            self.orphans.append(at)


def find_pane(text):
    """The picture pane: (start, end, highlights). start is its <!-- Real in-game picture --> comment, end is just past
    the </div> that closes the first <div> after it (and the newline after that), highlights counts the highlight boxes
    inside it. None when the document has no such pane, or the pane is never closed."""
    start = text.find(PANE_MARK)
    if start < 0:
        return None
    divs = _Divs(text)
    pane = next((d for d in divs.divs if d[0] > start), None)
    if pane is None or pane[1] is None:
        return None
    end = pane[1] + (1 if text[pane[1]:pane[1] + 1] == "\n" else 0)
    inside = sum(1 for d in divs.divs if d[2] and pane[0] < d[0] < pane[1])
    return start, end, inside


def stray_highlights(text):
    """Highlight boxes outside the picture pane, and </div> tags that close nothing - what the old regex left behind."""
    pane = find_pane(text)
    divs = _Divs(text)
    lo, hi = (pane[0], pane[1]) if pane else (-1, -1)
    return [d for d in divs.divs if d[2] and not (lo < d[0] < hi)], divs.orphans


def strip_template(tpl):
    """The template with its pane intact and every highlight box OUTSIDE the pane removed, together with a </div> that
    closes nothing directly after the pane - the leftovers of a banner the old regex made from a multi-box template."""
    pane = find_pane(tpl)
    if pane is None:
        return tpl
    strays, orphans = stray_highlights(tpl)
    cuts = [(d[0], d[1]) for d in strays if d[1] is not None]
    # The document closes divs it never opened: the old regex left the old pane's own </div> right after the new pane
    # (after any stray boxes), one more each time a banner was made from such a banner. The parser pins the orphans on
    # the LAST </div>s, so find the leftovers by position - the run of </div> straight after the pane, one per orphan.
    at, left = pane[1], len(orphans)
    while left:
        while at < len(tpl) and tpl[at].isspace():
            at += 1
        nxt = next(((s, e) for s, e in cuts if s == at), None)
        if nxt is not None:
            at = nxt[1]
        elif tpl.startswith("</div>", at):
            cuts.append((at, at + len("</div>")))
            at += len("</div>")
            left -= 1
        else:
            break
    for s, e in sorted(cuts, reverse=True):
        ls = tpl.rfind("\n", 0, s) + 1                       # take the whole line when the element is alone on it
        le = tpl.find("\n", e)
        le = len(tpl) if le < 0 else le + 1
        if not tpl[ls:s].strip() and not tpl[e:le].strip():
            s, e = ls, le
        tpl = tpl[:s] + tpl[e:]
    return tpl


def boxes_of(entry):
    hl = entry.get("highlight")
    if not hl:
        return []
    return [hl] if isinstance(hl[0], (int, float)) else hl


def pane_html(asset, src_name, size, boxes, dim_amount=0.45):
    w, h = size
    scale = min(PANE_W / w, PANE_H / h)                      # object-fit: contain
    ox, oy = (PANE_W - w * scale) / 2, (PANE_H - h * scale) / 2
    marks = []
    for x0, y0, x1, y1 in boxes:
        if not (0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h):
            die(f"highlight {x0, y0, x1, y1} is outside the {w}x{h} picture {src_name}")
        l, t = ox + x0 * scale, oy + y0 * scale
        bw, bh = (x1 - x0) * scale, (y1 - y0) * scale
        # The outline, with the rest of the picture dimmed by the box's own shadow - one mark per box. With more than
        # one box the dimming overlaps, so only the first darkens the picture.
        dim = f"0 0 0 2000px rgba(0,0,0,{dim_amount}), " if not marks and dim_amount > 0 else ""
        marks.append(f'      <div class="hl" style="position:absolute; left:{l:.0f}px; top:{t:.0f}px; width:{bw:.0f}px; height:{bh:.0f}px; '
                     f'border:3px solid #e8c766; border-radius:6px; box-shadow:{dim}0 0 18px 4px rgba(232,199,102,0.75); pointer-events:none;"></div>')
    return ("<!-- Real in-game picture (banner rule, 2026-08-30): " + src_name + ", the WHOLE picture, uncropped, in a 16:9 pane.\n"
            "         Highlight (the owner, 2026-10-05): " + ("the boxes below mark what the banner's line is about" if boxes else "none - the subject is the whole screen") + ". -->\n"
            f'    <div data-generator="make-feature-banners" data-highlights="{len(marks)}" style="position:absolute; left:50%; top:{PANE_TOP}px; transform:translateX(-50%); width:{PANE_W}px; height:{PANE_H}px; '
            'border:2px solid #f5f2e9; overflow:hidden; z-index:2; background:#000;">\n'
            f'      <img src="assets/{asset}" style="width:100%; height:100%; object-fit:contain;" />\n'
            + "\n".join(marks) + ("\n" if marks else "") +
            "    </div>\n")


def build_html(tpl, b, asset, src_name, size, pill=None):
    """The banner HTML for spec entry b from template text tpl: the template's whole pane - every highlight box it held
    included - replaced by the new one, any leftover box outside it removed, then the feature line, tagline and pill.
    Refuses (STOP) a result that does not hold exactly b's boxes, all inside the pane."""
    tpl = strip_template(tpl)
    pane = find_pane(tpl)
    if pane is None:
        die("the template has no closed <!-- Real in-game picture --> pane")
    boxes = boxes_of(b)
    t = tpl[:pane[0]] + pane_html(asset, src_name, size, boxes, float(b.get("dim", 0.45))) + tpl[pane[1]:]
    t = re.sub(r'(letter-spacing:0\.18em; text-transform:uppercase;">)[^<]*(</div>)',
               lambda m: m.group(1) + html.escape(b["feature"], quote=False) + m.group(2), t, count=1)
    t = re.sub(r'(<div class="tagline"[^>]*>)[^<]*(</div>)',
               lambda m: m.group(1) + html.escape(b["tagline"], quote=False) + m.group(2), t, count=1)
    if pill:
        t = re.sub(r'(<div class="pill">)v\d+\.\d+\.\d+(</div>)', lambda m: m.group(1) + pill + m.group(2), t, count=1)
    got = find_pane(t)
    strays, orphans = stray_highlights(t)
    if got is None or got[2] != len(boxes) or strays or orphans:
        die(f"{b.get('slug', '?')}: the built banner has {got[2] if got else 'no'} highlight(s) in its pane, {len(strays)} "
            f"outside it and {len(orphans)} unmatched </div> - the spec asks for {len(boxes)}")
    return t


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        die(__doc__)
    folder, spec_path = args[0], args[1]
    template = args[args.index("--template") + 1] if "--template" in args else None
    only = args[args.index("--only") + 1] if "--only" in args else None
    spec = json.load(open(spec_path, encoding="utf-8"))
    banners = spec["banners"]
    # The gate: every banner says what it shows, or says it is the whole screen.
    bad = [b.get("slug", "?") for b in banners if not boxes_of(b) and not b.get("whole")]
    if bad:
        die("these banners have no highlight and are not marked \"whole\": " + ", ".join(bad))
    if template is None:
        for name in sorted(os.listdir(folder)):
            if name.startswith("banner-1920x1080-") and name.endswith(".html"):
                if find_pane(open(os.path.join(folder, name), encoding="utf-8").read()):
                    template = os.path.join(folder, name)
                    break
    if not template:
        die("no template banner with a <!-- Real in-game picture --> pane; pass --template")
    tpl = open(template, encoding="utf-8").read()
    pill = spec.get("pill")
    for b in banners:
        if only and b["slug"] != only:
            continue
        src = b["src"]
        asset = "banner-src-" + b["slug"] + os.path.splitext(src)[1].lower()
        shutil.copy2(src, os.path.join(folder, "assets", asset))
        size = Image.open(src).size
        t = build_html(tpl, b, asset, os.path.basename(src), size, pill)
        h = os.path.join(folder, f"banner-1920x1080-{b['slug']}.html")
        p = os.path.join(folder, f"mod-page-banner-1920x1080-{b['slug']}.png")
        open(h, "w", encoding="utf-8", newline="").write(t)
        subprocess.run([EDGE, "--headless", "--disable-gpu", "--hide-scrollbars", "--window-size=1920,1080", f"--screenshot={p}", h],
                       capture_output=True, timeout=120)
        if Image.open(p).size != (1920, 1080):
            die(f"{p} did not render at 1920x1080")
        print("made", b["slug"], "(highlight: " + (str(len(boxes_of(b))) + " box(es)" if boxes_of(b) else "whole screen") + ")")


if __name__ == "__main__":
    main()
