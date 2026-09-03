# DSP48E2 multiply bank

`circuit.sv` contains eight independent DSP48E2 blocks. Each block uses the
required register settings and performs a signed pre-add followed by a signed
multiplication. The final P output is clocked.

The circuit is wide enough to make DSP shredding visible while keeping the
benchmark build time reasonable on a college laptop.
