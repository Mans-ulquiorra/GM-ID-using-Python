"""Simple 2-transistor PMOS current mirror."""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

import numpy as np

from mosplot.optimizer import (
    DesignReport, FastMosfet, Instance, Optimizer, OptimizationParameter,
    Passive, Spec, SpectreGenerator, VSource, build_ss_model,
)
from mosplot.plot import Expression, load_lookup_table

__all__ = ["run", "OptimizationParameter", "Spec"]


def scalar(v: Any) -> float:
    return float(np.asarray(v).reshape(-1)[0])


class Circuit:
    """Simple 2-transistor PMOS current mirror.

    Diode + mirror pair -- no cascode. Best compliance, lowest Rout.
    """

    MOSFETS: ClassVar[list[Instance]] = [
        Instance("M1", "pmos", d="IREF", g="IREF", s="vdd", b="vdd"),
        Instance("M2", "pmos", d="VOUT", g="IREF", s="vdd", b="vdd"),
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
        pmos_name: str,
        vdd: float,
        cout: float,
        iref: float,
        k: float,
        fixed_point_iterations: int = 5,
    ) -> None:
        self.vdd = vdd
        self.cout = cout
        self.iref = iref
        self.k = k
        self.vout_dc = vdd / 2
        self.fixed_point_iterations = fixed_point_iterations
        lut = load_lookup_table(lookup_table_path)
        self.pmos = FastMosfet(lut, pmos_name, cache_dir="~/.cache/mosplot/fast_tables", rebuild_cache=False)
        self._gdsid = Expression(["gds", "id"], function=lambda g, i: g / np.abs(i))
        self._gmbsid = Expression(["gmbs", "id"], function=lambda g, i: g / np.abs(i))
        self.device_map: dict[str, str] = {"pmos": pmos_name}
        self.device_dimensions: dict[str, dict[str, float]] = {}
        self.device_operating_points: dict[str, dict[str, float]] = {}
        self.passive_params: dict[str, float] = {}

    def evaluate_specs(self, **params: float) -> dict[str, float | None]:
        IREF = self.iref
        K = self.k
        GMID = params["GMID"]
        L = params["L"]

        VDD = self.vdd
        VOUT_DC = self.vout_dc
        CL = self.cout

        M1_VGS = M1_VDSAT = M1_gdsid = M1_gmbsid = 0.0
        M1_cgs = M1_cgd = M1_cdd = M1_JD = 0.0
        M1_W = M1_VDS = 0.0

        M2_VGS = M2_VDSAT = M2_gdsid = M2_gmbsid = 0.0
        M2_cgs = M2_cgd = M2_cdd = M2_JD = 0.0
        M2_W = M2_VDS = 0.0

        M1_VDS = VDD / 4
        M1_W = 0.0
        M2_W = 0.0

        for _ in range(self.fixed_point_iterations):
            # M1 -- diode-connected reference
            (M1_VGS, M1_VDSAT, M1_gdsid, M1_gmbsid, M1_cgs, M1_cgd, M1_cdd, M1_JD) = [
                scalar(x)
                for x in self.pmos.interpolate(
                    length=L,
                    gmid=GMID,
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
            M1_VDS = M1_VGS
            M1_VDSAT = abs(M1_VDSAT)
            M1_JD = abs(M1_JD)
            if M1_W == 0.0:
                M1_W = IREF / M1_JD

            # M2 -- output mirror (|VDS| = VDD - VOUT_DC at nominal operating point)
            M2_VDS = VDD - VOUT_DC
            (M2_VGS, M2_VDSAT, M2_gdsid, M2_gmbsid, M2_cgs, M2_cgd, M2_cdd, M2_JD) = [
                scalar(x)
                for x in self.pmos.interpolate(
                    length=L,
                    gmid=GMID,
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

        self.device_dimensions = {
            "M1": {"Length": L, "Width": M1_W, "Area": L * M1_W, "Current": IREF, "GMID": GMID},
            "M2": {"Length": L, "Width": M2_W, "Area": L * M2_W, "Current": M2_ID, "GMID": GMID},
        }
        self.device_operating_points = {
            "M1": {"VGS": M1_VGS, "VDS": M1_VDS, "VSB": 0.0, "ID": IREF, "VDSAT": M1_VDSAT},
            "M2": {"VGS": M2_VGS, "VDS": M2_VDS, "VSB": 0.0, "ID": M2_ID, "VDSAT": M2_VDSAT},
        }
        self.passive_params = {"CL": CL}

        # --- Output resistance ---
        ss_params = {
            "M1": {"gm": GMID * IREF, "gmb": abs(M1_gmbsid) * IREF, "gds": M1_gdsid * IREF},
            "M2": {"gm": GMID * M2_ID, "gmb": abs(M2_gmbsid) * M2_ID, "gds": M2_gdsid * M2_ID},
        }
        ss = build_ss_model(
            mosfets=self.MOSFETS, passives=self.PASSIVES, vsources=self.VSOURCES,
            ss_params=ss_params, passive_params={"CL": CL},
        )
        Rout = ss.port("VOUT").resistance()

        Area = M1_W * L + M2_W * L
        Itotal = IREF + M2_ID
        Vcompliance = M2_VDSAT

        return {
            "Rout": Rout,
            "Vcompliance": Vcompliance,
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
        mosfets=circuit.MOSFETS, passives=circuit.PASSIVES, vsources=circuit.VSOURCES,
        device_map=circuit.device_map, dimensions=circuit.device_dimensions,
        passive_params=circuit.passive_params,
        vsource_params=circuit.compute_vsource_params(opt_params),
        output_path=Path(output_path),
    )


def run(
    *,
    lookup_table: str,
    pmos_name: str,
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
        lookup_table_path=lookup_table, pmos_name=pmos_name,
        vdd=vdd, cout=cout, iref=iref, k=k,
        fixed_point_iterations=fixed_point_iterations,
    )
    optimizer = Optimizer(circuit, parameters, target_specs)
    optimizer.optimize(maxiter=maxiter, seed=seed, n_restarts=n_restarts)
    report = DesignReport(circuit, optimizer)
    print(report.report())
    _generate_simulation_netlist(optimizer, output_module)
