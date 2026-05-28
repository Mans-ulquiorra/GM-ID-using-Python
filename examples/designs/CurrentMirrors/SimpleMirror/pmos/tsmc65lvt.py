"""Simple 2-transistor PMOS current mirror config."""

from mirror import run, OptimizationParameter, Spec

LOOKUP_TABLE = "/home/medwatt/coding/gmid_lookup/tsmc_65_lv_spectre.npz"
PMOS_NAME = "pch_lvt"
OUTPUT_MODULE = "./simple_pmos_mirror.scs"

VDD = 1.2
COUT = 1e-12
LMIN = 200e-09
LMAX = 7.5e-06
IREF = 5e-6
K = 4.0

MAXITER = 200
SEED = 1
N_RESTARTS = 1
FIXED_POINT_ITERATIONS = 5

PARAMETERS = [
    OptimizationParameter("GMID", (8.0, 15.0)),
    OptimizationParameter("L", (LMIN, LMAX)),
]

TARGET_SPECS = {
    "Rout": Spec(5e9, "max", 1.0),
    "Area": Spec(20e-12, "min", 10.0),
    "Vcompliance": Spec(0.2, "min", 2.0),
}


CORNERS = [
    dict(
        lookup_table_path=LOOKUP_TABLE,
        pmos_name=PMOS_NAME,
        vdd=VDD,
        cout=COUT,
        iref=IREF,
        k=K,
    ),
]


if __name__ == "__main__":
    run(
        corners=CORNERS,
        parameters=PARAMETERS,
        target_specs=TARGET_SPECS,
        output_module=OUTPUT_MODULE,
        maxiter=MAXITER,
        seed=SEED,
        n_restarts=N_RESTARTS,
        fixed_point_iterations=FIXED_POINT_ITERATIONS,
    )
