# Deliverable D: Reproducible Production Performance Report

## Methodology

Primary metric: `simulated cycles / synchronized production-kernel elapsed seconds`.

Timing scope: one cooperative production simulation launch; excludes parsing, allocation, H2D/D2H, synthesis, partitioning, and output.

Every production row uses 12 untimed warm-up launches followed by 7 measured launches in one initialized process; mutable SRAM, DSP, SRL, and input state is reset outside each timed interval.

Timing uses a host monotonic clock around the production launch and a mandatory post-launch device synchronization. It therefore includes kernel-launch latency but excludes setup and transfers. CUDA-event timing is not implemented.

## Environment

- GPU: `NVIDIA GeForce RTX 4050 Laptop GPU, 8.9, 596.49, 6141 MiB`
- CUDA/NVCC: `Build cuda_12.9.r12.9/compiler.36037853_0`
- Nsight Compute: `Version 2025.2.1.0 (build 35987062) (public-release)`
- Yosys: `Yosys 0.68 (git sha1 38e001a6f, Release, GNU /usr/bin/c++ 13.3.0)`
- Rust: `rustc 1.98.0 (88d9e12ae 2026-08-18)`
- Build: `cargo build --release --features cuda`
- CUDA blocks: `4`

- Production CUDA compile command: `LC_ALL="C" "nvcc" "-Xcompiler" "-O3" "-Xcompiler" "-ffunction-sections" "-Xcompiler" "-fdata-sections" "-Xcompiler" "-fPIC" "-m64" "-I" "/home/pratham_sharma/gem/target/release/build/gem-3c058311bbecb430/out/ucc_csrc_includes" "-Xcompiler" "-Wall" "-Xcompiler" "-Wextra" "-Xcompiler" "-Wall" "-std=c++14" "-gencode" "arch=compute_80,code=sm_80" "-gencode" "arch=compute_70,code=sm_70" "-arch=compute_50" "-code=sm_50,compute_50" "-lineinfo" "-maxrregcount=128" "-DCARGO_PKG_NAME=gem" "-DCARGO_PKG_VERSION=0.1.0" "-DCARGO_PKG_VERSION_MAJOR=0" "-DCARGO_PKG_VERSION_MINOR=1" "-DCARGO_PKG_VERSION_PATCH=0" "-DUCC_VERSION=0.2.6" "csrc/kernel_v1.cu"`

## Correctness gate

**PASS** — `/usr/bin/python3 verif/full_integration_test.py`

production RTL-to-Yosys-to-partitioner-to-CUDA differential regression; this gates benchmark publication but is not a per-generated-workload oracle.

## Per-workload differential gates

Every timed workload is separately checked against the independent Python event model in `benchmark/workloads/generated_workload_reference.py`. The model uses the literal golden primitive models, not CUDA implementation code.

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
| boolean_heavy | 4 | 2000 | 507 | 0 | 0 | 0 | 73,059 | 73,013 | 72,886 | 73,116 | 93 |
| dsp_heavy | 4 | 2000 | 4464 | 32 | 0 | 0 | 20,741 | 20,741 | 20,726 | 20,761 | 12 |
| carry_heavy | 4 | 1000 | 2880 | 0 | 128 | 0 | 3,161 | 3,174 | 3,159 | 3,195 | 17 |
| srl_heavy | 4 | 2000 | 576 | 0 | 0 | 128 | 44,171 | 44,192 | 44,022 | 44,395 | 150 |
| scaling_small | 4 | 1000 | 1120 | 4 | 8 | 8 | 7,578 | 7,579 | 7,574 | 7,584 | 4 |
| mixed_heterogeneous | 4 | 1000 | 3520 | 16 | 32 | 32 | 3,517 | 3,514 | 3,499 | 3,518 | 7 |
| deep_dependency | 4 | 200 | 1981 | 0 | 64 | 0 | 890 | 891 | 882 | 900 | 9 |
| large_scale | 4 | 200 | 8704 | 32 | 128 | 128 | 1,041 | 1,046 | 1,041 | 1,052 | 6 |
| occupancy_stress | 16 | 1000 | 82385 | 1 | 1 | 1 | 16,805 | 16,804 | 16,798 | 16,809 | 4 |

These are production GEM measurements, not isolated macro microkernels.

## Preprocessing cost

| Workload | Synthesis (s) | Partition (s) |
|---|---:|---:|
| boolean_heavy | 4.072 | 0.085 |
| dsp_heavy | 6.557 | 0.874 |
| carry_heavy | 3.205 | 0.316 |
| srl_heavy | 0.296 | 0.091 |
| scaling_small | 0.916 | 0.125 |
| mixed_heterogeneous | 4.659 | 0.616 |
| deep_dependency | 0.916 | 0.246 |
| large_scale | 18.555 | 3.413 |
| occupancy_stress | 44.442 | 5.245 |

## Heterogeneous scaling

| Scale | Actual cells | AIG gates | Macros | Median cycles/s | Mean elapsed/cycle (us) |
|---|---:|---:|---:|---:|---:|
| small | 1219 | 1120 | 20 | 7,578 | 131.97 |
| medium | 3770 | 3520 | 80 | 3,517 | 284.31 |
| large | 9340 | 8704 | 288 | 1,041 | 960.16 |

Cycles/second falls as heterogeneous graph work per simulated cycle grows; these points test scaling, not a same-workload implementation speedup.

## Multi-partition occupancy scaling

| Blocks | Median cycles/s |
|---:|---:|
| 1 | 5,226 |
| 4 | 10,737 |
| 8 | 13,009 |
| 9 | 16,806 |
| 12 | 16,754 |
| 16 | 16,707 |
| 20 | 16,684 |
| 28 | 11,393 |
| 40 | 11,398 |

The 9-partition heterogeneous stress graph scales from 5,226 cycles/s at one block to 16,806 cycles/s at 9 blocks (**3.22x**). This measures useful multi-partition execution; larger grids with idle blocks are not counted as an occupancy improvement.

## Unmodified upstream comparison

Both binaries execute the same macro-free gate-level netlist, zero input frames, cycle count, CUDA block count, one internal warm-up, GPU, and synchronized launch timing boundary. Three alternating pairs are discarded to precondition GPU clocks; the seven retained pairs alternate execution order.

| Workload | Cycles | Upstream GEM CPS | Big-GEM CPS | Speedup |
|---|---:|---:|---:|---:|
| boolean_heavy (static zero input) | 2000 | 60,301 | 55,071 | 0.913x |

Upstream `9e913f9b5`: mean 60,452 CPS, standard deviation 2,385. Big-GEM `a6ddfba96`: mean 55,095 CPS, standard deviation 78.

Modified/upstream median ratio: **0.913x** (-8.7%).

## Macro-preserved versus shredded experiment

This experiment uses one combinational 15-CARRY4 chain. Both netlists are regenerated from the same RTL; the upstream form contains no macros and the modified form preserves all 15 CARRY4 instances.

Random changing-vector semantics are checked as RTL versus Icarus-simulated shredded gates and RTL versus production-CUDA preserved macros. The old upstream VCD adapter is not used for changing vectors because it does not preserve vector-event timing reliably. The timed comparison uses constant-zero input in both binaries, and that exact input is separately checked in both simulators.

- Random RTL vs shredded Icarus: `checked=195 mismatches=0`
- Random RTL vs preserved CUDA: `checked=195 mismatches=0`
- Timed zero input vs upstream: `checked=17 mismatches=0`
- Timed zero input vs modified: `checked=17 mismatches=0`

| Representation | Median cycles/s | Mean | Stddev |
|---|---:|---:|---:|
| Shredded, official upstream | 80,133 | 80,111 | 83 |
| Macro-preserved, modified | 17,778 | 16,841 | 1,512 |

Representation-plus-implementation ratio: **0.222x** (-77.8%). This is not an implementation-only speedup.

The result is a measured regression, not a claimed gain: macro dispatch and cooperative barriers cost more than the removed AIG work for this graph.

## Nsight Compute

| Workload | Occupancy | Theoretical | Divergent targets | Uniform targets | Predicated threads | DRAM peak | DRAM MB/s | Load/store sectors/request |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| exact-chain | 16.67% | 33.33% | 3.65% | 96.35% | 70.15% | 0.00% | 5.65 | 6.63 / 2.89 |

All rows profile `simulate_v1_noninteractive_simple_scan`, the production simulator kernel. Raw CSV and parsed JSON are stored beside this report.

Observed DRAM utilization rounds to 0.00–0.00% of peak while measured bandwidth is 5.65–5.65 MB/s, so these runs are not DRAM-bandwidth-bound. Achieved occupancy is 16.67–16.67% versus 33.33–33.33% theoretical. The launches use 121 registers/thread and 16,640 shared bytes/block; registers limit residency to 2 blocks/SM.

Branch-target divergence spans 3.65–3.65%. Predicated lane utilization spans 70.15–70.15%, so low branch divergence does not mean all lanes do useful work.

Sector/request values are measured transaction density, but mixed access widths prevent converting them into a defensible coalescing-efficiency percentage without instruction-level access classification.

Excluded stale profiles whose recorded kernel/macro source hashes do not match the current files: nsight_mixed_heterogeneous.json, nsight_large_scale.json, nsight_occupancy_stress.json.

### Identical-Boolean baseline profile

NOT REPORTED: the modified baseline profile is stale relative to current production sources.

## Cooperative block-count sweep

| Blocks | Median cycles/s |
|---:|---:|
| 1 | 3,564 |
| 2 | 3,554 |
| 4 | 3,516 |
| 8 | 3,539 |
| 16 | 3,508 |
| 20 | 3,531 |
| 32 | 2,593 |
| 40 | 2,572 |

Throughput is flat from 1–20 blocks and drops at 32–40 blocks. Increasing cooperative grid size therefore does not expose additional useful parallel work for this single-partition mixed graph; scheduling/coordination, rather than DRAM bandwidth, is the observed scaling limit. This sweep varies grid size; it is not a substitute for the measured Nsight occupancy counters above.

## Interpretation limits

- Cross-category throughput is not a macro speedup ratio because the workloads contain different graphs.
- The upstream comparison is intentionally restricted to the identical Boolean netlist that both official upstream and modified GEM can execute.
- Macro-preserved versus shredded measurements require different legal netlist representations and must be reported separately from implementation-only speedup.
- Nsight counter values apply to the four named production workloads and this RTX 4050; they are not universal GPU claims.
