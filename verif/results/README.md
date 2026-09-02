# A/B/C verification evidence

Run `python3 verif/record_abc_evidence.py` from the repository root. It records:

- independent CUDA macro-model comparisons, including real Xilinx UNISIM when installed;
- randomized RTL through Yosys, GEM partitioning, and the production CUDA kernel;
- the exact DSP→CARRY4→SRLC32E→DSP production chain, including a non-empty `StagedAIG` level split.

`abc_evidence_manifest.json` binds every log to SHA-256 hashes of the relevant
frontend, graph, formatter, kernel, and macro-model sources. A stored log is
evidence for that exact source state; rerun the recorder after any listed source changes.
