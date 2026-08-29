#!/usr/bin/env python3
"""Compare the golden `rdata` waveform (from Icarus, inside stim_and_golden.vcd,
at scope tb_stimulus.dut -- the DUT's own top-level output, NOT the nested
u_ram.rdata internal register) against GEM naive_sim's `gem_output.vcd`
(scope `top`, one bit-wire per rdata bit), sample-for-sample over time.
"""
import re
import sys


def parse_vcd(path, want_scope_depth=None):
    """Parse a VCD. Returns (name_of, idx_of, var_full, changes).
    Only keeps $var declarations at the shallowest scope depth encountered
    for a given name, to avoid conflating a same-named signal nested deeper
    (e.g. an internal submodule register also called `rdata`)."""
    name_of = {}
    idx_of = {}
    var_full = {}
    depth_of_name = {}   # name -> min depth seen so far
    code_for_name_depth = {}  # (name) -> chosen code at min depth

    depth = 0
    with open(path) as f:
        lines = f.readlines()

    chosen_codes = set()
    seen = {}  # name -> (depth, code, width, bitidx)
    for line in lines:
        line = line.strip()
        if line.startswith('$scope'):
            depth += 1
        elif line.startswith('$upscope'):
            depth -= 1
        elif line.startswith('$var'):
            m = re.match(r'\$var\s+\w+\s+(\d+)\s+(\S+)\s+(.+?)\s*\$end', line)
            width, code, ref = m.group(1), m.group(2), m.group(3).strip()
            width = int(width)
            bm = re.match(r'([A-Za-z_0-9]+)\[(\d+)\]$', ref)
            if bm:
                base, bidx = bm.group(1), int(bm.group(2))
            else:
                base, bidx = ref.split(' ')[0], None
            key = base if bidx is None else f"{base}[{bidx}]"
            prev = seen.get(key)
            if prev is None or depth < prev[0]:
                seen[key] = (depth, code, width, bidx)
        elif line.startswith('$enddefinitions'):
            break

    for key, (d, code, width, bidx) in seen.items():
        name_of[code] = key.split('[')[0]
        idx_of[code] = bidx
        if bidx is None:
            var_full[code] = width
        chosen_codes.add(code)

    changes = []
    cur_time = 0
    cur_vals = {}
    started = False
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith('#'):
                if started:
                    changes.append((cur_time, dict(cur_vals)))
                cur_time = int(line[1:])
                cur_vals = {}
                started = True
            elif line[0] in '01xXzZ':
                val, code = line[0], line[1:]
                if code in chosen_codes:
                    cur_vals[code] = val
            elif line[0] == 'b':
                parts = line[1:].split(' ')
                val, code = parts[0], parts[1]
                if code in chosen_codes:
                    cur_vals[code] = val
    if started:
        changes.append((cur_time, dict(cur_vals)))

    return name_of, idx_of, var_full, changes


def build_rdata_timeline(path, target_name='rdata'):
    name_of, idx_of, var_full, changes = parse_vcd(path)
    bit_codes = {}
    full_code = None
    for code, nm in name_of.items():
        if nm != target_name:
            continue
        if idx_of[code] is None:
            full_code = code
        else:
            bit_codes[idx_of[code]] = code

    state = {}
    timeline = []
    for t, vals in changes:
        changed = False
        if full_code is not None and full_code in vals:
            state['full'] = vals[full_code]
            changed = True
        for bi, code in bit_codes.items():
            if code in vals:
                state[bi] = vals[code]
                changed = True
        if not changed:
            continue
        if full_code is not None:
            raw = state.get('full')
            if raw is None or 'x' in raw or 'z' in raw:
                val = None
            else:
                val = int(raw, 2)
        else:
            width = max(bit_codes.keys()) + 1 if bit_codes else 0
            val = 0
            for bi in range(width):
                v = state.get(bi, '0')
                if v not in '01':
                    val = None
                    break
                val |= (int(v) << bi)
        timeline.append((t, val))
    return timeline


def sample_at(timeline, t):
    result = None
    for tt, v in timeline:
        if tt <= t:
            result = v
        else:
            break
    return result


golden_path = sys.argv[1]
gem_path = sys.argv[2]

golden_tl = build_rdata_timeline(golden_path)
gem_tl = build_rdata_timeline(gem_path)

print("golden rdata timeline:")
for t, v in golden_tl:
    print(f"  t={t:>7}  {'x' if v is None else hex(v)}")
print("gem rdata timeline:")
for t, v in gem_tl:
    print(f"  t={t:>7}  {'x' if v is None else hex(v)}")

sample_times = sorted(set(t for t, _ in golden_tl) | set(t for t, _ in gem_tl))

mismatches = 0
checked = 0
for t in sample_times:
    g = sample_at(golden_tl, t)
    m = sample_at(gem_tl, t)
    if g is None:
        continue
    checked += 1
    if m != g:
        mismatches += 1
        gstr = f"{g:#010x}" if g is not None else str(g)
        mstr = f"{m:#010x}" if m is not None else str(m)
        print(f"MISMATCH at t={t}: golden={gstr} gem={mstr}")

print(f"\nchecked {checked} sample points, {mismatches} mismatches")
if mismatches == 0 and checked > 0:
    print("PASS: gem_output.vcd matches golden rdata")
else:
    print("FAIL")
    sys.exit(1)
