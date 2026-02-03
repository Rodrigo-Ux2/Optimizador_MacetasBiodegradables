"""Bottleneck detection heuristics."""

from __future__ import annotations

from typing import Optional

from .model import Config
from .optimizer import OptimizationResult


def detect_bottleneck(config: Config, result: OptimizationResult) -> Optional[str]:
    """Return a single bottleneck label or None if not identifiable."""
    tol = 1e-6

    if result.mode == "minimize_time" and result.T_req is not None:
        if config.a * result.Q > config.M + tol:
            return "materia prima"
        t_p = result.Q * config.t_p / max(result.x_p, 1)
        t_m = result.Q * config.t_m / max(result.x_m, 1)
        t_o = result.Q * config.t_c / max(result.x_o, 1)
        if abs(result.T_req - t_p) <= tol:
            return "pesado"
        if abs(result.T_req - t_m) <= tol:
            return "mezcla"
        if abs(result.T_req - t_o) <= tol:
            return "moldes"
        if (result.x_p + result.x_m + 2 * result.x_o) == config.P:
            return "personal"
        return None

    # maximize_Q or fallback
    q_cont = result.Q_continuous
    if q_cont == 0:
        if (result.x_p + result.x_m + 2 * result.x_o) == config.P and config.P > 0:
            return "personal"
        return None

    lim_material = config.M / config.a
    lim_p = (config.T / config.t_p) * result.x_p
    lim_m = (config.T / config.t_m) * result.x_m
    lim_o = (config.T / config.t_c) * result.x_o

    if abs(q_cont - lim_material) <= tol:
        return "materia prima"

    if _is_coupling_tight(config, result) and (
        abs(q_cont - lim_p) <= tol or abs(q_cont - lim_m) <= tol
    ):
        return "acoplamiento"

    if abs(q_cont - lim_p) <= tol:
        return "pesado"
    if abs(q_cont - lim_m) <= tol:
        return "mezcla"
    if abs(q_cont - lim_o) <= tol:
        return "moldes"

    if (result.x_p + result.x_m + 2 * result.x_o) == config.P:
        return "personal"

    return None


def _is_coupling_tight(config: Config, result: OptimizationResult) -> bool:
    if not config.coupling:
        return False
    if result.x_p == 0 or result.x_m == 0 or result.x_o == 0:
        return False
    rate_p = result.x_p / config.t_p
    rate_m = result.x_m / config.t_m
    rate_o = result.x_o / config.t_c
    tol = 1e-6
    return abs(rate_p - rate_m) <= tol or abs(rate_m - rate_o) <= tol
