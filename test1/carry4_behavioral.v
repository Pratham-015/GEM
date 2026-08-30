// ============================================================
// carry4_behavioral.v  –  Transparent behavioral model of CARRY4
// Used ONLY by the baseline (flatten) flow so that Yosys/ABC
// can see through the CARRY4 and shred it into AIG gates.
// This file is NOT read in the macro-preserving flow.
// ============================================================
`timescale 1ns / 1ps

module CARRY4 (
    output [3:0] CO,
    output [3:0] O,
    input        CI,
    input        CYINIT,
    input  [3:0] DI,
    input  [3:0] S
);
    wire [4:0] C;
    assign C[0] = CYINIT | CI;

    genvar i;
    generate
        for (i = 0; i < 4; i = i + 1) begin : gen_bit
            assign C[i+1] = (S[i] & C[i]) | (~S[i] & DI[i]);
            assign O[i]   = S[i] ^ C[i];
            assign CO[i]  = C[i+1];
        end
    endgenerate
endmodule
