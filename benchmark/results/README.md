# Deliverable D results

Run `python3 benchmark/run_deliverable_d.py`, followed by
`python3 benchmark/analyze_deliverable_d.py`.

- `latest.json` contains environment metadata, every raw timing sample, commands,
  workload statistics, and summary statistics.
- `latest.csv` is the compact table.
- `performance_report.md` is generated only from `latest.json`.
- `runs/` contains timestamped local results and is intentionally ignored.

Nsight data is collected separately with
`python3 benchmark/profile_boomerang_ncu.py`. Missing counter permission is a
blocker and is never converted into zero-valued metrics.
