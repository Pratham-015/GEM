# Deliverable D benchmarks

## Official production benchmark

Run from the repository root:

```shell
python3 benchmark/run_benchmarks.py --repetitions 7 --require-clean
```

This command runs the correctness gate, regenerates deterministic RTL,
synthesizes with Yosys, partitions with the production Boomerang path, builds
and measures the production CUDA simulator, and compares an identical
macro-free netlist against official upstream commit. The runner creates an isolated
detached worktree under `/tmp`; it never treats the current binary as upstream.
`--require-clean` prevents final evidence from being published against source
that cannot be reconstructed from the recorded commit.

Before timing, every generated workload is run through the production CUDA
simulator for 48 randomized cycles and compared event-by-event with
`generated_workload_reference.py`. That model independently reconstructs the
generated ordinary RTL and imports only the literal Python macro models under
`verif/golden`; it never calls the C++/CUDA evaluator. Source, netlist,
partition, binary, reference, and VCD SHA-256 hashes are recorded in JSON.

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

`--skip-correctness` is only a development shortcut. Such runs are written to
`benchmark/results/development/` and cannot overwrite publishable `latest.*`
evidence.

## Macro-representation comparison

The runner also regenerates a 15-CARRY4 combinational design twice from the
same RTL: a fully shredded AIG netlist for official upstream and a preserved
CARRY4 netlist for modified GEM. Random vectors prove the shredded netlist in
Icarus and the preserved netlist in production CUDA. Timed runs use the exact
constant-zero input supported by both benchmark binaries and separately prove
that input in both simulators. The resulting ratio is explicitly labelled as
representation-plus-implementation, not an implementation-only speedup.

Historical upstream GEM's changing-vector VCD adapter is not used as random
correctness evidence because it does not retain vector event timing reliably.
This limitation is recorded rather than hidden or corrected after measurement.

## Nsight Compute

```shell
python3 benchmark/profile_boomerang_ncu.py
python3 benchmark/profile_boomerang_ncu.py --workload boolean_heavy
python3 benchmark/profile_boomerang_ncu.py --workload upstream_boolean
python3 benchmark/profile_boomerang_ncu.py --workload mixed_heterogeneous
python3 benchmark/profile_boomerang_ncu.py --workload large_scale
python3 benchmark/profile_boomerang_ncu.py --workload occupancy_stress
python3 benchmark/profile_boomerang_ncu.py --workload occupancy_stress --blocks 40 --profile-name occupancy_stress_40b
python3 benchmark/profile_block_sweep.py --workload occupancy_stress --repetitions 5 --warmup-runs 8
```

The profiler first queries metrics supported by the installed Nsight Compute
and then targets the production simulator kernel. The Boolean pair profiles
the same netlist, zero input, cycle count, and block count on official upstream
and modified GEM. The 16/40-block occupancy pair separates useful-partition
scaling from artificial occupancy produced by idle blocks. Source, executable,
and raw-CSV hashes are stored with the parsed JSON. If NVIDIA performance-counter
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
