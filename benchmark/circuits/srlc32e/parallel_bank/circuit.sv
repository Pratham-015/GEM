module srlc32e_parallel_bank (
    input  wire        clk,
    input  wire [63:0] data,
    output wire [63:0] result
);
    wire [127:0] q;
    wire [127:0] q31;

    genvar i;
    generate
        for (i = 0; i < 128; i = i + 1) begin : srl_bank
`ifdef SHREDDED
            reg [31:0] state;
            initial state = 32'd0;
            always @(posedge clk) begin
                if (data[(i + 1) % 64])
                    state <= {state[30:0], data[(i*5 + 3) % 64]};
            end
            assign q[i] = state[data[(i*7) % 59 +: 5]];
            assign q31[i] = state[31];
`else
            SRLC32E unit (
                .Q(q[i]), .Q31(q31[i]), .CLK(clk),
                .CE(data[(i + 1) % 64]), .D(data[(i*5 + 3) % 64]),
                .A(data[(i*7) % 59 +: 5])
            );
`endif
        end
    endgenerate

    assign result = q[63:0] ^ q[127:64] ^ q31[63:0] ^ q31[127:64];
endmodule
