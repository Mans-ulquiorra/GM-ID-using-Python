from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .datatypes import Spec


@dataclass
class CornerResult:
    name: str
    specs: dict[str, float]
    cost: float


def evaluate_corners(
    circuits: list[Any],
    params: dict[str, float],
) -> list[dict[str, float]]:
    """Evaluate all circuits at params. Replace body here when adding parallelism."""
    results = []
    for circuit in circuits:
        try:
            results.append(circuit.evaluate_specs(**params))
        except Exception:
            results.append({})
    return results


def worst_case_specs(
    corner_specs: list[tuple[str, dict[str, float]]],
    target_specs: dict[str, Spec],
) -> tuple[dict[str, float], dict[str, str]]:
    """
    Assemble worst-case specs across corners, mode-aware.

    For each targeted spec, selects the value from the corner that is hardest
    to satisfy:
      - "max" spec: the corner with the lowest value.
      - "min" spec: the corner with the highest value.
      - "eq"  spec: the corner furthest from the target.

    Non-targeted specs are passed through from the first corner unchanged.

    Returns:
        worst:   spec dict with the worst value for each targeted spec.
        binding: maps each targeted spec name to the corner where it was worst.
    """
    worst: dict[str, float] = {}
    binding: dict[str, str] = {}

    for key, spec in target_specs.items():
        candidates = [(specs[key], name) for name, specs in corner_specs if key in specs]
        if not candidates:
            continue
        if spec.mode == "max":
            val, corner = min(candidates, key=lambda x: x[0])
        elif spec.mode == "min":
            val, corner = max(candidates, key=lambda x: x[0])
        else:  # "eq"
            val, corner = max(candidates, key=lambda x: abs(x[0] - spec.target))
        worst[key] = val
        binding[key] = corner

    if corner_specs:
        for key, val in corner_specs[0][1].items():
            if key not in worst:
                worst[key] = val

    return worst, binding
