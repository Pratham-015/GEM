#!/usr/bin/env python3
"""
benchmark/flow2_pipeline_bench.py
Flow 2: Full End-to-End GEM Pipeline Benchmark.
- Uses real GEM binaries (cut_map_interactive + cuda_test).
- Compares:
  * Flow A (Legacy Shredded Netlist): test3/flowA_baseline_flatten_gatelevel.gv
  * Flow B (Macro-Augmented GEM): test3/flowB_macropreserve_gatelevel.gv (66 macro-preserved cells)
- Measures:
  * Netlist cell counts & script binary size
  * Host hypergraph partitioning time
  * CUDA GPU kernel simulation time & speedup
"""

import os
import sys
import time
import subprocess
import csv
import re

HERE = os.path.dirname(os.path.abspath(__file__))
GEM_ROOT = os.path.abspath(os.path.join(HERE, ".."))
SIM_OUT = os.path.join(GEM_ROOT, "verif", "sim_out")
CSV_PIPELINE = os.path.join(HERE, "flow2_pipeline_bench.csv")

def run_cmd(cmd, cwd=GEM_ROOT):
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    return p.returncode, p.stdout, p.stderr

def build_gem_binaries():
    print("=== Flow 2: Building Release GEM Binaries (cuda_test, cut_map_interactive) ===")
    cmd = "cargo build --release --features cuda --bin cut_map_interactive --bin cuda_test"
    rc, out, err = run_cmd(cmd)
    if rc != 0:
        print(f"Error building GEM binaries:\n{err}")
        sys.exit(1)
    print("Build successful.")

def generate_stimulus_vcd(num_cycles=64):
    print(f"=== Flow 2: Generating Stimulus VCD for {num_cycles} cycles ===")
    tb_file = os.path.join(HERE, "tb_signal_processor_stim.sv")
    vcd_path = os.path.join(SIM_OUT, "signal_processor_stim.vcd")
    sim_out = os.path.join(SIM_OUT, "sim_sp.out")

    # Update cycles in testbench if needed
    with open(tb_file, "r") as f:
        tb_content = f.read()
    tb_content = re.sub(r'cycle < \d+', f'cycle < {num_cycles}', tb_content)
    with open(tb_file, "w") as f:
        f.write(tb_content)

    compile_cmd = (
        f"iverilog -g2012 {GEM_ROOT}/test3/macros_behavioral.sv "
        f"{GEM_ROOT}/test3/signal_processor.sv {tb_file} -o {sim_out}"
    )
    rc, out, err = run_cmd(compile_cmd)
    if rc != 0:
        print(f"Error compiling stimulus testbench:\n{err}")
        sys.exit(1)

    rc, out, err = run_cmd(f"vvp {sim_out}")
    if rc != 0:
        print(f"Error running stimulus simulation:\n{err}")
        sys.exit(1)
    print(f"Stimulus generated at {vcd_path}")
    return vcd_path

def run_pipeline_flow(netlist_path, parts_path, vcd_in, vcd_out, label="Flow"):
    print(f"\n--- Running {label}: {os.path.basename(netlist_path)} ---")
    
    # 1. Hypergraph Cut Partitioning
    t0_part = time.perf_counter()
    part_cmd = f"{GEM_ROOT}/target/release/cut_map_interactive {netlist_path} {parts_path}"
    rc, out_part, err_part = run_cmd(part_cmd)
    t1_part = time.perf_counter()
    part_time_ms = (t1_part - t0_part) * 1000.0

    if rc != 0:
        print(f"Error in cut_map_interactive for {label}:\n{err_part}")
        sys.exit(1)

    # 2. CUDA GPU Simulation
    t0_sim = time.perf_counter()
    sim_cmd = (
        f"{GEM_ROOT}/target/release/cuda_test {netlist_path} {parts_path} "
        f"{vcd_in} {vcd_out} 32 --input-vcd-scope tb_signal_processor_stim/dut"
    )
    rc, out_sim, err_sim = run_cmd(sim_cmd)
    t1_sim = time.perf_counter()
    total_time_ms = (t1_sim - t0_sim) * 1000.0

    if rc != 0:
        print(f"Error in cuda_test for {label}:\n{err_sim}\n{out_sim}")
        sys.exit(1)

    # Parse simulation elapsed time from output logs
    gpu_sim_time_ms = 0.0
    m_time = re.search(r'simulation, Elapsed=([\d\.]+)ms', out_sim + err_sim)
    if m_time:
        gpu_sim_time_ms = float(m_time.group(1))

    # Parse script size from output logs
    script_size = 0
    m_script = re.search(r'script size (\d+)', out_sim + err_sim)
    if m_script:
        script_size = int(m_script.group(1))

    print(f"  {label} Partitioning: {part_time_ms:.2f} ms")
    print(f"  {label} Script Size:   {script_size:,} bytes")
    print(f"  {label} GPU Sim Time:  {gpu_sim_time_ms:.3f} ms (Total Wall: {total_time_ms:.2f} ms)")

    return {
        "part_time_ms": part_time_ms,
        "gpu_sim_time_ms": gpu_sim_time_ms,
        "total_time_ms": total_time_ms,
        "script_size": script_size
    }

def run_flow2(num_cycles=64):
    build_gem_binaries()
    vcd_in = generate_stimulus_vcd(num_cycles=num_cycles)

    flowA_netlist = os.path.join(GEM_ROOT, "test3", "flowA_baseline_flatten_gatelevel.gv")
    flowA_parts = os.path.join(SIM_OUT, "flowA.gemparts")
    flowA_vcd = os.path.join(SIM_OUT, "flowA_out.vcd")

    flowB_netlist = os.path.join(GEM_ROOT, "test3", "flowB_macropreserve_gatelevel.gv")
    flowB_parts = os.path.join(SIM_OUT, "flowB.gemparts")
    flowB_vcd = os.path.join(SIM_OUT, "flowB_out.vcd")

    resA = run_pipeline_flow(flowA_netlist, flowA_parts, vcd_in, flowA_vcd, label="Flow A (Baseline Flatten)")
    resB = run_pipeline_flow(flowB_netlist, flowB_parts, vcd_in, flowB_vcd, label="Flow B (Macro Preserved)")

    speedup_gpu = resA["gpu_sim_time_ms"] / resB["gpu_sim_time_ms"] if resB["gpu_sim_time_ms"] > 0 else 0.0
    speedup_total = resA["total_time_ms"] / resB["total_time_ms"] if resB["total_time_ms"] > 0 else 0.0
    script_reduction = (1.0 - resB["script_size"] / resA["script_size"]) * 100.0 if resA["script_size"] > 0 else 0.0

    print("\n" + "=" * 60)
    print("FLOW 2: END-TO-END GEM PIPELINE BENCHMARK SUMMARY")
    print("=" * 60)
    print(f"  Stimulus Cycles:             {num_cycles}")
    print(f"  Flow A Script Size:          {resA['script_size']:,} bytes (5,616 AIG gates)")
    print(f"  Flow B Script Size:          {resB['script_size']:,} bytes (66 cells)")
    print(f"  GPU Script Size Reduction:   {script_reduction:.1f}%")
    print(f"  Flow A GPU Sim Time:         {resA['gpu_sim_time_ms']:.3f} ms")
    print(f"  Flow B GPU Sim Time:         {resB['gpu_sim_time_ms']:.3f} ms")
    print(f"  GPU SIMULATION RATIO:        {speedup_gpu:.2f}x (not an upstream-baseline claim)")
    print(f"  TOTAL WALL-CLOCK SPEEDUP:    {speedup_total:.2f}x")
    print("=" * 60)

    # Save to CSV
    with open(CSV_PIPELINE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Metric", "FlowA_Baseline", "FlowB_MacroPreserve", "Speedup_or_Reduction"])
        writer.writerow(["Cycles", num_cycles, num_cycles, "-"])
        writer.writerow(["ScriptSizeBytes", resA["script_size"], resB["script_size"], f"{script_reduction:.1f}% reduction"])
        writer.writerow(["PartitionTime_ms", f"{resA['part_time_ms']:.2f}", f"{resB['part_time_ms']:.2f}", f"{resA['part_time_ms']/resB['part_time_ms']:.2f}x"])
        writer.writerow(["GPUSimTime_ms", f"{resA['gpu_sim_time_ms']:.3f}", f"{resB['gpu_sim_time_ms']:.3f}", f"{speedup_gpu:.2f}x"])
        writer.writerow(["TotalWallTime_ms", f"{resA['total_time_ms']:.2f}", f"{resB['total_time_ms']:.2f}", f"{speedup_total:.2f}x"])

    print(f"Flow 2 results written to {CSV_PIPELINE}")

if __name__ == "__main__":
    run_flow2()
