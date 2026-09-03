#!/usr/bin/env python3
"""
runner/run_circuit.py
======================
Automated end-to-end GPU simulation runner for ANY arbitrary Verilog/SystemVerilog design.
Executes both:
  1. Original GEM  (Flow A: macros shredded into 1-bit AIG gates)
  2. Modified GEM  (Flow B: macros preserved into native GPU execution)

Usage:
  python3 runner/run_circuit.py <design.sv> [--top <TOP>] [--cycles <N>] [--blocks <B>]
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def find_top_module(verilog_path):
    """Attempt to infer the top-level module name from the file if not provided."""
    text = verilog_path.read_text(errors="ignore")
    modules = re.findall(r'^\s*module\s+([a-zA-Z_][a-zA-Z0-9_]*)', text, re.MULTILINE)
    if not modules:
        return None
    stem = verilog_path.stem
    if stem in modules:
        return stem
    return modules[-1]

def count_netlist_cells(gv_path):
    """Count macro and AIG cells in a structural Verilog file."""
    macros = {"CARRY4": 0, "DSP48E2": 0, "GEM_DSP48E2": 0, "SRLC32E": 0}
    aig_cells = 0
    total = 0
    if not gv_path.exists():
        return {"total": 0, "aig": 0, "macros": macros}
    
    with open(gv_path) as f:
        for line in f:
            m = re.match(r'^\s*([a-zA-Z0-9_]+)\s+[a-zA-Z0-9_]+\s*\(', line)
            if m:
                cell = m.group(1)
                total += 1
                if cell in macros:
                    macros[cell] += 1
                else:
                    aig_cells += 1
    return {"total": total, "aig": aig_cells, "macros": macros}

def run_cmd(cmd, cwd=ROOT):
    """Run command and return stdout, or raise error."""
    res = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {res.returncode}:\n{' '.join(cmd)}\n\nStderr:\n{res.stderr}\n\nStdout:\n{res.stdout}")
    return res.stdout

def synthesize(verilog_file, top_module, out_gv, mode="modified", custom_yosys=None, reuse=False):
    """
    Synthesize design with Yosys.
    mode = 'original' (flatten macros) or 'modified' (preserve macros).
    """
    if reuse and out_gv.exists():
        print(f"   [Reusing pre-existing netlist: {out_gv.name}]")
        return

    yosys_bin = custom_yosys or shutil.which("yosys") or os.environ.get("YOSYS")
    if not yosys_bin:
        for cand in ["/usr/bin/yosys", "/usr/local/bin/yosys", os.path.expanduser("~/.local/bin/yosys")]:
            if os.path.isfile(cand) and os.access(cand, os.X_OK):
                yosys_bin = cand
                break
    if not yosys_bin:
        raise RuntimeError("Yosys is not installed or not found in PATH. Please install Yosys or pass --yosys /path/to/yosys.")

    script_lines = []
    if mode == "original":
        # Read behavioral whitebox models so macros flatten into AIG
        script_lines.append(f"read_verilog -sv {ROOT / 'test3/macros_behavioral.sv'}")
    else:
        # Read blackbox definitions to preserve macros
        script_lines.append(f"read_verilog -lib {ROOT / 'aigpdk/aigpdk_macros_bb.v'}")

    script_lines.append(f"read_verilog -sv {verilog_file}")
    script_lines.append(f"hierarchy -check -top {top_module}")

    if mode == "modified":
        # Map standard Xilinx DSP48E2 to normalized PS subset
        script_lines.append(f"techmap -map {ROOT / 'aigpdk/dsp48e2_ps_map.v'}")

    script_lines.extend([
        "synth -flatten",
        "delete t:$print",
        f"dfflibmap -liberty {ROOT / 'aigpdk/aigpdk_nomem.lib'}",
        "opt_clean -purge",
        f"abc -liberty {ROOT / 'aigpdk/aigpdk_nomem.lib'}",
        "opt_clean -purge",
        "techmap",
        f"abc -liberty {ROOT / 'aigpdk/aigpdk_nomem.lib'}",
        "opt_clean -purge",
        f"write_verilog -noexpr -nodec {out_gv}"
    ])

    ys_file = out_gv.with_suffix(".ys")
    ys_file.write_text("\n".join(script_lines) + "\n")
    run_cmd([yosys_bin, "-q", str(ys_file)])

def main():
    parser = argparse.ArgumentParser(description="Execute arbitrary Verilog/SystemVerilog on GPU via GEM.")
    parser.add_argument("input_file", help="Path to Verilog (.v) or SystemVerilog (.sv) file.")
    parser.add_argument("--top", help="Top-level module name (auto-detected if omitted).")
    parser.add_argument("--cycles", type=int, default=1000, help="Simulation cycles (default: 1000).")
    parser.add_argument("--blocks", type=int, default=4, help="GPU cooperative blocks (default: 4).")
    parser.add_argument("--flow", choices=["both", "original", "modified"], default="both", help="Which flow(s) to run.")
    parser.add_argument("--yosys", help="Path to Yosys binary (default: searches PATH).")
    parser.add_argument("--reuse-netlists", action="store_true", help="Reuse previously synthesized netlists if present.")
    parser.add_argument("--out-dir", default=str(ROOT / "runner/output"), help="Directory for generated artifacts.")
    args = parser.parse_args()

    input_path = Path(args.input_file).resolve()
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}")
        sys.exit(1)

    top = args.top or find_top_module(input_path)
    if not top:
        print(f"Error: Could not automatically determine top module for {input_path}. Please specify with --top <NAME>.")
        sys.exit(1)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "="*70)
    print(f"  GEM AUTOMATED GPU SIMULATION RUNNER")
    print(f"  Source File : {input_path.name}")
    print(f"  Top Module  : {top}")
    print(f"  Sim Cycles  : {args.cycles:,}")
    print(f"  GPU Blocks  : {args.blocks}")
    print("="*70 + "\n")

    # Ensure cargo binaries are built
    bin_cut = ROOT / "target/release/cut_map_interactive"
    bin_sim = ROOT / "target/release/cuda_dummy_test"
    if not (bin_cut.exists() and bin_sim.exists()):
        print(">> Building GEM release binaries (cargo build --release --features cuda)...")
        run_cmd(["cargo", "build", "--release", "--features", "cuda"])

    results = {}
    flows_to_run = ["original", "modified"] if args.flow == "both" else [args.flow]

    for flow in flows_to_run:
        label = "Flow A (Original GEM - Shredded)" if flow == "original" else "Flow B (Modified GEM - Preserved)"
        print(f">> Executing {label}...")
        
        gv_file = out_dir / f"{top}_{flow}.gv"
        parts_file = out_dir / f"{top}_{flow}.gemparts"

        # 1. Synthesis
        t0 = time.time()
        synthesize(input_path, top, gv_file, mode=flow, custom_yosys=args.yosys, reuse=args.reuse_netlists)
        synth_sec = time.time() - t0

        # 2. Partitioning
        t1 = time.time()
        run_cmd([str(bin_cut), str(gv_file), str(parts_file), "--top-module", top])
        part_sec = time.time() - t1

        # 3. Cell counts
        stats = count_netlist_cells(gv_file)

        # 4. GPU Simulation
        sim_stdout = run_cmd([
            str(bin_sim),
            str(gv_file),
            str(parts_file),
            str(args.blocks),
            str(args.cycles),
            "--top-module", top,
            "--warmup-runs", "3",
            "--repetitions", "5"
        ])

        cps_matches = [float(x.replace(",", "")) for x in re.findall(r'cycles_per_second=([0-9,.]+)', sim_stdout)]
        cps = sum(cps_matches) / len(cps_matches) if cps_matches else 0.0

        results[flow] = {
            "stats": stats,
            "synth_sec": synth_sec,
            "part_sec": part_sec,
            "cps": cps,
            "gv": gv_file
        }
        print(f"   -> Done. Netlist: {stats['total']} cells | Throughput: {cps:,.0f} cycles/s\n")

    # Display comparison
    print("="*70)
    print("  FINAL SIMULATION RESULTS & COMPARISON")
    print("="*70)
    
    if "original" in results and "modified" in results:
        a = results["original"]
        b = results["modified"]
        cell_diff = a["stats"]["total"] - b["stats"]["total"]
        pct_red = (cell_diff / a["stats"]["total"] * 100) if a["stats"]["total"] else 0
        speedup = (b["cps"] / a["cps"]) if a["cps"] > 0 else 1.0

        print(f"  {'Metric':<32} {'Flow A (Original)':>16} {'Flow B (Modified)':>16}")
        print(f"  {'-'*32} {'-'*16} {'-'*16}")
        print(f"  {'Total Cells':<32} {a['stats']['total']:>16,} {b['stats']['total']:>16,}")
        print(f"  {'AIG Boolean Gates':<32} {a['stats']['aig']:>16,} {b['stats']['aig']:>16,}")
        
        for m_name in ["CARRY4", "DSP48E2", "SRLC32E"]:
            m_a = a["stats"]["macros"].get(m_name, 0)
            m_b = b["stats"]["macros"].get(m_name, 0) + (b["stats"]["macros"].get("GEM_DSP48E2", 0) if m_name == "DSP48E2" else 0)
            if m_a > 0 or m_b > 0:
                print(f"  {f'Preserved {m_name} Macros':<32} {m_a:>16} {m_b:>16}")

        print(f"  {'-'*32} {'-'*16} {'-'*16}")
        print(f"  {'Gate Reduction':<32} {'--':>16} {f'{pct_red:.1f}% fewer':>16}")
        print(f"  {'GPU Throughput (cycles/s)':<32} {a['cps']:>16,.0f} {b['cps']:>16,.0f}")
        print(f"  {'Throughput Speedup':<32} {'1.00x (baseline)':>16} {f'{speedup:.2f}x':>16}")
        print("="*70)
        print(f"  Artifacts written to: {out_dir}\n")
    else:
        for flow, res in results.items():
            print(f"  Flow: {flow.upper()}")
            print(f"  Total Cells       : {res['stats']['total']:,}")
            print(f"  GPU Throughput    : {res['cps']:,.0f} cycles/s")
        print("="*70 + "\n")

if __name__ == "__main__":
    main()

