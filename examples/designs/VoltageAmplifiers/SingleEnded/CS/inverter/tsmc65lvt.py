"""Configuration for CMOS inverter amplifier — TSMC 65nm LVT."""

from amp import run, OptimizationParameter, Spec


LOOKUP_TABLE = "/home/medwatt/coding/gmid_lookup/tsmc_65_lv_spectre.npz"
NMOS_NAME = "nch_lvt"
PMOS_NAME = "pch_lvt"
OUTPUT_MODULE = "./inverter_cs.scs"

VDD = 1.2
VOUT_DC = 0.6
COUT = 5e-12

MAXITER = 300
SEED = 1
N_RESTARTS = 1
FIXED_POINT_ITERATIONS = 5

PARAMETERS = [
    OptimizationParameter("M1_ID",   (5e-06, 100e-06)),
    OptimizationParameter("M1_GMID", (5.0, 18.0)),
    OptimizationParameter("M1_L",    (120e-9, 2e-06)),
    OptimizationParameter("M2_GMID", (5.0, 18.0)),
    OptimizationParameter("M2_L",    (120e-9, 2e-06)),
]

TARGET_SPECS = {
    "GBW":          Spec(50e6,       "max", 1.0),
    "AC Gain (dB)": Spec(20.0,       "max", 1.0),
    "PM":           Spec(60.0,       "max", 0.5),
    "Area":         Spec(5e-12,      "min", 1.0),
    "Itotal":       Spec(100e-6,     "min", 1.0),
    "Output_Swing": Spec(0.7 * VDD,  "max", 1.0),
    "DC_Error":     Spec(0.01,       "min", 100.0),
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
