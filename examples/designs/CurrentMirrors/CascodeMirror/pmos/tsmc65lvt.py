"""User-editable configuration for the generated gm/ID optimizer.

Standard Cascode PMOS Current Mirror topology:
  M1, M4 : diode-connected reference pair (gate = drain)
  M2, M3 : output mirror pair
  M1+M4 : input branch  (carry IREF)
  M2+M3 : output branch (carry K * IREF)
"""

from mirror import run, OptimizationParameter, Spec


# === PDK / Technology (edit these) ============================================
LOOKUP_TABLE = "/home/medwatt/coding/gmid_lookup/tsmc_65_lv_spectre.npz"
PMOS_NAME = "pch_lvt"
OUTPUT_MODULE = "./cascode_pmos_mirror.scs"

# === Nominal circuit conditions (edit these) ===================================
VDD = 1.2
COUT = 1e-12
LMIN = 200e-09
LMAX = 7.5e-06
IREF = 5e-6         # reference current from bias generator
K = 4.0             # current mirror gain = Iout / Iref
VDSAT_MARGIN = 0.1  # VDSAT safety margin


# === Optimizer settings (edit these) ==========================================
MAXITER = 200
SEED = 1
N_RESTARTS = 1
FIXED_POINT_ITERATIONS = 5


# === Optimization parameters (L bounds must match LUT range) ==================
PARAMETERS = [
    OptimizationParameter("GMID_M1", (8.0, 15.0)),
    OptimizationParameter("L_M1", (LMIN, LMAX)),
    OptimizationParameter("GMID_M3", (8.0, 15.0)),
    OptimizationParameter("L_M3", (LMIN, LMAX)),
]


# === Target specs (edit these) ===============================================
TARGET_SPECS = {
    "Rout": Spec(5e9, "max", 1.0),
    "Area": Spec(200e-12, "min", 1.0),
    "Vcompliance": Spec(0.2, "min", 2.0),
}


if __name__ == "__main__":
    run(
        lookup_table=LOOKUP_TABLE,
        pmos_name=PMOS_NAME,
        vdd=VDD,
        cout=COUT,
        iref=IREF,
        k=K,
        parameters=PARAMETERS,
        target_specs=TARGET_SPECS,
        output_module=OUTPUT_MODULE,
        vdsat_margin=VDSAT_MARGIN,
        maxiter=MAXITER,
        seed=SEED,
        n_restarts=N_RESTARTS,
        fixed_point_iterations=FIXED_POINT_ITERATIONS,
    )
