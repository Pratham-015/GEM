`timescale 1ns/1ps

module tb_integrated_macro_top;
    reg clk = 0;
    reg [63:0] x = 0, y = 0;
    reg cin = 0;
    reg [26:0] dsp_a = 0, dsp_d = 0;
    reg [17:0] dsp_b = 0;
    reg [47:0] dsp_c = 0;
    reg [1:0] dsp_state = 0;
    reg dsp_use_pre = 0;
    reg srl_ce = 0;
    reg [4:0] srl_addr = 0;
    wire [63:0] sum, carry;
    wire [47:0] p;
    wire q, q31, glue, neg_probe;

    integrated_macro_top dut (.*);
    always #5 clk = ~clk;

    integer cycle;
    initial begin
        $dumpfile("/tmp/gem_integrated_golden.vcd");
        $dumpvars(0, dut);
        for (cycle = 0; cycle < 96; cycle = cycle + 1) begin
            @(negedge clk);
            // Keep stimulus changes away from the active clock edge. GEM's
            // VCD frontend is edge-sampled and intentionally has no delta
            // cycle event queue.
            #2;
            x = (64'h9e3779b97f4a7c15 * cycle) ^ (cycle >> 1);
            y = (64'hd1b54a32d192ed03 * cycle) ^ (cycle << 17);
            cin = cycle[0];
            srl_ce = (cycle % 3) != 0;
            srl_addr = (cycle * 7) & 31;
            dsp_state = cycle % 3;
            dsp_use_pre = cycle[1];
            case (cycle % 8)
                0: begin dsp_a = 27'h0;       dsp_d = 27'h0;       dsp_b = 18'h0;     dsp_c = 48'h0; end
                1: begin dsp_a = 27'h3ffffff; dsp_d = 27'h0;       dsp_b = 18'h1ffff; dsp_c = 48'h7fffffffffff; end
                2: begin dsp_a = 27'h4000000; dsp_d = 27'h0;       dsp_b = 18'h20000; dsp_c = 48'h800000000000; end
                3: begin dsp_a = 27'h3ffffff; dsp_d = 27'h4000000; dsp_b = 18'h20001; dsp_c = 48'hffffffffffff; end
                4: begin dsp_a = 27'h4000000; dsp_d = 27'h3ffffff; dsp_b = 18'h1ffff; dsp_c = 48'h000000000001; end
                5: begin dsp_a = 27'h7ffffff; dsp_d = 27'h7ffffff; dsp_b = 18'h3ffff; dsp_c = 48'h555555555555; end
                6: begin dsp_a = cycle * 12345; dsp_d = ~(cycle * 333); dsp_b = cycle * 71; dsp_c = cycle * 48'h100000001b3; end
                default: begin dsp_a = ~(cycle * 991); dsp_d = cycle * 17; dsp_b = ~(cycle * 13); dsp_c = ~cycle; end
            endcase
        end
        @(posedge clk);
        #1 $finish;
    end
endmodule
