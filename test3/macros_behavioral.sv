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
    reg [26:0] ad;
    reg [44:0] product;

    assign P = preg;
    always @(*) begin
        // Assignment to the fixed-width vectors performs the PS-mandated
        // 27-bit pre-adder and 45-bit product truncation.  Keep the declared
        // nets unsigned so Yosys' structural writer does not emit a `signed`
        // qualifier that the historical upstream GEM parser cannot consume;
        // the casts still make the actual multiply two's-complement signed.
        ad = USE_PRE ? (A + D) : A;
        product = $signed(ad) * $signed(B);
    end

    initial preg = 48'd0;
    always @(posedge CLK) begin
        case (STATE)
            2'd0:    preg <= C;
            2'd1:    preg <= {{3{product[44]}}, product};
            default: preg <= preg + {{3{product[44]}}, product};
        endcase
    end
endmodule

module GEM_DSP48E2(
    output [47:0] P,
    input         CLK,
    input         USE_PRE,
    input  [26:0] A,
    input  [17:0] B,
    input  [47:0] C,
    input  [26:0] D,
    input  [1:0]  STATE
);
    DSP48E2 u_impl (
        .P(P), .CLK(CLK), .USE_PRE(USE_PRE),
        .A(A), .B(B), .C(C), .D(D), .STATE(STATE)
    );
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
    initial shift_reg = 32'd0;
    assign Q31 = shift_reg[31];
    assign Q = shift_reg[A];
    always @(posedge CLK) begin
        if (CE) shift_reg <= {shift_reg[30:0], D};
    end
endmodule
