#!/usr/bin/env python3
"""
benchmark/legacy/flow1_microbench.py
Flow 1: GPU CUDA Device Micro-Benchmark Suite for Deliverable D.
- Measures raw hardware kernel execution speed of native 64-bit CUDA device functions (gem_macros.cuh)
  vs 1-bit boolean loop simulation on NVIDIA GPU.
- Sweeps batch sizes N in [1K, 10K, 100K, 1M]
- Sweeps clock cycles C in [1, 8, 64, 256]
"""

import os
import sys
import subprocess
import csv
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
GEM_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TEMP_DIR = os.path.join(GEM_ROOT, "benchmark", "temporary", "legacy")
ENGINE_BIN = os.path.join(TEMP_DIR, "bench_engine")
CSV_MICRO = os.path.join(TEMP_DIR, "flow1_microbench.csv")

def cuda_arch():
    override = os.environ.get("GEM_CUDA_ARCH")
    if override:
        return override
    try:
        cap = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=compute_cap", "--format=csv,noheader"],
            text=True, stderr=subprocess.DEVNULL).splitlines()[0].strip()
        major, minor = cap.split(".", 1)
        if major.isdigit() and minor.isdigit():
            return f"sm_{major}{minor}"
    except (OSError, subprocess.SubprocessError, IndexError, ValueError):
        pass
    return "compute_75"

def run_cmd(cmd, cwd=GEM_ROOT):
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    return p.returncode, p.stdout, p.stderr

def build_engine():
    print("=== Flow 1: Compiling CUDA Device Micro-Benchmark Engine ===")
    os.makedirs(TEMP_DIR, exist_ok=True)
    arch = cuda_arch()
    nvcc = shutil.which("nvcc") or os.path.join(os.environ.get("CUDA_HOME", "/usr/local/cuda"), "bin", "nvcc")
    cmd = (
        f"{nvcc} -O3 -std=c++17 -arch={arch} -Xptxas -v "
        f"-I{GEM_ROOT}/csrc {HERE}/bench_engine.cu -o {ENGINE_BIN}"
    )
    rc, out, err = run_cmd(cmd)
    if rc != 0:
        print(f"Error compiling bench_engine:\n{err}")
        sys.exit(1)
    print(f"Compilation successful (target {arch}).")
    return err

def run_flow1(batch_sizes=None, cycles_list=None):
    print("\n=== Flow 1: Running GPU CUDA Device Micro-Benchmark Sweeps ===")
    if os.path.exists(CSV_MICRO):
        os.remove(CSV_MICRO)

    with open(CSV_MICRO, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Macro", "BatchSize_N", "Cycles_C", "Baseline_ms", "Macro_ms", "Speedup", "Throughput_MEvals_sec"])

    if batch_sizes is None:
        batch_sizes = [1000, 10000, 100000, 1000000]
    if cycles_list is None:
        cycles_list = [1, 8, 64, 256]

    for n in batch_sizes:
        for c in cycles_list:
            print(f"  [Flow 1] Sweeping N={n:,}, Cycles={c}...")
            cmd = f"{ENGINE_BIN} --n {n} --cycles {c} --csv {CSV_MICRO}"
            rc, out, err = run_cmd(cmd)
            if rc != 0:
                print(f"Failed at N={n}, C={c}: {err}")

    print(f"Flow 1 complete. Results saved to {CSV_MICRO}")

if __name__ == "__main__":
    build_engine()
    run_flow1()
