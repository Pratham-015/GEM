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
| **PartitionTime_ms** | 185.19 | 36.97 | **5.01x** |
| **GPUSimTime_ms** | 10.945 | 12.407 | **0.88x** |
| **TotalWallTime_ms** | 886.52 | 480.91 | **1.84x** |

## 2. Flow 1: GPU Micro-Kernel Speedup & Scaling Summary

| Macro Type | Batch Size ($N$) | Clock Cycles ($C$) | Baseline Latency (ms) | Macro Latency (ms) | Speedup Factor | Throughput (MEvals/s) |
|---|---|---|---|---|---|---|
| **CARRYCHAIN** | 1,000 | 1 | 0.055 | 0.114 | **0.49x** | 8.80 |
| **DSP48E2** | 1,000 | 1 | 0.057 | 0.077 | **0.74x** | 12.98 |
| **SRLC32E** | 1,000 | 1 | 0.059 | 0.060 | **0.98x** | 16.55 |
| **CARRYCHAIN** | 1,000 | 8 | 0.069 | 0.085 | **0.81x** | 94.06 |
| **DSP48E2** | 1,000 | 8 | 0.094 | 0.019 | **4.87x** | 413.22 |
| **SRLC32E** | 1,000 | 8 | 0.135 | 0.019 | **6.94x** | 411.18 |
| **CARRYCHAIN** | 1,000 | 64 | 0.276 | 0.020 | **13.51x** | 3,129.89 |
| **DSP48E2** | 1,000 | 64 | 0.049 | 0.022 | **2.22x** | 2,886.00 |
| **SRLC32E** | 1,000 | 64 | 0.092 | 0.020 | **4.51x** | 3,129.89 |
| **CARRYCHAIN** | 1,000 | 256 | 0.762 | 0.078 | **9.76x** | 3,278.69 |
| **DSP48E2** | 1,000 | 256 | 0.204 | 0.023 | **9.04x** | 11,363.64 |
| **SRLC32E** | 1,000 | 256 | 0.296 | 0.022 | **13.76x** | 11,904.76 |
| **CARRYCHAIN** | 10,000 | 1 | 0.139 | 0.060 | **2.29x** | 165.43 |
| **DSP48E2** | 10,000 | 1 | 0.059 | 0.047 | **1.25x** | 212.30 |
| **SRLC32E** | 10,000 | 1 | 0.096 | 0.093 | **1.04x** | 107.43 |
| **CARRYCHAIN** | 10,000 | 8 | 0.082 | 0.112 | **0.73x** | 716.74 |
| **DSP48E2** | 10,000 | 8 | 0.094 | 0.024 | **3.96x** | 3,382.95 |
| **SRLC32E** | 10,000 | 8 | 0.073 | 0.019 | **3.74x** | 4,111.84 |
| **CARRYCHAIN** | 10,000 | 64 | 0.331 | 0.018 | **17.95x** | 34,722.22 |
| **DSP48E2** | 10,000 | 64 | 0.109 | 0.120 | **0.91x** | 5,341.88 |
| **SRLC32E** | 10,000 | 64 | 0.252 | 0.022 | **11.74x** | 29,761.90 |
| **CARRYCHAIN** | 10,000 | 256 | 1.168 | 0.023 | **51.86x** | 113,636.36 |
| **DSP48E2** | 10,000 | 256 | 0.276 | 0.028 | **9.98x** | 92,592.59 |
| **SRLC32E** | 10,000 | 256 | 0.918 | 0.020 | **44.83x** | 125,000.00 |
| **CARRYCHAIN** | 100,000 | 1 | 0.092 | 0.060 | **1.53x** | 1,655.19 |
| **DSP48E2** | 100,000 | 1 | 0.054 | 0.049 | **1.10x** | 2,034.51 |
| **SRLC32E** | 100,000 | 1 | 0.089 | 0.022 | **4.15x** | 4,650.30 |
| **CARRYCHAIN** | 100,000 | 8 | 0.411 | 0.057 | **7.16x** | 13,950.89 |
| **DSP48E2** | 100,000 | 8 | 0.214 | 0.117 | **1.83x** | 6,853.07 |
| **SRLC32E** | 100,000 | 8 | 0.309 | 0.050 | **6.15x** | 15,943.88 |
| **CARRYCHAIN** | 100,000 | 64 | 2.627 | 0.059 | **44.23x** | 107,758.62 |
| **DSP48E2** | 100,000 | 64 | 0.683 | 0.067 | **10.27x** | 96,153.85 |
| **SRLC32E** | 100,000 | 64 | 1.896 | 0.062 | **30.36x** | 102,459.02 |
| **CARRYCHAIN** | 100,000 | 256 | 9.995 | 0.062 | **160.02x** | 409,836.07 |
| **DSP48E2** | 100,000 | 256 | 2.296 | 0.132 | **17.42x** | 194,221.90 |
| **SRLC32E** | 100,000 | 256 | 7.406 | 0.062 | **118.56x** | 409,836.07 |
| **CARRYCHAIN** | 1,000,000 | 1 | 0.473 | 0.344 | **1.37x** | 2,906.44 |
| **DSP48E2** | 1,000,000 | 1 | 0.838 | 0.285 | **2.95x** | 3,512.81 |
| **SRLC32E** | 1,000,000 | 1 | 0.588 | 0.160 | **3.69x** | 6,268.81 |
| **CARRYCHAIN** | 1,000,000 | 8 | 3.018 | 0.276 | **10.92x** | 28,935.19 |
| **DSP48E2** | 1,000,000 | 8 | 0.741 | 0.498 | **1.49x** | 16,075.10 |
| **SRLC32E** | 1,000,000 | 8 | 2.542 | 0.101 | **25.08x** | 78,914.14 |
| **CARRYCHAIN** | 1,000,000 | 64 | 23.837 | 0.305 | **78.14x** | 209,797.54 |
| **DSP48E2** | 1,000,000 | 64 | 5.620 | 0.333 | **16.89x** | 192,307.69 |
| **SRLC32E** | 1,000,000 | 64 | 17.484 | 0.159 | **110.16x** | 403,225.80 |
| **CARRYCHAIN** | 1,000,000 | 256 | 94.606 | 0.297 | **318.58x** | 862,068.98 |
| **DSP48E2** | 1,000,000 | 256 | 17.893 | 0.603 | **29.67x** | 424,448.22 |
| **SRLC32E** | 1,000,000 | 256 | 56.332 | 0.332 | **169.79x** | 771,604.95 |

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
