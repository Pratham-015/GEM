// ramgem_sync_stub.v
// Behavioral Icarus-Verilog-simulatable model of the $__RAMGEM_SYNC_ memory
// primitive declared in synth/memlib_yosys.txt, used only to verify
// correctness of Yosys's memory_libmap output (verif/rtl/memory_mapped_sync.v)
// with a conventional simulator. Not part of the GEM toolchain itself.
//
// Port contract (from synth/memlib_yosys.txt):
//   abits 13, width 32, byte 1 (byte-level write granularity)
//   port sw "W" { clock posedge; }   -- synchronous write
//   port sr "R" { clock posedge; }   -- synchronous (registered) read
//
// Yosys expanded byte enables to full per-bit write-enable width (32 bits)
// in the mapped netlist, so this model treats PORT_W_WR_EN as a per-bit mask.

module \$__RAMGEM_SYNC_  (
    PORT_R_CLK, PORT_R_ADDR, PORT_R_RD_DATA,
    PORT_W_CLK, PORT_W_ADDR, PORT_W_WR_DATA, PORT_W_WR_EN
);
    input  wire         PORT_R_CLK;
    input  wire [12:0]  PORT_R_ADDR;
    output reg  [31:0]  PORT_R_RD_DATA;

    input  wire         PORT_W_CLK;
    input  wire [12:0]  PORT_W_ADDR;
    input  wire [31:0]  PORT_W_WR_DATA;
    input  wire [31:0]  PORT_W_WR_EN;

    reg [31:0] mem [0:8191];
    integer i;

    always @(posedge PORT_R_CLK)
        PORT_R_RD_DATA <= mem[PORT_R_ADDR];

    always @(posedge PORT_W_CLK)
        for (i = 0; i < 32; i = i + 1)
            if (PORT_W_WR_EN[i])
                mem[PORT_W_ADDR][i] <= PORT_W_WR_DATA[i];

endmodule
