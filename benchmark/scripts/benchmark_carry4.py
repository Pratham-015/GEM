#!/usr/bin/env python3
"""Run the CARRY4 speed test."""

import argparse
import datetime
import json
import pathlib
import subprocess
import sys

from run_benchmarks import ROOT, measure_macro_representation


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=7)
    parser.add_argument("--blocks", type=int, default=4)
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=ROOT / "benchmark/results/carry4_optimization.json",
    )
    args = parser.parse_args()
    if args.repetitions < 2:
        raise SystemExit("at least two repetitions are required")

    subprocess.run(
        [sys.executable, "benchmark/workloads/generate_workloads.py",
         "--output-dir", "benchmark/temporary/generated/workloads"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        ["cargo", "build", "--release", "--features", "cuda",
         "--bin", "cut_map_interactive", "--bin", "cuda_dummy_test",
         "--bin", "cuda_test"],
        cwd=ROOT,
        check=True,
    )
    result = measure_macro_representation(args.repetitions, args.blocks)
    upstream = result["shredded_upstream"]
    modified = result["preserved_modified"]
    historical_ratio = 0.117
    evidence = {
        "schema_version": 1,
        "recorded_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "experiment": result["label"],
        "experimental_factor": result["experimental_factor"],
        "blocks": args.blocks,
        "repetitions": args.repetitions,
        "source": result["source"],
        "netlist_stats": result["netlist_stats"],
        "upstream_commit": upstream["commit"],
        "modified_commit": modified["commit"],
        "upstream_median_cps": upstream["summary"]["median_cps"],
        "modified_median_cps": modified["summary"]["median_cps"],
        "ratio": result["speedup"],
        "historical_ratio": historical_ratio,
        "ratio_improvement": result["speedup"] / historical_ratio,
        "upstream_samples": upstream["samples"],
        "modified_samples": modified["samples"],
        "commands": {
            "upstream": upstream["command"],
            "modified": modified["command"],
        },
    }
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(
        f"PASS: CARRY4 {evidence['ratio']:.3f}x "
        f"({evidence['modified_median_cps']:.0f} vs "
        f"{evidence['upstream_median_cps']:.0f} cycles/s); {output}"
    )


if __name__ == "__main__":
    main()
