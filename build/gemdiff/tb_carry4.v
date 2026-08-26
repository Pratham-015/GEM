// Differential testbench: CARRY4 slice + cascaded carry chain.
// Reads stimulus vectors, writes results for comparison against the Python
// golden model. Purely combinational -- no clock.
`timescale 1ns/1ps
`include "xilinx_macros_ref.v"

module tb_carry4;
    localparam NBLK = 15;              // 60-bit chain
    localparam NBIT = 4*NBLK;

    // --- single slice ---
    reg  [3:0] S, DI;
    reg        CIN, CYINIT;
    wire [3:0] O, CO;
    CARRY4_ref u_slice (.CO(CO), .O(O), .CI(CIN), .CYINIT(CYINIT), .DI(DI), .S(S));

    // --- cascaded chain ---
    reg  [NBIT-1:0] cS, cDI;
    reg             cCYINIT;
    wire [NBIT-1:0] cO, cCO;
    carry_chain_ref #(.NBLK(NBLK)) u_chain
        (.O(cO), .CO(cCO), .CYINIT(cCYINIT), .DI(cDI), .S(cS));

    integer fi, fo, n;

    // Waveform capture for inspection. Written under sim_out/,
    // never the repo root.
    initial begin
        $dumpfile("sim_out/tb_carry4.vcd");
        $dumpvars(0, tb_carry4);
    end

    initial begin
        // ---- slice vectors ----
        fi = $fopen("sim_out/stim_carry4.txt", "r");
        fo = $fopen("sim_out/res_carry4.txt", "w");
        if (fi == 0 || fo == 0) begin $display("FILE ERROR"); $finish; end
        n = $fscanf(fi, "%h %h %h %h\n", S, DI, CIN, CYINIT);
        while (n == 4) begin
            #1;
            $fdisplay(fo, "%h %h", O, CO);
            n = $fscanf(fi, "%h %h %h %h\n", S, DI, CIN, CYINIT);
        end
        $fclose(fi); $fclose(fo);

        // ---- chain vectors ----
        fi = $fopen("sim_out/stim_chain.txt", "r");
        fo = $fopen("sim_out/res_chain.txt", "w");
        if (fi == 0 || fo == 0) begin $display("FILE ERROR"); $finish; end
        n = $fscanf(fi, "%h %h %h\n", cS, cDI, cCYINIT);
        while (n == 3) begin
            #1;
            $fdisplay(fo, "%h %h", cO, cCO);
            n = $fscanf(fi, "%h %h %h\n", cS, cDI, cCYINIT);
        end
        $fclose(fi); $fclose(fo);
        $finish;
    end
endmodule
