// ============================================================================
// test2/mixed_circuit.sv
// Complete heterogeneous benchmark integrating Deliverable A & B:
// - Boolean logic (AND, OR, XOR, INV)
// - Synchronous flip-flops (DFF)
// - CARRY4 fast-carry macro
// - DSP48E2 multiply-accumulate macro
// - SRLC32E dynamic shift register LUT macro
// ============================================================================
`timescale 1ns / 1ps

module mixed_circuit (
    input  wire        clk,
    input  wire        rst,
    // Boolean logic & CARRY4 inputs
    input  wire [3:0]  op_a,
    input  wire [3:0]  op_b,
    input  wire        cin,
    // DSP48E2 inputs
    input  wire [26:0] dsp_a,
    input  wire [17:0] dsp_b,
    input  wire [47:0] dsp_c,
    input  wire [26:0] dsp_d,
    input  wire [1:0]  dsp_state,
    input  wire        dsp_use_pre,
    // SRLC32E inputs
    input  wire        srl_d,
    input  wire        srl_ce,
    input  wire [4:0]  srl_addr,
    // Outputs
    output wire [3:0]  carry_sum,
    output wire [3:0]  carry_co,
    output wire [47:0] dsp_p,
    output wire        srl_q,
    output wire        srl_q31,
    output reg  [3:0]  registered_sum,
    output wire        status_flag
);

    // 1. Boolean logic front-end for CARRY4
    wire [3:0] s_wire;
    wire [3:0] di_wire;
    assign s_wire  = op_a ^ op_b;
    assign di_wire = op_a & op_b;

    // 2. CARRY4 Macro Instantiation
    CARRY4 u_carry4 (
        .CO(carry_co),
        .O(carry_sum),
        .CI(cin),
        .CYINIT(1'b0),
        .DI(di_wire),
        .S(s_wire)
    );

    // 3. DSP48E2 Macro Instantiation
    DSP48E2 u_dsp (
        .P(dsp_p),
        .CLK(clk),
        .USE_PRE(dsp_use_pre),
        .A(dsp_a),
        .B(dsp_b),
        .C(dsp_c),
        .D(dsp_d),
        .STATE(dsp_state)
    );

    // 4. SRLC32E Macro Instantiation
    SRLC32E u_srl (
        .Q(srl_q),
        .Q31(srl_q31),
        .A(srl_addr),
        .CE(srl_ce),
        .CLK(clk),
        .D(srl_d)
    );

    // 5. Sequential Logic: Register CARRY4 sum
    always @(posedge clk) begin
        if (rst) begin
            registered_sum <= 4'b0000;
        end else begin
            registered_sum <= carry_sum;
        end
    end

    // 6. Heterogeneous Output Cross-Check Flag
    // Combines boolean logic, carry output, DSP sign bit, and SRL bit
    assign status_flag = (carry_co[3] ^ dsp_p[47]) | (srl_q & ~srl_q31);

endmodule
