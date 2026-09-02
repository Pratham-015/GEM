#!/usr/bin/env python3
"""Measure production mixed-workload throughput versus cooperative grid size."""

import argparse
import datetime
import json
from pathlib import Path
import re
import statistics
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = re.compile(r"GEM_BENCH_SAMPLE .* cycles_per_second=([0-9.]+)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workload", default="mixed_heterogeneous")
    parser.add_argument("--blocks")
    parser.add_argument("--cycles", type=int, default=1000)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--warmup-runs", type=int, default=12)
    args = parser.parse_args()
    manifest = json.loads((ROOT / "benchmark/generated/workloads/manifest.json").read_text())
    item = next((item for item in manifest if item["name"] == args.workload), None)
    if item is None:
        raise SystemExit(f"unknown workload: {args.workload}")
    netlist = ROOT / f"benchmark/generated/artifacts/{args.workload}.gv"
    parts = ROOT / f"benchmark/generated/artifacts/{args.workload}.gemparts"
    if not netlist.exists() or not parts.exists():
        raise SystemExit("run the Deliverable D benchmark or mixed Nsight preparation first")
    results = []
    block_list = args.blocks or ("1,4,8,9,12,16,20,28,40"
                                 if args.workload == "occupancy_stress"
                                 else "1,2,4,8,16,20,32,40")
    for blocks in (int(value) for value in block_list.split(",")):
        command = [ROOT / "target/release/cuda_dummy_test", netlist, parts, blocks,
                   args.cycles, "--top-module", item["top"],
                   "--warmup-runs", args.warmup_runs, "--repetitions", args.repetitions,
                   "--seed", str(item["seed"])]
        completed = subprocess.run([str(value) for value in command], cwd=ROOT,
                                   text=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, check=True)
        samples = [float(value) for value in SAMPLE.findall(completed.stdout)]
        if len(samples) != args.repetitions:
            raise RuntimeError(f"blocks={blocks}: missing samples")
        results.append({"blocks": blocks, "samples_cps": samples,
                        "median_cps": statistics.median(samples),
                        "mean_cps": statistics.mean(samples),
                        "command": [str(value) for value in command],
                        "raw_stdout": completed.stdout})
    payload = {"workload": args.workload, "cycles": args.cycles,
               "repetitions": args.repetitions, "warmup_runs": args.warmup_runs,
               "results": results,
               "environment": {
                   "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   "commit": subprocess.check_output(
                       ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                   "dirty": bool(subprocess.check_output(
                       ["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
                   "gpu": subprocess.check_output(
                       ["nvidia-smi", "--query-gpu=name,driver_version,compute_cap",
                        "--format=csv,noheader"], text=True).strip(),
               }}
    suffix = "" if args.workload == "mixed_heterogeneous" else f"_{args.workload}"
    output = ROOT / f"benchmark/results/block_sweep{suffix}.json"
    output.write_text(json.dumps(payload, indent=2) + "\n")
    print(output)


if __name__ == "__main__":
    main()
