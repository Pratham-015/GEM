# Temporary benchmark files

All reproducible scratch data belongs here and is ignored by Git. Benchmark
scripts use the following subdirectories:

- `generated/` for generated RTL, Yosys netlists, JSON, and GEM partitions;
- `results/` for timestamped raw runs and development-only summaries;
- `legacy/` for outputs from historical benchmark scripts;
- `cache/` for Python bytecode and other local caches.

Deleting these directories is safe. The production scripts recreate them.
