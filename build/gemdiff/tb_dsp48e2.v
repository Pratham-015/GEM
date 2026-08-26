// Differential testbench: DSP48E2 simplified subset (PREG=1, all else comb).
// One stimulus line per clock cycle; records the P register AFTER each edge.
`timescale 1ns/1ps
`include "xilinx_macros_ref.v"

module tb_dsp48e2;
    reg                clk;
    reg  signed [26:0] A, D;
    reg  signed [17:0] B;
    reg  signed [47:0] C;
    reg         [1:0]  state;
    reg                use_pre;
    wire signed [47:0] P;

    dsp48e2_ref u_dsp (.P(P), .clk(clk), .A(A), .D(D), .B(B), .C(C),
                       .state(state), .use_pre(use_pre));

    integer fi, fo, n;

    // Waveform capture for inspection. Written under sim_out/,
    // never the repo root.
    initial begin
        $dumpfile("sim_out/tb_dsp48e2.vcd");
        $dumpvars(0, tb_dsp48e2);
    end

    initial begin
        clk = 1'b0;
        fi = $fopen("sim_out/stim_dsp.txt", "r");
        fo = $fopen("sim_out/res_dsp.txt", "w");
        if (fi == 0 || fo == 0) begin $display("FILE ERROR"); $finish; end

        n = $fscanf(fi, "%h %h %h %h %h %h\n", A, D, B, C, state, use_pre);
        while (n == 6) begin
            #1;                 // let the combinational cone settle
            clk = 1'b1; #1;     // rising edge: P latches
            clk = 1'b0; #1;
            $fdisplay(fo, "%h", P);
            n = $fscanf(fi, "%h %h %h %h %h %h\n", A, D, B, C, state, use_pre);
        end
        $fclose(fi); $fclose(fo);
        $finish;
    end
endmodule
