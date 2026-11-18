"""Self-test fixture for package_render_uv.py (Pipeline Kit, step 11 of kit-selftest.ps1). The mesh is made up here:
a flat strip of 40 x 4 unit quads, UV-mapped evenly, then the same strip with its last 30 % squashed six times along U
(a stretched patch, as a decimation can leave on a blade tip). The even strip must PASS, the squashed one FAIL.

    python uv-strip-test.py <the kit's scripts\\release folder>
"""
import sys

sys.path.insert(0, sys.argv[1])
import numpy as np  # noqa: E402
import package_render_uv as U  # noqa: E402

NX, NY = 40, 4
V = np.array([[x, y, 0.0] for y in range(NY + 1) for x in range(NX + 1)], float)


def at(x, y):
    return y * (NX + 1) + x


T = []
for y in range(NY):
    for x in range(NX):
        a, b, c, d = at(x, y), at(x + 1, y), at(x + 1, y + 1), at(x, y + 1)
        T += [(a, b, c), (a, c, d)]
T = np.array(T)


def uvs(squash):
    u = V[:, 0].copy()
    if squash:
        u = np.where(u > 28.0, 28.0 + (u - 28.0) / 6.0, u)
    return np.stack([u / 48.0, V[:, 1] / 48.0], 1)


even = U.measure_shape("strip", V, uvs(False), T, 1024, 1024)
squashed = U.measure_shape("strip", V, uvs(True), T, 1024, 1024)
print(f"even strip: {even['verdict']}   squashed strip: {squashed['verdict']}"
      + (f" ({'; '.join(squashed['islands'][0]['why'])})" if squashed["islands"] else ""))
sys.exit(0 if (even["verdict"], squashed["verdict"]) == ("PASS", "FAIL") else 1)
