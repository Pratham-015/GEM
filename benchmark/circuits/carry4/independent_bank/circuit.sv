module carry4_independent_bank (
    input  wire        clk,
    input  wire [63:0] data,
    output wire [1024:0] result
);
    wire [511:0] carry_o;
    wire [511:0] carry_co;
    reg heartbeat;
    initial heartbeat = 1'b0;
    always @(posedge clk) heartbeat <= data[63];

    genvar i;
    generate
        for (i = 0; i < 128; i = i + 1) begin : carry_bank
`ifdef SHREDDED
            wire [4:0] c;
            assign c[0] = data[(i + 1) % 64] | data[(i + 2) % 64];
            assign carry_o[i*4 + 0] = data[(i*3 + 0) % 64] ^ c[0];
            assign c[1] = data[(i*3 + 0) % 64] ? c[0] : data[(i*5 + 7) % 64];
            assign carry_o[i*4 + 1] = data[(i*3 + 1) % 64] ^ c[1];
            assign c[2] = data[(i*3 + 1) % 64] ? c[1] : data[(i*5 + 8) % 64];
            assign carry_o[i*4 + 2] = data[(i*3 + 2) % 64] ^ c[2];
            assign c[3] = data[(i*3 + 2) % 64] ? c[2] : data[(i*5 + 9) % 64];
            assign carry_o[i*4 + 3] = data[(i*3 + 3) % 64] ^ c[3];
            assign c[4] = data[(i*3 + 3) % 64] ? c[3] : data[(i*5 + 10) % 64];
            assign carry_co[i*4 +: 4] = c[4:1];
`else
            CARRY4 unit (
                .O(carry_o[i*4 +: 4]), .CO(carry_co[i*4 +: 4]),
                .DI({data[(i*5 + 10) % 64], data[(i*5 + 9) % 64],
                     data[(i*5 + 8) % 64], data[(i*5 + 7) % 64]}),
                .S({data[(i*3 + 3) % 64], data[(i*3 + 2) % 64],
                    data[(i*3 + 1) % 64], data[(i*3 + 0) % 64]}),
                .CI(data[(i + 1) % 64]), .CYINIT(data[(i + 2) % 64])
            );
`endif
        end
    endgenerate

    assign result = {heartbeat, carry_co, carry_o};
endmodule
