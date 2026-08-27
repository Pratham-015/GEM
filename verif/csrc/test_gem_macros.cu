// SPDX-License-Identifier: Apache-2.0
// GPU-executed differential test for csrc/gem_macros.cuh.
//
// This is deliberately NOT a compile-only smoke test: every macro kind is
// launched as a real CUDA kernel against the exact same stimulus vectors
// diff_harness.py already generated for the Verilog/Python cross-check
// (sim_out/stim_*.txt), and the results are written in the same res_*.txt
// format so the Python harness can diff them against the same golden model
// it already trusts for the Verilog side.
//
// CARRYCHAIN is embarrassingly parallel (each vector is an independent
// fused add), so it launches one thread per vector -- the actual
// many-lanes-converged execution pattern the header's design argument is
// about. DSP48E2 and SRLC32E carry state across vectors in program order
// (P and SRL are real registers), so those run as single-thread sequential
// loops inside their kernels: still genuine GPU execution, just not
// grid-parallel, because correctness requires reproducing the same in
// -order register chain the Python golden model (dsp.tick / srl.tick)
// walks.
#include <cstdio>
#include <cstdlib>
#include <cstring>
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

// ---------------------------------------------------------------------------
// CARRYCHAIN: one thread per vector, fully parallel.
// ---------------------------------------------------------------------------
struct ChainVec { gem_u64 s, di; gem_u32 cin; };

__global__ void k_carrychain(const ChainVec *in, gem_u64 *o, gem_u64 *co,
                              gem_u32 n, gem_u32 count) {
    gem_u32 i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= count) return;
    CarryChainIn ci;
    ci.s = in[i].s; ci.di = in[i].di; ci.cin = in[i].cin; ci.n = n;
    CarryChainOut co_out = gem_eval_carrychain(ci);
    o[i] = co_out.o;
    co[i] = co_out.co;
}

// ---------------------------------------------------------------------------
// DSP48E2: single-thread sequential loop -- P is a real register, so vector
// order matters exactly as it does for the Python golden model's dsp.tick().
// ---------------------------------------------------------------------------
struct DspVec { gem_u64 a, d, b, c; gem_u32 state, use_pre; };

__global__ void k_dsp48e2(const DspVec *in, gem_u64 *p_out, gem_u32 count) {
    if (blockIdx.x != 0 || threadIdx.x != 0) return;
    gem_u64 p_cur = 0;
    for (gem_u32 i = 0; i < count; i++) {
        Dsp48e2In di;
        di.a = in[i].a; di.d = in[i].d; di.b = in[i].b; di.c = in[i].c;
        di.state = in[i].state; di.use_pre = in[i].use_pre;
        p_cur = gem_eval_dsp48e2_next_p(di, p_cur);
        p_out[i] = p_cur;
    }
}

// ---------------------------------------------------------------------------
// SRLC32E: single-thread sequential loop -- same in-order register
// requirement as DSP48E2.
// ---------------------------------------------------------------------------
struct SrlVec { gem_u32 d, ce, a; };

__global__ void k_srlc32e(const SrlVec *in, gem_u32 *q_out, gem_u32 *q31_out,
                           gem_u64 *state_out, gem_u32 count) {
    if (blockIdx.x != 0 || threadIdx.x != 0) return;
    gem_u64 state = 0;
    for (gem_u32 i = 0; i < count; i++) {
        gem_u32 qq = gem_eval_srlc32e_read(state, in[i].a);
        q_out[i]   = qq & 1u;
        q31_out[i] = (qq >> 1) & 1u;
        state = gem_eval_srlc32e_next(state, in[i].d, in[i].ce);
        state_out[i] = state;
    }
}

// ---------------------------------------------------------------------------
// Host-side stimulus loading / result writing.
// ---------------------------------------------------------------------------
static FILE *open_or_die(const char *path, const char *mode) {
    FILE *f = fopen(path, mode);
    if (!f) { fprintf(stderr, "cannot open %s\n", path); exit(1); }
    return f;
}

static bool run_carrychain(const char *sim_out) {
    char stim_path[4096], res_path[4096];
    snprintf(stim_path, sizeof stim_path, "%s/stim_chain.txt", sim_out);
    snprintf(res_path, sizeof res_path, "%s/res_chain_cuda.txt", sim_out);

    std::vector<ChainVec> vecs;
    FILE *fi = open_or_die(stim_path, "r");
    unsigned long long s, di; unsigned cyi;
    while (fscanf(fi, "%llx %llx %x", &s, &di, &cyi) == 3)
        vecs.push_back(ChainVec{s, di, cyi});
    fclose(fi);
    if (vecs.empty()) { fprintf(stderr, "CARRYCHAIN: no vectors read\n"); return false; }

    ChainVec *d_in; gem_u64 *d_o, *d_co;
    CUDA_CHECK(cudaMalloc(&d_in, vecs.size() * sizeof(ChainVec)));
    CUDA_CHECK(cudaMalloc(&d_o, vecs.size() * sizeof(gem_u64)));
    CUDA_CHECK(cudaMalloc(&d_co, vecs.size() * sizeof(gem_u64)));
    CUDA_CHECK(cudaMemcpy(d_in, vecs.data(), vecs.size() * sizeof(ChainVec),
                           cudaMemcpyHostToDevice));

    gem_u32 n = GEM_CARRYCHAIN_MAX_BITS;
    gem_u32 threads = 256, blocks = (vecs.size() + threads - 1) / threads;
    k_carrychain<<<blocks, threads>>>(d_in, d_o, d_co, n, (gem_u32)vecs.size());
    CUDA_CHECK(cudaGetLastError());
    CUDA_CHECK(cudaDeviceSynchronize());

    std::vector<gem_u64> o(vecs.size()), co(vecs.size());
    CUDA_CHECK(cudaMemcpy(o.data(), d_o, vecs.size() * sizeof(gem_u64), cudaMemcpyDeviceToHost));
    CUDA_CHECK(cudaMemcpy(co.data(), d_co, vecs.size() * sizeof(gem_u64), cudaMemcpyDeviceToHost));
    cudaFree(d_in); cudaFree(d_o); cudaFree(d_co);

    FILE *fo = open_or_die(res_path, "w");
    for (size_t i = 0; i < vecs.size(); i++)
        fprintf(fo, "%llx %llx\n", (unsigned long long)o[i], (unsigned long long)co[i]);
    fclose(fo);
    printf("CARRYCHAIN : %zu vectors executed on GPU (%u threads/block, %u blocks)\n",
           vecs.size(), threads, blocks);
    return true;
}

static bool run_dsp48e2(const char *sim_out) {
    char stim_path[4096], res_path[4096];
    snprintf(stim_path, sizeof stim_path, "%s/stim_dsp.txt", sim_out);
    snprintf(res_path, sizeof res_path, "%s/res_dsp_cuda.txt", sim_out);

    std::vector<DspVec> vecs;
    FILE *fi = open_or_die(stim_path, "r");
    unsigned long long a, d, b, c; unsigned st, up;
    while (fscanf(fi, "%llx %llx %llx %llx %x %x", &a, &d, &b, &c, &st, &up) == 6)
        vecs.push_back(DspVec{a, d, b, c, st, up});
    fclose(fi);
    if (vecs.empty()) { fprintf(stderr, "DSP48E2: no vectors read\n"); return false; }

    DspVec *d_in; gem_u64 *d_p;
    CUDA_CHECK(cudaMalloc(&d_in, vecs.size() * sizeof(DspVec)));
    CUDA_CHECK(cudaMalloc(&d_p, vecs.size() * sizeof(gem_u64)));
    CUDA_CHECK(cudaMemcpy(d_in, vecs.data(), vecs.size() * sizeof(DspVec),
                           cudaMemcpyHostToDevice));

    k_dsp48e2<<<1, 1>>>(d_in, d_p, (gem_u32)vecs.size());
    CUDA_CHECK(cudaGetLastError());
    CUDA_CHECK(cudaDeviceSynchronize());

    std::vector<gem_u64> p(vecs.size());
    CUDA_CHECK(cudaMemcpy(p.data(), d_p, vecs.size() * sizeof(gem_u64), cudaMemcpyDeviceToHost));
    cudaFree(d_in); cudaFree(d_p);

    FILE *fo = open_or_die(res_path, "w");
    for (size_t i = 0; i < vecs.size(); i++)
        fprintf(fo, "%llx\n", (unsigned long long)p[i]);
    fclose(fo);
    printf("DSP48E2    : %zu vectors executed on GPU (sequential P register)\n", vecs.size());
    return true;
}

static bool run_srlc32e(const char *sim_out) {
    char stim_path[4096], res_path[4096];
    snprintf(stim_path, sizeof stim_path, "%s/stim_srl.txt", sim_out);
    snprintf(res_path, sizeof res_path, "%s/res_srl_cuda.txt", sim_out);

    std::vector<SrlVec> vecs;
    FILE *fi = open_or_die(stim_path, "r");
    unsigned d, ce, a;
    while (fscanf(fi, "%x %x %x", &d, &ce, &a) == 3)
        vecs.push_back(SrlVec{d, ce, a});
    fclose(fi);
    if (vecs.empty()) { fprintf(stderr, "SRLC32E: no vectors read\n"); return false; }

    SrlVec *d_in; gem_u32 *d_q, *d_q31; gem_u64 *d_state;
    CUDA_CHECK(cudaMalloc(&d_in, vecs.size() * sizeof(SrlVec)));
    CUDA_CHECK(cudaMalloc(&d_q, vecs.size() * sizeof(gem_u32)));
    CUDA_CHECK(cudaMalloc(&d_q31, vecs.size() * sizeof(gem_u32)));
    CUDA_CHECK(cudaMalloc(&d_state, vecs.size() * sizeof(gem_u64)));
    CUDA_CHECK(cudaMemcpy(d_in, vecs.data(), vecs.size() * sizeof(SrlVec),
                           cudaMemcpyHostToDevice));

    k_srlc32e<<<1, 1>>>(d_in, d_q, d_q31, d_state, (gem_u32)vecs.size());
    CUDA_CHECK(cudaGetLastError());
    CUDA_CHECK(cudaDeviceSynchronize());

    std::vector<gem_u32> q(vecs.size()), q31(vecs.size());
    std::vector<gem_u64> state(vecs.size());
    CUDA_CHECK(cudaMemcpy(q.data(), d_q, vecs.size() * sizeof(gem_u32), cudaMemcpyDeviceToHost));
    CUDA_CHECK(cudaMemcpy(q31.data(), d_q31, vecs.size() * sizeof(gem_u32), cudaMemcpyDeviceToHost));
    CUDA_CHECK(cudaMemcpy(state.data(), d_state, vecs.size() * sizeof(gem_u64), cudaMemcpyDeviceToHost));
    cudaFree(d_in); cudaFree(d_q); cudaFree(d_q31); cudaFree(d_state);

    FILE *fo = open_or_die(res_path, "w");
    for (size_t i = 0; i < vecs.size(); i++)
        fprintf(fo, "%x %x %llx\n", q[i], q31[i], (unsigned long long)state[i]);
    fclose(fo);
    printf("SRLC32E    : %zu vectors executed on GPU (sequential SRL register)\n", vecs.size());
    return true;
}

int main(int argc, char **argv) {
    if (argc != 2) {
        fprintf(stderr, "usage: %s <sim_out_dir>\n", argv[0]);
        return 1;
    }
    const char *sim_out = argv[1];

    int device_count = 0;
    CUDA_CHECK(cudaGetDeviceCount(&device_count));
    if (device_count == 0) {
        fprintf(stderr, "no CUDA device visible\n");
        return 1;
    }
    cudaDeviceProp prop;
    CUDA_CHECK(cudaGetDeviceProperties(&prop, 0));
    printf("GPU device : %s (sm_%d%d)\n", prop.name, prop.major, prop.minor);

    bool ok = true;
    ok &= run_carrychain(sim_out);
    ok &= run_dsp48e2(sim_out);
    ok &= run_srlc32e(sim_out);
    return ok ? 0 : 1;
}
