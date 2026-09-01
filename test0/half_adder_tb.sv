// SPDX-License-Identifier: Apache-2.0
`timescale 1ns / 1ps

`include "aigpdk/aigpdk.v"
`include "test0/half_adder_gatelevel.gv"

module half_adder_tb;
    reg  A;
    reg  B;
    wire sum_gate;
    wire carry_gate;

    // Gate-level synthesized netlist instance from half_adder_gatelevel.gv
    half_adder u_gate (
        .A(A),
        .B(B),
        .Sum(sum_gate),
        .Carry(carry_gate)
    );

    wire sum_expected   = A ^ B;
    wire carry_expected = A & B;

    integer i;
    reg match;

    initial begin
        match = 1'b1;
        $display("   Half Adder: RTL vs AIG Gatelevel Verification   ");

        for (i = 0; i < 4; i = i + 1) begin
            {A, B} = i[1:0];
            #1;
            $display("Input: A=%b, B=%b | Expected: Sum=%b, Carry=%b | Gatelevel: Sum=%b, Carry=%b",
                     A, B, sum_expected, carry_expected, sum_gate, carry_gate);

            if ((sum_expected !== sum_gate) || (carry_expected !== carry_gate)) begin
                $display("ERROR: Mismatch at input A=%b, B=%b!", A, B);
                match = 1'b0;
            end
        end

        if (match) begin
            $display("   VERIFICATION PASSED: 100%% Bit-Exact Match!    ");
            $finish(0);
        end else begin
            $display("   VERIFICATION FAILED!                          ");
            $finish(1);
        end
    end
endmodule

