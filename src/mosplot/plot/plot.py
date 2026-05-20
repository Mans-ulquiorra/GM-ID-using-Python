# imports <<<
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.ticker import EngFormatter
# >>>


class Plotter:
    def __init__(
        self,
        fig_size: tuple[int, int] | None = (8, 4),
        line_width: float = 1.5,
        grid_color: str = "0.9",
        show_legend: bool = True,
    ) -> None:
        self.fig_size = fig_size
        self.line_width = line_width
        self.grid_color = grid_color
        self.show_legend = show_legend

    # legend helpers <<<
    def _estimate_char_inch(self, fig: Figure) -> float:
        dpi = fig.dpi
        font_pt = plt.rcParams["font.size"]
        avg_char_px = font_pt * 0.5
        return avg_char_px / dpi

    def _get_legend_ncols(
        self, labels: list[str], fig: object, legend_placement: str | None
    ) -> int:
        if not isinstance(fig, Figure):
            return 1
        legend_len = len("".join(labels))
        char_inch = self._estimate_char_inch(fig)
        if legend_placement in ("bottom", "top"):
            symbol_inch = 0.15
            legend_width = legend_len * (char_inch + symbol_inch)
            fig_w = fig.get_size_inches()[0]
            nrow = int(np.ceil(legend_width / fig_w))
            ncol = int(np.ceil(len(labels) / nrow))
            return min(ncol, len(labels))
        else:
            legend_width = legend_len * char_inch
            fig_h = fig.get_size_inches()[1]
            ncol = int(np.ceil(legend_width / fig_h))
            return max(ncol, 1)
    # >>>

    # single axis plot <<<
    def create_figure(
        self,
        title: str = "",
        x_label: str = "",
        y_label: str = "",
        x_lim: tuple[float, float] | None = None,
        y_lim: tuple[float, float] | None = None,
        x_scale: str = "",
        y_scale: str = "",
        x_eng_format: bool = False,
        y_eng_format: bool = False,
    ) -> tuple[Figure, Axes]:
        fig, ax = plt.subplots(figsize=self.fig_size, tight_layout=True)
        ax.set_title(title)
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        ax.grid(True, which="major", ls="--", color=self.grid_color)
        if x_lim is not None:
            ax.set_xlim(*x_lim)
        if y_lim is not None:
            ax.set_ylim(*y_lim)
        if x_scale:
            ax.set_xscale(x_scale)
        if y_scale:
            ax.set_yscale(y_scale)
        if x_eng_format:
            ax.xaxis.set_major_formatter(EngFormatter(unit=""))
        if y_eng_format:
            ax.yaxis.set_major_formatter(EngFormatter(unit=""))
        return fig, ax
    # >>>

    # two axis plot <<<
    def create_figure_with_twin(
        self,
        title: str = "",
        x_label: str = "",
        y_label: str = "",
        y2_label: str = "",
        x_lim: tuple[float, float] | None = None,
        y_lim: tuple[float, float] | None = None,
        y2_lim: tuple[float, float] | None = None,
        x_scale: str = "",
        y_scale: str = "",
        y2_scale: str = "",
        x_eng_format: bool = False,
        y_eng_format: bool = False,
        y2_eng_format: bool = False,
    ) -> tuple[Figure, Axes, Axes]:
        fig, ax = self.create_figure(
            title=title, x_label=x_label, y_label=y_label,
            x_lim=x_lim, y_lim=y_lim,
            x_scale=x_scale, y_scale=y_scale,
            x_eng_format=x_eng_format, y_eng_format=y_eng_format,
        )
        ax2 = ax.twinx()
        ax2.set_ylabel(y2_label)
        if y2_lim is not None:
            ax2.set_ylim(*y2_lim)
        if y2_scale:
            ax2.set_yscale(y2_scale)
        if y2_eng_format:
            ax2.yaxis.set_major_formatter(EngFormatter(unit=""))
        return fig, ax, ax2
    # >>>

    # plot data <<<
    def plot_data(
        self,
        ax: Axes,
        x: np.ndarray | list[np.ndarray],
        y: np.ndarray | list[np.ndarray],
        line_style: str | None = "solid",
        legend: np.ndarray | list | None = None,
        legend_title: str | None = None,
        legend_placement: str | None = "right",
        legend_eng_format: bool = True,
        bbox_to_anchor: tuple[float, float] | None = None,
        save_fig: str = "",
        end_plotting: bool = True,
    ) -> None:
        if isinstance(x, np.ndarray) and isinstance(y, np.ndarray):
            if x.ndim > 1 and y.ndim > 1:
                ax.plot(x.T, y.T, lw=self.line_width, ls=line_style, picker=True)
            else:
                ax.plot(x, y, lw=self.line_width, ls=line_style, picker=True)
        elif isinstance(x, (list, tuple)) and isinstance(y, (list, tuple)):
            for x_item, y_item in zip(x, y):
                if isinstance(x_item, np.ndarray) and isinstance(y_item, np.ndarray):
                    if x_item.ndim > 1 and y_item.ndim > 1:
                        ax.plot(x_item.T, y_item.T, lw=self.line_width, ls=line_style, picker=True)
                    else:
                        ax.plot(x_item, y_item, lw=self.line_width, ls=line_style, picker=True)
                else:
                    ax.plot(np.asarray(x_item), np.asarray(y_item), lw=self.line_width, ls=line_style, picker=True)
        else:
            ax.plot(np.asarray(x), np.asarray(y), lw=self.line_width, ls=line_style, picker=True)

        if end_plotting:
            fig = ax.get_figure()
            if legend is not None and self.show_legend and len(legend) > 0:
                if legend_eng_format and isinstance(legend[0], (int, float, np.number)):
                    formatter = EngFormatter(unit="")
                    formatted_legend = [formatter(val) for val in legend]
                else:
                    formatted_legend = [str(val) for val in legend]
                ncol = self._get_legend_ncols(formatted_legend, fig, legend_placement)
                if legend_placement == "bottom":
                    anchor = (0.5, -0.25) if bbox_to_anchor is None else bbox_to_anchor
                    leg = ax.legend(formatted_legend, loc="upper center", bbox_to_anchor=anchor, ncol=ncol, title=legend_title)
                elif legend_placement == "top":
                    anchor = (0.5, 1.05) if bbox_to_anchor is None else bbox_to_anchor
                    leg = ax.legend(formatted_legend, loc="lower center", bbox_to_anchor=anchor, ncol=ncol, title=legend_title)
                elif legend_placement == "best":
                    leg = ax.legend(formatted_legend, loc="best", ncol=ncol, title=legend_title)
                else:
                    anchor = (1, 0.5) if bbox_to_anchor is None else bbox_to_anchor
                    leg = ax.legend(formatted_legend, loc="center left", bbox_to_anchor=anchor, ncol=ncol, title=legend_title)
                leg.get_title().set_fontsize("large")

            ax.minorticks_off()

            if save_fig and isinstance(fig, Figure):
                fig.savefig(save_fig, bbox_inches="tight")

            plt.show()
    # >>>
