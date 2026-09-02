# Deliverable D benchmarks

## Official production benchmark

Run from the repository root:

```shell
python3 benchmark/run_benchmarks.py --repetitions 7
```

This command runs the correctness gate, regenerates deterministic RTL,
synthesizes with Yosys, partitions with the production Boomerang path, builds
and measures the production CUDA simulator, and compares an identical
macro-free netlist against official upstream commit
`9e913f9b5efc8b12027bfb374be8b1a0028df00a`. The runner creates an isolated
detached worktree under `/tmp`; it never treats the current binary as upstream.

The primary metric is simulated cycles divided by elapsed seconds around one
production simulator launch and its mandatory device synchronization. Parsing,
allocation, transfers, synthesis, and partitioning are excluded; their costs
are separately identifiable. Twelve launches are discarded before seven
measurements. Mutable state is reset outside every timed interval.

Machine-readable evidence is written to `benchmark/results/latest.json` and
`latest.csv`. The JSON contains commands, individual samples, complete captured
stdout, versions, commit, dirty-tree flag, graph counts, and preprocessing
times. Timestamped raw runs are kept locally in `results/runs/`.

Generated inputs and netlists live in the ignored `benchmark/generated/`
directory. They are deterministic from seed `20260902` and can always be
regenerated from `workloads/generate_workloads.py`.

## Nsight Compute

```shell
python3 benchmark/profile_boomerang_ncu.py
python3 benchmark/profile_boomerang_ncu.py --workload mixed_heterogeneous
python3 benchmark/profile_boomerang_ncu.py --workload large_scale
python3 benchmark/profile_block_sweep.py
```

The profiler first queries metrics supported by the installed Nsight Compute
and then targets the production simulator kernel on exact-chain, mixed, and
large workloads. It stores raw CSV plus parsed JSON. If NVIDIA performance-counter
permissions are disabled, it exits 2 and writes the exact blocker to
`benchmark/nsight_boomerang_status.md`; it never substitutes invented values.

## Classification of older files

- `flow1_microbench.py` and `bench_engine.cu`: supplemental standalone CUDA
  microbenchmark; not a real GEM throughput result.
- `flow2_pipeline_bench.py`: legacy structural experiment; not an official
  upstream comparison and not valid speedup evidence.
- `run_benchmarks.py`: official compatibility entry point to the production
  runner.
- `run_deliverable_d.py`: official measurement implementation.
- `analyze_deliverable_d.py`: report generator from raw JSON.
- `profile_boomerang_ncu.py`: production-kernel profiling automation.

## External competition results

Populate `benchmark/other_pools.csv` only from measured, attributable results.
Unknown submissions remain `PENDING_EXTERNAL_DATA`.
