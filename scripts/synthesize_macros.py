#!/usr/bin/env python3
"""Yosys 0.68/Slang frontend for GEM heterogeneous netlists."""

import argparse
import json
import pathlib
import subprocess
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[1]


def ys_quote(path):
    return '"' + str(path).replace('\\', '\\\\').replace('"', '\\"') + '"'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--top", required=True)
    parser.add_argument("--output", required=True, help="structural Verilog output")
    parser.add_argument("--json", required=True, help="Yosys JSON evidence output")
    parser.add_argument("sources", nargs="+")
    args = parser.parse_args()

    version = subprocess.check_output(["yosys", "-V"], text=True).strip()
    if not version.startswith("Yosys 0.68 "):
        raise SystemExit(f"ERROR: required Yosys 0.68, found {version}")

    resolved_sources = [pathlib.Path(s).resolve() for s in args.sources]
    if any(any(ch.isspace() for ch in str(path)) for path in resolved_sources):
        raise SystemExit("ERROR: read_slang source paths containing whitespace are unsupported")
    sources = " ".join(str(path) for path in resolved_sources)
    commands = [
        f"read_slang --std 1800-2017 --top {args.top} "
        f"-v {ROOT / 'aigpdk/aigpdk_macros_bb.v'} {sources}",
        f"hierarchy -check -top {args.top}",
        "synth -flatten",
        "delete t:$print",
        f"techmap -map {ys_quote(ROOT / 'aigpdk/dsp48e2_ps_map.v')}",
        f"dfflibmap -liberty {ys_quote(ROOT / 'aigpdk/aigpdk_nomem.lib')}",
        "opt_clean -purge",
        f"abc -liberty {ys_quote(ROOT / 'aigpdk/aigpdk_nomem.lib')}",
        "opt_clean -purge",
        "techmap",
        f"abc -liberty {ys_quote(ROOT / 'aigpdk/aigpdk_nomem.lib')}",
        "opt_clean -purge",
        f"write_json {ys_quote(pathlib.Path(args.json).resolve())}",
        f"write_verilog -noexpr -nodec {ys_quote(pathlib.Path(args.output).resolve())}",
    ]
    with tempfile.NamedTemporaryFile("w", suffix=".ys", delete=False) as script:
        script.write("\n".join(commands) + "\n")
        script_path = pathlib.Path(script.name)
    try:
        subprocess.run(["yosys", "-q", str(script_path)], cwd=ROOT, check=True)
    finally:
        script_path.unlink(missing_ok=True)

    with open(args.json, encoding="utf-8") as stream:
        netlist = json.load(stream)
    cells = netlist["modules"][args.top].get("cells", {})
    raw = [name for name, cell in cells.items() if cell["type"] == "DSP48E2"]
    if raw:
        raise SystemExit(
            "ERROR: unsupported DSP48E2 configuration was not normalized: "
            + ", ".join(raw))
    kinds = {"CARRY4": 0, "GEM_DSP48E2": 0, "SRLC32E": 0}
    for cell in cells.values():
        if cell["type"] in kinds:
            kinds[cell["type"]] += 1
    print(f"PASS: {version}; preserved/normalized macros {kinds}")


if __name__ == "__main__":
    main()
