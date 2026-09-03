#!/usr/bin/env python3
"""Compatibility entry point for the official Deliverable D benchmark."""

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main():
    runner = [sys.executable, str(ROOT / "benchmark/scripts/run_deliverable_d.py"), *sys.argv[1:]]
    subprocess.run(runner, cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(ROOT / "benchmark/scripts/analyze_deliverable_d.py")],
                   cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
