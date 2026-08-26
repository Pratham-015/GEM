"""Golden model: Xilinx SRLC32E 32-bit shift register LUT.

Primitive : SRLC32E
Variant   : Xilinx 7-series / UltraScale SRL32 with clock enable + cascade out
Config    : One 32-bit shift register. The shift itself is CLOCKED; both
            outputs are COMBINATIONAL reads of the current register contents.

            SRL register : present (32 bits), initialised to zero
            INIT string  : NOT parsed -- the problem statement puts INIT hex
                           parsing explicitly out of scope, so the register
                           always starts at 0.

Behaviour:
    on rising edge, if CE == 1:  SRL <= {SRL[30:0], D}   (shift LSB -> MSB)
    Q   = SRL[A]     combinational, dynamic 5-bit address
    Q31 = SRL[31]    combinational cascade output

Scheduling note for the later CUDA port: because Q depends on the *current*
register contents but through a *combinational* address A, this primitive is
combinational from the scheduler's point of view whenever A is driven by
logic rather than by constants or registers.
"""

from typing import Tuple

from bitops import mask


class SRLC32E:
    """One SRLC32E: 32-bit shift register with dynamic combinational read."""

    # --- explicit hardware configuration ---
    HAS_REGISTERS: bool = True
    WIDTH_SRL: int = 32
    WIDTH_A: int = 5
    INIT_VALUE: int = 0        # INIT parsing out of scope; always zero

    def __init__(self) -> None:
        # The only hardware register: the 32-bit shift chain.
        self.SRL: int = self.INIT_VALUE

    # ------------------------------------------------------------------
    # Combinational section.
    # ------------------------------------------------------------------
    def eval_comb(self, A: int) -> Tuple[int, int]:
        """Return (Q, Q31), each 1 bit, read combinationally from SRL."""
        addr = mask(A, self.WIDTH_A)
        q = mask(self.SRL >> addr, 1)
        q31 = mask(self.SRL >> (self.WIDTH_SRL - 1), 1)
        return q, q31

    def eval_next_state(self, D: int, CE: int) -> int:
        """Return the 32-bit value SRL WOULD take on the next rising edge."""
        if mask(CE, 1) == 1:
            shifted = mask((self.SRL << 1) | mask(D, 1), self.WIDTH_SRL)
            return shifted
        return mask(self.SRL, self.WIDTH_SRL)

    # ------------------------------------------------------------------
    # Clocked section. Latches only.
    # ------------------------------------------------------------------
    def tick(self, next_srl: int) -> None:
        """Rising clock edge: latch the supplied next-state into SRL."""
        self.SRL = mask(next_srl, self.WIDTH_SRL)
