// SPDX-License-Identifier: Apache-2.0
// CPU-side half of the gem_macros.cuh timing baseline. Compiled with a
// plain host compiler (no nvcc, no __CUDACC__), so gem_macros.cuh's
// GEM_MACRO_FN resolves to ordinary `inline` here -- this is genuinely the
// same source running on the CPU, not a reimplementation.
//
// Writes results to bench_out/cpu_*.txt in the same layout bench_gpu.cu
// writes gpu_*.txt, so a wrapper can diff them for correctness, and prints
// wall-clock timing to stdout. See bench_gen.h for why both binaries see
// identical input despite not sharing a stimulus file.
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <vector>

#include "bench_gen.h"
#include "gem_macros.cuh"

using namespace gem;
using Clock = std::chrono::steady_clock;
static double ms_since(Clock::time_point t0) {
    return std::chrono::duration<double, std::milli>(Clock::now() - t0).count();
}

static FILE *open_or_die(const char *path, const char *mode) {
    FILE *f = fopen(path, mode);
    if (!f) { fprintf(stderr, "cannot open %s\n", path); exit(1); }
    return f;
}

int main(int argc, char **argv) {
    if (argc != 3) {
        fprintf(stderr, "usage: %s <n_instances> <out_dir>\n", argv[0]);
        return 1;
    }
    uint32_t n = (uint32_t)atoll(argv[1]);
    const char *out_dir = argv[2];

    std::vector<ChainInst> chain_in;
    std::vector<DspInst> dsp_in;
    std::vector<SrlInst> srl_in;
    gen_instances(n, chain_in, dsp_in, srl_in);

    char path[4096];

    // --- CARRYCHAIN ---
    std::vector<gem_u64> chain_o(n), chain_co(n);
    auto t0 = Clock::now();
    for (uint32_t i = 0; i < n; i++) {
        CarryChainIn ci{chain_in[i].s, chain_in[i].di, chain_in[i].cin,
                         GEM_CARRYCHAIN_MAX_BITS};
        CarryChainOut r = gem_eval_carrychain(ci);
        chain_o[i] = r.o; chain_co[i] = r.co;
    }
    double chain_ms = ms_since(t0);
    snprintf(path, sizeof path, "%s/cpu_chain.txt", out_dir);
    FILE *fo = open_or_die(path, "w");
    for (uint32_t i = 0; i < n; i++)
        fprintf(fo, "%llx %llx\n", (unsigned long long)chain_o[i], (unsigned long long)chain_co[i]);
    fclose(fo);

    // --- DSP48E2 ---
    std::vector<gem_u64> dsp_p(n);
    t0 = Clock::now();
    for (uint32_t i = 0; i < n; i++) {
        Dsp48e2In di{dsp_in[i].a, dsp_in[i].d, dsp_in[i].b, dsp_in[i].c,
                     dsp_in[i].state, dsp_in[i].use_pre};
        gem_u64 p = 0;
        for (int cyc = 0; cyc < GEM_BENCH_CYCLES_PER_INSTANCE; cyc++)
            p = gem_eval_dsp48e2_next_p(di, p);
        dsp_p[i] = p;
    }
    double dsp_ms = ms_since(t0);
    snprintf(path, sizeof path, "%s/cpu_dsp.txt", out_dir);
    fo = open_or_die(path, "w");
    for (uint32_t i = 0; i < n; i++) fprintf(fo, "%llx\n", (unsigned long long)dsp_p[i]);
    fclose(fo);

    // --- SRLC32E ---
    std::vector<gem_u64> srl_state(n);
    t0 = Clock::now();
    for (uint32_t i = 0; i < n; i++) {
        gem_u64 state = 0;
        for (int cyc = 0; cyc < GEM_BENCH_CYCLES_PER_INSTANCE; cyc++)
            state = gem_eval_srlc32e_next(state, srl_in[i].d, srl_in[i].ce);
        srl_state[i] = state;
    }
    double srl_ms = ms_since(t0);
    snprintf(path, sizeof path, "%s/cpu_srl.txt", out_dir);
    fo = open_or_die(path, "w");
    for (uint32_t i = 0; i < n; i++) fprintf(fo, "%llx\n", (unsigned long long)srl_state[i]);
    fclose(fo);

    printf("CARRYCHAIN %.3f ms\nDSP48E2    %.3f ms\nSRLC32E    %.3f ms\n",
           chain_ms, dsp_ms, srl_ms);
    return 0;
}
