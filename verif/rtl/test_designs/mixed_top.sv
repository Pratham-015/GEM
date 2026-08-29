// SPDX-License-Identifier: Apache-2.0
// Top-level heterogeneous design combining standard gates, DFFs, CARRY4, DSP48E2, and SRLC32E.
module mixed_top (
    input  logic        clk,
    input  logic        ce,
    input  logic        use_pre,
    input  logic [1:0]  state,
    input  logic [26:0] a,
    input  logic [17:0] b,
    input  logic [47:0] c,
    input  logic [26:0] d,
    input  logic [3:0]  carry_s,
    input  logic [3:0]  carry_di,
    input  logic        carry_ci,
    input  logic [4:0]  srl_addr,
    input  logic        srl_d,
    output logic [47:0] dsp_p,
    output logic [3:0]  carry_o,
    output logic [3:0]  carry_co,
    output logic        srl_q,
    output logic        srl_q31,
    output logic        status_flag
);

    // 1. DSP macro
    DSP48E2 dsp_u0 (
        .CLK(clk),
        .USE_PRE(use_pre),
        .STATE(state),
        .A(a),
        .B(b),
        .C(c),
        .D(d),
        .P(dsp_p)
    );

    // 2. CARRY4 macro
    CARRY4 carry_u0 (
        .CO(carry_co),
        .O(carry_o),
        .CI(carry_ci),
        .CYINIT(1'b0),
        .DI(carry_di),
        .S(carry_s)
    );

    // 3. SRLC32E macro
    SRLC32E srl_u0 (
        .CLK(clk),
        .CE(ce),
        .D(srl_d),
        .A(srl_addr),
        .Q(srl_q),
        .Q31(srl_q31)
    );

    // 4. Standard sequential logic + combinational gates
    logic [7:0] counter;
    always_ff @(posedge clk) begin
        counter <= counter + 8'd1;
    end

    assign status_flag = (dsp_p[0] ^ carry_o[0] ^ srl_q) & counter[0];

endmodule

