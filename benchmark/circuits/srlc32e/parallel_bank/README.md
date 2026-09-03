# SRLC32E parallel bank

`circuit.sv` contains 128 independent SRLC32E blocks. The blocks share a clock
but use different data, enable, and address bits.

The shredded form uses 4,096 flip-flop state bits and dynamic read logic. The
preserved form keeps 128 word-level SRLC32E macros.
