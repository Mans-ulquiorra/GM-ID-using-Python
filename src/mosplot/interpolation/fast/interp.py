"""Interpolation primitives for the (L, vbs, vds, gmid) grid.

Three functions are exported:
  _resample_into      -- build-time: remap a vgs sweep onto a uniform gmid axis
  _lookup_scalar_nb   -- scalar Numba path used by the optimizer hot loop
  _bracket_vec        -- vectorised NumPy bracketing used by the batch path
  _interp4d_nan       -- vectorised 4-D trilinear interpolation
"""

from __future__ import annotations

import numpy as np

from mosplot._numba import njit as _njit


# ---------------------------------------------------------------------------
# Build-time helper
# ---------------------------------------------------------------------------


def _resample_into(g_asc, d_mat, gmid_grid, out):
    """Linearly resample d_mat (n_params × n_vgs) onto a uniform gmid_grid.

    g_asc must be strictly ascending. Points in gmid_grid outside g_asc are
    left as NaN (out is pre-filled with NaN by the caller).
    """
    idx = np.searchsorted(g_asc, gmid_grid, side="right") - 1
    in_range = (idx >= 0) & (idx < len(g_asc) - 1)
    if not np.any(in_range):
        return
    i0 = idx[in_range]
    frac = (gmid_grid[in_range] - g_asc[i0]) / (g_asc[i0 + 1] - g_asc[i0])
    out[:, in_range] = d_mat[:, i0] + frac * (d_mat[:, i0 + 1] - d_mat[:, i0])


# ---------------------------------------------------------------------------
# Scalar lookup path  (Numba-JIT, called once per optimizer function evaluation)
# ---------------------------------------------------------------------------


@_njit(cache=True)
def _bracket_nb(axis, x):
    """Binary search: return (i0, frac) such that axis[i0] + frac*step ≈ x."""
    n = len(axis)
    if n == 1:
        return 0, 0.0
    i0 = min(max(int(np.searchsorted(axis, x, side="right")) - 1, 0), n - 2)
    dv = axis[i0 + 1] - axis[i0]
    frac = 0.0 if dv == 0.0 else (x - axis[i0]) / dv
    if frac < 0.0:
        frac = 0.0
    if frac > 1.0:
        frac = 1.0
    return i0, frac


@_njit(cache=True)
def _lookup_scalar_nb(data_stack, lengths, vbs_ax, vds_ax, gmid_ax, L, gmid, vds, vbs):
    """4-D trilinear interpolation for a single (L, gmid, vds, vbs) point.

    data_stack is shaped (n_params, n_L, n_vbs, n_vds, n_gmid). A contiguous
    stacked array is required because Numba njit cannot accept Python dicts.

    NaN cells are skipped in the weighted average. The check `c == c` is False
    only for NaN (IEEE 754), which is the idiomatic NaN test inside Numba.
    """
    il, fl = _bracket_nb(lengths, L)
    iv, fv = _bracket_nb(vbs_ax, vbs)
    id_, fd = _bracket_nb(vds_ax, vds)
    ig, fg = _bracket_nb(gmid_ax, gmid)

    il1 = il + 1
    iv1 = iv + 1
    id1 = id_ + 1
    ig1 = ig + 1

    # Trilinear weights for all 16 corners of the 4-D hypercube
    w0 = (1 - fl) * (1 - fv) * (1 - fd) * (1 - fg)
    w1 = fl * (1 - fv) * (1 - fd) * (1 - fg)
    w2 = (1 - fl) * fv * (1 - fd) * (1 - fg)
    w3 = (1 - fl) * (1 - fv) * fd * (1 - fg)
    w4 = (1 - fl) * (1 - fv) * (1 - fd) * fg
    w5 = fl * fv * (1 - fd) * (1 - fg)
    w6 = fl * (1 - fv) * fd * (1 - fg)
    w7 = fl * (1 - fv) * (1 - fd) * fg
    w8 = (1 - fl) * fv * fd * (1 - fg)
    w9 = (1 - fl) * fv * (1 - fd) * fg
    w10 = (1 - fl) * (1 - fv) * fd * fg
    w11 = fl * fv * fd * (1 - fg)
    w12 = fl * fv * (1 - fd) * fg
    w13 = fl * (1 - fv) * fd * fg
    w14 = (1 - fl) * fv * fd * fg
    w15 = fl * fv * fd * fg

    n_params = data_stack.shape[0]
    result = np.empty(n_params)

    for i in range(n_params):
        d = data_stack[i]
        c0 = d[il, iv, id_, ig]
        c1 = d[il1, iv, id_, ig]
        c2 = d[il, iv1, id_, ig]
        c3 = d[il, iv, id1, ig]
        c4 = d[il, iv, id_, ig1]
        c5 = d[il1, iv1, id_, ig]
        c6 = d[il1, iv, id1, ig]
        c7 = d[il1, iv, id_, ig1]
        c8 = d[il, iv1, id1, ig]
        c9 = d[il, iv1, id_, ig1]
        c10 = d[il, iv, id1, ig1]
        c11 = d[il1, iv1, id1, ig]
        c12 = d[il1, iv1, id_, ig1]
        c13 = d[il1, iv, id1, ig1]
        c14 = d[il, iv1, id1, ig1]
        c15 = d[il1, iv1, id1, ig1]

        num = 0.0
        den = 0.0
        if c0 == c0:
            num += w0 * c0
            den += w0
        if c1 == c1:
            num += w1 * c1
            den += w1
        if c2 == c2:
            num += w2 * c2
            den += w2
        if c3 == c3:
            num += w3 * c3
            den += w3
        if c4 == c4:
            num += w4 * c4
            den += w4
        if c5 == c5:
            num += w5 * c5
            den += w5
        if c6 == c6:
            num += w6 * c6
            den += w6
        if c7 == c7:
            num += w7 * c7
            den += w7
        if c8 == c8:
            num += w8 * c8
            den += w8
        if c9 == c9:
            num += w9 * c9
            den += w9
        if c10 == c10:
            num += w10 * c10
            den += w10
        if c11 == c11:
            num += w11 * c11
            den += w11
        if c12 == c12:
            num += w12 * c12
            den += w12
        if c13 == c13:
            num += w13 * c13
            den += w13
        if c14 == c14:
            num += w14 * c14
            den += w14
        if c15 == c15:
            num += w15 * c15
            den += w15

        result[i] = num / den if den > 0.0 else np.nan

    return result


# ---------------------------------------------------------------------------
# Vectorised lookup path  (NumPy, used for plotting / batch queries)
# ---------------------------------------------------------------------------


def _bracket_vec(axis, xs):
    """Vectorised bracketing: returns (i0, i1, frac) arrays for a query array xs."""
    n = len(axis)
    if n == 1:
        z = np.zeros(len(xs), dtype=np.intp)
        return z, z, np.zeros(len(xs))
    i0 = np.clip(np.searchsorted(axis, xs, side="right") - 1, 0, n - 2).astype(np.intp)
    frac = np.clip((xs - axis[i0]) / (axis[i0 + 1] - axis[i0]), 0.0, 1.0)
    return i0, i0 + 1, frac


def _interp4d_nan(data, il, il1, fl, iv, iv1, fv, id_, id1_, fd, ig, ig1, fg):
    """Trilinear interpolation over a 4-D (L, vbs, vds, gmid) grid.

    NaN cells are excluded from the weighted average so that queries near the
    edge of the valid operating region degrade gracefully instead of returning
    NaN whenever any corner of the interpolation hypercube is missing.
    """
    w = np.stack(
        [
            (1 - fl) * (1 - fv) * (1 - fd) * (1 - fg),
            fl * (1 - fv) * (1 - fd) * (1 - fg),
            (1 - fl) * fv * (1 - fd) * (1 - fg),
            (1 - fl) * (1 - fv) * fd * (1 - fg),
            (1 - fl) * (1 - fv) * (1 - fd) * fg,
            fl * fv * (1 - fd) * (1 - fg),
            fl * (1 - fv) * fd * (1 - fg),
            fl * (1 - fv) * (1 - fd) * fg,
            (1 - fl) * fv * fd * (1 - fg),
            (1 - fl) * fv * (1 - fd) * fg,
            (1 - fl) * (1 - fv) * fd * fg,
            fl * fv * fd * (1 - fg),
            fl * fv * (1 - fd) * fg,
            fl * (1 - fv) * fd * fg,
            (1 - fl) * fv * fd * fg,
            fl * fv * fd * fg,
        ]
    )
    v = np.stack(
        [
            data[il, iv, id_, ig],
            data[il1, iv, id_, ig],
            data[il, iv1, id_, ig],
            data[il, iv, id1_, ig],
            data[il, iv, id_, ig1],
            data[il1, iv1, id_, ig],
            data[il1, iv, id1_, ig],
            data[il1, iv, id_, ig1],
            data[il, iv1, id1_, ig],
            data[il, iv1, id_, ig1],
            data[il, iv, id1_, ig1],
            data[il1, iv1, id1_, ig],
            data[il1, iv1, id_, ig1],
            data[il1, iv, id1_, ig1],
            data[il, iv1, id1_, ig1],
            data[il1, iv1, id1_, ig1],
        ]
    )
    mask = np.isfinite(v)
    w_safe = np.where(mask, w, 0.0)
    w_sum = w_safe.sum(axis=0)
    num = (w_safe * np.where(mask, v, 0.0)).sum(axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(w_sum > 0, num / w_sum, np.nan)
