# Deliverable D results

Run `python3 benchmark/scripts/run_deliverable_d.py`, followed by
`python3 benchmark/scripts/analyze_deliverable_d.py`.

- `latest.json` contains environment metadata, every raw timing sample, commands,
  workload statistics, and summary statistics.
- `latest.csv` is the compact table.
- `performance_report.md` is generated only from `latest.json`.
- `carry4_optimization.json` is the focused, correctness-gated CARRY4
  before/after evidence produced by `benchmark/scripts/benchmark_carry4.py`.
- `carry4_optimization.md` is the short human-readable summary of that result.
- Timestamped local runs are stored under `benchmark/temporary/results/runs/`.

Nsight data is collected separately with
`python3 benchmark/scripts/profile_boomerang_ncu.py`. Profiles are stored under
`benchmark/profiles/`. Missing counter permission is a
blocker and is never converted into zero-valued metrics.
