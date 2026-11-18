"""patternlib.crossings - find where strand centre lines cross, and give every crossing an over and an under so each
strand goes over, under, over, under... along its whole length.

The assignment is a 2-colouring: every PASS (one strand going through one crossing) is over or under; the two passes of
a crossing differ, and consecutive passes along a strand differ (cyclically on a closed strand). A planar diagram can
always be coloured so; when the graph is not 2-colourable (an odd cycle) the conflict count is returned and the
alternation validator refuses. Deterministic: strands and passes are visited in index order, the first pass is over."""
from collections import deque
import numpy as np
from scipy.spatial import cKDTree
from .model import Crossing


def _segments(strands):
    A, B, S, I = [], [], [], []
    for si, s in enumerate(strands):
        P = s.pts; n = len(P)
        if n < 2: continue
        j = np.arange(n if s.closed else n - 1); A.append(P[j]); B.append(P[(j + 1) % n]); S.append(np.full(len(j), si)); I.append(j)
    return np.vstack(A), np.vstack(B), np.concatenate(S), np.concatenate(I)


def find(strands, tol_index=3):
    """All proper crossings: [(point, (strand a, index a), (strand b, index b))], deduplicated, sorted by position."""
    if not strands: return []
    A, B, S, I = _segments(strands)
    mid = (A + B) / 2; L = np.linalg.norm(B - A, axis=1); r = float(L.max()) * 1.01 + 1e-9
    pairs = cKDTree(mid).query_pairs(r, output_type="ndarray")
    if len(pairs) == 0: return []
    p, q = pairs[:, 0], pairs[:, 1]
    same = S[p] == S[q]
    n_of = np.array([len(s.pts) for s in strands])
    di = np.abs(I[p] - I[q]); di = np.where(same & np.array([strands[k].closed for k in S[p]]), np.minimum(di, n_of[S[p]] - di), di)
    keep = ~(same & (di <= tol_index)); p, q = p[keep], q[keep]
    a0, a1, b0, b1 = A[p], B[p], A[q], B[q]
    da, db = a1 - a0, b1 - b0; den = da[:, 0] * db[:, 1] - da[:, 1] * db[:, 0]
    ok = np.abs(den) > 1e-12; w = b0 - a0
    t = np.where(ok, (w[:, 0] * db[:, 1] - w[:, 1] * db[:, 0]) / np.where(ok, den, 1), -1)
    u = np.where(ok, (w[:, 0] * da[:, 1] - w[:, 1] * da[:, 0]) / np.where(ok, den, 1), -1)
    hit = ok & (t >= 0) & (t < 1) & (u >= 0) & (u < 1)
    out = []
    for k in np.where(hit)[0]:
        pt = a0[k] + da[k] * t[k]
        ia, ib = (int(S[p[k]]), int(I[p[k]]) + (1 if t[k] > 0.5 else 0)), (int(S[q[k]]), int(I[q[k]]) + (1 if u[k] > 0.5 else 0))
        ia = (ia[0], ia[1] % len(strands[ia[0]].pts)); ib = (ib[0], ib[1] % len(strands[ib[0]].pts))
        if (ib[0], ib[1]) < (ia[0], ia[1]): ia, ib = ib, ia
        out.append((pt, ia, ib))
    # dedupe: a crossing exactly on a sample point is reported by up to four segment pairs
    out.sort(key=lambda c: (round(float(c[0][0]), 4), round(float(c[0][1]), 4), c[1], c[2]))
    res, grid, cell = [], {}, 2.5 * r
    for c in out:
        gx, gy = int(np.floor(c[0][0] / cell)), int(np.floor(c[0][1] / cell)); dup = False
        for ox in (-1, 0, 1):
            for oy in (-1, 0, 1):
                for d in grid.get((gx + ox, gy + oy), ()):
                    if np.linalg.norm(c[0] - d[0]) < cell and {c[1][0], c[2][0]} == {d[1][0], d[2][0]}: dup = True
        if dup: continue
        res.append(c); grid.setdefault((gx, gy), []).append(c)
    return res


def assign(strands, found):
    """Alternating over/under for the crossings `found` (from find()). Returns (crossings, conflicts)."""
    passes = []                                     # (strand, index, crossing id, slot 0|1)
    for ci, (pt, a, b) in enumerate(found):
        passes.append((a[0], a[1], ci, 0)); passes.append((b[0], b[1], ci, 1))
    if not passes: return [], 0
    pid = {}
    for k, ps in enumerate(passes): pid[(ps[2], ps[3])] = k
    adj = [[] for _ in passes]
    for ci in range(len(found)):
        x, y = pid[(ci, 0)], pid[(ci, 1)]; adj[x].append(y); adj[y].append(x)
    by_strand = {}
    for k, (s, i, ci, sl) in enumerate(passes): by_strand.setdefault(s, []).append((i, ci, sl, k))
    for s, lst in by_strand.items():
        lst.sort(); ks = [k for (_, _, _, k) in lst]
        for x, y in zip(ks, ks[1:]): adj[x].append(y); adj[y].append(x)
        if strands[s].closed and len(ks) > 1: adj[ks[-1]].append(ks[0]); adj[ks[0]].append(ks[-1])
    col = [None] * len(passes); conflicts = 0
    order = sorted(range(len(passes)), key=lambda k: (passes[k][0], passes[k][1], passes[k][3]))
    for start in order:
        if col[start] is not None: continue
        col[start] = True; dq = deque([start])
        while dq:
            x = dq.popleft()
            for y in adj[x]:
                if col[y] is None: col[y] = not col[x]; dq.append(y)
                elif col[y] == col[x]: conflicts += 1
    out = []
    for ci, (pt, a, b) in enumerate(found):
        if col[pid[(ci, 0)]]: out.append(Crossing(pt, a, b))
        else: out.append(Crossing(pt, b, a))
    return out, conflicts // 2


def resolve(pattern, roles=None):
    """Find and assign the crossings of a pattern's strands (those with a role in `roles`, default every strand that is
    not a rune stroke); store them on the pattern."""
    idx = [i for i, s in enumerate(pattern.strands) if (roles is None and s.role != "rune") or (roles is not None and s.role in roles)]
    sub = [pattern.strands[i] for i in idx]
    found = find(sub); cr, conflicts = assign(sub, found)
    for c in cr:
        c.over = (idx[c.over[0]], c.over[1]); c.under = (idx[c.under[0]], c.under[1])
    pattern.crossings = cr; pattern.conflicts = conflicts
    return pattern
