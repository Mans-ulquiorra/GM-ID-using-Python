"""Assembled linear systems for reduced-MNA small-signal analysis."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class LinearSystem:
    """Numeric small-signal system shared by analysis objects."""

    G: np.ndarray
    C: np.ndarray
    node_idx: dict[str, int]

    def solve_dc(self, rhs: np.ndarray) -> np.ndarray:
        """Solve the zero-frequency system."""

        return np.linalg.solve(self.G, rhs)

    def solve_ac(self, rhs_g: np.ndarray, rhs_c: np.ndarray, frequency_hz: float) -> np.ndarray:
        """Solve the system at one nonzero frequency in Hz."""

        omega = 2.0 * np.pi * float(frequency_hz)
        admittance = self.G.astype(np.complex128) + 1j * omega * self.C
        rhs = rhs_g.astype(np.complex128) + 1j * omega * rhs_c
        return np.linalg.solve(admittance, rhs)

    def has_dynamic_terms(self, rhs_c: np.ndarray | None = None) -> bool:
        """Return true when this system has capacitance or capacitive excitation."""

        if np.any(self.C != 0.0):
            return True
        return bool(rhs_c is not None and np.any(rhs_c != 0.0))
