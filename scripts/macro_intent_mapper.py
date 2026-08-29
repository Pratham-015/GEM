#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Macro Intent Mapper: Pre-processor for Xilinx DSP48E2 and hardware macros.

Extracts hardware intent from full-featured Xilinx DSP48E2 instantiations
(OPMODE, INMODE, ALUMODE) and converts them into the GEM simplified subset:
  - 2-bit STATE:
      0: Bypass (P_next = C)
      1: Multiply-Only (P_next = M)
      2: Multiply-Accumulate (P_next = P_current + M)
  - 1-bit USE_PRE:
      0: Pass A directly (AD = A)
      1: Enable Pre-Adder (AD = A + D)

Usage:
  python3 scripts/macro_intent_mapper.py input_netlist.v -o preprocessed_netlist.v
"""

import argparse
import re
import sys


def decode_opmode_to_state(opmode_val: int) -> int:
    """Map 9-bit Xilinx OPMODE to simplified 2-bit state."""
    # OPMODE[1:0] selects X mux (01 = M product)
    # OPMODE[3:2] selects Y mux (01 = M product)
    # OPMODE[6:4] selects Z mux (011 = C, 010 = P feedback, 000 = 0)
    z_mux = (opmode_val >> 4) & 0x7
    xy_mult = ((opmode_val & 0x3) == 0x1) and (((opmode_val >> 2) & 0x3) == 0x1)

    if z_mux == 0x3 and not xy_mult:
        return 0  # Bypass (P <= C)
    elif z_mux == 0x0 and xy_mult:
        return 1  # Multiply-Only (P <= M)
    elif z_mux == 0x2 and xy_mult:
        return 2  # MAC (P <= P + M)
    else:
        # Default fallback heuristic based on multiplier / accumulator presence
        if xy_mult and z_mux != 0:
            return 2
        elif xy_mult:
            return 1
        return 0


def decode_inmode_to_use_pre(inmode_val: int) -> int:
    """Map 5-bit Xilinx INMODE to simplified 1-bit USE_PRE."""
    # INMODE[2] enables D in pre-adder (AD = A + D)
    return (inmode_val >> 2) & 1


def transform_dsp_instance(match: re.Match) -> str:
    """Transform full DSP48E2 instantiation text into simplified DSP48E2."""
    full_inst = match.group(0)
    inst_name = match.group(1)
    port_block = match.group(2)

    # Extract OPMODE / INMODE if statically assigned
    opmode_match = re.search(r'\.OPMODE\s*\(\s*9\'(?:b([01]+)|h([0-9a-fA-F]+)|d(\d+))\s*\)', port_block)
    inmode_match = re.search(r'\.INMODE\s*\(\s*5\'(?:b([01]+)|h([0-9a-fA-F]+)|d(\d+))\s*\)', port_block)

    state_val = 1  # Default to multiply-only if unspecified
    use_pre_val = 0

    if opmode_match:
        if opmode_match.group(1):
            opmode_int = int(opmode_match.group(1), 2)
        elif opmode_match.group(2):
            opmode_int = int(opmode_match.group(2), 16)
        else:
            opmode_int = int(opmode_match.group(3), 10)
        state_val = decode_opmode_to_state(opmode_int)

    if inmode_match:
        if inmode_match.group(1):
            inmode_int = int(inmode_match.group(1), 2)
        elif inmode_match.group(2):
            inmode_int = int(inmode_match.group(2), 16)
        else:
            inmode_int = int(inmode_match.group(3), 10)
        use_pre_val = decode_inmode_to_use_pre(inmode_int)

    # Reconstruct port mappings preserving A, B, C, D, CLK, P
    ports = {}
    for p_match in re.finditer(r'\.(\w+)\s*\(([^)]*)\)', port_block):
        pname = p_match.group(1)
        pconn = p_match.group(2).strip()
        ports[pname] = pconn

    # Check if STATE / USE_PRE were already explicitly connected
    state_conn = ports.get("STATE", f"2'd{state_val}")
    use_pre_conn = ports.get("USE_PRE", f"1'b{use_pre_val}")

    simplified_ports = [
        f".CLK({ports.get('CLK', '1\'b0')})",
        f".USE_PRE({use_pre_conn})",
        f".STATE({state_conn})",
        f".A({ports.get('A', '27\'d0')})",
        f".B({ports.get('B', '18\'d0')})",
        f".C({ports.get('C', '48\'d0')})",
        f".D({ports.get('D', '27\'d0')})",
        f".P({ports.get('P', '')})"
    ]

    return f"DSP48E2 {inst_name} (\n  " + ",\n  ".join(simplified_ports) + "\n);"


def preprocess_netlist(content: str) -> str:
    """Replace complex DSP48E2 instances with simplified DSP48E2 instances."""
    pattern = re.compile(r'DSP48E2\s+(?:#\s*\([^)]*\)\s+)?(\w+)\s*\((.*?)\);', re.DOTALL)
    return pattern.sub(transform_dsp_instance, content)


def main():
    parser = argparse.ArgumentParser(description="Pre-process netlists to extract macro intent for GEM.")
    parser.add_argument("input", help="Input SystemVerilog / Verilog file")
    parser.add_argument("-o", "--output", help="Output file (default stdout)", default=None)
    args = parser.parse_args()

    with open(args.input, "r") as f:
        src = f.read()

    processed = preprocess_netlist(src)

    if args.output:
        with open(args.output, "w") as f:
            f.write(processed)
        print(f"Preprocessed netlist written to {args.output}")
    else:
        sys.stdout.write(processed)


if __name__ == "__main__":
    main()

