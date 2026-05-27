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
        self.pmos = FastMosfet(lut, pmos_name, cache_dir="~/.cache/mosplot/fast_tables", rebuild_cache=False)
        self._gdsid = Expression(["gds", "id"], function=lambda g, i: g / np.abs(i))
        self._gmbsid = Expression(["gmbs", "id"], function=lambda g, i: g / np.abs(i))
        self.device_map: dict[str, str] = {"pmos": pmos_name}
        self.device_dimensions = {}
        self.device_operating_points = {}
        self.passive_params = {}

    def _interp(self, L, GMID, VDS, VSB):
        res = [scalar(x) for x in self.pmos.interpolate(
            length=L, gmid=GMID, vds=-abs(VDS), vbs=VSB,
            expression=[self.pmos.vgs_expression, self.pmos.vdsat_expression,
                        self._gdsid, self._gmbsid, self.pmos.current_density_expression],
        )]
        return {"vgs": abs(res[0]), "vdsat": abs(res[1]), "gdsid": res[2],
                "gmbsid": res[3], "jd": abs(res[4])}

    def evaluate_specs(self, **params):
        IREF = self.iref
        K = self.k
        GMID_M1 = params["GMID_M1"]
        L_M1 = params["L_M1"]
        GMID_M3 = params["GMID_M3"]
        L_M3 = params["L_M3"]

        VDD = self.vdd
        VOUT_DC = self.vout_dc
        CL = self.cout

        n02_drop = VDD / 4  # voltage drop from VDD to n02
        n01_drop = VDD / 4  # voltage drop from VDD to n01

        M1_W = M2_W = M3_W = M4_W = 0.0
        M1 = M2 = M3 = M4 = {}

        for _ in range(self.fixed_point_iterations):
            # M2 -- top diode (gate=drain=n02, source=vdd), ID=K*IREF
            r2 = self._interp(L_M1, GMID_M1, n02_drop, 0.0)  # VBS=0 (bulk=vdd=source)
            n02_drop = r2["vgs"]
            M2 = r2.copy()
            M2["vds"] = n02_drop
            M2["vsb"] = 0.0
            M2_ID = K * IREF
            if M2_W == 0.0:
                M2_W = M2_ID / r2["jd"]

            # M1 -- matches M2, ID=IREF. Find VDS giving VGS≈n02_drop.
            lo, hi = 0.02, VDD
            for _ in range(15):
                mid = (lo + hi) / 2
                vgs1 = self._interp(L_M1, GMID_M1, mid, 0.0)["vgs"]
                if vgs1 < n02_drop:
                    lo = mid
                else:
                    hi = mid
            n01_drop = (lo + hi) / 2
            r1 = self._interp(L_M1, GMID_M1, n01_drop, 0.0)
            M1 = r1.copy()
            M1["vds"] = n01_drop
            M1["vsb"] = 0.0
            if M1_W == 0.0:
                M1_W = IREF / r1["jd"]

            # M3 -- bottom diode (gate=drain=IREF, source=n01), ID=IREF
            # VBS = VDD - V(n01) = n01_drop (positive for PMOS, bulk above source)
            vds3 = r1["vgs"]
            for _ in range(6):
                r3 = self._interp(L_M3, GMID_M3, vds3, n01_drop)
                vds3 = r3["vgs"]
            M3 = r3.copy()
            M3["vds"] = vds3
            M3["vsb"] = -n01_drop  # signed VSB for dict
            if M3_W == 0.0:
                M3_W = IREF / r3["jd"]

            # M4 -- bottom cascode (gate=IREF, source=n02)
            vds4 = VDD - n02_drop - VOUT_DC  # |VDS4| magnitude
            M4 = self._interp(L_M3, GMID_M3, vds4, n02_drop)
            M4["vds"] = vds4
            M4["vsb"] = -n02_drop
            if M4_W == 0.0:
                M4_W = M2_ID / M4["jd"]

        M2_ID = K * IREF
        M3_ID = IREF
        M4_ID = M2_ID

        self.device_dimensions = {
            "M1": {"Length": L_M1, "Width": M1_W, "Area": L_M1 * M1_W, "Current": IREF, "GMID": GMID_M1},
            "M2": {"Length": L_M1, "Width": M2_W, "Area": L_M1 * M2_W, "Current": M2_ID, "GMID": GMID_M1},
            "M3": {"Length": L_M3, "Width": M3_W, "Area": L_M3 * M3_W, "Current": M3_ID, "GMID": GMID_M3},
            "M4": {"Length": L_M3, "Width": M4_W, "Area": L_M3 * M4_W, "Current": M4_ID, "GMID": GMID_M3},
        }
        self.device_operating_points = {k: v for k, v in [
            ("M1", {"VGS": M1["vgs"], "VDS": M1["vds"], "VSB": M1["vsb"], "ID": IREF, "VDSAT": M1["vdsat"]}),
            ("M2", {"VGS": M2["vgs"], "VDS": M2["vds"], "VSB": M2["vsb"], "ID": M2_ID, "VDSAT": M2["vdsat"]}),
            ("M3", {"VGS": M3["vgs"], "VDS": M3["vds"], "VSB": M3["vsb"], "ID": M3_ID, "VDSAT": M3["vdsat"]}),
            ("M4", {"VGS": M4["vgs"], "VDS": M4["vds"], "VSB": M4["vsb"], "ID": M4_ID, "VDSAT": M4["vdsat"]}),
        ]}
        self.passive_params = {"CL": CL}

        ss_params = {
            "M1": {"gm": GMID_M1 * IREF, "gmb": abs(M1["gmbsid"]) * IREF, "gds": M1["gdsid"] * IREF},
            "M2": {"gm": GMID_M1 * M2_ID, "gmb": abs(M2["gmbsid"]) * M2_ID, "gds": M2["gdsid"] * M2_ID},
            "M3": {"gm": GMID_M3 * M3_ID, "gmb": abs(M3["gmbsid"]) * M3_ID, "gds": M3["gdsid"] * M3_ID},
            "M4": {"gm": GMID_M3 * M4_ID, "gmb": abs(M4["gmbsid"]) * M4_ID, "gds": M4["gdsid"] * M4_ID},
        }
        ss = build_ss_model(mosfets=self.MOSFETS, passives=self.PASSIVES, vsources=self.VSOURCES,
                            ss_params=ss_params, passive_params={"CL": CL})
        Rout = ss.port("VOUT").resistance()

        Area = M1_W * L_M1 + M2_W * L_M1 + M3_W * L_M3 + M4_W * L_M3
        Itotal = IREF + M2_ID
        Vcompliance = n02_drop + M4["vdsat"]

        return {"Rout": Rout, "Vcompliance": Vcompliance, "Iout": M2_ID, "Area": Area, "Itotal": Itotal}

    def compute_vsource_params(self, opt_params):
        return {}


def build_circuit(**kwargs) -> Circuit:
    return Circuit(**kwargs)


def _generate_simulation_netlist(optimizer, output_path):
    circuit = optimizer.circuit
    spec = circuit.evaluate_specs(**optimizer.get_opt_params())
    gen = SpectreGenerator(name="Current_Mirror", ports=["IREF", "VOUT", "vdd", "vss"], ground="vss",
                           context={"vout_dc": float(circuit.vout_dc), "vdd": float(circuit.vdd),
                                    "iref": float(circuit.iref), "k": float(circuit.k),
                                    "iout": float(spec.get("Iout", 0)), "rout": float(spec.get("Rout", 0)),
                                    "vcompliance": float(spec.get("Vcompliance", 0))})
    gen.generate(mosfets=circuit.MOSFETS, passives=circuit.PASSIVES, vsources=circuit.VSOURCES,
                 device_map=circuit.device_map, dimensions=circuit.device_dimensions,
                 passive_params=circuit.passive_params,
                 vsource_params=circuit.compute_vsource_params(optimizer.get_opt_params()),
                 output_path=Path(output_path))


def run(*, lookup_table, pmos_name, vdd, cout, iref, k, parameters, target_specs, output_module,
        maxiter=200, seed=1, n_restarts=1, fixed_point_iterations=5):
    circuit = Circuit(lookup_table, pmos_name, vdd, cout, iref, k, fixed_point_iterations)
    opt = Optimizer(circuit, parameters, target_specs)
    opt.optimize(maxiter=maxiter, seed=seed, n_restarts=n_restarts)
    print(DesignReport(circuit, opt).report())
    _generate_simulation_netlist(opt, output_module)
