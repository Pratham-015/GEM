// test_ram_sync_fixed.v
// Same as test_ram_sync.v but with hardcoded widths (no module parameters),
// so Yosys does not mangle the module into a \$paramod$<hash>\ram_sync name.
// This keeps the mapped netlist's identifiers plain and parser-friendly.

module ram_sync (
    input  wire         clk,
    input  wire         we,
    input  wire [3:0]   wbyte_en,
    input  wire [12:0]  waddr,
    input  wire [31:0]  wdata,
    input  wire         re,
    input  wire [12:0]  raddr,
    output reg  [31:0]  rdata
);

    reg [31:0] mem [0:8191];

    always @(posedge clk) begin
        if (we) begin
            if (wbyte_en[0]) mem[waddr][7:0]   <= wdata[7:0];
            if (wbyte_en[1]) mem[waddr][15:8]  <= wdata[15:8];
            if (wbyte_en[2]) mem[waddr][23:16] <= wdata[23:16];
            if (wbyte_en[3]) mem[waddr][31:24] <= wdata[31:24];
        end
    end

    always @(posedge clk) begin
        if (re)
            rdata <= mem[raddr];
    end

endmodule


module top (
    input  wire        clk,
    input  wire        we,
    input  wire [3:0]  wbyte_en,
    input  wire [12:0] waddr,
    input  wire [31:0] wdata,
    input  wire        re,
    input  wire [12:0] raddr,
    output wire [31:0] rdata
);

    ram_sync u_ram (
        .clk      (clk),
        .we       (we),
        .wbyte_en (wbyte_en),
        .waddr    (waddr),
        .wdata    (wdata),
        .re       (re),
        .raddr    (raddr),
        .rdata    (rdata)
    );

endmodule