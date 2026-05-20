# imports <<<
from __future__ import annotations

from typing import Any

import numpy as np

from ..expressions import Expression
# >>>


def load_lookup_table(path: str) -> dict:
    return np.load(path, allow_pickle=True)["lookup_table"].item()


def evaluate_expression(
    expression: Expression,
    table: dict,
    filter_by_rows: np.ndarray | None = None,
) -> tuple[Any, str]:
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
