// tb_stimulus.v
// Generates the INPUT_VCD for `naive_sim NETLIST_VERILOG INPUT_VCD OUTPUT_VCD`.
//
// Runs the exact same stimulus sequence as tb_ram_sync.v, but against the
// ORIGINAL (pre-Yosys) RTL, and dumps the VCD scoped to the `top` instance
// only. Because this VCD is captured from the real (golden) RTL, it
// contains both:
//   - the input waveforms (clk, we, wbyte_en, waddr, wdata, re, raddr)
//     which naive_sim will replay against the mapped netlist, and
//   - the golden `rdata` waveform, which you diff naive_sim's OUTPUT_VCD
//     against afterward.
//
// IMPORTANT: the dumped scope is named `top` to match the top module name
// in memory_mapped_sync.v, so naive_sim can line up signal paths between
// the two files. If GEM's naive_sim expects a different scope/hierarchy
// convention (e.g. dumping at the testbench root instead of the DUT
// instance), adjust the $dumpvars scope accordingly -- check `naive_sim
// --help` or its source for the exact VCD hierarchy it expects.

`timescale 1ns/1ps

module tb_stimulus;

    reg         clk;
    reg         we;
    reg  [3:0]  wbyte_en;
    reg  [12:0] waddr;
    reg  [31:0] wdata;
    reg         re;
    reg  [12:0] raddr;
    wire [31:0] rdata;

    integer i;

    top dut (
        .clk      (clk),
        .we       (we),
        .wbyte_en (wbyte_en),
        .waddr    (waddr),
        .wdata    (wdata),
        .re       (re),
        .raddr    (raddr),
        .rdata    (rdata)
    );

    always #5 clk = ~clk;

    task do_write(input [12:0] a, input [31:0] d, input [3:0] be);
        begin
            @(negedge clk);
            we       = 1;
            wbyte_en = be;
            waddr    = a;
            wdata    = d;
            @(negedge clk);
            we       = 0;
        end
    endtask

    task do_read(input [12:0] a);
        begin
            @(negedge clk);
            re    = 1;
            raddr = a;
            @(negedge clk);
            re    = 0;
        end
    endtask

    initial begin
        clk      = 0;
        we       = 0;
        wbyte_en = 4'b0000;
        waddr    = 0;
        wdata    = 0;
        re       = 0;
        raddr    = 0;

        // identical sequence to tb_ram_sync.v, minus the self-check logic
        do_write(13'd10, 32'hDEADBEEF, 4'b1111);
        do_read(13'd10);

        do_write(13'd20, 32'h12345678, 4'b1111);
        do_read(13'd20);
        do_read(13'd10);

        do_write(13'd10, 32'h000000AA, 4'b0001);
        do_read(13'd10);

        do_write(13'd10, 32'hFF000000, 4'b1000);
        do_read(13'd10);

        for (i = 0; i < 8; i = i + 1)
            do_write(i, 32'hA000_0000 + i, 4'b1111);
        for (i = 0; i < 8; i = i + 1)
            do_read(i);

        do_write(13'd8191, 32'hCAFEF00D, 4'b1111);
        do_read(13'd8191);

        #20;
        $display("STIMULUS DONE");
        $finish;
    end

    initial begin
        $dumpfile("stim_and_golden.vcd");
        $dumpvars(0, dut);   // scope = `top` instance, matches mapped netlist's top module
    end

endmodule
