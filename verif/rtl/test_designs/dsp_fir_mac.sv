// SPDX-License-Identifier: Apache-2.0
// Multiply-Accumulate / FIR filter tap test design using simplified DSP48E2.
module dsp_fir_mac (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        use_pre,
    input  logic [1:0]  state,
    input  logic [26:0] a,
    input  logic [17:0] b,
    input  logic [47:0] c,
    input  logic [26:0] d,
    output logic [47:0] p_out
);

    DSP48E2 dsp_inst (
        .CLK(clk),
        .USE_PRE(use_pre),
        .STATE(state),
        .A(a),
        .B(b),
        .C(c),
        .D(d),
        .P(p_out)
    );

endmodule

