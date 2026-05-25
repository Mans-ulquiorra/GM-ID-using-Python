"""Shared data types for the reduced-MNA AC solver."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

import numpy as np


GROUND = "gnd"
UNKNOWN_NODE = -1


@dataclass(frozen=True)
class SmallSignalResult:
    """Metrics returned by a small-signal solve.

    Metrics that were explicitly disabled in ``SmallSignalSolver.solve`` are
    returned as ``None``. Gain is always computed because all other metrics
    depend on the differential output response.
    """

    gain: float
    ugf_hz: float | None
    cmrr: float | None
    phase_margin_deg: float | None


class CompiledModel(NamedTuple):
    """Topology compiled for one input pair and output node.

    ``*_idx`` arrays hold integer node indices. ``UNKNOWN_NODE`` means the node
    is either ground or a known ideal input source, so its contribution belongs
    on the RHS instead of in the matrix. ``*_dm`` and ``*_cm`` hold those known
    differential/common-mode source values.
    """

    node_idx: dict[str, int]
    mos_idx: np.ndarray
    mos_dm: np.ndarray
    mos_cm: np.ndarray
    cap_idx: np.ndarray
    cap_dm: np.ndarray
    cap_cm: np.ndarray
    out_idx: int


class MosStamp(NamedTuple):
    """User-facing MOS stamp stored before compilation."""

    gm: float
    gmb: float
    gds: float
    d: str
    g: str
    s: str
    b: str


class CapStamp(NamedTuple):
    """User-facing capacitor stamp stored before compilation."""

    c: float
    a: str
    b: str
