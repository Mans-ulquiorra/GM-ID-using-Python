from __future__ import annotations


_SI_TABLE: list[tuple[float, str]] = [
    (1e-15, "f"),
    (1e-12, "p"),
    (1e-9, "n"),
    (1e-6, "u"),
    (1e-3, "m"),
    (1e0, ""),
    (1e3, "k"),
    (1e6, "M"),
    (1e9, "G"),
    (1e12, "T"),
]


def si(value: float) -> str:
    abs_val = abs(value)
    for scale, prefix in reversed(_SI_TABLE):
        if abs_val >= scale:
            return f"{value / scale:.4g}{prefix}"
    return f"{value:.4g}"
