# Big-GEM — Takneek Zenith

**Problem statement:** The Big-GEM Theory  

This project extends NVIDIA GEM with native heterogeneous GPU execution for the
Xilinx DSP48E2 subset, CARRY4, and SRLC32E primitives. The original `README.md`
is retained as the upstream-oriented GEM documentation; this file contains the
submission-specific setup.

## Required environment

- 64-bit Linux with a CUDA-capable NVIDIA GPU and current NVIDIA driver;
- CUDA Toolkit with `nvcc` available in `PATH`;
- Rust stable (`rustc` and `cargo`);
- Yosys **0.68** built with the Slang SystemVerilog frontend (`read_slang`);
- Python 3.10 or newer;
- Icarus Verilog (`iverilog` and `vvp`) for differential testbenches;
- Nsight Compute (`ncu`) for profiling; access to NVIDIA performance counters
  must be enabled for Deliverable D profiling.

Xilinx UNISIM sources are optional. When available, set `UNISIM_DIR` to their
location to enable comparisons with the vendor models. The repository does not
redistribute those sources.

## Build

From the repository root:

```shell
cargo build --release --features cuda
```

The build detects the installed GPU architecture. It can be overridden when
needed, for example:

```shell
GEM_CUDA_ARCH=sm_89 cargo build --release --features cuda
```

## Verify the complete implementation

```shell
python3 verif/full_integration_test.py
```

This checks Yosys macro preservation, host DAG construction, aligned macro
storage, CUDA macro models, production RTL-to-CUDA execution, randomized mixed
macro graphs, Cargo tests, and available Nsight counters.

## Run the production benchmarks

```shell
python3 benchmark/scripts/run_benchmarks.py --repetitions 7
python3 benchmark/scripts/benchmark_carry4.py --repetitions 7 --blocks 4
```

Generated netlists, partitions, caches, and raw run directories are placed in
`benchmark/temporary/` and are intentionally ignored by Git. Published benchmark
summaries live in `benchmark/results/`, while Nsight evidence lives in
`benchmark/profiles/`. See `benchmark/README.md` for the three profiler
commands.

## Typical setup checks

```shell
nvidia-smi
nvcc --version
rustc --version
yosys -V
iverilog -V
ncu --version
```

The submission assumes a single global clock domain and zero-initialized internal
DSP/SRLC32E state, as specified by the Zenith problem statement.
