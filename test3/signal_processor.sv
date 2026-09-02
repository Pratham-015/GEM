module signal_processor(
    input clk,
    input [7:0] in_a,
    input [7:0] in_b,
    input [17:0] coeff,
    input [4:0] tap_sel,
    output [47:0] out_p,
    output out_parity
);
    wire [7:0] s_sum;
    wire [3:0] co_0;
    wire [3:0] co_1;
    
    CARRY4 c0 (
        .CO(co_0), .O(s_sum[3:0]), 
        .DI(in_a[3:0]), .S(in_a[3:0] ^ in_b[3:0]), .CYINIT(1'b0), .CI(1'b0)
    );
    
    CARRY4 c1 (
        .CO(co_1), .O(s_sum[7:4]), 
        .DI(in_a[7:4]), .S(in_a[7:4] ^ in_b[7:4]), .CYINIT(1'b0), .CI(co_0[3])
    );
    
    wire [47:0] mac_out;
    GEM_DSP48E2 dsp (
        .P(mac_out),
        .CLK(clk),
        .USE_PRE(1'b0),
        .A({{19{s_sum[7]}}, s_sum}),
        .B(coeff),
        .C(48'd0),
        .D(27'd0),
        // PS state 1 is the registered multiplier result.  State 0 is the
        // C-bypass mode and, with C tied low here, would intentionally
        // produce zero rather than exercise the multiplier.
        .STATE(2'b01)
    );
    
    wire parity = ^s_sum;
    wire delayed_parity;
    
    SRLC32E srl (
        .Q(delayed_parity),
        .Q31(),
        .CLK(clk),
        .CE(1'b1),
        .D(parity),
        .A(tap_sel)
    );
    
    // The DSP already contains the sole PS-mandated PREG.  Expose it directly
    // so this benchmark compares macro preservation rather than adding a
    // second, unrelated register stage after the primitive.
    assign out_p = mac_out;
    assign out_parity = delayed_parity;
endmodule
