// SPDX-License-Identifier: Apache-2.0
// CPU-vs-GPU timing baseline for csrc/gem_macros.cuh.
//
// Correctness for these macros is established elsewhere (test_gem_macros.cu,
// wired into verif/host/diff_harness.py, checked bit-exact against the
// Python golden model and, for CARRY4/DSP48E2/SRLC32E, against real Xilinx
// UNISIM). This file measures timing ONLY -- it does not re-derive
// correctness, and its pass/fail is not part of diff_harness.py's exit code.
//
// Benchmark shape, chosen to match how GEM would actually use these macros
// in a real netlist rather than to flatter the GPU number:
//   - N_INSTANCES independent macro instances (e.g. N_INSTANCES separate
//     DSP48E2 slices in a circuit), each evaluated for CYCLES_PER_INSTANCE
//     clock cycles. This is the realistic source of parallelism: many
//     independent macro sites in one netlist, not one macro re-run many
//     times. CARRYCHAIN is purely combinational, so its "cycles" collapse
//     to one evaluation per instance.
//   - GPU: one thread per instance, looping CYCLES_PER_INSTANCE times
//     sequentially within that thread (correct, since each instance's own
//     register chain must stay in program order) -- exactly
//     test_gem_macros.cu's k_dsp48e2/k_srlc32e pattern, just with many
//     independent instances running in parallel instead of one.
//   - CPU: the identical gem_macros.cuh source (it compiles as plain host
//     C++ when not __CUDACC__ -- see the header's own doc comment), run as
//     a single-threaded loop over all instances. This is a genuine
//     apples-to-apples comparison: same algorithm, same source, only the
//     execution target differs.
//
// Timing hygiene:
//   - A throwaway warm-up kernel launch absorbs CUDA's one-time context
//     -creation cost before any timed launch, so that cost isn't charged
//     to the measured kernel.
//   - cudaEvent_t timestamps separate H2D transfer, kernel execution, and
//     D2H transfer. Kernel time and end-to-end time (transfers included)
//     are reported SEPARATELY so neither number can misrepresent the other.
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <random>
#include <vector>

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

static const int CYCLES_PER_INSTANCE = 8;

struct ChainInst { gem_u64 s, di; gem_u32 cin; };
struct DspInst    { gem_u64 a, d, b, c; gem_u32 state, use_pre; };
struct SrlInst    { gem_u32 d, ce, a; };

// ---------------------------------------------------------------------------
// GPU kernels: one thread per instance.
// ---------------------------------------------------------------------------
__global__ void k_warmup() {}

__global__ void k_bench_carrychain(const ChainInst *in, gem_u64 *o, gem_u64 *co,
                                    gem_u32 n, gem_u32 count) {
    gem_u32 i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= count) return;
    CarryChainIn ci{in[i].s, in[i].di, in[i].cin, n};
    CarryChainOut r = gem_eval_carrychain(ci);
    o[i] = r.o; co[i] = r.co;
}

__global__ void k_bench_dsp48e2(const DspInst *in, gem_u64 *p_out, gem_u32 count) {
    gem_u32 i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= count) return;
    Dsp48e2In di{in[i].a, in[i].d, in[i].b, in[i].c, in[i].state, in[i].use_pre};
    gem_u64 p = 0;
    for (int cyc = 0; cyc < CYCLES_PER_INSTANCE; cyc++)
        p = gem_eval_dsp48e2_next_p(di, p);
    p_out[i] = p;
}

__global__ void k_bench_srlc32e(const SrlInst *in, gem_u64 *state_out, gem_u32 count) {
    gem_u32 i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= count) return;
    gem_u64 state = 0;
    for (int cyc = 0; cyc < CYCLES_PER_INSTANCE; cyc++)
        state = gem_eval_srlc32e_next(state, in[i].d, in[i].ce);
    state_out[i] = state;
}

// ---------------------------------------------------------------------------
// CPU reference: same gem_macros.cuh source, host-compiled path.
// ---------------------------------------------------------------------------
static void cpu_carrychain(const std::vector<ChainInst> &in,
                            std::vector<gem_u64> &o, std::vector<gem_u64> &co,
                            gem_u32 n) {
    for (size_t i = 0; i < in.size(); i++) {
        CarryChainIn ci{in[i].s, in[i].di, in[i].cin, n};
        CarryChainOut r = gem_eval_carrychain(ci);
        o[i] = r.o; co[i] = r.co;
    }
}

static void cpu_dsp48e2(const std::vector<DspInst> &in, std::vector<gem_u64> &p_out) {
    for (size_t i = 0; i < in.size(); i++) {
        Dsp48e2In di{in[i].a, in[i].d, in[i].b, in[i].c, in[i].state, in[i].use_pre};
        gem_u64 p = 0;
        for (int cyc = 0; cyc < CYCLES_PER_INSTANCE; cyc++)
            p = gem_eval_dsp48e2_next_p(di, p);
        p_out[i] = p;
    }
}

static void cpu_srlc32e(const std::vector<SrlInst> &in, std::vector<gem_u64> &state_out) {
    for (size_t i = 0; i < in.size(); i++) {
        gem_u64 state = 0;
        for (int cyc = 0; cyc < CYCLES_PER_INSTANCE; cyc++)
            state = gem_eval_srlc32e_next(state, in[i].d, in[i].ce);
        state_out[i] = state;
    }
}

// ---------------------------------------------------------------------------
// Driver
// ---------------------------------------------------------------------------
using Clock = std::chrono::steady_clock;
static double ms_since(Clock::time_point t0) {
    return std::chrono::duration<double, std::milli>(Clock::now() - t0).count();
}

int main(int argc, char **argv) {
    gem_u32 n_instances = (argc > 1) ? (gem_u32)atoll(argv[1]) : 2000000u;

    int device_count = 0;
    CUDA_CHECK(cudaGetDeviceCount(&device_count));
    if (device_count == 0) { fprintf(stderr, "no CUDA device visible\n"); return 1; }
    cudaDeviceProp prop;
    CUDA_CHECK(cudaGetDeviceProperties(&prop, 0));
    printf("GPU device        : %s (sm_%d%d)\n", prop.name, prop.major, prop.minor);
    printf("N_INSTANCES       : %u\n", n_instances);
    printf("CYCLES_PER_INSTANCE (DSP48E2/SRLC32E) : %d\n\n", CYCLES_PER_INSTANCE);

    std::mt19937_64 rng(20260828);
    gem_u32 n_bits = GEM_CARRYCHAIN_MAX_BITS;
    gem_u64 chain_mask = gem_mask(n_bits);

    std::vector<ChainInst> chain_in(n_instances);
    std::vector<DspInst>    dsp_in(n_instances);
    std::vector<SrlInst>    srl_in(n_instances);
    for (gem_u32 i = 0; i < n_instances; i++) {
        chain_in[i] = ChainInst{rng() & chain_mask, rng() & chain_mask, (gem_u32)(rng() & 1)};
        dsp_in[i] = DspInst{rng() & gem_mask(27), rng() & gem_mask(27), rng() & gem_mask(18),
                             rng() & gem_mask(48), (gem_u32)(rng() % 3), (gem_u32)(rng() & 1)};
        srl_in[i] = SrlInst{(gem_u32)(rng() & 1), (gem_u32)(rng() & 1), (gem_u32)(rng() % 32)};
    }

    // Warm-up: absorb CUDA context creation before any timed launch.
    k_warmup<<<1, 1>>>();
    CUDA_CHECK(cudaDeviceSynchronize());

    gem_u32 threads = 256, blocks = (n_instances + threads - 1) / threads;
    cudaEvent_t ev_start, ev_h2d, ev_kernel, ev_d2h;
    CUDA_CHECK(cudaEventCreate(&ev_start));
    CUDA_CHECK(cudaEventCreate(&ev_h2d));
    CUDA_CHECK(cudaEventCreate(&ev_kernel));
    CUDA_CHECK(cudaEventCreate(&ev_d2h));

    printf("%-12s %14s %14s %14s %14s %14s\n",
           "macro", "cpu_ms", "gpu_h2d_ms", "gpu_kernel_ms", "gpu_d2h_ms", "gpu_total_ms");

    // --- CARRYCHAIN ---
    {
        std::vector<gem_u64> cpu_o(n_instances), cpu_co(n_instances);
        auto t0 = Clock::now();
        cpu_carrychain(chain_in, cpu_o, cpu_co, n_bits);
        double cpu_ms = ms_since(t0);

        ChainInst *d_in; gem_u64 *d_o, *d_co;
        CUDA_CHECK(cudaMalloc(&d_in, n_instances * sizeof(ChainInst)));
        CUDA_CHECK(cudaMalloc(&d_o, n_instances * sizeof(gem_u64)));
        CUDA_CHECK(cudaMalloc(&d_co, n_instances * sizeof(gem_u64)));

        CUDA_CHECK(cudaEventRecord(ev_start));
        CUDA_CHECK(cudaMemcpyAsync(d_in, chain_in.data(), n_instances * sizeof(ChainInst),
                                    cudaMemcpyHostToDevice));
        CUDA_CHECK(cudaEventRecord(ev_h2d));
        k_bench_carrychain<<<blocks, threads>>>(d_in, d_o, d_co, n_bits, n_instances);
        CUDA_CHECK(cudaEventRecord(ev_kernel));
        std::vector<gem_u64> gpu_o(n_instances), gpu_co(n_instances);
        CUDA_CHECK(cudaMemcpyAsync(gpu_o.data(), d_o, n_instances * sizeof(gem_u64), cudaMemcpyDeviceToHost));
        CUDA_CHECK(cudaMemcpyAsync(gpu_co.data(), d_co, n_instances * sizeof(gem_u64), cudaMemcpyDeviceToHost));
        CUDA_CHECK(cudaEventRecord(ev_d2h));
        CUDA_CHECK(cudaEventSynchronize(ev_d2h));

        float h2d_ms, kernel_ms, d2h_ms;
        CUDA_CHECK(cudaEventElapsedTime(&h2d_ms, ev_start, ev_h2d));
        CUDA_CHECK(cudaEventElapsedTime(&kernel_ms, ev_h2d, ev_kernel));
        CUDA_CHECK(cudaEventElapsedTime(&d2h_ms, ev_kernel, ev_d2h));

        bool match = true;
        for (gem_u32 i = 0; i < n_instances && match; i++)
            match = (cpu_o[i] == gpu_o[i]) && (cpu_co[i] == gpu_co[i]);
        printf("%-12s %14.3f %14.3f %14.3f %14.3f %14.3f  %s\n",
               "CARRYCHAIN", cpu_ms, h2d_ms, kernel_ms, d2h_ms, h2d_ms + kernel_ms + d2h_ms,
               match ? "(CPU==GPU)" : "(MISMATCH!)");
        cudaFree(d_in); cudaFree(d_o); cudaFree(d_co);
    }

    // --- DSP48E2 ---
    {
        std::vector<gem_u64> cpu_p(n_instances);
        auto t0 = Clock::now();
        cpu_dsp48e2(dsp_in, cpu_p);
        double cpu_ms = ms_since(t0);

        DspInst *d_in; gem_u64 *d_p;
        CUDA_CHECK(cudaMalloc(&d_in, n_instances * sizeof(DspInst)));
        CUDA_CHECK(cudaMalloc(&d_p, n_instances * sizeof(gem_u64)));

        CUDA_CHECK(cudaEventRecord(ev_start));
        CUDA_CHECK(cudaMemcpyAsync(d_in, dsp_in.data(), n_instances * sizeof(DspInst),
                                    cudaMemcpyHostToDevice));
        CUDA_CHECK(cudaEventRecord(ev_h2d));
        k_bench_dsp48e2<<<blocks, threads>>>(d_in, d_p, n_instances);
        CUDA_CHECK(cudaEventRecord(ev_kernel));
        std::vector<gem_u64> gpu_p(n_instances);
        CUDA_CHECK(cudaMemcpyAsync(gpu_p.data(), d_p, n_instances * sizeof(gem_u64), cudaMemcpyDeviceToHost));
        CUDA_CHECK(cudaEventRecord(ev_d2h));
        CUDA_CHECK(cudaEventSynchronize(ev_d2h));

        float h2d_ms, kernel_ms, d2h_ms;
        CUDA_CHECK(cudaEventElapsedTime(&h2d_ms, ev_start, ev_h2d));
        CUDA_CHECK(cudaEventElapsedTime(&kernel_ms, ev_h2d, ev_kernel));
        CUDA_CHECK(cudaEventElapsedTime(&d2h_ms, ev_kernel, ev_d2h));

        bool match = true;
        for (gem_u32 i = 0; i < n_instances && match; i++) match = (cpu_p[i] == gpu_p[i]);
        printf("%-12s %14.3f %14.3f %14.3f %14.3f %14.3f  %s\n",
               "DSP48E2", cpu_ms, h2d_ms, kernel_ms, d2h_ms, h2d_ms + kernel_ms + d2h_ms,
               match ? "(CPU==GPU)" : "(MISMATCH!)");
        cudaFree(d_in); cudaFree(d_p);
    }

    // --- SRLC32E ---
    {
        std::vector<gem_u64> cpu_state(n_instances);
        auto t0 = Clock::now();
        cpu_srlc32e(srl_in, cpu_state);
        double cpu_ms = ms_since(t0);

        SrlInst *d_in; gem_u64 *d_state;
        CUDA_CHECK(cudaMalloc(&d_in, n_instances * sizeof(SrlInst)));
        CUDA_CHECK(cudaMalloc(&d_state, n_instances * sizeof(gem_u64)));

        CUDA_CHECK(cudaEventRecord(ev_start));
        CUDA_CHECK(cudaMemcpyAsync(d_in, srl_in.data(), n_instances * sizeof(SrlInst),
                                    cudaMemcpyHostToDevice));
        CUDA_CHECK(cudaEventRecord(ev_h2d));
        k_bench_srlc32e<<<blocks, threads>>>(d_in, d_state, n_instances);
        CUDA_CHECK(cudaEventRecord(ev_kernel));
        std::vector<gem_u64> gpu_state(n_instances);
        CUDA_CHECK(cudaMemcpyAsync(gpu_state.data(), d_state, n_instances * sizeof(gem_u64), cudaMemcpyDeviceToHost));
        CUDA_CHECK(cudaEventRecord(ev_d2h));
        CUDA_CHECK(cudaEventSynchronize(ev_d2h));

        float h2d_ms, kernel_ms, d2h_ms;
        CUDA_CHECK(cudaEventElapsedTime(&h2d_ms, ev_start, ev_h2d));
        CUDA_CHECK(cudaEventElapsedTime(&kernel_ms, ev_h2d, ev_kernel));
        CUDA_CHECK(cudaEventElapsedTime(&d2h_ms, ev_kernel, ev_d2h));

        bool match = true;
        for (gem_u32 i = 0; i < n_instances && match; i++) match = (cpu_state[i] == gpu_state[i]);
        printf("%-12s %14.3f %14.3f %14.3f %14.3f %14.3f  %s\n",
               "SRLC32E", cpu_ms, h2d_ms, kernel_ms, d2h_ms, h2d_ms + kernel_ms + d2h_ms,
               match ? "(CPU==GPU)" : "(MISMATCH!)");
        cudaFree(d_in); cudaFree(d_state);
    }

    printf("\nNote: gpu_total_ms includes H2D+kernel+D2H transfer, but NOT the one-time\n"
           "CUDA context creation cost -- that was absorbed by the warm-up launch before\n"
           "any timed event, exactly so it wouldn't inflate (or deflate) these numbers.\n"
           "cpu_ms and gpu_kernel_ms are the fair apples-to-apples comparison; gpu_total_ms\n"
           "is what a caller doing one round trip per launch would actually see.\n");
    return 0;
}
