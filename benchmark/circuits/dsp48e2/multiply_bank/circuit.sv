module dsp_multiply_bank (
    input  wire        clk,
    input  wire [63:0] data,
    output wire [63:0] result
);
    wire [47:0] p [0:7];

    genvar i;
    generate
        for (i = 0; i < 8; i = i + 1) begin : dsp_bank
`ifdef SHREDDED
            reg  [47:0] p_reg;
            reg  [26:0] ad;
            reg  [44:0] product;
            initial p_reg = 48'd0;
            always @(*) begin
                ad = data[26:0] + (data[53:27] ^ {23'd0, i[3:0]});
                product = $signed(ad) * $signed(data[17:0] ^ {14'd0, i[3:0]});
            end
            always @(posedge clk) begin
                p_reg <= {{3{product[44]}}, product};
            end
            assign p[i] = p_reg;
`else
            DSP48E2 #(
                .AREG(0), .BREG(0), .CREG(0), .DREG(0),
                .ADREG(0), .MREG(0), .PREG(1),
                .ACASCREG(0), .BCASCREG(0),
                .ALUMODEREG(0), .INMODEREG(0), .OPMODEREG(0),
                .CARRYINREG(0), .CARRYINSELREG(0), .AMULTSEL("AD")
            ) unit (
                .P(p[i]), .CLK(clk),
                .A({{3{data[26]}}, data[26:0]}),
                .D(data[53:27] ^ {23'd0, i[3:0]}),
                .B(data[17:0] ^ {14'd0, i[3:0]}),
                .C(data[47:0]), .OPMODE(9'h005),
                .ALUMODE(4'b0000), .INMODE(5'b00100)
            );
`endif
        end
    endgenerate

    assign result = {16'd0, p[0]} ^ {16'd0, p[1]} ^
                    {16'd0, p[2]} ^ {16'd0, p[3]} ^
                    {16'd0, p[4]} ^ {16'd0, p[5]} ^
                    {16'd0, p[6]} ^ {16'd0, p[7]};
endmodule
