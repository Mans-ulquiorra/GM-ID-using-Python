# imports <<<
from typing import List, Tuple, Union
import numpy as np
from scipy.interpolate import griddata
from scipy.spatial import cKDTree
from .expressions import Expression
from .util import evaluate_expression
# >>>

# grid interpolate <<<
class GridInterpolator:
    """
    Interpolator using griddata with cubic interpolation.

    Methods:
        interpolate: Interpolates z values based on provided x, y, and z expressions.
    """
    def __init__(self, extracted_table: dict) -> None:
        self.extracted_table = extracted_table

    def interpolate(
        self,
        x_expression: Expression,
        x_value: Union[float, Tuple[float, float], np.ndarray],
        y_expression: Expression,
        y_value: Union[float, Tuple[float, float], np.ndarray],
        z_expression: Union[Expression, List[Expression]]
    ) -> Union[np.ndarray, List[np.ndarray]]:
        """
        Interpolates z values based on x and y expressions.

        Args:
            x_expression: Expression for x-axis points.
            x_value: Value(s) within the x_expression domain.
            y_expression: Expression for y-axis points.
            y_value: Value(s) within the y_expression domain.
            z_expression: Expression or list of expressions for the output value(s).

        Returns:
            A single interpolated numpy array if z_expression is a single Expression,
            or a list of numpy arrays if a list of expressions is provided.
        """
        x_array, _ = evaluate_expression(x_expression, self.extracted_table)
        y_array, _ = evaluate_expression(y_expression, self.extracted_table)
        points = np.column_stack((x_array.ravel(), y_array.ravel()))
        eval_points = self._prepare_eval_points(x_value, y_value)

        # Allow single or multiple z_expressions.
        single_input = False
        if not isinstance(z_expression, list):
            z_expressions = [z_expression]
            single_input = True
        else:
            z_expressions = z_expression

        results = []
        for expr in z_expressions:
            z_array, _ = evaluate_expression(expr, self.extracted_table)
            res = griddata(points, z_array.ravel(), eval_points, method="cubic", rescale=True)
            results.append(res)
        return results[0] if single_input else results

    def _prepare_eval_points(
        self,
        x_value: Union[float, Tuple[float, float], np.ndarray],
        y_value: Union[float, Tuple[float, float], np.ndarray]
    ) -> np.ndarray:
        if isinstance(x_value, tuple) and isinstance(y_value, (int, float)):
            x_vals = np.arange(*x_value)
            return np.column_stack((x_vals, np.full(x_vals.shape, y_value)))
        elif isinstance(y_value, tuple) and isinstance(x_value, (int, float)):
            y_vals = np.arange(*y_value)
            return np.column_stack((np.full(y_vals.shape, x_value), y_vals))
        elif isinstance(x_value, tuple) and isinstance(y_value, tuple):
            x_vals = np.arange(*x_value)
            y_vals = np.arange(*y_value)
            X, Y = np.meshgrid(x_vals, y_vals)
            return np.dstack((X, Y)).reshape(-1, 2)
        else:
            return np.array([[x_value, y_value]])
# >>>

# kdtree interpolate <<<
class KDTreeInterpolator:
    """
    Interpolator using a KDTree with inverse distance weighting.

    Methods:
        interpolate: Interpolates z values based on provided x, y, and z expressions.
    """
    def __init__(self, extracted_table: dict, x_expression: Expression, y_expression: Expression) -> None:
        self.extracted_table = extracted_table
        x_array, _ = evaluate_expression(x_expression, extracted_table)
        y_array, _ = evaluate_expression(y_expression, extracted_table)
        self._x_min, self._x_max = x_array.min(), x_array.max()
        self._y_min, self._y_max = y_array.min(), y_array.max()
        raw = np.column_stack((x_array.ravel(), y_array.ravel()))
        scaled = self._scale(raw[:, 0], raw[:, 1])
        self._tree = cKDTree(scaled)
        self._k = min(8, len(scaled))

    def _scale(self, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        return np.column_stack((
            (x - self._x_min) / (self._x_max - self._x_min),
            (y - self._y_min) / (self._y_max - self._y_min)
        ))

    def interpolate(
        self,
        x_value: Union[float, Tuple[float, float], np.ndarray],
        y_value: Union[float, Tuple[float, float], np.ndarray],
        z_expression: Union[Expression, List[Expression]]
    ) -> Union[np.ndarray, List[np.ndarray]]:
        """
        Interpolates z values using inverse distance weighting with a KDTree.

        Args:
            x_value: Value(s) within the x_expression domain.
            y_value: Value(s) within the y_expression domain.
            z_expression: Expression or list of expressions for the output value(s).

        Returns:
            A single interpolated numpy array if z_expression is a single Expression,
            or a list of numpy arrays if a list of expressions is provided.
        """
        eval_points = self._prepare_eval_points(x_value, y_value)
        scaled_eval = self._scale(eval_points[:, 0], eval_points[:, 1])

        single_input = not isinstance(z_expression, list)
        z_expressions = [z_expression] if single_input else z_expression

        eps = 1e-12
        dist, idx = self._tree.query(scaled_eval, k=self._k)
        if self._k == 1:
            dist = dist[:, None]
            idx = idx[:, None]

        results = []
        for expr in z_expressions:
            z_flat, _ = evaluate_expression(expr, self.extracted_table)
            z_flat = z_flat.ravel()
            res = np.empty(len(scaled_eval))
            zero_mask = dist[:, 0] < eps
            res[zero_mask] = z_flat[idx[zero_mask, 0]]
            if np.any(~zero_mask):
                d = dist[~zero_mask]
                i = idx[~zero_mask]
                weights = 1 / (d**2)
                res[~zero_mask] = (weights * z_flat[i]).sum(axis=1) / weights.sum(axis=1)
            results.append(res)
        return results[0] if single_input else results

    def _prepare_eval_points(
        self,
        x_value: Union[float, Tuple[float, float], np.ndarray],
        y_value: Union[float, Tuple[float, float], np.ndarray]
    ) -> np.ndarray:
        if isinstance(x_value, tuple) and isinstance(y_value, (int, float)):
            x_vals = np.arange(*x_value)
            return np.column_stack((x_vals, np.full(x_vals.shape, y_value)))
        elif isinstance(y_value, tuple) and isinstance(x_value, (int, float)):
            y_vals = np.arange(*y_value)
            return np.column_stack((np.full(y_vals.shape, x_value), y_vals))
        elif isinstance(x_value, tuple) and isinstance(y_value, tuple):
            x_vals = np.arange(*x_value)
            y_vals = np.arange(*y_value)
            X, Y = np.meshgrid(x_vals, y_vals)
            return np.dstack((X, Y)).reshape(-1, 2)
        else:
            return np.array([[x_value, y_value]])
# >>>
