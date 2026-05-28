"""Shared number-formatting utilities."""

from __future__ import annotations

_AREA_TABLE: list[tuple[float, str]] = [
    (1e0,   "m²"),
    (1e-6,  "mm²"),
    (1e-12, "µm²"),
    (1e-18, "nm²"),
]


def si_area(value: float | None) -> str:
    """Format an area value (in m²) using the most readable SI unit."""
    if value is None:
        return "N/A"
    abs_val = abs(value)
    for i, (scale, unit) in enumerate(_AREA_TABLE):
        if abs_val >= scale:
            mantissa = value / scale
            s = f"{mantissa:.4g}"
            if "e" not in s and float(s) < 1000:
                return f"{s} {unit}"
            if i > 0:
                up_scale, up_unit = _AREA_TABLE[i - 1]
                return f"{value / up_scale:.4g} {up_unit}"
            break
    return f"{value * 1e18:.4g} nm²"


_SI_TABLE: list[tuple[float, str, str]] = [
    (1e12, "T", "T"),
    (1e9,  "G", "G"),
    (1e6,  "M", "M"),
    (1e3,  "k", "k"),
    (1e0,  "",  ""),
    (1e-3, "m", "m"),
    (1e-6, "u", "µ"),
    (1e-9, "n", "n"),
    (1e-12, "p", "p"),
    (1e-15, "f", "f"),
]


def si(value: float | None, *, unicode: bool = False) -> str:
    """Format *value* in SI engineering notation with 4 significant figures.

    Uses ASCII prefixes by default (e.g. ``u`` for micro) for netlist
    compatibility.  Pass ``unicode=True`` for human-readable display
    (e.g. ``µ``).  Returns ``"N/A"`` for ``None``.
    """
    if value is None:
        return "N/A"
    abs_val = abs(value)
    for i, (scale, ascii_p, uni_p) in enumerate(_SI_TABLE):
        if abs_val >= scale:
            prefix = uni_p if unicode else ascii_p
            mantissa = value / scale
            s = f"{mantissa:.4g}"
            if "e" not in s and float(s) < 1000:
                return f"{s}{prefix}"
            # Mantissa rounded to >=1000 -- step up one tier
            if i > 0:
                up_scale, up_ascii, up_uni = _SI_TABLE[i - 1]
                up_prefix = up_uni if unicode else up_ascii
                return f"{value / up_scale:.4g}{up_prefix}"
            break
    return f"{value:.4g}"
