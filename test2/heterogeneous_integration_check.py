#!/usr/bin/env python3
"""
test2/heterogeneous_integration_check.py
Deliverable A Verification for test2/mixed_circuit.sv.
Verifies that Yosys preserves CARRY4, DSP48E2, SRLC32E, DFFs, and maps AIG glue logic.

Rust counterpart: tests/test2_heterogeneous_integration_test.rs
  Loads test2/heterogeneous_integration_gatelevel.gv and exercises the full
  NetlistDB -> AIG -> MacroStorageLayout host-side pipeline via `cargo test`.
"""

import os
import sys
import subprocess
import re

HERE = os.path.dirname(os.path.abspath(__file__))
GEM_ROOT = os.path.abspath(os.path.join(HERE, ".."))


def banner(msg):
    print(f"  {msg}")


def check(label, ok):
    tag = "[PASS]" if ok else "[FAIL]"
    print(f"  {tag} {label}")
    if not ok:
        raise AssertionError(f"FAILED: {label}")


def main():
    banner("Deliverable A — Yosys Macro Preservation (test2/mixed_circuit.sv)")

    netlist = os.path.join(HERE, "heterogeneous_integration_gatelevel.gv")
    if not os.path.exists(netlist):
        print("  Netlist not found, synthesizing...")
        ys = os.path.join(HERE, "heterogeneous_integration_synth.ys")
        subprocess.run(
            ["yosys", ys],
            cwd=GEM_ROOT, capture_output=True, check=True
        )

    with open(netlist) as f:
        content = f.read()

    # Count cell instances
    cells = {}
    for m in re.finditer(r'^\s+(\w+)\s+\w+\s*\(', content, re.MULTILINE):
        ctype = m.group(1)
        if ctype in ("module", "wire", "input", "output", "assign", "endmodule"):
            continue
        cells[ctype] = cells.get(ctype, 0) + 1

    print(f"\n  Gate-level netlist: {netlist}")
    print("  Cell summary:")
    for ct, n in sorted(cells.items()):
        print(f"    {ct:20s} {n:4d}")

    print("\n  Preservation checks:")
    check("CARRY4 preserved in netlist", cells.get("CARRY4", 0) == 1)
    dsp_count = cells.get("DSP48E2", 0) + cells.get("GEM_DSP48E2", 0)
    check("DSP48E2 preserved in netlist", dsp_count == 1)
    check("SRLC32E preserved in netlist", cells.get("SRLC32E", 0) == 1)
    check("DFF cells present", cells.get("DFF", 0) == 4)
    aig_count = sum(v for k, v in cells.items() if k.startswith("AND2_"))
    check(f"AIG glue logic mapped ({aig_count} AND2_* cells)", aig_count >= 10)

    print("\n  VERDICT: [PASS] All target macros preserved in test2 netlist!\n")


if __name__ == "__main__":
    main()

