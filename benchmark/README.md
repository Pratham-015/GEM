# The Big-GEM Theory Benchmark

Event: Takneek PS - Zenith

This folder contains the performance tests required by the problem statement.
It measures simulation speed and collects Nsight Compute data.

## Setup

Run the commands from the repository root. The project needs:

- a Linux system with an NVIDIA GPU;
- the CUDA toolkit and `nvcc`;
- Rust and Cargo;
- Python 3;
- Yosys 0.68 with SystemVerilog support; and
- Nsight Compute (`ncu`) for the profile commands.

Build GEM before running the tests:

```bash
cargo build --release --features cuda
```

## Folder contents

- `scripts/run_benchmarks.py` runs the main speed test.
- `scripts/benchmark_carry4.py` compares the CARRY4 version with upstream GEM.
- `scripts/profile_ncu.py` collects memory and warp data with Nsight Compute.
- `workloads/` creates the input circuits used by the speed test.
- `results/` contains the saved speed results.
- `profiles/` contains the saved Nsight Compute results.
- `temporary/` is created during a run. Git ignores this folder.

## Run the speed test

From the repository root, run:

```bash
python3 benchmark/scripts/run_benchmarks.py --repetitions 7
```

The script measures cycles per second and runs the same Boolean circuit on
upstream GEM. Generated files are placed in
`benchmark/temporary/`.

## Run the CARRY4 comparison

```bash
python3 benchmark/scripts/benchmark_carry4.py --repetitions 7 --blocks 4
```

## Run Nsight Compute

Use these three commands:

```bash
python3 benchmark/scripts/profile_ncu.py --workload upstream_boolean
python3 benchmark/scripts/profile_ncu.py --workload boolean_heavy
python3 benchmark/scripts/profile_ncu.py --workload mixed_heterogeneous
```

The first two commands compare upstream GEM and this project on the same
Boolean circuit. The third command profiles a circuit that uses DSP48E2,
CARRY4, SRLC32E, and Boolean logic.

Nsight Compute needs permission to read NVIDIA performance counters. If the
permission is missing, the script reports the error instead of saving fake
values.
