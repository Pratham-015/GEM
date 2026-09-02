#!/usr/bin/env python3
"""Compare PS-faithful RTL and GEM VCD outputs at GEM sample timestamps."""
import argparse
import re
import sys

DEFAULT_TARGETS = {"sum": 64, "carry": 64, "p": 48, "q": 1, "q31": 1, "glue": 1}
TARGETS = DEFAULT_TARGETS


def parse(path):
    codes = {}
    scope = []
    values = {}
    snapshots = []
    time = 0
    with open(path, encoding="utf-8") as f:
        lines = list(f)
    for line in lines:
        s = line.strip()
        if s.startswith("$scope"):
            scope.append(s.split()[2])
        elif s.startswith("$upscope"):
            scope.pop()
        elif s.startswith("$var"):
            m = re.match(r"\$var\s+\w+\s+(\d+)\s+(\S+)\s+(.+?)\s+\$end", s)
            if not m:
                continue
            width, code, ref = int(m.group(1)), m.group(2), m.group(3)
            bm = re.match(r"(\w+)\[(\d+)\]$", ref)
            name, bit = (bm.group(1), int(bm.group(2))) if bm else (ref.split()[0], None)
            if name in TARGETS and ("dut" in scope or "gem_top_module" in scope):
                codes[code] = (name, bit, width)
        elif s.startswith("$enddefinitions"):
            break
    started = False
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            if started:
                snapshots.append((time, dict(values)))
            time = int(s[1:])
            started = True
        elif s[0] in "01xXzZ" and s[1:] in codes:
            values[s[1:]] = s[0].lower()
        elif s[0] == "b":
            raw, code = s[1:].split()
            if code in codes:
                values[code] = raw.lower()
    if started:
        snapshots.append((time, dict(values)))
    return codes, snapshots


def materialize(codes, state):
    result = {}
    for target, width in TARGETS.items():
        bits = ["x"] * width
        for code, (name, bit, declared_width) in codes.items():
            if name != target or code not in state:
                continue
            raw = state[code]
            if bit is None:
                raw = raw.rjust(declared_width, "0")
                bits[:declared_width] = reversed(raw[-declared_width:])
            else:
                bits[bit] = raw[-1]
        result[target] = None if any(b not in "01" for b in bits) else sum(
            (b == "1") << i for i, b in enumerate(bits))
    return result


def timeline(path):
    codes, snaps = parse(path)
    return [(t, materialize(codes, state)) for t, state in snaps]


def sample(tl, t):
    value = None
    for tt, state in tl:
        if tt > t:
            break
        value = state
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("golden")
    parser.add_argument("gem")
    parser.add_argument(
        "--signals",
        help="comma-separated output names and widths, e.g. p0:48,o:4,q:1",
    )
    args = parser.parse_args()
    global TARGETS
    if args.signals:
        TARGETS = {}
        for item in args.signals.split(","):
            name, width = item.rsplit(":", 1)
            TARGETS[name] = int(width)
        if not TARGETS or any(width <= 0 for width in TARGETS.values()):
            parser.error("--signals must contain positive name:width entries")

    golden, gem = timeline(args.golden), timeline(args.gem)
    mismatches = []
    checked = 0
    all_timestamps = sorted(set(t for t, _ in golden) | set(t for t, _ in gem))
    for t in all_timestamps:
        expected = sample(golden, t)
        got = sample(gem, t)
        if expected is None or got is None:
            continue
        for name in TARGETS:
            if expected[name] is None or got[name] is None:
                continue
            checked += 1
            if got[name] != expected[name]:
                mismatches.append((t, name, expected[name], got[name]))
    for row in mismatches[:30]:
        print("MISMATCH t=%d %s expected=%s got=%s" % row)
    print(f"checked={checked} mismatches={len(mismatches)}")
    if checked == 0 or mismatches:
        return 1
    print("PASS: integrated CPU RTL and GEM CUDA outputs match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
