from __future__ import annotations

from typing import cast

import numpy as np

from mosplot.expressions import (
    Expression,
    evaluate_expression,
    build_expressions,
    compute_device_width,
)
from mosplot.table import extract_2d_table
from mosplot.interpolation import GridInterpolator
from .plot import Plotter


_LEGEND_TITLE: dict[str, str] = {
    "length": "Length",
    "vbs": "$V_{\\mathrm{BS}}$",
    "vgs": "$V_{\\mathrm{GS}}$",
    "vds": "$V_{\\mathrm{DS}}$",
}


class Mosfet:
    """
    Initialize a MOSFET object.

    When creating a MOSFET object, exactly two of the parameters `length`, `vbs`, `vgs`, or `vds`
    must be provided as fixed values. The remaining parameters can be specified as a range or set to
    `None` to use the full range from the lookup table. Any parameter not fixed is treated as the
    secondary sweep variable.

    If two parameters are given as ranges, you must indicate which one is the primary sweep variable
    using the `primary` argument.

    Args:
        lookup_table: dictionary containing MOSFET parameter data.
        mos: model name of the MOSFET.
        length: mosfet length.
        vbs: body-source voltage.
        vgs: gate-source voltage.
        vds: drain-source voltage.
        primary: name of the primary sweep.

    Examples:
        Fixed vbs and vds; sweep vgs (primary) and length (secondary)

        nmos = Mosfet(lookup_table=lookup_table, mos="nch_lvt", vbs=0.0, vds=0.4, vgs=(0.01, 1.19))
        pmos = Mosfet(lookup_table=lookup_table, mos="pch_lvt", vbs=0.0, vgs=-0.4, vds=(-1.19, -0.01))
    """

    # Class-level annotations for LSP resolution -- populated by build_expressions() in __init__
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
        *,
        lookup_table: dict,
        mos: str,
        length: float | list[float] | np.ndarray | None = None,
        vbs: float | tuple[float, float] | tuple[float, float, float] | None = None,
        vgs: float | tuple[float, float] | tuple[float, float, float] | None = None,
        vds: float | tuple[float, float] | tuple[float, float, float] | None = None,
        primary: str | None = None,
    ) -> None:
        self.mos = mos
        self.lookup_table = lookup_table[mos]
        self.length_all = self.lookup_table["length"]
        self.parameters = self.lookup_table["parameter_names"]
        self.device_parameters = self.lookup_table["device_parameters"]
        self.width = compute_device_width(self.device_parameters, self.parameters, self.lookup_table)

        self.secondary_var, self.filtered_variables, self.extracted_table = extract_2d_table(
            lookup_table=self.lookup_table,
            length=length,
            vbs=vbs,
            vgs=vgs,
            vds=vds,
            primary=primary,
        )
        self.length = self.filtered_variables["length"]
        self.vbs = self.filtered_variables["vbs"]
        self.vgs = self.filtered_variables["vgs"]
        self.vds = self.filtered_variables["vds"]

        vdsat_var = "vdssat" if "vdssat" in self.parameters else "vdsat"
        for name, expr in build_expressions(self.width, vdsat_var).items():
            setattr(self, name, expr)

    def calculate_from_expression(
        self,
        expression: Expression,
        filter_by_rows: np.ndarray | None = None,
    ) -> tuple[np.ndarray, str]:
        """
        Evaluate an expression over the extracted lookup table.

        Args:
            expression: The Expression object defining the computation.
            filter_by_rows: Optional array of row indices to filter the data.

        Returns:
            A tuple of (computed array, label string).
        """
        return evaluate_expression(expression, self.extracted_table, filter_by_rows)

    def _render_plot(
        self,
        *,
        x: np.ndarray,
        y: np.ndarray,
        x_label: str,
        y_label: str,
        y2: np.ndarray | None,
        y2_label: str,
        legend: list | None,
        legend_title: str | None,
        x_limit: tuple[float, float] | None,
        y_limit: tuple[float, float] | None,
        y2_limit: tuple[float, float] | None,
        x_scale: str,
        y_scale: str,
        y2_scale: str,
        x_eng_format: bool,
        y_eng_format: bool,
        y2_eng_format: bool,
        legend_placement: str | None,
        legend_location: tuple[float, float] | None,
        legend_eng_format: bool,
        show_legend: bool,
        fig_size: tuple[int, int] | None,
        save_fig: str,
        return_result: bool,
    ) -> tuple | None:
        if y2 is not None:
            fig_size = (6, 4) if fig_size is None else fig_size
            plotter = Plotter(fig_size=fig_size, show_legend=show_legend)
            _, ax, ax2 = plotter.create_figure_with_twin(
                title="",
                x_label=x_label,
                y_label=y_label,
                y2_label=y2_label,
                x_lim=x_limit,
                y_lim=y_limit,
                y2_lim=y2_limit,
                x_scale=x_scale,
                y_scale=y_scale,
                y2_scale=y2_scale,
                x_eng_format=x_eng_format,
                y_eng_format=y_eng_format,
                y2_eng_format=y2_eng_format,
            )
            plotter.plot_data(ax2, x, y2, line_style="dashed", end_plotting=False)
            plotter.plot_data(
                ax,
                x,
                y,
                line_style="solid",
                legend=legend,
                legend_title=legend_title,
                legend_eng_format=legend_eng_format,
                legend_placement="top" if legend_placement is None else legend_placement,
                bbox_to_anchor=legend_location,
                save_fig=save_fig,
            )
            return (x, y, y2) if return_result else None
        else:
            fig_size = (8, 4) if fig_size is None else fig_size
            plotter = Plotter(fig_size=fig_size, show_legend=show_legend)
            _, ax = plotter.create_figure(
                title="",
                x_label=x_label,
                y_label=y_label,
                x_lim=x_limit,
                y_lim=y_limit,
                x_scale=x_scale,
                y_scale=y_scale,
                x_eng_format=x_eng_format,
                y_eng_format=y_eng_format,
            )
            plotter.plot_data(
                ax,
                x,
                y,
                legend=legend,
                legend_title=legend_title,
                legend_eng_format=legend_eng_format,
                legend_placement=legend_placement,
                bbox_to_anchor=legend_location,
                save_fig=save_fig,
            )
            return (x, y) if return_result else None

    def plot_by_expression(
        self,
        *,
        x_expression: Expression,
        y_expression: Expression,
        y2_expression: Expression | None = None,
        filtered_values: float | list[float] | np.ndarray | None = None,
        x_limit: tuple[float, float] | None = None,
        y_limit: tuple[float, float] | None = None,
        y2_limit: tuple[float, float] | None = None,
        x_scale: str = "",
        y_scale: str = "",
        y2_scale: str = "",
        x_eng_format: bool = False,
        y_eng_format: bool = False,
        y2_eng_format: bool = False,
        legend_placement: str | None = None,
        legend_location: tuple[float, float] | None = None,
        legend_eng_format: bool = True,
        show_legend: bool = True,
        fig_size: tuple[int, int] | None = None,
        save_fig: str = "",
        return_result: bool = False,
    ) -> tuple | None:
        """
        Plot computed x, y, and optionally y2 expressions, filtering by the secondary sweep variable.

        If y2_expression is provided, a twin y-axis plot is created.

        Parameters:
            x_expression: Expression for x-axis computation.
            y_expression: Expression for primary y-axis computation.
            y2_expression: Optional expression for secondary y-axis computation.
            filtered_values: Values to filter the secondary sweep variable.
            x_limit: Limits for the x-axis.
            y_limit: Limits for the primary y-axis.
            y2_limit: Limits for the secondary y-axis.
            x_scale: Scale type for the x-axis.
            y_scale: Scale type for the primary y-axis.
            y2_scale: Scale type for the secondary y-axis.
            x_eng_format: If True, format the x-axis in engineering units.
            y_eng_format: If True, format the primary y-axis in engineering units.
            y2_eng_format: If True, format the secondary y-axis in engineering units.
            legend_placement: Position of the legend (e.g., 'best', 'right', 'top', 'bottom').
            legend_location: Manual coordinates for legend placement as (x, y) tuple.
            legend_eng_format: If True, format legend values in engineering units.
            save_fig: Filename to save the figure.
            return_result: If True, return the computed arrays.

        Returns:
            A tuple (x, y, y2) if y2_expression is provided; otherwise, (x, y) when return_result is True.
        """
        filter_var = self.secondary_var if self.secondary_var is not None else "length"
        sec_values = self.filtered_variables[filter_var]
        if filtered_values is not None:
            if isinstance(filtered_values, (list, np.ndarray)):
                indices = np.nonzero(np.isin(sec_values, np.array(filtered_values)))[0]
            else:
                indices = np.array([np.abs(sec_values - filtered_values).argmin()])
        else:
            indices = np.arange(len(sec_values))

        legend = list(np.array(sec_values)[indices])
        x, x_label = self.calculate_from_expression(x_expression, indices)
        y, y_label = self.calculate_from_expression(y_expression, indices)
        if y2_expression is not None:
            y2, y2_label = self.calculate_from_expression(y2_expression, indices)
        else:
            y2, y2_label = None, ""

        return self._render_plot(
            x=x,
            y=y,
            x_label=x_label,
            y_label=y_label,
            y2=y2,
            y2_label=y2_label,
            legend=legend,
            legend_title=_LEGEND_TITLE.get(filter_var, filter_var),
            x_limit=x_limit,
            y_limit=y_limit,
            y2_limit=y2_limit,
            x_scale=x_scale,
            y_scale=y_scale,
            y2_scale=y2_scale,
            x_eng_format=x_eng_format,
            y_eng_format=y_eng_format,
            y2_eng_format=y2_eng_format,
            legend_placement=legend_placement,
            legend_location=legend_location,
            legend_eng_format=legend_eng_format,
            show_legend=show_legend,
            fig_size=fig_size,
            save_fig=save_fig,
            return_result=return_result,
        )

    def plot_by_sweep(
        self,
        *,
        x_expression: Expression,
        y_expression: Expression,
        y2_expression: Expression | None = None,
        primary: str,
        length: float | list[float] | np.ndarray | None = None,
        vbs: float | tuple[float, float] | tuple[float, float, float] | None = None,
        vgs: float | tuple[float, float] | tuple[float, float, float] | None = None,
        vds: float | tuple[float, float] | tuple[float, float, float] | None = None,
        x_limit: tuple[float, float] | None = None,
        y_limit: tuple[float, float] | None = None,
        y2_limit: tuple[float, float] | None = None,
        x_scale: str = "",
        y_scale: str = "",
        y2_scale: str = "",
        x_eng_format: bool = False,
        y_eng_format: bool = False,
        y2_eng_format: bool = False,
        legend_location: tuple[float, float] | None = None,
        legend_placement: str | None = None,
        legend_eng_format: bool = True,
        show_legend: bool = True,
        save_fig: str = "",
        fig_size: tuple[int, int] | None = None,
        return_result: bool = False,
    ) -> tuple | None:
        """
        Plot computed x, y, and optionally y2 expressions for a sweep with fixed parameters.

        If y2_expression is provided, a twin y-axis plot is created.

        Parameters:
            x_expression: Expression for x-axis computation.
            y_expression: Expression for primary y-axis computation.
            y2_expression: Optional expression for secondary y-axis computation.
            primary: Primary sweep variable.
            length: Length value(s) to filter the lookup table.
            vbs: body-source voltage value(s) or range.
            vgs: Gate-source voltage value(s) or range.
            vds: Drain-source voltage value(s) or range.
            x_limit: Limits for the x-axis.
            y_limit: Limits for the primary y-axis.
            y2_limit: Limits for the secondary y-axis.
            x_scale: Scale type for the x-axis.
            y_scale: Scale type for the primary y-axis.
            y2_scale: Scale type for the secondary y-axis.
            x_eng_format: If True, format the x-axis in engineering units.
            y_eng_format: If True, format the primary y-axis in engineering units.
            y2_eng_format: If True, format the secondary y-axis in engineering units.
            legend_placement: Position of the legend (e.g., 'best', 'right', 'top', 'bottom').
            legend_location: Manual coordinates for legend placement as (x, y) tuple.
            legend_eng_format: If True, format legend values in engineering units.
            save_fig: Filename to save the figure.
            return_result: If True, return the computed arrays.

        Returns:
            A tuple (x, y, y2) if y2_expression is provided; otherwise, (x, y) when return_result is True.
        """
        secondary_var, filtered_vars, extracted_table = extract_2d_table(
            lookup_table=self.lookup_table,
            length=length,
            vbs=vbs,
            vgs=vgs,
            vds=vds,
            primary=primary,
        )
        x, x_label = evaluate_expression(x_expression, extracted_table)
        y, y_label = evaluate_expression(y_expression, extracted_table)
        if y2_expression is not None:
            y2, y2_label = evaluate_expression(y2_expression, extracted_table)
        else:
            y2, y2_label = None, ""

        if secondary_var is not None:
            legend: list | None = list(filtered_vars[secondary_var])
            legend_title: str | None = _LEGEND_TITLE.get(secondary_var, secondary_var)
        else:
            legend, legend_title = None, None

        return self._render_plot(
            x=x,
            y=y,
            x_label=x_label,
            y_label=y_label,
            y2=y2,
            y2_label=y2_label,
            legend=legend,
            legend_title=legend_title,
            x_limit=x_limit,
            y_limit=y_limit,
            y2_limit=y2_limit,
            x_scale=x_scale,
            y_scale=y_scale,
            y2_scale=y2_scale,
            x_eng_format=x_eng_format,
            y_eng_format=y_eng_format,
            y2_eng_format=y2_eng_format,
            legend_placement=legend_placement,
            legend_location=legend_location,
            legend_eng_format=legend_eng_format,
            show_legend=show_legend,
            fig_size=fig_size,
            save_fig=save_fig,
            return_result=return_result,
        )

    def quick_plot(
        self,
        *,
        x: np.ndarray | list[np.ndarray],
        y: np.ndarray | list[np.ndarray],
        x_label: str = "",
        y_label: str = "",
        x_limit: tuple[float, float] | None = None,
        y_limit: tuple[float, float] | None = None,
        x_scale: str = "",
        y_scale: str = "",
        x_eng_format: bool = False,
        y_eng_format: bool = False,
        legend: list[str] | None = None,
        fig_size: tuple[int, int] | None = None,
        legend_title: str | None = "",
        legend_location: tuple[float, float] | None = None,
        legend_placement: str | None = None,
        legend_eng_format: bool = True,
        show_legend: bool = True,
        title: str | None = None,
        save_fig: str = "",
    ) -> None:
        """
        Quickly plot arbitrary x and y data (arrays or lists of arrays).

        Args:
            x: x-axis data as a numpy array or a list of numpy arrays.
            y: y-axis data as a numpy array or a list of numpy arrays.
            x_label: Label for the x-axis.
            y_label: Label for the y-axis.
            x_limit: Optional x-axis limits.
            y_limit: Optional y-axis limits.
            x_scale: Optional x-axis scale type.
            y_scale: Optional y-axis scale type.
            x_eng_format: If True, format x-axis labels in engineering units.
            y_eng_format: If True, format y-axis labels in engineering units.
            legend: Optional list of legend entries.
            legend_placement: Position of the legend.
            legend_location: Manual coordinates for legend placement as (x, y) tuple.
            legend_eng_format: If True, format legend values in engineering units.
            title: Optional title for the plot.
            save_fig: Optional filename to save the figure.
        """
        plotter = Plotter(fig_size=fig_size, show_legend=show_legend)
        _, ax = plotter.create_figure(
            title=title or "",
            x_label=x_label,
            y_label=y_label,
            x_lim=x_limit,
            y_lim=y_limit,
            x_scale=x_scale,
            y_scale=y_scale,
            x_eng_format=x_eng_format,
            y_eng_format=y_eng_format,
        )
        plotter.plot_data(
            ax,
            x,
            y,
            legend=legend,
            legend_title=legend_title,
            legend_placement=legend_placement,
            legend_eng_format=legend_eng_format,
            bbox_to_anchor=legend_location,
            save_fig=save_fig,
        )

    def interpolate(
        self,
        *,
        x_expression: Expression,
        x_value: float | tuple[float, ...] | np.ndarray,
        y_expression: Expression,
        y_value: float | tuple[float, ...] | np.ndarray,
        z_expression: Expression | list[Expression],
    ) -> np.ndarray | list[np.ndarray]:
        """
        Interpolate z values given x and y expressions using cubic griddata.

        The x and y expressions define the two axes of a scattered-data surface built
        from every point in the extracted table. The interpolator finds where that surface
        evaluates to z at the queried (x_value, y_value); no data is discarded.

        Args:
            x_expression: Expression for the x-axis of the interpolation surface.
            x_value: Query value(s) for the x-axis.
            y_expression: Expression for the y-axis of the interpolation surface.
            y_value: Query value(s) for the y-axis.
            z_expression: Expression or list of expressions to interpolate.

        Returns:
            A single interpolated array if z_expression is a single Expression,
            or a list of arrays if a list is provided.
        """
        return GridInterpolator(self.extracted_table, x_expression, y_expression).interpolate(
            x_value, y_value, z_expression
        )

    def lookup_expression_from_table(
        self,
        *,
        length: float | list[float] | np.ndarray,
        vbs: float | tuple[float, float, float],
        vgs: float | tuple[float, float, float],
        vds: float | tuple[float, float, float],
        primary: str,
        expression: Expression | list[Expression],
    ) -> np.ndarray | list[np.ndarray]:
        """
        Evaluate one or more expressions directly on the lookup table without interpolation.

        Args:
            length: The MOSFET length to filter the table.
            vbs: The body-source voltage parameter.
            vgs: The gate-source voltage parameter.
            vds: The drain-source voltage parameter.
            primary: The primary sweep variable.
            expression: A single Expression or a list of Expressions to evaluate.

        Returns:
            A numpy array if a single Expression is provided, or a list of numpy arrays
            if multiple Expressions are provided.
        """
        _, _, extracted_table = extract_2d_table(
            lookup_table=self.lookup_table,
            length=length,
            vbs=vbs,
            vgs=vgs,
            vds=vds,
            primary=primary,
        )
        if isinstance(expression, list):
            return [
                evaluate_expression(e, extracted_table)[0]
                for e in cast(list[Expression], expression)
            ]
        return evaluate_expression(expression, extracted_table)[0]
