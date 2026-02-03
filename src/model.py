"""Data models and validation for the biodegradable pot production system."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class Config:
    """Configuration parameters for the optimization/simulation."""

    mode: str  # "maximize_Q" or "minimize_time"

    # Global resources
    T: float  # available time in minutes (also T_max for minimize_time if T_max not set)
    P: int  # available people
    M: float  # available material in grams
    T_max: Optional[float] = None

    # Per-pot material
    a: float = 155.0

    # Average times (min per pot)
    t_p: float = 1.25
    t_m: float = 2.4
    t_c: float = 8.5

    # Optional equipment limits
    L_p_min: Optional[int] = None
    L_p_max: Optional[int] = None
    L_m_min: Optional[int] = None
    L_m_max: Optional[int] = None
    L_o_min: Optional[int] = None
    L_o_max: Optional[int] = None

    # Objective-specific
    Q_obj: Optional[int] = None

    # Flags
    coupling: bool = True
    simulation_on: bool = False
    simulation_save_schedule: bool = False

    # Output
    output_path: str = "results.json"

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Config":
        """Create Config from a dict with defaults."""
        t_value = float(data.get("T", data.get("T_max", 0.0)))
        return Config(
            mode=data.get("mode", "maximize_Q"),
            T=t_value,
            T_max=_none_or_float(data.get("T_max")),
            P=int(data.get("P", 0)),
            M=float(data.get("M", 0.0)),
            a=float(data.get("a", 155.0)),
            t_p=float(data.get("t_p", 1.25)),
            t_m=float(data.get("t_m", 2.4)),
            t_c=float(data.get("t_c", 8.5)),
            L_p_min=_none_or_int(data.get("L_p_min")),
            L_p_max=_none_or_int(data.get("L_p_max", data.get("L_p"))),
            L_m_min=_none_or_int(data.get("L_m_min")),
            L_m_max=_none_or_int(data.get("L_m_max", data.get("L_m"))),
            L_o_min=_none_or_int(data.get("L_o_min")),
            L_o_max=_none_or_int(data.get("L_o_max", data.get("L_o"))),
            Q_obj=_none_or_int(data.get("Q_obj")),
            coupling=False,
            simulation_on=bool(data.get("simulation_on", False)),
            simulation_save_schedule=bool(data.get("simulation_save_schedule", False)),
            output_path=str(data.get("output_path", "results.json")),
        )

    def validate(self) -> None:
        """Raise ValueError if configuration is invalid."""
        if self.mode not in {"maximize_Q", "minimize_time"}:
            raise ValueError("mode must be 'maximize_Q' or 'minimize_time'")
        if self.T < 0:
            raise ValueError("T must be >= 0")
        if self.P < 0:
            raise ValueError("P must be >= 0")
        if self.M < 0:
            raise ValueError("M must be >= 0")
        if self.a <= 0:
            raise ValueError("a must be > 0")
        if self.t_p <= 0 or self.t_m <= 0 or self.t_c <= 0:
            raise ValueError("t_p, t_m, t_c must be > 0")
        for name, val in (
            ("L_p_min", self.L_p_min),
            ("L_p_max", self.L_p_max),
            ("L_m_min", self.L_m_min),
            ("L_m_max", self.L_m_max),
            ("L_o_min", self.L_o_min),
            ("L_o_max", self.L_o_max),
        ):
            if val is not None and val < 0:
                raise ValueError(f"{name} must be None or >= 0")
        if (
            self.L_p_min is not None
            and self.L_p_max is not None
            and self.L_p_min > self.L_p_max
        ):
            raise ValueError("L_p_min must be <= L_p_max")
        if (
            self.L_m_min is not None
            and self.L_m_max is not None
            and self.L_m_min > self.L_m_max
        ):
            raise ValueError("L_m_min must be <= L_m_max")
        if (
            self.L_o_min is not None
            and self.L_o_max is not None
            and self.L_o_min > self.L_o_max
        ):
            raise ValueError("L_o_min must be <= L_o_max")
        if self.mode == "minimize_time":
            if self.Q_obj is None or self.Q_obj < 0:
                raise ValueError("Q_obj must be provided and >= 0 in minimize_time")
            if self.T_max is None:
                self._validate_t_max_from_t()
            if self.T_max is not None and self.T_max < 0:
                raise ValueError("T_max must be >= 0")

    def _validate_t_max_from_t(self) -> None:
        object.__setattr__(self, "T_max", self.T)

    def derived_limits(self) -> Dict[str, int]:
        """Return practical upper bounds for equipment counts."""
        max_p = min(self.L_p_max if self.L_p_max is not None else self.P, self.P)
        max_m = min(self.L_m_max if self.L_m_max is not None else self.P, self.P)
        max_o = min(
            self.L_o_max if self.L_o_max is not None else self.P // 2,
            self.P // 2,
        )
        max_p = max(max_p, 0)
        max_m = max(max_m, 0)
        max_o = max(max_o, 0)
        min_p = max(self.L_p_min if self.L_p_min is not None else 0, 0)
        min_m = max(self.L_m_min if self.L_m_min is not None else 0, 0)
        min_o = max(self.L_o_min if self.L_o_min is not None else 0, 0)
        return {
            "min_p": min_p,
            "min_m": min_m,
            "min_o": min_o,
            "max_p": max_p,
            "max_m": max_m,
            "max_o": max_o,
        }


def _none_or_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    return int(value)


def _none_or_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    return float(value)
