# Independent CARRY4 bank

`circuit.sv` contains 128 independent CARRY4 slices. There is no carry link
between slices, so all slices can be placed in the same macro dependency level.

This circuit measures the best case for filling macro warps. It is different
from the existing long carry-chain experiment, which measures dependency cost.
All O and CO bits are kept as outputs so synthesis cannot remove repeated
slices or cancel them in a reduction.
