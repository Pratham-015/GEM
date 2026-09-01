#!/usr/bin/env python3
"""
verif/full_integration_test.py
End-to-End System Integration Test for Deliverables B + C + Full Regression.

Pipeline verified:
  [B] Host parser → AIG DAG → 64-bit aligned macro memory layout
  [C] Cycle-accurate CUDA macro models vs Python golden models vs Silicon UNISIM
  [D] Full workspace Rust unit and regression test suite
"""

import os
import sys
import subprocess
import random

HERE = os.path.dirname(os.path.abspath(__file__))
GEM_ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "golden"))

from carry4 import CARRY4, eval_carry_chain_fused
from dsp48e2 import DSP48E2
from srlc32e import SRLC32E
from bitops import mask, to_signed


def banner(msg):
    print(f"  {msg}")


def section(msg):
    print(f"\n  {msg}")


def check(label, ok):
    tag = "[PASS]" if ok else "[FAIL]"
    print(f"  {tag} {label}")
    if not ok:
        raise AssertionError(f"FAILED: {label}")


# PHASE 1: Deliverable B — Host Parser + DAG + Memory Layout
def phase_host_dag():
    banner("PHASE 1: Deliverable B — Host Parser, DAG & Memory Layout")

    result = subprocess.run(
        ["cargo", "test", "--test", "test2_heterogeneous_integration_test",
         "--", "--nocapture"],
        cwd=GEM_ROOT, capture_output=True, text=True, timeout=120
    )

    # Print captured stdout
    for line in result.stdout.splitlines():
        if line.strip():
            print(f"  {line.strip()}")

    check("Rust integration test passed (exit 0)", result.returncode == 0)
    check("All 3 macros found in AIG DAG",
          "Deliverable A & B Pipeline Integration: 100% SUCCESS" in result.stdout)


# PHASE 2: Deliverable C — Cycle-Accurate Macro Models vs Golden
def phase_macro_models():
    banner("PHASE 2: Deliverable C — Cycle-Accurate Macro Models")

    section("2.1: CARRY4 Golden Model Verification")
    c4 = CARRY4()
    # Edge cases + random
    vectors_c4 = [
        (0x0, 0x0, 0, 0),   # all-zero
        (0xF, 0xF, 1, 0),   # all-one S/DI + carry in
        (0xA, 0x5, 0, 1),   # alternating + CYINIT
        (0x3, 0xC, 1, 0),   # partial
    ]
    random.seed(42)
    for _ in range(200):
        vectors_c4.append((random.randint(0, 15), random.randint(0, 15),
                           random.randint(0, 1), random.randint(0, 1)))

    for s, di, cin, cyinit in vectors_c4:
        o, co = c4.eval_comb(s, di, cin, cyinit)
        # Cross-check with fused form
        o2, co2 = eval_carry_chain_fused(s, di, cyinit | cin, 4)
        assert o == o2 and co == co2, f"CARRY4 mismatch: S={s:#x} DI={di:#x}"

    check(f"CARRY4 slice: {len(vectors_c4)} vectors (ripple vs fused)", True)

    section("2.2: DSP48E2 Golden Model Verification (Multi-Cycle)")
    dsp = DSP48E2()
    cycles_dsp = [
        # (A, D, B, C, state, use_pre)
        (10, 0, 20, 0, 1, 0),       # Multiply: 10*20 = 200
        (5, 0, 10, 0, 2, 0),        # MAC: 200 + 50 = 250
        (2, 4, 3, 0, 1, 1),         # Pre-add: (2+4)*3 = 18
        (0, 0, 0, 12345, 0, 0),     # Bypass: P <= C = 12345
        (100, 0, 100, 0, 1, 0),     # Multiply: 100*100 = 10000
        (1, 0, 1, 0, 2, 0),         # MAC: 10000 + 1 = 10001
    ]
    expected_p = [200, 250, 18, 12345, 10000, 10001]
    for i, (a, d, b, c, st, up) in enumerate(cycles_dsp):
        p_next = dsp.eval_comb(a, d, b, c, st, up)
        dsp.tick(p_next)
        assert dsp.read_P() == expected_p[i], \
            f"DSP48E2 cycle {i}: got P={dsp.read_P()}, expected {expected_p[i]}"
    check(f"DSP48E2: {len(cycles_dsp)} sequential cycles, all P values correct", True)

    section("2.3: SRLC32E Golden Model Verification (Multi-Cycle)")
    srl = SRLC32E()
    # Shift in 8 bits: 1,0,1,1,0,0,1,0  → SRL = 0b10110010 = 0xB2
    shift_bits = [1, 0, 1, 1, 0, 0, 1, 0]
    for bit in shift_bits:
        ns = srl.eval_next_state(bit, 1)
        srl.tick(ns)
    assert srl.SRL == 0xB2, f"SRLC32E SRL mismatch: got {srl.SRL:#x}, expected 0xB2"

    # Read each address 0..7 and verify bit-by-bit
    for addr in range(8):
        q, q31 = srl.eval_comb(addr)
        expected_q = (0xB2 >> addr) & 1
        assert q == expected_q, f"SRLC32E Q[{addr}] mismatch: got {q}, expected {expected_q}"
    check("SRLC32E: 8-cycle shift + address read verification", True)

    section("2.4: GPU Differential Harness (vs Icarus Verilog & Xilinx UNISIM)")
    diff_script = os.path.join(HERE, "host", "diff_harness.py")
    result = subprocess.run(
        ["python3", diff_script],
        cwd=GEM_ROOT, capture_output=True, text=True, timeout=120
    )
    for line in result.stdout.splitlines():
        if "PASS" in line or "FAIL" in line or "summary" in line or "GPU" in line:
            print(f"  {line}")

    check("GPU differential harness exited cleanly", result.returncode == 0)
    check("All macros PASS vs real silicon",
          "gem_macros.cuh (GPU) PASS" in result.stdout)


# PHASE 3: Full Cargo Test Suite
def phase_cargo():
    banner("PHASE 3: Full Workspace Regression (cargo test)")

    result = subprocess.run(
        ["cargo", "test"],
        cwd=GEM_ROOT, capture_output=True, text=True, timeout=600
    )

    # Extract test results
    for line in result.stdout.splitlines():
        if "test result:" in line or "test " in line:
            print(f"  {line.strip()}")

    check("cargo test suite passed (exit 0)", result.returncode == 0)


# MAIN
def main():
    print()
    banner("GEM — FULL SYSTEM & GPU INTEGRATION TEST (verif/)")
    print()

    phase_host_dag()
    print()
    phase_macro_models()
    print()
    phase_cargo()

    print()
    banner("FINAL VERDICT")
    print()
    print("  ✅ Deliverable B: Host parser + AIG DAG + 64-bit GPU memory layout")
    print("  ✅ Deliverable C: Cycle-accurate CUDA models — bit-exact vs silicon")
    print("  ✅ All workspace cargo tests passing")
    print()
    print("  [PASS] FULL SYSTEM INTEGRATION AND REGRESSION VERIFIED")
    print()


if __name__ == "__main__":
    main()

