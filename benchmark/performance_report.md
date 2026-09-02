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
| **PartitionTime_ms** | 191.45 | 41.19 | **4.65x** |
| **GPUSimTime_ms** | 13.785 | 42.672 | **0.32x** |
| **TotalWallTime_ms** | 2058.62 | 497.90 | **4.13x** |

## 2. Flow 1: GPU Micro-Kernel Speedup & Scaling Summary

| Macro Type | Batch Size ($N$) | Clock Cycles ($C$) | Baseline Latency (ms) | Macro Latency (ms) | Speedup Factor | Throughput (MEvals/s) |
|---|---|---|---|---|---|---|
| **CARRYCHAIN** | 1,000 | 1 | 0.135 | 0.040 | **3.38x** | 24.98 |
| **DSP48E2** | 1,000 | 1 | 0.076 | 0.038 | **2.00x** | 26.39 |
| **SRLC32E** | 1,000 | 1 | 0.108 | 0.069 | **1.57x** | 14.58 |
| **CARRYCHAIN** | 1,000 | 8 | 0.081 | 0.049 | **1.64x** | 162.87 |
| **DSP48E2** | 1,000 | 8 | 0.065 | 0.078 | **0.83x** | 102.80 |
| **SRLC32E** | 1,000 | 8 | 0.043 | 0.129 | **0.33x** | 62.00 |
| **CARRYCHAIN** | 1,000 | 64 | 0.189 | 0.055 | **3.43x** | 1,157.41 |
| **DSP48E2** | 1,000 | 64 | 0.116 | 0.082 | **1.41x** | 781.25 |
| **SRLC32E** | 1,000 | 64 | 0.132 | 0.059 | **2.22x** | 1,077.59 |
| **CARRYCHAIN** | 1,000 | 256 | 0.721 | 0.131 | **5.50x** | 1,953.13 |
| **DSP48E2** | 1,000 | 256 | 0.158 | 0.026 | **6.16x** | 10,000.00 |
| **SRLC32E** | 1,000 | 256 | 0.267 | 0.025 | **10.88x** | 10,416.67 |
| **CARRYCHAIN** | 10,000 | 1 | 0.066 | 0.074 | **0.90x** | 135.63 |
| **DSP48E2** | 10,000 | 1 | 0.168 | 0.083 | **2.03x** | 120.56 |
| **SRLC32E** | 10,000 | 1 | 0.051 | 0.032 | **1.62x** | 315.02 |
| **CARRYCHAIN** | 10,000 | 8 | 0.166 | 0.081 | **2.06x** | 988.92 |
| **DSP48E2** | 10,000 | 8 | 0.086 | 0.101 | **0.85x** | 790.14 |
| **SRLC32E** | 10,000 | 8 | 0.087 | 0.082 | **1.06x** | 976.56 |
| **CARRYCHAIN** | 10,000 | 64 | 0.357 | 0.059 | **6.02x** | 10,793.31 |
| **DSP48E2** | 10,000 | 64 | 0.121 | 0.080 | **1.52x** | 8,012.82 |
| **SRLC32E** | 10,000 | 64 | 0.255 | 0.023 | **11.33x** | 28,409.09 |
| **CARRYCHAIN** | 10,000 | 256 | 1.109 | 0.111 | **10.02x** | 23,114.71 |
| **DSP48E2** | 10,000 | 256 | 0.296 | 0.027 | **11.12x** | 96,153.85 |
| **SRLC32E** | 10,000 | 256 | 0.890 | 0.028 | **31.40x** | 90,293.45 |
| **CARRYCHAIN** | 100,000 | 1 | 0.237 | 0.073 | **3.26x** | 1,376.65 |
| **DSP48E2** | 100,000 | 1 | 0.134 | 0.031 | **4.36x** | 3,255.21 |
| **SRLC32E** | 100,000 | 1 | 0.097 | 0.024 | **4.11x** | 4,245.92 |
| **CARRYCHAIN** | 100,000 | 8 | 0.379 | 0.024 | **16.10x** | 33,967.39 |
| **DSP48E2** | 100,000 | 8 | 0.145 | 0.047 | **3.07x** | 16,983.70 |
| **SRLC32E** | 100,000 | 8 | 0.331 | 0.138 | **2.39x** | 5,787.04 |
| **CARRYCHAIN** | 100,000 | 64 | 2.493 | 0.107 | **23.37x** | 59,988.00 |
| **DSP48E2** | 100,000 | 64 | 0.605 | 0.037 | **16.41x** | 173,611.10 |
| **SRLC32E** | 100,000 | 64 | 2.466 | 0.111 | **22.30x** | 57,870.37 |
| **CARRYCHAIN** | 100,000 | 256 | 9.792 | 0.012 | **811.63x** | 2,122,015.97 |
| **DSP48E2** | 100,000 | 256 | 2.285 | 0.077 | **29.79x** | 333,750.51 |
| **SRLC32E** | 100,000 | 256 | 7.398 | 0.104 | **70.81x** | 245,022.97 |
| **CARRYCHAIN** | 1,000,000 | 1 | 0.453 | 0.342 | **1.33x** | 2,926.30 |
| **DSP48E2** | 1,000,000 | 1 | 0.304 | 0.306 | **0.99x** | 3,266.10 |
| **SRLC32E** | 1,000,000 | 1 | 0.577 | 0.061 | **9.43x** | 16,352.69 |
| **CARRYCHAIN** | 1,000,000 | 8 | 3.044 | 0.291 | **10.47x** | 27,508.80 |
| **DSP48E2** | 1,000,000 | 8 | 0.745 | 0.348 | **2.14x** | 22,988.51 |
| **SRLC32E** | 1,000,000 | 8 | 2.520 | 0.056 | **44.74x** | 142,045.45 |
| **CARRYCHAIN** | 1,000,000 | 64 | 23.729 | 0.295 | **80.51x** | 217,131.69 |
| **DSP48E2** | 1,000,000 | 64 | 5.528 | 0.378 | **14.64x** | 169,462.80 |
| **SRLC32E** | 1,000,000 | 64 | 17.518 | 0.150 | **116.48x** | 425,531.92 |
| **CARRYCHAIN** | 1,000,000 | 256 | 94.672 | 0.263 | **359.74x** | 972,762.62 |
| **DSP48E2** | 1,000,000 | 256 | 17.727 | 0.555 | **31.94x** | 461,307.83 |
| **SRLC32E** | 1,000,000 | 256 | 56.144 | 0.422 | **133.08x** | 606,796.13 |

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
