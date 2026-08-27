// Differential testbench: SRLC32E against the REAL Xilinx UNISIM primitive
// (not xilinx_macros_ref.v). Reuses stim_srl.txt; same result format as
// tb_srlc32e.v so diff_harness.py can compare both against the same golden
// model. Real primitive's clock port is named CLK (not clk), and it takes
// INIT/IS_CLK_INVERTED parameters -- left at their default (INIT=0,
// IS_CLK_INVERTED=0) to match srlc32e_ref, which always starts at zero.
`timescale 1ns/1ps

module tb_srlc32e_unisim;
    reg        clk;
    reg        CE, D;
    reg  [4:0] A;
    wire       Q, Q31;

    SRLC32E u_srl (.Q(Q), .Q31(Q31), .CLK(clk), .CE(CE), .D(D), .A(A));

    reg q_cap, q31_cap;
    integer fi, fo, n;

    initial begin
        clk = 1'b0;
        fi = $fopen("sim_out/stim_srl.txt", "r");
        fo = $fopen("sim_out/res_srl_unisim.txt", "w");
        if (fi == 0 || fo == 0) begin $display("FILE ERROR"); $finish; end

        n = $fscanf(fi, "%h %h %h\n", D, CE, A);
        while (n == 3) begin
            #1;
            q_cap   = Q;
            q31_cap = Q31;
            clk = 1'b1; #1;
            clk = 1'b0; #1;
            $fdisplay(fo, "%h %h %h", q_cap, q31_cap, u_srl.data);
            n = $fscanf(fi, "%h %h %h\n", D, CE, A);
        end
        $fclose(fi); $fclose(fo);
        $finish;
    end
endmodule
