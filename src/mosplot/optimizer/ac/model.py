"""Reusable topology model for reduced-MNA small-signal analysis."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property, lru_cache

import numpy as np

from ._types import CompiledModel, GROUND, UNKNOWN_NODE, SmallSignalResult
from .kernels import assemble_compiled, find_unity_gain, phase_margin


def _known_values(node: str, inp: str, inn: str) -> tuple[float, float]:
    """Return known differential/common-mode voltages for ideal input nodes.

    The solver uses a 1 V differential stimulus:

        inp = +0.5 V, inn = -0.5 V

    and a 1 V common-mode stimulus:

        inp = inn = +1 V

    Ground and non-input known nodes are zero for both solves.
    """

    if node == inp:
        return +0.5, 1.0
    if node == inn:
        return -0.5, 1.0
    return 0.0, 0.0


def _node_index_and_known(
    node: str,
    node_idx: dict[str, int],
    inp: str,
    inn: str,
) -> tuple[int, float, float]:
    """Map a node name to either a matrix index or a known-source value."""

    idx = node_idx.get(node)
    if idx is not None:
        return idx, 0.0, 0.0
    dm, cm = _known_values(node, inp, inn)
    return UNKNOWN_NODE, dm, cm


def _compile_node_maps(
    node_idx: dict[str, int],
    node_groups: tuple[tuple[str, ...], ...],
    inp: str,
    inn: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compile node-name tuples into index and known-source arrays.

    ``node_groups`` is either a tuple of MOS nodes ``(d, g, s, b)`` or a tuple
    of capacitor nodes ``(a, b)``. The returned arrays have matching shape:

    * ``idx``: matrix row/column indices, or ``UNKNOWN_NODE``
    * ``dm``: known-node voltage for a 1 V differential input
    * ``cm``: known-node voltage for a 1 V common-mode input
    """

    width = len(node_groups[0]) if node_groups else 0
    idx = np.empty((len(node_groups), width), dtype=np.int64)
    dm = np.zeros_like(idx, dtype=float)
    cm = np.zeros_like(idx, dtype=float)
    for i, nodes in enumerate(node_groups):
        for j, node in enumerate(nodes):
            idx[i, j], dm[i, j], cm[i, j] = _node_index_and_known(node, node_idx, inp, inn)
    return idx, dm, cm


def _dc_solve(
    G: np.ndarray,
    rhs_dm: np.ndarray,
    rhs_cm: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Solve differential and common-mode DC systems in one dense solve."""

    rhs = np.column_stack((rhs_dm, rhs_cm))
    solution = np.linalg.solve(G, rhs)
    return solution[:, 0], solution[:, 1]


def _dc_solve_one(G: np.ndarray, rhs: np.ndarray) -> np.ndarray:
    """Solve only the differential DC system when CMRR is not requested."""

    return np.linalg.solve(G, rhs)


@dataclass(frozen=True)
class SmallSignalModel:
    """Reusable small-signal topology with numeric values supplied per solve.

    This object captures only the topology: MOS terminal names and capacitor
    terminal names. It does not store gm/gds/c values. That separation lets
    optimizer code reuse the same compiled node map while changing only numeric
    device values at every candidate point.
    """

    mos_nodes: tuple[tuple[str, str, str, str], ...]
    cap_nodes: tuple[tuple[str, str], ...]

    @cached_property
    def nodes(self) -> tuple[str, ...]:
        """All nodes in first-seen order.

        Stable ordering matters for reproducible matrix layouts and profiles;
        using a set here would make node indices depend on hash iteration order.
        """

        node_order: dict[str, None] = {}
        for nodes in self.mos_nodes:
            for node in nodes:
                node_order.setdefault(node, None)
        for nodes in self.cap_nodes:
            for node in nodes:
                node_order.setdefault(node, None)
        return tuple(node_order)

    def _node_index(self, inp: str, inn: str) -> dict[str, int]:
        """Assign matrix indices to unknown non-ground nodes."""

        sources = frozenset({inp, inn})
        return {
            node: i
            for i, node in enumerate(
                node for node in self.nodes if node != GROUND and node not in sources
            )
        }

    @lru_cache(maxsize=32)
    def _compile(self, inp: str, inn: str, out: str) -> CompiledModel:
        """Compile topology for a specific input pair and output node.

        The same topology can be solved with different input/output choices, so
        the compiled map is cached by ``(inp, inn, out)``. Typical optimizer
        use has exactly one such tuple, which means this work happens once.
        """

        node_idx = self._node_index(inp, inn)
        if out not in node_idx:
            raise ValueError(
                f"Output node '{out}' is not an unknown node. Unknown nodes: {list(node_idx)}"
            )

        mos_idx, mos_dm, mos_cm = _compile_node_maps(node_idx, self.mos_nodes, inp, inn)
        cap_idx, cap_dm, cap_cm = _compile_node_maps(node_idx, self.cap_nodes, inp, inn)
        return CompiledModel(
            node_idx=node_idx,
            mos_idx=mos_idx,
            mos_dm=mos_dm,
            mos_cm=mos_cm,
            cap_idx=cap_idx,
            cap_dm=cap_dm,
            cap_cm=cap_cm,
            out_idx=node_idx[out],
        )

    def solve(
        self,
        mos_values: np.ndarray,
        cap_values: np.ndarray,
        *,
        inp: str,
        inn: str,
        out: str,
        gbw_iters: int,
        compute_cmrr: bool,
        compute_gbw: bool,
        compute_phase_margin: bool,
    ) -> SmallSignalResult:
        """Solve this topology for one numeric operating point."""

        if compute_phase_margin and not compute_gbw:
            raise ValueError(
                "Phase margin requires GBW; set compute_gbw=True or compute_phase_margin=False."
            )

        compiled = self._compile(inp, inn, out)
        G, C, rhs_g_dm, rhs_c_dm, rhs_g_cm, rhs_c_cm = assemble_compiled(
            mos_values,
            cap_values,
            compiled.mos_idx,
            compiled.mos_dm,
            compiled.mos_cm,
            compiled.cap_idx,
            compiled.cap_dm,
            compiled.cap_cm,
            len(compiled.node_idx),
        )

        if compute_cmrr:
            v_dm, v_cm = _dc_solve(G, rhs_g_dm, rhs_g_cm)
            adm = float(v_dm[compiled.out_idx])
            acm = float(v_cm[compiled.out_idx])
            cmrr = abs(adm / acm) if abs(acm) > 1e-30 else 1e12
        else:
            v_dm = _dc_solve_one(G, rhs_g_dm)
            adm = float(v_dm[compiled.out_idx])
            cmrr = None

        has_caps = bool(np.any(C != 0.0) or np.any(rhs_c_dm != 0.0))
        if compute_gbw:
            if has_caps:
                gbw = float(find_unity_gain(G, C, rhs_g_dm, rhs_c_dm, compiled.out_idx, gbw_iters))
            else:
                gbw = float("inf") if abs(adm) >= 1.0 else 0.0
        else:
            gbw = None

        if compute_phase_margin:
            phase_margin_deg = float(
                phase_margin(G, C, rhs_g_dm, rhs_c_dm, compiled.out_idx, gbw, adm)
            )
        else:
            phase_margin_deg = None

        return SmallSignalResult(
            gain=adm,
            ugf_hz=gbw,
            cmrr=cmrr,
            phase_margin_deg=phase_margin_deg,
        )
