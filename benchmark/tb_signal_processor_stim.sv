`timescale 1ns/1ps

module tb_signal_processor_stim;
    reg clk;
    reg [7:0] in_a;
    reg [7:0] in_b;
    reg [17:0] coeff;
    reg [4:0] tap_sel;
    wire [47:0] out_p;
    wire out_parity;

    signal_processor dut (
        .clk(clk),
        .in_a(in_a),
        .in_b(in_b),
        .coeff(coeff),
        .tap_sel(tap_sel),
        .out_p(out_p),
        .out_parity(out_parity)
    );

    always #5 clk = ~clk;

    integer cycle;
    initial begin
        $dumpfile("verif/sim_out/signal_processor_stim.vcd");
        $dumpvars(0, dut);

        clk = 0;
        in_a = 0;
        in_b = 0;
        coeff = 0;
        tap_sel = 0;

        for (cycle = 0; cycle < 64; cycle = cycle + 1) begin
            @(negedge clk);
            in_a = $random;
            in_b = $random;
            coeff = $random;
            tap_sel = cycle % 32;
        end

        @(posedge clk);
        $finish;
    end
endmodule

