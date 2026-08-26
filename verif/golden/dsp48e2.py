"""Golden model: Xilinx DSP48E2 slice, simplified subset.

Primitive : DSP48E2   (NOT DSP48E1 -- the problem statement names E2 explicitly)
Variant   : UltraScale / UltraScale+ DSP48E2
Config    : PREG = 1, every other pipeline register bypassed.

            AREG = BREG = CREG = DREG = ADREG = MREG = 0
            PREG = 1

            This is stated as explicit class constants below rather than being
            implied by absent code: a reader must be able to see "only P is
            registered" directly, not infer it from what is missing.

Datapath (all signed two's complement):

    AD     = A + D   if use_pre else A          27-bit, wraps at 27 bits
    M      = AD * B                             45-bit product
    P_next = state 0 -> C                       bypass
             state 1 -> M                       multiply only
             state 2 -> P + M                   multiply-accumulate
    P      <= P_next on the rising clock edge   48-bit

OPMODE / ALUMODE note: the real DSP48E2 selects its datapath with a 9-bit
OPMODE plus a 4-bit ALUMODE. The problem statement explicitly replaces both
with a simplified 2-bit `state` input supplied per instance by the Yosys
front-end, so this model takes `state` as a runtime input rather than a fixed
parameter. The three legal values are enumerated in STATE_* below.

Width sanity: |AD| <= 2^26 and |B| <= 2^17, so |M| <= 2^43 < 2^44. The product
fits in 45 signed bits and therefore in a native int64_t on the GPU -- no
multi-word arithmetic is ever required.

Output pins: OVERFLOW and UNDERFLOW are explicitly out of scope; only the
core 48-bit P output is modelled.
"""

from bitops import mask, to_signed


class DSP48E2:
    """One DSP48E2 slice with only the P register active."""

    # --- pipeline register configuration (0 = bypassed, 1 = registered) ---
    AREG: int = 0
    BREG: int = 0
    CREG: int = 0
    DREG: int = 0
    ADREG: int = 0
    MREG: int = 0
    PREG: int = 1          # the ONLY registered stage in this configuration

    # --- port widths ---
    WIDTH_A: int = 27
    WIDTH_D: int = 27
    WIDTH_B: int = 18
    WIDTH_C: int = 48
    WIDTH_AD: int = 27
    WIDTH_M: int = 45
    WIDTH_P: int = 48

    # --- simplified opmode encoding (replaces 9-bit OPMODE + 4-bit ALUMODE) ---
    STATE_BYPASS: int = 0          # P_next = C
    STATE_MULTIPLY: int = 1        # P_next = M
    STATE_MAC: int = 2             # P_next = P + M

    def __init__(self) -> None:
        # The one and only hardware register in this configuration.
        # Initialised to zero per the problem statement's initialisation rule.
        self.P: int = 0

    # ------------------------------------------------------------------
    # Combinational section. Computes, but never latches.
    # ------------------------------------------------------------------
    def eval_pre_adder(self, A: int, D: int, use_pre: int) -> int:
        """AD = A + D (or A). Result wraps to 27 bits, returned unsigned."""
        a_s = to_signed(A, self.WIDTH_A)
        if mask(use_pre, 1) == 1:
            d_s = to_signed(D, self.WIDTH_D)
            return mask(a_s + d_s, self.WIDTH_AD)
        return mask(a_s, self.WIDTH_AD)

    def eval_multiplier(self, AD: int, B: int) -> int:
        """M = AD * B. Returns the 45-bit product as an unsigned pattern."""
        ad_s = to_signed(AD, self.WIDTH_AD)
        b_s = to_signed(B, self.WIDTH_B)
        return mask(ad_s * b_s, self.WIDTH_M)

    def eval_comb(self, A: int, D: int, B: int, C: int,
                  state: int, use_pre: int) -> int:
        """Return P_next: the 48-bit value the P register WOULD latch now.

        Reads self.P because the accumulator path feeds the register output
        back into the ALU -- that is a real hardware path, not hidden state.
        Performs no latching; call tick() to commit.
        """
        ad = self.eval_pre_adder(A, D, use_pre)
        m = self.eval_multiplier(ad, B)
        m_s = to_signed(m, self.WIDTH_M)

        state = mask(state, 2)
        if state == self.STATE_BYPASS:
            p_next = mask(to_signed(C, self.WIDTH_C), self.WIDTH_P)
        elif state == self.STATE_MULTIPLY:
            p_next = mask(m_s, self.WIDTH_P)
        else:
            # STATE_MAC (2). State 3 is not defined by the spec; it is folded
            # into the accumulate path so the model is total over 2 bits.
            p_cur_s = to_signed(self.P, self.WIDTH_P)
            p_next = mask(p_cur_s + m_s, self.WIDTH_P)
        return p_next

    # ------------------------------------------------------------------
    # Clocked section. Latches only; computes nothing.
    # ------------------------------------------------------------------
    def tick(self, p_next: int) -> None:
        """Rising clock edge: latch the supplied combinational result into P.

        Deliberately takes p_next as an argument rather than recomputing it,
        so that this method contains no combinational logic whatsoever.
        """
        self.P = mask(p_next, self.WIDTH_P)

    # ------------------------------------------------------------------
    def read_P(self) -> int:
        """The 48-bit registered output, as an unsigned bit pattern."""
        return mask(self.P, self.WIDTH_P)
