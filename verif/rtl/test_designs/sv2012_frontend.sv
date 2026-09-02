package gem_frontend_pkg;
    parameter int WIDTH = 8;
    typedef logic [WIDTH-1:0] word_t;
endpackage

module sv2012_frontend #(
    parameter int N = 4
) (
    input  logic clk,
    input  gem_frontend_pkg::word_t a,
    input  gem_frontend_pkg::word_t b,
    output logic [N-1:0] q
);
    for (genvar i = 0; i < N; ++i) begin : generated
        always_ff @(posedge clk)
            q[i] <= a[i] ^ b[i];
    end
endmodule
