`timescale 1ns/1ps

// Required dependency chain, without parallel shortcuts:
// DSP48E2(PREG) -> CARRY4 -> SRLC32E -> DSP48E2(PREG).
module exact_macro_chain (
    input  wire        clk,
    input  wire [26:0] a0,
    input  wire [26:0] d0,
    input  wire [17:0] b0,
    input  wire [47:0] c0,
    input  wire [1:0]  state0,
    input  wire        use_pre0,
    input  wire [3:0]  carry_di,
    input  wire        carry_cin,
    input  wire        srl_ce,
    input  wire [4:0]  srl_addr,
    input  wire [26:0] a1,
    input  wire [26:0] d1,
    input  wire [17:0] b1,
    input  wire [47:0] c1,
    input  wire [1:0]  state1,
    input  wire        use_pre1,
    output wire [47:0] p0,
    output wire [3:0]  carry_o,
    output wire [3:0]  carry_co,
    output wire        q,
    output wire        q31,
    output wire [47:0] p1,
    output wire        chain_probe
);
`ifdef GOLDEN
    dsp48e2_ref dsp0 (.P(p0), .clk(clk), .A(a0), .D(d0), .B(b0),
        .C(c0), .state(state0), .use_pre(use_pre0));
    CARRY4_ref carry0 (.O(carry_o), .CO(carry_co), .S(p0[3:0]),
        .DI(carry_di), .CI(carry_cin), .CYINIT(1'b0));
    srlc32e_ref srl0 (.Q(q), .Q31(q31), .clk(clk), .CE(srl_ce),
        .D(^carry_o), .A(srl_addr));
    dsp48e2_ref dsp1 (.P(p1), .clk(clk), .A(a1 ^ {26'd0, q}), .D(d1),
        .B(b1), .C(c1), .state(state1), .use_pre(use_pre1));
`else
    wire [8:0] opmode0 = state0 == 0 ? 9'h030 : state0 == 1 ? 9'h005 : 9'h025;
    wire [8:0] opmode1 = state1 == 0 ? 9'h030 : state1 == 1 ? 9'h005 : 9'h025;
    DSP48E2 #(.AREG(0), .BREG(0), .CREG(0), .DREG(0), .ADREG(0),
        .MREG(0), .PREG(1), .ACASCREG(0), .BCASCREG(0), .ALUMODEREG(0),
        .INMODEREG(0), .OPMODEREG(0), .CARRYINREG(0),
        .CARRYINSELREG(0), .AMULTSEL("AD")) dsp0 (
        .P(p0), .CLK(clk), .A({{3{a0[26]}},a0}), .D(d0), .B(b0), .C(c0),
        .OPMODE(opmode0), .ALUMODE(4'b0), .INMODE({2'b0,use_pre0,2'b0}));
    CARRY4 carry0 (.O(carry_o), .CO(carry_co), .S(p0[3:0]),
        .DI(carry_di), .CI(carry_cin), .CYINIT(1'b0));
    SRLC32E srl0 (.Q(q), .Q31(q31), .CLK(clk), .CE(srl_ce),
        .D(^carry_o), .A(srl_addr));
    DSP48E2 #(.AREG(0), .BREG(0), .CREG(0), .DREG(0), .ADREG(0),
        .MREG(0), .PREG(1), .ACASCREG(0), .BCASCREG(0), .ALUMODEREG(0),
        .INMODEREG(0), .OPMODEREG(0), .CARRYINREG(0),
        .CARRYINSELREG(0), .AMULTSEL("AD")) dsp1 (
        .P(p1), .CLK(clk), .A({{3{a1[26]}},(a1 ^ {26'd0,q})}), .D(d1),
        .B(b1), .C(c1), .OPMODE(opmode1), .ALUMODE(4'b0),
        .INMODE({2'b0,use_pre1,2'b0}));
`endif
    assign chain_probe = p0[47] ^ carry_co[3] ^ q ^ q31 ^ p1[0] ^ p1[47];
endmodule
