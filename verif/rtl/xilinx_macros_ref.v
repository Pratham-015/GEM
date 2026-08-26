// SPDX-License-Identifier: Apache-2.0
// Behavioural golden models for the three Xilinx primitives GEM must
// evaluate natively.
//
// These are written to be as LITERAL a transcription of the problem
// statement's equations as possible -- in particular CARRY4_ref is a genuine
// four-step ripple, and carry_chain_ref really does daisy-chain CO[3] into
// the next block's CI. They are intentionally NOT clever.
//
// The point of that is independence: csrc/gem_macros.cuh evaluates a fused
// carry chain as a single 64-bit add, and the whole verification argument is
// that the clever version and this literal version agree on random vectors.
// If both files shared an optimisation, the test would prove nothing.

`timescale 1ns / 1ps

// ---------------------------------------------------------------------------
// CARRY4 -- literal transcription of the silicon equations
// ---------------------------------------------------------------------------
//   C[0]   = CYINIT | CI
//   C[i+1] = (S[i] & C[i]) | (~S[i] & DI[i])
//   O[i]   = S[i] ^ C[i]
//   CO[i]  = C[i+1]
module CARRY4_ref (
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

// ---------------------------------------------------------------------------
// A cascade of NBLK CARRY4s, wired CO[3] -> CI exactly as a synthesiser would
// emit for a wide adder. This is the structure GEM must recognise and fuse.
// ---------------------------------------------------------------------------
module carry_chain_ref #(
    parameter NBLK = 15
) (
    output [4*NBLK-1:0] O,
    output [4*NBLK-1:0] CO,
    input               CYINIT,
    input  [4*NBLK-1:0] DI,
    input  [4*NBLK-1:0] S
);
    wire [NBLK:0] cc;
    assign cc[0] = 1'b0;

    genvar b;
    generate
        for (b = 0; b < NBLK; b = b + 1) begin : gen_blk
            CARRY4_ref u_c4 (
                .CO     (CO[4*b+3 -: 4]),
                .O      (O [4*b+3 -: 4]),
                // Block 0 takes the chain initialiser on CYINIT; every later
                // block takes the previous block's CO[3] on CI. Only one of
                // the two is ever active, per the problem statement.
                .CI     ((b == 0) ? 1'b0   : cc[b]),
                .CYINIT ((b == 0) ? CYINIT : 1'b0),
                .DI     (DI[4*b+3 -: 4]),
                .S      (S [4*b+3 -: 4])
            );
            assign cc[b+1] = CO[4*b+3];
        end
    endgenerate
endmodule

// ---------------------------------------------------------------------------
// DSP48E2 simplified subset
// ---------------------------------------------------------------------------
// AREG/BREG/CREG/DREG/ADREG/MREG = 0 (combinational), PREG = 1 (clocked).
//   AD     = use_pre ? A + D : A      (wraps at 27 bits)
//   M      = AD * B                   (45-bit signed)
//   P_next = state==0 ? C : state==1 ? M : P + M
module dsp48e2_ref (
    output reg signed [47:0] P,
    input                    clk,
    input      signed [26:0] A,
    input      signed [26:0] D,
    input      signed [17:0] B,
    input      signed [47:0] C,
    input             [1:0]  state,
    input                    use_pre
);
    // 27-bit pre-adder: the sum truncates back to 27 bits.
    wire signed [26:0] AD = use_pre ? (A + D) : A;
    // 27 x 18 -> 45 bit signed product.
    wire signed [44:0] M  = AD * B;

    reg signed [47:0] p_next;
    always @(*) begin
        case (state)
            2'd0:    p_next = C;        // bypass
            2'd1:    p_next = M;        // multiply only
            default: p_next = P + M;    // multiply-accumulate
        endcase
    end

    initial P = 48'd0;                  // registers initialise to zero
    always @(posedge clk) P <= p_next;
endmodule

// ---------------------------------------------------------------------------
// SRLC32E shift register LUT
// ---------------------------------------------------------------------------
//   on posedge, if CE: state <= {state[30:0], D}   (shift LSB -> MSB)
//   Q   = state[A]    combinational, dynamic address
//   Q31 = state[31]   combinational cascade output
module srlc32e_ref (
    output       Q,
    output       Q31,
    input        clk,
    input        CE,
    input        D,
    input  [4:0] A
);
    reg [31:0] state;
    initial state = 32'd0;              // registers initialise to zero

    assign Q   = state[A];
    assign Q31 = state[31];

    always @(posedge clk) begin
        if (CE) state <= {state[30:0], D};
    end
endmodule
