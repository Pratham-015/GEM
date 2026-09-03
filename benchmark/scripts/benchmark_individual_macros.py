#!/usr/bin/env python3
"""Compare individual macro circuits with shredded upstream GEM."""

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
import re
import sys

from run_benchmarks import (
    GENERATED,
    OLD_TIMER_RE,
    ROOT,
    UPSTREAM_COMMIT,
    ensure_upstream_worktree,
    environment_commit,
    netlist_counts,
    parse_new_samples,
    run,
    sha256_file,
    summarize,
    ys_quote,
)


CIRCUITS = (
    {
        "name": "dsp_multiply_bank",
        "macro": "DSP48E2",
        "top": "dsp_multiply_bank",
        "source": "benchmark/circuits/dsp48e2/multiply_bank/circuit.sv",
        "expected": {"dsp": 8, "carry4": 0, "srlc32e": 0},
        "cycles": 5000,
    },
    {
        "name": "carry4_independent_bank",
        "macro": "CARRY4",
        "top": "carry4_independent_bank",
        "source": "benchmark/circuits/carry4/independent_bank/circuit.sv",
        "expected": {"dsp": 0, "carry4": 128, "srlc32e": 0},
        "cycles": 5000,
    },
    {
        "name": "srlc32e_parallel_bank",
        "macro": "SRLC32E",
        "top": "srlc32e_parallel_bank",
        "source": "benchmark/circuits/srlc32e/parallel_bank/circuit.sv",
        "expected": {"dsp": 0, "carry4": 0, "srlc32e": 128},
        "cycles": 5000,
    },
)


def synthesize_shredded(spec, output):
    source = ROOT / spec["source"]
    commands = [
        f"read_verilog -sv -DSHREDDED {ys_quote(source)}",
        f"hierarchy -check -top {spec['top']}",
        "synth -flatten",
        "delete t:$print",
        f"dfflibmap -liberty {ys_quote(ROOT / 'aigpdk/aigpdk_nomem.lib')}",
        "opt_clean -purge",
        f"abc -liberty {ys_quote(ROOT / 'aigpdk/aigpdk_nomem.lib')}",
        "opt_clean -purge",
        "techmap",
        f"abc -liberty {ys_quote(ROOT / 'aigpdk/aigpdk_nomem.lib')}",
        "opt_clean -purge",
        f"write_verilog -noexpr -nodec {ys_quote(output)}",
    ]
    run(["yosys", "-q", "-p", "; ".join(commands)])


def prepare_circuit(spec, upstream):
    work = GENERATED / "individual_macros" / spec["name"]
    work.mkdir(parents=True, exist_ok=True)
    source = ROOT / spec["source"]
    shredded = work / "shredded.gv"
    preserved = work / "preserved.gv"
    preserved_json = work / "preserved.json"
    shredded_parts = work / "shredded.upstream.gemparts"
    preserved_parts = work / "preserved.modified.gemparts"

    synthesize_shredded(spec, shredded)
    run([
        sys.executable,
        "scripts/synthesize_macros.py",
        "--top",
        spec["top"],
        "--output",
        preserved,
        "--json",
        preserved_json,
        source,
    ])

    shredded_stats = netlist_counts(shredded)
    preserved_stats = netlist_counts(preserved)
    if any(shredded_stats[key] for key in ("dsp", "carry4", "srlc32e")):
        raise RuntimeError(f"{spec['name']}: shredded netlist still has macros")
    for key, expected in spec["expected"].items():
        if preserved_stats[key] != expected:
            raise RuntimeError(
                f"{spec['name']}: expected {expected} {key}, "
                f"found {preserved_stats[key]}"
            )

    run([
        upstream / "target/release/cut_map_interactive",
        shredded,
        shredded_parts,
        "--top-module",
        spec["top"],
    ], cwd=upstream)
    run([
        ROOT / "target/release/cut_map_interactive",
        preserved,
        preserved_parts,
        "--top-module",
        spec["top"],
    ])
    return {
        "source": source,
        "shredded": shredded,
        "preserved": preserved,
        "shredded_parts": shredded_parts,
        "preserved_parts": preserved_parts,
        "stats": {"shredded": shredded_stats, "preserved": preserved_stats},
    }


def measure(spec, files, upstream, repetitions, blocks):
    upstream_command = [
        upstream / "target/release/cuda_dummy_test",
        files["shredded"],
        files["shredded_parts"],
        str(blocks),
        str(spec["cycles"]),
        "--top-module",
        spec["top"],
    ]
    modified_command = [
        ROOT / "target/release/cuda_dummy_test",
        files["preserved"],
        files["preserved_parts"],
        str(blocks),
        str(spec["cycles"]),
        "--top-module",
        spec["top"],
        "--warmup-runs",
        "1",
        "--repetitions",
        "1",
        "--seed",
        "0",
    ]

    for _ in range(3):
        run(upstream_command, cwd=upstream)
        run(modified_command)

    upstream_samples = []
    modified_samples = []
    for repetition in range(repetitions):
        order = ("upstream", "modified")
        if repetition % 2:
            order = tuple(reversed(order))
        for implementation in order:
            if implementation == "upstream":
                result = run(upstream_command, cwd=upstream)
                values = OLD_TIMER_RE.findall(result.stdout)
                if len(values) != 1:
                    raise RuntimeError(f"{spec['name']}: upstream timer missing")
                elapsed_ms = float(values[0])
                upstream_samples.append({
                    "repetition": repetition,
                    "cycles": spec["cycles"],
                    "elapsed_ms": elapsed_ms,
                    "cycles_per_second": spec["cycles"] / (elapsed_ms / 1000.0),
                })
            else:
                result = run(modified_command)
                samples = parse_new_samples(result.stdout)
                if len(samples) != 1:
                    raise RuntimeError(f"{spec['name']}: modified timer missing")
                samples[0]["repetition"] = repetition
                modified_samples.append(samples[0])

    upstream_summary = summarize(upstream_samples)
    modified_summary = summarize(modified_samples)
    return {
        "name": spec["name"],
        "macro": spec["macro"],
        "source": str(files["source"].relative_to(ROOT)),
        "cycles": spec["cycles"],
        "blocks": blocks,
        "netlist_stats": files["stats"],
        "sha256": {
            "source": sha256_file(files["source"]),
            "shredded_netlist": sha256_file(files["shredded"]),
            "preserved_netlist": sha256_file(files["preserved"]),
        },
        "upstream": {
            "commit": UPSTREAM_COMMIT,
            "command": [str(value) for value in upstream_command],
            "samples": upstream_samples,
            "summary": upstream_summary,
        },
        "modified": {
            "commit": environment_commit(),
            "command": [str(value) for value in modified_command],
            "samples": modified_samples,
            "summary": modified_summary,
        },
        "ratio": modified_summary["median_cps"] / upstream_summary["median_cps"],
    }


def write_results(results, output):
    payload = {
        "schema_version": 1,
        "recorded_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "comparison": "same circuit behavior; shredded upstream versus macro-preserved Big-GEM",
        "experimental_factor": "representation plus implementation",
        "results": results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    csv_path = output.with_suffix(".csv")
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=(
            "circuit", "macro", "shredded_cells", "preserved_cells",
            "upstream_median_cps", "modified_median_cps", "ratio",
            "percentage_change",
        ))
        writer.writeheader()
        for item in results:
            writer.writerow({
                "circuit": item["name"],
                "macro": item["macro"],
                "shredded_cells": item["netlist_stats"]["shredded"]["cells"],
                "preserved_cells": item["netlist_stats"]["preserved"]["cells"],
                "upstream_median_cps": item["upstream"]["summary"]["median_cps"],
                "modified_median_cps": item["modified"]["summary"]["median_cps"],
                "ratio": item["ratio"],
                "percentage_change": (item["ratio"] - 1.0) * 100.0,
            })
    print(f"results: {output}")
    print(f"summary: {csv_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=7)
    parser.add_argument("--blocks", type=int, default=1)
    parser.add_argument("--only", choices=[item["name"] for item in CIRCUITS])
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "benchmark/results/individual_macros.json",
    )
    args = parser.parse_args()
    if args.repetitions < 2:
        raise SystemExit("at least two repetitions are required")

    selected = [item for item in CIRCUITS if not args.only or item["name"] == args.only]
    upstream = ensure_upstream_worktree()
    run([
        "cargo", "build", "--release", "--features", "cuda", "--bin",
        "cut_map_interactive", "--bin", "cuda_dummy_test",
    ])
    results = []
    for spec in selected:
        print(f"\n=== {spec['name']} ===", flush=True)
        files = prepare_circuit(spec, upstream)
        result = measure(spec, files, upstream, args.repetitions, args.blocks)
        results.append(result)
        print(
            f"{spec['macro']}: {result['ratio']:.3f}x "
            f"({result['modified']['summary']['median_cps']:.0f} vs "
            f"{result['upstream']['summary']['median_cps']:.0f} CPS)",
            flush=True,
        )

    output = args.output if args.output.is_absolute() else ROOT / args.output
    write_results(results, output)


if __name__ == "__main__":
    main()
