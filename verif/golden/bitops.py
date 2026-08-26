"""Explicit fixed-width integer helpers shared by the golden models.

Every arithmetic step in the golden models is performed through these two
helpers so that no operation silently relies on Python's arbitrary-precision
integers. Each call site names the width it is working in, which makes the
models translate line-for-line into CUDA where the widths are implicit in the
C types.

CUDA mapping:
    mask(v, w)      ->  (v & ((1ull << w) - 1ull))
    to_signed(v, w) ->  ((int64_t)((v ^ (1ull << (w-1))) - (1ull << (w-1))))
"""


def mask(value: int, width: int) -> int:
    """Truncate `value` to `width` bits, returning an unsigned bit pattern."""
    return value & ((1 << width) - 1)


def to_signed(value: int, width: int) -> int:
    """Interpret the low `width` bits of `value` as two's complement."""
    value = value & ((1 << width) - 1)
    if (value >> (width - 1)) & 1:
        return value - (1 << width)
    return value
