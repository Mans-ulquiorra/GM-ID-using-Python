"""Generated gm/ID optimizer circuit model.

This is the circuit/equation file used by the companion *_config.py
script.  Treat it as the base generated model: read it to understand
what quantities exist, and edit it only when you want to add or change
the actual circuit equations.

Execution flow:
1. Unpack optimizer parameters and fixed circuit conditions.
2. Iterate lookup-table operating points to settle widths, currents,
   VGS/VDS/VSB, and small-signal quantities.
3. Build a small-signal AC model and solve output resistance.
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
    """Standard cascode NMOS current mirror.

    Diode-stacked reference branch -- self-biased, no external VBN.
    Cascode output boosts Rout at the cost of headroom.
    """

    MOSFETS: ClassVar[list[Instance]] = [
        Instance("M1", "nmos", d="n01", g="n01", s="gnd", b="gnd"),
        Instance("M4", "nmos", d="IREF", g="IREF", s="n01", b="gnd"),
        Instance("M2", "nmos", d="n02", g="n01", s="gnd", b="gnd"),
        Instance("M3", "nmos", d="VOUT", g="IREF", s="n02", b="gnd"),
    ]

    PASSIVES: ClassVar[list[Passive]] = [
        Passive("CL", "cap", a="VOUT", b="gnd", external=True),
    ]

    VSOURCES: ClassVar[list[VSource]] = [
        VSource("VDD", p="vdd", n="gnd", supply=True),
    ]

    def __init__(
        self,
        lookup_table_path: str,
        nmos_name: str,
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
        self.nmos = FastMosfet(lut, nmos_name, cache_dir="~/.cache/mosplot/fast_tables")
        self._gdsid = Expression(["gds", "id"], function=lambda g, i: g / np.abs(i))
        self._gmbsid = Expression(["gmbs", "id"], function=lambda g, i: g / np.abs(i))
        self.device_map: dict[str, str] = {"nmos": nmos_name}
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
        M4_VDS = VDD / 4
        M1_W = 0.0
        M2_W = 0.0
        M3_W = 0.0
        M4_W = 0.0

        for _ in range(self.fixed_point_iterations):
            # M1 -- bottom diode (VDS = VGS)
            (M1_VGS, M1_VDSAT, M1_gdsid, M1_gmbsid, M1_cgs, M1_cgd, M1_cdd, M1_JD) = [
                scalar(x)
                for x in self.nmos.interpolate(
                    length=L_M1,
                    gmid=GMID_M1,
                    vds=abs(M1_VDS),
                    vbs=-abs(0.0),
                    expression=[
                        self.nmos.vgs_expression,
                        self.nmos.vdsat_expression,
                        self._gdsid,
                        self._gmbsid,
                        self.nmos.cgs_expression,
                        self.nmos.cgd_expression,
                        self.nmos.cdd_expression,
                        self.nmos.current_density_expression,
                    ],
                )
            ]
            M1_VDS = abs(M1_VGS)
            M1_VDSAT = abs(M1_VDSAT)
            M1_JD = abs(M1_JD)
            if M1_W == 0.0:
                M1_W = IREF / M1_JD

            # M4 -- top diode (VDS = VGS, body effect from n01)
            M4_VSB = M1_VDS
            (M4_VGS, M4_VDSAT, M4_gdsid, M4_gmbsid, M4_cgs, M4_cgd, M4_cdd, M4_JD) = [
                scalar(x)
                for x in self.nmos.interpolate(
                    length=L_M3,
                    gmid=GMID_M3,
                    vds=abs(M4_VDS),
                    vbs=-abs(M4_VSB),
                    expression=[
                        self.nmos.vgs_expression,
                        self.nmos.vdsat_expression,
                        self._gdsid,
                        self._gmbsid,
                        self.nmos.cgs_expression,
                        self.nmos.cgd_expression,
                        self.nmos.cdd_expression,
                        self.nmos.current_density_expression,
                    ],
                )
            ]
            M4_VDS = abs(M4_VGS)
            M4_VDSAT = abs(M4_VDSAT)
            M4_JD = abs(M4_JD)
            if M4_W == 0.0:
                M4_W = IREF / M4_JD

            # M2 -- bottom mirror (VGS set by M1 gate via n01)
            M2_VDS = abs(M1_VGS)
            (M2_VGS, M2_VDSAT, M2_gdsid, M2_gmbsid, M2_cgs, M2_cgd, M2_cdd, M2_JD) = [
                scalar(x)
                for x in self.nmos.interpolate(
                    length=L_M1,
                    gmid=GMID_M1,
                    vds=abs(M2_VDS),
                    vbs=-abs(0.0),
                    expression=[
                        self.nmos.vgs_expression,
                        self.nmos.vdsat_expression,
                        self._gdsid,
                        self._gmbsid,
                        self.nmos.cgs_expression,
                        self.nmos.cgd_expression,
                        self.nmos.cdd_expression,
                        self.nmos.current_density_expression,
                    ],
                )
            ]
            M2_VDSAT = abs(M2_VDSAT)
            M2_ID = K * IREF
            M2_JD = abs(M2_JD)
            if M2_W == 0.0:
                M2_W = M2_ID / M2_JD

            # M3 -- top cascode (gate = IREF)
            M3_VDS = VOUT_DC - M2_VDS
            M3_VSB = M2_VDS
            (M3_VGS, M3_VDSAT, M3_gdsid, M3_gmbsid, M3_cgs, M3_cgd, M3_cdd, M3_JD) = [
                scalar(x)
                for x in self.nmos.interpolate(
                    length=L_M3,
                    gmid=GMID_M3,
                    vds=abs(M3_VDS),
                    vbs=-abs(M3_VSB),
                    expression=[
                        self.nmos.vgs_expression,
                        self.nmos.vdsat_expression,
                        self._gdsid,
                        self._gmbsid,
                        self.nmos.cgs_expression,
                        self.nmos.cgd_expression,
                        self.nmos.cdd_expression,
                        self.nmos.current_density_expression,
                    ],
                )
            ]
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
        VOUT_MIN = M2_VDS + M3_VDSAT

        return {
            "Rout": Rout,
            "Vcompliance": VOUT_MIN,
            "Iout": M2_ID,
            "Area": Area,
            "Itotal": Itotal,
        }

    def compute_vsource_params(self, opt_params: dict[str, float]) -> dict[str, float]:
        return {}


def build_circuit(**kwargs) -> Circuit:
    return Circuit(**kwargs)


def _generate_simulation_netlist(optimizer: Optimizer, output_path: str) -> None:
    circuit = optimizer.circuit
    opt_params = optimizer.get_opt_params()
    specs = circuit.evaluate_specs(**opt_params)
    generator = SpectreGenerator(
        name="Current_Mirror",
        ports=["IREF", "VOUT", "vdd", "vss"],
        ground="vss",
        context={
            "vout_dc": float(circuit.vout_dc),
            "vdd": float(circuit.vdd),
            "iref": float(circuit.iref),
            "k": float(circuit.k),
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
    lookup_table: str,
    nmos_name: str,
    vdd: float,
    cout: float,
    iref: float,
    k: float,
    parameters: list[OptimizationParameter],
    target_specs: dict[str, Spec],
    output_module: str,
    maxiter: int = 200,
    seed: int = 1,
    n_restarts: int = 1,
    fixed_point_iterations: int = 5,
) -> None:
    circuit = Circuit(
        lookup_table_path=lookup_table,
        nmos_name=nmos_name,
        vdd=vdd,
        cout=cout,
        iref=iref,
        k=k,
        fixed_point_iterations=fixed_point_iterations,
    )
    optimizer = Optimizer(circuit, parameters, target_specs)
    optimizer.optimize(maxiter=maxiter, seed=seed, n_restarts=n_restarts)
    report = DesignReport(circuit, optimizer)
    print(report.report())
    _generate_simulation_netlist(optimizer, output_module)
