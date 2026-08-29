// test_ram_async.v
// Same RAM but with a COMBINATIONAL (asynchronous) read port.
// This should get mapped to $__RAMGEM_ASYNC_, the trap cell in memlib_yosys.txt,
// since GEM's simulator only supports synchronous reads.

module ram_async #(
    parameter ADDR_W = 13,
    parameter DATA_W = 32
)(
    input  wire                   clk,
    input  wire                   we,
    input  wire [3:0]             wbyte_en,
    input  wire [ADDR_W-1:0]      waddr,
    input  wire [DATA_W-1:0]      wdata,
    input  wire [ADDR_W-1:0]      raddr,
    output wire [DATA_W-1:0]      rdata
);

    reg [DATA_W-1:0] mem [0:(1<<ADDR_W)-1];

    always @(posedge clk) begin
        if (we) begin
            if (wbyte_en[0]) mem[waddr][7:0]   <= wdata[7:0];
            if (wbyte_en[1]) mem[waddr][15:8]  <= wdata[15:8];
            if (wbyte_en[2]) mem[waddr][23:16] <= wdata[23:16];
            if (wbyte_en[3]) mem[waddr][31:24] <= wdata[31:24];
        end
    end

    // combinational read -> asynchronous
    assign rdata = mem[raddr];

endmodule


module top (
    input  wire        clk,
    input  wire        we,
    input  wire [3:0]  wbyte_en,
    input  wire [12:0] waddr,
    input  wire [31:0] wdata,
    input  wire [12:0] raddr,
    output wire [31:0] rdata
);

    ram_async #(
        .ADDR_W(13),
        .DATA_W(32)
    ) u_ram (
        .clk      (clk),
        .we       (we),
        .wbyte_en (wbyte_en),
        .waddr    (waddr),
        .wdata    (wdata),
        .raddr    (raddr),
        .rdata    (rdata)
    );

endmodule
