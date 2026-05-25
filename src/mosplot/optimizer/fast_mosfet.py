from __future__ import annotations

from typing import overload

from mosplot.expressions import Expression, build_expressions, compute_device_width
from mosplot.interpolation import GmIdTable


class FastMosfet:
    """Fast MOSFET lookup for circuit optimization.

    Wraps GmIdTable to provide expression-based lookups indexed by
    (length, gmid, vds, vbs). Designed for optimization loops where hundreds
    of lookups are performed per iteration.

    Construction
    ------------
        # Build the grid in memory:
        pmos = FastMosfet(lookup_table, "pch_lvt")

        # Build once and cache to disk (subsequent runs load instantly):
        pmos = FastMosfet(lookup_table, "pch_lvt", cache_dir="~/.cache/mosplot")

        # Force a cache rebuild:
        pmos = FastMosfet(lookup_table, "pch_lvt", cache_dir="~/.cache/mosplot", rebuild_cache=True)

    Parameters
    ----------
    cache_dir : str | Path | None
        Directory for cached GmIdTable .npz files. Omit to build in memory.
    rebuild_cache : bool
        Ignore an existing cache and force a rebuild.
    cache_tag : str | None
        Tag included in the cache filename. Bump this when the raw lookup
        table changes but device names and n_gmid settings do not.
    compressed_cache : bool
        Write compressed .npz files (slower to load). Default False.
    verbose : bool
        Print cache load/build messages.
    """

    # Class-level annotations for LSP resolution -- populated by build_expressions()
    length_expression: Expression
    vgs_expression: Expression
    vsg_expression: Expression
    vbs_expression: Expression
    vsb_expression: Expression
    vds_expression: Expression
    vsd_expression: Expression
    vdsat_expression: Expression
    vth_expression: Expression
    vov_expression: Expression
    vstar_expression: Expression
    id_expression: Expression
    gm_expression: Expression
    gmbs_expression: Expression
    gds_expression: Expression
    cgg_expression: Expression
    cgs_expression: Expression
    cgd_expression: Expression
    cbg_expression: Expression
    cdd_expression: Expression
    gmid_expression: Expression
    gain_expression: Expression
    transit_frequency_expression: Expression
    early_voltage_expression: Expression
    inverse_early_voltage_expression: Expression
    current_density_expression: Expression
    rds_expression: Expression

    def __init__(
        self,
        lookup_table,
        mos_name,
        n_gmid=50,
        gmid_bounds=None,
        *,
        cache_dir=None,
        rebuild_cache=False,
        cache_tag=None,
        compressed_cache=False,
        verbose=False,
    ):
        if cache_dir is None:
            self._table = GmIdTable(
                lookup_table, mos_name,
                n_gmid=n_gmid, gmid_bounds=gmid_bounds,
            )
        else:
            self._table = GmIdTable.build_or_load(
                lookup_table, mos_name,
                cache_dir=cache_dir, n_gmid=n_gmid, gmid_bounds=gmid_bounds,
                cache_tag=cache_tag, rebuild=rebuild_cache,
                compressed=compressed_cache, verbose=verbose,
            )

        dev         = lookup_table[mos_name]
        dev_params  = dev.get("device_parameters", {})
        param_names = list(dev.get("parameter_names", []))

        self._width = compute_device_width(dev_params)

        vdsat_var = "vdssat" if "vdssat" in param_names else "vdsat"
        for name, expr in build_expressions(self._width, vdsat_var).items():
            setattr(self, name, expr)

    @overload
    def interpolate(self, length: float, gmid: float, vds: float, vbs: float, expression: Expression) -> float: ...
    @overload
    def interpolate(self, length: float, gmid: float, vds: float, vbs: float, expression: list[Expression]) -> list[float]: ...

    def interpolate(
        self,
        length: float,
        gmid: float,
        vds: float,
        vbs: float,
        expression: Expression | list[Expression],
    ) -> float | list[float]:
        """Look up one or more expressions at a single operating point.

        Parameters
        ----------
        length : float
            Channel length (metres).
        gmid : float
            Target gm/Id ratio (S/A).
        vds : float
            Drain-source voltage (V).
        vbs : float
            Body-source voltage (V).
        expression : Expression or list[Expression]
            Quantity or quantities to look up.

        Returns
        -------
        float if a single Expression is given, list[float] otherwise.
        """
        single = not isinstance(expression, list)
        exprs  = [expression] if single else expression

        needed = list({v for e in exprs for v in e.variables if v != "length"})
        raw    = self._table.lookup_scalar(length, gmid, vds, vbs, params=needed)

        results = [expr.function(*[raw[v] for v in expr.variables]) for expr in exprs]
        return results[0] if single else results
