from __future__ import annotations

from typing import cast
import numpy as np
from scipy.interpolate import griddata
from scipy.spatial import KDTree
from .expressions import Expression
from .util import evaluate_expression


_KDTREE_K = 8          # neighbours used for inverse-distance weighting
_EPS_ZERO_DIST = 1e-12  # distance below which a point is treated as an exact hit


def _prepare_eval_points(
    x_value: float | tuple | np.ndarray,
    y_value: float | tuple | np.ndarray,
) -> np.ndarray:
    """Return a (N, 2) array of query points from scalars, (start, stop[, step]) tuples, or arrays."""
    if isinstance(x_value, np.ndarray) and isinstance(y_value, (int, float)):
        return np.column_stack((x_value, np.full_like(x_value, y_value)))
    if isinstance(y_value, np.ndarray) and isinstance(x_value, (int, float)):
        return np.column_stack((np.full_like(y_value, x_value), y_value))
    if isinstance(x_value, np.ndarray) and isinstance(y_value, np.ndarray):
        return np.column_stack((x_value, y_value))
    if isinstance(x_value, tuple) and isinstance(y_value, (int, float)):
        x_vals = np.arange(*x_value)
        return np.column_stack((x_vals, np.full_like(x_vals, y_value)))
    if isinstance(y_value, tuple) and isinstance(x_value, (int, float)):
        y_vals = np.arange(*y_value)
        return np.column_stack((np.full_like(y_vals, x_value), y_vals))
    if isinstance(x_value, tuple) and isinstance(y_value, tuple):
        X, Y = np.meshgrid(np.arange(*x_value), np.arange(*y_value))
        return np.dstack((X, Y)).reshape(-1, 2)
    return np.array([[x_value, y_value]])


class GridInterpolator:
    """Scattered-data interpolator using scipy griddata (cubic method)."""

    def __init__(
        self,
        extracted_table: dict,
        x_expression: Expression,
        y_expression: Expression,
    ) -> None:
        self.extracted_table = extracted_table
        x_array, _ = evaluate_expression(x_expression, extracted_table)
        y_array, _ = evaluate_expression(y_expression, extracted_table)
        self._points = np.column_stack((x_array.ravel(), y_array.ravel()))

    def interpolate(
        self,
        x_value: float | tuple | np.ndarray,
        y_value: float | tuple | np.ndarray,
        z_expression: Expression | list[Expression],
    ) -> np.ndarray | list[np.ndarray]:
        eval_points = _prepare_eval_points(x_value, y_value)
        if isinstance(z_expression, list):
            exprs, single = cast(list[Expression], z_expression), False
        else:
            exprs, single = [z_expression], True
        results = [
            griddata(
                self._points,
                evaluate_expression(e, self.extracted_table)[0].ravel(),
                eval_points,
                method="cubic",
                rescale=True,
            )
            for e in exprs
        ]
        return results[0] if single else results


class KDTreeInterpolator:
    """Scattered-data interpolator using inverse-distance weighting on a KDTree."""

    def __init__(
        self,
        extracted_table: dict,
        x_expression: Expression,
        y_expression: Expression,
    ) -> None:
        self.extracted_table = extracted_table
        x_array, _ = evaluate_expression(x_expression, extracted_table)
        y_array, _ = evaluate_expression(y_expression, extracted_table)
        self._x_min = float(x_array.min())
        self._x_max = float(x_array.max())
        self._y_min = float(y_array.min())
        self._y_max = float(y_array.max())
        raw = np.column_stack((x_array.ravel(), y_array.ravel()))
        self._tree = KDTree(self._scale(raw[:, 0], raw[:, 1]))
        self._k = min(_KDTREE_K, len(raw))

    def _scale(self, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        x_span = (self._x_max - self._x_min) or 1.0
        y_span = (self._y_max - self._y_min) or 1.0
        return np.column_stack(((x - self._x_min) / x_span, (y - self._y_min) / y_span))

    def interpolate(
        self,
        x_value: float | tuple | np.ndarray,
        y_value: float | tuple | np.ndarray,
        z_expression: Expression | list[Expression],
    ) -> np.ndarray | list[np.ndarray]:
        eval_pts = _prepare_eval_points(x_value, y_value)
        scaled_eval = self._scale(eval_pts[:, 0], eval_pts[:, 1])
        _d, _i = self._tree.query(scaled_eval, k=self._k)
        dist: np.ndarray = np.asarray(_d)
        idx:  np.ndarray = np.asarray(_i)
        if self._k == 1:
            dist = dist[:, np.newaxis]
            idx  = idx[:, np.newaxis]

        if isinstance(z_expression, list):
            exprs, single = cast(list[Expression], z_expression), False
        else:
            exprs, single = [z_expression], True

        results = []
        for expr in exprs:
            z_flat = evaluate_expression(expr, self.extracted_table)[0].ravel()
            res = np.empty(len(scaled_eval))
            exact = dist[:, 0] < _EPS_ZERO_DIST
            res[exact] = z_flat[idx[exact, 0]]
            if np.any(~exact):
                w = 1.0 / dist[~exact] ** 2
                res[~exact] = (w * z_flat[idx[~exact]]).sum(axis=1) / w.sum(axis=1)
            results.append(res)

        return results[0] if single else results
