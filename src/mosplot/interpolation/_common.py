from __future__ import annotations

import numpy as np


def _prepare_eval_points(
    x_value: float | tuple[float, ...] | np.ndarray,
    y_value: float | tuple[float, ...] | np.ndarray,
) -> np.ndarray:
    """
    Build a (N, 2) array of query points from scalars, range tuples, or arrays.

    Accepted combinations
    ---------------------
    - scalar + scalar   -> single point
    - array  + scalar   -> one point per x element, y held constant
    - scalar + array    -> one point per y element, x held constant
    - array  + array    -> paired points (must be the same length)
    - tuple  + scalar   -> np.arange(*tuple) for x, y held constant
    - scalar + tuple    -> np.arange(*tuple) for y, x held constant
    - tuple  + tuple    -> meshgrid over both ranges, flattened
    """
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
