module CARRY4(
    output [3:0] CO,
    output [3:0] O,
    input  [3:0] DI,
    input  [3:0] S,
    input        CYINIT,
    input        CI
);
    wire [4:0] c;
    assign c[0] = CYINIT | CI;
    assign O[0] = S[0] ^ c[0];
    assign c[1] = S[0] ? c[0] : DI[0];
    assign O[1] = S[1] ^ c[1];
    assign c[2] = S[1] ? c[1] : DI[1];
    assign O[2] = S[2] ^ c[2];
    assign c[3] = S[2] ? c[2] : DI[2];
    assign O[3] = S[3] ^ c[3];
    assign c[4] = S[3] ? c[3] : DI[3];
    
    assign CO = c[4:1];
endmodule

module DSP48E2(
    output [47:0] P,
    input         CLK,
    input         USE_PRE,
    input  [26:0] A,
    input  [17:0] B,
    input  [47:0] C,
    input  [26:0] D,
    input  [1:0]  STATE
);
    reg [47:0] preg;
    assign P = preg;
    always @(posedge CLK) begin
        preg <= C + (A * B);
    end
endmodule

module SRLC32E(
    output Q,
    output Q31,
    input  CLK,
    input  CE,
    input  D,
    input  [4:0] A
);
    reg [31:0] shift_reg;
    assign Q31 = shift_reg[31];
    assign Q = shift_reg[A];
    always @(posedge CLK) begin
        if (CE) shift_reg <= {shift_reg[30:0], D};
    end
endmodule
