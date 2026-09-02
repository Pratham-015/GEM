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
    // Reject unsupported pipeline registers, control registers, and non-PS structural configurations
    wire invalid_param =
        AREG != 0 || BREG != 0 || CREG != 0 || DREG != 0 ||
        ADREG != 0 || MREG != 0 || PREG != 1 ||
        ACASCREG != 0 || BCASCREG != 0 || ALUMODEREG != 0 ||
        INMODEREG != 0 || OPMODEREG != 0 || CARRYINREG != 0 ||
        CARRYINSELREG != 0 || AMULTSEL != "AD" || BMULTSEL != "B" ||
        PREADDINSEL != "A" || USE_MULT != "MULTIPLY" || USE_SIMD != "ONE48";

    // Exact encodings established against DSP48E2 UNISIM:
    // 0x030: C (bypass), 0x005: M (mult), 0x025: P+M (accumulate).
    // ALUMODE must be 4'b0000 (plain add).
    wire is_bypass = (ALUMODE == 4'b0000) && (OPMODE == 9'h030);
    wire is_mult   = (ALUMODE == 4'b0000) && (OPMODE == 9'h005);
    wire is_mac    = (ALUMODE == 4'b0000) && (OPMODE == 9'h025);
    wire valid_op_alu = is_bypass || is_mult || is_mac;

    // Supported pre-adder modes: 5'b00000 (A) and 5'b00100 (A+D).
    wire is_inmode_a  = (INMODE == 5'b00000);
    wire is_inmode_ad = (INMODE == 5'b00100);
    wire valid_inmode = is_inmode_a || is_inmode_ad;

    // Yosys requires _TECHMAP_FAIL_ to be constant after parameter
    // specialization.  OPMODE/ALUMODE/INMODE are legal runtime controls in
    // the PS interface, so they are normalized below rather than folded into
    // this structural configuration predicate.
    wire _TECHMAP_FAIL_ = invalid_param;

    wire [1:0] state = is_mult ? 2'd1 :
                       is_mac  ? 2'd2 : 2'd0;
    wire use_pre = is_inmode_ad;

    GEM_DSP48E2 _TECHMAP_REPLACE_ (
        .P(P), .CLK(CLK), .A(A[26:0]), .B(B), .C(C), .D(D),
        .STATE(state), .USE_PRE(use_pre)
    );
endmodule
