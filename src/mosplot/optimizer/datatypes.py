from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Spec:
    """
    Target specification for a circuit parameter.

    Attributes:
        target: The threshold value for this specification.
        mode: Optimization direction.
            "max": higher is better; penalize when actual < target (e.g. GBW, Gain, CMRR).
            "min": lower is better; penalize when actual > target (e.g. Ibias, Area).
            "eq": target an exact value; penalize deviation in both directions (e.g. VOUT_DC).
        weight: Relative importance in the cost function. Higher weight means
            violations of this spec are penalised more strongly.
    """

    target: float
    mode: Literal["min", "max", "eq"]
    weight: float


@dataclass(frozen=True)
class OptimizationParameter:
    """
    An optimization parameter with its search domain.

    Attributes:
        name: Parameter name -- must match a keyword argument of Circuit.evaluate_specs.
        bound: Search domain.
            tuple (lo, hi): continuous parameter; the optimizer searches over [lo, hi].
            list or 1-D ndarray: discrete parameter; the optimizer picks from these values.
    """

    name: str
    bound: tuple[float, float] | list[float] | np.ndarray
