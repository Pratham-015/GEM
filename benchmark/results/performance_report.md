# Deliverable D: Reproducible Production Performance Report

## Methodology

Primary metric: `simulated cycles / synchronized production-kernel elapsed seconds`.

Timing scope: one cooperative production simulation launch; excludes parsing, allocation, H2D/D2H, synthesis, partitioning, and output.

Every production row uses 12 untimed warm-up launches followed by seven measured launches in one initialized process; mutable SRAM, DSP, SRL, and input state is reset outside each timed interval.

Timing uses a host monotonic clock around the production launch and a mandatory post-launch device synchronization. It therefore includes kernel-launch latency but excludes setup and transfers. CUDA-event timing is not implemented.

## Environment

- Commit: `04796087195e3f0db28468301d77ecf02ad91392`
- Dirty during run: `True`
- GPU: `NVIDIA GeForce RTX 4050 Laptop GPU, 8.9, 596.49, 6141 MiB`
- CUDA/NVCC: `Build cuda_12.9.r12.9/compiler.36037853_0`
- Nsight Compute: `Version 2025.2.1.0 (build 35987062) (public-release)`
- Yosys: `Yosys 0.68 (git sha1 38e001a6f, Release, GNU /usr/bin/c++ 13.3.0)`
- Rust: `rustc 1.98.0 (88d9e12ae 2026-08-18)`
- Build: `cargo build --release --features cuda`
- CUDA blocks: `4`

- Production CUDA compile command: `LC_ALL="C" "nvcc" "-Xcompiler" "-O3" "-Xcompiler" "-ffunction-sections" "-Xcompiler" "-fdata-sections" "-Xcompiler" "-fPIC" "-m64" "-I" "/home/pratham_sharma/gem/target/debug/build/gem-0b35bd030a215153/out/ucc_csrc_includes" "-Xcompiler" "-Wall" "-Xcompiler" "-Wextra" "-Xcompiler" "-Wall" "-std=c++14" "-gencode" "arch=compute_80,code=sm_80" "-gencode" "arch=compute_70,code=sm_70" "-arch=compute_50" "-code=sm_50,compute_50" "-lineinfo" "-maxrregcount=128" "-DCARGO_PKG_NAME=gem" "-DCARGO_PKG_VERSION=0.1.0" "-DCARGO_PKG_VERSION_MAJOR=0" "-DCARGO_PKG_VERSION_MINOR=1" "-DCARGO_PKG_VERSION_PATCH=0" "-DUCC_VERSION=0.2.6" "csrc/kernel_v1.cu"`

## Correctness gate

**PASS** — `/usr/bin/python3 verif/full_integration_test.py`

production RTL-to-Yosys-to-partitioner-to-CUDA differential regression; this gates benchmark publication but is not a per-generated-workload oracle.

## Production throughput

| Workload | Cycles | AIG gates | DSP | CARRY4 | SRLC32E | Median cycles/s | Mean | Min | Max | Stddev |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| boolean_heavy | 2000 | 507 | 0 | 0 | 0 | 78,589 | 78,617 | 78,420 | 78,899 | 163 |
| dsp_heavy | 2000 | 4464 | 32 | 0 | 0 | 21,039 | 21,044 | 21,022 | 21,062 | 16 |
| carry_heavy | 1000 | 2880 | 0 | 128 | 0 | 1,571 | 1,571 | 1,571 | 1,572 | 0 |
| srl_heavy | 2000 | 576 | 0 | 0 | 128 | 42,794 | 42,845 | 42,634 | 43,058 | 172 |
| scaling_small | 1000 | 1120 | 4 | 8 | 8 | 7,720 | 7,715 | 7,682 | 7,726 | 15 |
| mixed_heterogeneous | 1000 | 3520 | 16 | 32 | 32 | 3,559 | 3,559 | 3,558 | 3,560 | 1 |
| deep_dependency | 200 | 1981 | 0 | 64 | 0 | 466 | 466 | 466 | 466 | 0 |
| large_scale | 200 | 8704 | 32 | 128 | 128 | 1,053 | 1,053 | 1,052 | 1,053 | 0 |

These are production GEM measurements, not isolated macro microkernels.

## Preprocessing cost

| Workload | Synthesis (s) | Partition (s) |
|---|---:|---:|
| boolean_heavy | 2.341 | 0.057 |
| dsp_heavy | 4.719 | 0.631 |
| carry_heavy | 2.323 | 0.248 |
| srl_heavy | 0.221 | 0.086 |
| scaling_small | 0.576 | 0.086 |
| mixed_heterogeneous | 3.307 | 0.456 |
| deep_dependency | 0.640 | 0.194 |
| large_scale | 12.004 | 2.638 |

## Heterogeneous scaling

| Scale | Actual cells | AIG gates | Macros | Median cycles/s | Mean elapsed/cycle (us) |
|---|---:|---:|---:|---:|---:|
| small | 1219 | 1120 | 20 | 7,720 | 129.53 |
| medium | 3770 | 3520 | 80 | 3,559 | 280.97 |
| large | 9340 | 8704 | 288 | 1,053 | 949.99 |

Cycles/second falls as heterogeneous graph work per simulated cycle grows; these points test scaling, not a same-workload implementation speedup.

## Unmodified upstream comparison

Both binaries execute the same macro-free gate-level netlist, zero input frames, cycle count, CUDA block count, one internal warm-up, GPU, and synchronized launch timing boundary. Three alternating pairs are discarded to precondition GPU clocks; the seven retained pairs alternate execution order.

| Implementation | Commit | Median cycles/s | Mean | Stddev |
|---|---|---:|---:|---:|
| Official upstream GEM | `9e913f9b5efc8b12027bfb374be8b1a0028df00a` | 59,385 | 59,349 | 84 |
| Modified GEM | `04796087195e3f0db28468301d77ecf02ad91392` | 59,422 | 59,377 | 87 |

Modified/upstream median ratio: **1.001x** (+0.1%).

## Macro-preserved versus shredded experiment

**INVALID — no performance number is reported.**

performance comparison suppressed because at least one representation failed RTL differential checking.

- Historical shredded/upstream differential: `checked=256 mismatches=145`
- Historical preserved/modified differential: `checked=256 mismatches=125`

## Nsight Compute

| Workload | Occupancy | Theoretical | Divergent targets | Uniform targets | Predicated threads | DRAM peak | DRAM MB/s | Load/store sectors/request |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| exact-chain | 16.67% | 33.33% | 3.76% | 96.24% | 70.09% | 0.00% | 6.81 | 6.63 / 2.89 |
| mixed_heterogeneous | 16.67% | 33.33% | 1.21% | 98.79% | 75.15% | 0.00% | 2.10 | 7.35 / 3.73 |
| large_scale | 16.67% | 33.33% | 1.08% | 98.92% | 75.57% | 0.00% | 3.28 | 7.52 / 3.70 |

All rows profile `simulate_v1_noninteractive_simple_scan`, the production simulator kernel. Raw CSV and parsed JSON are stored beside this report.

Profiled commit(s): `4260717aef83cad17ad57d1fad33966ee40bc0d4`.

Observed DRAM utilization rounds to 0.00–0.00% of peak while measured bandwidth is 2.10–6.81 MB/s, so these runs are not DRAM-bandwidth-bound. Achieved occupancy is 16.67–16.67% versus 33.33–33.33% theoretical. The launches use 124 registers/thread and 16,640 shared bytes/block; registers limit residency to 2 blocks/SM.

Branch-target divergence is 3.76% on the exact chain and falls to 1.21%/1.08% on mixed/large workloads. Predicated lane utilization remains 70–76%, so low branch divergence does not mean all lanes do useful work.

Sector/request values are measured transaction density, but mixed access widths prevent converting them into a defensible coalescing-efficiency percentage without instruction-level access classification.

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
- Nsight counter values apply to the three named production workloads and this RTX 4050; they are not universal GPU claims.
