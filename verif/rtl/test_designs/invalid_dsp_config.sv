module invalid_dsp_config(input wire clk, output wire [47:0] p);
    DSP48E2 #(.AREG(1), .BREG(0), .CREG(0), .DREG(0), .ADREG(0),
        .MREG(0), .PREG(1)) bad (
        .P(p), .CLK(clk), .A(30'b0), .B(18'b0), .C(48'b0), .D(27'b0),
        .OPMODE(9'h005), .ALUMODE(4'b0), .INMODE(5'b0));
endmodule
