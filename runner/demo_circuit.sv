// SPDX-License-Identifier: Apache-2.0
// runner/demo_circuit.sv
// ==============================================================================
// Custom Heterogeneous DSP & Fast-Carry Filter Pipeline
// Demonstrates native GPU acceleration of mixed-width primitives alongside
// standard Boolean logic in NVIDIA GEM.
//
// Primitives instantiated:
//   1. SRLC32E     : 32-bit dynamic shift register LUT (variable delay line)
//   2. GEM_DSP48E2 : 27x18-bit Multiplier-Accumulator (MAC engine)
//   3. CARRY4      : 4-bit Fast Carry Lookahead adder (post-scaling threshold)
// ==============================================================================

module demo_circuit (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        valid_in,
    input  wire [15:0] sample_in,      // 16-bit audio/sensor sample
    input  wire [15:0] coeff_in,       // 16-bit filter coefficient
    input  wire [4:0]  delay_tap,      // Dynamic delay selector for SRLC32E
    output reg  [31:0] filtered_out,   // Final processed 32-bit output
    output wire        overflow_flag   // Fast carry overflow detection
);

    // --------------------------------------------------------------------------
    // 1. SRLC32E: Dynamic Variable Delay Buffer
    // Buffers the input valid pulse through a 32-bit shift register.
    // --------------------------------------------------------------------------
    wire delayed_valid;
    wire cascade_valid;

    SRLC32E u_srl_delay (
        .CLK(clk),
        .CE(1'b1),
        .D(valid_in),
        .A(delay_tap),
        .Q(delayed_valid),
        .Q31(cascade_valid)
    );

    // --------------------------------------------------------------------------
    // 2. Input Conditioning & Sequential Control Logic
    // --------------------------------------------------------------------------
    reg [26:0] dsp_a_reg;
    reg [17:0] dsp_b_reg;
    reg [47:0] dsp_c_reg;
    reg [1:0]  dsp_state_reg;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            dsp_a_reg     <= 27'd0;
            dsp_b_reg     <= 18'd0;
            dsp_c_reg     <= 48'd0;
            dsp_state_reg <= 2'b00; // bypass
        end else begin
            // Sign-extend input samples for DSP inputs
            dsp_a_reg     <= {{11{sample_in[15]}}, sample_in};
            dsp_b_reg     <= {{2{coeff_in[15]}}, coeff_in};
            dsp_c_reg     <= 48'h0000_0000_1000; // Rounding offset
            // State 2'b10 = accumulate (P <= P + A*B) when delayed valid is high
            dsp_state_reg <= delayed_valid ? 2'b10 : 2'b01;
        end
    end

    // --------------------------------------------------------------------------
    // 3. GEM_DSP48E2: Multi-Cycle Arithmetic MAC Unit
    // Evaluates P <= P + (A * B) natively on GPU ALU (int64_t) with PREG=1
    // --------------------------------------------------------------------------
    wire [47:0] dsp_p_out;

    GEM_DSP48E2 u_dsp_mac (
        .CLK(clk),
        .USE_PRE(1'b0),
        .A(dsp_a_reg),
        .B(dsp_b_reg),
        .C(dsp_c_reg),
        .D(27'd0),
        .STATE(dsp_state_reg),
        .P(dsp_p_out)
    );

    // --------------------------------------------------------------------------
    // 4. CARRY4: High-Speed Post-Scaling Addition
    // Adds a 4-bit calibration bias to the lower bits of the DSP output.
    // --------------------------------------------------------------------------
    wire [3:0] carry_sum;
    wire [3:0] carry_co;
    wire [3:0] dsp_low_bits = dsp_p_out[3:0];
    wire [3:0] bias_bits    = 4'b0101; // Calibration constant +5

    CARRY4 u_carry_bias (
        .CI(1'b0),
        .CYINIT(1'b0),
        .DI(dsp_low_bits),
        .S(dsp_low_bits ^ bias_bits),
        .O(carry_sum),
        .CO(carry_co)
    );

    assign overflow_flag = carry_co[3];

    // --------------------------------------------------------------------------
    // 5. Output Stage
    // --------------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            filtered_out <= 32'd0;
        end else begin
            // Combine DSP high bits with CARRY4 adjusted low bits
            filtered_out <= {dsp_p_out[31:4], carry_sum};
        end
    end

endmodule
