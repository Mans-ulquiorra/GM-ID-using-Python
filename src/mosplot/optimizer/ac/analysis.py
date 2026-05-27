from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ._types import UNKNOWN_NODE
from .kernels import find_unity_gain, phase_margin, solve_response
from .system import LinearSystem


@dataclass
class TransferAnalysis:
    """Voltage-transfer analysis with lazily computed metrics."""

    system: LinearSystem
    out_idx: int
    rhs_g: np.ndarray
    rhs_c: np.ndarray
    gbw_iters: int = 32
    _v: np.ndarray | None = field(default=None, init=False, repr=False)
    _gain: float | None = field(default=None, init=False, repr=False)
    _ugf_hz: float | None = field(default=None, init=False, repr=False)

    def gain(self) -> float:
        """Return the zero-frequency voltage gain."""

        if self._gain is None:
            self._v = self.system.solve_dc(self.rhs_g)
            self._gain = float(self._v[self.out_idx])
        return self._gain

    def rejection(self, interference: TransferAnalysis) -> float:
        """Return absolute rejection ratio against another transfer analysis."""

        signal = self.gain()
        interferer = interference.gain()
        return abs(signal / interferer) if abs(interferer) > 1e-30 else 1e12

    def response(self, frequency_hz: float) -> complex:
        """Return output response at one frequency in Hz."""

        return solve_response(
            self.system.G,
            self.system.C,
            self.rhs_g,
            self.rhs_c,
            self.out_idx,
            2.0 * np.pi * float(frequency_hz),
        )

    def ugf(self) -> float:
        """Return the first unity-gain frequency in Hz."""

        if self._ugf_hz is not None:
            return self._ugf_hz

        dc_gain = self.gain()
        if self.system.has_dynamic_terms(self.rhs_c):
            self._ugf_hz = float(
                find_unity_gain(
                    self.system.G,
                    self.system.C,
                    self.rhs_g,
                    self.rhs_c,
                    self.out_idx,
                    self.gbw_iters,
                )
            )
        else:
            self._ugf_hz = float("inf") if abs(dc_gain) >= 1.0 else 0.0
        return self._ugf_hz

    def phase_margin(self) -> float:
        """Return phase margin in degrees at the unity-gain frequency."""

        return float(
            phase_margin(
                self.system.G,
                self.system.C,
                self.rhs_g,
                self.rhs_c,
                self.out_idx,
                self.ugf(),
                self.gain(),
            )
        )


@dataclass
class PortAnalysis:
    """One-port impedance analysis."""

    system: LinearSystem
    node_idx_probe: int
    reference_idx: int

    def _current_rhs(self, current: float) -> np.ndarray:
        rhs = np.zeros(len(self.system.node_idx), dtype=float)
        if self.node_idx_probe != UNKNOWN_NODE:
            rhs[self.node_idx_probe] -= current
        if self.reference_idx != UNKNOWN_NODE:
            rhs[self.reference_idx] += current
        return rhs

    @staticmethod
    def _voltage_at(solution: np.ndarray, idx: int) -> complex:
        return 0.0 if idx == UNKNOWN_NODE else solution[idx]

    def impedance(self, frequency_hz: float = 0.0, *, test_current: float = 1.0) -> complex:
        """Return impedance seen by a current entering the probe node."""

        if test_current == 0.0:
            raise ValueError("test_current must be non-zero.")

        rhs_g = self._current_rhs(float(test_current))
        if frequency_hz == 0.0:
            v = self.system.solve_dc(rhs_g)
        else:
            rhs_c = np.zeros(len(self.system.node_idx), dtype=float)
            v = self.system.solve_ac(rhs_g, rhs_c, frequency_hz)

        node_v = self._voltage_at(v, self.node_idx_probe)
        reference_v = self._voltage_at(v, self.reference_idx)
        return (node_v - reference_v) / test_current

    def resistance(self, *, test_current: float = 1.0) -> float:
        """Return the DC small-signal resistance."""

        return float(np.real(self.impedance(0.0, test_current=test_current)))
