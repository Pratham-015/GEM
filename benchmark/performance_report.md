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
| **PartitionTime_ms** | 207.91 | 49.68 | **4.18x** |
| **GPUSimTime_ms** | 11.631 | 22.970 | **0.51x** |
| **TotalWallTime_ms** | 885.02 | 412.85 | **2.14x** |

## 2. Flow 1: GPU Micro-Kernel Speedup & Scaling Summary

| Macro Type | Batch Size ($N$) | Clock Cycles ($C$) | Baseline Latency (ms) | Macro Latency (ms) | Speedup Factor | Throughput (MEvals/s) |
|---|---|---|---|---|---|---|
| **CARRYCHAIN** | 1,000 | 1 | 0.091 | 0.040 | **2.28x** | 25.04 |
| **DSP48E2** | 1,000 | 1 | 0.075 | 0.051 | **1.46x** | 19.53 |
| **SRLC32E** | 1,000 | 1 | 0.025 | 0.015 | **1.60x** | 65.10 |
| **CARRYCHAIN** | 1,000 | 8 | 0.060 | 0.035 | **1.74x** | 229.78 |
| **DSP48E2** | 1,000 | 8 | 0.022 | 0.019 | **1.16x** | 431.78 |
| **SRLC32E** | 1,000 | 8 | 0.058 | 0.050 | **1.16x** | 159.44 |
| **CARRYCHAIN** | 1,000 | 64 | 0.196 | 0.025 | **7.94x** | 2,597.40 |
| **DSP48E2** | 1,000 | 64 | 0.098 | 0.066 | **1.48x** | 962.46 |
| **SRLC32E** | 1,000 | 64 | 0.080 | 0.018 | **4.37x** | 3,502.63 |
| **CARRYCHAIN** | 1,000 | 256 | 0.639 | 0.039 | **16.42x** | 6,578.95 |
| **DSP48E2** | 1,000 | 256 | 0.202 | 0.060 | **3.34x** | 4,237.29 |
| **SRLC32E** | 1,000 | 256 | 0.279 | 0.020 | **13.75x** | 12,638.23 |
| **CARRYCHAIN** | 10,000 | 1 | 0.046 | 0.053 | **0.87x** | 188.03 |
| **DSP48E2** | 10,000 | 1 | 0.047 | 0.096 | **0.49x** | 104.03 |
| **SRLC32E** | 10,000 | 1 | 0.123 | 0.069 | **1.79x** | 145.76 |
| **CARRYCHAIN** | 10,000 | 8 | 0.087 | 0.031 | **2.83x** | 2,604.17 |
| **DSP48E2** | 10,000 | 8 | 0.117 | 0.066 | **1.79x** | 1,220.70 |
| **SRLC32E** | 10,000 | 8 | 0.063 | 0.056 | **1.12x** | 1,420.45 |
| **CARRYCHAIN** | 10,000 | 64 | 0.317 | 0.032 | **9.91x** | 20,020.02 |
| **DSP48E2** | 10,000 | 64 | 0.131 | 0.038 | **3.46x** | 16,891.89 |
| **SRLC32E** | 10,000 | 64 | 0.260 | 0.022 | **11.69x** | 28,776.98 |
| **CARRYCHAIN** | 10,000 | 256 | 1.080 | 0.024 | **45.87x** | 108,695.65 |
| **DSP48E2** | 10,000 | 256 | 0.280 | 0.029 | **9.76x** | 89,285.71 |
| **SRLC32E** | 10,000 | 256 | 0.876 | 0.022 | **40.74x** | 119,047.62 |
| **CARRYCHAIN** | 100,000 | 1 | 0.102 | 0.069 | **1.49x** | 1,457.56 |
| **DSP48E2** | 100,000 | 1 | 0.118 | 0.063 | **1.86x** | 1,575.10 |
| **SRLC32E** | 100,000 | 1 | 0.184 | 0.194 | **0.95x** | 514.91 |
| **CARRYCHAIN** | 100,000 | 8 | 0.373 | 0.059 | **6.29x** | 13,469.83 |
| **DSP48E2** | 100,000 | 8 | 0.176 | 0.083 | **2.12x** | 9,667.44 |
| **SRLC32E** | 100,000 | 8 | 0.316 | 0.017 | **18.17x** | 45,955.88 |
| **CARRYCHAIN** | 100,000 | 64 | 2.519 | 0.041 | **61.50x** | 156,250.00 |
| **DSP48E2** | 100,000 | 64 | 0.604 | 0.081 | **7.47x** | 79,113.93 |
| **SRLC32E** | 100,000 | 64 | 1.923 | 0.030 | **64.76x** | 215,517.24 |
| **CARRYCHAIN** | 100,000 | 256 | 9.861 | 0.057 | **171.96x** | 446,428.57 |
| **DSP48E2** | 100,000 | 256 | 2.302 | 0.074 | **31.22x** | 347,222.21 |
| **SRLC32E** | 100,000 | 256 | 7.470 | 0.118 | **63.43x** | 217,391.30 |
| **CARRYCHAIN** | 1,000,000 | 1 | 0.469 | 0.309 | **1.52x** | 3,233.65 |
| **DSP48E2** | 1,000,000 | 1 | 0.322 | 0.285 | **1.13x** | 3,512.81 |
| **SRLC32E** | 1,000,000 | 1 | 0.589 | 0.044 | **13.41x** | 22,776.97 |
| **CARRYCHAIN** | 1,000,000 | 8 | 3.094 | 0.269 | **11.49x** | 29,705.32 |
| **DSP48E2** | 1,000,000 | 8 | 0.751 | 0.322 | **2.34x** | 24,880.57 |
| **SRLC32E** | 1,000,000 | 8 | 2.493 | 0.053 | **46.82x** | 150,240.39 |
| **CARRYCHAIN** | 1,000,000 | 64 | 23.734 | 0.238 | **99.91x** | 269,396.55 |
| **DSP48E2** | 1,000,000 | 64 | 5.574 | 0.335 | **16.65x** | 191,131.51 |
| **SRLC32E** | 1,000,000 | 64 | 17.471 | 0.120 | **146.13x** | 535,331.90 |
| **CARRYCHAIN** | 1,000,000 | 256 | 94.628 | 0.234 | **403.54x** | 1,091,703.07 |
| **DSP48E2** | 1,000,000 | 256 | 21.855 | 0.572 | **38.18x** | 447,227.19 |
| **SRLC32E** | 1,000,000 | 256 | 68.989 | 0.400 | **172.31x** | 639,386.18 |

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
