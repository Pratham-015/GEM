# Individual macro circuits

This folder contains small circuits used to compare a shredded upstream GEM
netlist with a macro-preserved Big-GEM netlist.

Each circuit has its own folder. The source file uses `SHREDDED` only during
the upstream synthesis run. Both forms have the same top-level inputs, outputs,
and behavior.

- `dsp48e2/multiply_bank/` contains eight independent DSP48E2 multipliers.
- `carry4/independent_bank/` contains 128 independent CARRY4 slices.
- `srlc32e/parallel_bank/` contains 128 independent SRLC32E shift registers.

Run all three comparisons from the repository root:

```bash
python3 benchmark/scripts/benchmark_individual_macros.py --repetitions 7
```

Generated netlists and partition files are written under
`benchmark/temporary/`, which is ignored by Git.
