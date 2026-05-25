from __future__ import annotations

from pathlib import Path
from typing import Any
import numpy as np
import numpy.typing as npt
import cma
from scipy.optimize import OptimizeResult, minimize
from .datatypes import OptimizationParameter, Spec
from .netlist.base import NetlistGenerator


# Guard threshold: for x > _SOFTPLUS_LIN_THRESHOLD the function is linear (avoids exp overflow).
_SOFTPLUS_LIN_THRESHOLD = 20.0


def _softplus(x: float, beta: float = 20.0) -> float:
    """Smooth, differentiable approximation of max(0, x)."""
    if x > _SOFTPLUS_LIN_THRESHOLD / beta:
        return x
    return float(np.log1p(np.exp(beta * x)) / beta)


class Optimizer:
    """Optimizes a circuit design using CMA-ES followed by SLSQP polishing."""

    def __init__(
        self,
        circuit: Any,
        parameters: list[OptimizationParameter],
        target_specs: dict[str, Spec],
    ) -> None:
        self.circuit = circuit
        self.parameters = parameters
        self.target_specs = target_specs
        self.opt_params: dict[str, float] | None = None
        self.result: OptimizeResult | None = None

    def compute_cost(self, specs: dict[str, float]) -> float:
        """
        Scalar cost for a given set of circuit specs against the targets.

        "max" specs use log-scale normalisation so that large violations
        (e.g. CMRR 10x below target) produce proportionally larger gradients
        than a linearisation would. "min" specs use linear normalisation,
        which is appropriate for quantities that vary by small factors, and
        include a secondary term that keeps cost non-zero when satisfied so
        the optimizer continues driving them down. "eq" specs use squared
        relative error, penalising deviation from the target in both directions.
        """
        cost = 0.0
        for key, spec in self.target_specs.items():
            actual = specs[key]
            target = spec.target

            if spec.mode == "min":
                raw = (actual - target) / target
                violation = _softplus(raw)
                secondary = max(0.0, actual / target)
                cost += spec.weight * (violation**2 + 0.05 * secondary)

            elif spec.mode == "max":
                ratio = target / actual if actual > 0 else np.inf
                raw = float(np.log(ratio)) if np.isfinite(ratio) else 100.0
                violation = _softplus(raw)
                cost += spec.weight * (violation**2)

            elif spec.mode == "eq":
                raw = (actual - target) / abs(target)
                cost += spec.weight * (raw**2)

        return cost

    def _transform_params(self, x: list[float] | npt.NDArray) -> dict[str, float]:
        params: dict[str, float] = {}
        for i, param in enumerate(self.parameters):
            bound = param.bound
            if isinstance(bound, (list, np.ndarray)):
                idx = max(0, min(int(round(x[i])), len(bound) - 1))
                params[param.name] = float(np.array(bound)[idx])
            else:
                params[param.name] = float(x[i])
        return params

    def _objective(self, x: list[float] | npt.NDArray) -> float:
        params = self._transform_params(x)
        try:
            specs = self.circuit.evaluate_specs(**params)
        except Exception:
            return 1e6
        return self.compute_cost(specs)

    def _get_bounds(self) -> list[tuple[float, float]]:
        bounds = []
        for param in self.parameters:
            bound = param.bound
            if isinstance(bound, (list, np.ndarray)):
                bounds.append((0, len(bound) - 1))
            else:
                bounds.append(bound)
        return bounds

    def _run_cma(
        self,
        x0_norm: npt.NDArray,
        lbs: npt.NDArray,
        ubs: npt.NDArray,
        maxiter: int,
        sigma0: float,
        seed: int,
    ) -> tuple[npt.NDArray, float, int]:
        n = len(lbs)

        def objective_normalised(x_norm: npt.NDArray) -> float:
            return self._objective(lbs + x_norm * (ubs - lbs))

        opts = cma.CMAOptions()
        opts["bounds"] = [[0.0] * n, [1.0] * n]
        opts["maxiter"] = maxiter
        opts["seed"] = seed

        # Show optimizer progress, but do not write CMA log/output folders
        opts["verb_log"] = 0
        opts["verbose"] = 1

        opts["tolx"] = 1e-5
        opts["tolfun"] = 1e-5

        es = cma.CMAEvolutionStrategy(x0_norm, sigma0, opts)
        es.optimize(objective_normalised)

        best_x = lbs + es.result.xbest * (ubs - lbs)
        return best_x, float(es.result.fbest), int(es.result.iterations)

    def optimize(
        self,
        maxiter: int = 500,
        sigma0: float = 0.3,
        n_restarts: int = 1,
        seed: int = 42,
    ) -> OptimizeResult:
        """
        Run CMA-ES (with optional random restarts) then polish with SLSQP.

        Args:
            maxiter: Maximum CMA-ES iterations per restart.
            sigma0: Initial step size as a fraction of the normalised [0, 1] search space.
            n_restarts: Number of independent CMA-ES runs. The first starts from the
                centre of the search space; subsequent ones from random points. Increase
                beyond 1 only if results are inconsistent across runs (multimodal landscape).
            seed: Base random seed; restart i uses seed + i for reproducibility.
        """
        bounds = self._get_bounds()
        lbs = np.array([b[0] for b in bounds], dtype=float)
        ubs = np.array([b[1] for b in bounds], dtype=float)
        rng = np.random.default_rng(seed)

        best_x: npt.NDArray = np.empty(len(bounds))
        best_cost = np.inf
        total_iters = 0

        for i in range(n_restarts):
            x0_norm = np.full(len(bounds), 0.5) if i == 0 else rng.uniform(0.1, 0.9, len(bounds))
            print(f"\n--- CMA-ES restart {i + 1}/{n_restarts} ---")
            x, cost, iters = self._run_cma(x0_norm, lbs, ubs, maxiter, sigma0, seed + i)
            total_iters += iters
            if cost < best_cost:
                best_cost = cost
                best_x = x

        print(f"\nBest CMA-ES cost across {n_restarts} restart(s): {best_cost:.6g}")
        print("Polishing with SLSQP...")

        polish = minimize(
            self._objective,
            best_x,
            method="SLSQP",
            bounds=bounds,
            options={"maxiter": 500, "ftol": 1e-9},
        )

        if polish.fun < best_cost:
            best_x, best_cost = polish.x, polish.fun
            print(f"SLSQP improved cost to {best_cost:.6g}")
        else:
            print("SLSQP did not improve on CMA-ES result.")

        self.opt_params = self._transform_params(best_x)
        self.result = OptimizeResult(
            x=best_x,
            fun=best_cost,
            success=True,
            message="CMA-ES + SLSQP optimization complete.",
            nit=total_iters,
        )
        return self.result

    def get_opt_params(self) -> dict[str, float]:
        if self.opt_params is None:
            raise ValueError("Optimization has not been performed yet.")
        return self.opt_params

    def generate(self, generator: NetlistGenerator, output_path: Path | str) -> Path:
        """Write a simulator netlist for the best found design.

        Calls evaluate_specs() once at the optimum to refresh device_dimensions
        and passive_params, then delegates to the given generator.
        """
        opt_params = self.get_opt_params()
        self.circuit.evaluate_specs(**opt_params)
        vsource_params = self.circuit.compute_vsource_params(opt_params)
        return generator.generate(
            mosfets=self.circuit.MOSFETS,
            passives=self.circuit.PASSIVES,
            vsources=self.circuit.VSOURCES,
            device_map=self.circuit.device_map,
            dimensions=self.circuit.device_dimensions,
            passive_params=self.circuit.passive_params,
            vsource_params=vsource_params,
            output_path=Path(output_path),
        )
