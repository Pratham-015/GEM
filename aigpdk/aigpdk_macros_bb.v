// SPDX-License-Identifier: Apache-2.0
// Blackbox definitions for Xilinx hardware macros recognized natively by GEM.
// Used during Yosys synthesis to prevent flattening into 1-bit boolean AIG gates.

(* blackbox, keep *)
module CARRY4 (
    output [3:0] CO,
    output [3:0] O,
    input        CI,
    input        CYINIT,
    input  [3:0] DI,
    input  [3:0] S
);
endmodule

(* blackbox, keep *)
module GEM_DSP48E2 (
    output [47:0] P,
    input         CLK,
    input         USE_PRE,
    input  [26:0] A,
    input  [17:0] B,
    input  [47:0] C,
    input  [26:0] D,
    input  [1:0]  STATE
);
endmodule

// Native Xilinx-style interface accepted by the Yosys intent normalizer.
// Unsupported datapaths are deliberately present as ports so elaboration is
// structural; the normalizer rejects non-PS configurations before GEM runs.
(* blackbox, keep *)
module DSP48E2 #(
    parameter integer AREG = 1, BREG = 1, CREG = 1, DREG = 1,
    parameter integer ADREG = 1, MREG = 1, PREG = 1,
    parameter integer ACASCREG = 1, BCASCREG = 1,
    parameter integer ALUMODEREG = 1, INMODEREG = 1, OPMODEREG = 1,
    parameter integer CARRYINREG = 1, CARRYINSELREG = 1,
    parameter AMULTSEL = "A", parameter BMULTSEL = "B",
    parameter PREADDINSEL = "A", parameter USE_MULT = "MULTIPLY",
    parameter USE_SIMD = "ONE48"
) (
    output [47:0] P, PCOUT,
    output [29:0] ACOUT,
    output [17:0] BCOUT,
    output [3:0] CARRYOUT,
    output CARRYCASCOUT, MULTSIGNOUT, OVERFLOW, UNDERFLOW,
    output PATTERNBDETECT, PATTERNDETECT,
    output [7:0] XOROUT,
    input CLK,
    input [29:0] A, ACIN,
    input [17:0] B, BCIN,
    input [47:0] C, PCIN,
    input [26:0] D,
    input [8:0] OPMODE,
    input [3:0] ALUMODE,
    input [4:0] INMODE,
    input [1:0] STATE,
    input USE_PRE,
    input [2:0] CARRYINSEL,
    input CARRYIN, CARRYCASCIN, MULTSIGNIN,
    input CEA1, CEA2, CEAD, CEALUMODE, CEB1, CEB2, CEC,
    input CECARRYIN, CECTRL, CED, CEINMODE, CEM, CEP,
    input RSTA, RSTALLCARRYIN, RSTALUMODE, RSTB, RSTC, RSTCTRL,
    input RSTD, RSTINMODE, RSTM, RSTP
);
endmodule

(* blackbox, keep *)
module SRLC32E (
    output       Q,
    output       Q31,
    input  [4:0] A,
    input        CE,
    input        CLK,
    input        D
);
endmodule
