#!/usr/bin/env python3
"""Independent event-accurate references for generated Deliverable D workloads.

This module intentionally does not call the CUDA/C++ implementation.  It uses
the literal Python primitive models under verif/golden and separately
reconstructs the small amount of ordinary RTL emitted by generate_workloads.py.
"""

from pathlib import Path
import random
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "verif/golden"))

from carry4 import CARRY4  # noqa: E402
from dsp48e2 import DSP48E2  # noqa: E402
from srlc32e import SRLC32E  # noqa: E402


MASK64 = (1 << 64) - 1


def bit(value, index):
    return (value >> index) & 1


def parity(value):
    return value.bit_count() & 1


class WorkloadReference:
    def __init__(self, item):
        self.item = item
        self.name = item["name"]
        self.requested = item.get("requested", {})
        self.num_dsp = int(self.requested.get("dsp", 0))
        self.num_carry = int(self.requested.get("carry4", 0))
        self.num_srl = int(self.requested.get("srlc32e", 0))
        self.boolean_gates = int(self.requested.get("aig_target", 0))
        self.deep = bool(self.requested.get("deep", False))
        self.dsps = [DSP48E2() for _ in range(self.num_dsp)]
        self.srls = [SRLC32E() for _ in range(self.num_srl)]
        self.carry = CARRY4()
        self.occupancy_literals = None
        if self.name == "occupancy_stress":
            rng = random.Random(int(item["seed"]))
            self.occupancy_literals = [
                [(rng.randrange(64), bool(rng.randrange(2))) for _ in range(6)]
                for _ in range(int(item["result_width"]))
            ]

    def _carry_vectors(self, data):
        oo = 0
        co = 0
        previous = 0
        for index in range(self.num_carry):
            di = (data >> ((index * 3) % 61)) & 0xF
            s = (data >> ((index * 7) % 61)) & 0xF
            if index == 0:
                ci = bit(data, 0)
            elif self.deep:
                ci = previous ^ bit(data, (index + 11) % 64)
            else:
                ci = previous
            o4, co4 = self.carry.eval_comb(s, di, ci, 0)
            oo |= o4 << (4 * index)
            co |= co4 << (4 * index)
            previous = bit(co4, 3)
        return oo, co

    def _macro_boolean(self, data):
        value = parity(data)
        for index in range(self.boolean_gates):
            value = (value & bit(data, index % 64)) ^ bit(data, (index * 17 + 5) % 64)
        return value

    def _boolean_only(self, data):
        value = parity(data)
        for index in range(self.boolean_gates):
            value = ((value & bit(data, index % 64)) ^
                     (bit(data, (index * 13 + 7) % 64) &
                      bit(data, (index * 29 + 3) % 64)))
        return value

    def _occupancy_carry(self, data):
        return self.carry.eval_comb(
            (data >> 0) & 0xF,
            (data >> 4) & 0xF,
            bit(data, 8),
            bit(data, 9),
        )

    def tick(self, data):
        dsp_next = []
        for index, dsp in enumerate(self.dsps):
            dsp_next.append(dsp.eval_comb(
                data & ((1 << 27) - 1),
                (data & ((1 << 27) - 1)) ^ index,
                (data & ((1 << 18) - 1)) ^ index,
                data & ((1 << 48) - 1),
                DSP48E2.STATE_MULTIPLY,
                1,
            ))

        srl_next = []
        for index, srl in enumerate(self.srls):
            srl_d = bit(data, (index * 5 + 3) % 64)
            srl_next.append(srl.eval_next_state(srl_d, bit(data, (index + 1) % 64)))

        if self.name == "occupancy_stress":
            dsp_next = [self.dsps[0].eval_comb(
                data & ((1 << 27) - 1),
                (data >> 27) & ((1 << 27) - 1),
                data & ((1 << 18) - 1),
                data & ((1 << 48) - 1),
                DSP48E2.STATE_MULTIPLY,
                1,
            )]
            _, carry_co = self._occupancy_carry(data)
            srl_next = [self.srls[0].eval_next_state(bit(carry_co, 3), bit(data, 10))]

        for dsp, next_value in zip(self.dsps, dsp_next):
            dsp.tick(next_value)
        for srl, next_value in zip(self.srls, srl_next):
            srl.tick(next_value)

    def result(self, data):
        if self.name == "boolean_heavy":
            return self._boolean_only(data)

        if self.name == "occupancy_stress":
            dp = self.dsps[0].read_P()
            carry_o, _ = self._occupancy_carry(data)
            sq, _ = self.srls[0].eval_comb((data >> 11) & 31)
            result = 0
            for index, literals in enumerate(self.occupancy_literals):
                values = [bit(data, pos) ^ invert for pos, invert in literals]
                out = ((values[0] & values[1]) ^ (values[2] & values[3]) ^
                       (values[4] & values[5]) ^ bit(dp, index % 48) ^
                       bit(carry_o, index % 4) ^ sq)
                result |= out << index
            return result

        terms = []
        if self.boolean_gates:
            terms.append(self._macro_boolean(data))
        terms.extend(dsp.read_P() for dsp in self.dsps)

        if self.num_carry:
            oo, co = self._carry_vectors(data)
            width = self.num_carry * 4
            for offset in range(0, width, 64):
                chunk_width = min(64, width - offset)
                chunk_mask = (1 << chunk_width) - 1
                terms.append((oo >> offset) & chunk_mask)
                terms.append((co >> offset) & chunk_mask)

        if self.num_srl:
            sq = 0
            sq31 = 0
            for index, srl in enumerate(self.srls):
                q, q31 = srl.eval_comb((data >> ((index * 7) % 59)) & 31)
                sq |= q << index
                sq31 |= q31 << index
            for offset in range(0, self.num_srl, 64):
                chunk_width = min(64, self.num_srl - offset)
                chunk_mask = (1 << chunk_width) - 1
                terms.append((sq >> offset) & chunk_mask)
                terms.append((sq31 >> offset) & chunk_mask)

        result = 0
        for term in terms:
            result ^= term
        return result & MASK64


def write_reference_vcd(item, cycles, path):
    """Write input stimulus and independently calculated output to one VCD."""
    width = int(item["result_width"])
    model = WorkloadReference(item)
    prng = (int(item["seed"]) ^ 0xD1B54A32D192ED03) & MASK64
    clk = 0
    data = 0
    events = [(0, clk, data, model.result(data))]

    # Match write_stimulus_tb: one initial rising edge, followed by data at
    # negedge+2 and one rising edge for each requested stimulus cycle.
    clk = 1
    model.tick(data)
    events.append((5000, clk, data, model.result(data)))
    for cycle in range(cycles):
        clk = 0
        events.append((10000 + cycle * 10000, clk, data, model.result(data)))
        prng = (prng * 0x5851F42D4C957F2D + 0x14057B7EF767814F) & MASK64
        data = prng
        events.append((12000 + cycle * 10000, clk, data, model.result(data)))
        clk = 1
        model.tick(data)
        events.append((15000 + cycle * 10000, clk, data, model.result(data)))

    with Path(path).open("w", encoding="utf-8") as stream:
        stream.write("$timescale 1 ps $end\n")
        stream.write("$scope module tb $end\n$scope module dut $end\n")
        stream.write("$var wire 1 ! clk $end\n")
        stream.write("$var wire 64 \" data [63:0] $end\n")
        stream.write(f"$var wire {width} # result [{width - 1}:0] $end\n")
        stream.write("$upscope $end\n$upscope $end\n$enddefinitions $end\n$dumpvars\n")
        for time_ps, event_clk, event_data, event_result in events:
            stream.write(f"#{time_ps}\n{event_clk}!\n")
            stream.write(f"b{event_data:064b} \"\n")
            stream.write(f"b{event_result:0{width}b} #\n")
        stream.write("$end\n")

