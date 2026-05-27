from mirror import run, OptimizationParameter, Spec


# === PDK / Technology (edit these) ============================================
LOOKUP_TABLE = "/home/medwatt/coding/gmid_lookup/tsmc_65_lv_spectre.npz"
NMOS_NAME = "nch_lvt"
OUTPUT_MODULE = "./cascode_nmos_mirror.scs"

# === Nominal circuit conditions (edit these) ===================================
VDD = 1.2
COUT = 1e-12
LMIN = 200e-09
LMAX = 7.5e-06
IREF = 5e-6  # reference current from bias generator
K = 4.0  # current mirror gain = Iout / Iref

# === Optimizer settings (edit these) ==========================================
MAXITER = 500
SEED = 1
N_RESTARTS = 1
FIXED_POINT_ITERATIONS = 10


# === Optimization parameters (L bounds must match LUT range) ==================
# GMID_M1 : gm/ID for bottom pair M1, M2
# L_M1    : channel length for bottom pair
# GMID_M3 : gm/ID for top pair M3, M4
# L_M3    : channel length for top pair
PARAMETERS = [
    OptimizationParameter("GMID_M1", (8.0, 15.0)),
    OptimizationParameter("L_M1", (LMIN, LMAX)),
    OptimizationParameter("GMID_M3", (8.0, 15.0)),
    OptimizationParameter("L_M3", (LMIN, LMAX)),
]


# === Target specs (edit these) ===============================================
TARGET_SPECS = {
    "Rout": Spec(5e9, "max", 1.0),
    "Area": Spec(20e-12, "min", 10.0),
    "Vcompliance": Spec(0.3, "min", 2.0),
}


if __name__ == "__main__":
    run(
        lookup_table=LOOKUP_TABLE,
        nmos_name=NMOS_NAME,
        vdd=VDD,
        cout=COUT,
        iref=IREF,
        k=K,
        parameters=PARAMETERS,
        target_specs=TARGET_SPECS,
        output_module=OUTPUT_MODULE,
        maxiter=MAXITER,
        seed=SEED,
        n_restarts=N_RESTARTS,
        fixed_point_iterations=FIXED_POINT_ITERATIONS,
    )
