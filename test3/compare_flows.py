import re
import sys
import os

BASELINE_GV = "test3/flowA_baseline_flatten_gatelevel.gv"
PRESERVE_GV = "test3/flowB_macropreserve_gatelevel.gv"
MACROS = ["CARRY4", "DSP48E2", "SRLC32E"]

def count_cells(filepath):
    counts = {}
    with open(filepath) as f:
        for line in f:
            m = re.match(r'\s+(\w+)\s+\w+\s+\(', line)
            if m:
                cell = m.group(1)
                counts[cell] = counts.get(cell, 0) + 1
    return counts

def has_macro(filepath, macro_name):
    with open(filepath) as f:
        content = f.read()
    return bool(re.search(r'\b' + macro_name + r'\b', content))

def count_macro_instances(filepath, macro_name):
    count = 0
    with open(filepath) as f:
        for line in f:
            m = re.match(r'\s+' + macro_name + r'\s+\w+\s+\(', line)
            if m:
                count += 1
    return count

def print_cell_table(label, counts):
    print(f"\n  {label}")
    print(f"  {'Cell Type':<24} {'Count':>8}")
    macro_cells = {k: v for k, v in sorted(counts.items()) if k in MACROS}
    aig_cells   = {k: v for k, v in sorted(counts.items()) if k not in MACROS}
    if macro_cells:
        for cell, n in sorted(macro_cells.items()):
            print(f"  {'>> ' + cell:<24} {n:>8}   [MACRO]")
    for cell, n in sorted(aig_cells.items()):
        print(f"  {cell:<24} {n:>8}")
    total = sum(counts.values())
    print(f"  {'TOTAL':<24} {total:>8}")
    return total

def main():
    print("  GEM TEST 3 — Comprehensive Macro Preservation Verification")
    
    for path in [BASELINE_GV, PRESERVE_GV]:
        if not os.path.exists(path):
            print(f"\n  [ERROR] File not found: {path}")
            sys.exit(1)

    base_cells = count_cells(BASELINE_GV)
    pres_cells = count_cells(PRESERVE_GV)
    base_total = print_cell_table("FLOW A — Original GEM (ALL MACROS SHREDDED)", base_cells)
    pres_total = print_cell_table("FLOW B — Modified GEM (ALL MACROS PRESERVED)", pres_cells)

    print("\n  PER-MACRO PRESERVATION CHECK")
    all_macros_pass = True
    for macro in MACROS:
        base_has  = has_macro(BASELINE_GV, macro)
        pres_has  = has_macro(PRESERVE_GV, macro)
        pres_count = count_macro_instances(PRESERVE_GV, macro)
        base_status = "ABSENT" if not base_has else "PRESENT"
        pres_status = f"PRESENT x {pres_count}" if pres_has else "ABSENT"
        print(f"  {macro}: Base={base_status}, Pres={pres_status}")
        if base_has or not pres_has:
            all_macros_pass = False

    print("\n  GATE COUNT COMPARISON")
    pres_macro_count = sum(pres_cells.get(m, 0) for m in MACROS)
    pres_aig_only    = pres_total - pres_macro_count
    saved = base_total - pres_total
    pct = saved / base_total * 100 if base_total > 0 else 0
    print(f"  Saved: {saved} ({pct:.1f}% reduction)")

    print("\n  VERDICT")
    if all_macros_pass:
        print("  [PASS] ALL THREE MACROS CONFIRMED PRESERVED")
    else:
        print("  [FAIL] Not all macros passed the preservation check.")
    return 0 if all_macros_pass else 1

if __name__ == "__main__":
    sys.exit(main())
