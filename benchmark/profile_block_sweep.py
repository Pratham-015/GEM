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
    parser.add_argument("--blocks", default="1,2,4,8,16,20,32,40")
    parser.add_argument("--cycles", type=int, default=300)
    parser.add_argument("--repetitions", type=int, default=3)
    args = parser.parse_args()
    netlist = ROOT / "benchmark/generated/artifacts/mixed_heterogeneous.gv"
    parts = ROOT / "benchmark/generated/artifacts/mixed_heterogeneous.gemparts"
    if not netlist.exists() or not parts.exists():
        raise SystemExit("run the Deliverable D benchmark or mixed Nsight preparation first")
    results = []
    for blocks in (int(value) for value in args.blocks.split(",")):
        command = [ROOT / "target/release/cuda_dummy_test", netlist, parts, blocks,
                   args.cycles, "--top-module", "mixed_heterogeneous",
                   "--warmup-runs", "3", "--repetitions", args.repetitions,
                   "--seed", "20260902"]
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
    payload = {"workload": "mixed_heterogeneous", "cycles": args.cycles,
               "repetitions": args.repetitions, "results": results,
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
    output = ROOT / "benchmark/results/block_sweep.json"
    output.write_text(json.dumps(payload, indent=2) + "\n")
    print(output)


if __name__ == "__main__":
    main()
