"""User-editable configuration for the generated gm/ID optimizer.

This is the file you normally run and edit.  The sibling amp.py
file contains the circuit model and equations.  Use this config file
for technology paths, fixed bias conditions, optimizer settings,
optimization variables, and target specs.

How the optimizer works:
- PARAMETERS define the variables CMA-ES/SLSQP are allowed to change.
- Circuit conditions such as VDD, VOUT_DC, and load capacitance are fixed.
- The circuit model uses gm/ID lookup tables to compute operating
  points, device widths, currents, small-signal parameters, and specs.
- TARGET_SPECS assigns goals to returned spec names.  Specs with mode
  "max" are pushed above the target; specs with mode "min" are pushed
  below the target.

Wide-Swing Cascode Current Mirror topology:
  M1, M2 : bottom mirror pair (gates tied to IREF)
  M3, M4 : cascode pair (gates tied to VBN)
  M1+M4 : input branch  (carry IREF)
  M2+M3 : output branch (carry K * IREF)

Adding an optimization parameter:
- Add an OptimizationParameter entry here only for a variable that the
  circuit model reads from params[...] in evaluate_specs().
- Circuit variables: IREF, K, GMID_M1, L_M1, GMID_M3, L_M3.
- M1 and M2 share the same GMID and L (matched pair).
- M3 and M4 share the same GMID and L (cascode pair).

Adding a target spec:
- The key must exist in the dictionary returned by evaluate_specs().
- Available keys: "Rout", "DC Gain", "Vcompliance", "Iout", "Area",
  "Itotal", "VOUT_DC", "VBN", "VOUT_MIN", "VOUT_MAX", "Output_Swing".
- To add a new spec, first compute and return it in amp.py,
  then add a matching TARGET_SPECS entry here.
"""

from mirror import run, OptimizationParameter, Spec


# === PDK / Technology (edit these) ============================================
LOOKUP_TABLE = "/home/medwatt/coding/gmid_lookup/tsmc_65_lv_spectre.npz"
NMOS_NAME = "nch_lvt"
OUTPUT_MODULE = "./wide_swing_nmos_mirror.scs"

# === Nominal circuit conditions (edit these) ===================================
VDD = 1.2
COUT = 1e-12
LMIN = 200e-09
LMAX = 7.5e-06
IREF = 5e-6         # reference current from bias generator
K = 4.0             # current mirror gain = Iout / Iref
VDSAT_MARGIN = 0.1  # VDSAT safety margin for M1/M2 bottom devices


# === Optimizer settings (edit these) ==========================================
MAXITER = 200
SEED = 1
N_RESTARTS = 1
FIXED_POINT_ITERATIONS = 5


# === Optimization parameters (L bounds must match LUT range) ==================
# GMID_M1 : gm/ID for bottom pair M1, M2
# L_M1    : channel length for bottom pair
# GMID_M3 : gm/ID for cascode pair M3, M4
# L_M3    : channel length for cascode pair
PARAMETERS = [
    OptimizationParameter("GMID_M1", (8.0, 15.0)),
    OptimizationParameter("L_M1", (LMIN, LMAX)),
    OptimizationParameter("GMID_M3", (8.0, 15.0)),
    OptimizationParameter("L_M3", (LMIN, LMAX)),
]


# === Target specs (edit these) ===============================================
# Spec(target, mode, weight), where mode is "max" or "min".
TARGET_SPECS = {
    "Rout": Spec(5e9, "max", 1.0),
    "Area": Spec(200e-12, "min", 1.0),
    "Vcompliance": Spec(0.2, "min", 2.0),
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
        vdsat_margin=VDSAT_MARGIN,
        maxiter=MAXITER,
        seed=SEED,
        n_restarts=N_RESTARTS,
        fixed_point_iterations=FIXED_POINT_ITERATIONS,
    )

# To verify: python cm_tb.py <OUTPUT_MODULE> --pdk <pdk.scs> --section tt_lib --model nch_lvt
