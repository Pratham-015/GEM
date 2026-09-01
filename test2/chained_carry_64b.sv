// test2/chained_carry_64b.sv
// 64-bit Adder composed of 16 chained CARRY4 primitives (CO[3] -> CI ripple).
// Demonstrates macro-to-macro dependency resolution without intermediate gates.
`timescale 1ns / 1ps

module chained_carry_64b (
    input  wire [63:0] a,
    input  wire [63:0] b,
    input  wire        cin,
    output wire [63:0] sum,
    output wire        cout
);

    wire [63:0] s_wire;
    wire [63:0] di_wire;
    assign s_wire  = a ^ b;
    assign di_wire = a & b;

    wire [3:0] co[0:15];
    wire [3:0] s_out[0:15];

    genvar i;
    generate
        for (i = 0; i < 16; i = i + 1) begin : gen_carry
            wire ci_in = (i == 0) ? cin : co[i-1][3];
            CARRY4 u_c4 (
                .CO(co[i]),
                .O(s_out[i]),
                .CI(ci_in),
                .CYINIT(1'b0),
                .DI(di_wire[i*4 +: 4]),
                .S(s_wire[i*4 +: 4])
            );
            assign sum[i*4 +: 4] = s_out[i];
        end
    endgenerate

    assign cout = co[15][3];

endmodule
