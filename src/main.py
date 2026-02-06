"""CLI entry point."""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict

from .bottleneck import detect_bottleneck
from .model import Config
from .optimizer import constraint_checks, optimize
from .simulate import simulate


def main() -> None:
    parser = argparse.ArgumentParser(description="Biodegradable pot production optimizer")
    parser.add_argument("--config", required=True, help="Path to config JSON")
    args = parser.parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        data = json.load(f)

    config = Config.from_dict(data)
    config.validate()

    result = optimize(config)
    bottleneck = detect_bottleneck(config, result)
    checks = constraint_checks(config, result)

    output: Dict[str, Any] = {
        "mode": result.mode,
        "status": result.status,
        "equipos": {"x_p": result.x_p, "x_m": result.x_m, "x_o": result.x_o},
        "Q": result.Q,
        "Q_continuous": result.Q_continuous,
        "T_req": result.T_req,
        "T_max": config.T_max if config.T_max is not None else config.T,
        "bottleneck": bottleneck,
        "checks": checks,
        "notes": result.notes,
    }

    if config.simulation_on and result.Q > 0:
        sim = simulate(config, result.x_p, result.x_m, result.x_o, result.Q)
        output["simulation"] = {
            "makespan": sim.makespan,
            "utilization": sim.utilization,
            "queue_stats": sim.queue_stats,
            "wip_stats": sim.wip_stats,
            "mix_to_mold_stats": sim.mix_to_mold_stats,
        }
        if config.simulation_save_schedule:
            output["simulation"]["items"] = [
                {
                    "id": item.item_id,
                    "pesado": _stage_dict(item.pesado),
                    "mezcla": _stage_dict(item.mezcla),
                    "moldes": _stage_dict(item.moldes),
                }
                for item in sim.items
            ]

    print_summary(output)
    with open(config.output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=True)


def _stage_dict(stage) -> Dict[str, Any]:
    if stage is None:
        return {}
    return {"start": stage.start, "end": stage.end, "wait": stage.wait}


def print_summary(output: Dict[str, Any]) -> None:
    print("=== RESULTADO ===")
    print(f"Modo: {output['mode']} (status: {output['status']})")
    equipos = output["equipos"]
    print(f"Equipos: balanzas={equipos['x_p']}, bowls={equipos['x_m']}, moldes={equipos['x_o']}")
    print(f"Produccion Q: {output['Q']} (Q continuo: {output['Q_continuous']:.2f})")
    if output["T_req"] is not None:
        print(f"Tiempo requerido: {output['T_req']:.2f} min")
    if output.get("T_max") is not None:
        print(f"T_max: {output['T_max']:.2f} min")
    print(f"Cuello de botella: {output['bottleneck']}")
    print(f"Restricciones: {output['checks']}")
    if output.get("notes"):
        print(f"Notas: {output['notes']}")


if __name__ == "__main__":
    main()
