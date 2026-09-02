`timescale 1ns/1ps
module tb_exact_macro_chain;
    reg clk = 0;
    reg [26:0] a0=0,d0=0,a1=0,d1=0;
    reg [17:0] b0=0,b1=0;
    reg [47:0] c0=0,c1=0;
    reg [1:0] state0=0,state1=0;
    reg use_pre0=0,use_pre1=0;
    reg [3:0] carry_di=0;
    reg carry_cin=0,srl_ce=0;
    reg [4:0] srl_addr=0;
    wire [47:0] p0,p1;
    wire [3:0] carry_o,carry_co;
    wire q,q31,chain_probe;
    exact_macro_chain dut (.*);
    always #5 clk = ~clk;
    integer cycle;
    reg [63:0] prng = 64'hd1b54a32d192ed03;
    initial begin
        $dumpfile("/tmp/gem_exact_chain_golden.vcd");
        $dumpvars(0,dut);
        for (cycle=0; cycle<128; cycle=cycle+1) begin
            @(negedge clk); #2;
            prng = prng * 64'h5851f42d4c957f2d + 64'h14057b7ef767814f;
            a0=prng[26:0]; d0=prng[53:27]; b0=prng[45:28]; c0={prng[31:0],prng[63:48]};
            state0=cycle%3; use_pre0=prng[7]; carry_di=prng[11:8]; carry_cin=prng[12];
            srl_ce=(cycle%4)!=0; srl_addr=prng[17:13];
            a1=~prng[26:0]; d1=prng[58:32]; b1=prng[35:18]; c1={prng[47:0]};
            state1=(cycle+1)%3; use_pre1=prng[19];
        end
        @(posedge clk); #1 $finish;
    end
endmodule
