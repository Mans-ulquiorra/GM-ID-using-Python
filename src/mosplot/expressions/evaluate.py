from __future__ import annotations

from typing import Any

import numpy as np

from .expression import Expression


def evaluate_expression(
    expression: Expression,
    table: dict,
    filter_by_rows: np.ndarray | None = None,
) -> tuple[Any, str]:
    """Evaluate an expression against a table dict, optionally filtering rows."""
    _filter = np.array([]) if filter_by_rows is None else filter_by_rows
    var_list = []
    for var in expression.variables:
        data = table[var]
        if _filter.size > 0 and data.ndim > 1:
            var_list.append(np.take(data, _filter, axis=0))
        else:
            var_list.append(data)
    result = expression.function(*var_list)
    return result, expression.label
