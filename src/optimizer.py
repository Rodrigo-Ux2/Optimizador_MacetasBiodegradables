"""Discrete enumeration optimizer for equipment sizing."""

from __future__ import annotations

from dataclasses import dataclass
from math import floor
from typing import Dict, Optional, Tuple

from .model import Config


@dataclass(frozen=True)
class OptimizationResult:
    mode: str
    status: str  # "ok" or "fallback"
    x_p: int
    x_m: int
    x_o: int
    Q: int
    Q_continuous: float
    T_req: Optional[float]
    notes: Optional[str] = None


def optimize(config: Config) -> OptimizationResult:
    """Dispatch to the selected optimization mode."""
    if config.mode == "maximize_Q":
        return _maximize_q(config)
    return _minimize_time(config)


def _maximize_q(config: Config) -> OptimizationResult:
    limits = config.derived_limits()
    min_p = limits["min_p"]
    min_m = limits["min_m"]
    min_o = limits["min_o"]
    max_p = limits["max_p"]
    max_m = limits["max_m"]
    max_o = limits["max_o"]

    best: Optional[Tuple[int, int, int, int, float]] = None
    # tuple: (Q_int, x_p, x_m, x_o, Q_cont)

    for x_o in range(min_o, max_o + 1):
        for x_p in range(min_p, max_p + 1):
            for x_m in range(min_m, max_m + 1):
                if x_p + x_m + 2 * x_o > config.P:
                    continue
                if not _coupling_ok(config, x_p, x_m, x_o):
                    continue
                q_cont = _q_continuous(config, x_p, x_m, x_o)
                q_int = floor(q_cont)
                if best is None:
                    best = (q_int, x_p, x_m, x_o, q_cont)
                    continue
                if q_int > best[0]:
                    best = (q_int, x_p, x_m, x_o, q_cont)
                elif q_int == best[0]:
                    if (x_p + x_m + x_o) < (best[1] + best[2] + best[3]):
                        best = (q_int, x_p, x_m, x_o, q_cont)

    if best is None:
        return OptimizationResult(
            mode="maximize_Q",
            status="fallback",
            x_p=0,
            x_m=0,
            x_o=0,
            Q=0,
            Q_continuous=0.0,
            T_req=None,
            notes="No feasible solution found; returning zero production.",
        )

    q_int, x_p, x_m, x_o, q_cont = best
    return OptimizationResult(
        mode="maximize_Q",
        status="ok",
        x_p=x_p,
        x_m=x_m,
        x_o=x_o,
        Q=q_int,
        Q_continuous=q_cont,
        T_req=None,
    )


def _minimize_time(config: Config) -> OptimizationResult:
    limits = config.derived_limits()
    min_p = limits["min_p"]
    min_m = limits["min_m"]
    min_o = limits["min_o"]
    max_p = limits["max_p"]
    max_m = limits["max_m"]
    max_o = limits["max_o"]

    q_obj = int(config.Q_obj or 0)
    if q_obj == 0:
        return OptimizationResult(
            mode="minimize_time",
            status="ok",
            x_p=0,
            x_m=0,
            x_o=0,
            Q=0,
            Q_continuous=0.0,
            T_req=0.0,
            notes="Q_obj is 0; no production required.",
        )

    if config.M < config.a * q_obj:
        fallback = _maximize_q(config)
        q_possible = fallback.Q
        if q_possible == 0:
            return OptimizationResult(
                mode="minimize_time",
                status="material_limited",
                x_p=fallback.x_p,
                x_m=fallback.x_m,
                x_o=fallback.x_o,
                Q=0,
                Q_continuous=0.0,
                T_req=0.0,
                notes="Materia prima insuficiente para Q_obj; produccion posible = 0.",
            )
        best = _best_time_for_q(config, q_possible, min_p, min_m, min_o, max_p, max_m, max_o)
        if best is None:
            return OptimizationResult(
                mode="minimize_time",
                status="material_limited",
                x_p=fallback.x_p,
                x_m=fallback.x_m,
                x_o=fallback.x_o,
                Q=q_possible,
                Q_continuous=float(q_possible),
                T_req=None,
                notes="Materia prima insuficiente para Q_obj; no se encontro combinacion para minimizar tiempo.",
            )
        t_req, x_p, x_m, x_o, _eq_sum = best
        return OptimizationResult(
            mode="minimize_time",
            status="material_limited",
            x_p=x_p,
            x_m=x_m,
            x_o=x_o,
            Q=q_possible,
            Q_continuous=float(q_possible),
            T_req=t_req,
            notes="Materia prima insuficiente para Q_obj; se optimiza tiempo para Q_max posible.",
        )

    best = _best_time_for_q(config, q_obj, min_p, min_m, min_o, max_p, max_m, max_o)

    if best is None:
        fallback = _maximize_q(config)
        return OptimizationResult(
            mode="minimize_time",
            status="fallback",
            x_p=fallback.x_p,
            x_m=fallback.x_m,
            x_o=fallback.x_o,
            Q=fallback.Q,
            Q_continuous=fallback.Q_continuous,
            T_req=None,
            notes="No feasible equipment combination found; returning max production in T.",
        )

    t_req, x_p, x_m, x_o, _eq_sum = best
    t_max = config.T_max if config.T_max is not None else config.T
    if t_req <= t_max:
        return OptimizationResult(
            mode="minimize_time",
            status="ok",
            x_p=x_p,
            x_m=x_m,
            x_o=x_o,
            Q=q_obj,
            Q_continuous=float(q_obj),
            T_req=t_req,
        )

    return OptimizationResult(
        mode="minimize_time",
        status="infeasible",
        x_p=x_p,
        x_m=x_m,
        x_o=x_o,
        Q=q_obj,
        Q_continuous=float(q_obj),
        T_req=t_req,
        notes="No es posible cumplir Q_obj dentro de T_max; se devuelve la mejor configuracion de tiempo.",
    )


def _best_time_for_q(
    config: Config,
    q_target: int,
    min_p: int,
    min_m: int,
    min_o: int,
    max_p: int,
    max_m: int,
    max_o: int,
) -> Optional[Tuple[float, int, int, int, int]]:
    if q_target <= 0:
        return (0.0, 0, 0, 0, 0)

    best: Optional[Tuple[float, int, int, int, int]] = None
    min_p_eff = max(min_p, 1)
    min_m_eff = max(min_m, 1)
    min_o_eff = max(min_o, 1)
    for x_o in range(min_o_eff, max_o + 1):
        for x_p in range(min_p_eff, max_p + 1):
            for x_m in range(min_m_eff, max_m + 1):
                if x_p + x_m + 2 * x_o > config.P:
                    continue
                if not _coupling_ok(config, x_p, x_m, x_o):
                    continue
                if not _gel_ok(config, x_p, x_m, x_o, q_target):
                    continue
                t_req = max(
                    q_target * config.t_p / x_p,
                    q_target * config.t_m / x_m,
                    q_target * config.t_c / x_o,
                )
                eq_sum = x_p + x_m + x_o
                if best is None:
                    best = (t_req, x_p, x_m, x_o, eq_sum)
                elif t_req < best[0]:
                    best = (t_req, x_p, x_m, x_o, eq_sum)
                elif abs(t_req - best[0]) <= 1e-9 and eq_sum < best[4]:
                    best = (t_req, x_p, x_m, x_o, eq_sum)
    return best


def _q_continuous(config: Config, x_p: int, x_m: int, x_o: int) -> float:
    if x_p == 0 or x_m == 0 or x_o == 0:
        return 0.0
    q_gel = _gel_q_limit(config, x_p, x_m, x_o)
    if q_gel is None or q_gel == float("inf"):
        q_gel = float("inf")
    return min(
        config.M / config.a,
        (config.T / config.t_p) * x_p,
        (config.T / config.t_m) * x_m,
        (config.T / config.t_c) * x_o,
        q_gel,
    )


def _coupling_ok(config: Config, x_p: int, x_m: int, x_o: int) -> bool:
    if not config.coupling:
        return True
    if x_p == 0 or x_m == 0 or x_o == 0:
        return x_p == 0 and x_m == 0 and x_o == 0
    rate_p = x_p / config.t_p
    rate_m = x_m / config.t_m
    rate_o = x_o / config.t_c
    return rate_p <= rate_m and rate_m <= rate_o


def _gel_q_limit(config: Config, x_p: int, x_m: int, x_o: int) -> Optional[float]:
    if config.t_gel_max is None:
        return None
    if config.t_gel_max < config.t_m:
        return 0.0
    return float("inf")


def _gel_ok(config: Config, x_p: int, x_m: int, x_o: int, q_target: int) -> bool:
    if config.t_gel_max is None:
        return True
    return config.t_gel_max + 1e-9 >= config.t_m


def constraint_checks(config: Config, result: OptimizationResult) -> Dict[str, bool]:
    """Return boolean checks for each major constraint."""
    x_p, x_m, x_o = result.x_p, result.x_m, result.x_o
    t_limit = config.T_max if config.T_max is not None else config.T
    limits = config.derived_limits()
    checks = {
        "material": config.a * result.Q <= config.M + 1e-9,
        "time_pesado": result.Q <= (t_limit / config.t_p) * x_p + 1e-9,
        "time_mezcla": result.Q <= (t_limit / config.t_m) * x_m + 1e-9,
        "time_moldes": result.Q <= (t_limit / config.t_c) * x_o + 1e-9,
        "personal": (x_p + x_m + 2 * x_o) <= config.P,
        "acoplamiento": _coupling_ok(config, x_p, x_m, x_o),
        "min_p": x_p >= limits["min_p"],
        "min_m": x_m >= limits["min_m"],
        "min_o": x_o >= limits["min_o"],
    }
    if config.t_gel_max is not None:
        checks["gelificacion"] = config.t_gel_max + 1e-9 >= config.t_m
    return checks
