// Differential testbench: CARRY4 slice + cascaded carry chain, against the
// REAL Xilinx UNISIM primitive (not xilinx_macros_ref.v). Same stimulus
// files, same vector format as tb_carry4.v, so diff_harness.py can compare
// both Verilog runs against the same Python golden model.
`timescale 1ns/1ps

// Cascade of NBLK real CARRY4 primitives, wired CO[3] -> CI, mirroring
// carry_chain_ref's topology in xilinx_macros_ref.v exactly.
module carry_chain_real #(
    parameter NBLK = 15
) (
    output [4*NBLK-1:0] O,
    output [4*NBLK-1:0] CO,
    input               CYINIT,
    input  [4*NBLK-1:0] DI,
    input  [4*NBLK-1:0] S
);
    wire [NBLK:0] cc;
    assign cc[0] = 1'b0;

    genvar b;
    generate
        for (b = 0; b < NBLK; b = b + 1) begin : gen_blk
            CARRY4 u_c4 (
                .CO     (CO[4*b+3 -: 4]),
                .O      (O [4*b+3 -: 4]),
                .CI     ((b == 0) ? 1'b0   : cc[b]),
                .CYINIT ((b == 0) ? CYINIT : 1'b0),
                .DI     (DI[4*b+3 -: 4]),
                .S      (S [4*b+3 -: 4])
            );
            assign cc[b+1] = CO[4*b+3];
        end
    endgenerate
endmodule

module tb_carry4_unisim;
    localparam NBLK = 15;
    localparam NBIT = 4*NBLK;

    // CARRY4 declares `tri0 glblGSR = glbl.GSR;` unconditionally (see
    // UNISIM CARRY4.v) even though glblGSR is never read by its
    // combinational logic. Icarus still needs the hierarchical name to
    // resolve at elaboration, so a bare glbl instance is required here --
    // its value has no effect on CARRY4's O/CO outputs.
    glbl glbl();

    // --- single slice ---
    reg  [3:0] S, DI;
    reg        CIN, CYINIT;
    wire [3:0] O, CO;
    CARRY4 u_slice (.CO(CO), .O(O), .CI(CIN), .CYINIT(CYINIT), .DI(DI), .S(S));

    // --- cascaded chain ---
    reg  [NBIT-1:0] cS, cDI;
    reg             cCYINIT;
    wire [NBIT-1:0] cO, cCO;
    carry_chain_real #(.NBLK(NBLK)) u_chain
        (.O(cO), .CO(cCO), .CYINIT(cCYINIT), .DI(cDI), .S(cS));

    integer fi, fo, n;

    initial begin
        // ---- slice vectors (reuses stim_carry4.txt from the custom-ref run) ----
        fi = $fopen("sim_out/stim_carry4.txt", "r");
        fo = $fopen("sim_out/res_carry4_unisim.txt", "w");
        if (fi == 0 || fo == 0) begin $display("FILE ERROR"); $finish; end
        n = $fscanf(fi, "%h %h %h %h\n", S, DI, CIN, CYINIT);
        while (n == 4) begin
            #1;
            $fdisplay(fo, "%h %h", O, CO);
            n = $fscanf(fi, "%h %h %h %h\n", S, DI, CIN, CYINIT);
        end
        $fclose(fi); $fclose(fo);

        // ---- chain vectors (reuses stim_chain.txt) ----
        fi = $fopen("sim_out/stim_chain.txt", "r");
        fo = $fopen("sim_out/res_chain_unisim.txt", "w");
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
