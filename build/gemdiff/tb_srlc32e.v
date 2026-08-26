// Differential testbench: SRLC32E 32-bit shift register LUT.
// Per cycle: apply inputs, sample the COMBINATIONAL outputs against the
// current register contents, then clock and record the new register value.
`timescale 1ns/1ps
`include "xilinx_macros_ref.v"

module tb_srlc32e;
    reg        clk;
    reg        CE, D;
    reg  [4:0] A;
    wire       Q, Q31;

    srlc32e_ref u_srl (.Q(Q), .Q31(Q31), .clk(clk), .CE(CE), .D(D), .A(A));

    reg q_cap, q31_cap;
    integer fi, fo, n;

    // Waveform capture for inspection. Written under sim_out/,
    // never the repo root.
    initial begin
        $dumpfile("sim_out/tb_srlc32e.vcd");
        $dumpvars(0, tb_srlc32e);
    end

    initial begin
        clk = 1'b0;
        fi = $fopen("sim_out/stim_srl.txt", "r");
        fo = $fopen("sim_out/res_srl.txt", "w");
        if (fi == 0 || fo == 0) begin $display("FILE ERROR"); $finish; end

        n = $fscanf(fi, "%h %h %h\n", D, CE, A);
        while (n == 3) begin
            #1;                       // combinational read of CURRENT state
            q_cap   = Q;
            q31_cap = Q31;
            clk = 1'b1; #1;           // rising edge: shift happens
            clk = 1'b0; #1;
            // hierarchical peek at the register so the harness can compare
            // the full 32-bit state, not just the two output bits
            $fdisplay(fo, "%h %h %h", q_cap, q31_cap, u_srl.state);
            n = $fscanf(fi, "%h %h %h\n", D, CE, A);
        end
        $fclose(fi); $fclose(fo);
        $finish;
    end
endmodule
