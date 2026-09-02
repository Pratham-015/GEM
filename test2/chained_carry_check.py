#!/usr/bin/env python3
"""
test2/chained_carry_check.py
Verification script for test2/chained_carry_64b.sv (64-bit chained CARRY4 adder).

1. Checks Yosys netlist (chained_carry_gatelevel.gv) to verify all 16 CARRY4 macros
   are preserved intact alongside the input conditioning AIG gates.
2. Runs cycle-accurate mathematical verification comparing 16-slice ripple carry
   evaluation against the 64-bit fused-addition CUDA formulation.

Rust counterpart: tests/test2_chained_carry_test.rs
  Loads test2/chained_carry_gatelevel.gv and verifies the full NetlistDB -> AIG
  carry-chain fusion (16 CARRY4s -> 2 bounded segments) via `cargo test`.
"""

import os
import sys
import subprocess
import re
import random

HERE = os.path.dirname(os.path.abspath(__file__))
GEM_ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(GEM_ROOT, "verif", "golden"))

from carry4 import CARRY4, eval_carry_chain_fused


def banner(msg):
    print(f"  {msg}")


def check(label, ok):
    tag = "[PASS]" if ok else "[FAIL]"
    print(f"  {tag} {label}")
    if not ok:
        raise AssertionError(f"FAILED: {label}")


def verify_netlist():
    banner("1. Netlist Macro Preservation Check (test2/chained_carry_64b.sv)")

    netlist = os.path.join(HERE, "chained_carry_gatelevel.gv")
    if not os.path.exists(netlist):
        print("  Netlist not found, synthesizing...")
        ys = os.path.join(HERE, "chained_carry_synth.ys")
        subprocess.run(
            ["yosys", ys],
            cwd=GEM_ROOT, capture_output=True, check=True
        )

    with open(netlist) as f:
        content = f.read()

    # Count cell instances (supports escaped identifiers like \gen_carry[0].u_c4)
    cells = {}
    for m in re.finditer(r'^\s+(\w+)\s+\S+\s*\(', content, re.MULTILINE):
        ctype = m.group(1)
        if ctype in ("module", "wire", "input", "output", "assign", "endmodule"):
            continue
        cells[ctype] = cells.get(ctype, 0) + 1

    print(f"\n  Gate-level netlist: {netlist}")
    print("  Cell summary:")
    for ct, n in sorted(cells.items()):
        print(f"    {ct:20s} {n:4d}")

    c4_count = cells.get("CARRY4", 0)
    aig_count = sum(v for k, v in cells.items() if k.startswith("AND2_"))

    print("\n  Preservation checks:")
    check(f"16 CARRY4 macros preserved in 64-bit chain (found {c4_count})", c4_count == 16)
    check(f"Input conditioning AIG gates mapped (found {aig_count} AND2_* cells)", aig_count == 192)


def verify_golden_math():
    banner("2. Mathematical Golden Verification (16-Block Ripple vs 64-Bit Fused)")

    c4 = CARRY4()
    mask64 = (1 << 64) - 1

    # Test vectors: (a, b, cin)
    vectors = [
        (0x0, 0x0, 0),
        (0x0, 0x0, 1),
        (mask64, 0x0, 0),
        (mask64, 0x0, 1),
        (mask64, mask64, 0),
        (mask64, mask64, 1),
        (0xAAAAAAAAAAAAAAAA, 0x5555555555555555, 0),
        (0xAAAAAAAAAAAAAAAA, 0x5555555555555555, 1),
        (0x123456789ABCDEF0, 0x0FEDCBA987654321, 0),
        (0x123456789ABCDEF0, 0x0FEDCBA987654321, 1),
        (0xFFFFFFFFFFFFFFFF, 0x1, 0),
    ]

    # Add 200 pseudo-random 64-bit vectors
    random.seed(42)
    for _ in range(200):
        a_rand = random.getrandbits(64)
        b_rand = random.getrandbits(64)
        cin_rand = random.randint(0, 1)
        vectors.append((a_rand, b_rand, cin_rand))

    for a, b, cin in vectors:
        s_wire = a ^ b
        di_wire = a & b

        # 1. Ripple through 16 CARRY4 blocks
        ripple_sum = 0
        current_ci = cin
        for i in range(16):
            s_nibble = (s_wire >> (i * 4)) & 0xF
            di_nibble = (di_wire >> (i * 4)) & 0xF
            ci_in = cin if i == 0 else current_ci
            o_nibble, co_nibble = c4.eval_comb(s_nibble, di_nibble, ci_in, 0)
            ripple_sum |= (o_nibble << (i * 4))
            current_ci = (co_nibble >> 3) & 1
        ripple_cout = current_ci

        # 2. Closed-form 64-bit fused add (CUDA form: a + b + cin)
        tot = a + b + cin
        expected_sum = tot & mask64
        expected_cout = (tot >> 64) & 1

        assert ripple_sum == expected_sum, \
            f"Sum mismatch: a={a:#x}, b={b:#x}, cin={cin} -> ripple={ripple_sum:#x}, expected={expected_sum:#x}"
        assert ripple_cout == expected_cout, \
            f"Cout mismatch: a={a:#x}, b={b:#x}, cin={cin} -> ripple_cout={ripple_cout}, expected_cout={expected_cout}"

    check(f"64-bit adder: {len(vectors)} vectors verified bit-exact (ripple == fused-add)", True)


def main():
    print()
    banner("CHAINED CARRY 64-BIT ADDER VERIFICATION (test2/chained_carry_64b.sv)")
    print()

    verify_netlist()
    print()
    verify_golden_math()

    print()
    banner("VERDICT: [PASS] 64-bit chained carry macro preservation & math verified!")
    print()


if __name__ == "__main__":
    main()

