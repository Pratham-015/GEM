"""Differential test harness: Python golden models vs Verilog reference sim.

WHAT THE REFERENCE IS -- read this before trusting the results.

The authoritative reference for a Xilinx primitive is its UNISIM behavioural
model, which ships only inside a Vivado installation. Vivado is NOT installed
in this environment and the UNISIM sources are not redistributable, so they
are unavailable here (see the report accompanying this harness).

The reference actually used is verif/rtl/xilinx_macros_ref.v: an independent
LITERAL transcription of the equations in the problem statement, simulated with
Icarus Verilog. This is a genuine differential test -- the Verilog ripples the
carry chain bit by bit while the Python model is free to use closed-form
arithmetic, and the two implementations share no code -- but it validates
against the SPEC, not against Xilinx silicon. Any place where the spec itself
diverges from real DSP48E2/CARRY4/SRLC32E behaviour will not be caught here.

Flow per primitive:
    1. build stimulus (directed edge cases first, then randomized)
    2. run the Python golden model over it
    3. run the Verilog reference over the identical stimulus via iverilog
    4. compare every output signal, every cycle, bit-exact
"""

import os
import random
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GOLDEN = os.path.abspath(os.path.join(HERE, "..", "golden"))
RTL = os.path.abspath(os.path.join(HERE, "..", "rtl"))
TB = os.path.abspath(os.path.join(HERE, "..", "tb"))
sys.path.insert(0, GOLDEN)

from bitops import mask, to_signed
from carry4 import CARRY4, eval_carry_chain_ripple, eval_carry_chain_fused
from dsp48e2 import DSP48E2
from srlc32e import SRLC32E

# Icarus is installed natively in WSL (sudo apt install iverilog), so no
# Windows-interop path translation is needed.
# vvp can still read from stdin in some invocations, so keep feeding it
# DEVNULL to avoid it swallowing our own input.
IVERILOG = "iverilog"
VVP = "vvp"
STAGE = "/home/pratham_sharma/gem/build/gemdiff"
# The testbenches open every file -- stimulus in, results out, VCD -- relative
# to their own cwd, under sim_out/, so the stimulus this harness generates has
# to land there too. Writing it to the STAGE root instead makes the tb's
# $fopen(.., "r") return 0; the tb then prints FILE ERROR and $finish-es before
# producing any output, and the harness is left reading an empty or absent
# result file.
SIM_OUT = os.path.join(STAGE, "sim_out")
os.makedirs(SIM_OUT, exist_ok=True)


def stim_path(name):
    return os.path.join(SIM_OUT, name)

CHAIN_BLOCKS = 15
CHAIN_BITS = CHAIN_BLOCKS * 4
N_RANDOM = 2000


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True)


def stage_setup():
    os.makedirs(STAGE, exist_ok=True)
    shutil.copy(os.path.join(RTL, "xilinx_macros_ref.v"), STAGE)
    for f in ("tb_carry4.v", "tb_dsp48e2.v", "tb_srlc32e.v"):
        shutil.copy(os.path.join(TB, f), STAGE)


def compile_and_run(tb_file, top):
    vvp_out = top + ".vvp"
    r = run([IVERILOG, "-g2012", "-I", ".", "-s", top, "-o", vvp_out, tb_file], STAGE)
    if r.returncode != 0:
        return False, "iverilog failed:\n" + r.stdout
    r = run([VVP, vvp_out], STAGE)
    if r.returncode != 0:
        return False, "vvp failed:\n" + r.stdout
    # An $fopen failure inside the tb is not an exit code -- the tb prints
    # FILE ERROR and $finish-es cleanly. Treat it as a build failure so the
    # cause is reported here instead of as an empty-results puzzle later.
    if "FILE ERROR" in r.stdout:
        return False, ("testbench could not open its stimulus/result files "
                       "under %s:\n%s" % (SIM_OUT, r.stdout))
    return True, r.stdout


def read_results(name, ncol):
    rows = []
    with open(os.path.join(SIM_OUT, name)) as f:
        for line in f:
            parts = line.split()
            if len(parts) == ncol:
                rows.append(tuple(int(p, 16) for p in parts))
    return rows


def report(label, golden, actual, signals):
    n = min(len(golden), len(actual))
    if n == 0:
        print("  %-24s ERROR  no vectors compared" % label)
        return False
    bad = []
    for i in range(n):
        if golden[i] != actual[i]:
            bad.append((i, golden[i], actual[i]))
    if len(golden) != len(actual):
        print("  %-24s ERROR  length mismatch golden=%d verilog=%d"
              % (label, len(golden), len(actual)))
        return False
    if not bad:
        print("  %-24s PASS   %d vectors bit-exact" % (label, n))
        return True
    cyc, exp, got = bad[0]
    print("  %-24s FAIL   %d/%d mismatched" % (label, len(bad), n))
    print("      first divergence at cycle/vector %d:" % cyc)
    for i, sig in enumerate(signals):
        flag = "   <-- MISMATCH" if exp[i] != got[i] else ""
        print("        %-5s golden=0x%-14x verilog=0x%-14x%s"
              % (sig, exp[i], got[i], flag))
    return False


def test_carry4(rng):
    slice_vecs = []
    for s in (0x0, 0xF, 0xA, 0x5, 0x1, 0x8):
        for di in (0x0, 0xF, 0xA, 0x5):
            for cin in (0, 1):
                for cyi in (0, 1):
                    slice_vecs.append((s, di, cin, cyi))
    for _ in range(N_RANDOM):
        slice_vecs.append((rng.getrandbits(4), rng.getrandbits(4),
                           rng.getrandbits(1), rng.getrandbits(1)))

    allo = (1 << CHAIN_BITS) - 1
    chain_vecs = [(0, 0, 0), (0, 0, 1), (allo, allo, 0), (allo, allo, 1),
                  (allo, 0, 1), (0, allo, 0), (1, 0, 1), (allo ^ 1, allo, 1),
                  (int("A" * CHAIN_BLOCKS, 16), int("5" * CHAIN_BLOCKS, 16), 1)]
    for _ in range(N_RANDOM):
        chain_vecs.append((rng.getrandbits(CHAIN_BITS),
                           rng.getrandbits(CHAIN_BITS), rng.getrandbits(1)))

    with open(stim_path("stim_carry4.txt"), "w") as f:
        for s, di, cin, cyi in slice_vecs:
            f.write("%x %x %x %x\n" % (s, di, cin, cyi))
    with open(stim_path("stim_chain.txt"), "w") as f:
        for s, di, cyi in chain_vecs:
            f.write("%x %x %x\n" % (s, di, cyi))

    ok, out = compile_and_run("tb_carry4.v", "tb_carry4")
    if not ok:
        print("  CARRY4 BUILD ERROR:\n" + out)
        return False

    model = CARRY4()
    g_slice = [model.eval_comb(s, di, cin, cyi) for (s, di, cin, cyi) in slice_vecs]
    v_slice = read_results("res_carry4.txt", 2)
    r1 = report("CARRY4 slice", g_slice, v_slice, ("O", "CO"))

    v_chain = read_results("res_chain.txt", 2)
    g_ripple = [eval_carry_chain_ripple(s, di, cyi, CHAIN_BITS)
                for (s, di, cyi) in chain_vecs]
    r2 = report("CARRY4 chain x%d (%db)" % (CHAIN_BLOCKS, CHAIN_BITS),
                g_ripple, v_chain, ("O", "CO"))

    g_fused = [eval_carry_chain_fused(s, di, cyi, CHAIN_BITS)
               for (s, di, cyi) in chain_vecs]
    r3 = report("  fused-add (CUDA form)", g_fused, v_chain, ("O", "CO"))
    return r1 and r2 and r3


def test_dsp(rng):
    A_MAX = (1 << 27) - 1
    B_MAX = (1 << 18) - 1
    C_MAX = (1 << 48) - 1
    A_MINS = 1 << 26
    B_MINS = 1 << 17

    vecs = []
    for st in (0, 1, 2):
        for up in (0, 1):
            vecs.append((0, 0, 0, 0, st, up))
            vecs.append((A_MAX, A_MAX, B_MAX, C_MAX, st, up))
            vecs.append((A_MINS, A_MINS, B_MINS, 0, st, up))
            vecs.append((A_MAX >> 1, 0, B_MAX >> 1, 0, st, up))
            vecs.append((A_MINS, 1, B_MINS, C_MAX, st, up))
            vecs.append((1, A_MAX, 1, 0, st, up))
    for _ in range(300):
        vecs.append((rng.getrandbits(27), rng.getrandbits(27),
                     rng.getrandbits(18), rng.getrandbits(48), 2, 1))
    for _ in range(N_RANDOM):
        vecs.append((rng.getrandbits(27), rng.getrandbits(27),
                     rng.getrandbits(18), rng.getrandbits(48),
                     rng.randrange(3), rng.getrandbits(1)))

    with open(stim_path("stim_dsp.txt"), "w") as f:
        for a, d, b, c, st, up in vecs:
            f.write("%x %x %x %x %x %x\n" % (a, d, b, c, st, up))

    ok, out = compile_and_run("tb_dsp48e2.v", "tb_dsp48e2")
    if not ok:
        print("  DSP48E2 BUILD ERROR:\n" + out)
        return False

    dsp = DSP48E2()
    golden = []
    for a, d, b, c, st, up in vecs:
        p_next = dsp.eval_comb(A=a, D=d, B=b, C=c, state=st, use_pre=up)
        dsp.tick(p_next)
        golden.append((dsp.read_P(),))

    actual = read_results("res_dsp.txt", 1)
    return report("DSP48E2 (PREG=1)", golden, actual, ("P",))


def test_srl(rng):
    vecs = []
    for i in range(32):
        vecs.append((1, 1, i))
    for i in range(32):
        vecs.append((0, 1, i))
    for i in range(32):
        vecs.append((1, 0, i))
    vecs.append((1, 1, 31))
    vecs.append((0, 1, 31))
    vecs.append((1, 1, 0))
    vecs.append((0, 0, 0))
    for _ in range(N_RANDOM):
        vecs.append((rng.getrandbits(1), rng.getrandbits(1), rng.getrandbits(5)))

    with open(stim_path("stim_srl.txt"), "w") as f:
        for d, ce, a in vecs:
            f.write("%x %x %x\n" % (d, ce, a))

    ok, out = compile_and_run("tb_srlc32e.v", "tb_srlc32e")
    if not ok:
        print("  SRLC32E BUILD ERROR:\n" + out)
        return False

    srl = SRLC32E()
    golden = []
    for d, ce, a in vecs:
        q, q31 = srl.eval_comb(a)
        ns = srl.eval_next_state(d, ce)
        srl.tick(ns)
        golden.append((q, q31, srl.SRL))

    actual = read_results("res_srl.txt", 3)
    return report("SRLC32E", golden, actual, ("Q", "Q31", "SRL"))


def main():
    rng = random.Random(20260827)
    stage_setup()
    ver = run([IVERILOG, "-V"], STAGE).stdout.splitlines()[0]
    print("Reference simulator : %s" % ver)
    print("Reference model     : verif/rtl/xilinx_macros_ref.v (spec-literal)")
    print("NOT Xilinx UNISIM   : Vivado unavailable in this environment\n")

    results = []
    results.append(("CARRY4", test_carry4(rng)))
    results.append(("DSP48E2", test_dsp(rng)))
    results.append(("SRLC32E", test_srl(rng)))

    print("\n--- summary ---")
    allok = True
    for name, ok in results:
        print("%-10s %s" % (name, "PASS" if ok else "FAIL"))
        allok = allok and ok
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
