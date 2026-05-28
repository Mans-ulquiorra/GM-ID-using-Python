from __future__ import annotations

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
    if value is None:
        return "N/A"
    abs_val = abs(value)
    for scale, prefix in _SI_PREFIXES:
        if abs_val >= scale:
            return f"{value / scale:.3g}{prefix}"
    return f"{value:.3g}"


def _format_area(value: float | None) -> str:
    if value is None:
        return "N/A"
    um2 = value * 1e12
    if um2 >= 1.0:
        return f"{um2:.3f} µm²"
    return f"{value * 1e18:.3f} nm²"


def _format_spec(key: str, value: float | None) -> str:
    if key == "Area":
        return _format_area(value)
    try:
        return _format_eng(value)
    except (ValueError, TypeError):
        return str(value)


def _format_target(key: str, spec) -> str:
    mode_sym = {"max": "≥", "min": "≤", "eq": "="}
    sym = mode_sym.get(spec.mode, "")
    val = _format_area(spec.target) if key == "Area" else _format_eng(spec.target)
    return f"{sym}{val}"


class DesignReport:
    """Generates a human-readable report for an optimized circuit."""

    def __init__(self, optimizer: Optimizer) -> None:
        self.optimizer = optimizer
        self.objective: float | None = (
            optimizer.result.fun if optimizer.result is not None else None
        )

    def report(self) -> str:
        lines: list[str] = []
        opt = self.optimizer
        nominal = opt.circuits[0]

        # --- Transistor dimensions (from the first corner) ---
        dims = getattr(nominal, "device_dimensions", None)
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

        # --- Per-corner spec table ---
        lines.append("\nCorner Results:")
        corner_results = opt.corner_results
        binding = opt.binding or {}
        target_specs = opt.target_specs

        if not corner_results:
            lines.append("  Not available.")
        else:
            all_keys = list(corner_results[0].specs.keys())
            corner_names = [r.name for r in corner_results]

            # Build formatted cell values
            rows: dict[str, list[str]] = {}
            for key in all_keys:
                rows[key] = [_format_spec(key, r.specs.get(key)) for r in corner_results]

            # Column widths
            key_w = max(len(k) for k in all_keys)
            col_ws = [
                max(len(name), max(len(rows[k][i]) for k in all_keys))
                for i, name in enumerate(corner_names)
            ]
            tgt_w = max(
                (max(len(_format_target(k, target_specs[k])) for k in target_specs) if target_specs else 0),
                len("Target"),
            )
            bind_w = max(
                (max(len(v) for v in binding.values()) if binding else 0),
                len("Binding"),
            )

            def row_line(label: str, cells: list[str], target: str = "", bind: str = "") -> str:
                parts = [f"  {label:<{key_w}}"]
                for cell, w in zip(cells, col_ws):
                    parts.append(f" | {cell:<{w}}")
                parts.append(f" | {target:<{tgt_w}}")
                parts.append(f" | {bind:<{bind_w}}")
                return "".join(parts)

            sep = (
                "  " + "-" * key_w
                + "".join("-+-" + "-" * w for w in col_ws)
                + "-+-" + "-" * tgt_w
                + "-+-" + "-" * bind_w
            )

            lines.append(row_line("Spec", corner_names, "Target", "Binding"))
            lines.append(sep)

            for key in all_keys:
                cells = rows[key]
                if key in target_specs:
                    target_str = _format_target(key, target_specs[key])
                    bind_str = binding.get(key, "--")
                else:
                    target_str = ""
                    bind_str = ""
                lines.append(row_line(key, cells, target_str, bind_str))

        if self.objective is not None:
            lines.append(f"\nFinal cost: {self.objective:.6g}")

        return "\n".join(lines)
