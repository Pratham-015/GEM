#!/usr/bin/env python3
"""Profile the production heterogeneous Boomerang kernel with Nsight Compute.

The script uses the exact-chain integration artifacts produced by
verif/full_integration_test.py.  It never substitutes a micro-kernel.  A
counter-permission failure is recorded explicitly and returns exit status 2.
"""
import argparse
import csv
import datetime
import hashlib
import io
import json
import pathlib
import shutil
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
CANDIDATE_METRICS = [
    "sm__warps_active.avg.pct_of_peak_sustained_active",
    "sm__sass_average_branch_targets_threads_uniform.pct",
    "sm__average_thread_inst_executed_pred_on_per_inst_executed_realtime.pct",
    "sm__sass_branch_targets_threads_divergent.sum",
    "sm__sass_branch_targets_threads_uniform.sum",
    "dram__throughput.avg.pct_of_peak_sustained_elapsed",
    "dram__bytes.sum",
    "dram__bytes.sum.per_second",
    "l1tex__average_t_sectors_per_request_pipe_lsu_mem_global_op_ld.ratio",
    "l1tex__average_t_sectors_per_request_pipe_lsu_mem_global_op_st.ratio",
    "gpu__time_duration.sum",
]
EXTRA_COLUMNS = [
    "sm__maximum_warps_per_active_cycle_pct",
    "launch__grid_size", "launch__block_size", "launch__registers_per_thread",
    "launch__shared_mem_per_block", "launch__shared_mem_per_block_static",
    "launch__occupancy_limit_registers", "launch__occupancy_limit_shared_mem",
    "launch__occupancy_limit_warps", "launch__waves_per_multiprocessor",
]


def display_path(path):
    """Return a stable repo-relative path when possible."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def require_files(paths, hint):
    missing = [display_path(path) for path in paths if not path.exists()]
    if missing:
        raise SystemExit(
            "--skip-prepare requested, but required files are missing: "
            + ", ".join(missing) + f". {hint}"
        )


def supported_metrics():
    outputs = []
    for attempt in range(3):
        query = run(["ncu", "--query-metrics-mode", "all", "--devices", "0"],
                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        outputs.append(query.stdout)
        if query.returncode == 0:
            available = set()
            for line in query.stdout.splitlines():
                token = line.strip().split()[0] if line.strip() else ""
                if "__" in token:
                    available.add(token.rstrip(","))
            metrics = [metric for metric in CANDIDATE_METRICS if metric in available]
            if metrics:
                return metrics, "\n".join(outputs)
        if attempt != 2:
            time.sleep(1)
    return [], "\n".join(outputs)


def sha256_file(path):
    digest = hashlib.sha256()
    with pathlib.Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_raw_csv(output):
    lines = output.splitlines()
    header = next((i for i, line in enumerate(lines)
                   if line.startswith('"ID","Process ID"')), None)
    if header is None:
        return []
    table = list(csv.reader(io.StringIO("\n".join(lines[header:]))))
    if len(table) < 3:
        return []
    columns, units = table[0], table[1]
    indices = {name: i for i, name in enumerate(columns)}
    kernel_i = indices.get("Kernel Name")
    rows = []
    for data in table[2:]:
        if len(data) != len(columns) or not data or not data[0].isdigit():
            continue
        for metric in CANDIDATE_METRICS + EXTRA_COLUMNS:
            index = indices.get(metric)
            if index is not None and data[index] != "":
                rows.append({"kernel": data[kernel_i] if kernel_i is not None else None,
                             "metric": metric, "unit": units[index],
                             "value": data[index]})
    return rows


def run(cmd, **kwargs):
    print("+", " ".join(map(str, cmd)), flush=True)
    return subprocess.run([str(x) for x in cmd], cwd=ROOT, **kwargs)


def numeric_values(values):
    parsed = {}
    for row in values:
        try:
            parsed[row["metric"]] = float(row["value"].replace(",", ""))
        except ValueError:
            pass
    return parsed


def prepare():
    run([sys.executable, "scripts/synthesize_macros.py", "--top", "exact_macro_chain",
         "--output", "/tmp/gem_exact_chain.gv", "--json", "/tmp/gem_exact_chain.json",
         "verif/rtl/test_designs/exact_macro_chain.sv"], check=True)
    run(["iverilog", "-g2012", "-DGOLDEN", "-s", "tb_exact_macro_chain",
         "-o", "/tmp/gem_exact_chain_ref.out", "verif/rtl/xilinx_macros_ref.v",
         "verif/rtl/test_designs/exact_macro_chain.sv",
         "verif/tb/tb_exact_macro_chain.sv"], check=True)
    run(["vvp", "/tmp/gem_exact_chain_ref.out"], check=True)
    run(["cargo", "build", "--release", "--features", "cuda",
         "--bin", "cut_map_interactive", "--bin", "cuda_test"], check=True)
    run(["target/release/cut_map_interactive", "/tmp/gem_exact_chain.gv",
         "/tmp/gem_exact_chain.gemparts", "--top-module", "exact_macro_chain"], check=True)


def prepare_generated(name):
    workloads = ROOT / "benchmark/generated/workloads"
    artifacts = ROOT / "benchmark/generated/artifacts"
    workloads.mkdir(parents=True, exist_ok=True)
    artifacts.mkdir(parents=True, exist_ok=True)
    run([sys.executable, "benchmark/workloads/generate_workloads.py",
         "--output-dir", workloads], check=True)
    manifest = json.loads((workloads / "manifest.json").read_text())
    item = next(item for item in manifest if item["name"] == name)
    source = pathlib.Path(item["source"])
    if not source.is_absolute():
        source = ROOT / source
    gv, js, parts = (artifacts / f"{name}.gv", artifacts / f"{name}.json",
                     artifacts / f"{name}.gemparts")
    run([sys.executable, "scripts/synthesize_macros.py", "--top", item["top"],
         "--output", gv, "--json", js, source], check=True)
    run(["cargo", "build", "--release", "--features", "cuda", "--bin",
         "cut_map_interactive", "--bin", "cuda_dummy_test"], check=True)
    run(["target/release/cut_map_interactive", gv, parts,
         "--top-module", item["top"]], check=True)
    return item, gv, parts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-prepare", action="store_true")
    ap.add_argument("--workload", choices=["exact-chain", "mixed_heterogeneous", "large_scale",
                                            "occupancy_stress"],
                    default="exact-chain")
    ap.add_argument("--blocks", type=int,
                    help="cooperative CUDA grid size (generated workloads only)")
    ap.add_argument("--parts", help="override generated-workload .gemparts file")
    ap.add_argument("--profile-name", help="output stem for a controlled profile variant")
    ap.add_argument("--output")
    args = ap.parse_args()
    stem = args.profile_name or ("boomerang" if args.workload == "exact-chain" else args.workload)
    status = ROOT / f"benchmark/nsight_{stem}_status.md"
    output_path = pathlib.Path(args.output or f"benchmark/nsight_{stem}.csv")
    if not output_path.is_absolute():
        output_path = ROOT / output_path
    if shutil.which("ncu") is None:
        status.write_text("# Nsight Boomerang Profile\n\nBLOCKED: `ncu` is not installed.\n")
        print("BLOCKED: ncu is not installed")
        return 2
    if args.workload == "exact-chain":
        if args.blocks is not None or args.parts is not None:
            raise SystemExit("--blocks/--parts are only supported for generated workloads")
        if not args.skip_prepare:
            prepare()
        else:
            require_files(
                [ROOT / "target/release/cuda_test", pathlib.Path("/tmp/gem_exact_chain.gv"),
                 pathlib.Path("/tmp/gem_exact_chain.gemparts"),
                 pathlib.Path("/tmp/gem_exact_chain_golden.vcd")],
                "Run without --skip-prepare first.",
            )
        application = ["target/release/cuda_test", "/tmp/gem_exact_chain.gv",
                       "/tmp/gem_exact_chain.gemparts", "/tmp/gem_exact_chain_golden.vcd",
                       "/tmp/gem_exact_chain_ncu.vcd", "1", "--top-module", "exact_macro_chain",
                       "--input-vcd-scope", "tb_exact_macro_chain/dut"]
    else:
        if args.skip_prepare:
            manifest = json.loads((ROOT / "benchmark/generated/workloads/manifest.json").read_text())
            item = next(item for item in manifest if item["name"] == args.workload)
            gv = ROOT / f"benchmark/generated/artifacts/{args.workload}.gv"
            parts = ROOT / f"benchmark/generated/artifacts/{args.workload}.gemparts"
            if args.parts:
                parts = pathlib.Path(args.parts).resolve()
            require_files([ROOT / "target/release/cuda_dummy_test", gv, parts],
                          "Run without --skip-prepare first.")
        else:
            item, gv, parts = prepare_generated(args.workload)
        blocks = args.blocks if args.blocks is not None else (
            16 if args.workload == "occupancy_stress" else 4)
        application = ["target/release/cuda_dummy_test", gv, parts, str(blocks), str(item["cycles"]),
                       "--top-module", item["top"], "--warmup-runs", "0",
                       "--repetitions", "1", "--seed", str(item["seed"])]
    metrics, query_output = supported_metrics()
    if not metrics:
        if "ERR_NVGPUCTRPERM" in query_output:
            status.write_text(
                "# Nsight Boomerang Profile\n\nBLOCKED: `ERR_NVGPUCTRPERM` prevents metric discovery and collection.\n\n"
                "IMPACT: production-kernel occupancy, warp divergence, bandwidth, and coalescing remain unmeasured.\n\n"
                "REQUIRED ACTION: enable NVIDIA performance counters and run `python3 benchmark/profile_boomerang_ncu.py`.\n")
            print("BLOCKED: ERR_NVGPUCTRPERM during metric discovery")
            return 2
        status.write_text("# Nsight Boomerang Profile\n\nFAILED: none of the requested metrics are supported.\n")
        print("FAILED: no supported requested metrics")
        return 1
    command = [
        "ncu", "--target-processes", "all", "--kernel-name-base", "demangled",
        "--kernel-name", "regex:simulate_v1_noninteractive_simple_scan.*",
        "--metrics", ",".join(metrics), "--csv", "--page", "raw",
        *application,
    ]
    result = run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = result.stdout
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output, encoding="utf-8")
    if "ERR_NVGPUCTRPERM" in output:
        # The profiler output contains only application logs and the permission
        # error, not counter data.  Keep the concise status report instead of
        # leaving a misleading file named *.csv.
        output_path.unlink(missing_ok=True)
        status.write_text(
            "# Nsight Boomerang Profile\n\n"
            "BLOCKED: `ERR_NVGPUCTRPERM` prevents performance-counter access.\n\n"
            "IMPACT: warp occupancy, branch uniformity, DRAM utilization, and "
            "global-load/store sectors per request remain unmeasured.\n\n"
            "REQUIRED ACTION: enable non-admin NVIDIA performance counters, then run:\n\n"
            "```shell\npython3 benchmark/profile_boomerang_ncu.py\n```\n",
            encoding="utf-8",
        )
        print("BLOCKED: ERR_NVGPUCTRPERM (details in benchmark/nsight_boomerang_status.md)")
        return 2
    if result.returncode != 0:
        status.write_text(f"# Nsight Boomerang Profile\n\nFAILED (exit {result.returncode}).\n\n```\n{output[-4000:]}\n```\n")
        return result.returncode
    missing = [metric for metric in metrics if metric not in output]
    if missing:
        status.write_text("# Nsight Boomerang Profile\n\nFAILED: missing counters: " + ", ".join(missing) + "\n")
        return 1
    values = parse_raw_csv(output)
    found = {row["metric"] for row in values}
    missing_values = [metric for metric in metrics if metric not in found]
    if missing_values:
        status.write_text("# Nsight Boomerang Profile\n\nFAILED: raw CSV did not contain values for: "
                          + ", ".join(missing_values) + "\n")
        return 1
    kernel_names = sorted({row["kernel"] for row in values})
    if len(kernel_names) != 1 or "simulate_v1_noninteractive_simple_scan" not in kernel_names[0]:
        status.write_text("# Nsight Boomerang Profile\n\nFAILED: counters are not from exactly one production kernel.\n")
        return 1
    metadata = {"metrics": metrics, "values": values,
                "raw_csv": display_path(output_path),
                "command": [str(part) for part in command]}
    nums = numeric_values(values)
    divergent = nums.get("sm__sass_branch_targets_threads_divergent.sum", 0.0)
    uniform = nums.get("sm__sass_branch_targets_threads_uniform.sum", 0.0)
    divergent_pct = 100.0 * divergent / (divergent + uniform) if divergent + uniform else 0.0
    summary = {
        "achieved_occupancy_percent": nums.get("sm__warps_active.avg.pct_of_peak_sustained_active"),
        "uniform_branch_targets_percent": nums.get("sm__sass_average_branch_targets_threads_uniform.pct"),
        "derived_divergent_branch_targets_percent": divergent_pct,
        "predicated_thread_utilization_percent": nums.get("sm__average_thread_inst_executed_pred_on_per_inst_executed_realtime.pct"),
        "dram_peak_utilization_percent": nums.get("dram__throughput.avg.pct_of_peak_sustained_elapsed"),
        "dram_bytes": nums.get("dram__bytes.sum"),
        "dram_bytes_per_second": nums.get("dram__bytes.sum.per_second"),
        "global_load_sectors_per_request": nums.get("l1tex__average_t_sectors_per_request_pipe_lsu_mem_global_op_ld.ratio"),
        "global_store_sectors_per_request": nums.get("l1tex__average_t_sectors_per_request_pipe_lsu_mem_global_op_st.ratio"),
        "kernel_duration_ns": nums.get("gpu__time_duration.sum"),
        "theoretical_occupancy_percent": nums.get("sm__maximum_warps_per_active_cycle_pct"),
        "grid_blocks": nums.get("launch__grid_size"),
        "threads_per_block": nums.get("launch__block_size"),
        "registers_per_thread": nums.get("launch__registers_per_thread"),
        "shared_memory_per_block_bytes": nums.get("launch__shared_mem_per_block"),
        "resident_block_limit_registers": nums.get("launch__occupancy_limit_registers"),
        "resident_block_limit_shared_memory": nums.get("launch__occupancy_limit_shared_mem"),
        "resident_block_limit_warps": nums.get("launch__occupancy_limit_warps"),
        "waves_per_sm": nums.get("launch__waves_per_multiprocessor"),
    }
    metadata["summary"] = summary
    metadata["workload"] = args.workload
    metadata["profiled_kernel"] = kernel_names[0]
    metadata["environment"] = {
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "dirty": bool(subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
        "ncu": subprocess.check_output(["ncu", "--version"], text=True).strip(),
        "gpu": subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,driver_version,compute_cap",
             "--format=csv,noheader"], text=True).strip(),
    }
    metadata["sha256"] = {
        "raw_csv": sha256_file(output_path),
        "kernel_source": sha256_file(ROOT / "csrc/kernel_v1_impl.cuh"),
        "macro_source": sha256_file(ROOT / "csrc/gem_macros.cuh"),
        "executable": sha256_file(ROOT / application[0]),
    }
    metadata_path = ROOT / f"benchmark/nsight_{stem}.json"
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
    status.write_text(
        f"# Nsight {args.workload} Profile\n\nVERIFIED on the production simulator kernel.\n\n"
        f"- Achieved occupancy: `{summary['achieved_occupancy_percent']:.2f}%`\n"
        f"- Theoretical occupancy: `{summary['theoretical_occupancy_percent']:.2f}%`\n"
        f"- Launch: `{summary['grid_blocks']:.0f}` blocks x `{summary['threads_per_block']:.0f}` threads, `{summary['waves_per_sm']:.2f}` waves/SM\n"
        f"- Resources: `{summary['registers_per_thread']:.0f}` registers/thread, `{summary['shared_memory_per_block_bytes']:.0f}` shared bytes/block\n"
        f"- Uniform branch targets: `{summary['uniform_branch_targets_percent']:.2f}%`\n"
        f"- Derived divergent branch targets: `{summary['derived_divergent_branch_targets_percent']:.2f}%`\n"
        f"- Predicated-on threads per instruction: `{summary['predicated_thread_utilization_percent']:.2f}%`\n"
        f"- DRAM peak utilization: `{summary['dram_peak_utilization_percent']:.2f}%`\n"
        f"- DRAM bandwidth: `{summary['dram_bytes_per_second']/1e6:.2f} MB/s`\n"
        f"- Global load/store sectors per request: `{summary['global_load_sectors_per_request']:.2f}` / `{summary['global_store_sectors_per_request']:.2f}`\n"
        f"- Profiled kernel duration: `{summary['kernel_duration_ns']/1e6:.3f} ms`\n\n"
        f"Metrics: `{', '.join(metrics)}`\n\nRaw counters: [{output_path.relative_to(ROOT)}]({output_path.name})\n",
        encoding="utf-8",
    )
    print("PASS: production Nsight counters captured in", display_path(output_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
