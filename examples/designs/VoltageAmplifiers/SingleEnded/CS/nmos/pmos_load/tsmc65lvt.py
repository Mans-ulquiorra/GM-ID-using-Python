"""User-editable configuration for the generated gm/ID optimizer.

This is the file you normally run and edit.  The sibling generated_*.py
file contains the circuit model and equations.  Use this config file
for technology paths, fixed bias conditions, optimizer settings,
optimization variables, and target specs.

How the optimizer works:
- PARAMETERS define the variables CMA-ES/SLSQP are allowed to change.
- Circuit conditions such as VDD, VIN_CM, and load capacitance are fixed.
- The generated circuit uses gm/ID lookup tables to compute operating
  points, device widths, currents, small-signal parameters, and specs.
- TARGET_SPECS assigns goals to returned spec names.  Specs with mode
  "max" are pushed above the target; specs with mode "min" are pushed
  below the target.

Adding an optimization parameter:
- Add an OptimizationParameter entry here only for a variable that the
  circuit model reads from params[...] in evaluate_specs().
- Common examples are device current, gm/ID, length, or a passive value:
  M1a_ID, M1a_GMID, M1a_L, Rz, CC, etc.
- Adding a parameter name here alone is not enough.  The generated_*.py
  model must also use that same name when computing specs.

Adding a target spec:
- The key must exist in the dictionary returned by evaluate_specs().
- Common generated keys include "GBW", "AC Gain (dB)", "PM",
  "DC CMR (dB)", "Area", "Itotal", "VOUT_MAX", "VOUT_MIN",
  "VIN_MAX", "VIN_MIN", and "Output_Swing" when available.
- To add a new spec, first compute and return it in generated_*.py,
  then add a matching TARGET_SPECS entry here.
- Do not target a name that is not returned by evaluate_specs(); the
  optimizer will fail when it cannot find that spec.
"""

from amp import run, OptimizationParameter, Spec


# === PDK / Technology (edit these) ============================================
LOOKUP_TABLE = "/home/medwatt/coding/gmid_lookup/tsmc_65_lv_spectre.npz"
NMOS_NAME = "nch_lvt"
PMOS_NAME = "pch_lvt"
OUTPUT_MODULE = "./pmos_cs.scs"

# === Nominal circuit conditions (edit these) ===================================
VDD = 1.2
VOUT_DC = 0.6
COUT = 5e-12


# === Optimizer settings (edit these) ==========================================
# MAXITER controls optimizer effort.  Increase it for harder designs.
# FIXED_POINT_ITERATIONS controls operating-point settling inside each
# spec evaluation; 5 is usually enough unless equations converge slowly.
MAXITER    = 200
SEED       = 1
N_RESTARTS = 1
FIXED_POINT_ITERATIONS = 5


# === Optimization parameters (L bounds must match LUT range) ==================
# Each entry is OptimizationParameter(name, (lower, upper)).
# These names are generated from circuit variables and are read from
# params[...] in the generated circuit model.
PARAMETERS = [
    OptimizationParameter("M1_ID", (5e-06, 100e-06)),
    OptimizationParameter("M1_GMID", (8.0, 18.0)),
    OptimizationParameter("M1_L", (120e-9, 2e-06)),
    OptimizationParameter("M2_GMID", (8.0, 18.0)),
    OptimizationParameter("M2_L", (120e-9, 2e-06)),
]


# === Target specs (edit these) ===============================================
# Spec(target, mode, weight), where mode is "max" or "min".
# Increase weight for specs that should dominate the scalar cost.
TARGET_SPECS = {
    "GBW": Spec(50e6, "max", 1.0),
    "AC Gain (dB)": Spec(20.0, "max", 1.0),
    "PM": Spec(60.0, "max", 1.0),
    "Area": Spec(5e-12, "min", 1.0),
    "Itotal": Spec(10e-6, "min", 1.0),
    "Output_Swing": Spec(0.7 * VDD, "max", 1.0),
}


if __name__ == "__main__":
    run(
        lookup_table=LOOKUP_TABLE,
        nmos_name=NMOS_NAME,
        pmos_name=PMOS_NAME,
        vdd=VDD,
        vout_dc=VOUT_DC,
        cout=COUT,
        parameters=PARAMETERS,
        target_specs=TARGET_SPECS,
        output_module=OUTPUT_MODULE,
        maxiter=MAXITER,
        seed=SEED,
        n_restarts=N_RESTARTS,
        fixed_point_iterations=FIXED_POINT_ITERATIONS,
    )
