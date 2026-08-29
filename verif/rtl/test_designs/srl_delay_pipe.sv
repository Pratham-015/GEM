// SPDX-License-Identifier: Apache-2.0
// Variable delay line test design using SRLC32E.
module srl_delay_pipe (
    input  logic       clk,
    input  logic       ce,
    input  logic       din,
    input  logic [4:0] delay_addr,
    output logic       dout,
    output logic       cascade_out
);

    SRLC32E srl_inst (
        .CLK(clk),
        .CE(ce),
        .D(din),
        .A(delay_addr),
        .Q(dout),
        .Q31(cascade_out)
    );

endmodule

