// Differential testbench: the project's simplified DSP48E2 (PREG=1, all
// else combinational, 2-bit `state`/`use_pre` control) against the REAL
// Xilinx UNISIM DSP48E2 primitive, driven through its native OPMODE/
// ALUMODE/INMODE/CARRYINSEL buses. Reuses stim_dsp.txt; same result format
// as tb_dsp48e2.v so diff_harness.py can compare both against the same
// golden model.
//
// Mapping derived by reading DSP48E2.v's behavioural model directly (not
// guessed from documentation prose):
//
//   Pipeline stages: AREG=BREG=CREG=DREG=ADREG=MREG=ALUMODEREG=INMODEREG
//                     =OPMODEREG=CARRYINSELREG=CARRYINREG=0, PREG=1.
//                     Matches xilinx_macros_ref.v's dsp48e2_ref exactly.
//
//   Pre-adder (use_pre): AMULTSEL="AD" routes the pre-adder output into the
//   multiplier's A operand unconditionally (DSP48E2.v:1592-1595); the
//   dynamic part is INMODE[2], which selects whether D joins the sum
//   (D_DATA_mux = INMODE[2] ? D : 0; AD_in = INMODE[3] ? D_DATA_mux-PREADD_AB
//   : D_DATA_mux+PREADD_AB -- DSP48E2.v:1729-1730). With INMODE[3]=0 fixed:
//     use_pre=0 -> INMODE[2]=0 -> AD_in = 0 + A = A            (AD = A)
//     use_pre=1 -> INMODE[2]=1 -> AD_in = D + A                (AD = A+D)
//   INMODE[1:0]=00 and INMODE[4]=0 keep A2A1/B2B1 on the direct (registered
//   -bypass) A/B path (DSP48E2.v:1752-1759), matching the spec's AREG=BREG=0.
//   So per vector: INMODE = 5'b00{use_pre}00.
//
//   ALU state (state): OPMODE[8:0] selects the W/Z/Y/X operands feeding the
//   adder (DSP48E2.v:1223-1264); ALUMODE=4'b0000 is a plain add in every
//   state, so P_next = W + X + Y + Z + CARRYIN with CARRYIN tied 0:
//     state=0 (P<=C):   W=0(00) Z=C(011) Y=0(00) X=0(00) -> OPMODE=9'b000_011_00_00
//     state=1 (P<=M):   W=0(00) Z=0(000) Y=U(01) X=V(01) -> OPMODE=9'b000_000_01_01
//                        (U_DATA/V_DATA are the multiplier's split product;
//                        X=U,Y=V reconstructs M = U_DATA + V_DATA exactly)
//     state=2 (P<=P+M): W=0(00) Z=P_FDBK(010) Y=U(01) X=U(01)
//                        -> OPMODE=9'b000_010_01_01
//   CARRYINSEL=3'b000 selects the CARRYIN pin directly; CARRYIN tied 0.
`timescale 1ns/1ps

module tb_dsp48e2_unisim;
    reg                clk;
    reg  signed [26:0] A27, D;
    reg  signed [17:0] B;
    reg  signed [47:0] C;
    reg         [1:0]  state;
    reg                use_pre;
    wire signed [47:0] P;

    // OPMODE[8:0] = {W[1:0], Z[2:0], Y[1:0], X[1:0]}.
    wire [8:0] opmode = (state == 2'd0) ? 9'b000110000 :  // W=0 Z=C(011) Y=0 X=0
                         (state == 2'd1) ? 9'b000000101 :  // W=0 Z=0 Y=U(01) X=V(01)
                                           9'b000100101;   // W=0 Z=P(010) Y=U(01) X=V(01)
    wire [4:0] inmode = {2'b00, use_pre, 2'b00};

    // DSP48E2's reset paths gate on `... || glblGSR`, so a bare glbl
    // instance is required for elaboration even with all resets tied 0.
    glbl glbl();

    DSP48E2 #(
        .AREG(0), .BREG(0), .CREG(0), .DREG(0), .ADREG(0), .MREG(0), .PREG(1),
        .ACASCREG(0), .BCASCREG(0),
        .ALUMODEREG(0), .INMODEREG(0), .OPMODEREG(0),
        .CARRYINREG(0), .CARRYINSELREG(0),
        .AMULTSEL("AD"), .BMULTSEL("B"), .PREADDINSEL("A"),
        .USE_MULT("MULTIPLY"), .USE_SIMD("ONE48")
    ) u_dsp (
        .P(P), .CLK(clk),
        .A({{3{A27[26]}}, A27}), .D(D), .B(B), .C(C),
        .OPMODE(opmode), .ALUMODE(4'b0000), .INMODE(inmode),
        .CARRYIN(1'b0), .CARRYINSEL(3'b000),
        .ACIN(30'b0), .BCIN(18'b0), .PCIN(48'b0),
        .CARRYCASCIN(1'b0), .MULTSIGNIN(1'b0),
        .CEA1(1'b1), .CEA2(1'b1), .CEAD(1'b1), .CEALUMODE(1'b1),
        .CEB1(1'b1), .CEB2(1'b1), .CEC(1'b1), .CECARRYIN(1'b1),
        .CECTRL(1'b1), .CED(1'b1), .CEINMODE(1'b1), .CEM(1'b1), .CEP(1'b1),
        .RSTA(1'b0), .RSTALLCARRYIN(1'b0), .RSTALUMODE(1'b0), .RSTB(1'b0),
        .RSTC(1'b0), .RSTCTRL(1'b0), .RSTD(1'b0), .RSTINMODE(1'b0),
        .RSTM(1'b0), .RSTP(1'b0)
    );

    integer fi, fo, n;

    initial begin
        clk = 1'b0;
        // glbl's GSR pulse holds every register in reset for its first
        // ROC_WIDTH (100 ns per glbl.v) -- P would silently read back 0 for
        // every vector run before that window closes.
        #101;
        fi = $fopen("sim_out/stim_dsp.txt", "r");
        fo = $fopen("sim_out/res_dsp_unisim.txt", "w");
        if (fi == 0 || fo == 0) begin $display("FILE ERROR"); $finish; end

        n = $fscanf(fi, "%h %h %h %h %h %h\n", A27, D, B, C, state, use_pre);
        while (n == 6) begin
            #1;
            clk = 1'b1; #1;
            clk = 1'b0; #1;
            $fdisplay(fo, "%h", P);
            n = $fscanf(fi, "%h %h %h %h %h %h\n", A27, D, B, C, state, use_pre);
        end
        $fclose(fi); $fclose(fo);
        $finish;
    end
endmodule
