#!/usr/bin/env python3
"""Generate a conservative human-readable report from raw D results."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "benchmark/results"


def fmt(value):
    return f"{value:,.0f}"


def main():
    data = json.loads((RESULTS / "latest.json").read_text())
    env = data["environment"]
    lines = ["# Deliverable D: Reproducible Production Performance Report", "",
             "## Methodology", "",
             f"Primary metric: `{data['metric_definition']}`.", "",
             f"Timing scope: {data['timing_scope']}.", "",
             "Every production row uses 12 untimed warm-up launches followed by seven measured launches in one initialized process; mutable SRAM, DSP, SRL, and input state is reset outside each timed interval.", "",
             "Timing uses a host monotonic clock around the production launch and a mandatory post-launch device synchronization. It therefore includes kernel-launch latency but excludes setup and transfers. CUDA-event timing is not implemented.", "",
             "## Environment", "",
             f"- Commit: `{env['commit']}`", f"- Dirty during run: `{env['dirty']}`",
             f"- GPU: `{env['gpu']}`", f"- CUDA/NVCC: `{env['cuda'].splitlines()[-1]}`",
             f"- Nsight Compute: `{env['ncu'].splitlines()[-1]}`",
             f"- Yosys: `{env['yosys']}`", f"- Rust: `{env['rust']}`",
             f"- Build: `{env['build']}`", f"- CUDA blocks: `{env['cuda_blocks']}`", "",
             f"- Production CUDA compile command: `{env.get('cuda_compile_command', 'UNAVAILABLE')}`", "",
             "## Correctness gate", ""]
    gate = data.get("correctness_gate")
    if gate:
        lines += [f"**{gate['status']}** — `{ ' '.join(str(x) for x in gate['command']) }`", "",
                  gate["scope"] + ".", ""]
    else:
        lines += ["NOT RUN — these measurements are development-only and must not be published as final results.", ""]
    lines += [
             "## Production throughput", "",
             "| Workload | Cycles | AIG gates | DSP | CARRY4 | SRLC32E | Median cycles/s | Mean | Min | Max | Stddev |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for row in data["results"]:
        n, s = row["netlist_stats"], row["measurement"]["summary"]
        lines.append(f"| {row['name']} | {row['cycles']} | {n['aig_cells']} | {n['dsp']} | {n['carry4']} | {n['srlc32e']} | {fmt(s['median_cps'])} | {fmt(s['mean_cps'])} | {fmt(s['min_cps'])} | {fmt(s['max_cps'])} | {fmt(s['stdev_cps'])} |")
    lines += ["", "These are production GEM measurements, not isolated macro microkernels.", "",
              "## Preprocessing cost", "",
              "| Workload | Synthesis (s) | Partition (s) |", "|---|---:|---:|"]
    for row in data["results"]:
        lines.append(f"| {row['name']} | {row['synthesis_seconds']:.3f} | {row['partition_seconds']:.3f} |")
    scaling = [row for row in data["results"] if row.get("requested", {}).get("scale_group") == "heterogeneous"]
    lines += ["", "## Heterogeneous scaling", ""]
    if scaling:
        lines += ["| Scale | Actual cells | AIG gates | Macros | Median cycles/s | Mean elapsed/cycle (us) |",
                  "|---|---:|---:|---:|---:|---:|"]
        order = {"small": 0, "medium": 1, "large": 2}
        for row in sorted(scaling, key=lambda x: order[x["requested"]["scale"]]):
            n, s = row["netlist_stats"], row["measurement"]["summary"]
            macros = n["dsp"] + n["carry4"] + n["srlc32e"]
            lines.append(f"| {row['requested']['scale']} | {n['cells']} | {n['aig_cells']} | {macros} | {fmt(s['median_cps'])} | {1e6/s['median_cps']:.2f} |")
        lines += ["", "Cycles/second falls as heterogeneous graph work per simulated cycle grows; these points test scaling, not a same-workload implementation speedup."]
    else:
        lines.append("NOT MEASURED")
    lines += ["",
              "## Unmodified upstream comparison", ""]
    baseline = data.get("upstream_baseline")
    modified = data.get("modified_identical_upstream_workload")
    if baseline and modified:
        b, m = baseline["summary"], modified["summary"]
        speedup = data["boolean_speedup"]
        lines += ["Both binaries execute the same macro-free gate-level netlist, zero input frames, cycle count, CUDA block count, one internal warm-up, GPU, and synchronized launch timing boundary. Three alternating pairs are discarded to precondition GPU clocks; the seven retained pairs alternate execution order.", "",
                  "| Implementation | Commit | Median cycles/s | Mean | Stddev |", "|---|---|---:|---:|---:|",
                  f"| Official upstream GEM | `{baseline['commit']}` | {fmt(b['median_cps'])} | {fmt(b['mean_cps'])} | {fmt(b['stdev_cps'])} |",
                  f"| Modified GEM | `{env['commit']}` | {fmt(m['median_cps'])} | {fmt(m['mean_cps'])} | {fmt(m['stdev_cps'])} |", "",
                  f"Modified/upstream median ratio: **{speedup:.3f}x** ({(speedup-1)*100:+.1f}%)."]
    else:
        lines.append("NOT MEASURED")
    rep = data.get("macro_representation_experiment")
    lines += ["", "## Macro-preserved versus shredded experiment", ""]
    if not rep:
        lines.append("NOT MEASURED")
    elif rep["correctness"]["status"] != "PASS":
        a_tail = rep["correctness"]["upstream_diff"].strip().splitlines()[-1]
        b_tail = rep["correctness"]["modified_diff"].strip().splitlines()[-1]
        lines += ["**INVALID — no performance number is reported.**", "", rep["reason"] + ".", "",
                  f"- Historical shredded/upstream differential: `{a_tail}`",
                  f"- Historical preserved/modified differential: `{b_tail}`"]
    else:
        a = rep["shredded_upstream"]["summary"]
        b = rep["preserved_modified"]["summary"]
        lines += ["Both representations passed output differential checking against the same RTL stimulus.", "",
                  "| Representation | Median cycles/s | Mean | Stddev |", "|---|---:|---:|---:|",
                  f"| Shredded, official upstream | {fmt(a['median_cps'])} | {fmt(a['mean_cps'])} | {fmt(a['stdev_cps'])} |",
                  f"| Macro-preserved, modified | {fmt(b['median_cps'])} | {fmt(b['mean_cps'])} | {fmt(b['stdev_cps'])} |", "",
                  f"Representation-plus-implementation ratio: **{rep['speedup']:.3f}x**. This is not an implementation-only speedup."]
    status = (ROOT / "benchmark/nsight_boomerang_status.md")
    nsight = status.read_text().replace("# Nsight Boomerang Profile\n\n", "") if status.exists() else "NOT MEASURED"
    lines += ["", "## Nsight Compute", "", nsight, "",
              "## Other pools", "", "External results are not available. `benchmark/other_pools.csv` is the import template; missing values remain `PENDING_EXTERNAL_DATA`.", "",
              "## Interpretation limits", "",
              "- Cross-category throughput is not a macro speedup ratio because the workloads contain different graphs.",
              "- The upstream comparison is intentionally restricted to the identical Boolean netlist that both official upstream and modified GEM can execute.",
              "- Macro-preserved versus shredded measurements require different legal netlist representations and must be reported separately from implementation-only speedup.",
              "- Memory bandwidth, coalescing, occupancy, and divergence are not claimed unless the Nsight section contains measured counters.", ""]
    (RESULTS / "performance_report.md").write_text("\n".join(lines), encoding="utf-8")
    print("report:", RESULTS / "performance_report.md")


if __name__ == "__main__":
    main()
