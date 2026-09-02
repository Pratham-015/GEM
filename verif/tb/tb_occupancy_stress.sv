`timescale 1ns/1ps
module tb_occupancy_stress;
  reg clk = 0;
  reg [63:0] data = 64'h0123_4567_89ab_cdef;
  wire [8191:0] result;

  occupancy_stress dut(.clk(clk), .data(data), .result(result));

  initial begin
    $dumpfile("/tmp/gem_occupancy_stress_golden.vcd");
    $dumpvars(0, dut);
    repeat (8) begin
      #5 clk = 1;
      #5 clk = 0;
      data = {data[62:0], data[63] ^ data[62] ^ data[60] ^ data[59]};
    end
    #1 $finish;
  end
endmodule
