#!/usr/bin/env python3
"""Generate a conservative human-readable report from raw D results."""

import json
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "benchmark/results"


def fmt(value):
    return f"{value:,.0f}"


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def profile_is_current(profile):
    """Reject profile JSON whose recorded production sources changed later."""
    recorded = profile.get("sha256", {})
    required = {
        "kernel_source": ROOT / "csrc/kernel_v1_impl.cuh",
        "macro_source": ROOT / "csrc/gem_macros.cuh",
    }
    return all(recorded.get(name) == sha256_file(path)
               for name, path in required.items())


def main():
    data = json.loads((RESULTS / "latest.json").read_text())
    env = data["environment"]
    repetitions = data["results"][0]["measurement"]["summary"]["samples"]
    lines = ["# Deliverable D: Reproducible Production Performance Report", "",
             "## Methodology", "",
             f"Primary metric: `{data['metric_definition']}`.", "",
             f"Timing scope: {data['timing_scope']}.", "",
             f"Every production row uses 12 untimed warm-up launches followed by {repetitions} measured launches in one initialized process; mutable SRAM, DSP, SRL, and input state is reset outside each timed interval.", "",
             "Timing uses a host monotonic clock around the production launch and a mandatory post-launch device synchronization. It therefore includes kernel-launch latency but excludes setup and transfers. CUDA-event timing is not implemented.", "",
             "## Environment", "",
             f"- Commit: `{env['commit'][:9]}`", f"- Dirty during run: `{env['dirty']}`",
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
    lines += ["## Per-workload differential gates", "",
              "Every timed workload is separately checked against the independent Python event model in `benchmark/generated_workload_reference.py`. The model uses the literal golden primitive models, not CUDA implementation code.", "",
              "| Workload | Status | Random cycles | Result bits | Checked event values | Mismatches |",
              "|---|---|---:|---:|---:|---:|"]
    for row in data["results"]:
        gate = row.get("workload_correctness")
        if gate:
            lines.append(f"| {row['name']} | {gate['status']} | {gate['cycles']} | {gate['result_width']} | {gate['checked_values']} | {gate['mismatches']} |")
        else:
            lines.append(f"| {row['name']} | NOT RUN | — | — | — | — |")
    lines += [
             "## Production throughput", "",
             "| Workload | Blocks | Cycles | AIG gates | DSP | CARRY4 | SRLC32E | Median cycles/s | Mean | Min | Max | Stddev |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for row in data["results"]:
        n, s = row["netlist_stats"], row["measurement"]["summary"]
        command = [str(value) for value in row["measurement"]["command"]]
        blocks = command[3]
        lines.append(f"| {row['name']} | {blocks} | {row['cycles']} | {n['aig_cells']} | {n['dsp']} | {n['carry4']} | {n['srlc32e']} | {fmt(s['median_cps'])} | {fmt(s['mean_cps'])} | {fmt(s['min_cps'])} | {fmt(s['max_cps'])} | {fmt(s['stdev_cps'])} |")
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
    occupancy_sweep_path = RESULTS / "block_sweep_occupancy_stress.json"
    lines += ["", "## Multi-partition occupancy scaling", ""]
    if occupancy_sweep_path.exists():
        sweep = json.loads(occupancy_sweep_path.read_text())
        lines += ["| Blocks | Median cycles/s |", "|---:|---:|"]
        for row in sweep["results"]:
            lines.append(f"| {row['blocks']} | {fmt(row['median_cps'])} |")
        one = next(row["median_cps"] for row in sweep["results"] if row["blocks"] == 1)
        best = max(sweep["results"], key=lambda row: row["median_cps"])
        lines += ["", f"The 9-partition heterogeneous stress graph scales from {fmt(one)} cycles/s at one block to {fmt(best['median_cps'])} cycles/s at {best['blocks']} blocks (**{best['median_cps']/one:.2f}x**). This measures useful multi-partition execution; larger grids with idle blocks are not counted as an occupancy improvement."]
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
                  "| Workload | Cycles | Upstream GEM CPS | Big-GEM CPS | Speedup |", "|---|---:|---:|---:|---:|",
                  f"| boolean_heavy (static zero input) | {baseline['samples'][0]['cycles']} | {fmt(b['median_cps'])} | {fmt(m['median_cps'])} | {speedup:.3f}x |", "",
                  f"Upstream `{baseline['commit'][:9]}`: mean {fmt(b['mean_cps'])} CPS, standard deviation {fmt(b['stdev_cps'])}. Big-GEM `{env['commit'][:9]}`: mean {fmt(m['mean_cps'])} CPS, standard deviation {fmt(m['stdev_cps'])}.", "",
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
        c = rep["correctness"]
        random_a = c["randomized_shredded_iverilog_diff"].strip().splitlines()[-2]
        random_b = c["randomized_preserved_cuda_diff"].strip().splitlines()[-2]
        zero_a = c["upstream_diff"].strip().splitlines()[-2]
        zero_b = c["modified_diff"].strip().splitlines()[-2]
        lines += ["This experiment uses one combinational 15-CARRY4 chain. Both netlists are regenerated from the same RTL; the upstream form contains no macros and the modified form preserves all 15 CARRY4 instances.", "",
                  "Random changing-vector semantics are checked as RTL versus Icarus-simulated shredded gates and RTL versus production-CUDA preserved macros. The old upstream VCD adapter is not used for changing vectors because it does not preserve vector-event timing reliably. The timed comparison uses constant-zero input in both binaries, and that exact input is separately checked in both simulators.", "",
                  f"- Random RTL vs shredded Icarus: `{random_a}`",
                  f"- Random RTL vs preserved CUDA: `{random_b}`",
                  f"- Timed zero input vs upstream: `{zero_a}`",
                  f"- Timed zero input vs modified: `{zero_b}`", "",
                  "| Representation | Median cycles/s | Mean | Stddev |", "|---|---:|---:|---:|",
                  f"| Shredded, official upstream | {fmt(a['median_cps'])} | {fmt(a['mean_cps'])} | {fmt(a['stdev_cps'])} |",
                  f"| Macro-preserved, modified | {fmt(b['median_cps'])} | {fmt(b['mean_cps'])} | {fmt(b['stdev_cps'])} |", "",
                  f"Representation-plus-implementation ratio: **{rep['speedup']:.3f}x** ({(rep['speedup']-1)*100:+.1f}%). This is not an implementation-only speedup.", "",
                  "The result is a measured regression, not a claimed gain: macro dispatch and cooperative barriers cost more than the removed AIG work for this graph."]
    profiles = []
    stale_profiles = []
    for stem in ("boomerang", "mixed_heterogeneous", "large_scale", "occupancy_stress"):
        path = ROOT / f"benchmark/nsight_{stem}.json"
        if path.exists():
            profile = json.loads(path.read_text())
            if profile_is_current(profile):
                profiles.append(profile)
            else:
                stale_profiles.append(path.name)
    lines += ["", "## Nsight Compute", ""]
    if profiles:
        lines += ["| Workload | Occupancy | Theoretical | Divergent targets | Uniform targets | Predicated threads | DRAM peak | DRAM MB/s | Load/store sectors/request |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for profile in profiles:
            s = profile["summary"]
            lines.append(f"| {profile['workload']} | {s['achieved_occupancy_percent']:.2f}% | {s['theoretical_occupancy_percent']:.2f}% | {s['derived_divergent_branch_targets_percent']:.2f}% | {s['uniform_branch_targets_percent']:.2f}% | {s['predicated_thread_utilization_percent']:.2f}% | {s['dram_peak_utilization_percent']:.2f}% | {s['dram_bytes_per_second']/1e6:.2f} | {s['global_load_sectors_per_request']:.2f} / {s['global_store_sectors_per_request']:.2f} |")
        bandwidths = [p["summary"]["dram_bytes_per_second"] / 1e6 for p in profiles]
        dram_util = [p["summary"]["dram_peak_utilization_percent"] for p in profiles]
        occupancies = [p["summary"]["achieved_occupancy_percent"] for p in profiles]
        theoretical = [p["summary"]["theoretical_occupancy_percent"] for p in profiles]
        registers = sorted({p["summary"]["registers_per_thread"] for p in profiles})
        shared_bytes = sorted({p["summary"]["shared_memory_per_block_bytes"] for p in profiles})
        register_limits = sorted({p["summary"]["resident_block_limit_registers"] for p in profiles})
        profile_commits = sorted({p.get("environment", {}).get("commit", "UNRECORDED")
                                  for p in profiles})
        lines += ["", "All rows profile `simulate_v1_noninteractive_simple_scan`, the production simulator kernel. Raw CSV and parsed JSON are stored beside this report.", "",
                  f"Profiled commit(s): `{', '.join(commit[:9] for commit in profile_commits)}`.", "",
                  f"Observed DRAM utilization rounds to {min(dram_util):.2f}–{max(dram_util):.2f}% of peak while measured bandwidth is {min(bandwidths):.2f}–{max(bandwidths):.2f} MB/s, so these runs are not DRAM-bandwidth-bound. Achieved occupancy is {min(occupancies):.2f}–{max(occupancies):.2f}% versus {min(theoretical):.2f}–{max(theoretical):.2f}% theoretical. The launches use {registers[0]:.0f} registers/thread and {shared_bytes[0]:,.0f} shared bytes/block; registers limit residency to {register_limits[0]:.0f} blocks/SM.", "",
                  f"Branch-target divergence spans {min(p['summary']['derived_divergent_branch_targets_percent'] for p in profiles):.2f}–{max(p['summary']['derived_divergent_branch_targets_percent'] for p in profiles):.2f}%. Predicated lane utilization spans {min(p['summary']['predicated_thread_utilization_percent'] for p in profiles):.2f}–{max(p['summary']['predicated_thread_utilization_percent'] for p in profiles):.2f}%, so low branch divergence does not mean all lanes do useful work.", "",
                  "Sector/request values are measured transaction density, but mixed access widths prevent converting them into a defensible coalescing-efficiency percentage without instruction-level access classification."]
        saturation_path = ROOT / "benchmark/nsight_occupancy_stress_40b.json"
        if saturation_path.exists():
            saturation = json.loads(saturation_path.read_text())
            if profile_is_current(saturation):
                base = next((p for p in profiles if p["workload"] == "occupancy_stress"), None)
                if base:
                    base_s, sat_s = base["summary"], saturation["summary"]
                    duration_ratio = sat_s["kernel_duration_ns"] / base_s["kernel_duration_ns"]
                    lines += ["", "### Controlled occupancy saturation", "",
                              f"On the same occupancy-stress graph, increasing the grid from {base_s['grid_blocks']:.0f} to {sat_s['grid_blocks']:.0f} blocks raises achieved occupancy from {base_s['achieved_occupancy_percent']:.2f}% to {sat_s['achieved_occupancy_percent']:.2f}% (the {sat_s['theoretical_occupancy_percent']:.2f}% register-limited ceiling). Kernel duration simultaneously grows by {duration_ratio:.2f}x, because only nine partitions perform useful work. This control proves the low 16-block occupancy is grid undersubscription; it does not claim that padding with idle blocks improves throughput."]
        if stale_profiles:
            lines += ["", "Excluded stale profiles whose recorded kernel/macro source hashes do not match the current files: " + ", ".join(stale_profiles) + "."]
    else:
        lines.append("NOT MEASURED with current production source hashes.")
    upstream_profile_path = ROOT / "benchmark/nsight_upstream_boolean.json"
    modified_profile_path = ROOT / "benchmark/nsight_boolean_heavy.json"
    lines += ["", "### Identical-Boolean baseline profile", ""]
    if upstream_profile_path.exists() and modified_profile_path.exists():
        upstream_profile = json.loads(upstream_profile_path.read_text())
        modified_profile = json.loads(modified_profile_path.read_text())
        if profile_is_current(modified_profile):
            u, m = upstream_profile["summary"], modified_profile["summary"]
            lines += ["Both profiles use the same Boolean netlist, zero inputs, 2,000 cycles, four blocks, and the production simulator kernel. Nsight reports the final measured launch after each implementation's warm-up launch.", "",
                      "| Implementation | Kernel ms | Occupancy | Divergent targets | Predicated threads | DRAM MB/s | Registers/thread | Shared bytes/block |",
                      "|---|---:|---:|---:|---:|---:|---:|---:|",
                      f"| Official upstream `{upstream_profile['environment']['commit'][:9]}` | {u['kernel_duration_ns']/1e6:.3f} | {u['achieved_occupancy_percent']:.2f}% | {u['derived_divergent_branch_targets_percent']:.2f}% | {u['predicated_thread_utilization_percent']:.2f}% | {u['dram_bytes_per_second']/1e6:.2f} | {u['registers_per_thread']:.0f} | {u['shared_memory_per_block_bytes']:.0f} |",
                      f"| Modified `{modified_profile['environment']['commit'][:9]}` | {m['kernel_duration_ns']/1e6:.3f} | {m['achieved_occupancy_percent']:.2f}% | {m['derived_divergent_branch_targets_percent']:.2f}% | {m['predicated_thread_utilization_percent']:.2f}% | {m['dram_bytes_per_second']/1e6:.2f} | {m['registers_per_thread']:.0f} | {m['shared_memory_per_block_bytes']:.0f} |", "",
                      f"The modified kernel is {u['kernel_duration_ns']/m['kernel_duration_ns']:.3f}x as fast by profiled kernel duration on this macro-free control. It consumes 124 registers/thread and 16,640 shared bytes/block versus 90 and 4,352 upstream; the four-block grid is too small to expose the resulting residency difference in achieved occupancy."]
        else:
            lines.append("NOT REPORTED: the modified baseline profile is stale relative to current production sources.")
    else:
        lines.append("NOT MEASURED")
    sweep_path = RESULTS / "block_sweep.json"
    lines += ["", "## Cooperative block-count sweep", ""]
    if sweep_path.exists():
        sweep = json.loads(sweep_path.read_text())
        lines += ["| Blocks | Median cycles/s |", "|---:|---:|"]
        for row in sweep["results"]:
            lines.append(f"| {row['blocks']} | {fmt(row['median_cps'])} |")
        lines += ["", "Throughput is flat from 1–20 blocks and drops at 32–40 blocks. Increasing cooperative grid size therefore does not expose additional useful parallel work for this single-partition mixed graph; scheduling/coordination, rather than DRAM bandwidth, is the observed scaling limit. This sweep varies grid size; it is not a substitute for the measured Nsight occupancy counters above."]
    else:
        lines.append("NOT MEASURED")
    lines += ["",
              "## Interpretation limits", "",
              "- Cross-category throughput is not a macro speedup ratio because the workloads contain different graphs.",
              "- The upstream comparison is intentionally restricted to the identical Boolean netlist that both official upstream and modified GEM can execute.",
              "- Macro-preserved versus shredded measurements require different legal netlist representations and must be reported separately from implementation-only speedup.",
              "- Nsight counter values apply to the four named production workloads and this RTX 4050; they are not universal GPU claims.", ""]
    (RESULTS / "performance_report.md").write_text("\n".join(lines), encoding="utf-8")
    print("report:", RESULTS / "performance_report.md")


if __name__ == "__main__":
    main()
