from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import NetlistGenerator
from ..topology.elements import Instance, Passive, VSource
from ._util import si


class SpectreGenerator(NetlistGenerator):
    """Emit a Spectre subcircuit (.scs) from the optimized topology.

    Parameters
    ----------
    name:
        Subcircuit cell name.
    ports:
        Ordered list of external port node names (included in the subckt line).
    ground:
        The port that serves as circuit ground.  Internal "gnd" nodes are
        remapped to this name in the output.  Defaults to "vss".
    """

    def __init__(
        self,
        name: str,
        ports: list[str],
        ground: str = "vss",
        context: dict[str, Any] | None = None,
    ) -> None:
        self.name = name
        self.ports = ports
        self.ground = ground
        self.context = context or {}

    def _node(self, n: str) -> str:
        return self.ground if n == "gnd" else n

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
        lines: list[str] = []
        if self.context:
            params = " ".join(
                f"{key}={si(float(value))}" for key, value in sorted(self.context.items())
            )
            lines.append(f"parameters {params}")

        port_str = " ".join(self.ports)
        lines.append(f"subckt {self.name} ({port_str})")

        for inst in mosfets:
            model = device_map[inst.group]["model"]
            dim = dimensions[inst.group]
            d, g, s, b = (self._node(x) for x in (inst.d, inst.g, inst.s, inst.b))
            l_str = si(dim["Length"])
            w_str = si(dim["Width"])
            lines.append(f"{inst.name} ({d} {g} {s} {b}) {model} l={l_str} w={w_str}")

        for passive in passives:
            if passive.external:
                continue
            val = passive_params[passive.name]
            a, b = self._node(passive.a), self._node(passive.b)
            if passive.kind == "cap":
                lines.append(f"{passive.name} ({a} {b}) capacitor c={si(val)}")
            elif passive.kind == "res":
                lines.append(f"{passive.name} ({a} {b}) resistor r={si(val)}")

        for vs in vsources:
            p, n = self._node(vs.p), self._node(vs.n)
            lines.append(f"{vs.name} ({p} {n}) vsource dc={si(vsource_params[vs.name])}")

        lines.append(f"ends {self.name}")

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return output_path
