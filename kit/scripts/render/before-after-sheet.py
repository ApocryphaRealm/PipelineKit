#!/usr/bin/env python3
r"""before-after-sheet.py - the side-by-side review sheet every design revision is shown on (role before-after-sheet,
2026-11-18; generalised from the Nordic Ebony full-3D set's render_set.py / sheet_set.py, which stay in that repo).

The owner's standard: every revision he is shown carries a before / after side by side, with the same camera and light;
when he marked up a picture, the row is original / his marks / result. This tool lays out any number of rows of two
or more pictures each, labelled, and - with Blender - renders the before and after NIFs itself, framed identically.

    py -3 before-after-sheet.py sheet --out <sheet.jpg> [--title "..."] [--labels "Before,After"]
                                      --row "<label>|<before.png>|<after.png>[|<third.png>]" [--row ...]
    py -3 before-after-sheet.py render --out <dir> --before <nif> --before-tex <data folder>
                                       --after <nif> --after-tex <data folder> [--name <piece>] [--yaw 0] [--up z|y]
                                       [--prefix textures\mymod] [--size 900x1200] [--samples 48] [--title "..."]
    py -3 before-after-sheet.py --self-test

sheet: one sheet; a row whose pictures are wide (more than 1.6 x as wide as tall: a weapon lying flat) stacks its
pictures one above the other, any other row sets them side by side; every picture of a row is scaled to one height
(or width) so the pair compares at the same size. Labels: --labels names the columns ("Before,After" by default;
"Original,Marks,Result" for a marked-up revision).
render: render_lib renders <name>-before.png and <name>-after.png with ONE camera fitted to both (same_frame), then
makes <name>-before-after.jpg. Without Blender (or without PyNifly in it) it prints SKIP and exits 3, writing nothing.
Exit: 0 written, 1 a picture missing or unreadable, 2 usage, 3 SKIP (no Blender / PyNifly).
"""
import argparse, os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
BG = (34, 34, 36); TX = (235, 235, 235); AC = (225, 200, 120); P = 14


def font(size):
    from PIL import ImageFont
    for name in ("arialbd.ttf", "DejaVuSans-Bold.ttf"):
        try: return ImageFont.truetype(name, size)
        except OSError: pass
    try: return ImageFont.load_default(size=size)
    except TypeError: return ImageFont.load_default()


def make_sheet(rows, out, title="", labels=("Before", "After"), height=900):
    """rows: [(label, [image paths])]. Returns the problems (empty = written)."""
    from PIL import Image, ImageDraw
    bad, laid = [], []
    for label, paths in rows:
        ims = []
        for p in paths:
            try:
                with Image.open(p) as im0: ims.append(im0.convert("RGB"))
            except Exception as e: bad.append(f"{label}: {p} unreadable ({e})")
        if len(ims) < 2 and not bad: bad.append(f"{label}: a row needs two pictures or more, it has {len(ims)}")
        laid.append((label, ims))
    if bad: return bad
    blocks = []
    for label, ims in laid:
        wide = ims[0].width > ims[0].height * 1.6
        if wide:                                                     # stacked: one width
            Wt = max(im.width for im in ims); Wt = min(Wt, 2200)
            ims = [im.resize((Wt, max(1, round(im.height * Wt / im.width)))) for im in ims]
            Hb = 40 + sum(im.height + 34 for im in ims); Wb = Wt + 2 * P
        else:                                                        # side by side: one height
            Ht = min(height, max(im.height for im in ims))
            ims = [im.resize((max(1, round(im.width * Ht / im.height)), Ht)) for im in ims]
            Hb = 40 + 30 + Ht + P; Wb = P + sum(im.width + P for im in ims)
        blocks.append((label, ims, wide, Wb, Hb))
    W = max([b[3] for b in blocks] + [900]); H = (60 if title else 14) + sum(b[4] for b in blocks) + P
    S = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(S); y = 14
    if title: d.text((P, y), title, fill=TX, font=font(24)); y = 60
    for label, ims, wide, Wb, Hb in blocks:
        d.text((P, y), label, fill=TX, font=font(20)); y += 40
        if wide:
            for i, im in enumerate(ims):
                d.text((P, y), labels[i] if i < len(labels) else f"#{i + 1}", fill=AC, font=font(17)); S.paste(im, (P, y + 26)); y += im.height + 34
        else:
            x = P
            for i, im in enumerate(ims):
                d.text((x, y), labels[i] if i < len(labels) else f"#{i + 1}", fill=AC, font=font(17)); S.paste(im, (x, y + 30)); x += im.width + P
            y += 30 + ims[0].height + P
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    S.save(out, quality=90)
    return []


def cmd_sheet(a):
    rows = []
    for r in a.row:
        parts = r.split("|")
        if len(parts) < 3: print(f"before-after-sheet: --row needs <label>|<a>|<b>: {r!r}"); return 2
        rows.append((parts[0], parts[1:]))
    if not rows: print("before-after-sheet: give at least one --row"); return 2
    bad = make_sheet(rows, a.out, a.title or "", [x.strip() for x in a.labels.split(",")])
    for b in bad: print("before-after-sheet: " + b)
    if bad: return 1
    print(f"before-after-sheet: wrote {a.out} ({len(rows)} row(s))"); return 0


def cmd_render(a):
    import render_lib
    ok, why = render_lib.pynifly_ok()
    if not ok:
        print(f"before-after-sheet: SKIP - {why}; nothing rendered"); return 3
    W, H = (int(x) for x in a.size.lower().split("x"))
    name = a.name or os.path.splitext(os.path.basename(a.after))[0]
    shots = {name + "-before": ([a.before], a.yaw, a.up), name + "-after": ([a.after], a.yaw, a.up)}
    os.makedirs(a.out, exist_ok=True)
    # the two sides are rendered from their own data folders, so each NIF wears its own textures
    for side, nif, tex in (("before", a.before, a.before_tex), ("after", a.after, a.after_tex)):
        if not os.path.isfile(nif): print(f"before-after-sheet: no {side} NIF {nif}"); return 1
    work = tempfile.mkdtemp(prefix="before-after-")
    if os.path.normcase(os.path.abspath(a.before_tex)) == os.path.normcase(os.path.abspath(a.after_tex)):
        # one data folder: one Blender run, one camera fitted to both sides
        render_lib.render(shots, [a.after_tex], work, a.prefix, (W, H), same_frame=[list(shots)], samples=a.samples)
    else:
        _render_two(render_lib, shots, a, work, (W, H))
    out_imgs = []
    for k in shots:
        src = os.path.join(work, k + ".png")
        if not os.path.isfile(src): print(f"before-after-sheet: Blender wrote no {k}.png"); return 1
        # flattened on the backdrop, NOT cropped: a crop per side would undo the shared camera
        from PIL import Image
        with Image.open(src) as im0: im = im0.convert("RGBA")
        flat = Image.new("RGB", im.size, (38, 39, 42)); flat.paste(im, (0, 0), im)
        dst = os.path.join(a.out, k + ".png"); flat.save(dst); out_imgs.append(dst)
    sheet = os.path.join(a.out, name + "-before-after.jpg")
    bad = make_sheet([(name, out_imgs)], sheet, a.title or f"{name}: before | after (same camera and light)")
    for b in bad: print("before-after-sheet: " + b)
    if bad: return 1
    print(f"before-after-sheet: wrote {sheet}"); return 0


def _render_two(render_lib, shots, a, work, size):
    """before and after from DIFFERENT data folders. render_lib looks a texture up in its roots in order, so the pair is
    rendered twice with the roots swapped and each side is kept from the run whose roots start with its own folder.
    Both runs hold both NIFs in one same_frame group, so the camera is identical in each."""
    wa, wb = os.path.join(work, "a"), os.path.join(work, "b")
    render_lib.render(shots, [a.before_tex, a.after_tex], wa, a.prefix, size, same_frame=[list(shots)], samples=a.samples)
    render_lib.render(shots, [a.after_tex, a.before_tex], wb, a.prefix, size, same_frame=[list(shots)], samples=a.samples)
    import shutil
    b_, f_ = list(shots)
    shutil.copy2(os.path.join(wa, b_ + ".png"), os.path.join(work, b_ + ".png"))
    shutil.copy2(os.path.join(wb, f_ + ".png"), os.path.join(work, f_ + ".png"))


def self_test():
    from PIL import Image
    res = {}
    with tempfile.TemporaryDirectory() as t:
        def pic(name, w, h, c):
            p = os.path.join(t, name); Image.new("RGB", (w, h), c).save(p); return p
        a, b, c = pic("a.png", 300, 400, (90, 90, 90)), pic("b.png", 600, 800, (160, 150, 120)), pic("c.png", 300, 400, (200, 60, 60))
        wa, wb = pic("wa.png", 900, 200, (90, 90, 90)), pic("wb.png", 900, 200, (160, 150, 120))
        out = os.path.join(t, "s.jpg")
        res["two upright pictures side by side"] = (len(make_sheet([("helmet", [a, b])], out, "t")) == 0 and os.path.isfile(out), True)
        with Image.open(out) as im: res["side by side: wider than tall"] = (im.width > im.height, True)
        out2 = os.path.join(t, "w.jpg")
        res["wide pictures stacked"] = (len(make_sheet([("sword", [wa, wb])], out2)) == 0, True)
        with Image.open(out2) as im2: res["stacked: taller than one picture"] = (im2.height > 2 * 200, True)
        res["original / marks / result row"] = (len(make_sheet([("plate", [a, c, b])], os.path.join(t, "m.jpg"), "", ("Original", "Marks", "Result"))) == 0, True)
        res["a missing picture refuses"] = (len(make_sheet([("x", [a, os.path.join(t, "none.png")])], os.path.join(t, "n.jpg"))) > 0, True)
        res["a one-picture row refuses"] = (len(make_sheet([("x", [a])], os.path.join(t, "o.jpg"))) > 0, True)
    ok = all(g == w for g, w in res.values())
    print("self-test", "PASS" if ok else "FAIL", {k: f"{g} (want {w})" for k, (g, w) in res.items()})
    return 0 if ok else 1


def main(argv):
    if argv[:1] == ["--self-test"]: return self_test()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("sheet"); s.add_argument("--out", required=True); s.add_argument("--title"); s.add_argument("--labels", default="Before,After")
    s.add_argument("--row", action="append", default=[])
    r = sub.add_parser("render"); r.add_argument("--out", required=True); r.add_argument("--before", required=True); r.add_argument("--before-tex", required=True)
    r.add_argument("--after", required=True); r.add_argument("--after-tex", required=True); r.add_argument("--name"); r.add_argument("--yaw", type=float, default=0.0)
    r.add_argument("--up", default="z", choices=("z", "y")); r.add_argument("--prefix", action="append", default=[]); r.add_argument("--size", default="900x1200")
    r.add_argument("--samples", type=int, default=48); r.add_argument("--title")
    a = ap.parse_args(argv)
    if a.cmd == "sheet": return cmd_sheet(a)
    if a.cmd == "render": return cmd_render(a)
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
