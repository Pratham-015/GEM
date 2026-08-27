// SPDX-License-Identifier: Apache-2.0
// GPU-side half of the gem_macros.cuh timing baseline. See bench_cpu.cpp
// for the CPU side and bench_gen.h for why both binaries see identical
// input. Correctness is established separately by test_gem_macros.cu (via
// verif/host/diff_harness.py); this file's job is timing only, plus writing
// results so a wrapper can cross-check them against the CPU side as a
// sanity backstop.
//
// Timing hygiene: a throwaway warm-up kernel absorbs CUDA's one-time
// context-creation cost before any timed launch. cudaEvent_t timestamps
// separate H2D transfer, kernel execution, and D2H transfer, reported
// separately so no one number can misrepresent another.
#include <cstdio>
#include <cstdlib>
#include <vector>

#include "bench_gen.h"
#include "gem_macros.cuh"

using namespace gem;

#define CUDA_CHECK(call)                                                    \
  do {                                                                      \
    cudaError_t err = (call);                                               \
    if (err != cudaSuccess) {                                               \
      fprintf(stderr, "CUDA error at %s:%d: %s\n", __FILE__, __LINE__,      \
              cudaGetErrorString(err));                                     \
      exit(1);                                                              \
    }                                                                       \
  } while (0)

__global__ void k_warmup() {}

__global__ void k_carrychain(const ChainInst *in, gem_u64 *o, gem_u64 *co, gem_u32 count) {
    gem_u32 i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= count) return;
    CarryChainIn ci{in[i].s, in[i].di, in[i].cin, GEM_CARRYCHAIN_MAX_BITS};
    CarryChainOut r = gem_eval_carrychain(ci);
    o[i] = r.o; co[i] = r.co;
}

__global__ void k_dsp48e2(const DspInst *in, gem_u64 *p_out, gem_u32 count) {
    gem_u32 i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= count) return;
    Dsp48e2In di{in[i].a, in[i].d, in[i].b, in[i].c, in[i].state, in[i].use_pre};
    gem_u64 p = 0;
    for (int cyc = 0; cyc < GEM_BENCH_CYCLES_PER_INSTANCE; cyc++)
        p = gem_eval_dsp48e2_next_p(di, p);
    p_out[i] = p;
}

__global__ void k_srlc32e(const SrlInst *in, gem_u64 *state_out, gem_u32 count) {
    gem_u32 i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= count) return;
    gem_u64 state = 0;
    for (int cyc = 0; cyc < GEM_BENCH_CYCLES_PER_INSTANCE; cyc++)
        state = gem_eval_srlc32e_next(state, in[i].d, in[i].ce);
    state_out[i] = state;
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

    int device_count = 0;
    CUDA_CHECK(cudaGetDeviceCount(&device_count));
    if (device_count == 0) { fprintf(stderr, "no CUDA device visible\n"); return 1; }
    cudaDeviceProp prop;
    CUDA_CHECK(cudaGetDeviceProperties(&prop, 0));
    fprintf(stderr, "GPU device: %s (sm_%d%d)\n", prop.name, prop.major, prop.minor);

    std::vector<ChainInst> chain_in;
    std::vector<DspInst> dsp_in;
    std::vector<SrlInst> srl_in;
    gen_instances(n, chain_in, dsp_in, srl_in);

    // Warm-up: absorb CUDA context creation before any timed launch.
    k_warmup<<<1, 1>>>();
    CUDA_CHECK(cudaDeviceSynchronize());

    gem_u32 threads = 256, blocks = (n + threads - 1) / threads;
    cudaEvent_t ev_start, ev_h2d, ev_kernel, ev_d2h;
    CUDA_CHECK(cudaEventCreate(&ev_start));
    CUDA_CHECK(cudaEventCreate(&ev_h2d));
    CUDA_CHECK(cudaEventCreate(&ev_kernel));
    CUDA_CHECK(cudaEventCreate(&ev_d2h));

    char path[4096];
    printf("%-12s %14s %14s %14s %14s\n",
           "macro", "h2d_ms", "kernel_ms", "d2h_ms", "total_ms");

    // --- CARRYCHAIN ---
    {
        ChainInst *d_in; gem_u64 *d_o, *d_co;
        CUDA_CHECK(cudaMalloc(&d_in, n * sizeof(ChainInst)));
        CUDA_CHECK(cudaMalloc(&d_o, n * sizeof(gem_u64)));
        CUDA_CHECK(cudaMalloc(&d_co, n * sizeof(gem_u64)));

        CUDA_CHECK(cudaEventRecord(ev_start));
        CUDA_CHECK(cudaMemcpyAsync(d_in, chain_in.data(), n * sizeof(ChainInst), cudaMemcpyHostToDevice));
        CUDA_CHECK(cudaEventRecord(ev_h2d));
        k_carrychain<<<blocks, threads>>>(d_in, d_o, d_co, n);
        CUDA_CHECK(cudaEventRecord(ev_kernel));
        std::vector<gem_u64> o(n), co(n);
        CUDA_CHECK(cudaMemcpyAsync(o.data(), d_o, n * sizeof(gem_u64), cudaMemcpyDeviceToHost));
        CUDA_CHECK(cudaMemcpyAsync(co.data(), d_co, n * sizeof(gem_u64), cudaMemcpyDeviceToHost));
        CUDA_CHECK(cudaEventRecord(ev_d2h));
        CUDA_CHECK(cudaEventSynchronize(ev_d2h));

        float h2d_ms, kernel_ms, d2h_ms;
        CUDA_CHECK(cudaEventElapsedTime(&h2d_ms, ev_start, ev_h2d));
        CUDA_CHECK(cudaEventElapsedTime(&kernel_ms, ev_h2d, ev_kernel));
        CUDA_CHECK(cudaEventElapsedTime(&d2h_ms, ev_kernel, ev_d2h));
        printf("%-12s %14.3f %14.3f %14.3f %14.3f\n",
               "CARRYCHAIN", h2d_ms, kernel_ms, d2h_ms, h2d_ms + kernel_ms + d2h_ms);

        snprintf(path, sizeof path, "%s/gpu_chain.txt", out_dir);
        FILE *fo = open_or_die(path, "w");
        for (uint32_t i = 0; i < n; i++)
            fprintf(fo, "%llx %llx\n", (unsigned long long)o[i], (unsigned long long)co[i]);
        fclose(fo);
        cudaFree(d_in); cudaFree(d_o); cudaFree(d_co);
    }

    // --- DSP48E2 ---
    {
        DspInst *d_in; gem_u64 *d_p;
        CUDA_CHECK(cudaMalloc(&d_in, n * sizeof(DspInst)));
        CUDA_CHECK(cudaMalloc(&d_p, n * sizeof(gem_u64)));

        CUDA_CHECK(cudaEventRecord(ev_start));
        CUDA_CHECK(cudaMemcpyAsync(d_in, dsp_in.data(), n * sizeof(DspInst), cudaMemcpyHostToDevice));
        CUDA_CHECK(cudaEventRecord(ev_h2d));
        k_dsp48e2<<<blocks, threads>>>(d_in, d_p, n);
        CUDA_CHECK(cudaEventRecord(ev_kernel));
        std::vector<gem_u64> p(n);
        CUDA_CHECK(cudaMemcpyAsync(p.data(), d_p, n * sizeof(gem_u64), cudaMemcpyDeviceToHost));
        CUDA_CHECK(cudaEventRecord(ev_d2h));
        CUDA_CHECK(cudaEventSynchronize(ev_d2h));

        float h2d_ms, kernel_ms, d2h_ms;
        CUDA_CHECK(cudaEventElapsedTime(&h2d_ms, ev_start, ev_h2d));
        CUDA_CHECK(cudaEventElapsedTime(&kernel_ms, ev_h2d, ev_kernel));
        CUDA_CHECK(cudaEventElapsedTime(&d2h_ms, ev_kernel, ev_d2h));
        printf("%-12s %14.3f %14.3f %14.3f %14.3f\n",
               "DSP48E2", h2d_ms, kernel_ms, d2h_ms, h2d_ms + kernel_ms + d2h_ms);

        snprintf(path, sizeof path, "%s/gpu_dsp.txt", out_dir);
        FILE *fo = open_or_die(path, "w");
        for (uint32_t i = 0; i < n; i++) fprintf(fo, "%llx\n", (unsigned long long)p[i]);
        fclose(fo);
        cudaFree(d_in); cudaFree(d_p);
    }

    // --- SRLC32E ---
    {
        SrlInst *d_in; gem_u64 *d_state;
        CUDA_CHECK(cudaMalloc(&d_in, n * sizeof(SrlInst)));
        CUDA_CHECK(cudaMalloc(&d_state, n * sizeof(gem_u64)));

        CUDA_CHECK(cudaEventRecord(ev_start));
        CUDA_CHECK(cudaMemcpyAsync(d_in, srl_in.data(), n * sizeof(SrlInst), cudaMemcpyHostToDevice));
        CUDA_CHECK(cudaEventRecord(ev_h2d));
        k_srlc32e<<<blocks, threads>>>(d_in, d_state, n);
        CUDA_CHECK(cudaEventRecord(ev_kernel));
        std::vector<gem_u64> state(n);
        CUDA_CHECK(cudaMemcpyAsync(state.data(), d_state, n * sizeof(gem_u64), cudaMemcpyDeviceToHost));
        CUDA_CHECK(cudaEventRecord(ev_d2h));
        CUDA_CHECK(cudaEventSynchronize(ev_d2h));

        float h2d_ms, kernel_ms, d2h_ms;
        CUDA_CHECK(cudaEventElapsedTime(&h2d_ms, ev_start, ev_h2d));
        CUDA_CHECK(cudaEventElapsedTime(&kernel_ms, ev_h2d, ev_kernel));
        CUDA_CHECK(cudaEventElapsedTime(&d2h_ms, ev_kernel, ev_d2h));
        printf("%-12s %14.3f %14.3f %14.3f %14.3f\n",
               "SRLC32E", h2d_ms, kernel_ms, d2h_ms, h2d_ms + kernel_ms + d2h_ms);

        snprintf(path, sizeof path, "%s/gpu_srl.txt", out_dir);
        FILE *fo = open_or_die(path, "w");
        for (uint32_t i = 0; i < n; i++) fprintf(fo, "%llx\n", (unsigned long long)state[i]);
        fclose(fo);
        cudaFree(d_in); cudaFree(d_state);
    }

    return 0;
}
