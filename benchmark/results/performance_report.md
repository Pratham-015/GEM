# Deliverable D: Reproducible Production Performance Report

## Methodology

Primary metric: `simulated cycles / synchronized production-kernel elapsed seconds`.

Timing scope: one cooperative production simulation launch; excludes parsing, allocation, H2D/D2H, synthesis, partitioning, and output.

Every production row uses 12 untimed warm-up launches followed by 7 measured launches in one initialized process; mutable SRAM, DSP, SRL, and input state is reset outside each timed interval.

Timing uses a host monotonic clock around the production launch and a mandatory post-launch device synchronization. It therefore includes kernel-launch latency but excludes setup and transfers. CUDA-event timing is not implemented.

## Environment

- Commit: `619f7d4aed0d23ae969ea81d6818c5f2a3c69f23`
- Dirty during run: `True`
- GPU: `NVIDIA GeForce RTX 4050 Laptop GPU, 8.9, 596.49, 6141 MiB`
- CUDA/NVCC: `Build cuda_12.9.r12.9/compiler.36037853_0`
- Nsight Compute: `Version 2025.2.1.0 (build 35987062) (public-release)`
- Yosys: `Yosys 0.68 (git sha1 38e001a6f, Release, GNU /usr/bin/c++ 13.3.0)`
- Rust: `rustc 1.98.0 (88d9e12ae 2026-08-18)`
- Build: `cargo build --release --features cuda`
- CUDA blocks: `4`

- Production CUDA compile command: `LC_ALL="C" "nvcc" "-Xcompiler" "-O3" "-Xcompiler" "-ffunction-sections" "-Xcompiler" "-fdata-sections" "-Xcompiler" "-fPIC" "-m64" "-I" "/home/pratham_sharma/gem/target/debug/build/gem-8c79d60a263ba35d/out/ucc_csrc_includes" "-Xcompiler" "-Wall" "-Xcompiler" "-Wextra" "-Xcompiler" "-Wall" "-std=c++14" "-gencode" "arch=compute_80,code=sm_80" "-gencode" "arch=compute_70,code=sm_70" "-arch=compute_50" "-code=sm_50,compute_50" "-lineinfo" "-maxrregcount=128" "-DCARGO_PKG_NAME=gem" "-DCARGO_PKG_VERSION=0.1.0" "-DCARGO_PKG_VERSION_MAJOR=0" "-DCARGO_PKG_VERSION_MINOR=1" "-DCARGO_PKG_VERSION_PATCH=0" "-DUCC_VERSION=0.2.6" "csrc/kernel_v1.cu"`

## Correctness gate

**PASS** — `/usr/bin/python3 verif/full_integration_test.py`

production RTL-to-Yosys-to-partitioner-to-CUDA differential regression; this gates benchmark publication but is not a per-generated-workload oracle.

## Per-workload differential gates

Every timed workload is separately checked against the independent Python event model in `benchmark/generated_workload_reference.py`. The model uses the literal golden primitive models, not CUDA implementation code.

| Workload | Status | Random cycles | Result bits | Checked event values | Mismatches |
|---|---|---:|---:|---:|---:|
| boolean_heavy | PASS | 48 | 64 | 146 | 0 |
| dsp_heavy | PASS | 48 | 64 | 146 | 0 |
| carry_heavy | PASS | 48 | 64 | 146 | 0 |
| srl_heavy | PASS | 48 | 64 | 146 | 0 |
| scaling_small | PASS | 48 | 64 | 146 | 0 |
| mixed_heterogeneous | PASS | 48 | 64 | 146 | 0 |
| deep_dependency | PASS | 48 | 64 | 146 | 0 |
| large_scale | PASS | 48 | 64 | 146 | 0 |
| occupancy_stress | PASS | 48 | 8192 | 146 | 0 |
## Production throughput

| Workload | Blocks | Cycles | AIG gates | DSP | CARRY4 | SRLC32E | Median cycles/s | Mean | Min | Max | Stddev |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| boolean_heavy | 4 | 2000 | 507 | 0 | 0 | 0 | 82,113 | 81,227 | 78,877 | 82,217 | 1,529 |
| dsp_heavy | 4 | 2000 | 4464 | 32 | 0 | 0 | 21,933 | 21,933 | 21,919 | 21,951 | 11 |
| carry_heavy | 4 | 1000 | 2880 | 0 | 128 | 0 | 1,583 | 1,583 | 1,582 | 1,585 | 1 |
| srl_heavy | 4 | 2000 | 576 | 0 | 0 | 128 | 43,057 | 43,097 | 42,936 | 43,306 | 160 |
| scaling_small | 4 | 1000 | 1120 | 4 | 8 | 8 | 7,748 | 7,749 | 7,746 | 7,754 | 3 |
| mixed_heterogeneous | 4 | 1000 | 3520 | 16 | 32 | 32 | 3,689 | 3,683 | 3,647 | 3,690 | 16 |
| deep_dependency | 4 | 200 | 1981 | 0 | 64 | 0 | 472 | 472 | 472 | 472 | 0 |
| large_scale | 4 | 200 | 8704 | 32 | 128 | 128 | 1,064 | 1,064 | 1,064 | 1,065 | 0 |
| occupancy_stress | 16 | 1000 | 82385 | 1 | 1 | 1 | 16,725 | 16,717 | 16,669 | 16,739 | 23 |

These are production GEM measurements, not isolated macro microkernels.

## Preprocessing cost

| Workload | Synthesis (s) | Partition (s) |
|---|---:|---:|
| boolean_heavy | 2.615 | 0.078 |
| dsp_heavy | 4.650 | 0.636 |
| carry_heavy | 2.284 | 0.247 |
| srl_heavy | 0.202 | 0.066 |
| scaling_small | 0.542 | 0.079 |
| mixed_heterogeneous | 3.150 | 0.431 |
| deep_dependency | 0.625 | 0.177 |
| large_scale | 12.408 | 2.531 |
| occupancy_stress | 35.890 | 3.994 |

## Heterogeneous scaling

| Scale | Actual cells | AIG gates | Macros | Median cycles/s | Mean elapsed/cycle (us) |
|---|---:|---:|---:|---:|---:|
| small | 1219 | 1120 | 20 | 7,748 | 129.06 |
| medium | 3770 | 3520 | 80 | 3,689 | 271.10 |
| large | 9340 | 8704 | 288 | 1,064 | 939.42 |

Cycles/second falls as heterogeneous graph work per simulated cycle grows; these points test scaling, not a same-workload implementation speedup.

## Multi-partition occupancy scaling

| Blocks | Median cycles/s |
|---:|---:|
| 1 | 5,284 |
| 4 | 10,867 |
| 8 | 13,175 |
| 9 | 18,123 |
| 12 | 16,805 |
| 16 | 16,641 |
| 20 | 16,645 |
| 28 | 11,529 |
| 40 | 11,541 |

The 9-partition heterogeneous stress graph scales from 5,284 cycles/s at one block to 18,123 cycles/s at 9 blocks (**3.43x**). This measures useful multi-partition execution; larger grids with idle blocks are not counted as an occupancy improvement.

## Unmodified upstream comparison

Both binaries execute the same macro-free gate-level netlist, zero input frames, cycle count, CUDA block count, one internal warm-up, GPU, and synchronized launch timing boundary. Three alternating pairs are discarded to precondition GPU clocks; the seven retained pairs alternate execution order.

| Implementation | Commit | Median cycles/s | Mean | Stddev |
|---|---|---:|---:|---:|
| Official upstream GEM | `9e913f9b5efc8b12027bfb374be8b1a0028df00a` | 57,973 | 58,807 | 1,089 |
| Modified GEM | `619f7d4aed0d23ae969ea81d6818c5f2a3c69f23` | 57,956 | 58,845 | 1,181 |

Modified/upstream median ratio: **1.000x** (-0.0%).

## Macro-preserved versus shredded experiment

This experiment uses one combinational 15-CARRY4 chain. Both netlists are regenerated from the same RTL; the upstream form contains no macros and the modified form preserves all 15 CARRY4 instances.

Random changing-vector semantics are checked as RTL versus Icarus-simulated shredded gates and RTL versus production-CUDA preserved macros. The old upstream VCD adapter is not used for changing vectors because it does not preserve vector-event timing reliably. The timed comparison uses constant-zero input in both binaries, and that exact input is separately checked in both simulators.

- Random RTL vs shredded Icarus: `checked=195 mismatches=0`
- Random RTL vs preserved CUDA: `checked=195 mismatches=0`
- Timed zero input vs upstream: `checked=17 mismatches=0`
- Timed zero input vs modified: `checked=17 mismatches=0`

| Representation | Median cycles/s | Mean | Stddev |
|---|---:|---:|---:|
| Shredded, official upstream | 77,365 | 77,731 | 907 |
| Macro-preserved, modified | 8,949 | 8,917 | 154 |

Representation-plus-implementation ratio: **0.116x** (-88.4%). This is not an implementation-only speedup.

The result is a measured regression, not a claimed gain: macro dispatch and cooperative barriers cost more than the removed AIG work for this graph.

## Nsight Compute

| Workload | Occupancy | Theoretical | Divergent targets | Uniform targets | Predicated threads | DRAM peak | DRAM MB/s | Load/store sectors/request |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| exact-chain | 16.67% | 33.33% | 3.76% | 96.24% | 70.09% | 0.00% | 6.69 | 6.63 / 2.89 |
| mixed_heterogeneous | 16.67% | 33.33% | 1.21% | 98.79% | 75.15% | 0.00% | 2.08 | 7.35 / 3.73 |
| large_scale | 16.67% | 33.33% | 1.08% | 98.92% | 75.58% | 0.00% | 3.03 | 7.52 / 3.70 |
| occupancy_stress | 16.63% | 33.33% | 1.31% | 98.69% | 83.22% | 0.01% | 14.21 | 9.72 / 4.06 |

All rows profile `simulate_v1_noninteractive_simple_scan`, the production simulator kernel. Raw CSV and parsed JSON are stored beside this report.

Profiled commit(s): `619f7d4aed0d23ae969ea81d6818c5f2a3c69f23`.

Observed DRAM utilization rounds to 0.00–0.01% of peak while measured bandwidth is 2.08–14.21 MB/s, so these runs are not DRAM-bandwidth-bound. Achieved occupancy is 16.63–16.67% versus 33.33–33.33% theoretical. The launches use 124 registers/thread and 16,640 shared bytes/block; registers limit residency to 2 blocks/SM.

Branch-target divergence spans 1.08–3.76%. Predicated lane utilization spans 70.09–83.22%, so low branch divergence does not mean all lanes do useful work.

Sector/request values are measured transaction density, but mixed access widths prevent converting them into a defensible coalescing-efficiency percentage without instruction-level access classification.

### Controlled occupancy saturation

On the same occupancy-stress graph, increasing the grid from 16 to 40 blocks raises achieved occupancy from 16.63% to 33.30% (the 33.33% register-limited ceiling). Kernel duration simultaneously grows by 1.45x, because only nine partitions perform useful work. This control proves the low 16-block occupancy is grid undersubscription; it does not claim that padding with idle blocks improves throughput.

### Identical-Boolean baseline profile

Both profiles use the same Boolean netlist, zero inputs, 2,000 cycles, four blocks, and the production simulator kernel. Nsight reports the final measured launch after each implementation's warm-up launch.

| Implementation | Kernel ms | Occupancy | Divergent targets | Predicated threads | DRAM MB/s | Registers/thread | Shared bytes/block |
|---|---:|---:|---:|---:|---:|---:|---:|
| Official upstream `9e913f9b5` | 41.801 | 16.66% | 1.94% | 88.55% | 17.35 | 90 | 4352 |
| Modified `619f7d4ae` | 41.404 | 16.66% | 1.89% | 88.60% | 14.20 | 124 | 16640 |

The modified kernel is 1.010x as fast by profiled kernel duration on this macro-free control. It consumes 124 registers/thread and 16,640 shared bytes/block versus 90 and 4,352 upstream; the four-block grid is too small to expose the resulting residency difference in achieved occupancy.

## Cooperative block-count sweep

| Blocks | Median cycles/s |
|---:|---:|
| 1 | 3,552 |
| 2 | 3,557 |
| 4 | 3,556 |
| 8 | 3,553 |
| 16 | 3,556 |
| 20 | 3,553 |
| 32 | 2,581 |
| 40 | 2,582 |

Throughput is flat from 1–20 blocks and drops at 32–40 blocks. Increasing cooperative grid size therefore does not expose additional useful parallel work for this single-partition mixed graph; scheduling/coordination, rather than DRAM bandwidth, is the observed scaling limit. This sweep varies grid size; it is not a substitute for the measured Nsight occupancy counters above.

## Other pools

External results are not available. `benchmark/other_pools.csv` is the import template; missing values remain `PENDING_EXTERNAL_DATA`.

## Interpretation limits

- Cross-category throughput is not a macro speedup ratio because the workloads contain different graphs.
- The upstream comparison is intentionally restricted to the identical Boolean netlist that both official upstream and modified GEM can execute.
- Macro-preserved versus shredded measurements require different legal netlist representations and must be reported separately from implementation-only speedup.
- Nsight counter values apply to the four named production workloads and this RTX 4050; they are not universal GPU claims.
