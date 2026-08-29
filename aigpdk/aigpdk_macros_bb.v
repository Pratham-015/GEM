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
module DSP48E2 (
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

