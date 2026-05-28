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
    """Wide-swing cascode PMOS current mirror."""

    MOSFETS: ClassVar[list[Instance]] = [
        Instance("M1", "pmos", d="n01",  g="IREF", s="vdd", b="vdd"),
        Instance("M2", "pmos", d="n02",  g="IREF", s="vdd", b="vdd"),
        Instance("M3", "pmos", d="VOUT", g="vbp",  s="n02", b="vdd"),
        Instance("M4", "pmos", d="IREF", g="vbp",  s="n01", b="vdd"),
    ]

    PASSIVES: ClassVar[list[Passive]] = [
        Passive("CL", "cap", a="VOUT", b="gnd", external=True),
    ]

    VSOURCES: ClassVar[list[VSource]] = [
        VSource("VDD", p="vdd", n="gnd", supply=True),
        VSource("VBP", p="vbp", n="gnd"),
    ]

    def __init__(
        self,
        lookup_table_path: str,
        pmos_name: str,
        vdd: float,
        cout: float,
        iref: float,
        k: float,
        vdsat_margin: float = 0.05,
        fixed_point_iterations: int = 5,
    ) -> None:
        self.vdd = vdd
        self.cout = cout
        self.iref = iref
        self.k = k
        self.vdsat_margin = vdsat_margin
        self.vout_dc = vdd / 2
        self.fixed_point_iterations = fixed_point_iterations
        lut = load_lookup_table(lookup_table_path)
        self.pmos = FastMosfet(lut, pmos_name, cache_dir="~/.cache/mosplot/fast_tables")
        self._gdsid = Expression(["gds", "id"], function=lambda g, i: g / np.abs(i))
        self._gmbsid = Expression(["gmbs", "id"], function=lambda g, i: g / np.abs(i))
        self.device_map: dict[str, str] = {"pmos": pmos_name}
        self.device_dimensions: dict[str, dict[str, float]] = {}
        self.device_operating_points: dict[str, dict[str, float]] = {}
        self.passive_params: dict[str, float] = {}

    def evaluate_specs(self, **params: float) -> dict[str, float | None]:
        IREF = self.iref
        K = self.k
        GMID_M1 = params["GMID_M1"]
        L_M1 = params["L_M1"]
        GMID_M3 = params["GMID_M3"]
        L_M3 = params["L_M3"]

        VDSAT_MARGIN = self.vdsat_margin

        VDD = self.vdd
        VOUT_DC = self.vout_dc
        CL = self.cout

        M1_VGS = M1_VDSAT = M1_gdsid = M1_gmbsid = 0.0
        M1_cgs = M1_cgd = M1_cdd = M1_JD = 0.0
        M1_W = M1_VDS = M1_VSB = 0.0

        M2_VGS = M2_VDSAT = M2_gdsid = M2_gmbsid = 0.0
        M2_cgs = M2_cgd = M2_cdd = M2_JD = 0.0
        M2_W = M2_VDS = M2_VSB = 0.0

        M3_VGS = M3_VDSAT = M3_gdsid = M3_gmbsid = 0.0
        M3_cgs = M3_cgd = M3_cdd = M3_JD = 0.0
        M3_W = M3_VDS = M3_VSB = 0.0

        M4_VGS = M4_VDSAT = M4_gdsid = M4_gmbsid = 0.0
        M4_cgs = M4_cgd = M4_cdd = M4_JD = 0.0
        M4_W = M4_VDS = M4_VSB = 0.0

        M1_VDS = VDD / 4
        M2_VDS = VDD / 4
        M1_W = 0.0
        M2_W = 0.0
        M3_W = 0.0
        M4_W = 0.0

        for _ in range(self.fixed_point_iterations):
            # M1 -- top mirror device, input side (ID = IREF)
            (M1_VGS, M1_VDSAT, M1_gdsid, M1_gmbsid, M1_cgs, M1_cgd, M1_cdd, M1_JD) = [
                scalar(x)
                for x in self.pmos.interpolate(
                    length=L_M1,
                    gmid=GMID_M1,
                    vds=-abs(M1_VDS),
                    vbs=-0.0,
                    expression=[
                        self.pmos.vgs_expression,
                        self.pmos.vdsat_expression,
                        self._gdsid,
                        self._gmbsid,
                        self.pmos.cgs_expression,
                        self.pmos.cgd_expression,
                        self.pmos.cdd_expression,
                        self.pmos.current_density_expression,
                    ],
                )
            ]
            M1_VGS = abs(M1_VGS)
            M1_VDSAT = abs(M1_VDSAT)
            M1_JD = abs(M1_JD)
            if M1_W == 0.0:
                M1_W = IREF / M1_JD

            # M4 -- cascode, input side (ID = IREF)
            M1_VDS = M1_VDSAT + VDSAT_MARGIN
            M4_VDS = M1_VGS - M1_VDS
            M4_VSB = -M1_VDS
            (M4_VGS, M4_VDSAT, M4_gdsid, M4_gmbsid, M4_cgs, M4_cgd, M4_cdd, M4_JD) = [
                scalar(x)
                for x in self.pmos.interpolate(
                    length=L_M3,
                    gmid=GMID_M3,
                    vds=-abs(M4_VDS),
                    vbs=-M4_VSB,
                    expression=[
                        self.pmos.vgs_expression,
                        self.pmos.vdsat_expression,
                        self._gdsid,
                        self._gmbsid,
                        self.pmos.cgs_expression,
                        self.pmos.cgd_expression,
                        self.pmos.cdd_expression,
                        self.pmos.current_density_expression,
                    ],
                )
            ]
            M4_VGS = abs(M4_VGS)
            M4_VDSAT = abs(M4_VDSAT)
            M4_JD = abs(M4_JD)
            if M4_W == 0.0:
                M4_W = IREF / M4_JD

            VBP = VDD - M1_VDS - M4_VGS

            # M2 -- top mirror device, output side (ID = K * IREF)
            (M2_VGS, M2_VDSAT, M2_gdsid, M2_gmbsid, M2_cgs, M2_cgd, M2_cdd, M2_JD) = [
                scalar(x)
                for x in self.pmos.interpolate(
                    length=L_M1,
                    gmid=GMID_M1,
                    vds=-abs(M2_VDS),
                    vbs=-0.0,
                    expression=[
                        self.pmos.vgs_expression,
                        self.pmos.vdsat_expression,
                        self._gdsid,
                        self._gmbsid,
                        self.pmos.cgs_expression,
                        self.pmos.cgd_expression,
                        self.pmos.cdd_expression,
                        self.pmos.current_density_expression,
                    ],
                )
            ]
            M2_VGS = abs(M2_VGS)
            M2_VDSAT = abs(M2_VDSAT)
            M2_ID = K * IREF
            M2_JD = abs(M2_JD)
            if M2_W == 0.0:
                M2_W = M2_ID / M2_JD

            # M3 -- cascode, output side (ID = K * IREF)
            M2_VDS = M2_VDSAT + VDSAT_MARGIN
            M3_VDS = VDD - M2_VDS - VOUT_DC
            M3_VSB = -M2_VDS
            (M3_VGS, M3_VDSAT, M3_gdsid, M3_gmbsid, M3_cgs, M3_cgd, M3_cdd, M3_JD) = [
                scalar(x)
                for x in self.pmos.interpolate(
                    length=L_M3,
                    gmid=GMID_M3,
                    vds=-abs(M3_VDS),
                    vbs=-M3_VSB,
                    expression=[
                        self.pmos.vgs_expression,
                        self.pmos.vdsat_expression,
                        self._gdsid,
                        self._gmbsid,
                        self.pmos.cgs_expression,
                        self.pmos.cgd_expression,
                        self.pmos.cdd_expression,
                        self.pmos.current_density_expression,
                    ],
                )
            ]
            M3_VGS = abs(M3_VGS)
            M3_VDSAT = abs(M3_VDSAT)
            M3_ID = M2_ID
            M3_JD = abs(M3_JD)
            if M3_W == 0.0:
                M3_W = M3_ID / M3_JD

        self.device_dimensions = {
            "M1": {
                "Length": L_M1,
                "Width": M1_W,
                "Area": L_M1 * M1_W,
                "Current": IREF,
                "GMID": GMID_M1,
            },
            "M2": {
                "Length": L_M1,
                "Width": M2_W,
                "Area": L_M1 * M2_W,
                "Current": M2_ID,
                "GMID": GMID_M1,
            },
            "M3": {
                "Length": L_M3,
                "Width": M3_W,
                "Area": L_M3 * M3_W,
                "Current": M3_ID,
                "GMID": GMID_M3,
            },
            "M4": {
                "Length": L_M3,
                "Width": M4_W,
                "Area": L_M3 * M4_W,
                "Current": IREF,
                "GMID": GMID_M3,
            },
        }
        self.device_operating_points = {
            "M1": {"VGS": M1_VGS, "VDS": M1_VDS, "VSB": M1_VSB, "ID": IREF, "VDSAT": M1_VDSAT},
            "M2": {"VGS": M2_VGS, "VDS": M2_VDS, "VSB": M2_VSB, "ID": M2_ID, "VDSAT": M2_VDSAT},
            "M3": {"VGS": M3_VGS, "VDS": M3_VDS, "VSB": M3_VSB, "ID": M3_ID, "VDSAT": M3_VDSAT},
            "M4": {"VGS": M4_VGS, "VDS": M4_VDS, "VSB": M4_VSB, "ID": IREF, "VDSAT": M4_VDSAT},
        }
        self.passive_params = {"CL": CL}

        # --- Output resistance ---
        ss_params = {
            "M1": {
                "gm": GMID_M1 * IREF,
                "gmb": abs(M1_gmbsid) * IREF,
                "gds": M1_gdsid * IREF,
            },
            "M2": {
                "gm": GMID_M1 * M2_ID,
                "gmb": abs(M2_gmbsid) * M2_ID,
                "gds": M2_gdsid * M2_ID,
            },
            "M3": {
                "gm": GMID_M3 * M3_ID,
                "gmb": abs(M3_gmbsid) * M3_ID,
                "gds": M3_gdsid * M3_ID,
            },
            "M4": {
                "gm": GMID_M3 * IREF,
                "gmb": abs(M4_gmbsid) * IREF,
                "gds": M4_gdsid * IREF,
            },
        }
        ss = build_ss_model(
            mosfets=self.MOSFETS,
            passives=self.PASSIVES,
            vsources=self.VSOURCES,
            ss_params=ss_params,
            passive_params={"CL": CL},
        )
        Rout = ss.port("VOUT").resistance()

        # --- Specs ---
        Area = M1_W * L_M1 + M2_W * L_M1 + M3_W * L_M3 + M4_W * L_M3
        Itotal = IREF + M2_ID
        Vcompliance = M2_VDS + M3_VDSAT

        return {
            "Rout": Rout,
            "Vcompliance": Vcompliance,
            "Iout": M2_ID,
            "Area": Area,
            "Itotal": Itotal,
            "VBP": VBP,
        }

    def compute_vsource_params(self, opt_params: dict[str, float]) -> dict[str, float]:
        self.evaluate_specs(**opt_params)
        ops = self.device_operating_points
        VBP = self.vdd - ops.get("M1", {}).get("VDS", 0.0) - ops.get("M4", {}).get("VGS", 0.0)
        return {"VBP": VBP}




def _generate_simulation_netlist(optimizer: Optimizer, output_path: str) -> None:
    circuit = optimizer.circuits[0]
    opt_params = optimizer.get_opt_params()
    specs = optimizer.corner_results[0].specs
    generator = SpectreGenerator(
        name="Current_Mirror",
        ports=["IREF", "VOUT", "vdd", "vss"],
        ground="vss",
        context={
            "vout_dc": float(circuit.vout_dc),
            "vdd": float(circuit.vdd),
            "iref": float(circuit.iref),
            "k": float(circuit.k),
            "vbp": float(specs.get("VBP", 0)),
            "iout": float(specs.get("Iout", 0)),
            "rout": float(specs.get("Rout", 0)),
            "vcompliance": float(specs.get("Vcompliance", 0)),
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
