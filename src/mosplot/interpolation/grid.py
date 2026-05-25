from __future__ import annotations

from typing import cast

import numpy as np
from scipy.interpolate import griddata

from mosplot.expressions import Expression, evaluate_expression
from ._common import _prepare_eval_points


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
        x_value: float | tuple[float, ...] | np.ndarray,
        y_value: float | tuple[float, ...] | np.ndarray,
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
