#!/usr/bin/env python3
"""Reproducible production-GEM throughput runner for Deliverable D."""

import argparse
import csv
import datetime as dt
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmark"
GENERATED = BENCH / "generated"
RESULTS = BENCH / "results"
UPSTREAM_COMMIT = "9e913f9b5efc8b12027bfb374be8b1a0028df00a"
SAMPLE_RE = re.compile(r"GEM_BENCH_SAMPLE repetition=(\d+) cycles=(\d+) elapsed_ms=([0-9.]+) cycles_per_second=([0-9.]+)")
OLD_TIMER_RE = re.compile(r"simulation, Elapsed=([0-9.]+)ms")
INPUT_HASH_RE = re.compile(r"Benchmark input hash: (\d+)")


def run(command, cwd=ROOT, check=True, timeout=1800):
    command = [str(x) for x in command]
    print("+", " ".join(command), flush=True)
    result = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=timeout)
    if check and result.returncode:
        print(result.stdout)
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}")
    return result


def version(command):
    try:
        return run(command, check=False, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "UNAVAILABLE"


def environment():
    status = run(["git", "status", "--porcelain"], check=True).stdout.strip()
    return {
        "recorded_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "commit": run(["git", "rev-parse", "HEAD"]).stdout.strip(),
        "dirty": bool(status),
        "gpu": version(["nvidia-smi", "--query-gpu=name,compute_cap,driver_version,memory.total", "--format=csv,noheader"]),
        "cuda": version(["nvcc", "--version"]),
        "ncu": version(["ncu", "--version"]),
        "yosys": version(["yosys", "--version"]),
        "rust": version(["rustc", "--version"]),
        "build": "cargo build --release --features cuda",
        "cuda_blocks": None,
        "cuda_compile_command": "RECORDED_AFTER_BUILD",
    }


def cuda_compile_command():
    path = ROOT / "compile_commands.json"
    if not path.exists():
        return "UNAVAILABLE"
    for entry in json.loads(path.read_text(encoding="utf-8")):
        if entry.get("file") == "csrc/kernel_v1.cu":
            return entry.get("command", "UNAVAILABLE")
    return "UNAVAILABLE"


def netlist_counts(path):
    counts = {}
    pattern = re.compile(r"^\s+(\w+)\s+\\?\S+\s*\(", re.MULTILINE)
    for kind in pattern.findall(path.read_text(encoding="utf-8")):
        if kind not in {"module", "input", "output", "wire", "assign"}:
            counts[kind] = counts.get(kind, 0) + 1
    return {
        "cells": sum(counts.values()),
        "aig_cells": sum(v for k, v in counts.items() if k.startswith("AND2_")),
        "dsp": counts.get("GEM_DSP48E2", 0) + counts.get("DSP48E2", 0),
        "carry4": counts.get("CARRY4", 0),
        "srlc32e": counts.get("SRLC32E", 0),
        "cell_types": counts,
    }


def prepare(only=None):
    workloads = GENERATED / "workloads"
    artifacts = GENERATED / "artifacts"
    workloads.mkdir(parents=True, exist_ok=True)
    artifacts.mkdir(parents=True, exist_ok=True)
    run([sys.executable, BENCH / "workloads/generate_workloads.py", "--output-dir", workloads])
    run(["cargo", "build", "--release", "--features", "cuda", "--bin",
         "cut_map_interactive", "--bin", "cuda_dummy_test", "--bin", "cuda_test"])
    manifest = json.loads((workloads / "manifest.json").read_text())
    if only:
        requested = set(only)
        known = {item["name"] for item in manifest}
        unknown = sorted(requested - known)
        if unknown:
            raise RuntimeError(f"unknown workload(s): {', '.join(unknown)}")
        manifest = [item for item in manifest if item["name"] in requested]
    prepared = []
    for item in manifest:
        name = item["name"]
        source = ROOT / item["source"] if not Path(item["source"]).is_absolute() else Path(item["source"])
        gv, js, parts = artifacts / f"{name}.gv", artifacts / f"{name}.json", artifacts / f"{name}.gemparts"
        t0 = time.perf_counter()
        run([sys.executable, "scripts/synthesize_macros.py", "--top", item["top"],
             "--output", gv, "--json", js, source])
        synthesis_s = time.perf_counter() - t0
        t0 = time.perf_counter()
        part = run(["target/release/cut_map_interactive", gv, parts,
                    "--top-module", item["top"]])
        partition_s = time.perf_counter() - t0
        match = re.search(r"netlist has (\d+) pins, (\d+) aig pins, (\d+) and gates", part.stdout)
        item.update({"source": str(source.relative_to(ROOT)), "netlist": str(gv.relative_to(ROOT)),
                     "json": str(js.relative_to(ROOT)), "gemparts": str(parts.relative_to(ROOT)),
                     "synthesis_seconds": synthesis_s, "partition_seconds": partition_s,
                     "netlist_stats": netlist_counts(gv)})
        if match:
            item["graph_stats"] = {"pins": int(match.group(1)), "aig_pins": int(match.group(2)), "and_gates": int(match.group(3))}
        prepared.append(item)
    (GENERATED / "prepared.json").write_text(json.dumps(prepared, indent=2) + "\n")
    return prepared


def summarize(samples):
    cps = [s["cycles_per_second"] for s in samples]
    elapsed = [s["elapsed_ms"] for s in samples]
    return {"samples": len(samples), "mean_cps": statistics.mean(cps),
            "median_cps": statistics.median(cps), "min_cps": min(cps), "max_cps": max(cps),
            "stdev_cps": statistics.stdev(cps) if len(cps) > 1 else 0.0,
            "mean_elapsed_ms": statistics.mean(elapsed)}


def parse_new_samples(output):
    return [{"repetition": int(m.group(1)), "cycles": int(m.group(2)),
             "elapsed_ms": float(m.group(3)), "cycles_per_second": float(m.group(4))}
            for m in SAMPLE_RE.finditer(output)]


def measure_current(item, repetitions, blocks, seed, warmup_runs=12):
    command = ["target/release/cuda_dummy_test", item["netlist"], item["gemparts"],
               str(blocks), str(item["cycles"]), "--top-module", item["top"],
               "--warmup-runs", str(warmup_runs), "--repetitions", str(repetitions),
               "--seed", str(seed)]
    t0 = time.perf_counter()
    result = run(command)
    wall = time.perf_counter() - t0
    samples = parse_new_samples(result.stdout)
    if len(samples) != repetitions:
        raise RuntimeError(f"{item['name']}: expected {repetitions} samples, found {len(samples)}")
    input_hashes = INPUT_HASH_RE.findall(result.stdout)
    if len(input_hashes) != 1:
        raise RuntimeError(f"{item['name']}: deterministic input hash missing")
    return {"implementation": "modified", "command": command,
            "input_hash": input_hashes[0], "process_wall_seconds": wall,
            "raw_stdout": result.stdout,
            "samples": samples, "summary": summarize(samples)}


def ensure_upstream_worktree():
    path = Path("/tmp/gem-deliverable-d-upstream")
    if not path.exists():
        run(["git", "worktree", "add", "--detach", path, UPSTREAM_COMMIT])
    head = run(["git", "rev-parse", "HEAD"], cwd=path).stdout.strip()
    if head != UPSTREAM_COMMIT:
        raise RuntimeError(f"refusing non-upstream worktree {path}: {head}")
    run(["git", "submodule", "update", "--init", "--recursive"], cwd=path)
    run(["cargo", "build", "--release", "--features", "cuda", "--bin",
         "cut_map_interactive", "--bin", "cuda_dummy_test", "--bin", "cuda_test"], cwd=path)
    return path


def measure_boolean_comparison(item, repetitions, blocks):
    upstream = ensure_upstream_worktree()
    parts = GENERATED / "artifacts/boolean_heavy.upstream.gemparts"
    run([upstream / "target/release/cut_map_interactive", ROOT / item["netlist"], parts,
         "--top-module", item["top"]], cwd=upstream)
    upstream_command = [upstream / "target/release/cuda_dummy_test", ROOT / item["netlist"], parts,
                        str(blocks), str(item["cycles"]), "--top-module", item["top"]]
    modified_command = [ROOT / "target/release/cuda_dummy_test", ROOT / item["netlist"],
                        parts.with_name("boolean_heavy.gemparts"), str(blocks), str(item["cycles"]),
                        "--top-module", item["top"], "--warmup-runs", "1",
                        "--repetitions", "1", "--seed", "0"]

    # Precondition the GPU before sampling.  The official upstream executable
    # already performs one internal warm-up; these discarded invocations avoid
    # treating laptop-GPU clock ramp as an implementation speedup.
    for _ in range(3):
        run(upstream_command, cwd=upstream)
        run(modified_command)

    upstream_samples, modified_samples = [], []
    upstream_stdout, modified_stdout = [], []

    def sample_upstream(repetition):
        result = run(upstream_command, cwd=upstream)
        upstream_stdout.append(result.stdout)
        matches = OLD_TIMER_RE.findall(result.stdout)
        if len(matches) != 1:
            raise RuntimeError(f"upstream sample {repetition}: expected one measured timer, got {matches}")
        elapsed_ms = float(matches[0])
        upstream_samples.append({"repetition": repetition, "cycles": item["cycles"],
                                 "elapsed_ms": elapsed_ms,
                                 "cycles_per_second": item["cycles"] / (elapsed_ms / 1000.0)})

    def sample_modified(repetition):
        result = run(modified_command)
        modified_stdout.append(result.stdout)
        samples = parse_new_samples(result.stdout)
        if len(samples) != 1:
            raise RuntimeError(f"modified comparison sample {repetition}: expected one timer")
        samples[0]["repetition"] = repetition
        modified_samples.append(samples[0])

    for repetition in range(repetitions):
        if repetition % 2 == 0:
            sample_upstream(repetition); sample_modified(repetition)
        else:
            sample_modified(repetition); sample_upstream(repetition)

    baseline = {"implementation": "upstream", "commit": UPSTREAM_COMMIT,
                "command": [str(x) for x in upstream_command], "raw_stdout": upstream_stdout,
                "samples": upstream_samples, "summary": summarize(upstream_samples)}
    modified = {"implementation": "modified", "commit": environment_commit(),
                "command": [str(x) for x in modified_command], "raw_stdout": modified_stdout,
                "samples": modified_samples, "summary": summarize(modified_samples)}
    return baseline, modified


def environment_commit():
    return run(["git", "rev-parse", "HEAD"]).stdout.strip()


def measure_macro_representation(repetitions, blocks):
    """Compare same RTL as shredded upstream vs preserved modified netlists.

    This is intentionally separate from the identical-netlist implementation
    comparison because the representation is one of the experimental factors.
    """
    upstream = ensure_upstream_worktree()
    out = GENERATED / "representation"
    out.mkdir(parents=True, exist_ok=True)
    flow_a = ROOT / "test3/flowA_baseline_flatten_gatelevel.gv"
    flow_b = ROOT / "test3/flowB_macropreserve_gatelevel.gv"
    parts_a, parts_b = out / "shredded.upstream.gemparts", out / "preserved.modified.gemparts"
    run([upstream / "target/release/cut_map_interactive", flow_a, parts_a,
         "--top-module", "signal_processor"], cwd=upstream)
    run([ROOT / "target/release/cut_map_interactive", flow_b, parts_b,
         "--top-module", "signal_processor"])

    # Correctness gate for the two historical synthesis representations.
    (ROOT / "verif/sim_out").mkdir(parents=True, exist_ok=True)
    run(["iverilog", "-g2012", "test3/macros_behavioral.sv", "test3/signal_processor.sv",
         "benchmark/tb_signal_processor_stim.sv", "-o", out / "golden.out"])
    run(["vvp", out / "golden.out"])
    golden = ROOT / "verif/sim_out/signal_processor_stim.vcd"
    gpu_a, gpu_b = out / "shredded.vcd", out / "preserved.vcd"
    common = [golden, None, "1", "--top-module", "signal_processor",
              "--input-vcd-scope", "tb_signal_processor_stim/dut", "--check-with-cpu"]
    cmd_a = [upstream / "target/release/cuda_test", flow_a, parts_a,
             common[0], gpu_a, *common[2:]]
    cmd_b = [ROOT / "target/release/cuda_test", flow_b, parts_b,
             common[0], gpu_b, *common[2:]]
    result_a = run(cmd_a, cwd=upstream)
    result_b = run(cmd_b)
    signals = "out_p:48,out_parity:1"
    diff_a = run([sys.executable, "verif/host/compare_macro_integration.py",
                  golden, gpu_a, "--signals", signals], check=False)
    diff_b = run([sys.executable, "verif/host/compare_macro_integration.py",
                  golden, gpu_b, "--signals", signals], check=False)
    correctness = {"status": "PASS" if diff_a.returncode == diff_b.returncode == 0 else "INVALID",
                   "signals": signals, "upstream_stdout": result_a.stdout,
                   "modified_stdout": result_b.stdout,
                   "upstream_diff": diff_a.stdout, "modified_diff": diff_b.stdout}
    if correctness["status"] != "PASS":
        return {"label": "same RTL, different synthesis representation and simulator",
                "correctness": correctness, "speedup": None,
                "reason": "performance comparison suppressed because at least one representation failed RTL differential checking"}

    cycles = 2000
    upstream_command = [upstream / "target/release/cuda_dummy_test", flow_a, parts_a,
                        str(blocks), str(cycles), "--top-module", "signal_processor"]
    modified_command = [ROOT / "target/release/cuda_dummy_test", flow_b, parts_b,
                        str(blocks), str(cycles), "--top-module", "signal_processor",
                        "--warmup-runs", "1", "--repetitions", "1", "--seed", "0"]
    for _ in range(3):
        run(upstream_command, cwd=upstream); run(modified_command)
    samples_a, samples_b, stdout_a, stdout_b = [], [], [], []
    for repetition in range(repetitions):
        ordered = (("a", upstream_command), ("b", modified_command))
        if repetition % 2:
            ordered = tuple(reversed(ordered))
        for kind, command in ordered:
            result = run(command, cwd=upstream if kind == "a" else ROOT)
            if kind == "a":
                stdout_a.append(result.stdout)
                matches = OLD_TIMER_RE.findall(result.stdout)
                if len(matches) != 1:
                    raise RuntimeError("shredded upstream timer missing")
                elapsed = float(matches[0])
                samples_a.append({"repetition": repetition, "cycles": cycles,
                                  "elapsed_ms": elapsed,
                                  "cycles_per_second": cycles / (elapsed / 1000.0)})
            else:
                stdout_b.append(result.stdout)
                samples = parse_new_samples(result.stdout)
                if len(samples) != 1:
                    raise RuntimeError("preserved modified timer missing")
                samples[0]["repetition"] = repetition
                samples_b.append(samples[0])
    a = {"implementation": "official_upstream_shredded", "commit": UPSTREAM_COMMIT,
         "netlist": str(flow_a.relative_to(ROOT)), "command": [str(x) for x in upstream_command],
         "raw_stdout": stdout_a, "samples": samples_a, "summary": summarize(samples_a)}
    b = {"implementation": "modified_macro_preserved", "commit": environment_commit(),
         "netlist": str(flow_b.relative_to(ROOT)), "command": [str(x) for x in modified_command],
         "raw_stdout": stdout_b, "samples": samples_b, "summary": summarize(samples_b)}
    return {"label": "same RTL, different synthesis representation and simulator",
            "correctness": correctness,
            "shredded_upstream": a, "preserved_modified": b,
            "speedup": b["summary"]["median_cps"] / a["summary"]["median_cps"]}


def verify_correctness():
    command = [sys.executable, "verif/full_integration_test.py"]
    t0 = time.perf_counter()
    result = run(command, timeout=3600)
    return {"status": "PASS", "command": command,
            "elapsed_seconds": time.perf_counter() - t0,
            "raw_stdout": result.stdout,
            "scope": "production RTL-to-Yosys-to-partitioner-to-CUDA differential regression; "
                     "this gates benchmark publication but is not a per-generated-workload oracle"}


def write_results(payload):
    RESULTS.mkdir(parents=True, exist_ok=True)
    run_id = payload["environment"]["recorded_utc"].replace(":", "-")
    run_dir = RESULTS / "runs" / run_id
    run_dir.mkdir(parents=True)
    raw = json.dumps(payload, indent=2) + "\n"
    (run_dir / "results.json").write_text(raw)
    (RESULTS / "latest.json").write_text(raw)
    rows = []
    for result in payload["results"]:
        s = result["measurement"]["summary"]
        rows.append({"benchmark": result["name"], "cycles": result["cycles"],
                     "implementation": result["measurement"]["implementation"], **s})
    if payload.get("upstream_baseline"):
        s = payload["upstream_baseline"]["summary"]
        rows.append({"benchmark": "boolean_heavy", "cycles": payload["upstream_baseline"]["samples"][0]["cycles"],
                     "implementation": "upstream", **s})
    for path in (run_dir / "summary.csv", RESULTS / "latest.csv"):
        with path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
    if payload.get("upstream_baseline") and payload.get("modified_identical_upstream_workload"):
        baseline = payload["upstream_baseline"]
        modified = payload["modified_identical_upstream_workload"]
        comparison = {
            "benchmark": "boolean_heavy",
            "cycles": baseline["samples"][0]["cycles"],
            "baseline_commit": baseline["commit"],
            "modified_commit": payload["environment"]["commit"],
            "baseline_median_cps": baseline["summary"]["median_cps"],
            "modified_median_cps": modified["summary"]["median_cps"],
            "speedup": payload["boolean_speedup"],
            "percentage_change": (payload["boolean_speedup"] - 1.0) * 100.0,
        }
        for path in (run_dir / "comparison.csv", RESULTS / "comparison.csv"):
            with path.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=comparison.keys())
                writer.writeheader(); writer.writerow(comparison)
    print("results:", RESULTS / "latest.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repetitions", type=int, default=7)
    ap.add_argument("--blocks", type=int, default=4)
    ap.add_argument("--skip-upstream", action="store_true")
    ap.add_argument("--skip-correctness", action="store_true",
                    help="development smoke tests only; final results must not use this")
    ap.add_argument("--only", action="append", help="run only named workload(s)")
    args = ap.parse_args()
    if args.repetitions < 2:
        raise SystemExit("at least two repetitions are required")
    env = environment(); env["cuda_blocks"] = args.blocks
    correctness = None if args.skip_correctness else verify_correctness()
    prepared = prepare(args.only)
    env["cuda_compile_command"] = cuda_compile_command()
    results = []
    for item in prepared:
        measurement = measure_current(item, args.repetitions, args.blocks, item["seed"])
        results.append({**item, "measurement": measurement})
    payload = {"schema_version": 1, "metric_definition": "simulated cycles / synchronized production-kernel elapsed seconds",
               "timing_scope": "one cooperative production simulation launch; excludes parsing, allocation, H2D/D2H, synthesis, partitioning, and output",
               "environment": env, "correctness_gate": correctness,
               "results": results, "upstream_baseline": None,
               "other_pools": "benchmark/other_pools.csv"}
    if not args.skip_upstream:
        boolean = next((item for item in prepared if item["name"] == "boolean_heavy"), None)
        if boolean:
            baseline, modified_zero = measure_boolean_comparison(
                boolean, args.repetitions, args.blocks)
            payload["upstream_baseline"] = baseline
            payload["modified_identical_upstream_workload"] = modified_zero
            payload["boolean_speedup"] = modified_zero["summary"]["median_cps"] / payload["upstream_baseline"]["summary"]["median_cps"]
            payload["macro_representation_experiment"] = measure_macro_representation(
                args.repetitions, args.blocks)
    write_results(payload)


if __name__ == "__main__":
    main()
