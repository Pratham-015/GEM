// SPDX-License-Identifier: Apache-2.0
// Yosys techmap from the native Xilinx DSP48E2 interface to GEM's explicit
// problem-statement subset. Parameter validation is structural and occurs
// after elaboration, so nested parameter syntax and generate hierarchy do not
// require fragile source-text parsing.
(* techmap_celltype = "DSP48E2" *)
module DSP48E2_PS_MAP #(
    parameter integer AREG = 1, BREG = 1, CREG = 1, DREG = 1,
    parameter integer ADREG = 1, MREG = 1, PREG = 1,
    parameter integer ACASCREG = 1, BCASCREG = 1,
    parameter integer ALUMODEREG = 1, INMODEREG = 1, OPMODEREG = 1,
    parameter integer CARRYINREG = 1, CARRYINSELREG = 1,
    parameter AMULTSEL = "A", parameter BMULTSEL = "B",
    parameter PREADDINSEL = "A", parameter USE_MULT = "MULTIPLY",
    parameter USE_SIMD = "ONE48"
) (
    output [47:0] P,
    input CLK,
    input [29:0] A,
    input [17:0] B,
    input [47:0] C,
    input [26:0] D,
    input [8:0] OPMODE,
    input [3:0] ALUMODE,
    input [4:0] INMODE
);
    wire _TECHMAP_FAIL_ = AREG != 0 || BREG != 0 || CREG != 0 ||
        DREG != 0 || ADREG != 0 || MREG != 0 || PREG != 1;

    // Exact encodings established against DSP48E2 UNISIM:
    // 0x030: C, 0x005: M, 0x025: P+M. ALUMODE must select plain add.
    wire [1:0] state = (ALUMODE == 4'b0000 && OPMODE == 9'h005) ? 2'd1 :
                       (ALUMODE == 4'b0000 && OPMODE == 9'h025) ? 2'd2 : 2'd0;
    // The supported pre-adder modes are 00000 (A) and 00100 (A+D).
    wire use_pre = INMODE == 5'b00100;

    GEM_DSP48E2 _TECHMAP_REPLACE_ (
        .P(P), .CLK(CLK), .A(A[26:0]), .B(B), .C(C), .D(D),
        .STATE(state), .USE_PRE(use_pre)
    );
endmodule
