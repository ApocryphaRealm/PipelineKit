"""THE THEME OUTLINE GATE (2026-10-12, AMF Skyrim after 2.1.9).

The owner, on Norden - Black: "the button faces don't have any kind of outline at all, even a basic one. But everything
should have a basic minimal outline so that it's at least visible." A control's face sits on the panel colour at rest, so
it is told from the panel by its outline alone - the theme's border line. A theme whose border is thin to nothing,
transparent, or too close to its panel colour leaves every button, box and tick box invisible.

AMF's theme::Apply falls back to the text colour at run time when this happens; this gate keeps a SHIPPED theme from ever
needing the fallback. Every theme INI in the package (any `themes\\*.ini` holding a [Theme] section) must have:
  * fBorderThickness above 0 (when given);
  * a border colour (sBorder, else sFrame - AMF's own order) whose contrast is at least MIN_CONTRAST, alpha included,
    against the control face (sBackground drawn over black: faces are the panel colour at rest) AND against the window
    background as drawn - the theme's background art (sBackgroundArt, assets\\backgrounds\\<name>.png beside themes\\)
    over that colour, taken at its darker tone (the 10th percentile of the line's contrast across the art), since the line
    crosses the art's grain. The sum is AMF's (Theme.cpp OutlineContrast): WCAG contrast ratio of relative luminances,
    1 = identical, 21 = black on white.

MIN_CONTRAST is 4.5 (v4, the owner 2026-10-12: outlines "faint" in Oblivion and Dear Diary, "at least visible"; was 2.0).
WCAG's 3:1 (non-text contrast, 1.4.11) is the floor for a component boundary, but this outline is a one-pixel hairline
that does not grow with the display, and a stroke that thin reads like text, so it is held to text's 4.5:1 (1.4.3). At
3:1 both themes reported faint would still have passed (Dear Diary 3.4, Oblivion 3.6 on its parchment's grain).

Usage:
  python theme-outline-gate.py --path <package or folder> [--repo <repo>]
Exit 1 on any hit; each hit is printed as a FAIL line.
"""
import argparse, os, re, sys

MIN_CONTRAST = 4.5   # Theme.cpp kMinOutlineContrast
ART_PERCENTILE = 0.10   # the art's darker tone: the line's contrast at this fraction of the art's pixels, lowest first


def parse_colour(text):
    """#RRGGBB or #RRGGBBAA (AMF's ParseColor) -> (r, g, b, a) in 0..1, or None."""
    m = re.fullmatch(r'#?([0-9A-Fa-f]{6})([0-9A-Fa-f]{2})?', (text or '').strip())
    if not m:
        return None
    rgb = m.group(1)
    a = int(m.group(2), 16) / 255.0 if m.group(2) else 1.0
    return (int(rgb[0:2], 16) / 255.0, int(rgb[2:4], 16) / 255.0, int(rgb[4:6], 16) / 255.0, a)


def over(top, under):
    a = max(0.0, min(1.0, top[3]))
    return tuple(top[i] * a + under[i] * (1.0 - a) for i in range(3)) + (1.0,)


def luminance(c):
    lin = lambda v: v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2])


def outline_contrast(line, face, panel):
    panel = over(panel, (0.0, 0.0, 0.0, 1.0))
    face = over(face, panel)
    l1, l2 = luminance(over(line, face)), luminance(face)
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)


def art_contrast(line, panel, art_path):
    """The line's contrast against the background art drawn over the panel, at its darker tone; None when the art cannot
    be read (no file, or Pillow missing - then only the colour is checked, and a NOTE says so)."""
    if not art_path or not os.path.isfile(art_path):
        return None
    try:
        from PIL import Image
    except ImportError:
        print(f'NOTE theme-outline-gate: Pillow is not installed, {os.path.basename(art_path)} is not measured')
        return None
    im = Image.open(art_path).convert('RGBA')
    im.thumbnail((128, 128))
    base = over(panel, (0.0, 0.0, 0.0, 1.0))
    cs = []
    for q in (im.get_flattened_data() if hasattr(im, 'get_flattened_data') else im.getdata()):
        a = q[3] / 255.0
        tone = tuple(q[i] / 255.0 * a + base[i] * (1.0 - a) for i in range(3)) + (1.0,)
        cs.append(outline_contrast(line, tone, tone))
    cs.sort()
    return cs[int(len(cs) * ART_PERCENTILE)] if cs else None


def read_ini(p):
    b = open(p, 'rb').read()
    if b[:2] in (b'\xff\xfe', b'\xfe\xff'):
        t = b.decode('utf-16')
    else:
        t = b.decode('utf-8-sig', errors='replace')
    section, out = None, {}
    for raw in t.splitlines():
        line = raw.strip()
        if not line or line.startswith(';') or line.startswith('#'):
            continue
        if line.startswith('[') and line.endswith(']'):
            section = line[1:-1].strip().lower()
            continue
        if section == 'theme' and '=' in line:
            k, v = line.split('=', 1)
            out[k.strip()] = v.split(';', 1)[0].strip()
    return out if section is not None or out else None


def check_theme(path):
    """The hits for one theme INI (empty = passes), or None when the file is not a theme."""
    keys = read_ini(path)
    if not keys or 'sBackground' not in keys:
        return None   # not an AMF menu theme (Dragon's Eye Minimap's compass themes also use [Theme], with other keys)
    name = keys.get('sName') or os.path.basename(path)
    hits = []
    thick = keys.get('fBorderThickness')
    if thick is not None:
        try:
            if float(thick) <= 0.0:
                hits.append(f'{name}: fBorderThickness={thick} - the controls get no outline')
        except ValueError:
            hits.append(f'{name}: fBorderThickness={thick!r} is not a number')
    panel = parse_colour(keys.get('sBackground'))
    line = parse_colour(keys.get('sBorder')) or parse_colour(keys.get('sFrame'))
    if panel is None:
        hits.append(f'{name}: no readable sBackground')
    elif line is None:
        hits.append(f'{name}: no readable sBorder or sFrame - the outline colour is unknown')
    else:
        c = outline_contrast(line, panel, panel)   # faces are the panel colour at rest (Theme.cpp kRoleBoxes)
        if c < MIN_CONTRAST:
            hits.append(f'{name}: the border {keys.get("sBorder") or keys.get("sFrame")} on the face / panel {keys.get("sBackground")} '
                        f'has contrast {c:.2f}, below {MIN_CONTRAST} - controls would have no clearly visible outline')
        art = keys.get('sBackgroundArt')
        if art:
            p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(path))), 'assets', 'backgrounds', art + '.png')
            ca = art_contrast(line, panel, p)
            if ca is not None and ca < MIN_CONTRAST:
                hits.append(f'{name}: the border {keys.get("sBorder") or keys.get("sFrame")} on the background art {art} over '
                            f'{keys.get("sBackground")} has contrast {ca:.2f} at its darker tone, below {MIN_CONTRAST} - '
                            'controls would have no clearly visible outline')
    return hits


def check(root):
    hits = []
    for dp, _, files in os.walk(root):
        if os.sep + '.git' in dp or os.path.basename(dp).lower() != 'themes':
            continue
        for f in files:
            if not f.lower().endswith('.ini'):
                continue
            p = os.path.join(dp, f)
            r = check_theme(p)
            for h in r or []:
                hits.append(f'FAIL {os.path.relpath(p, root)}: {h}')
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--path', required=True)
    ap.add_argument('--repo')
    a = ap.parse_args()
    hits = check(a.path)
    for h in hits:
        print(h)
    return 1 if hits else 0


if __name__ == '__main__':
    sys.exit(main())
