#!/usr/bin/env python3
"""RTL -> Yosys 0.68 -> GEM graph -> Boomerang/CUDA -> RTL differential."""
import os
import json
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def run(cmd):
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)


def main():
    version = subprocess.check_output(["yosys", "-V"], text=True).strip()
    if not version.startswith("Yosys 0.68 "):
        raise RuntimeError(f"required Yosys 0.68, found: {version}")
    run([sys.executable, "scripts/synthesize_macros.py",
         "--top", "integrated_macro_top",
         "--output", "/tmp/gem_integrated_gatelevel.gv",
         "--json", "/tmp/gem_integrated_gatelevel.json",
         "verif/rtl/test_designs/integrated_macro_top.sv"])
    with open("/tmp/gem_integrated_gatelevel.json", encoding="utf-8") as f:
        netlist = json.load(f)
    cells = netlist["modules"]["integrated_macro_top"]["cells"]
    counts = {}
    for cell in cells.values():
        counts[cell["type"]] = counts.get(cell["type"], 0) + 1
    required = {"CARRY4": 16, "GEM_DSP48E2": 1, "SRLC32E": 1}
    for kind, expected in required.items():
        if counts.get(kind, 0) != expected:
            raise AssertionError(
                f"macro preservation failed for {kind}: expected {expected}, "
                f"found {counts.get(kind, 0)}; cell histogram={counts}")
    print("PASS: Yosys JSON preserves exact macro identities", required)
    run(["iverilog", "-g2012", "-DGOLDEN", "-s", "tb_integrated_macro_top",
         "-o", "/tmp/gem_integrated_ref.out", "verif/rtl/xilinx_macros_ref.v",
         "verif/rtl/test_designs/integrated_macro_top.sv",
         "verif/tb/tb_integrated_macro_top.sv"])
    run(["vvp", "/tmp/gem_integrated_ref.out"])
    run(["cargo", "build", "--release", "--features", "cuda",
         "--bin", "cut_map_interactive", "--bin", "cuda_test"])
    run(["target/release/cut_map_interactive", "/tmp/gem_integrated_gatelevel.gv",
         "/tmp/gem_integrated.gemparts", "--top-module", "integrated_macro_top"])
    for blocks in (1, 4):
        output = f"/tmp/gem_integrated_cuda_{blocks}b.vcd"
        run(["target/release/cuda_test", "/tmp/gem_integrated_gatelevel.gv",
             "/tmp/gem_integrated.gemparts", "/tmp/gem_integrated_golden.vcd",
             output, str(blocks), "--top-module", "integrated_macro_top",
             "--input-vcd-scope", "tb_integrated_macro_top/dut", "--check-with-cpu"])
        run([sys.executable, "verif/host/compare_macro_integration.py",
             "/tmp/gem_integrated_golden.vcd", output])
    print("PASS: full integrated macro regression (1 block and 4 blocks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
