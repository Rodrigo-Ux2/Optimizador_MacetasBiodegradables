"""Discrete-event simulation for pot-by-pot flow."""

from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .model import Config


@dataclass
class StageRecord:
    start: float
    end: float
    wait: float


@dataclass
class ItemRecord:
    item_id: int
    arrival_p: float = 0.0
    arrival_m: Optional[float] = None
    arrival_o: Optional[float] = None
    pesado: Optional[StageRecord] = None
    mezcla: Optional[StageRecord] = None
    moldes: Optional[StageRecord] = None


@dataclass
class SimulationResult:
    makespan: float
    items: List[ItemRecord]
    utilization: Dict[str, float]
    queue_stats: Dict[str, Dict[str, float]]
    wip_stats: Dict[str, Dict[str, float]]
    wip_series: List[Tuple[float, int]]


def simulate(
    config: Config,
    x_p: int,
    x_m: int,
    x_o: int,
    Q_target: int,
) -> SimulationResult:
    """Simulate sequential stages with resource pools."""
    if Q_target <= 0:
        return SimulationResult(0.0, [], {}, {})

    now = 0.0
    items = [ItemRecord(item_id=i + 1) for i in range(Q_target)]
    queue_p = list(items)
    queue_m: List[ItemRecord] = []
    queue_o: List[ItemRecord] = []

    avail_p = x_p
    avail_m = x_m
    avail_o = x_o

    events: List[Tuple[float, int, str, ItemRecord]] = []
    seq = itertools.count()

    busy_time = {"pesado": 0.0, "mezcla": 0.0, "moldes": 0.0}
    waits = {"pesado": [], "mezcla": [], "moldes": []}
    wip_area = {"pesado": 0.0, "mezcla": 0.0, "moldes": 0.0, "system": 0.0}
    wip_max = {"pesado": 0, "mezcla": 0, "moldes": 0, "system": 0}
    completed = 0
    started = [0]
    last_time = 0.0
    wip_series: List[Tuple[float, int]] = []

    def try_start_pesado() -> None:
        nonlocal avail_p
        while avail_p > 0 and queue_p:
            item = queue_p.pop(0)
            start = now
            wait = 0.0
            end = start + config.t_p
            item.pesado = StageRecord(start=start, end=end, wait=wait)
            busy_time["pesado"] += config.t_p
            waits["pesado"].append(wait)
            avail_p -= 1
            started[0] += 1
            heapq.heappush(events, (end, next(seq), "pesado", item))

    def try_start_mezcla() -> None:
        nonlocal avail_m
        while avail_m > 0 and queue_m:
            item = queue_m.pop(0)
            start = now
            wait = start - (item.arrival_m if item.arrival_m is not None else start)
            end = start + config.t_m
            item.mezcla = StageRecord(start=start, end=end, wait=wait)
            busy_time["mezcla"] += config.t_m
            waits["mezcla"].append(wait)
            avail_m -= 1
            heapq.heappush(events, (end, next(seq), "mezcla", item))

    def try_start_moldes() -> None:
        nonlocal avail_o
        while avail_o > 0 and queue_o:
            item = queue_o.pop(0)
            start = now
            wait = start - (item.arrival_o if item.arrival_o is not None else start)
            end = start + config.t_c
            item.moldes = StageRecord(start=start, end=end, wait=wait)
            busy_time["moldes"] += config.t_c
            waits["moldes"].append(wait)
            avail_o -= 1
            heapq.heappush(events, (end, next(seq), "moldes", item))

    def current_wip() -> Dict[str, int]:
        in_p = (x_p - avail_p) + len(queue_p)
        in_m = (x_m - avail_m) + len(queue_m)
        in_o = (x_o - avail_o) + len(queue_o)
        # WIP in system considers only items that have started processing
        in_sys = max(started[0] - completed, 0)
        return {"pesado": in_p, "mezcla": in_m, "moldes": in_o, "system": in_sys}

    # Prime the system
    try_start_pesado()
    wip_now = current_wip()
    wip_series.append((0.0, wip_now["system"]))

    # initialize WIP max with current state
    wip_now = current_wip()
    for key, val in wip_now.items():
        wip_max[key] = max(wip_max[key], val)

    while events:
        now, _seq, stage, item = heapq.heappop(events)
        dt = now - last_time
        if dt > 0:
            wip_now = current_wip()
            for key, val in wip_now.items():
                wip_area[key] += val * dt
                if val > wip_max[key]:
                    wip_max[key] = val
            last_time = now
        if stage == "pesado":
            avail_p += 1
            item.arrival_m = now
            queue_m.append(item)
        elif stage == "mezcla":
            avail_m += 1
            item.arrival_o = now
            queue_o.append(item)
        elif stage == "moldes":
            avail_o += 1
            completed += 1

        try_start_pesado()
        try_start_mezcla()
        try_start_moldes()
        wip_now = current_wip()
        wip_series.append((now, wip_now["system"]))

    makespan = now
    utilization = {}
    if makespan > 0:
        utilization = {
            "pesado": busy_time["pesado"] / (makespan * max(x_p, 1)),
            "mezcla": busy_time["mezcla"] / (makespan * max(x_m, 1)),
            "moldes": busy_time["moldes"] / (makespan * max(x_o, 1)),
        }

    queue_stats = {
        "pesado": _queue_stats(waits["pesado"]),
        "mezcla": _queue_stats(waits["mezcla"]),
        "moldes": _queue_stats(waits["moldes"]),
    }
    wip_stats = {}
    if makespan > 0:
        wip_stats = {
            "pesado": {"avg": wip_area["pesado"] / makespan, "max": wip_max["pesado"]},
            "mezcla": {"avg": wip_area["mezcla"] / makespan, "max": wip_max["mezcla"]},
            "moldes": {"avg": wip_area["moldes"] / makespan, "max": wip_max["moldes"]},
            "system": {"avg": wip_area["system"] / makespan, "max": wip_max["system"]},
        }

    return SimulationResult(
        makespan=makespan,
        items=items,
        utilization=utilization,
        queue_stats=queue_stats,
        wip_stats=wip_stats,
        wip_series=wip_series,
    )


def _queue_stats(values: List[float]) -> Dict[str, float]:
    if not values:
        return {"avg": 0.0, "max": 0.0}
    return {"avg": sum(values) / len(values), "max": max(values)}
