from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Instance:
    """One transistor instance in the circuit topology."""

    name: str
    group: str  # key into Circuit.device_map and device_dimensions
    d: str
    g: str
    s: str
    b: str


@dataclass(frozen=True)
class Passive:
    """A two-terminal passive element (capacitor or resistor).

    Set external=True for elements that belong to the AC model but not to the
    generated subcircuit netlist (e.g. an off-chip load capacitor).
    """

    name: str
    kind: str  # "cap" | "res"
    a: str
    b: str
    external: bool = field(default=False)


@dataclass(frozen=True)
class VSource:
    """An ideal DC voltage source inside the subcircuit.

    The positive terminal p is treated as AC ground by the small-signal solver
    because it is driven by an ideal source.
    """

    name: str
    p: str  # driven (bias) node
    n: str  # reference node (typically "vss")
