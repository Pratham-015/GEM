"""Golden model: Xilinx CARRY4 fast carry chain primitive.

Primitive : CARRY4
Variant   : Xilinx 7-series / UltraScale carry logic block
Config    : PURELY COMBINATIONAL. This primitive contains no registers of any
            kind, therefore this class deliberately has NO tick() method and
            NO instance state. That is a statement about the hardware, not an
            omission -- see `HAS_REGISTERS` below.

Equations implemented verbatim from the problem statement:

    C[0]   = CYINIT | CIN          (valid RTL drives only one of the two)
    C[i+1] = (S[i] & C[i]) | (~S[i] & DI[i])     for i in 0..3
    O[i]   = S[i] ^ C[i]                          for i in 0..3
    CO[i]  = C[i+1]                               for i in 0..3

This module intentionally implements the LITERAL four-step ripple. It is the
reference against which the optimised fused-chain form (see
`eval_carry_chain_fused` below) is validated, so the two must not share an
implementation strategy -- otherwise the comparison proves nothing.
"""

from typing import Tuple

from bitops import mask

# Chain-fusion limit for the optimised form. A fused chain performs one
# (n+1)-bit addition inside a 64-bit register; capping n at 60 keeps bit n --
# which carries C[n], the final carry-out -- always representable. 60 bits is
# exactly 15 CARRY4 blocks, and chains are always a multiple of 4 bits wide.
CARRYCHAIN_MAX_BLOCKS: int = 15
CARRYCHAIN_MAX_BITS: int = CARRYCHAIN_MAX_BLOCKS * 4


class CARRY4:
    """One CARRY4 slice: 4-bit S/DI in, 4-bit O/CO out."""

    # --- explicit hardware configuration -------------------------------
    HAS_REGISTERS: bool = False   # no tick(): every output is combinational
    WIDTH_S: int = 4
    WIDTH_DI: int = 4
    WIDTH_O: int = 4
    WIDTH_CO: int = 4

    def __init__(self) -> None:
        # No hardware registers exist in CARRY4, so there is no state to hold.
        pass

    def eval_comb(self, S: int, DI: int, CIN: int, CYINIT: int) -> Tuple[int, int]:
        """Combinational evaluation. Returns (O, CO), each 4 bits.

        Written as an explicit loop with one-bit temporaries so it maps
        directly onto a CUDA thread body.
        """
        S = mask(S, self.WIDTH_S)
        DI = mask(DI, self.WIDTH_DI)
        CIN = mask(CIN, 1)
        CYINIT = mask(CYINIT, 1)

        c = mask(CYINIT | CIN, 1)          # C[0]

        o_out = 0
        co_out = 0
        i = 0
        while i < 4:
            s_i = mask(S >> i, 1)
            di_i = mask(DI >> i, 1)

            o_i = mask(s_i ^ c, 1)                              # O[i]
            c_next = mask((s_i & c) | ((mask(~s_i, 1)) & di_i), 1)  # C[i+1]

            o_out = mask(o_out | (o_i << i), self.WIDTH_O)
            co_out = mask(co_out | (c_next << i), self.WIDTH_CO)

            c = c_next
            i = i + 1

        return o_out, co_out


def eval_carry_chain_ripple(S: int, DI: int, CYINIT: int, n: int) -> Tuple[int, int]:
    """Reference: an n-bit chain built from literal CARRY4 slices.

    Models `n // 4` CARRY4 blocks cascaded CO[3] -> CIN, which is what a
    synthesiser emits for a wide adder. Returns (O, CO), each n bits.
    """
    slice_model = CARRY4()
    o_total = 0
    co_total = 0
    carry = mask(CYINIT, 1)

    blk = 0
    num_blocks = n // 4
    while blk < num_blocks:
        s_blk = mask(S >> (blk * 4), 4)
        di_blk = mask(DI >> (blk * 4), 4)

        # Block 0 receives the chain initialiser on CYINIT; every later block
        # receives the previous block's CO[3] on CIN. Only one is ever active.
        if blk == 0:
            o_blk, co_blk = slice_model.eval_comb(s_blk, di_blk, 0, carry)
        else:
            o_blk, co_blk = slice_model.eval_comb(s_blk, di_blk, carry, 0)

        o_total = mask(o_total | (o_blk << (blk * 4)), n)
        co_total = mask(co_total | (co_blk << (blk * 4)), n)
        carry = mask(co_blk >> 3, 1)
        blk = blk + 1

    return o_total, co_total


def eval_carry_chain_fused(S: int, DI: int, CYINIT: int, n: int) -> Tuple[int, int]:
    """OPTIMISED form destined for the CUDA kernel -- one native add.

    NOT the golden reference. This exists so the differential harness can
    prove it equals `eval_carry_chain_ripple` before any CUDA porting starts.

    Derivation. With A = S | DI and B = ~S & DI, at every bit position:
        A[i] ^ B[i] == S[i]
            S=1 -> A=1, B=0, xor = 1 = S
            S=0 -> A=DI, B=DI, xor = 0 = S
        majority(A[i], B[i], C[i]) == (S[i] & C[i]) | (~S[i] & DI[i])
            S=1 -> maj(1, 0, C) = C
            S=0 -> maj(DI, DI, C) = DI
    Those are exactly the sum and carry rules of binary addition, so the whole
    chain collapses to the integer sum A + B + C[0]:
        tot   = A + B + C[0]
        O     = tot                  (tot[i] = A[i]^B[i]^C[i] = S[i]^C[i])
        Cvec  = tot ^ A ^ B          (recovers the carry vector C[0..n])
        CO[i] = C[i+1] = (Cvec >> 1)[i]
    """
    if n > CARRYCHAIN_MAX_BITS:
        raise ValueError("fused chain limited to %d bits" % CARRYCHAIN_MAX_BITS)

    S = mask(S, n)
    DI = mask(DI, n)

    a = mask(S | DI, n)
    b = mask(mask(~S, n) & DI, n)

    # Computed in n+1 bits so that bit n (which holds C[n]) survives.
    tot = mask(a + b + mask(CYINIT, 1), n + 1)

    o_out = mask(tot, n)
    cvec = mask(tot ^ a ^ b, n + 1)        # cvec[i] = C[i]
    co_out = mask(cvec >> 1, n)            # co[i]   = C[i+1]
    return o_out, co_out
