"""Reusable topology model for reduced-MNA small-signal analysis."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property, lru_cache

import numpy as np

from ._types import CompiledModel, GROUND, UNKNOWN_NODE, SmallSignalResult
from .kernels import assemble_compiled, find_unity_gain, phase_margin


InputItems = tuple[tuple[str, float], ...]


def canonical_inputs(inputs: dict[str, float] | None) -> InputItems:
    if not inputs:
        return ()
    return tuple(sorted((str(node), float(value)) for node, value in inputs.items()))


def _input_value(node: str, inputs: InputItems) -> float:
    for input_node, value in inputs:
        if node == input_node:
            return value
    return 0.0


def _node_index_and_known(
    node: str,
    node_idx: dict[str, int],
    inputs: InputItems,
    cm_inputs: InputItems,
) -> tuple[int, float, float]:
    """Map a node name to either a matrix index or a known-source value."""

    idx = node_idx.get(node)
    if idx is not None:
        return idx, 0.0, 0.0
    return UNKNOWN_NODE, _input_value(node, inputs), _input_value(node, cm_inputs)


def _compile_node_maps(
    node_idx: dict[str, int],
    node_groups: tuple[tuple[str, ...], ...],
    inputs: InputItems,
    cm_inputs: InputItems,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compile node-name tuples into index and known-source arrays.

    ``node_groups`` is either a tuple of MOS nodes ``(d, g, s, b)`` or a tuple
    of capacitor nodes ``(a, b)``. The returned arrays have matching shape:

    * ``idx``: matrix row/column indices, or ``UNKNOWN_NODE``
    * ``dm``: known-node voltage for the requested AC input
    * ``cm``: known-node voltage for the optional common-mode input
    """

    width = len(node_groups[0]) if node_groups else 0
    idx = np.empty((len(node_groups), width), dtype=np.int64)
    dm = np.zeros_like(idx, dtype=float)
    cm = np.zeros_like(idx, dtype=float)
    for i, nodes in enumerate(node_groups):
        for j, node in enumerate(nodes):
            idx[i, j], dm[i, j], cm[i, j] = _node_index_and_known(node, node_idx, inputs, cm_inputs)
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

    def _node_index(self, known_nodes: frozenset[str]) -> dict[str, int]:
        """Assign matrix indices to unknown non-ground nodes."""

        return {
            node: i
            for i, node in enumerate(
                node for node in self.nodes if node != GROUND and node not in known_nodes
            )
        }

    @lru_cache(maxsize=32)
    def _compile(self, inputs: InputItems, cm_inputs: InputItems, out: str) -> CompiledModel:
        """Compile topology for a specific known-node set and output node.

        The same topology can be solved with different input vectors, so the
        compiled map is cached by input nodes and output. Typical optimizer use
        has exactly one such tuple, which means this work happens once.
        """

        known_nodes = frozenset(node for node, _ in inputs) | frozenset(
            node for node, _ in cm_inputs
        )
        node_idx = self._node_index(known_nodes)
        if out not in node_idx:
            raise ValueError(
                f"Output node '{out}' is not an unknown node. Unknown nodes: {list(node_idx)}"
            )

        mos_idx, mos_dm, mos_cm = _compile_node_maps(node_idx, self.mos_nodes, inputs, cm_inputs)
        cap_idx, cap_dm, cap_cm = _compile_node_maps(node_idx, self.cap_nodes, inputs, cm_inputs)
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
        inputs: dict[str, float],
        cm_inputs: dict[str, float] | None,
        out: str,
        gbw_iters: int,
        compute_cmrr: bool,
        compute_gbw: bool,
        compute_phase_margin: bool,
    ) -> SmallSignalResult:
        """Solve this topology for one numeric operating point."""

        input_items = canonical_inputs(inputs)
        cm_input_items = canonical_inputs(cm_inputs) if compute_cmrr else ()
        if not input_items:
            raise ValueError("At least one AC input must be provided.")
        if compute_cmrr and not cm_input_items:
            raise ValueError("CMRR requires cm_inputs.")
        if compute_phase_margin and not compute_gbw:
            raise ValueError(
                "Phase margin requires GBW; set compute_gbw=True or compute_phase_margin=False."
            )

        compiled = self._compile(input_items, cm_input_items, out)
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
