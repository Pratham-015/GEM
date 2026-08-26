// SPDX-License-Identifier: Apache-2.0
// Native word-level macro evaluation models for GEM.
//
// This header is deliberately dependency-free and compiles BOTH as CUDA
// device code (when included from a .cu) and as plain host C++ (when
// included from a host test harness). The GPU kernel and the CPU golden
// model therefore execute *literally the same source*, which removes the
// usual class of "the reference and the kernel drifted apart" bugs.
//
// Every function here is branch-light and operates on native 64-bit
// integers, so a warp evaluating 32 instances of the same macro kind runs
// fully converged: there is no data-dependent control flow except the DSP
// opmode select, which is resolved with arithmetic predication rather than
// an if/else chain.

#ifndef GEM_MACROS_CUH
#define GEM_MACROS_CUH

#if defined(__CUDACC__)
#define GEM_MACRO_FN __device__ __forceinline__
#else
#define GEM_MACRO_FN inline
#endif

namespace gem {

typedef unsigned int       gem_u32;
typedef int                gem_i32;
typedef unsigned long long gem_u64;
typedef long long          gem_i64;

// ---------------------------------------------------------------------------
// Macro taxonomy
// ---------------------------------------------------------------------------
//
// The scheduler cares about exactly one property of a macro: whether any of
// its outputs depend combinationally on its inputs *within the same cycle*.
//
//   COMB  - the macro must be evaluated at a barrier in the middle of the
//           cycle, because downstream boolean logic consumes its outputs in
//           this same cycle. Costs one macro layer in the schedule.
//   SEQ   - every output is a register read, so downstream logic sees the
//           value the register held at the start of the cycle. The macro can
//           be evaluated once, at end of cycle, exactly like GEM's existing
//           SRAM path. Costs nothing in the schedule.
//
// Classification of the three required primitives:
//
//   CARRYCHAIN  COMB  (O and CO are pure functions of S, DI, CYINIT/CIN)
//   SRLC32E     COMB  (Q = state[A]; A is a combinational 5-bit address)
//   DSP48E2     SEQ   (only PREG is clocked, so P is a register output;
//                      the pre-adder/multiplier/ALU all collapse into the
//                      next-state function of that single register)
//
// Note the DSP being SEQ is what makes this problem tractable: the 48-bit
// datapath never appears on a combinational path, so it never constrains the
// levelized DAG at all.
enum GemMacroKind : gem_u32 {
    GEM_MACRO_CARRYCHAIN = 0u,
    GEM_MACRO_DSP48E2    = 1u,
    GEM_MACRO_SRLC32E    = 2u,
    GEM_MACRO_KIND_COUNT = 3u
};

// Maximum number of CARRY4 blocks fused into one CARRYCHAIN macro.
//
// The fused evaluation performs a single (n+1)-bit add inside a 64-bit
// register. We cap n at 60 rather than 64 so that bit n of the intermediate
// sum -- which carries C[n], the final carry-out -- is always representable.
// 60 bits is exactly 15 CARRY4 primitives, and CARRY4 chains are always a
// multiple of 4 bits wide, so nothing is wasted by this choice.
#define GEM_CARRYCHAIN_MAX_BLOCKS 15
#define GEM_CARRYCHAIN_MAX_BITS   (GEM_CARRYCHAIN_MAX_BLOCKS * 4)

// ---------------------------------------------------------------------------
// Small bit helpers
// ---------------------------------------------------------------------------

// Low-n-bit mask, safe for n in [0, 64].
GEM_MACRO_FN gem_u64 gem_mask(gem_u32 n) {
    // The shift is undefined at n == 64 on both hosts and PTX, so bias it.
    return (n >= 64u) ? ~0ull : ((1ull << n) - 1ull);
}

// Sign-extend the low w bits of v into a full 64-bit signed value.
// Branch-free: the classic (x ^ m) - m trick.
GEM_MACRO_FN gem_i64 gem_sext(gem_u64 v, gem_u32 w) {
    gem_u64 m = 1ull << (w - 1u);
    v &= gem_mask(w);
    return (gem_i64)((v ^ m) - m);
}

// ---------------------------------------------------------------------------
// A. CARRY4 / fused carry chain
// ---------------------------------------------------------------------------
//
// Xilinx CARRY4 defines, for i in 0..3:
//
//     C[0]   = CYINIT | CIN          (valid RTL drives only one of them)
//     C[i+1] = (S[i] & C[i]) | (~S[i] & DI[i])
//     O[i]   = S[i] ^ C[i]
//     CO[i]  = C[i+1]
//
// Evaluating that literally is a 4-step serial ripple, and chaining k of them
// via CO[3] -> CIN is a 4k-step ripple: exactly the dependency chain the
// problem statement calls out as the hard case.
//
// Instead we fuse the whole chain and solve it in closed form. Define
//
//     A = S | DI
//     B = ~S & DI
//
// Then for every bit position:
//   * A[i] ^ B[i] == S[i].
//       S=1 -> A=1, B=0, xor = 1 = S.
//       S=0 -> A=DI, B=DI, xor = 0 = S.
//   * majority(A[i], B[i], C[i]) == (S[i] & C[i]) | (~S[i] & DI[i]).
//       S=1 -> maj(1, 0, C) = C.
//       S=0 -> maj(DI, DI, C) = DI.
//
// Those are precisely the sum and carry rules of a binary adder. So the
// CARRY4 chain *is* the integer addition A + B + C[0], and:
//
//     tot   = A + B + C[0]
//     O     = tot                     (since tot[i] = A[i]^B[i]^C[i] = S[i]^C[i])
//     Cvec  = tot ^ A ^ B             (recovers the full carry vector C[0..n])
//     CO[i] = C[i+1] = (Cvec >> 1)[i]
//
// A 60-bit carry chain therefore costs ONE 64-bit add on the GPU ALU at graph
// depth 1, replacing ~O(n) AIG nodes at depth O(n). This is the single largest
// source of speedup in the whole design, and it also dissolves the
// macro-to-macro CO->CIN dependency inside a fused chain: there is nothing
// left to sequence.
struct CarryChainIn {
    gem_u64 s;      // per-bit S,  n bits
    gem_u64 di;     // per-bit DI, n bits
    gem_u32 cin;    // C[0] = CYINIT | CIN, already reduced by the host
    gem_u32 n;      // chain width in bits, multiple of 4, <= GEM_CARRYCHAIN_MAX_BITS
};

struct CarryChainOut {
    gem_u64 o;      // O[i]  = S[i] ^ C[i]
    gem_u64 co;     // CO[i] = C[i+1]
};

GEM_MACRO_FN CarryChainOut gem_eval_carrychain(CarryChainIn in) {
    gem_u64 m = gem_mask(in.n);
    gem_u64 s = in.s & m;
    gem_u64 di = in.di & m;

    gem_u64 a = s | di;
    gem_u64 b = (~s) & di;
    // Because n <= 60, bit n of tot is a real bit and holds C[n].
    gem_u64 tot = a + b + (gem_u64)(in.cin & 1u);

    CarryChainOut out;
    out.o = tot & m;
    gem_u64 cvec = tot ^ a ^ b;         // cvec[i] = C[i] for i in 0..n
    out.co = (cvec >> 1) & m;           // co[i]   = C[i+1]
    return out;
}

// ---------------------------------------------------------------------------
// B. DSP48E2 simplified subset
// ---------------------------------------------------------------------------
//
// Configuration fixed by the problem statement:
//   AREG = BREG = CREG = DREG = ADREG = MREG = 0   (all combinational)
//   PREG = 1                                       (only P is clocked)
//
// Datapath:
//   AD     = use_pre ? (A + D) : A          27-bit, wraps at 27 bits
//   M      = AD * B                         45-bit signed product
//   P_next = state 0 -> C
//            state 1 -> M
//            state 2 -> P + M
//   P      = P_next truncated to 48 bits
//
// Because PREG is the only register, P is read by downstream logic as a
// register output. The entire block is thus a pure next-state function and
// carries no combinational obligation -- see the SEQ note at the top.
//
// Width sanity: |AD| <= 2^26, |B| <= 2^17, so |M| <= 2^43 < 2^44. The product
// fits comfortably in 45 signed bits and therefore in a native int64_t, which
// is why no emulated multi-word arithmetic is needed anywhere on the GPU.
struct Dsp48e2In {
    gem_u64 a;        // 27 bits, raw two's complement
    gem_u64 d;        // 27 bits
    gem_u64 b;        // 18 bits
    gem_u64 c;        // 48 bits
    gem_u32 state;    // 2-bit opmode: 0 bypass, 1 mult-only, 2 mult-accumulate
    gem_u32 use_pre;  // 1 = engage pre-adder (AD = A + D), 0 = pass A
};

// Combinational product stage. Split out so that the host golden model and any
// future MREG=1 variant can reuse it.
GEM_MACRO_FN gem_i64 gem_dsp_product(Dsp48e2In in) {
    gem_i64 a = gem_sext(in.a, 27);
    gem_i64 d = gem_sext(in.d, 27);
    // Predicated rather than branched: `use_pre` is 0 or 1, so this is a
    // multiply-add the compiler folds into the datapath with no divergence.
    gem_i64 ad = gem_sext((gem_u64)(a + d * (gem_i64)(in.use_pre & 1u)), 27);
    gem_i64 b = gem_sext(in.b, 18);
    return ad * b;
}

// Next value of the clocked P register.
GEM_MACRO_FN gem_u64 gem_eval_dsp48e2_next_p(Dsp48e2In in, gem_u64 p_cur) {
    gem_i64 m = gem_dsp_product(in);

    // Branch-free opmode select. Each mask is all-ones or all-zeros, so every
    // lane in a warp executes the identical instruction stream regardless of
    // which opmode its own macro instance carries. This is what keeps a warp
    // holding a mix of bypass/multiply/MAC instances fully converged.
    gem_u32 st = in.state & 3u;
    gem_i64 sel0 = -(gem_i64)(st == 0u);
    gem_i64 sel1 = -(gem_i64)(st == 1u);
    gem_i64 sel2 = -(gem_i64)(st >= 2u);

    gem_i64 v_bypass = gem_sext(in.c, 48);
    gem_i64 v_mult   = m;
    gem_i64 v_mac    = gem_sext(p_cur, 48) + m;

    gem_i64 next = (v_bypass & sel0) | (v_mult & sel1) | (v_mac & sel2);
    return (gem_u64)next & gem_mask(48);
}

// ---------------------------------------------------------------------------
// C. SRLC32E shift register LUT
// ---------------------------------------------------------------------------
//
//   state : 32 bits, initialised to zero (INIT parsing is out of scope)
//   shift : on the global rising edge, if CE then state = (state << 1) | D
//   Q     : combinational read of state[A[4:0]]
//   Q31   : combinational read of state[31], the cascade output
//
// Q depends on the *current* state but on a *combinational* address, so this
// macro is COMB: a mid-cycle barrier is required whenever A is driven by
// logic rather than by constants or registers.

// Combinational read port. Returns bit 0 = Q, bit 1 = Q31.
GEM_MACRO_FN gem_u32 gem_eval_srlc32e_read(gem_u64 state, gem_u32 addr) {
    gem_u32 q   = (gem_u32)((state >> (addr & 31u)) & 1ull);
    gem_u32 q31 = (gem_u32)((state >> 31) & 1ull);
    return q | (q31 << 1);
}

// Clock-edge state update. Branch-free on CE so a warp with mixed enables
// stays converged.
GEM_MACRO_FN gem_u64 gem_eval_srlc32e_next(gem_u64 state, gem_u32 d, gem_u32 ce) {
    gem_u64 shifted = ((state << 1) | (gem_u64)(d & 1u)) & 0xFFFFFFFFull;
    gem_u64 keep = (gem_u64)0 - (gem_u64)(ce & 1u);   // all-ones if CE else 0
    return (shifted & keep) | (state & ~keep);
}

} // namespace gem

#endif // GEM_MACROS_CUH
