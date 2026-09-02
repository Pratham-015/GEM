`timescale 1ns/1ps

module integrated_macro_top (
    input  wire        clk,
    input  wire [63:0] x,
    input  wire [63:0] y,
    input  wire        cin,
    input  wire [26:0] dsp_a,
    input  wire [26:0] dsp_d,
    input  wire [17:0] dsp_b,
    input  wire [47:0] dsp_c,
    input  wire [1:0]  dsp_state,
    input  wire        dsp_use_pre,
    input  wire        srl_ce,
    input  wire [4:0]  srl_addr,
    output wire [63:0] sum,
    output wire [63:0] carry,
    output wire [47:0] p,
    output wire        q,
    output wire        q31,
    output wire        glue,
    output reg         neg_probe
);
    wire [63:0] s = x ^ y;
    wire [63:0] di = x & y;

    genvar i;
    generate for (i = 0; i < 16; i = i + 1) begin : carry_chain
`ifdef GOLDEN
        CARRY4_ref c4 (.CO(carry[4*i +: 4]), .O(sum[4*i +: 4]),
`else
        CARRY4 c4 (.CO(carry[4*i +: 4]), .O(sum[4*i +: 4]),
`endif
            .CI(i == 0 ? cin : carry[4*i-1]), .CYINIT(1'b0),
            .DI(di[4*i +: 4]), .S(s[4*i +: 4]));
    end endgenerate

    // Carry -> ordinary RTL -> DSP dependency.
    wire [26:0] mixed_a = dsp_a ^ sum[26:0];

`ifdef GOLDEN
    dsp48e2_ref dsp (.P(p), .clk(clk), .A(mixed_a), .D(dsp_d), .B(dsp_b),
        .C(dsp_c), .state(dsp_state), .use_pre(dsp_use_pre));
    srlc32e_ref srl (.Q(q), .Q31(q31), .clk(clk), .CE(srl_ce),
        .D(^sum), .A(srl_addr));
`else
    wire [8:0] dsp_opmode = (dsp_state == 2'd0) ? 9'h030 :
                             (dsp_state == 2'd1) ? 9'h005 : 9'h025;
    DSP48E2 #(.AREG(0), .BREG(0), .CREG(0), .DREG(0), .ADREG(0),
        .MREG(0), .PREG(1), .ACASCREG(0), .BCASCREG(0),
        .ALUMODEREG(0), .INMODEREG(0), .OPMODEREG(0),
        .CARRYINREG(0), .CARRYINSELREG(0), .AMULTSEL("AD")) dsp (
        .P(p), .CLK(clk), .A({{3{mixed_a[26]}}, mixed_a}), .D(dsp_d),
        .B(dsp_b), .C(dsp_c), .OPMODE(dsp_opmode), .ALUMODE(4'b0),
        .INMODE({2'b0, dsp_use_pre, 2'b0}));
    SRLC32E srl (.Q(q), .Q31(q31), .CLK(clk), .CE(srl_ce),
        .D(^sum), .A(srl_addr));
`endif

    // Macro -> AIG fanout from all macro classes.
    assign glue = p[47] ^ p[0] ^ q ^ q31 ^ sum[0] ^ carry[63];
    always @(negedge clk)
        neg_probe <= glue;
endmodule
