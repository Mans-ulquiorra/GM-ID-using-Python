from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..topology.elements import Instance, Passive, VSource


class NetlistGenerator(ABC):
    """Interface for subcircuit netlist generators.

    Concrete subclasses emit a simulator-ready file from the unified topology
    representation produced by the optimizer.
    """

    @abstractmethod
    def generate(
        self,
        mosfets: list[Instance],
        passives: list[Passive],
        vsources: list[VSource],
        device_map: dict,
        dimensions: dict,
        passive_params: dict[str, float],
        vsource_params: dict[str, float],
        output_path: Path,
    ) -> Path:
        """Write the netlist to output_path and return the path."""
