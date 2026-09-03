# CARRY4 Optimization Result

The focused, correctness-gated experiment improved the macro-preserved CARRY4
ratio from **0.117x** to **0.221x**. This is a **1.89x improvement in the
ratio**, while still remaining slower than the upstream shredded representation.

| Representation | Median cycles/s |
|---|---:|
| Shredded, official upstream | 78,227 |
| Macro-preserved, optimized | 17,317 |

The optimized kernel avoids an empty DSP publication barrier and runs only one
settle phase for combinational carry-only workloads. Sequential DSP/SRL graphs
retain the original two-phase behavior.

All four differential comparisons passed: 64 randomized vectors for the
shredded and preserved forms, plus the exact constant-zero input timed by both
binaries. Full commands, seven timing samples per implementation, commits, and
netlist statistics are in `carry4_optimization.json`.

This remains a representation-plus-implementation comparison, not an
implementation-only speedup.
