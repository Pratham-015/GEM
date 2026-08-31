// SPDX-License-Identifier: Apache-2.0
module half_adder (
    input  A,
    input  B,
    output Sum,
    output Carry
);

    assign Sum   = A ^ B;
    assign Carry = A & B;

endmodule

