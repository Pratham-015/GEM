#!/usr/bin/env python3
"""Seeded RTL-to-CUDA differential tests over genuinely different macro DAGs.

Each seed emits a new SystemVerilog topology containing the dependency path
DSP(PREG) -> one or more chained CARRY4s -> one or more chained SRLC32Es ->
DSP(PREG), with randomized ordinary RTL glue between stages.  Expected values
come from the independent literal Verilog models, never from GEM's C++ model.
"""
import argparse
import json
import pathlib
import random
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]


def run(cmd):
    print("+", " ".join(map(str, cmd)), flush=True)
    subprocess.run([str(x) for x in cmd], cwd=ROOT, check=True)


def emit_design(path, top, ncarry, nsrl, salt):
    width = 4 * ncarry
    carry_cells = []
    for i in range(ncarry):
        ci = "cin" if i == 0 else f"carry_co[{4*i-1}]"
        carry_cells.append(f"""
`ifdef GOLDEN
  CARRY4_ref carry_inst_{i} (.O(carry_o[{4*i} +: 4]), .CO(carry_co[{4*i} +: 4]),
`else
  CARRY4 carry_inst_{i} (.O(carry_o[{4*i} +: 4]), .CO(carry_co[{4*i} +: 4]),
`endif
    .S(carry_s[{4*i} +: 4]), .DI(carry_di[{4*i} +: 4]),
    .CI({ci}), .CYINIT(1'b0));""")
    srl_cells = []
    for i in range(nsrl):
        d = "^carry_o" if i == 0 else f"q_vec[{i-1}] ^ p0[{(i + salt) % 48}]"
        srl_cells.append(f"""
`ifdef GOLDEN
  srlc32e_ref srl{i} (.Q(q_vec[{i}]), .Q31(q31_vec[{i}]), .clk(clk),
`else
  SRLC32E srl{i} (.Q(q_vec[{i}]), .Q31(q31_vec[{i}]), .CLK(clk),
`endif
    .CE(srl_ce[{i}]), .D({d}), .A(srl_addr ^ 5'd{(i * 7 + salt) & 31}));""")
    text = f"""`timescale 1ns/1ps
module {top}(
  input clk, input [26:0] a0,d0,a1,d1, input [17:0] b0,b1,
  input [47:0] c0,c1, input [1:0] state0,state1,
  input use_pre0,use_pre1, input [{width-1}:0] x,y, input cin,
  input [{nsrl-1}:0] srl_ce, input [4:0] srl_addr,
  output [47:0] p0,p1, output [{width-1}:0] carry_o,carry_co,
  output [{nsrl-1}:0] q_vec,q31_vec, output [7:0] digest);
  wire [8:0] op0 = state0==0 ? 9'h030 : state0==1 ? 9'h005 : 9'h025;
  wire [8:0] op1 = state1==0 ? 9'h030 : state1==1 ? 9'h005 : 9'h025;
`ifdef GOLDEN
  dsp48e2_ref dsp0 (.P(p0),.clk(clk),.A(a0),.D(d0),.B(b0),.C(c0),.state(state0),.use_pre(use_pre0));
`else
  DSP48E2 #(.AREG(0),.BREG(0),.CREG(0),.DREG(0),.ADREG(0),.MREG(0),.PREG(1),
    .ACASCREG(0),.BCASCREG(0),.ALUMODEREG(0),.INMODEREG(0),.OPMODEREG(0),
    .CARRYINREG(0),.CARRYINSELREG(0),.AMULTSEL("AD")) dsp0
    (.P(p0),.CLK(clk),.A({{{{3{{a0[26]}}}},a0}}),.D(d0),.B(b0),.C(c0),
     .OPMODE(op0),.ALUMODE(0),.INMODE({{2'b0,use_pre0,2'b0}}));
`endif
  wire [{width-1}:0] carry_s = (x ^ y) ^ p0[{width-1}:0];
  wire [{width-1}:0] carry_di = (x & y) ^ {{{width}{{p0[{salt % 48}]}}}};
  {''.join(carry_cells)}
  {''.join(srl_cells)}
  wire [26:0] chained_a1 = a1 ^ {{26'd0,q_vec[{nsrl-1}]}} ^ {{23'd0,carry_co[{width-1} -: 4]}};
`ifdef GOLDEN
  dsp48e2_ref dsp1 (.P(p1),.clk(clk),.A(chained_a1),.D(d1),.B(b1),.C(c1),.state(state1),.use_pre(use_pre1));
`else
  DSP48E2 #(.AREG(0),.BREG(0),.CREG(0),.DREG(0),.ADREG(0),.MREG(0),.PREG(1),
    .ACASCREG(0),.BCASCREG(0),.ALUMODEREG(0),.INMODEREG(0),.OPMODEREG(0),
    .CARRYINREG(0),.CARRYINSELREG(0),.AMULTSEL("AD")) dsp1
    (.P(p1),.CLK(clk),.A({{{{3{{chained_a1[26]}}}},chained_a1}}),.D(d1),.B(b1),.C(c1),
     .OPMODE(op1),.ALUMODE(0),.INMODE({{2'b0,use_pre1,2'b0}}));
`endif
  assign digest = {{p0[47],p0[0],carry_o[{width-1}],carry_co[{width-1}],
                    q_vec[{nsrl-1}],q31_vec[{nsrl-1}],p1[47],p1[0]}};
endmodule
"""
    path.write_text(text, encoding="utf-8")


def emit_tb(path, top, width, nsrl, cycles, seed, vcd):
    path.write_text(f"""`timescale 1ns/1ps
module tb;
 reg clk=0; reg [26:0] a0=0,d0=0,a1=0,d1=0; reg [17:0] b0=0,b1=0;
 reg [47:0] c0=0,c1=0; reg [1:0] state0=0,state1=0; reg use_pre0=0,use_pre1=0;
 reg [{width-1}:0] x=0,y=0; reg cin=0; reg [{nsrl-1}:0] srl_ce=0; reg [4:0] srl_addr=0;
 wire [47:0] p0,p1; wire [{width-1}:0] carry_o,carry_co;
 wire [{nsrl-1}:0] q_vec,q31_vec; wire [7:0] digest;
 {top} dut(.*); always #5 clk=~clk;
 integer cycle; reg [63:0] r=64'h{(seed * 0x9e3779b97f4a7c15) & ((1<<64)-1):016x};
 initial begin $dumpfile("{vcd}"); $dumpvars(0,dut);
  for(cycle=0;cycle<{cycles};cycle=cycle+1) begin @(negedge clk); #2;
   r=r*64'h5851f42d4c957f2d+64'h14057b7ef767814f;
   a0=r[26:0];d0=r[53:27];b0=r[45:28];c0={{r[31:0],r[63:48]}};
   a1=~r[26:0];d1=r[58:32];b1=r[35:18];c1=r[47:0];
   state0=cycle%3;state1=(cycle+{seed})%3;use_pre0=r[3];use_pre1=r[9];
   x=r[{width-1}:0];y=(r>>{max(1, width//2)})^r;cin=r[11];srl_ce=r[{nsrl-1}:0];srl_addr=r[20:16];
  end @(posedge clk); #1 $finish; end
endmodule
""", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=4)
    ap.add_argument("--cycles", type=int, default=48)
    args = ap.parse_args()
    run(["cargo", "build", "--release", "--features", "cuda", "--bin", "cut_map_interactive", "--bin", "cuda_test"])
    total_cycles = 0
    with tempfile.TemporaryDirectory(prefix="gem_random_dag_") as td:
        work = pathlib.Path(td)
        for seed in range(1, args.seeds + 1):
            rng = random.Random(0xB00 + seed)
            ncarry, nsrl, salt = rng.randint(1, 4), rng.randint(1, 3), rng.randrange(48)
            width, top = 4*ncarry, f"random_dag_{seed}"
            rtl, tb = work/f"{top}.sv", work/f"tb_{top}.sv"
            gv, js, parts = work/f"{top}.gv", work/f"{top}.json", work/f"{top}.gemparts"
            gold, gpu, sim = work/f"{top}_gold.vcd", work/f"{top}_gpu.vcd", work/f"{top}.out"
            emit_design(rtl, top, ncarry, nsrl, salt)
            emit_tb(tb, top, width, nsrl, args.cycles, seed, gold)
            run([sys.executable,"scripts/synthesize_macros.py","--top",top,"--output",gv,"--json",js,rtl])
            cells=json.loads(js.read_text())["modules"][top]["cells"].values()
            counts={k:sum(c["type"]==k for c in cells) for k in ("CARRY4","GEM_DSP48E2","SRLC32E")}
            expected={"CARRY4":ncarry,"GEM_DSP48E2":2,"SRLC32E":nsrl}
            if counts != expected: raise AssertionError(f"seed {seed}: {counts} != {expected}")
            run(["iverilog","-g2012","-DGOLDEN","-s","tb","-o",sim,"verif/rtl/xilinx_macros_ref.v",rtl,tb])
            run(["vvp",sim])
            run(["target/release/cut_map_interactive",gv,parts,"--top-module",top])
            run(["target/release/cuda_test",gv,parts,gold,gpu,"1","--top-module",top,
                 "--input-vcd-scope","tb/dut","--check-with-cpu"])
            signals=f"p0:48,p1:48,carry_o:{width},carry_co:{width},q_vec:{nsrl},q31_vec:{nsrl},digest:8"
            run([sys.executable,"verif/host/compare_macro_integration.py",gold,gpu,"--signals",signals])
            print(f"PASS seed={seed} topology=DSP->CARRY4x{ncarry}->SRLC32Ex{nsrl}->DSP")
            total_cycles += args.cycles
    print(f"PASS: {args.seeds} production CUDA topologies, {total_cycles} randomized stimulus cycles")


if __name__ == "__main__":
    main()
