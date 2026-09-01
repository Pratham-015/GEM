#!/usr/bin/env python3
"""
test2/golden_reference.py
Cycle-accurate software golden reference model for mixed_circuit.sv.
Computes expected mathematical outputs cycle-by-cycle for reference verification.
"""

import sys

def simulate_step(clk, rst, op_a, op_b, cin, dsp_a, dsp_b, dsp_c, dsp_d, dsp_state, dsp_use_pre, srl_d, srl_ce, srl_addr, srl_state_reg, dsp_p_reg, reg_sum_prev):
    # 1. CARRY4 Logic
    # S = op_a ^ op_b, DI = op_a & op_b
    s_wire = (op_a ^ op_b) & 0xF
    di_wire = (op_a & op_b) & 0xF
    
    # 4-bit addition
    tot = op_a + op_b + (cin & 1)
    carry_sum = tot & 0xF
    carry_co_3 = (tot >> 4) & 1
    
    # 2. DSP48E2 Logic
    # Sign extend
    def sext(v, w):
        m = 1 << (w - 1)
        v = v & ((1 << w) - 1)
        return (v ^ m) - m

    a_s = sext(dsp_a, 27)
    d_s = sext(dsp_d, 27)
    ad_s = sext(a_s + d_s if dsp_use_pre else a_s, 27)
    b_s = sext(dsp_b, 18)
    m_prod = ad_s * b_s

    if dsp_state == 0:
        p_next = sext(dsp_c, 48)
    elif dsp_state == 1:
        p_next = m_prod
    elif dsp_state == 2:
        p_next = sext(dsp_p_reg, 48) + m_prod
    else:
        p_next = 0
    p_next = p_next & ((1 << 48) - 1)

    # 3. SRLC32E Logic
    srl_q = (srl_state_reg >> (srl_addr & 31)) & 1
    srl_q31 = (srl_state_reg >> 31) & 1
    if srl_ce:
        srl_next_state = ((srl_state_reg << 1) | (srl_d & 1)) & 0xFFFFFFFF
    else:
        srl_next_state = srl_state_reg

    # 4. DFF Registered Sum
    if rst:
        reg_sum_next = 0
    else:
        reg_sum_next = carry_sum

    # 5. Status Flag
    p_sign = (dsp_p_reg >> 47) & 1
    status_flag = ((carry_co_3 ^ p_sign) | (srl_q & (1 - srl_q31))) & 1

    return {
        "carry_sum": carry_sum,
        "carry_co_3": carry_co_3,
        "dsp_p": p_next,
        "srl_q": srl_q,
        "srl_q31": srl_q31,
        "registered_sum": reg_sum_next,
        "status_flag": status_flag,
        "srl_state_next": srl_next_state
    }

def main():
    print("  GOLDEN REFERENCE SIMULATION (test2/mixed_circuit.sv)")
    print("  Computing cycle-accurate expected values across CARRY4, DSP48E2, SRLC32E, and DFFs")

    dsp_p_reg = 0
    srl_state_reg = 0
    reg_sum = 0

    test_vectors = [
        # (cycle, rst, op_a, op_b, cin, dsp_a, dsp_b, dsp_c, dsp_d, state, use_pre, srl_d, srl_ce, srl_addr)
        (1, 1, 5, 3, 0, 10, 20, 0, 0, 1, 0, 1, 1, 0),    # Mult: 10*20 = 200, shift '1' in
        (2, 0, 7, 8, 1, 5, 10, 0, 0, 2, 0, 1, 1, 1),     # MAC: 200 + 50 = 250, read addr 1
        (3, 0, 15, 1, 0, 2, 3, 0, 4, 1, 1, 0, 1, 0),     # Pre-add: (2+4)*3 = 18, shift '0'
        (4, 0, 9, 6, 1, 0, 0, 12345, 0, 0, 0, 1, 1, 2),  # Bypass: C = 12345, read addr 2
    ]

    all_pass = True
    for vec in test_vectors:
        cyc, rst, op_a, op_b, cin, dsp_a, dsp_b, dsp_c, dsp_d, state, use_pre, srl_d, srl_ce, srl_addr = vec
        res = simulate_step(1, rst, op_a, op_b, cin, dsp_a, dsp_b, dsp_c, dsp_d, state, use_pre, srl_d, srl_ce, srl_addr, srl_state_reg, dsp_p_reg, reg_sum)
        
        print(f"Cycle {cyc}:")
        print(f"  CARRY4 Sum: {res['carry_sum']} (CO[3]={res['carry_co_3']}), Registered Sum: {res['registered_sum']}")
        print(f"  DSP48E2 P : {res['dsp_p']}")
        print(f"  SRLC32E Q : {res['srl_q']} (Q31={res['srl_q31']})")
        print(f"  Status Flag: {res['status_flag']}")

        # State updates for next cycle
        dsp_p_reg = res["dsp_p"]
        srl_state_reg = res["srl_state_next"]
        reg_sum = res["registered_sum"]

    print("  VERDICT: [PASS] Golden reference values successfully computed!")

if __name__ == "__main__":
    main()
