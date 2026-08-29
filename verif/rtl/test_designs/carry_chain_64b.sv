// SPDX-License-Identifier: Apache-2.0
// 64-bit adder test design built from 16 chained CARRY4 primitives.
module carry_chain_64b (
    input  logic [63:0] a,
    input  logic [63:0] b,
    input  logic        cin,
    output logic [63:0] sum,
    output logic        cout
);

    logic [63:0] s;
    logic [63:0] di;
    logic [16:0] carry;

    assign carry[0] = cin;

    genvar i;
    generate
        for (i = 0; i < 16; i = i + 1) begin : gen_carry4
            assign s[i*4 +: 4]  = a[i*4 +: 4] ^ b[i*4 +: 4];
            assign di[i*4 +: 4] = a[i*4 +: 4];

            CARRY4 carry4_inst (
                .CO(carry[i+1]),    // carry[i+1] captures CO[3]
                .O(sum[i*4 +: 4]),
                .CI(carry[i]),
                .CYINIT(1'b0),
                .DI(di[i*4 +: 4]),
                .S(s[i*4 +: 4])
            );
        end
    endgenerate

    assign cout = carry[16];

endmodule

