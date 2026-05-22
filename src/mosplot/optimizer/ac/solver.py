"""Reduced-MNA small-signal AC solver for gm/ID amplifier sizing.

The solver stamps a linear small-signal circuit and returns the open-loop
differential gain, unity-gain frequency, common-mode rejection ratio, and phase
margin estimate used by the optimizer.

Modeling assumptions
--------------------
* ``inp`` and ``inn`` are ideal independent voltage sources. They are removed
  from the matrix and their effects are moved to the right-hand side. This also
  works for conductors and capacitors connected to the input nodes, for example
  MOS ``cgs`` and ``cgd``.
* Ground and bias/supply nodes should be named ``"gnd"`` when they are AC
  ground. Other node names are treated as unknown circuit nodes.
* MOS polarity is provided by the caller. ``gm`` and optional ``gmb`` stamp a
  current from drain to source controlled by ``vgs`` and ``vbs`` respectively.
* Capacitances are two-terminal lumped capacitances. This is efficient and
  adequate for optimizer screening; it is not a charge-conserving intrinsic
  MOS capacitance matrix.
"""

# imports <<<
from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

import numpy as np


try:
    from numba import njit as _njit  # type: ignore[import]
except ImportError:

    def _njit(**_kw):  # type: ignore[misc]
        def _wrap(fn):
            return fn

        return _wrap
# >>>

@_njit(cache=True)
def _solve_response(
    G: np.ndarray,
    C: np.ndarray,
    rhs_g: np.ndarray,
    rhs_c: np.ndarray,
    out_idx: int,
    omega: float,
) -> complex:
    """Solve one frequency point and return output voltage."""
    y = G + 1j * omega * C
    rhs = rhs_g.astype(np.complex128) + 1j * omega * rhs_c.astype(np.complex128)
    solution = np.linalg.solve(y, rhs)
    return solution[out_idx]


@_njit(cache=True)
def _response_mag(
    G: np.ndarray,
    C: np.ndarray,
    rhs_g: np.ndarray,
    rhs_c: np.ndarray,
    out_idx: int,
    omega: float,
) -> float:
    return abs(_solve_response(G, C, rhs_g, rhs_c, out_idx, omega))


@dataclass(frozen=True)
class SmallSignalResult:
    """Optimizer AC metrics from a solved small-signal circuit."""

    gain: float
    ugf_hz: float
    cmrr: float
    phase_margin_deg: float


class _MosStamp(NamedTuple):
    gm: float
    gmb: float
    gds: float
    d: str
    g: str
    s: str
    b: str


class _CapStamp(NamedTuple):
    c: float
    a: str
    b: str


class _KnownValues(NamedTuple):
    dm: float
    cm: float


class _Assembly(NamedTuple):
    G: np.ndarray
    C: np.ndarray
    rhs_g_dm: np.ndarray
    rhs_c_dm: np.ndarray
    rhs_g_cm: np.ndarray
    rhs_c_cm: np.ndarray


class SmallSignalSolver:
    """Stamp-based small-signal solver for optimizer-grade AC metrics."""

    GND = "gnd"

    def __init__(self) -> None:
        self._mos: list[_MosStamp] = []
        self._caps: list[_CapStamp] = []

    def reset(self) -> None:
        """Remove all stamps so the instance can be reused."""
        self._mos.clear()
        self._caps.clear()

    def add_mos(
        self,
        *,
        gm: float,
        gds: float,
        d: str,
        g: str,
        s: str,
        b: str,
        gmb: float = 0.0,
    ) -> None:
        """Add a linear MOS small-signal stamp.

        ``gm`` controls drain-to-source current by ``V(g)-V(s)``.
        ``gmb`` controls drain-to-source current by ``V(b)-V(s)``.
        Use ``"gnd"`` for AC-grounded supply, bias, or substrate nodes.
        """
        self._mos.append(
            _MosStamp(
                gm=float(gm),
                gmb=float(gmb),
                gds=float(gds),
                d=d,
                g=g,
                s=s,
                b=b,
            )
        )

    def add_cap(self, *, c: float, a: str, b: str) -> None:
        """Add a two-terminal linear capacitance."""
        self._caps.append(_CapStamp(c=float(c), a=a, b=b))

    @staticmethod
    def _known_value(node: str, inp: str, inn: str, vid: float, vcm: float) -> _KnownValues:
        if node == inp:
            return _KnownValues(+vid / 2.0, vcm)
        if node == inn:
            return _KnownValues(-vid / 2.0, vcm)
        return _KnownValues(0.0, 0.0)

    def _build_node_index(self, sources: frozenset[str]) -> dict[str, int]:
        """Assign matrix indices to unknown non-ground nodes."""
        node_idx: dict[str, int] = {}

        def add(node: str) -> None:
            if node != self.GND and node not in sources and node not in node_idx:
                node_idx[node] = len(node_idx)

        for m in self._mos:
            add(m.d)
            add(m.g)
            add(m.s)
            add(m.b)
        for cap in self._caps:
            add(cap.a)
            add(cap.b)
        return node_idx

    def _assemble(
        self,
        node_idx: dict[str, int],
        *,
        inp: str,
        inn: str,
        vid: float,
        vcm: float,
    ) -> _Assembly:
        n = len(node_idx)
        G = np.zeros((n, n), dtype=float)
        C = np.zeros((n, n), dtype=float)
        rhs_g_dm = np.zeros(n, dtype=float)
        rhs_c_dm = np.zeros(n, dtype=float)
        rhs_g_cm = np.zeros(n, dtype=float)
        rhs_c_cm = np.zeros(n, dtype=float)

        def known(node: str) -> _KnownValues:
            return self._known_value(node, inp, inn, vid, vcm)

        def stamp_admittance(
            mat: np.ndarray,
            rhs_dm: np.ndarray,
            rhs_cm: np.ndarray,
            value: float,
            a: str,
            b: str,
        ) -> None:
            """Stamp value between a and b using entering-current KCL.

            Row for a: value * (Vb - Va). Known-node terms are moved to RHS.
            """
            if value == 0.0:
                return
            ia = node_idx.get(a)
            ib = node_idx.get(b)

            if ia is not None:
                mat[ia, ia] -= value
                if ib is not None:
                    mat[ia, ib] += value
                else:
                    kb = known(b)
                    rhs_dm[ia] -= value * kb.dm
                    rhs_cm[ia] -= value * kb.cm

            if ib is not None:
                mat[ib, ib] -= value
                if ia is not None:
                    mat[ib, ia] += value
                else:
                    ka = known(a)
                    rhs_dm[ib] -= value * ka.dm
                    rhs_cm[ib] -= value * ka.cm

        def stamp_vccs(value: float, out_p: str, out_m: str, ctrl_p: str, ctrl_m: str) -> None:
            """Stamp value*(Vctrl_p - Vctrl_m) flowing from out_p to out_m."""
            if value == 0.0:
                return
            op = node_idx.get(out_p)
            om = node_idx.get(out_m)
            cp = node_idx.get(ctrl_p)
            cm = node_idx.get(ctrl_m)

            def add_row(row: int | None, sign: float) -> None:
                if row is None:
                    return

                if cp is not None:
                    G[row, cp] += sign * value
                else:
                    kp = known(ctrl_p)
                    rhs_g_dm[row] -= sign * value * kp.dm
                    rhs_g_cm[row] -= sign * value * kp.cm

                if cm is not None:
                    G[row, cm] -= sign * value
                else:
                    km = known(ctrl_m)
                    rhs_g_dm[row] += sign * value * km.dm
                    rhs_g_cm[row] += sign * value * km.cm

            # Current leaves out_p and enters out_m.
            add_row(op, -1.0)
            add_row(om, +1.0)

        for m in self._mos:
            stamp_admittance(G, rhs_g_dm, rhs_g_cm, m.gds, m.d, m.s)
            stamp_vccs(m.gm, m.d, m.s, m.g, m.s)
            stamp_vccs(m.gmb, m.d, m.s, m.b, m.s)

        for cap in self._caps:
            stamp_admittance(C, rhs_c_dm, rhs_c_cm, cap.c, cap.a, cap.b)

        return _Assembly(G, C, rhs_g_dm, rhs_c_dm, rhs_g_cm, rhs_c_cm)

    @staticmethod
    def _dc_solve(
        G: np.ndarray, rhs_dm: np.ndarray, rhs_cm: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        rhs = np.column_stack((rhs_dm, rhs_cm))
        solution = np.linalg.solve(G, rhs)
        return solution[:, 0], solution[:, 1]

    def _find_unity_gain(
        self,
        G: np.ndarray,
        C: np.ndarray,
        rhs_g: np.ndarray,
        rhs_c: np.ndarray,
        out_idx: int,
        *,
        n_iter: int,
    ) -> float:
        """Return first unity-gain frequency in Hz for a mostly low-pass response."""
        max_g = float(np.max(np.abs(G))) if G.size else 1.0
        max_g = max(max_g, 1.0)
        cap_vals = np.abs(C[np.nonzero(C)])
        min_c = float(np.min(cap_vals)) if cap_vals.size else 1e-12
        pole_est = max_g / min_c

        lo = max(pole_est * 1e-9, 1e-3)
        hi = max(pole_est * 1e3, lo * 10.0)
        h_lo = _response_mag(G, C, rhs_g, rhs_c, out_idx, lo)
        if h_lo < 1.0:
            return 0.0

        h_hi = _response_mag(G, C, rhs_g, rhs_c, out_idx, hi)
        for _ in range(60):
            if h_hi <= 1.0:
                break
            hi *= 10.0
            h_hi = _response_mag(G, C, rhs_g, rhs_c, out_idx, hi)
        else:
            return float("inf")

        for _ in range(n_iter):
            mid = float(np.sqrt(lo * hi))
            if _response_mag(G, C, rhs_g, rhs_c, out_idx, mid) > 1.0:
                lo = mid
            else:
                hi = mid

        return float(np.sqrt(lo * hi) / (2.0 * np.pi))

    @staticmethod
    def _phase_margin(
        G: np.ndarray,
        C: np.ndarray,
        rhs_g: np.ndarray,
        rhs_c: np.ndarray,
        out_idx: int,
        gbw_hz: float,
        dc_gain: float,
    ) -> float:
        if not np.isfinite(gbw_hz) or gbw_hz <= 0.0:
            return 180.0
        if dc_gain == 0.0:
            return 180.0

        w_unity = 2.0 * np.pi * gbw_hz
        w_ref = max(w_unity * 1e-3, 1e-3)

        # Normalize by the real DC gain to remove arbitrary inversion sign.
        # Include an explicit zero-frequency phase point so the phase lag is
        # measured from the DC transfer, not from a finite reference frequency.
        if w_unity <= w_ref:
            omegas = np.array([w_unity], dtype=float)
        else:
            omegas = np.geomspace(w_ref, w_unity, num=16)
        rel_phase = np.empty(omegas.size + 1, dtype=float)
        rel_phase[0] = 0.0
        for i, omega in enumerate(omegas):
            h = _solve_response(G, C, rhs_g, rhs_c, out_idx, float(omega))
            rel_phase[i + 1] = np.angle(h / dc_gain)
        phase_lag = float(np.unwrap(rel_phase)[-1])
        if phase_lag > 0.0:
            phase_lag -= 2.0 * np.pi

        pm = 180.0 + float(np.degrees(phase_lag))
        return float(np.clip(pm, 0.0, 180.0))

    def solve(
        self,
        *,
        inp: str,
        inn: str,
        out: str,
        gbw_iters: int = 60,
    ) -> SmallSignalResult:
        """Solve the stamped circuit.

        Returns:
            Linear differential gain, unity-gain frequency in Hz, linear CMRR,
            and phase margin in degrees.
        """
        if not self._mos and not self._caps:
            raise RuntimeError("No stamps added; call add_mos/add_cap first.")

        sources = frozenset({inp, inn})
        node_idx = self._build_node_index(sources)
        if out not in node_idx:
            raise ValueError(
                f"Output node '{out}' is not an unknown node. Unknown nodes: {list(node_idx)}"
            )

        assembled = self._assemble(node_idx, inp=inp, inn=inn, vid=1.0, vcm=1.0)
        out_idx = node_idx[out]

        v_dm, v_cm = self._dc_solve(assembled.G, assembled.rhs_g_dm, assembled.rhs_g_cm)
        adm = float(v_dm[out_idx])
        acm = float(v_cm[out_idx])
        cmrr = abs(adm / acm) if abs(acm) > 1e-30 else 1e12

        has_caps = bool(np.any(assembled.C != 0.0) or np.any(assembled.rhs_c_dm != 0.0))
        if has_caps:
            gbw = self._find_unity_gain(
                assembled.G,
                assembled.C,
                assembled.rhs_g_dm,
                assembled.rhs_c_dm,
                out_idx,
                n_iter=gbw_iters,
            )
        else:
            gbw = float("inf") if abs(adm) >= 1.0 else 0.0

        phase_margin = self._phase_margin(
            assembled.G,
            assembled.C,
            assembled.rhs_g_dm,
            assembled.rhs_c_dm,
            out_idx,
            gbw,
            adm,
        )

        return SmallSignalResult(
            gain=adm,
            ugf_hz=gbw,
            cmrr=cmrr,
            phase_margin_deg=phase_margin,
        )
