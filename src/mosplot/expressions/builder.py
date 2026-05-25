from __future__ import annotations

import numpy as np

from .expression import Expression


def compute_device_width(
    dev_params: dict,
    param_names: list[str],
    lookup_table_entry: dict,
) -> float:
    """
    Compute the effective device width from the lookup table entry.

    Priority: explicit 'w' in device_parameters -> 'weff' parameter (scaled by 'nf').
    Raises ValueError if neither is found.
    """
    if "w" in dev_params:
        return float(dev_params["w"])
    if "weff" in param_names:
        weff = float(np.asarray(lookup_table_entry["weff"]).ravel()[0])
        nf = float(dev_params.get("nf", 1))
        return weff * nf
    raise ValueError(
        "Device width could not be computed: neither 'w' in device_parameters "
        "nor 'weff' in parameter_names."
    )


def build_expressions(width: float, vdsat_var: str) -> dict[str, Expression]:
    """
    Build the complete set of standard MOSFET expressions.

    Returns a dict mapping attribute name -> Expression. The caller assigns each
    entry to self via setattr in __init__, making all expressions available on
    both Mosfet and FastMosfet.

    Parameters
    ----------
    width : float
        Effective device width in metres; captured by current_density_expression.
    vdsat_var : str
        The table key for the saturation voltage -- either "vdsat" or "vdssat"
        depending on the simulator model.
    """
    w = width
    return {
        # --- bias voltages ---------------------------------------------------------------------------------
        "length_expression": Expression(
            variables=["length"],
            label=r"$\mathrm{Length}\ (m)$",
        ),
        "vgs_expression": Expression(
            variables=["vgs"],
            label=r"$V_{\mathrm{GS}}\ (V)$",
        ),
        "vsg_expression": Expression(
            variables=["vgs"],
            function=lambda x: -x,
            label=r"$V_{\mathrm{SG}}\ (V)$",
        ),
        "vbs_expression": Expression(
            variables=["vbs"],
            label=r"$V_{\mathrm{BS}}\ (V)$",
        ),
        "vsb_expression": Expression(
            variables=["vbs"],
            function=lambda x: -x,
            label=r"$V_{\mathrm{SB}}\ (V)$",
        ),
        "vds_expression": Expression(
            variables=["vds"],
            label=r"$V_{\mathrm{DS}}\ (V)$",
        ),
        "vsd_expression": Expression(
            variables=["vds"],
            function=lambda x: -x,
            label=r"$V_{\mathrm{SD}}\ (V)$",
        ),
        # vdsat_var is either "vdsat" or "vdssat" depending on the simulator model
        "vdsat_expression": Expression(
            variables=[vdsat_var],
            label=r"$V_{\mathrm{DS_{\mathrm{SAT}}}}\ (V)$",
        ),
        "vth_expression": Expression(
            variables=["vth"],
            label=r"$V_{\mathrm{TH}}\ (V)$",
        ),
        "vov_expression": Expression(
            variables=["vgs", "vth"],
            function=lambda x, y: x - y,
            label=r"$V_{\mathrm{OV}}\ (V)$",
        ),
        "vstar_expression": Expression(
            variables=["gm", "id"],
            function=lambda x, y: (2 * y) / x,
            label=r"$V^{\star}\ (V)$",
        ),
        # --- small-signal parameters ------------------------------------------------------------------
        "id_expression": Expression(
            variables=["id"],
            label=r"$I_{D}\ (A)$",
        ),
        "gm_expression": Expression(
            variables=["gm"],
            label=r"$g_{m}\ (S)$",
        ),
        "gmbs_expression": Expression(
            variables=["gmbs"],
            label=r"$g_{\mathrm{mbs}}\ (S)$",
        ),
        "gds_expression": Expression(
            variables=["gds"],
            label=r"$g_{\mathrm{ds}}\ (S)$",
        ),
        "cgg_expression": Expression(
            variables=["cgg"],
            label=r"$c_{\mathrm{gg}}\ (F)$",
        ),
        "cgs_expression": Expression(
            variables=["cgs"],
            label=r"$c_{\mathrm{gs}}\ (F)$",
        ),
        "cgd_expression": Expression(
            variables=["cgd"],
            label=r"$c_{\mathrm{gd}}\ (F)$",
        ),
        "cbg_expression": Expression(
            variables=["cbg"],
            label=r"$c_{\mathrm{bg}}\ (F)$",
        ),
        "cdd_expression": Expression(
            variables=["cdd"],
            label=r"$c_{\mathrm{dd}}\ (F)$",
        ),
        # --- derived figures of merit ---------------------------------------------------------------─
        "gmid_expression": Expression(
            variables=["gm", "id"],
            function=lambda gm, id_: gm / id_,
            label=r"$g_m/I_D\ (S/A)$",
        ),
        "gain_expression": Expression(
            variables=["gm", "gds"],
            function=lambda x, y: x / y,
            label=r"$g_{m}/g_{\mathrm{ds}}$",
        ),
        "transit_frequency_expression": Expression(
            variables=["gm", "cgg"],
            function=lambda x, y: x / (2 * np.pi * y),
            label=r"$f_{T}\ (Hz)$",
        ),
        "early_voltage_expression": Expression(
            variables=["id", "gds"],
            function=lambda x, y: x / y,
            label=r"$V_{A}\ (V)$",
        ),
        "inverse_early_voltage_expression": Expression(
            variables=["gds", "id"],
            function=lambda x, y: x / y,
            label=r"$1/V_{A}\ (V^{-1})$",
        ),
        "current_density_expression": Expression(
            variables=["id"],
            function=lambda x: x / w,
            label=r"$I_{D}/W\ (A/m)$",
        ),
        "rds_expression": Expression(
            variables=["gds"],
            function=lambda x: 1 / x,
            label=r"$r_{\mathrm{ds}}\ (\Omega)$",
        ),
    }
