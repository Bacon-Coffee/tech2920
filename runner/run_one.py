"""Run a single SUMO experiment and emit a 7-KPI summary.

Usage:
    python -m runner.run_one \
        --cfg sim/grid4x4_normal_400.sumocfg \
        --controller fixed_time \
        --seed 1 \
        --scenario normal \
        --flow 400

Outputs (under ``results/<run_id>/``):
    * ``tripinfo.xml``     -- SUMO per-trip records (incl. emissions)
    * ``summary.xml``      -- SUMO per-step aggregate counts
    * ``queue.xml``        -- SUMO per-step per-lane queues
    * ``statistic.xml``    -- SUMO end-of-run aggregate stats
    * ``summary.json``     -- our 7 KPIs + run metadata

The CRN principle: ``--seed`` is forwarded to SUMO so the same seed
with the same .rou.xml produces the same vehicle insertion sequence,
allowing paired t-tests across controllers later.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

_SUMO_HOME = os.environ.get("SUMO_HOME") or \
    "/Library/Frameworks/EclipseSUMO.framework/Versions/1.26.0/EclipseSUMO/share/sumo"
os.environ["SUMO_HOME"] = _SUMO_HOME
if _SUMO_HOME and os.path.isdir(os.path.join(_SUMO_HOME, "tools")):
    sys.path.insert(0, os.path.join(_SUMO_HOME, "tools"))

import traci  # noqa: E402

from controllers import BaseController, FixedTimeController  # noqa: E402

CONTROLLER_REGISTRY: dict[str, type[BaseController]] = {
    FixedTimeController.name: FixedTimeController,
}

WARMUP_SECONDS = 600
SIM_END = 3600
SUMO_BIN = "/Library/Frameworks/EclipseSUMO.framework/Versions/1.26.0/EclipseSUMO/bin/sumo"
TLL_STATIC_ADD = PROJECT_ROOT / "sim" / "tll_static.add.xml"


def _safe_float(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _jain_index(values):
    vals = [v for v in values if v is not None and not math.isnan(v)]
    if not vals:
        return float("nan")
    s = sum(vals)
    sq = sum(v * v for v in vals)
    if sq == 0:
        return 1.0
    return (s * s) / (len(vals) * sq)


def _parse_tripinfo(tripinfo_path: Path):
    durations, waits, stops = [], [], []
    co2_total = 0.0
    n = 0
    if not tripinfo_path.exists():
        return durations, waits, stops, co2_total, n
    for _, elem in ET.iterparse(tripinfo_path, events=("end",)):
        if elem.tag != "tripinfo":
            continue
        n += 1
        durations.append(_safe_float(elem.get("duration")))
        waits.append(_safe_float(elem.get("waitingTime")))
        stops.append(_safe_float(elem.get("waitingCount")))
        em = elem.find("emissions")
        if em is not None:
            co2_total += _safe_float(em.get("CO2_abs"))
        elem.clear()
    return durations, waits, stops, co2_total, n


def _parse_summary(summary_path: Path):
    if not summary_path.exists():
        return 0, 0, 0
    inserted = arrived = teleports = 0
    for _, elem in ET.iterparse(summary_path, events=("end",)):
        if elem.tag != "step":
            continue
        inserted = max(inserted, int(_safe_float(elem.get("inserted"))))
        arrived = max(arrived, int(_safe_float(elem.get("ended"))))
        teleports = max(teleports, int(_safe_float(elem.get("teleports"))))
        elem.clear()
    return inserted, arrived, teleports


def _parse_max_queue(queue_path: Path, warmup: int = WARMUP_SECONDS):
    if not queue_path.exists():
        return 0.0
    max_q = 0.0
    for _, elem in ET.iterparse(queue_path, events=("end",)):
        if elem.tag != "data":
            continue
        t = _safe_float(elem.get("timestep"))
        if t >= warmup:
            for lane in elem.findall("./lanes/lane"):
                q = _safe_float(lane.get("queueing_length"))
                if q > max_q:
                    max_q = q
        elem.clear()
    return max_q


def run_one(cfg: Path, controller_name: str, seed: int,
            scenario: str, flow: int, output_root: Path) -> Path:
    if controller_name not in CONTROLLER_REGISTRY:
        raise ValueError(
            f"unknown controller {controller_name!r}; "
            f"known: {sorted(CONTROLLER_REGISTRY)}"
        )

    run_id = f"{scenario}_flow{flow}_{controller_name}_seed{seed}"
    out_dir = output_root / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    tripinfo = out_dir / "tripinfo.xml"
    summary_xml = out_dir / "summary.xml"
    queue_xml = out_dir / "queue.xml"
    statistic_xml = out_dir / "statistic.xml"

    sumo_cmd = [
        SUMO_BIN,
        "-c", str(cfg),
        "--additional-files", str(TLL_STATIC_ADD),
        "--seed", str(seed),
        "--tripinfo-output", str(tripinfo),
        "--tripinfo-output.write-unfinished", "true",
        "--summary-output", str(summary_xml),
        "--queue-output", str(queue_xml),
        "--statistic-output", str(statistic_xml),
        "--device.emissions.probability", "1.0",
        "--emissions.volumetric-fuel", "true",
        "--no-step-log", "true",
        "--time-to-teleport", "300",
        "--duration-log.statistics", "true",
        "--verbose", "false",
    ]

    t0 = time.time()
    traci.start(sumo_cmd)
    try:
        tl_ids = traci.trafficlight.getIDList()
        controller_cls = CONTROLLER_REGISTRY[controller_name]
        controller = controller_cls()
        controller.setup(traci, tl_ids)

        sim_time = traci.simulation.getTime()
        while sim_time < SIM_END:
            traci.simulationStep()
            sim_time = traci.simulation.getTime()
            controller.step(sim_time)
        controller.teardown()
    finally:
        traci.close()
    wall = time.time() - t0

    durations, waits, stops, co2_mg, n_trip = _parse_tripinfo(tripinfo)
    inserted, arrived, teleports = _parse_summary(summary_xml)
    max_q = _parse_max_queue(queue_xml)

    def _mean(xs):
        return float(sum(xs) / len(xs)) if xs else float("nan")

    summary = {
        "run_id": run_id,
        "controller": controller_name,
        "cfg": str(cfg),
        "scenario": scenario,
        "flow": flow,
        "seed": seed,
        "sim_seconds": SIM_END,
        "warmup_seconds": WARMUP_SECONDS,
        "wall_seconds": round(wall, 2),
        "n_tl": len(tl_ids),
        "n_inserted": inserted,
        "n_arrived": arrived,
        "n_teleports": teleports,
        "n_tripinfo_records": n_trip,
        "avg_travel_time": _mean(durations),
        "avg_waiting_time": _mean(waits),
        "avg_stops": _mean(stops),
        "throughput": arrived,
        "total_co2_mg": co2_mg,
        "max_queue_m": max_q,
        "jain_fairness": _jain_index(waits),
        "finished_at_iso": datetime.now(timezone.utc).isoformat(),
    }
    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    return summary_path


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cfg", type=Path, required=True)
    p.add_argument("--controller", required=True,
                   choices=sorted(CONTROLLER_REGISTRY))
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--scenario", required=True,
                   choices=["normal", "unbalanced", "incident"])
    p.add_argument("--flow", type=int, required=True)
    p.add_argument("--output-root", type=Path,
                   default=PROJECT_ROOT / "results")
    args = p.parse_args()

    cfg = args.cfg if args.cfg.is_absolute() else (PROJECT_ROOT / args.cfg).resolve()
    out = run_one(cfg, args.controller, args.seed, args.scenario,
                  args.flow, args.output_root)
    print(f"summary -> {out}")


if __name__ == "__main__":
    main()
