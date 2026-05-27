"""Improved Wilson PMOS current mirror config."""

from mirror import run, OptimizationParameter, Spec

LOOKUP_TABLE = "/home/medwatt/coding/gmid_lookup/tsmc_65_lv_spectre.npz"
PMOS_NAME = "pch_lvt"
OUTPUT_MODULE = "./iwilson_pmos_mirror.scs"
VDD, COUT, IREF, K = 1.2, 1e-12, 5e-6, 4.0
LMIN = 200e-09
LMAX = 7.5e-06

PARAMETERS = [
    OptimizationParameter("GMID_M1", (8.0, 15.0)),
    OptimizationParameter("L_M1", (LMIN, LMAX)),
    OptimizationParameter("GMID_M3", (8.0, 15.0)),
    OptimizationParameter("L_M3", (LMIN, LMAX)),
]
TARGET_SPECS = {"Rout": Spec(5e9, "max", 1.0), "Area": Spec(200e-12, "min", 1.0),
                "Vcompliance": Spec(0.2, "min", 2.0)}

if __name__ == "__main__":
    run(lookup_table=LOOKUP_TABLE, pmos_name=PMOS_NAME, vdd=VDD, cout=COUT, iref=IREF, k=K,
        parameters=PARAMETERS, target_specs=TARGET_SPECS, output_module=OUTPUT_MODULE)
