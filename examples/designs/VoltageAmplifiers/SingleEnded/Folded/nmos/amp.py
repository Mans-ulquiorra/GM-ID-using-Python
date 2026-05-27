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

__all__ = ['run', 'OptimizationParameter', 'Spec']


def scalar(v: Any) -> float:
    return float(np.asarray(v).reshape(-1)[0])


class Circuit:
    """Folded-cascode single-ended OTA.

    NMOS diff pair with PMOS cascode fold.
    Single-stage with cascode Rout boost, wider swing than telescopic.
    """

    MOSFETS: ClassVar[list[Instance]] = [
        Instance("M1a", "nmos", d="n01", g="VINP", s="n02", b="gnd"),
        Instance("M1b", "nmos", d="n03", g="VINN", s="n02", b="gnd"),
        Instance("M2a", "pmos", d="n01", g="vbp", s="vdd", b="vdd"),
        Instance("M2b", "pmos", d="n03", g="vbp", s="vdd", b="vdd"),
        Instance("M3a", "pmos", d="n04", g="vcascp", s="n01", b="vdd"),
        Instance("M3b", "pmos", d="VOUT", g="vcascp", s="n03", b="vdd"),
        Instance("M4a", "nmos", d="n04", g="vcascn", s="n05", b="gnd"),
        Instance("M4b", "nmos", d="VOUT", g="vcascn", s="n06", b="gnd"),
        Instance("M5a", "nmos", d="n05", g="n04", s="gnd", b="gnd"),
        Instance("M5b", "nmos", d="n06", g="n04", s="gnd", b="gnd"),
        Instance("M6", "nmos", d="n02", g="vbn", s="gnd", b="gnd"),
    ]

    PASSIVES: ClassVar[list[Passive]] = [
        Passive("COUT", "cap", a="VOUT", b="gnd", external=True),
    ]

    VSOURCES: ClassVar[list[VSource]] = [
        VSource("VDD", p="vdd", n="gnd", supply=True),
        VSource("VCASCP", p="vcascp", n="gnd"),
        VSource("VBN", p="vbn", n="gnd"),
        VSource("VBP", p="vbp", n="gnd"),
        VSource("VCASCN", p="vcascn", n="gnd"),
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
        lut          = load_lookup_table(lookup_table_path)
        self.nmos    = FastMosfet(lut, nmos_name, cache_dir='~/.cache/mosplot/fast_tables')
        self.pmos    = FastMosfet(lut, pmos_name, cache_dir='~/.cache/mosplot/fast_tables')
        self._gdsid  = Expression(['gds', 'id'], function=lambda g, i: g / np.abs(i))
        self.device_map: dict[str, str] = {"nmos": nmos_name, "pmos": pmos_name}
        self.device_dimensions:       dict[str, dict[str, float]] = {}
        self.device_operating_points: dict[str, dict[str, float]] = {}
        self.passive_params:          dict[str, float] = {}

    def evaluate_specs(self, **params: float) -> dict[str, float | None]:
        # --- DOF parameters ---
        M5a_ID_over_M1a_ID = params['M5a_ID_over_M1a_ID']
        M5a_VDSAT_MARGIN = params['M5a_VDSAT_MARGIN']
        M2a_VDSAT_MARGIN = params['M2a_VDSAT_MARGIN']
        M1a_ID = params['M1a_ID']
        M1a_GMID = params['M1a_GMID']
        M1a_L = params['M1a_L']
        M2a_GMID = params['M2a_GMID']
        M2a_L = params['M2a_L']
        M3a_GMID = params['M3a_GMID']
        M3a_L = params['M3a_L']
        M4a_GMID = params['M4a_GMID']
        M4a_L = params['M4a_L']
        M5a_GMID = params['M5a_GMID']
        M5a_L = params['M5a_L']
        M6_GMID = params['M6_GMID']
        M6_L = params['M6_L']

        # --- Circuit conditions ---
        VDD = self.vdd
        VIN_CM = self.vin_cm
        COUT = self.cout

        # --- Lookup state ---
        M1a_VGS = M1a_VDSAT = M1a_gdsid = 0.0
        M1a_cgs = M1a_cgd = M1a_cdd = M1a_JD = 0.0
        M1a_W = M1a_VDS = M1a_VSB = 0.0
        M1b_VGS = M1b_VDSAT = M1b_gdsid = 0.0
        M1b_cgs = M1b_cgd = M1b_cdd = 0.0
        M1b_W = M1b_L = M1b_ID = M1b_VDS = M1b_VSB = 0.0
        M2a_VGS = M2a_VDSAT = M2a_gdsid = 0.0
        M2a_cgs = M2a_cgd = M2a_cdd = M2a_JD = 0.0
        M2a_W = M2a_ID = M2a_VDS = M2a_VSB = 0.0
        M2b_VGS = M2b_gdsid = 0.0
        M2b_cgs = M2b_cgd = M2b_cdd = 0.0
        M2b_W = M2b_L = M2b_ID = M2b_VDS = M2b_VSB = 0.0
        M3a_VGS = M3a_gdsid = 0.0
        M3a_cgs = M3a_cgd = M3a_cdd = M3a_JD = 0.0
        M3a_W = M3a_ID = M3a_VDS = M3a_VSB = 0.0
        M3b_VGS = M3b_VDSAT = M3b_gdsid = 0.0
        M3b_cgs = M3b_cgd = M3b_cdd = 0.0
        M3b_W = M3b_L = M3b_ID = M3b_VDS = M3b_VSB = 0.0
        M4a_VGS = M4a_gdsid = 0.0
        M4a_cgs = M4a_cgd = M4a_cdd = M4a_JD = 0.0
        M4a_W = M4a_ID = M4a_VDS = M4a_VSB = 0.0
        M4b_VGS = M4b_VDSAT = M4b_gdsid = 0.0
        M4b_cgs = M4b_cgd = M4b_cdd = 0.0
        M4b_W = M4b_L = M4b_ID = M4b_VDS = M4b_VSB = 0.0
        M5a_VGS = M5a_VDSAT = M5a_gdsid = 0.0
        M5a_cgs = M5a_cgd = M5a_cdd = M5a_JD = 0.0
        M5a_W = M5a_ID = M5a_VDS = M5a_VSB = 0.0
        M5b_VGS = M5b_gdsid = 0.0
        M5b_cgs = M5b_cgd = M5b_cdd = 0.0
        M5b_W = M5b_L = M5b_ID = M5b_VDS = M5b_VSB = 0.0
        M6_VGS = M6_VDSAT = M6_gdsid = 0.0
        M6_cgs = M6_cgd = M6_cdd = M6_JD = 0.0
        M6_W = M6_ID = M6_VDS = M6_VSB = 0.0
        Mvbp_VGS = 0.0
        Mvbp_JD = 0.0
        Mvbp_W = Mvbp_L = Mvbp_ID = Mvbp_VDS = Mvbp_VSB = 0.0
        Mvbn_VGS = 0.0
        Mvbn_JD = 0.0
        Mvbn_W = Mvbn_L = Mvbn_ID = Mvbn_VDS = Mvbn_VSB = 0.0

        # --- Initial guesses (loop-carried values) ---
        M1a_VGS = VDD / 4
        M2a_VGS = VDD / 4
        M3a_VGS = VDD / 4
        M3b_VGS = VDD / 4
        M4a_VGS = VDD / 4
        M4b_VGS = VDD / 4
        M5a_VGS = VDD / 4
        M6_VGS = VDD / 4
        Mvbn_VGS = VDD / 4
        Mvbp_VGS = VDD / 4
        M2a_ID = M1a_ID*(M5a_ID_over_M1a_ID + 1)
        M3a_ID = M5a_ID_over_M1a_ID*M1a_ID
        M4a_ID = M5a_ID_over_M1a_ID*M1a_ID
        M5a_ID = M5a_ID_over_M1a_ID*M1a_ID
        M6_ID = 2*M1a_ID
        M1b_ID = 0.0
        M2b_ID = 0.0
        M3b_ID = 0.0
        M4b_ID = 0.0
        M5b_ID = 0.0
        Mvbp_ID = 0.0
        Mvbn_ID = 0.0

        # --- Widths frozen from first lookup ---
        M1a_W = 0.0
        M2a_W = 0.0
        M3a_W = 0.0
        M4a_W = 0.0
        M5a_W = 0.0
        M6_W = 0.0

        # --- Pre-seed VDS and VSB ---
        M1a_VDS = VDD/3
        M1a_VSB = 0
        M1b_VDS = VDD/3
        M1b_VSB = 0
        M2a_VDS = VDD/4
        M2a_VSB = 0
        M3a_VDS = VDD/4
        M3a_VSB = 0
        M4a_VDS = VDD/4
        M4a_VSB = 0
        M5a_VDS = VDD/4
        M5a_VSB = 0
        M6_VDS = VDD/3
        M6_VSB = 0
        M2b_VDS = VDD/4
        M2b_VSB = 0
        M3b_VDS = VDD/4
        M3b_VSB = 0
        M4b_VDS = VDD/4
        M4b_VSB = 0
        M5b_VDS = VDD/4
        M5b_VSB = 0

        for _ in range(self.fixed_point_iterations):
            # --- Phase A: lookup all devices ---
            # M1a -- NMOS
            (M1a_VGS, M1a_VDSAT, M1a_gdsid, M1a_cgs, M1a_cgd, M1a_cdd, M1a_JD) = [
                scalar(x) for x in self.nmos.interpolate(
                    length=M1a_L, gmid=M1a_GMID,
                    vds=abs(M1a_VDS), vbs=-abs(M1a_VSB),
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
            M1a_VDSAT = abs(M1a_VDSAT)
            M1a_JD    = abs(M1a_JD)
            if M1a_W == 0.0:
                M1a_W = M1a_ID / M1a_JD
            
            # M1b -- NMOS
            M1b_W = M1a_W
            M1b_VGS = M1a_VGS
            M1b_L = M1a_L
            M1b_ID = M1a_ID
            (M1b_VGS, M1b_VDSAT, M1b_gdsid, M1b_cgs, M1b_cgd, M1b_cdd) = [
                scalar(x) for x in self.nmos.interpolate(
                    length=M1b_L, gmid=M1a_GMID,
                    vds=abs(M1b_VDS), vbs=-abs(M1b_VSB),
                    expression=[
                    self.nmos.vgs_expression,
                    self.nmos.vdsat_expression,
                    self._gdsid,
                    self.nmos.cgs_expression,
                    self.nmos.cgd_expression,
                    self.nmos.cdd_expression,
                    ],
                )
            ]
            M1b_VDSAT = abs(M1b_VDSAT)
            
            # M2a -- PMOS
            M2a_ID = M1a_ID*(M5a_ID_over_M1a_ID + 1)
            (M2a_VGS, M2a_VDSAT, M2a_gdsid, M2a_cgs, M2a_cgd, M2a_cdd, M2a_JD) = [
                scalar(x) for x in self.pmos.interpolate(
                    length=M2a_L, gmid=M2a_GMID,
                    vds=-abs(M2a_VDS), vbs=-abs(M2a_VSB),
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
            M2a_VDSAT = abs(M2a_VDSAT)
            M2a_JD    = abs(M2a_JD)
            if M2a_W == 0.0:
                M2a_W = M2a_ID / M2a_JD
            
            # M3a -- PMOS
            M3a_ID = M5a_ID_over_M1a_ID*M1a_ID
            (M3a_VGS, M3a_gdsid, M3a_cgs, M3a_cgd, M3a_cdd, M3a_JD) = [
                scalar(x) for x in self.pmos.interpolate(
                    length=M3a_L, gmid=M3a_GMID,
                    vds=-abs(M3a_VDS), vbs=-abs(M3a_VSB),
                    expression=[
                    self.pmos.vsg_expression,
                    self._gdsid,
                    self.pmos.cgs_expression,
                    self.pmos.cgd_expression,
                    self.pmos.cdd_expression,
                    self.pmos.current_density_expression,
                    ],
                )
            ]
            M3a_JD    = abs(M3a_JD)
            if M3a_W == 0.0:
                M3a_W = M3a_ID / M3a_JD
            
            # M4a -- NMOS
            M4a_ID = M5a_ID_over_M1a_ID*M1a_ID
            (M4a_VGS, M4a_gdsid, M4a_cgs, M4a_cgd, M4a_cdd, M4a_JD) = [
                scalar(x) for x in self.nmos.interpolate(
                    length=M4a_L, gmid=M4a_GMID,
                    vds=abs(M4a_VDS), vbs=-abs(M4a_VSB),
                    expression=[
                    self.nmos.vgs_expression,
                    self._gdsid,
                    self.nmos.cgs_expression,
                    self.nmos.cgd_expression,
                    self.nmos.cdd_expression,
                    self.nmos.current_density_expression,
                    ],
                )
            ]
            M4a_JD    = abs(M4a_JD)
            if M4a_W == 0.0:
                M4a_W = M4a_ID / M4a_JD
            
            # M5a -- NMOS
            M5a_ID = M5a_ID_over_M1a_ID*M1a_ID
            (M5a_VGS, M5a_VDSAT, M5a_gdsid, M5a_cgs, M5a_cgd, M5a_cdd, M5a_JD) = [
                scalar(x) for x in self.nmos.interpolate(
                    length=M5a_L, gmid=M5a_GMID,
                    vds=abs(M5a_VDS), vbs=-abs(M5a_VSB),
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
            M5a_VDSAT = abs(M5a_VDSAT)
            M5a_JD    = abs(M5a_JD)
            if M5a_W == 0.0:
                M5a_W = M5a_ID / M5a_JD
            
            # M6 -- NMOS
            M6_ID = M1a_ID + M1b_ID
            (M6_VGS, M6_VDSAT, M6_gdsid, M6_cgs, M6_cgd, M6_cdd, M6_JD) = [
                scalar(x) for x in self.nmos.interpolate(
                    length=M6_L, gmid=M6_GMID,
                    vds=abs(M6_VDS), vbs=-abs(M6_VSB),
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
            M6_VDSAT = abs(M6_VDSAT)
            M6_JD    = abs(M6_JD)
            if M6_W == 0.0:
                M6_W = M6_ID / M6_JD
            
            # M2b -- PMOS
            M2b_W = M2a_W
            M2b_VGS = M2a_VGS
            M2b_L = M2a_L
            M2b_ID = M2a_ID
            (M2b_VGS, M2b_gdsid, M2b_cgs, M2b_cgd, M2b_cdd) = [
                scalar(x) for x in self.pmos.interpolate(
                    length=M2b_L, gmid=M2a_GMID,
                    vds=-abs(M2b_VDS), vbs=-abs(M2b_VSB),
                    expression=[
                    self.pmos.vsg_expression,
                    self._gdsid,
                    self.pmos.cgs_expression,
                    self.pmos.cgd_expression,
                    self.pmos.cdd_expression,
                    ],
                )
            ]
            
            # M3b -- PMOS
            M3b_W = M3a_W
            M3b_L = M3a_L
            M3b_ID = M3a_ID
            (M3b_VGS, M3b_VDSAT, M3b_gdsid, M3b_cgs, M3b_cgd, M3b_cdd) = [
                scalar(x) for x in self.pmos.interpolate(
                    length=M3b_L, gmid=M3a_GMID,
                    vds=-abs(M3b_VDS), vbs=-abs(M3b_VSB),
                    expression=[
                    self.pmos.vsg_expression,
                    self.pmos.vdsat_expression,
                    self._gdsid,
                    self.pmos.cgs_expression,
                    self.pmos.cgd_expression,
                    self.pmos.cdd_expression,
                    ],
                )
            ]
            M3b_VDSAT = abs(M3b_VDSAT)
            
            # M4b -- NMOS
            M4b_W = M4a_W
            M4b_L = M4a_L
            M4b_ID = M4a_ID
            (M4b_VGS, M4b_VDSAT, M4b_gdsid, M4b_cgs, M4b_cgd, M4b_cdd) = [
                scalar(x) for x in self.nmos.interpolate(
                    length=M4b_L, gmid=M4a_GMID,
                    vds=abs(M4b_VDS), vbs=-abs(M4b_VSB),
                    expression=[
                    self.nmos.vgs_expression,
                    self.nmos.vdsat_expression,
                    self._gdsid,
                    self.nmos.cgs_expression,
                    self.nmos.cgd_expression,
                    self.nmos.cdd_expression,
                    ],
                )
            ]
            M4b_VDSAT = abs(M4b_VDSAT)
            
            # M5b -- NMOS
            M5b_W = M5a_W
            M5b_VGS = M5a_VGS
            M5b_L = M5a_L
            M5b_ID = M5a_ID
            (M5b_VGS, M5b_gdsid, M5b_cgs, M5b_cgd, M5b_cdd) = [
                scalar(x) for x in self.nmos.interpolate(
                    length=M5b_L, gmid=M5a_GMID,
                    vds=abs(M5b_VDS), vbs=-abs(M5b_VSB),
                    expression=[
                    self.nmos.vgs_expression,
                    self._gdsid,
                    self.nmos.cgs_expression,
                    self.nmos.cgd_expression,
                    self.nmos.cdd_expression,
                    ],
                )
            ]
            
            # Mvbn -- NMOS
            Mvbn_W = M6_W
            Mvbn_VGS = M6_VGS
            Mvbn_L = M6_L
            Mvbn_VGS = M6_VGS
            Mvbn_JD = M6_JD
            Mvbn_ID = Mvbn_W * Mvbn_JD
            Mvbn_VDS = Mvbn_VGS
            
            # Mvbp -- PMOS
            Mvbp_W = M2a_W
            Mvbp_VGS = M2a_VGS
            Mvbp_L = M2a_L
            Mvbp_VGS = M2a_VGS
            Mvbp_JD = M2a_JD
            Mvbp_ID = Mvbp_W * Mvbp_JD
            Mvbp_VDS = Mvbp_VGS
            
            # --- Phase B: update VDS for next iteration ---
            M1a_VDS = VDD - VIN_CM + M1a_VGS - M2a_VDS
            M1a_VSB = abs(-VIN_CM + M1a_VGS)
            M1b_VDS = VDD - VIN_CM + M1a_VGS - M2a_VDS - M3a_VGS + M3b_VGS
            M1b_VSB = abs(-VIN_CM + M1a_VGS)
            M2a_VDS = M2a_VDSAT + M2a_VDSAT_MARGIN
            M2a_VSB = 0.0
            M3a_VDS = VDD - M2a_VDS - M5a_VGS
            M3a_VSB = abs(M2a_VDS)
            M4a_VDS = -M5a_VDS + M5a_VGS
            M4a_VSB = abs(M5a_VDS)
            M5a_VDS = M5a_VDSAT + M5a_VDSAT_MARGIN
            M5a_VSB = 0.0
            M6_VDS = VIN_CM - M1a_VGS
            M6_VSB = 0.0
            M2b_VDS = M2a_VDS + M3a_VGS - M3b_VGS
            M2b_VSB = 0.0
            M3b_VDS = M3a_VDS
            M3b_VSB = abs(M2a_VDS + M3a_VGS - M3b_VGS)
            M4b_VDS = VDD - M2a_VDS - M3a_VGS - M3b_VDS + M3b_VGS - M4a_VGS + M4b_VGS - M5a_VDS
            M4b_VSB = abs(M4a_VGS - M4b_VGS + M5a_VDS)
            M5b_VDS = M4a_VGS - M4b_VGS + M5a_VDS
            M5b_VSB = 0.0
            Mvbn_VSB = 0.0
            Mvbp_VSB = 0.0

        # --- Dimensions and operating points ---
        self.device_dimensions = {
            "M1a": {"Length": M1a_L, "Width": M1a_W, "Area": M1a_L * M1a_W, "Current": M1a_ID, "GMID": M1a_GMID},
            "M1b": {"Length": M1b_L, "Width": M1b_W, "Area": M1b_L * M1b_W, "Current": M1b_ID, "GMID": M1a_GMID},
            "M2a": {"Length": M2a_L, "Width": M2a_W, "Area": M2a_L * M2a_W, "Current": M2a_ID, "GMID": M2a_GMID},
            "M2b": {"Length": M2b_L, "Width": M2b_W, "Area": M2b_L * M2b_W, "Current": M2b_ID, "GMID": M2a_GMID},
            "M3a": {"Length": M3a_L, "Width": M3a_W, "Area": M3a_L * M3a_W, "Current": M3a_ID, "GMID": M3a_GMID},
            "M3b": {"Length": M3b_L, "Width": M3b_W, "Area": M3b_L * M3b_W, "Current": M3b_ID, "GMID": M3a_GMID},
            "M4a": {"Length": M4a_L, "Width": M4a_W, "Area": M4a_L * M4a_W, "Current": M4a_ID, "GMID": M4a_GMID},
            "M4b": {"Length": M4b_L, "Width": M4b_W, "Area": M4b_L * M4b_W, "Current": M4b_ID, "GMID": M4a_GMID},
            "M5a": {"Length": M5a_L, "Width": M5a_W, "Area": M5a_L * M5a_W, "Current": M5a_ID, "GMID": M5a_GMID},
            "M5b": {"Length": M5b_L, "Width": M5b_W, "Area": M5b_L * M5b_W, "Current": M5b_ID, "GMID": M5a_GMID},
            "M6": {"Length": M6_L, "Width": M6_W, "Area": M6_L * M6_W, "Current": M6_ID, "GMID": M6_GMID},
            "Mvbp": {"Length": Mvbp_L, "Width": Mvbp_W, "Area": Mvbp_L * Mvbp_W, "Current": Mvbp_ID, "GMID": M2a_GMID},
            "Mvbn": {"Length": Mvbn_L, "Width": Mvbn_W, "Area": Mvbn_L * Mvbn_W, "Current": Mvbn_ID, "GMID": M6_GMID},
        }
        self.device_operating_points = {
            "M1a": {"VGS": M1a_VGS, "VDS": M1a_VDS, "VSB": M1a_VSB, "ID": M1a_ID},
            "M1b": {"VGS": M1b_VGS, "VDS": M1b_VDS, "VSB": M1b_VSB, "ID": M1b_ID},
            "M2a": {"VGS": M2a_VGS, "VDS": M2a_VDS, "VSB": M2a_VSB, "ID": M2a_ID},
            "M2b": {"VGS": M2b_VGS, "VDS": M2b_VDS, "VSB": M2b_VSB, "ID": M2b_ID},
            "M3a": {"VGS": M3a_VGS, "VDS": M3a_VDS, "VSB": M3a_VSB, "ID": M3a_ID},
            "M3b": {"VGS": M3b_VGS, "VDS": M3b_VDS, "VSB": M3b_VSB, "ID": M3b_ID},
            "M4a": {"VGS": M4a_VGS, "VDS": M4a_VDS, "VSB": M4a_VSB, "ID": M4a_ID},
            "M4b": {"VGS": M4b_VGS, "VDS": M4b_VDS, "VSB": M4b_VSB, "ID": M4b_ID},
            "M5a": {"VGS": M5a_VGS, "VDS": M5a_VDS, "VSB": M5a_VSB, "ID": M5a_ID},
            "M5b": {"VGS": M5b_VGS, "VDS": M5b_VDS, "VSB": M5b_VSB, "ID": M5b_ID},
            "M6": {"VGS": M6_VGS, "VDS": M6_VDS, "VSB": M6_VSB, "ID": M6_ID},
            "Mvbp": {"VGS": Mvbp_VGS, "VDS": Mvbp_VDS, "VSB": Mvbp_VSB, "ID": Mvbp_ID},
            "Mvbn": {"VGS": Mvbn_VGS, "VDS": Mvbn_VDS, "VSB": Mvbn_VSB, "ID": Mvbn_ID},
        }

        # --- Small-signal AC analysis ---
        pmos_tw = self.pmos._width
        nmos_tw = self.nmos._width
        ss_params = {
            "M1a": {
                "gm":  M1a_GMID * M1a_ID,
                "gmb": 0.0,
                "gds": M1a_gdsid * M1a_ID,
                "cgs": M1a_cgs * (M1a_W / nmos_tw),
                "cgd": M1a_cgd * (M1a_W / nmos_tw),
                "cdd": M1a_cdd * (M1a_W / nmos_tw),
            },
            "M1b": {
                "gm":  M1a_GMID * M1b_ID,
                "gmb": 0.0,
                "gds": M1b_gdsid * M1b_ID,
                "cgs": M1b_cgs * (M1b_W / nmos_tw),
                "cgd": M1b_cgd * (M1b_W / nmos_tw),
                "cdd": M1b_cdd * (M1b_W / nmos_tw),
            },
            "M2a": {
                "gm":  M2a_GMID * M2a_ID,
                "gmb": 0.0,
                "gds": M2a_gdsid * M2a_ID,
                "cgs": M2a_cgs * (M2a_W / pmos_tw),
                "cgd": M2a_cgd * (M2a_W / pmos_tw),
                "cdd": M2a_cdd * (M2a_W / pmos_tw),
            },
            "M2b": {
                "gm":  M2a_GMID * M2b_ID,
                "gmb": 0.0,
                "gds": M2b_gdsid * M2b_ID,
                "cgs": M2b_cgs * (M2b_W / pmos_tw),
                "cgd": M2b_cgd * (M2b_W / pmos_tw),
                "cdd": M2b_cdd * (M2b_W / pmos_tw),
            },
            "M3a": {
                "gm":  M3a_GMID * M3a_ID,
                "gmb": 0.0,
                "gds": M3a_gdsid * M3a_ID,
                "cgs": M3a_cgs * (M3a_W / pmos_tw),
                "cgd": M3a_cgd * (M3a_W / pmos_tw),
                "cdd": M3a_cdd * (M3a_W / pmos_tw),
            },
            "M3b": {
                "gm":  M3a_GMID * M3b_ID,
                "gmb": 0.0,
                "gds": M3b_gdsid * M3b_ID,
                "cgs": M3b_cgs * (M3b_W / pmos_tw),
                "cgd": M3b_cgd * (M3b_W / pmos_tw),
                "cdd": M3b_cdd * (M3b_W / pmos_tw),
            },
            "M4a": {
                "gm":  M4a_GMID * M4a_ID,
                "gmb": 0.0,
                "gds": M4a_gdsid * M4a_ID,
                "cgs": M4a_cgs * (M4a_W / nmos_tw),
                "cgd": M4a_cgd * (M4a_W / nmos_tw),
                "cdd": M4a_cdd * (M4a_W / nmos_tw),
            },
            "M4b": {
                "gm":  M4a_GMID * M4b_ID,
                "gmb": 0.0,
                "gds": M4b_gdsid * M4b_ID,
                "cgs": M4b_cgs * (M4b_W / nmos_tw),
                "cgd": M4b_cgd * (M4b_W / nmos_tw),
                "cdd": M4b_cdd * (M4b_W / nmos_tw),
            },
            "M5a": {
                "gm":  M5a_GMID * M5a_ID,
                "gmb": 0.0,
                "gds": M5a_gdsid * M5a_ID,
                "cgs": M5a_cgs * (M5a_W / nmos_tw),
                "cgd": M5a_cgd * (M5a_W / nmos_tw),
                "cdd": M5a_cdd * (M5a_W / nmos_tw),
            },
            "M5b": {
                "gm":  M5a_GMID * M5b_ID,
                "gmb": 0.0,
                "gds": M5b_gdsid * M5b_ID,
                "cgs": M5b_cgs * (M5b_W / nmos_tw),
                "cgd": M5b_cgd * (M5b_W / nmos_tw),
                "cdd": M5b_cdd * (M5b_W / nmos_tw),
            },
            "M6": {
                "gm":  M6_GMID * M6_ID,
                "gmb": 0.0,
                "gds": M6_gdsid * M6_ID,
                "cgs": M6_cgs * (M6_W / nmos_tw),
                "cgd": M6_cgd * (M6_W / nmos_tw),
                "cdd": M6_cdd * (M6_W / nmos_tw),
            },
        }
        self.passive_params = {"COUT": COUT}
        ss  = build_ss_model(
            self.MOSFETS,
            self.PASSIVES,
            self.VSOURCES,
            ss_params,
            self.passive_params,
            signal_nodes={'VINP', 'VINN'},
        )
        ac  = ss.transfer(inputs={'VINP': 0.5, 'VINN': -0.5}, out='VOUT')
        ac_cm = ss.transfer(inputs={'VINP': 1.0, 'VINN': 1.0}, out='VOUT')

        # --- Output variables ---
        Area = M1a_L*M1a_W + M1b_L*M1b_W + M2a_L*M2a_W + M2b_L*M2b_W + M3a_L*M3a_W + M3b_L*M3b_W + M4a_L*M4a_W + M4b_L*M4b_W + M5a_L*M5a_W + M5b_L*M5b_W + M6_L*M6_W + Mvbn_L*Mvbn_W + Mvbp_L*Mvbp_W
        Itotal = M5a_ID_over_M1a_ID*M1a_ID + M1a_ID + M2b_ID
        VBP = VDD - M2a_VGS
        VCASCP = VDD - M2a_VDS - M3a_VGS
        VCASCN = M4a_VGS + M5a_VDS
        VBN = M6_VGS
        VOUT_DC = VDD - M2a_VDS - M3a_VGS - M3b_VDS + M3b_VGS
        VOUT_MAX = min(-M3b_VDSAT + M3b_VGS + VCASCP, -M2a_VGS - M3b_VDSAT + M3b_VGS - VBP + VCASCP + VDD, -M2b_VGS - M3b_VDSAT + M3b_VGS - VBP + VCASCP + VDD)
        VOUT_MIN = max(M4b_VDSAT - M4b_VGS + VCASCN, -M2a_VGS + M4b_VDSAT - M4b_VGS - VBP + VCASCN + VDD, -M2b_VGS + M4b_VDSAT - M4b_VGS - VBP + VCASCN + VDD)
        VIN_MAX = min(-M1a_VDSAT + M1a_VGS + M3a_VGS + VCASCP, M1a_VGS - M1b_VDSAT + M3b_VGS + VCASCP, -M1a_VDSAT + M1a_VGS - M2a_VGS + M3a_VGS - VBP + VCASCP + VDD, -M1a_VDSAT + M1a_VGS - M2b_VGS + M3a_VGS - VBP + VCASCP + VDD, M1a_VGS - M1b_VDSAT - M2a_VGS + M3b_VGS - VBP + VCASCP + VDD, M1a_VGS - M1b_VDSAT - M2b_VGS + M3b_VGS - VBP + VCASCP + VDD)
        VIN_MIN = max(M1a_VGS + M6_VDSAT, M1a_VGS - M2a_VGS + M6_VDSAT - VBP + VDD, M1a_VGS - M2b_VGS + M6_VDSAT - VBP + VDD)
        Output_Swing = VOUT_MAX - VOUT_MIN

        return {
            "GBW":         ac.ugf(),
            "AC Gain (dB)": 20.0 * np.log10(max(abs(ac.gain()), 1e-300)),
            "PM":          ac.phase_margin(),
            "DC CMR (dB)": 20.0 * np.log10(max(ac.rejection(ac_cm), 1e-300)),
            'Area': Area,
            'Itotal': Itotal,
            'VBP': VBP,
            'VCASCP': VCASCP,
            'VCASCN': VCASCN,
            'VBN': VBN,
            'VOUT_DC': VOUT_DC,
            'VOUT_MAX': VOUT_MAX,
            'VOUT_MIN': VOUT_MIN,
            'VIN_MAX': VIN_MAX,
            'VIN_MIN': VIN_MIN,
            'Output_Swing': Output_Swing,
        }

    def compute_vsource_params(self, opt_params: dict[str, float]) -> dict[str, float]:
        ops = self.device_operating_points
        VDD = self.vdd
        opt_params.get('M5a_ID_over_M1a_ID', 0.0)
        opt_params.get('M5a_VDSAT_MARGIN', 0.0)
        opt_params.get('M2a_VDSAT_MARGIN', 0.0)
        VBP = VDD - ops.get("M2a", {}).get("VGS", 0.0)
        VCASCP = VDD - ops.get("M2a", {}).get("VDS", 0.0) - ops.get("M3a", {}).get("VGS", 0.0)
        VCASCN = ops.get("M4a", {}).get("VGS", 0.0) + ops.get("M5a", {}).get("VDS", 0.0)
        VBN = ops.get("M6", {}).get("VGS", 0.0)
        return {"VBP": VBP, "VCASCP": VCASCP, "VCASCN": VCASCN, "VBN": VBN}


def build_circuit(**kwargs) -> Circuit:
    return Circuit(**kwargs)


def _generate_simulation_netlist(optimizer: Optimizer, output_path: str) -> None:
    circuit = optimizer.circuit
    opt_params = optimizer.get_opt_params()
    specs = circuit.evaluate_specs(**opt_params)
    generator = SpectreGenerator(
        name='amp',
        ports=['VINN', 'VINP', 'VOUT', 'vdd', 'vss'],
        ground='vss',
        context={"vcm": circuit.vin_cm, "vout_dc": specs.get("VOUT_DC", circuit.vin_cm)},
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
