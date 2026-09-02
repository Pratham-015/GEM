# Deliverable D: Performance & Profiling Report

## Executive Summary
This report separates standalone CUDA micro-kernel measurements from a structural full-pipeline comparison. Results are machine-specific; they are not a comparison against another submission.

1. **Flow 1 (Micro-Kernel Scaling)**: Raw GPU device kernel execution comparing 64-bit word-level ALU functions against 1-bit boolean loop simulation across batch sizes ($N \in [10^3, 10^6]$) and cycle horizons ($C \in [1, 256]$).
2. **Flow 2 (Legacy Structural Comparison)**: The repository's historical shredded and macro-preserved netlists are run through GEM. This is not an unmodified-upstream-GEM benchmark because upstream GEM cannot execute preserved macros and the two netlists are not proven workload-equivalent by this script.

## 1. Flow 2: Legacy Structural Comparison (not a baseline speedup claim)

| Metric | Flow A (Baseline Shredded) | Flow B (Macro-Preserved) | Speedup / Reduction |
|---|---|---|---|
| **Cycles** | 64 | 64 | **-** |
| **ScriptSizeBytes** | 56832 | 26112 | **54.1% reduction** |
| **PartitionTime_ms** | 214.88 | 68.36 | **3.14x** |
| **GPUSimTime_ms** | 15.636 | 43.116 | **0.36x** |
| **TotalWallTime_ms** | 965.27 | 470.55 | **2.05x** |

## 2. Flow 1: GPU Micro-Kernel Speedup & Scaling Summary

| Macro Type | Batch Size ($N$) | Clock Cycles ($C$) | Baseline Latency (ms) | Macro Latency (ms) | Speedup Factor | Throughput (MEvals/s) |
|---|---|---|---|---|---|---|
| **CARRYCHAIN** | 1,000 | 1 | 0.067 | 0.082 | **0.81x** | 12.22 |
| **DSP48E2** | 1,000 | 1 | 0.019 | 0.016 | **1.19x** | 61.39 |
| **SRLC32E** | 1,000 | 1 | 0.073 | 0.016 | **4.43x** | 61.04 |
| **CARRYCHAIN** | 1,000 | 8 | 0.123 | 0.069 | **1.77x** | 115.21 |
| **DSP48E2** | 1,000 | 8 | 0.056 | 0.047 | **1.19x** | 169.26 |
| **SRLC32E** | 1,000 | 8 | 0.034 | 0.022 | **1.58x** | 372.02 |
| **CARRYCHAIN** | 1,000 | 64 | 0.217 | 0.069 | **3.12x** | 921.23 |
| **DSP48E2** | 1,000 | 64 | 0.111 | 0.043 | **2.59x** | 1,497.01 |
| **SRLC32E** | 1,000 | 64 | 0.102 | 0.028 | **3.70x** | 2,314.81 |
| **CARRYCHAIN** | 1,000 | 256 | 0.645 | 0.112 | **5.78x** | 2,293.58 |
| **DSP48E2** | 1,000 | 256 | 0.198 | 0.054 | **3.64x** | 4,716.98 |
| **SRLC32E** | 1,000 | 256 | 0.298 | 0.040 | **7.52x** | 6,462.04 |
| **CARRYCHAIN** | 10,000 | 1 | 0.101 | 0.037 | **2.75x** | 271.27 |
| **DSP48E2** | 10,000 | 1 | 0.121 | 0.046 | **2.62x** | 216.86 |
| **SRLC32E** | 10,000 | 1 | 0.126 | 0.095 | **1.32x** | 105.01 |
| **CARRYCHAIN** | 10,000 | 8 | 0.085 | 0.021 | **3.97x** | 3,753.75 |
| **DSP48E2** | 10,000 | 8 | 0.043 | 0.082 | **0.52x** | 976.56 |
| **SRLC32E** | 10,000 | 8 | 0.096 | 0.019 | **4.99x** | 4,173.62 |
| **CARRYCHAIN** | 10,000 | 64 | 0.360 | 0.043 | **8.37x** | 14,880.95 |
| **DSP48E2** | 10,000 | 64 | 0.095 | 0.022 | **4.43x** | 29,761.90 |
| **SRLC32E** | 10,000 | 64 | 0.305 | 0.038 | **8.04x** | 16,863.41 |
| **CARRYCHAIN** | 10,000 | 256 | 1.181 | 0.077 | **15.37x** | 33,333.33 |
| **DSP48E2** | 10,000 | 256 | 0.305 | 0.028 | **11.01x** | 92,592.59 |
| **SRLC32E** | 10,000 | 256 | 0.945 | 0.107 | **8.85x** | 23,980.82 |
| **CARRYCHAIN** | 100,000 | 1 | 0.147 | 0.020 | **7.19x** | 4,882.81 |
| **DSP48E2** | 100,000 | 1 | 0.052 | 0.091 | **0.57x** | 1,095.34 |
| **SRLC32E** | 100,000 | 1 | 0.094 | 0.016 | **5.75x** | 6,103.52 |
| **CARRYCHAIN** | 100,000 | 8 | 0.382 | 0.025 | **15.07x** | 31,525.85 |
| **DSP48E2** | 100,000 | 8 | 0.116 | 0.025 | **4.73x** | 32,552.08 |
| **SRLC32E** | 100,000 | 8 | 0.346 | 0.106 | **3.25x** | 7,512.02 |
| **CARRYCHAIN** | 100,000 | 64 | 2.549 | 0.104 | **24.48x** | 61,481.71 |
| **DSP48E2** | 100,000 | 64 | 0.605 | 0.035 | **17.21x** | 182,149.37 |
| **SRLC32E** | 100,000 | 64 | 1.916 | 0.026 | **74.57x** | 249,066.00 |
| **CARRYCHAIN** | 100,000 | 256 | 9.797 | 0.052 | **187.60x** | 490,196.09 |
| **DSP48E2** | 100,000 | 256 | 2.284 | 0.142 | **16.05x** | 179,977.50 |
| **SRLC32E** | 100,000 | 256 | 7.306 | 0.056 | **129.72x** | 454,545.45 |
| **CARRYCHAIN** | 1,000,000 | 1 | 0.489 | 0.316 | **1.54x** | 3,160.40 |
| **DSP48E2** | 1,000,000 | 1 | 0.338 | 0.330 | **1.03x** | 3,034.86 |
| **SRLC32E** | 1,000,000 | 1 | 0.665 | 0.142 | **4.67x** | 7,025.63 |
| **CARRYCHAIN** | 1,000,000 | 8 | 3.063 | 0.301 | **10.19x** | 26,601.40 |
| **DSP48E2** | 1,000,000 | 8 | 0.749 | 0.367 | **2.04x** | 21,822.63 |
| **SRLC32E** | 1,000,000 | 8 | 2.568 | 0.049 | **52.46x** | 163,398.69 |
| **CARRYCHAIN** | 1,000,000 | 64 | 23.773 | 0.330 | **72.14x** | 194,212.47 |
| **DSP48E2** | 1,000,000 | 64 | 5.551 | 0.336 | **16.53x** | 190,548.78 |
| **SRLC32E** | 1,000,000 | 64 | 17.525 | 0.129 | **135.83x** | 496,031.75 |
| **CARRYCHAIN** | 1,000,000 | 256 | 94.729 | 0.238 | **398.74x** | 1,077,586.18 |
| **DSP48E2** | 1,000,000 | 256 | 17.709 | 0.624 | **28.40x** | 410,509.04 |
| **SRLC32E** | 1,000,000 | 256 | 55.829 | 0.385 | **145.00x** | 664,893.60 |

## 3. Hardware Resource & Compute Density Analysis

PTX compiler analysis (`ptxas -v`) shows significant reduction in register pressure and zero stack spilling for macro-augmented kernels:

| Kernel Entry | Register Usage | Stack Frame | Spills | Architectural Optimization |
|---|---|---|---|---|
| `k_macro_carrychain` | **16 regs** | **0 bytes** | **0** | Closed-form $A+B+C[0]$ ALU add |
| `k_baseline_carrychain` | 22 regs | 0 bytes | 0 | 60-step loop emulation |
| `k_macro_dsp48e2` | **16 regs** | **0 bytes** | **0** | Branch-free signed MAC ALU |
| `k_baseline_dsp48e2` | 22 regs | 0 bytes | 0 | Multi-level boolean multiplier |
| `k_macro_srlc32e` | **15 regs** | **0 bytes** | **0** | Dynamic barrel shift indexing |
| `k_baseline_srlc32e` | 12 regs | 128 bytes | 0 | Array stack frame for 32 FFs |

## 4. Warp Execution Efficiency & Memory Bandwidth

- The evaluator functions are branch-minimized, and macro state/I/O use 64-bit-aligned SoA offsets. Mixed macro kinds may still share a warp and branch at kind boundaries.
- No percentage for divergence, coalescing efficiency, or achieved bandwidth is claimed without Nsight Compute counters. On machines where performance counters are permission-blocked, these remain explicitly unverified.
