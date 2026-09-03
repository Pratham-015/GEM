#!/usr/bin/env python3
"""Create the RTL circuits used by the benchmarks."""

import argparse
import json
from pathlib import Path
import random


DSP_PARAMS = """#(.AREG(0),.BREG(0),.CREG(0),.DREG(0),.ADREG(0),.MREG(0),.PREG(1),.ACASCREG(0),.BCASCREG(0),.ALUMODEREG(0),.INMODEREG(0),.OPMODEREG(0),.CARRYINREG(0),.CARRYINSELREG(0),.AMULTSEL(\"AD\"))"""


def boolean_rtl(name, gates):
    return f"""module {name}(input wire clk,input wire [63:0] data,output wire [63:0] result);
wire [{gates}:0] x; assign x[0]=^data;
genvar i; generate for(i=0;i<{gates};i=i+1) begin:g
  assign x[i+1]=(x[i]&data[i%64])^(data[(i*13+7)%64]&data[(i*29+3)%64]);
end endgenerate
assign result={{63'b0,x[{gates}]}};
endmodule
"""


def macro_rtl(name, dsp, carry, srl, boolean_gates=0, deep=False):
    lines = [f"module {name}(input wire clk,input wire [63:0] data,output wire [63:0] result);"]
    terms = []
    if boolean_gates:
        lines += [f"wire [{boolean_gates}:0] bx; assign bx[0]=^data;",
                  f"genvar bgi; generate for(bgi=0;bgi<{boolean_gates};bgi=bgi+1) begin:bg",
                  "assign bx[bgi+1]=(bx[bgi]&data[bgi%64])^data[(bgi*17+5)%64];",
                  "end endgenerate"]
        terms.append(f"{{63'b0,bx[{boolean_gates}]}}")
    if dsp:
        lines += [f"wire [47:0] dp[0:{dsp-1}];", "genvar di; generate for(di=0;di<%d;di=di+1) begin:dg" % dsp,
                  "`ifdef GOLDEN",
                  "dsp48e2_ref u(.P(dp[di]),.clk(clk),.A(data[26:0]),.D(data[26:0]^{22'd0,di[4:0]}),.B(data[17:0]^{13'd0,di[4:0]}),.C(data[47:0]),.state(2'd1),.use_pre(1'b1));",
                  "`else",
                  "DSP48E2 " + DSP_PARAMS + " u(.P(dp[di]),.CLK(clk),.A({{3{data[26]}},data[26:0]}),.D(data[26:0]^{22'd0,di[4:0]}),.B(data[17:0]^{13'd0,di[4:0]}),.C(data[47:0]),.OPMODE(9'h005),.ALUMODE(4'b0),.INMODE(5'b00100));",
                  "`endif",
                  "end endgenerate"]
        for i in range(dsp):
            terms.append(f"{{16'b0,dp[{i}]}}")
    if carry:
        lines += [f"wire [{carry*4-1}:0] co,oo;", "genvar ci; generate for(ci=0;ci<%d;ci=ci+1) begin:cg" % carry]
        ci_expr = "(ci==0 ? data[0] : co[ci*4-1])"
        if deep:
            ci_expr = "(ci==0 ? data[0] : (co[ci*4-1]^data[(ci+11)%64]))"
        lines += ["`ifdef GOLDEN",
                  f"CARRY4_ref u(.O(oo[ci*4 +: 4]),.CO(co[ci*4 +: 4]),.DI(data[(ci*3)%61 +: 4]),.S(data[(ci*7)%61 +: 4]),.CI({ci_expr}),.CYINIT(1'b0));",
                  "`else",
                  f"CARRY4 u(.O(oo[ci*4 +: 4]),.CO(co[ci*4 +: 4]),.DI(data[(ci*3)%61 +: 4]),.S(data[(ci*7)%61 +: 4]),.CI({ci_expr}),.CYINIT(1'b0));",
                  "`endif",
                  "end endgenerate"]
        for offset in range(0, carry * 4, 64):
            width = min(64, carry * 4 - offset)
            terms.append(f"{{{{{64-width}{{1'b0}}}},oo[{offset} +: {width}]}}")
            terms.append(f"{{{{{64-width}{{1'b0}}}},co[{offset} +: {width}]}}")
    if srl:
        lines += [f"wire [{srl-1}:0] sq,sq31;", "genvar si; generate for(si=0;si<%d;si=si+1) begin:sg" % srl,
                  "`ifdef GOLDEN",
                  "srlc32e_ref u(.Q(sq[si]),.Q31(sq31[si]),.clk(clk),.CE(data[(si+1)%64]),.D(data[(si*5+3)%64]),.A(data[(si*7)%59 +: 5]));",
                  "`else",
                  "SRLC32E u(.Q(sq[si]),.Q31(sq31[si]),.CLK(clk),.CE(data[(si+1)%64]),.D(data[(si*5+3)%64]),.A(data[(si*7)%59 +: 5]));",
                  "`endif",
                  "end endgenerate"]
        for offset in range(0, srl, 64):
            width = min(64, srl - offset)
            terms.append(f"{{{{{64-width}{{1'b0}}}},sq[{offset} +: {width}]}}")
            terms.append(f"{{{{{64-width}{{1'b0}}}},sq31[{offset} +: {width}]}}")
    lines.append("assign result=" + ("^".join(terms) if terms else "64'b0") + ";")
    lines.append("endmodule")
    return "\n".join(lines) + "\n"


def occupancy_rtl(name, outputs=8192, seed=20260902):
    """Make many separate outputs so several GPU blocks have work."""
    rng = random.Random(seed)
    lines = [
        f"module {name}(input wire clk,input wire [63:0] data,output wire [{outputs-1}:0] result);",
        "wire [47:0] dp; wire [3:0] carry_o,carry_co; wire sq,sq31;",
        "`ifdef GOLDEN",
        "dsp48e2_ref dsp(.P(dp),.clk(clk),.A(data[26:0]),.D(data[53:27]),.B(data[17:0]),.C(data[47:0]),.state(2'd1),.use_pre(1'b1));",
        "CARRY4_ref carry(.O(carry_o),.CO(carry_co),.DI(data[7:4]),.S(data[3:0]),.CI(data[8]),.CYINIT(data[9]));",
        "srlc32e_ref srl(.Q(sq),.Q31(sq31),.clk(clk),.CE(data[10]),.D(carry_co[3]),.A(data[15:11]));",
        "`else",
        "DSP48E2 " + DSP_PARAMS + " dsp(.P(dp),.CLK(clk),.A({{3{data[26]}},data[26:0]}),.D(data[53:27]),.B(data[17:0]),.C(data[47:0]),.OPMODE(9'h005),.ALUMODE(4'b0),.INMODE(5'b00100));",
        "CARRY4 carry(.O(carry_o),.CO(carry_co),.DI(data[7:4]),.S(data[3:0]),.CI(data[8]),.CYINIT(data[9]));",
        "SRLC32E srl(.Q(sq),.Q31(sq31),.CLK(clk),.CE(data[10]),.D(carry_co[3]),.A(data[15:11]));",
        "`endif",
    ]
    for i in range(outputs):
        literals = []
        for _ in range(6):
            bit = rng.randrange(64)
            literals.append(("~" if rng.randrange(2) else "") + f"data[{bit}]")
        macro_term = f"dp[{i % 48}]^carry_o[{i % 4}]^sq"
        lines.append(
            f"assign result[{i}]=({literals[0]}&{literals[1]})^"
            f"({literals[2]}&{literals[3]})^({literals[4]}&{literals[5]})^{macro_term};"
        )
    lines.append("endmodule")
    return "\n".join(lines) + "\n"


def carry_representation_rtl():
    """Make the CARRY4 circuit used for the upstream speed test."""
    rtl = macro_rtl("carry_representation", 0, 15, 0, 256)
    rtl = rtl.replace(
        "output wire [63:0] result);",
        "output wire [63:0] result, output reg heartbeat);",
        1,
    )
    return rtl.replace(
        "endmodule\n",
        "initial heartbeat=1'b0; always @(posedge clk) heartbeat<=data[63];\nendmodule\n",
        1,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", default="benchmark/temporary/generated/workloads")
    args = ap.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    specs = [
        ("boolean_heavy", 2000, 64, boolean_rtl("boolean_heavy", 4096), {"aig_target": 4096}),
        ("dsp_heavy", 2000, 64, macro_rtl("dsp_heavy", 32, 0, 0), {"dsp": 32}),
        ("carry_heavy", 1000, 64, macro_rtl("carry_heavy", 0, 128, 0), {"carry4": 128}),
        ("srl_heavy", 2000, 64, macro_rtl("srl_heavy", 0, 0, 128), {"srlc32e": 128}),
        ("scaling_small", 1000, 64, macro_rtl("scaling_small", 4, 8, 8, 256), {"dsp":4,"carry4":8,"srlc32e":8,"aig_target":256,"scale_group":"heterogeneous","scale":"small"}),
        ("mixed_heterogeneous", 1000, 64, macro_rtl("mixed_heterogeneous", 16, 32, 32, 1024), {"dsp": 16,"carry4":32,"srlc32e":32,"aig_target":1024,"scale_group":"heterogeneous","scale":"medium"}),
        ("deep_dependency", 200, 64, macro_rtl("deep_dependency", 0, 64, 0, 128, True), {"carry4":64,"aig_target":128,"deep":True}),
        ("large_scale", 200, 64, macro_rtl("large_scale", 32, 128, 128, 8192), {"dsp":32,"carry4":128,"srlc32e":128,"aig_target":8192,"scale_group":"heterogeneous","scale":"large"}),
        ("occupancy_stress", 1000, 8192, occupancy_rtl("occupancy_stress"), {"dsp":1,"carry4":1,"srlc32e":1,"wide_outputs":8192,"purpose":"multi-partition occupancy","benchmark_blocks":16}),
    ]
    manifest = []
    for name, cycles, result_width, rtl, requested in specs:
        path = out / f"{name}.sv"
        path.write_text(rtl, encoding="utf-8")
        manifest.append({"name": name, "top": name, "cycles": cycles,
                         "seed": 20260902, "source": str(path), "requested": requested})

    # Use the same CARRY4 circuit for both versions of GEM.
    comparison = out / "carry_representation.sv"
    comparison.write_text(
        carry_representation_rtl(), encoding="utf-8"
    )
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"generated {len(manifest)} deterministic workloads in {out}")


if __name__ == "__main__":
    main()
