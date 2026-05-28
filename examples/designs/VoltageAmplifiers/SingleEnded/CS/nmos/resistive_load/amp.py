"""Generated gm/ID optimizer circuit model.

This is the circuit/equation file used by the companion *_config.py
script.  Treat it as the base generated model: read it to understand
what quantities exist, and edit it only when you want to add or change
the actual circuit equations.

Execution flow:
1. Unpack optimizer parameters and fixed circuit conditions.
2. Iterate lookup-table operating points to settle widths, currents,
   VGS/VDS/VSB, and small-signal quantities.
3. Build a small-signal AC model and solve AC gain, GBW, PM, and CMRR.
4. Compute derived specs such as area, swing, bias voltages, and
   other circuit-specific constraints.
5. After optimization, export a simulation netlist for the best design.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

import numpy as np

from mosplot.optimizer import (
    DesignReport,
    FastMosfet,
    Instance,
    Optimizer,
    OptimizationParameter,
    Passive,
    Spec,
    SpectreGenerator,
    VSource,
    build_ss_model,
)
from mosplot.plot import Expression, load_lookup_table

__all__ = ["run", "OptimizationParameter", "Spec"]


def scalar(v: Any) -> float:
    return float(np.asarray(v).reshape(-1)[0])


class Circuit:
    """CS amplifier with resistive load."""

    MOSFETS: ClassVar[list[Instance]] = [
        Instance("M1", "nmos", d="VOUT", g="VIN", s="gnd", b="gnd"),
    ]

    PASSIVES: ClassVar[list[Passive]] = [
        Passive("R1", "res", a="vdd", b="VOUT"),
        Passive("COUT", "cap", a="VOUT", b="gnd", external=True),
    ]

    VSOURCES: ClassVar[list[VSource]] = [
        VSource("VDD", p="vdd", n="gnd", supply=True),
    ]

    def __init__(
        self,
        lookup_table_path: str,
        nmos_name: str,
        vdd: float,
        vout_dc: float,
        cout: float,
        fixed_point_iterations: int = 5,
    ) -> None:
        self.vdd = vdd
        self.vout_dc = vout_dc
        self.cout = cout
        self.fixed_point_iterations = fixed_point_iterations
        lut = load_lookup_table(lookup_table_path)
        self.nmos = FastMosfet(lut, nmos_name, cache_dir="~/.cache/mosplot/fast_tables")
        self._gdsid = Expression(["gds", "id"], function=lambda g, i: g / np.abs(i))
        self.device_map: dict[str, str] = {"nmos": nmos_name}
        self.device_dimensions: dict[str, dict[str, float]] = {}
        self.device_operating_points: dict[str, dict[str, float]] = {}
        self.passive_params: dict[str, float] = {}

    def evaluate_specs(self, **params: float) -> dict[str, float | None]:
        M1_GMID = params["M1_GMID"]
        M1_L = params["M1_L"]
        R1 = params["R1"]

        VDD = self.vdd
        VOUT_DC = self.vout_dc
        COUT = self.cout

        M1_ID = (VDD - VOUT_DC) / R1

        M1_VGS = M1_VDSAT = M1_gdsid = 0.0
        M1_cgs = M1_cgd = M1_cdd = M1_JD = 0.0
        M1_W = 0.0
        M1_VDS = VOUT_DC
        M1_VSB = 0.0

        for _ in range(self.fixed_point_iterations):
            (M1_VGS, M1_VDSAT, M1_gdsid, M1_cgs, M1_cgd, M1_cdd, M1_JD) = [
                scalar(x)
                for x in self.nmos.interpolate(
                    length=M1_L,
                    gmid=M1_GMID,
                    vds=abs(M1_VDS),
                    vbs=-abs(M1_VSB),
                    expression=[
                        self.nmos.vgs_expression,
                        self.nmos.vdsat_expression,
                        self._gdsid,
                        self.nmos.cgs_expression,
                        self.nmos.cgd_expression,
                        self.nmos.cdd_expression,
                        self.nmos.current_density_expression,
                    ],
                )
            ]
            M1_VDSAT = abs(M1_VDSAT)
            M1_JD = abs(M1_JD)
            if M1_W == 0.0:
                M1_W = M1_ID / M1_JD

            M1_VDS = VOUT_DC
            M1_VSB = 0.0

        self.device_dimensions = {
            "M1": {
                "Length": M1_L,
                "Width": M1_W,
                "Area": M1_L * M1_W,
                "Current": M1_ID,
                "GMID": M1_GMID,
            },
        }
        self.device_operating_points = {
            "M1": {"VGS": M1_VGS, "VDS": M1_VDS, "VSB": M1_VSB, "ID": M1_ID},
        }

        nmos_tw = self.nmos._width
        ss_params = {
            "M1": {
                "gm": M1_GMID * M1_ID,
                "gmb": 0.0,
                "gds": M1_gdsid * M1_ID,
                "cgs": M1_cgs * (M1_W / nmos_tw),
                "cgd": M1_cgd * (M1_W / nmos_tw),
                "cdd": M1_cdd * (M1_W / nmos_tw),
            },
        }
        self.passive_params = {"R1": R1, "COUT": COUT}
        ss = build_ss_model(
            self.MOSFETS,
            self.PASSIVES,
            self.VSOURCES,
            ss_params,
            self.passive_params,
            signal_nodes={"VIN"},
        )
        ac = ss.transfer(inputs={"VIN": 1.0}, out="VOUT")

        Area = M1_L * M1_W
        Itotal = M1_ID
        VIN_DC = M1_VGS
        VOUT_MAX = VDD
        VOUT_MIN = M1_VDSAT
        Output_Swing = VOUT_MAX - VOUT_MIN

        return {
            "GBW": ac.ugf(),
            "AC Gain (dB)": 20.0 * np.log10(max(abs(ac.gain()), 1e-300)),
            "PM": ac.phase_margin(),
            "DC CMR (dB)": None,
            "Area": Area,
            "Itotal": Itotal,
            "VOUT_DC": VOUT_DC,
            "VIN_DC": VIN_DC,
            "VOUT_MAX": VOUT_MAX,
            "VOUT_MIN": VOUT_MIN,
            "Output_Swing": Output_Swing,
        }

    def compute_vsource_params(self, _opt_params: dict[str, float]) -> dict[str, float]:
        return {}




def _generate_simulation_netlist(optimizer: Optimizer, output_path: str) -> None:
    circuit = optimizer.circuits[0]
    opt_params = optimizer.get_opt_params()
    specs = optimizer.corner_results[0].specs
    generator = SpectreGenerator(
        name="amp",
        ports=["VIN", "VOUT", "vdd", "vss"],
        ground="vss",
        context={
            "vcm": specs.get("VIN_DC", circuit.vdd / 2),
            "vin_dc": specs.get("VIN_DC", circuit.vdd / 2),
            "vout_dc": specs.get("VOUT_DC", circuit.vdd / 2),
        },
    )
    generator.generate(
        mosfets=circuit.MOSFETS,
        passives=circuit.PASSIVES,
        vsources=circuit.VSOURCES,
        device_map=circuit.device_map,
        dimensions=circuit.device_dimensions,
        passive_params=circuit.passive_params,
        vsource_params=circuit.compute_vsource_params(opt_params),
        output_path=Path(output_path),
    )


def run(
    *,
    corners: list[dict],
    parameters: list[OptimizationParameter],
    target_specs: dict[str, Spec],
    output_module: str,
    maxiter: int = 200,
    seed: int = 1,
    n_restarts: int = 1,
    fixed_point_iterations: int = 5,
) -> None:
    corner_names = [c.get("name", f"corner_{i}") for i, c in enumerate(corners)]
    circuit_kwargs = [{k: v for k, v in c.items() if k != "name"} for c in corners]
    circuits = [Circuit(**kwargs, fixed_point_iterations=fixed_point_iterations) for kwargs in circuit_kwargs]
    optimizer = Optimizer(circuits, parameters, target_specs, corner_names=corner_names)
    optimizer.optimize(maxiter=maxiter, seed=seed, n_restarts=n_restarts)
    print(DesignReport(optimizer).report())
    _generate_simulation_netlist(optimizer, output_module)
