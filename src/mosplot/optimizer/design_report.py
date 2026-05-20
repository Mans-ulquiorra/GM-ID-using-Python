from __future__ import annotations

from typing import Any
from .optimizer import Optimizer


_SI_PREFIXES: list[tuple[float, str]] = [
    (1e12, "T"),
    (1e9, "G"),
    (1e6, "M"),
    (1e3, "k"),
    (1e0, ""),
    (1e-3, "m"),
    (1e-6, "µ"),
    (1e-9, "n"),
    (1e-12, "p"),
    (1e-15, "f"),
]


def _format_eng(value: float | None) -> str:
    """Format a scalar using the largest applicable SI prefix."""
    if value is None:
        return "N/A"
    abs_val = abs(value)
    for scale, prefix in _SI_PREFIXES:
        if abs_val >= scale:
            return f"{value / scale:.3g}{prefix}"
    return f"{value:.3g}"


def _format_area(value: float | None) -> str:
    """Format an area value (in m²) as µm² or nm²."""
    if value is None:
        return "N/A"
    um2 = value * 1e12
    if um2 >= 1.0:
        return f"{um2:.3f} µm²"
    return f"{value * 1e18:.3f} nm²"


class DesignReport:
    """Generates a human-readable report for an optimized circuit."""

    def __init__(self, circuit: Any, optimizer: Optimizer) -> None:
        self.circuit = circuit
        self.optimizer = optimizer
        self.opt_params: dict[str, float] = optimizer.get_opt_params()
        self.full_specs: dict[str, Any] = circuit.evaluate_specs(**self.opt_params)
        self.objective: float | None = (
            optimizer.result.fun if optimizer.result is not None else None
        )

    def report(self) -> str:
        lines: list[str] = []

        dims = getattr(self.circuit, "device_dimensions", None)
        lines.append("\nTransistor Details:")
        if dims:
            for device, item in dims.items():
                lines.append(f"  {device}:")
                lines.append(f"    Length:  {_format_eng(item.get('Length'))}m")
                lines.append(f"    Width:   {_format_eng(item.get('Width'))}m")
                lines.append(f"    Area:    {_format_area(item.get('Area'))}")
                lines.append(f"    Current: {_format_eng(item.get('Current'))}A")
                gmid = item.get("GMID")
                if gmid is not None:
                    lines.append(f"    GmID:    {gmid:.2f}")
        else:
            lines.append("  Not available.")

        lines.append("\nFinal Circuit Specs:")
        target_specs = getattr(self.optimizer, "target_specs", {})
        if self.full_specs:
            for key, val in self.full_specs.items():
                target = target_specs.get(key)
                target_str = (
                    f"  (target: {_format_area(target.target) if key == 'Area' else _format_eng(target.target)})"
                    if target
                    else ""
                )
                if key == "Area":
                    lines.append(f"  {key}: {_format_area(val)}{target_str}")
                else:
                    try:
                        lines.append(f"  {key}: {_format_eng(val)}{target_str}")
                    except (ValueError, TypeError):
                        lines.append(f"  {key}: {val}{target_str}")
        else:
            lines.append("  Not available.")

        if self.objective is not None:
            lines.append(f"\nFinal cost: {self.objective:.6g}")

        return "\n".join(lines)
