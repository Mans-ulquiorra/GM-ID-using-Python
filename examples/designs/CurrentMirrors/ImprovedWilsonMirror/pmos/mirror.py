"""gm/ID optimizer for 4-T Improved Wilson PMOS Current Mirror.

M1: top mirror        (d=n01, g=n02, s=vdd)   -- matched to M2
M2: top diode         (d=n02, g=n02, s=vdd)   -- sets n02 = VDD - |VGS2|
M3: bottom diode      (d=IREF,g=IREF,s=n01)    -- reference input
M4: bottom cascode    (d=VOUT,g=IREF,s=n02)    -- output
"""

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
    """Improved 4-transistor Wilson PMOS current mirror.

    Top diode pair with bottom cascode -- feedback-boosted Rout
    without external bias. Highest Rout among the mirrors.
    """

    MOSFETS: ClassVar[list[Instance]] = [
        Instance("M1", "pmos", d="n01",  g="n02",  s="vdd", b="vdd"),
        Instance("M2", "pmos", d="n02",  g="n02",  s="vdd", b="vdd"),
        Instance("M3", "pmos", d="IREF", g="IREF", s="n01", b="vdd"),
        Instance("M4", "pmos", d="VOUT", g="IREF", s="n02", b="vdd"),
    ]

    PASSIVES: ClassVar[list[Passive]] = [
        Passive("CL", "cap", a="VOUT", b="gnd", external=True),
    ]

    VSOURCES: ClassVar[list[VSource]] = [
        VSource("VDD", p="vdd", n="gnd", supply=True),
    ]

    def __init__(self, lookup_table_path, pmos_name, vdd, cout, iref, k,
                 fixed_point_iterations=5):
        self.vdd = vdd
        self.cout = cout
        self.iref = iref
        self.k = k
        self.vout_dc = vdd / 2
        self.fixed_point_iterations = fixed_point_iterations
        lut = load_lookup_table(lookup_table_path)
        self.pmos = FastMosfet(lut, pmos_name,
                               cache_dir="~/.cache/mosplot/fast_tables",
                               rebuild_cache=False)
        self._gdsid = Expression(["gds", "id"], function=lambda g, i: g / np.abs(i))
        self._gmbsid = Expression(["gmbs", "id"], function=lambda g, i: g / np.abs(i))
        self.device_map: dict[str, str] = {"pmos": pmos_name}
        self.device_dimensions = {}
        self.device_operating_points = {}
        self.passive_params = {}

    def _lookup(self, L, GMID, VDS, VSB):
        r = [scalar(x) for x in self.pmos.interpolate(
            length=L, gmid=GMID, vds=-abs(VDS), vbs=VSB,
            expression=[self.pmos.vsg_expression,
                        self.pmos.vdsat_expression,
                        self._gdsid, self._gmbsid,
                        self.pmos.current_density_expression],
        )]
        return abs(r[0]), abs(r[1]), r[2], r[3], abs(r[4])

    def evaluate_specs(self, **params: float) -> dict[str, float | None]:
        IREF = self.iref
        K = self.k
        GMID_M1 = params["GMID_M1"]
        L_M1 = params["L_M1"]
        GMID_M3 = params["GMID_M3"]
        L_M3 = params["L_M3"]

        VDD = self.vdd
        VOUT_DC = self.vout_dc

        # --- Loop-carried state ---
        M1_VGS = M1_VDSAT = M1_gdsid = M1_gmbsid = M1_JD = 0.0
        M1_W = M1_VDS = M1_VSB = 0.0
        M2_VGS = M2_VDSAT = M2_gdsid = M2_gmbsid = M2_JD = 0.0
        M2_W = M2_ID = M2_VDS = M2_VSB = 0.0
        M3_VGS = M3_VDSAT = M3_gdsid = M3_gmbsid = M3_JD = 0.0
        M3_W = M3_ID = M3_VDS = M3_VSB = 0.0
        M4_VGS = M4_VDSAT = M4_gdsid = M4_gmbsid = M4_JD = 0.0
        M4_W = M4_ID = M4_VDS = M4_VSB = 0.0

        # --- Initial guesses ---
        M2_VGS = VDD / 4
        M2_VDS = M2_VGS
        M1_VDS = VDD / 4
        M3_VGS = VDD / 4
        M3_VDS = M3_VGS

        # --- Fixed currents ---
        M2_ID = K * IREF
        M3_ID = IREF
        M4_ID = M2_ID

        for _ in range(self.fixed_point_iterations):
            # --- Phase A: lookup all devices ---
            M2_VGS, M2_VDSAT, M2_gdsid, M2_gmbsid, M2_JD = self._lookup(
                L_M1, GMID_M1, M2_VDS, 0.0)
            if M2_W == 0.0:
                M2_W = M2_ID / M2_JD

            M4_VGS, M4_VDSAT, M4_gdsid, M4_gmbsid, M4_JD = self._lookup(
                L_M3, GMID_M3, VDD - M2_VGS - VOUT_DC, M2_VGS)
            if M4_W == 0.0:
                M4_W = M4_ID / M4_JD

            M3_VGS, M3_VDSAT, M3_gdsid, M3_gmbsid, M3_JD = self._lookup(
                L_M3, GMID_M3, M3_VDS, M1_VDS)
            if M3_W == 0.0:
                M3_W = M3_ID / M3_JD

            M1_VGS, M1_VDSAT, M1_gdsid, M1_gmbsid, M1_JD = self._lookup(
                L_M1, GMID_M1, M1_VDS, 0.0)
            if M1_W == 0.0:
                M1_W = IREF / M1_JD

            # --- Phase B: update VDS for next iteration ---
            M2_VDS = M2_VGS                       # diode
            M3_VDS = M3_VGS                       # diode
            M4_VDS = VDD - M2_VGS - VOUT_DC       # |VDS4| from VDD down to VOUT
            M1_VDS = M2_VGS - M3_VGS + M4_VGS     # moseq: n01_drop = n02_drop - VGS3 + VGS4

            # --- VSB ---
            M2_VSB = 0.0
            M1_VSB = 0.0
            M3_VSB = M1_VDS
            M4_VSB = M2_VGS

        # --- Dimensions and operating points ---
        self.device_dimensions = {
            "M1": {"Length": L_M1, "Width": M1_W, "Area": L_M1 * M1_W,
                   "Current": IREF, "GMID": GMID_M1},
            "M2": {"Length": L_M1, "Width": M2_W, "Area": L_M1 * M2_W,
                   "Current": M2_ID, "GMID": GMID_M1},
            "M3": {"Length": L_M3, "Width": M3_W, "Area": L_M3 * M3_W,
                   "Current": M3_ID, "GMID": GMID_M3},
            "M4": {"Length": L_M3, "Width": M4_W, "Area": L_M3 * M4_W,
                   "Current": M4_ID, "GMID": GMID_M3},
        }
        self.device_operating_points = {
            "M1": {"VGS": M1_VGS, "VDS": M1_VDS, "VSB": M1_VSB,
                   "ID": IREF, "VDSAT": M1_VDSAT},
            "M2": {"VGS": M2_VGS, "VDS": M2_VDS, "VSB": M2_VSB,
                   "ID": M2_ID, "VDSAT": M2_VDSAT},
            "M3": {"VGS": M3_VGS, "VDS": M3_VDS, "VSB": M3_VSB,
                   "ID": M3_ID, "VDSAT": M3_VDSAT},
            "M4": {"VGS": M4_VGS, "VDS": M4_VDS, "VSB": M4_VSB,
                   "ID": M4_ID, "VDSAT": M4_VDSAT},
        }
        self.passive_params = {"CL": self.cout}

        # --- Small-signal model ---
        ss_params = {
            "M1": {"gm": GMID_M1 * IREF, "gmb": M1_gmbsid * IREF,
                   "gds": M1_gdsid * IREF},
            "M2": {"gm": GMID_M1 * M2_ID, "gmb": M2_gmbsid * M2_ID,
                   "gds": M2_gdsid * M2_ID},
            "M3": {"gm": GMID_M3 * M3_ID, "gmb": M3_gmbsid * M3_ID,
                   "gds": M3_gdsid * M3_ID},
            "M4": {"gm": GMID_M3 * M4_ID, "gmb": M4_gmbsid * M4_ID,
                   "gds": M4_gdsid * M4_ID},
        }
        ss = build_ss_model(mosfets=self.MOSFETS, passives=self.PASSIVES,
                            vsources=self.VSOURCES, ss_params=ss_params,
                            passive_params={"CL": self.cout})
        Rout = ss.port("VOUT").resistance()

        # --- Derived specs ---
        Area = M1_W * L_M1 + M2_W * L_M1 + M3_W * L_M3 + M4_W * L_M3
        Itotal = IREF + M2_ID
        Vcompliance = M2_VGS + M4_VDSAT

        return {"Rout": Rout, "Vcompliance": Vcompliance, "Iout": M2_ID,
                "Area": Area, "Itotal": Itotal}

    def compute_vsource_params(self, opt_params):
        return {}




def _generate_simulation_netlist(optimizer, output_path):
    circuit = optimizer.circuits[0]
    specs = optimizer.corner_results[0].specs
    gen = SpectreGenerator(
        name="Current_Mirror", ports=["IREF", "VOUT", "vdd", "vss"],
        ground="vss",
        context={"vout_dc": float(circuit.vout_dc), "vdd": float(circuit.vdd),
                 "iref": float(circuit.iref), "k": float(circuit.k),
                 "iout": float(spec.get("Iout", 0)),
                 "rout": float(spec.get("Rout", 0)),
                 "vcompliance": float(spec.get("Vcompliance", 0))})
    gen.generate(mosfets=circuit.MOSFETS, passives=circuit.PASSIVES,
                 vsources=circuit.VSOURCES, device_map=circuit.device_map,
                 dimensions=circuit.device_dimensions,
                 passive_params=circuit.passive_params,
                 vsource_params=circuit.compute_vsource_params(
                     optimizer.get_opt_params()),
                 output_path=Path(output_path))


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
