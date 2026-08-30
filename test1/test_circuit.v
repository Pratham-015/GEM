// ============================================================
// test_circuit.v  –  GEM Deliverable A verification circuit
// Has: AND gate, OR gate, XOR gate, and one CARRY4 macro.
// ============================================================
`timescale 1ns / 1ps

module test_circuit (
    input  wire       in_a,
    input  wire       in_b,
    input  wire       in_c,
    input  wire       in_d,
    input  wire       ci,
    input  wire       cyinit,
    input  wire [3:0] di,
    input  wire [3:0] s,
    output wire       out_and,
    output wire       out_or,
    output wire       out_xor,
    output wire [3:0] carry_co,
    output wire [3:0] carry_o
);

    // ---- Standard boolean gates ----
    wire and_result;
    wire or_result;

    assign and_result = in_a & in_b;   // AND
    assign or_result  = in_c | in_d;   // OR
    assign out_and    = and_result;
    assign out_or     = or_result;
    assign out_xor    = and_result ^ or_result;  // XOR

    // ---- Word-level hardware macro: CARRY4 ----
    CARRY4 u_carry4 (
        .CO    (carry_co),
        .O     (carry_o),
        .CI    (ci),
        .CYINIT(cyinit),
        .DI    (di),
        .S     (s)
    );

endmodule

