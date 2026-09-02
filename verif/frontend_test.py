#!/usr/bin/env python3
"""Hostile Yosys 0.68/Slang frontend and DSP normalization checks."""

import pathlib
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]


def run(source, top, stem):
    return subprocess.run([
        sys.executable, "scripts/synthesize_macros.py", "--top", top,
        "--output", f"/tmp/{stem}.gv", "--json", f"/tmp/{stem}.json", source,
    ], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def main():
    sv = run("verif/rtl/test_designs/sv2012_frontend.sv",
             "sv2012_frontend", "gem_sv2012")
    print(sv.stdout, end="")
    if sv.returncode:
        return 1

    bad = run("verif/rtl/test_designs/invalid_dsp_config.sv",
              "invalid_dsp_config", "gem_invalid_dsp")
    if bad.returncode == 0 or "unsupported DSP48E2 configuration" not in bad.stdout:
        print("FAIL: invalid AREG=1 DSP configuration was not rejected")
        print(bad.stdout)
        return 1
    print("PASS: invalid DSP48E2 pipeline configuration rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
