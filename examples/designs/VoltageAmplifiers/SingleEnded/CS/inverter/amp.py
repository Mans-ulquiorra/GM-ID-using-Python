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
    """CMOS inverter used as a common-source amplifier."""

    MOSFETS: ClassVar[list[Instance]] = [
        Instance("M1", "nmos", d="VOUT", g="VIN", s="gnd", b="gnd"),
        Instance("M2", "pmos", d="VOUT", g="VIN", s="vdd", b="vdd"),
    ]

    PASSIVES: ClassVar[list[Passive]] = [
        Passive("COUT", "cap", a="VOUT", b="gnd", external=True),
    ]

    VSOURCES: ClassVar[list[VSource]] = [
        VSource("VDD", p="vdd", n="gnd", supply=True),
    ]

    def __init__(
        self,
        lookup_table_path: str,
        nmos_name: str,
        pmos_name: str,
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
        self.pmos = FastMosfet(lut, pmos_name, cache_dir="~/.cache/mosplot/fast_tables")
        self._gdsid = Expression(["gds", "id"], function=lambda g, i: g / np.abs(i))
        self.device_map: dict[str, str] = {"nmos": nmos_name, "pmos": pmos_name}
        self.device_dimensions: dict[str, dict[str, float]] = {}
        self.device_operating_points: dict[str, dict[str, float]] = {}
        self.passive_params: dict[str, float] = {}

    def evaluate_specs(self, **params: float) -> dict[str, float | None]:
        M1_ID = params["M1_ID"]
        M1_GMID = params["M1_GMID"]
        M1_L = params["M1_L"]
        M2_GMID = params["M2_GMID"]
        M2_L = params["M2_L"]

        VDD = self.vdd
        VOUT_DC = self.vout_dc
        COUT = self.cout

        M1_VGS = M1_VDSAT = M1_gdsid = 0.0
        M1_cgs = M1_cgd = M1_cdd = M1_JD = 0.0
        M1_W = 0.0
        M1_VDS = VOUT_DC
        M1_VSB = 0.0
        M2_VGS = M2_VDSAT = M2_gdsid = 0.0
        M2_cgs = M2_cgd = M2_cdd = M2_JD = 0.0
        M2_W = 0.0
        M2_VDS = VDD - VOUT_DC
        M2_VSB = 0.0

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

            M2_ID = M1_ID
            (M2_VGS, M2_VDSAT, M2_gdsid, M2_cgs, M2_cgd, M2_cdd, M2_JD) = [
                scalar(x)
                for x in self.pmos.interpolate(
                    length=M2_L,
                    gmid=M2_GMID,
                    vds=-abs(M2_VDS),
                    vbs=0.0,
                    expression=[
                        self.pmos.vsg_expression,
                        self.pmos.vdsat_expression,
                        self._gdsid,
                        self.pmos.cgs_expression,
                        self.pmos.cgd_expression,
                        self.pmos.cdd_expression,
                        self.pmos.current_density_expression,
                    ],
                )
            ]
            M2_VDSAT = abs(M2_VDSAT)
            M2_JD = abs(M2_JD)
            if M2_W == 0.0:
                M2_W = M2_ID / M2_JD

            M1_VDS = VOUT_DC
            M1_VSB = 0.0
            M2_VDS = VDD - VOUT_DC
            M2_VSB = 0.0

        self.device_dimensions = {
            "M1": {
                "Length": M1_L,
                "Width": M1_W,
                "Area": M1_L * M1_W,
                "Current": M1_ID,
                "GMID": M1_GMID,
            },
            "M2": {
                "Length": M2_L,
                "Width": M2_W,
                "Area": M2_L * M2_W,
                "Current": M2_ID,
                "GMID": M2_GMID,
            },
        }
        self.device_operating_points = {
            "M1": {"VGS": M1_VGS, "VDS": M1_VDS, "VSB": M1_VSB, "ID": M1_ID},
            "M2": {"VGS": M2_VGS, "VDS": M2_VDS, "VSB": M2_VSB, "ID": M2_ID},
        }

        nmos_tw = self.nmos._width
        pmos_tw = self.pmos._width
        ss_params = {
            "M1": {
                "gm": M1_GMID * M1_ID,
                "gmb": 0.0,
                "gds": M1_gdsid * M1_ID,
                "cgs": M1_cgs * (M1_W / nmos_tw),
                "cgd": M1_cgd * (M1_W / nmos_tw),
                "cdd": M1_cdd * (M1_W / nmos_tw),
            },
            "M2": {
                "gm": M2_GMID * M2_ID,
                "gmb": 0.0,
                "gds": M2_gdsid * M2_ID,
                "cgs": M2_cgs * (M2_W / pmos_tw),
                "cgd": M2_cgd * (M2_W / pmos_tw),
                "cdd": M2_cdd * (M2_W / pmos_tw),
            },
        }
        self.passive_params = {"COUT": COUT}
        ss = build_ss_model(
            self.MOSFETS,
            self.PASSIVES,
            self.VSOURCES,
            ss_params,
            self.passive_params,
            signal_nodes={"VIN"},
        )
        ac = ss.transfer(inputs={"VIN": 1.0}, out="VOUT")

        DC_Error = abs(M1_VGS + M2_VGS - VDD) / VDD
        Area = M1_L * M1_W + M2_L * M2_W
        Itotal = M1_ID
        VIN_DC = M1_VGS
        VOUT_MAX = VDD - M2_VDSAT
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
            "DC_Error": DC_Error,
        }

    def compute_vsource_params(self, _opt_params: dict[str, float]) -> dict[str, float]:
        return {}


def build_circuit(**kwargs) -> Circuit:
    return Circuit(**kwargs)


def _generate_simulation_netlist(optimizer: Optimizer, output_path: str) -> None:
    circuit = optimizer.circuit
    opt_params = optimizer.get_opt_params()
    specs = circuit.evaluate_specs(**opt_params)
    generator = SpectreGenerator(
        name="inv_amp",
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
    lookup_table: str,
    nmos_name: str,
    pmos_name: str,
    vdd: float,
    vout_dc: float,
    cout: float,
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
        pmos_name=pmos_name,
        vdd=vdd,
        vout_dc=vout_dc,
        cout=cout,
        fixed_point_iterations=fixed_point_iterations,
    )
    optimizer = Optimizer(circuit, parameters, target_specs)
    optimizer.optimize(maxiter=maxiter, seed=seed, n_restarts=n_restarts)
    report = DesignReport(circuit, optimizer)
    print(report.report())
    _generate_simulation_netlist(optimizer, output_module)
