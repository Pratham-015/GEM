# Benchmark suite

The benchmark tree is split by purpose so production measurements, generated
scratch data, and historical experiments cannot be confused.

## Directory layout

- `scripts/` — production benchmark, report, block-sweep, and Nsight entry points.
- `workloads/` — deterministic RTL generator and independent Python reference model.
- `results/` — checked-in production throughput evidence and generated report.
- `profiles/` — checked-in Nsight Compute CSV, JSON, and status evidence.
- `legacy/` — older microbenchmarks and simulation artifacts retained for provenance;
  these are not official GEM speedup results.
- `temporary/` — all generated RTL, netlists, partitions, caches, development
  results, raw run directories, and temporary profiler output. Its contents are
  ignored except for its README.

## Production benchmark

Run from the repository root:

```shell
python3 benchmark/scripts/run_benchmarks.py --repetitions 7 --require-clean
```

This runs the correctness gate, generates deterministic RTL under
`benchmark/temporary/generated/`, synthesizes and partitions it, measures the
production CUDA simulator, and compares an identical macro-free netlist against
official upstream commit `9e913f9b5`. Every workload first runs for 48 randomized
cycles against `workloads/generated_workload_reference.py`.

Publishable summaries are written to `results/latest.json`, `latest.csv`, and
`performance_report.md`. Timestamped raw runs and development-only runs are kept
under `temporary/results/`. `--skip-correctness` never overwrites publishable
evidence.

## CARRY4 representation comparison

The production runner synthesizes the same CARRY4 RTL twice: a shredded AIG for
official upstream and a macro-preserved form for this implementation. Both forms
are correctness checked before timing. The ratio is representation plus
implementation performance, not an implementation-only speedup.

Run the focused, reproducible experiment with:

```shell
python3 benchmark/scripts/benchmark_carry4.py --repetitions 7 --blocks 4
```

Its compact evidence is written to `results/carry4_optimization.json`.

## Nsight Compute

```shell
python3 benchmark/scripts/profile_boomerang_ncu.py
python3 benchmark/scripts/profile_boomerang_ncu.py --workload boolean_heavy
python3 benchmark/scripts/profile_boomerang_ncu.py --workload upstream_boolean
python3 benchmark/scripts/profile_boomerang_ncu.py --workload mixed_heterogeneous
python3 benchmark/scripts/profile_boomerang_ncu.py --workload large_scale
python3 benchmark/scripts/profile_boomerang_ncu.py --workload occupancy_stress
python3 benchmark/scripts/profile_boomerang_ncu.py --workload occupancy_stress --blocks 40 --profile-name occupancy_stress_40b
python3 benchmark/scripts/profile_block_sweep.py --workload occupancy_stress --repetitions 5 --warmup-runs 8
```

Profiles are written to `profiles/`. The profiler records unsupported metrics or
permission failures explicitly; it does not invent zero-valued counters.

## Legacy material

`legacy/flow1_microbench.py` and `legacy/bench_engine.cu` form a standalone CUDA
microbenchmark. `legacy/flow2_pipeline_bench.py` is an older structural
experiment. They are retained for auditability but are not the official
Deliverable D comparison.
