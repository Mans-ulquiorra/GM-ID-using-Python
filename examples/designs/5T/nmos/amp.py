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
    """gm/ID optimizer for A010003.

    Design cell name: A010003
    Input: DIFF  Output: SE  Feedback: NONE
    """

    MOSFETS: ClassVar[list[Instance]] = [
        Instance("M1a", "M1a", d="n01", g="VINP", s="n02", b="gnd"),
        Instance("M1b", "M1b", d="VOUT", g="VINN", s="n02", b="gnd"),
        Instance("M2a", "M2a", d="n01", g="n01", s="vdd", b="vdd"),
        Instance("M2b", "M2b", d="VOUT", g="n01", s="vdd", b="vdd"),
        Instance("M3", "M3", d="n02", g="gnd", s="gnd", b="gnd"),
    ]

    PASSIVES: ClassVar[list[Passive]] = [
        Passive("COUT", "cap", a="VOUT", b="gnd"),
    ]

    VSOURCES: ClassVar[list[VSource]] = [
        VSource("VDD", p="vdd", n="gnd"),
        VSource("VBN", p="VBN", n="gnd"),
    ]

    NETLIST_MOSFETS: ClassVar[list[Instance]] = [
        Instance("M1a", "M1a", d="n01", g="VINP", s="n02", b="gnd"),
        Instance("M1b", "M1b", d="VOUT", g="VINN", s="n02", b="gnd"),
        Instance("M2a", "M2a", d="n01", g="n01", s="vdd", b="vdd"),
        Instance("M2b", "M2b", d="VOUT", g="n01", s="vdd", b="vdd"),
        Instance("M3", "M3", d="n02", g="vbn", s="gnd", b="gnd"),
    ]

    NETLIST_PASSIVES: ClassVar[list[Passive]] = [
        Passive("COUT", "cap", a="VOUT", b="gnd", external=True),
    ]

    NETLIST_VSOURCES: ClassVar[list[VSource]] = [
        VSource("VBN", p="vbn", n="gnd"),
    ]

    def __init__(
        self,
        lookup_table_path: str,
        nmos_name: str,
        pmos_name: str,
        vdd: float,
        vin_cm: float,
        cout: float,
        fixed_point_iterations: int = 5,
    ) -> None:
        self.vdd = vdd
        self.vin_cm = vin_cm
        self.cout = cout
        self.fixed_point_iterations = fixed_point_iterations
        lut = load_lookup_table(lookup_table_path)
        self.nmos = FastMosfet(lut, nmos_name, cache_dir="~/.cache/mosplot/fast_tables")
        self.pmos = FastMosfet(lut, pmos_name, cache_dir="~/.cache/mosplot/fast_tables")
        self._gdsid = Expression(["gds", "id"], function=lambda g, i: g / np.abs(i))
        self.device_map: dict[str, dict[str, Any]] = {
            "M1a": {
                "transistor": self.nmos,
                "model": nmos_name,
                "length": None,
                "gmid": None,
                "current": 0.0,
                "instances": 1,
            },
            "M1b": {
                "transistor": self.nmos,
                "model": nmos_name,
                "length": None,
                "gmid": None,
                "current": 0.0,
                "instances": 1,
            },
            "M2a": {
                "transistor": self.pmos,
                "model": pmos_name,
                "length": None,
                "gmid": None,
                "current": 0.0,
                "instances": 1,
            },
            "M2b": {
                "transistor": self.pmos,
                "model": pmos_name,
                "length": None,
                "gmid": None,
                "current": 0.0,
                "instances": 1,
            },
            "M3": {
                "transistor": self.nmos,
                "model": nmos_name,
                "length": None,
                "gmid": None,
                "current": 0.0,
                "instances": 1,
            },
            "Mvbn": {
                "transistor": self.nmos,
                "model": nmos_name,
                "length": None,
                "gmid": None,
                "current": 0.0,
                "instances": 1,
            },
        }
        self.device_dimensions: dict[str, dict[str, float]] = {}
        self.device_operating_points: dict[str, dict[str, float]] = {}
        self.passive_params: dict[str, float] = {}

    def evaluate_specs(self, **params: float) -> dict[str, float | None]:
        # --- DOF parameters ---
        M1a_ID = params["M1a_ID"]
        M1a_GMID = params["M1a_GMID"]
        M1a_L = params["M1a_L"]
        M2a_GMID = params["M2a_GMID"]
        M2a_L = params["M2a_L"]
        M3_GMID = params["M3_GMID"]
        M3_L = params["M3_L"]

        # --- Circuit conditions ---
        VDD = self.vdd
        VIN_CM = self.vin_cm
        COUT = self.cout

        # --- Lookup state ---
        M1a_VGS = M1a_VDSAT = M1a_gm = M1a_gdsid = 0.0
        M1a_cgs = M1a_cgd = M1a_cdd = M1a_JD = M1a_early = 0.0
        M1a_W = M1a_VDS = M1a_VSB = 0.0
        M1b_VGS = M1b_VDSAT = M1b_gm = M1b_gdsid = 0.0
        M1b_cgs = M1b_cgd = M1b_cdd = M1b_JD = M1b_early = 0.0
        M1b_W = M1b_L = M1b_ID = M1b_VDS = M1b_VSB = 0.0
        M2a_VGS = M2a_VDSAT = M2a_gm = M2a_gdsid = 0.0
        M2a_cgs = M2a_cgd = M2a_cdd = M2a_JD = M2a_early = 0.0
        M2a_W = M2a_ID = M2a_VDS = M2a_VSB = 0.0
        M2b_VGS = M2b_VDSAT = M2b_gm = M2b_gdsid = 0.0
        M2b_cgs = M2b_cgd = M2b_cdd = M2b_JD = M2b_early = 0.0
        M2b_W = M2b_L = M2b_ID = M2b_VDS = M2b_VSB = 0.0
        M3_VGS = M3_VDSAT = M3_gm = M3_gdsid = 0.0
        M3_cgs = M3_cgd = M3_cdd = M3_JD = M3_early = 0.0
        M3_W = M3_ID = M3_VDS = M3_VSB = 0.0
        Mvbn_VGS = Mvbn_VDSAT = Mvbn_gm = Mvbn_gdsid = 0.0
        Mvbn_cgs = Mvbn_cgd = Mvbn_cdd = Mvbn_JD = Mvbn_early = 0.0
        Mvbn_W = Mvbn_L = Mvbn_ID = Mvbn_VDS = Mvbn_VSB = 0.0

        # --- Initial guesses (loop-carried values) ---
        M1a_VGS = VDD / 4
        M2a_VGS = VDD / 4
        M3_VGS = VDD / 4
        Mvbn_VGS = VDD / 4
        M2a_ID = M1a_ID
        M3_ID = 2 * M1a_ID
        M1b_ID = 0.0
        M2b_ID = 0.0
        Mvbn_ID = 0.0

        # --- Widths frozen from first lookup ---
        M1a_W = 0.0
        M2a_W = 0.0
        M3_W = 0.0

        # --- Pre-seed VDS and VSB ---
        M1a_VDS = VDD / 3
        M1a_VSB = 0
        M1b_VDS = VDD / 3
        M1b_VSB = 0
        M2a_VDS = VDD / 3
        M2a_VSB = 0
        M3_VDS = VDD / 3
        M3_VSB = 0
        M2b_VDS = VDD / 3
        M2b_VSB = 0

        for _ in range(self.fixed_point_iterations):
            # --- Phase A: lookup all devices ---
            # M1a -- NMOS
            (
                M1a_VGS,
                M1a_VDSAT,
                M1a_gm,
                M1a_gdsid,
                M1a_cgs,
                M1a_cgd,
                M1a_cdd,
                M1a_JD,
                M1a_early,
            ) = [
                scalar(x)
                for x in self.nmos.interpolate(
                    length=M1a_L,
                    gmid=M1a_GMID,
                    vds=abs(M1a_VDS),
                    vbs=-abs(M1a_VSB),
                    expression=[
                        self.nmos.vgs_expression,
                        self.nmos.vdsat_expression,
                        self.nmos.gm_expression,
                        self._gdsid,
                        self.nmos.cgs_expression,
                        self.nmos.cgd_expression,
                        self.nmos.cdd_expression,
                        self.nmos.current_density_expression,
                        self.nmos.early_voltage_expression,
                    ],
                )
            ]
            M1a_VDSAT = abs(M1a_VDSAT)
            M1a_JD = abs(M1a_JD)
            if M1a_W == 0.0:
                M1a_W = M1a_ID / M1a_JD

            # M1b -- NMOS
            M1b_W = M1a_W
            M1b_VGS = M1a_VGS
            M1b_L = M1a_L
            M1b_ID = M1a_ID
            (
                M1b_VGS,
                M1b_VDSAT,
                M1b_gm,
                M1b_gdsid,
                M1b_cgs,
                M1b_cgd,
                M1b_cdd,
                M1b_JD,
                M1b_early,
            ) = [
                scalar(x)
                for x in self.nmos.interpolate(
                    length=M1b_L,
                    gmid=M1a_GMID,
                    vds=abs(M1b_VDS),
                    vbs=-abs(M1b_VSB),
                    expression=[
                        self.nmos.vgs_expression,
                        self.nmos.vdsat_expression,
                        self.nmos.gm_expression,
                        self._gdsid,
                        self.nmos.cgs_expression,
                        self.nmos.cgd_expression,
                        self.nmos.cdd_expression,
                        self.nmos.current_density_expression,
                        self.nmos.early_voltage_expression,
                    ],
                )
            ]
            M1b_VDSAT = abs(M1b_VDSAT)
            M1b_JD = abs(M1b_JD)

            # M2a -- PMOS
            M2a_ID = M1a_ID
            (
                M2a_VGS,
                M2a_VDSAT,
                M2a_gm,
                M2a_gdsid,
                M2a_cgs,
                M2a_cgd,
                M2a_cdd,
                M2a_JD,
                M2a_early,
            ) = [
                scalar(x)
                for x in self.pmos.interpolate(
                    length=M2a_L,
                    gmid=M2a_GMID,
                    vds=-abs(M2a_VDS),
                    vbs=-abs(M2a_VSB),
                    expression=[
                        self.pmos.vsg_expression,
                        self.pmos.vdsat_expression,
                        self.pmos.gm_expression,
                        self._gdsid,
                        self.pmos.cgs_expression,
                        self.pmos.cgd_expression,
                        self.pmos.cdd_expression,
                        self.pmos.current_density_expression,
                        self.pmos.early_voltage_expression,
                    ],
                )
            ]
            M2a_VDSAT = abs(M2a_VDSAT)
            M2a_JD = abs(M2a_JD)
            if M2a_W == 0.0:
                M2a_W = M2a_ID / M2a_JD

            # M3 -- NMOS
            M3_ID = M1a_ID + M1b_ID
            (M3_VGS, M3_VDSAT, M3_gm, M3_gdsid, M3_cgs, M3_cgd, M3_cdd, M3_JD, M3_early) = [
                scalar(x)
                for x in self.nmos.interpolate(
                    length=M3_L,
                    gmid=M3_GMID,
                    vds=abs(M3_VDS),
                    vbs=-abs(M3_VSB),
                    expression=[
                        self.nmos.vgs_expression,
                        self.nmos.vdsat_expression,
                        self.nmos.gm_expression,
                        self._gdsid,
                        self.nmos.cgs_expression,
                        self.nmos.cgd_expression,
                        self.nmos.cdd_expression,
                        self.nmos.current_density_expression,
                        self.nmos.early_voltage_expression,
                    ],
                )
            ]
            M3_VDSAT = abs(M3_VDSAT)
            M3_JD = abs(M3_JD)
            if M3_W == 0.0:
                M3_W = M3_ID / M3_JD

            # M2b -- PMOS
            M2b_W = M2a_W
            M2b_VGS = M2a_VGS
            M2b_L = M2a_L
            M2b_ID = M2a_ID
            (
                M2b_VGS,
                M2b_VDSAT,
                M2b_gm,
                M2b_gdsid,
                M2b_cgs,
                M2b_cgd,
                M2b_cdd,
                M2b_JD,
                M2b_early,
            ) = [
                scalar(x)
                for x in self.pmos.interpolate(
                    length=M2b_L,
                    gmid=M2a_GMID,
                    vds=-abs(M2b_VDS),
                    vbs=-abs(M2b_VSB),
                    expression=[
                        self.pmos.vsg_expression,
                        self.pmos.vdsat_expression,
                        self.pmos.gm_expression,
                        self._gdsid,
                        self.pmos.cgs_expression,
                        self.pmos.cgd_expression,
                        self.pmos.cdd_expression,
                        self.pmos.current_density_expression,
                        self.pmos.early_voltage_expression,
                    ],
                )
            ]
            M2b_VDSAT = abs(M2b_VDSAT)
            M2b_JD = abs(M2b_JD)

            # Mvbn -- NMOS
            Mvbn_W = M3_W
            Mvbn_VGS = M3_VGS
            Mvbn_L = M3_L
            Mvbn_gm = M3_gm
            Mvbn_gdsid = M3_gdsid
            Mvbn_cgs = M3_cgs
            Mvbn_cgd = M3_cgd
            Mvbn_cdd = M3_cdd
            Mvbn_JD = M3_JD
            Mvbn_VDSAT = M3_VDSAT
            Mvbn_ID = Mvbn_W * Mvbn_JD
            Mvbn_VDS = Mvbn_VGS

            # --- Phase B: update VDS for next iteration ---
            M1a_VDS = VDD - VIN_CM + M1a_VGS - M2a_VGS
            M1a_VSB = abs(-VIN_CM + M1a_VGS)
            M1b_VDS = M1a_VDS
            M1b_VSB = abs(-VIN_CM + M1a_VGS)
            M2a_VDS = M2a_VGS
            M2a_VSB = 0.0
            M3_VDS = VIN_CM - M1a_VGS
            M3_VSB = 0.0
            M2b_VDS = VDD - VIN_CM + M1a_VGS - M1b_VDS
            M2b_VSB = 0.0
            Mvbn_VSB = 0.0

        # --- Dimensions and operating points ---
        self.device_dimensions = {
            "M1a": {
                "Length": M1a_L,
                "Width": M1a_W,
                "Area": M1a_L * M1a_W,
                "Current": M1a_ID,
                "GMID": M1a_GMID,
            },
            "M1b": {
                "Length": M1b_L,
                "Width": M1b_W,
                "Area": M1b_L * M1b_W,
                "Current": M1b_ID,
                "GMID": M1a_GMID,
            },
            "M2a": {
                "Length": M2a_L,
                "Width": M2a_W,
                "Area": M2a_L * M2a_W,
                "Current": M2a_ID,
                "GMID": M2a_GMID,
            },
            "M2b": {
                "Length": M2b_L,
                "Width": M2b_W,
                "Area": M2b_L * M2b_W,
                "Current": M2b_ID,
                "GMID": M2a_GMID,
            },
            "M3": {
                "Length": M3_L,
                "Width": M3_W,
                "Area": M3_L * M3_W,
                "Current": M3_ID,
                "GMID": M3_GMID,
            },
            "Mvbn": {
                "Length": Mvbn_L,
                "Width": Mvbn_W,
                "Area": Mvbn_L * Mvbn_W,
                "Current": Mvbn_ID,
                "GMID": M3_GMID,
            },
        }
        self.device_operating_points = {
            "M1a": {"VGS": M1a_VGS, "VDS": M1a_VDS, "VSB": M1a_VSB, "ID": M1a_ID},
            "M1b": {"VGS": M1b_VGS, "VDS": M1b_VDS, "VSB": M1b_VSB, "ID": M1b_ID},
            "M2a": {"VGS": M2a_VGS, "VDS": M2a_VDS, "VSB": M2a_VSB, "ID": M2a_ID},
            "M2b": {"VGS": M2b_VGS, "VDS": M2b_VDS, "VSB": M2b_VSB, "ID": M2b_ID},
            "M3": {"VGS": M3_VGS, "VDS": M3_VDS, "VSB": M3_VSB, "ID": M3_ID},
            "Mvbn": {"VGS": Mvbn_VGS, "VDS": Mvbn_VDS, "VSB": Mvbn_VSB, "ID": Mvbn_ID},
        }

        # --- Small-signal AC analysis ---
        pmos_tw = self.pmos._width
        nmos_tw = self.nmos._width
        ss_params = {
            "M1a": {
                "gm": M1a_GMID * M1a_ID,
                "gmb": 0.0,
                "gds": M1a_gdsid * M1a_ID,
                "cgs": M1a_cgs * (M1a_W / nmos_tw),
                "cgd": M1a_cgd * (M1a_W / nmos_tw),
                "cdd": M1a_cdd * (M1a_W / nmos_tw),
            },
            "M1b": {
                "gm": M1a_GMID * M1b_ID,
                "gmb": 0.0,
                "gds": M1b_gdsid * M1b_ID,
                "cgs": M1b_cgs * (M1b_W / nmos_tw),
                "cgd": M1b_cgd * (M1b_W / nmos_tw),
                "cdd": M1b_cdd * (M1b_W / nmos_tw),
            },
            "M2a": {
                "gm": M2a_GMID * M2a_ID,
                "gmb": 0.0,
                "gds": M2a_gdsid * M2a_ID,
                "cgs": M2a_cgs * (M2a_W / pmos_tw),
                "cgd": M2a_cgd * (M2a_W / pmos_tw),
                "cdd": M2a_cdd * (M2a_W / pmos_tw),
            },
            "M2b": {
                "gm": M2a_GMID * M2b_ID,
                "gmb": 0.0,
                "gds": M2b_gdsid * M2b_ID,
                "cgs": M2b_cgs * (M2b_W / pmos_tw),
                "cgd": M2b_cgd * (M2b_W / pmos_tw),
                "cdd": M2b_cdd * (M2b_W / pmos_tw),
            },
            "M3": {
                "gm": M3_GMID * M3_ID,
                "gmb": 0.0,
                "gds": M3_gdsid * M3_ID,
                "cgs": M3_cgs * (M3_W / nmos_tw),
                "cgd": M3_cgd * (M3_W / nmos_tw),
                "cdd": M3_cdd * (M3_W / nmos_tw),
            },
        }
        self.passive_params = {"COUT": COUT}
        ss = build_ss_model(
            self.MOSFETS, self.PASSIVES, self.VSOURCES, ss_params, self.passive_params
        )
        ac = ss.solve(
            inp="VINP",
            inn="VINN",
            out="VOUT",
            compute_cmrr=True,
            compute_gbw=True,
            compute_phase_margin=True,
        )

        # --- Output variables ---
        Area = (
            M1a_L * M1a_W
            + M1b_L * M1b_W
            + M2a_L * M2a_W
            + M2b_L * M2b_W
            + M3_L * M3_W
            + Mvbn_L * Mvbn_W
        )
        Itotal = M1a_ID + M2b_ID
        VBN = M3_VGS
        VINP = VIN_CM
        VINN = VIN_CM
        VOUT_DC = VIN_CM - M1a_VGS + M1b_VDS
        VOUT_MAX = -M2b_VDSAT + VDD
        VOUT_MIN = max(-M1a_VGS + M1b_VDSAT + VIN_CM, M1b_VDSAT - M1b_VGS + VIN_CM)
        VIN_MAX = min(
            M1a_VGS - M1b_VDSAT + VOUT_DC,
            -M1a_VDSAT + M1a_VGS - M2a_VGS + VDD,
            -M1a_VDSAT + M1a_VGS - M2b_VGS + VDD,
        )
        VIN_MIN = M1a_VGS + M3_VDSAT
        Output_Swing = VOUT_MAX - VOUT_MIN

        return {
            "GBW": ac.ugf_hz,
            "AC Gain (dB)": 20.0 * np.log10(max(abs(ac.gain), 1e-300)),
            "PM": ac.phase_margin_deg,
            "DC CMR (dB)": 20.0 * np.log10(max(ac.cmrr, 1e-300)) if ac.cmrr else None,
            "Area": Area,
            "Itotal": Itotal,
            "VBN": VBN,
            "VOUT_DC": VOUT_DC,
            "VOUT_MAX": VOUT_MAX,
            "VOUT_MIN": VOUT_MIN,
            "VIN_MAX": VIN_MAX,
            "VIN_MIN": VIN_MIN,
            "Output_Swing": Output_Swing,
        }

    def compute_vsource_params(self, opt_params: dict[str, float]) -> dict[str, float]:
        ops = self.device_operating_points
        VDD = self.vdd
        VIN_CM = self.vin_cm
        COUT = self.cout
        VBN = ops.get("M3", {}).get("VGS", 0.0)
        return {"VBN": VBN}


def build_circuit(**kwargs) -> Circuit:
    return Circuit(**kwargs)


def _generate_simulation_netlist(optimizer: Optimizer, output_path: str) -> None:
    circuit = optimizer.circuit
    opt_params = optimizer.get_opt_params()
    specs = circuit.evaluate_specs(**opt_params)
    generator = SpectreGenerator(
        name="a010003",
        ports=["VINN", "VINP", "VOUT", "vdd", "vss"],
        ground="vss",
        context={"vcm": circuit.vin_cm, "vout_dc": specs.get("VOUT_DC", circuit.vin_cm)},
    )
    generator.generate(
        mosfets=circuit.NETLIST_MOSFETS,
        passives=circuit.NETLIST_PASSIVES,
        vsources=circuit.NETLIST_VSOURCES,
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
    vin_cm: float,
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
        vin_cm=vin_cm,
        cout=cout,
        fixed_point_iterations=fixed_point_iterations,
    )
    optimizer = Optimizer(circuit, parameters, target_specs)
    optimizer.optimize(maxiter=maxiter, seed=seed, n_restarts=n_restarts)
    report = DesignReport(circuit, optimizer)
    print(report.report())
    _generate_simulation_netlist(optimizer, output_module)
