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
    logic [3:0] carry_co [0:15];

    assign carry[0] = cin;

    genvar i;
    generate
        for (i = 0; i < 16; i = i + 1) begin : gen_carry4
            assign s[i*4 +: 4]  = a[i*4 +: 4] ^ b[i*4 +: 4];
            assign di[i*4 +: 4] = a[i*4 +: 4];

            CARRY4 carry4_inst (
                .CO(carry_co[i]),
                .O(sum[i*4 +: 4]),
                .CI(carry[i]),
                .CYINIT(1'b0),
                .DI(di[i*4 +: 4]),
                .S(s[i*4 +: 4])
            );

            // The cascade input is specifically CO[3].  Connecting the
            // four-bit CO port directly to a scalar would truncate to CO[0].
            assign carry[i+1] = carry_co[i][3];
        end
    endgenerate

    assign cout = carry[16];

endmodule
