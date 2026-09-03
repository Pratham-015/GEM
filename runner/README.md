# Automated GPU Simulation Runner (`runner/`)

This directory provides a single-command tool to compile and simulate **any arbitrary Verilog (`.v`) or SystemVerilog (`.sv`) design** on an NVIDIA GPU using both:
1. **Flow A — Original GEM**: Standard flattened flow (macros shredded into 1-bit boolean AIG gates).
2. **Flow B — Modified GEM**: Macro-preserved flow (hardware macros evaluated natively on the GPU ALU).

---

## Quick Start

To simulate any arbitrary circuit on the GPU:

```bash
python3 runner/run_circuit.py path/to/your_circuit.sv
```

### Options:
```bash
python3 runner/run_circuit.py path/to/your_circuit.sv \
    --top my_top_module \    # Optional: Top module name (auto-detected if omitted)
    --cycles 2000 \          # Optional: Number of simulation cycles (default: 1000)
    --blocks 4 \             # Optional: Number of GPU cooperative blocks (default: 4)
    --flow both              # Optional: 'both', 'original', or 'modified' (default: 'both')
```

---

## What the Tool Does Automatically

1. **Auto-Detection**: Automatically detects the top-level module name if not specified.
2. **Synthesis (Yosys)**:
   - For **Flow A**: Ingests whitebox behavioral models so macros are shredded into AIG cells.
   - For **Flow B**: Ingests blackbox definitions and maps Xilinx DSPs/Carry chains to native GEM macros.
3. **Partitioning**: Runs GEM's `cut_map_interactive` to partition the graph across GPU thread blocks.
4. **GPU Execution**: Launches `cuda_dummy_test` on your NVIDIA GPU to run warm-up and timed cycles.
5. **Comparison Report**: Prints a clean side-by-side comparison of gate count, macro counts, gate reduction %, and GPU throughput speedup.

---

## Example Test

Run on the realistic multi-macro signal processor pipeline:

```bash
python3 runner/run_circuit.py test3/signal_processor.sv --top signal_processor --cycles 2000
```

