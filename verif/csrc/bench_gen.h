// SPDX-License-Identifier: Apache-2.0
// Shared, deterministic instance generator for bench_cpu.cpp / bench_gpu.cu.
//
// Both binaries include this and call gen_instances() with the same seed,
// so they operate on byte-identical stimulus without needing a shared
// runtime or an intermediate stimulus file -- std::mt19937_64 is a
// standard-specified deterministic algorithm, so the two independently
// -compiled (g++ vs nvcc host-side) programs produce the same sequence.
#ifndef GEM_BENCH_GEN_H
#define GEM_BENCH_GEN_H

#include <cstdint>
#include <random>
#include <vector>

#include "gem_macros.cuh"

static const int GEM_BENCH_CYCLES_PER_INSTANCE = 8;
static const uint64_t GEM_BENCH_SEED = 20260828ull;

struct ChainInst { gem::gem_u64 s, di; gem::gem_u32 cin; };
struct DspInst    { gem::gem_u64 a, d, b, c; gem::gem_u32 state, use_pre; };
struct SrlInst    { gem::gem_u32 d, ce, a; };

// Plain host helper, deliberately NOT gem::gem_mask: that function is
// __device__-only when this header is included from a .cu under nvcc, and
// generation is not part of what's being tested, just what's being fed in.
static inline uint64_t bench_mask(uint32_t w) {
    return (w >= 64u) ? ~0ull : ((1ull << w) - 1ull);
}

inline void gen_instances(uint32_t n,
                           std::vector<ChainInst> &chain_in,
                           std::vector<DspInst> &dsp_in,
                           std::vector<SrlInst> &srl_in) {
    std::mt19937_64 rng(GEM_BENCH_SEED);
    chain_in.resize(n); dsp_in.resize(n); srl_in.resize(n);
    uint64_t chain_mask = bench_mask(GEM_CARRYCHAIN_MAX_BITS);
    for (uint32_t i = 0; i < n; i++) {
        chain_in[i] = ChainInst{rng() & chain_mask, rng() & chain_mask,
                                 (gem::gem_u32)(rng() & 1)};
        dsp_in[i] = DspInst{rng() & bench_mask(27), rng() & bench_mask(27),
                             rng() & bench_mask(18), rng() & bench_mask(48),
                             (gem::gem_u32)(rng() % 3), (gem::gem_u32)(rng() & 1)};
        srl_in[i] = SrlInst{(gem::gem_u32)(rng() & 1), (gem::gem_u32)(rng() & 1),
                             (gem::gem_u32)(rng() % 32)};
    }
}

#endif // GEM_BENCH_GEN_H
