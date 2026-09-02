#!/usr/bin/env python3
"""Run A/B/C verification and store reproducible, source-bound pass logs."""

import datetime
import hashlib
import json
import pathlib
import re
import shlex
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
RESULTS = ROOT / "verif" / "results"
SOURCES = (
    "scripts/synthesize_macros.py",
    "src/aig.rs",
    "src/flatten.rs",
    "src/macro_layout.rs",
    "csrc/kernel_v1_impl.cuh",
    "csrc/gem_macros.cuh",
    "verif/full_integration_test.py",
    "verif/host/diff_harness.py",
    "verif/host/randomized_production_dag.py",
)


def capture(command):
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=1200,
    )
    return result.returncode, result.stdout


def record(name, command, timestamp):
    returncode, output = capture(command)
    path = RESULTS / f"{name}_latest.log"
    header = (
        f"recorded_utc: {timestamp}\n"
        f"command: {shlex.join(map(str, command))}\n"
        f"returncode: {returncode}\n"
        "--- output ---\n"
    )
    path.write_text(header + output, encoding="utf-8")
    if returncode:
        raise RuntimeError(f"{name} failed; see {path}")
    return path


def record_cuda_binary_evidence(timestamp):
    """Prove that macro shared-memory and warp-vote code reached the binary."""
    binary = ROOT / "target" / "release" / "cuda_test"
    if not binary.exists():
        raise RuntimeError(f"missing CUDA binary: {binary}")
    outputs = {}
    for name, command in (
        ("resources", ["cuobjdump", "--dump-resource-usage", binary]),
        ("ptx", ["cuobjdump", "--dump-ptx", binary]),
        ("sass", ["cuobjdump", "--dump-sass", binary]),
    ):
        returncode, output = capture(command)
        if returncode:
            raise RuntimeError(f"cuobjdump {name} failed with exit {returncode}")
        outputs[name] = output

    shared_sizes = [
        int(size)
        for size in re.findall(
            r"Function _Z38simulate_v1_noninteractive_simple_scan[^\n]*:\n"
            r"[^\n]*SHARED:(\d+)",
            outputs["resources"],
        )
    ]
    checks = {
        "production_kernel_has_shared_memory": bool(shared_sizes) and min(shared_sizes) >= 12288,
        "macro_tile_is_12288_bytes": "shared_macro_fields[12288]" in outputs["ptx"],
        "compiled_shared_store_64": "STS.64" in outputs["sass"],
        "compiled_shared_load_64": "LDS.U.64" in outputs["sass"],
        "compiled_warp_vote": "VOTE." in outputs["sass"],
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise RuntimeError("compiled CUDA evidence missing: " + ", ".join(failed))

    interesting_sass = [
        line.strip()
        for line in outputs["sass"].splitlines()
        if any(op in line for op in ("STS.64", "LDS.U.64", "VOTE."))
    ][:24]
    path = RESULTS / "cuda_kernel_binary_latest.log"
    path.write_text(
        f"recorded_utc: {timestamp}\n"
        f"binary: {binary.relative_to(ROOT)}\n"
        f"shared_bytes_by_arch: {shared_sizes}\n"
        + "\n".join(f"{name}: PASS" for name in checks)
        + "\n--- representative SASS ---\n"
        + "\n".join(interesting_sass)
        + "\n",
        encoding="utf-8",
    )
    return path


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    jobs = (
        ("unisim_gpu", [sys.executable, "verif/host/diff_harness.py"]),
        (
            "randomized_production_cuda",
            [sys.executable, "verif/host/randomized_production_dag.py", "--seeds", "4", "--cycles", "48"],
        ),
        (
            "exact_staged_production_cuda",
            [sys.executable, "-c", "import verif.full_integration_test as t; t.phase_exact_macro_chain()"],
        ),
    )
    logs = [record(name, command, timestamp) for name, command in jobs]
    logs.append(record_cuda_binary_evidence(timestamp))
    versions = {}
    for name, command in (
        ("yosys", ["yosys", "--version"]),
        ("nvcc", ["nvcc", "--version"]),
        ("gpu", ["nvidia-smi", "--query-gpu=name,compute_cap,driver_version", "--format=csv,noheader"]),
    ):
        rc, output = capture(command)
        versions[name] = {"returncode": rc, "output": output.strip()}
    manifest = {
        "recorded_utc": timestamp,
        "status": "PASS",
        "versions": versions,
        "source_sha256": {
            source: hashlib.sha256((ROOT / source).read_bytes()).hexdigest() for source in SOURCES
        },
        "logs": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in logs
        },
    }
    (RESULTS / "abc_evidence_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"PASS: stored {len(logs)} A/B/C evidence logs in {RESULTS}")


if __name__ == "__main__":
    main()
