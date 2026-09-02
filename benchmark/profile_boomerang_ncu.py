#!/usr/bin/env python3
"""Profile the production heterogeneous Boomerang kernel with Nsight Compute.

The script uses the exact-chain integration artifacts produced by
verif/full_integration_test.py.  It never substitutes a micro-kernel.  A
counter-permission failure is recorded explicitly and returns exit status 2.
"""
import argparse
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
METRICS = [
    "sm__warps_active.avg.pct_of_peak_sustained_active",
    "smsp__sass_average_branch_targets_threads_uniform.pct",
    "gpu__dram_throughput.avg.pct_of_peak_sustained_elapsed",
    "l1tex__average_t_sectors_per_request_pipe_lsu_mem_global_op_ld.ratio",
    "l1tex__average_t_sectors_per_request_pipe_lsu_mem_global_op_st.ratio",
]


def run(cmd, **kwargs):
    print("+", " ".join(map(str, cmd)), flush=True)
    return subprocess.run([str(x) for x in cmd], cwd=ROOT, **kwargs)


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-prepare", action="store_true")
    ap.add_argument("--output", default="benchmark/nsight_boomerang.csv")
    args = ap.parse_args()
    status = ROOT / "benchmark/nsight_boomerang_status.md"
    output_path = pathlib.Path(args.output)
    if not output_path.is_absolute():
        output_path = ROOT / output_path
    if shutil.which("ncu") is None:
        status.write_text("# Nsight Boomerang Profile\n\nBLOCKED: `ncu` is not installed.\n")
        print("BLOCKED: ncu is not installed")
        return 2
    if not args.skip_prepare:
        prepare()
    command = [
        "ncu", "--target-processes", "all", "--kernel-name-base", "demangled",
        "--kernel-name", "regex:simulate_v1_noninteractive_simple_scan.*",
        "--metrics", ",".join(METRICS), "--csv", "--page", "raw",
        "target/release/cuda_test", "/tmp/gem_exact_chain.gv",
        "/tmp/gem_exact_chain.gemparts", "/tmp/gem_exact_chain_golden.vcd",
        "/tmp/gem_exact_chain_ncu.vcd", "1", "--top-module", "exact_macro_chain",
        "--input-vcd-scope", "tb_exact_macro_chain/dut",
    ]
    result = run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = result.stdout
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
    missing = [metric for metric in METRICS if metric not in output]
    if missing:
        status.write_text("# Nsight Boomerang Profile\n\nFAILED: missing counters: " + ", ".join(missing) + "\n")
        return 1
    status.write_text(
        "# Nsight Boomerang Profile\n\nVERIFIED on the production exact-chain kernel.\n\n"
        f"Raw counters: [{args.output}]({output_path.name})\n",
        encoding="utf-8",
    )
    print("PASS: production Boomerang Nsight counters captured in", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
