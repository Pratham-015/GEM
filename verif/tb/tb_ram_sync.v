// tb_ram_sync.v
// Self-checking testbench for test_ram_sync.v (module `top` wrapping ram_sync)
// Exercises: basic write+read, byte-enable partial writes, and read-during-different-address writes.

`timescale 1ns/1ps

module tb_ram_sync;

    reg         clk;
    reg         we;
    reg  [3:0]  wbyte_en;
    reg  [12:0] waddr;
    reg  [31:0] wdata;
    reg         re;
    reg  [12:0] raddr;
    wire [31:0] rdata;

    integer errors = 0;
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

    // 100MHz clock
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

    task do_read_check(input [12:0] a, input [31:0] expected);
        begin
            @(negedge clk);
            re    = 1;
            raddr = a;
            @(negedge clk);   // rdata is registered, valid one cycle after re+raddr
            re    = 0;
            if (rdata !== expected) begin
                $display("FAIL: addr=%0d expected=%h got=%h", a, expected, rdata);
                errors = errors + 1;
            end else begin
                $display("PASS: addr=%0d data=%h", a, rdata);
            end
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

        // Test 1: basic full-word write then read
        do_write(13'd10, 32'hDEADBEEF, 4'b1111);
        do_read_check(13'd10, 32'hDEADBEEF);

        // Test 2: write a different address, confirm no aliasing
        do_write(13'd20, 32'h12345678, 4'b1111);
        do_read_check(13'd20, 32'h12345678);
        do_read_check(13'd10, 32'hDEADBEEF);  // addr 10 should be unaffected

        // Test 3: byte-enable partial write (only low byte)
        do_write(13'd10, 32'h000000AA, 4'b0001);
        do_read_check(13'd10, 32'hDEADBEAA);  // only [7:0] changed

        // Test 4: byte-enable partial write (only top byte)
        do_write(13'd10, 32'hFF000000, 4'b1000);
        do_read_check(13'd10, 32'hFFADBEAA);  // only [31:24] changed

        // Test 5: sweep several addresses
        for (i = 0; i < 8; i = i + 1) begin
            do_write(i, 32'hA000_0000 + i, 4'b1111);
        end
        for (i = 0; i < 8; i = i + 1) begin
            do_read_check(i, 32'hA000_0000 + i);
        end

        // Test 6: max address (2^13 - 1 = 8191)
        do_write(13'd8191, 32'hCAFEF00D, 4'b1111);
        do_read_check(13'd8191, 32'hCAFEF00D);

        if (errors == 0)
            $display("ALL TESTS PASSED");
        else
            $display("%0d TEST(S) FAILED", errors);

        $finish;
    end

    // safety timeout
    initial begin
        #10000;
        $display("TIMEOUT");
        $finish;
    end

    // optional waveform dump
    // initial begin
    //     $dumpfile("tb_ram_sync.vcd");
    //     $dumpvars(0, tb_ram_sync);
    // end

endmodule
