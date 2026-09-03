// ============================================================================
// benchmark/bench_engine.cu
// High-performance CUDA benchmarking engine comparing:
// 1. Baseline GEM (flattened 1-bit boolean AIG gate evaluation)
// 2. Macro-Augmented GEM (native 64-bit word-level ALU evaluation)
// ============================================================================
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <vector>
#include <string>
#include <chrono>
#include <cuda_runtime.h>

#include "../csrc/gem_macros.cuh"

#define CUDA_CHECK(call)                                                    \
  do {                                                                      \
    cudaError_t err = (call);                                               \
    if (err != cudaSuccess) {                                               \
      fprintf(stderr, "CUDA Error at %s:%d: %s\n", __FILE__, __LINE__,      \
              cudaGetErrorString(err));                                     \
      exit(1);                                                              \
    }                                                                       \
  } while (0)

using namespace gem;

// Data structures for inputs
struct CarryInput {
    gem_u64 s;
    gem_u64 di;
    gem_u32 cin;
    gem_u32 bits;
};

struct DspInput {
    gem_u64 a;
    gem_u64 d;
    gem_u64 b;
    gem_u64 c;
    gem_u32 state;
    gem_u32 use_pre;
};

struct SrlInput {
    gem_u32 d;
    gem_u32 ce;
    gem_u32 addr;
};

// ============================================================================
// 1. BASELINE KERNELS (Shredded bit-level boolean AIG logic)
// ============================================================================

// Baseline CARRY4: Bit-by-bit ripple through 60 boolean levels
__global__ void k_baseline_carrychain(const CarryInput *__restrict__ in,
                                      gem_u64 *__restrict__ o_out,
                                      gem_u64 *__restrict__ co_out,
                                      gem_u32 count,
                                      gem_u32 cycles) {
    gem_u32 idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= count) return;

    gem_u64 s = in[idx].s;
    gem_u64 di = in[idx].di;
    gem_u32 bits = in[idx].bits;

    gem_u64 o = 0;
    gem_u64 co = 0;

    for (gem_u32 cyc = 0; cyc < cycles; cyc++) {
        gem_u32 c = (in[idx].cin ^ cyc) & 1;
        o = 0;
        co = 0;
        // Serial ripple loop emulating discrete 1-bit Boolean operations.
        #pragma unroll 1
        for (gem_u32 i = 0; i < bits; i++) {
            gem_u32 s_i = (s >> i) & 1;
            gem_u32 di_i = (di >> i) & 1;
            gem_u32 o_i = s_i ^ c;
            gem_u32 c_next = (s_i & c) | ((~s_i & 1) & di_i);
            o |= ((gem_u64)o_i << i);
            co |= ((gem_u64)c_next << i);
            c = c_next;
        }
    }

    o_out[idx] = o;
    co_out[idx] = co;
}

// Baseline DSP48E2: Multi-step boolean bit-level multiplier & accumulator
__global__ void k_baseline_dsp48e2(const DspInput *__restrict__ in,
                                   gem_u64 *__restrict__ p_out,
                                   gem_u32 count,
                                   gem_u32 cycles) {
    gem_u32 idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= count) return;

    gem_u64 a = in[idx].a & 0x7FFFFFFULL;
    gem_u64 d = in[idx].d & 0x7FFFFFFULL;
    gem_u64 b = in[idx].b & 0x3FFFFULL;
    gem_u64 c = in[idx].c & 0xFFFFFFFFFFFFULL;
    gem_u32 state = in[idx].state;
    gem_u32 use_pre = in[idx].use_pre;

    gem_u64 p_reg = 0;

    for (gem_u32 cyc = 0; cyc < cycles; cyc++) {
        // Sign-extend A and D to 27-bit signed
        gem_i64 a_s = (a ^ 0x4000000ULL) - 0x4000000ULL;
        gem_i64 d_s = (d ^ 0x4000000ULL) - 0x4000000ULL;
        gem_i64 ad_s = use_pre ? ((a_s + d_s) & 0x7FFFFFFULL) : a_s;
        if (use_pre) ad_s = (ad_s ^ 0x4000000ULL) - 0x4000000ULL;

        gem_i64 b_s = (b ^ 0x20000ULL) - 0x20000ULL;

        // Bit-level shift-and-add emulation
        gem_i64 m_prod = 0;
        #pragma unroll 1
        for (int i = 0; i < 18; i++) {
            if ((b & (1 << i)) != 0) {
                m_prod += (ad_s << i);
            }
        }
        if (b_s < 0) {
            m_prod -= (ad_s << 18);
        }

        gem_u64 p_next = 0;
        if (state == 0) {
            p_next = c;
        } else if (state == 1) {
            p_next = (gem_u64)m_prod & 0xFFFFFFFFFFFFULL;
        } else {
            gem_i64 p_s = ((gem_i64)p_reg ^ 0x800000000000LL) - 0x800000000000LL;
            p_next = (gem_u64)(p_s + m_prod) & 0xFFFFFFFFFFFFULL;
        }
        p_reg = p_next;
    }

    p_out[idx] = p_reg;
}

// Baseline SRLC32E: 32 discrete flip-flops + 32-to-1 mux tree
__global__ void k_baseline_srlc32e(const SrlInput *__restrict__ in,
                                   gem_u64 *__restrict__ state_out,
                                   gem_u32 count,
                                   gem_u32 cycles) {
    gem_u32 idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= count) return;

    gem_u32 d = in[idx].d & 1;
    gem_u32 ce = in[idx].ce & 1;
    gem_u32 addr = in[idx].addr & 31;

    gem_u32 ff[32] = {0};

    for (gem_u32 cyc = 0; cyc < cycles; cyc++) {
        if (ce) {
            #pragma unroll 1
            for (int i = 31; i > 0; i--) {
                ff[i] = ff[i - 1];
            }
            ff[0] = d;
        }
    }

    // 32-to-1 mux tree read
    gem_u32 q = ff[addr];
    gem_u32 q31 = ff[31];
    state_out[idx] = ((gem_u64)q31 << 32) | (gem_u64)q;
}

// ============================================================================
// 2. MACRO-AUGMENTED KERNELS (64-bit Integer ALU Native Acceleration)
// ============================================================================

__global__ void k_macro_carrychain(const CarryInput *__restrict__ in,
                                   gem_u64 *__restrict__ o_out,
                                   gem_u64 *__restrict__ co_out,
                                   gem_u32 count,
                                   gem_u32 cycles) {
    gem_u32 idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= count) return;

    CarryChainOut r{};
    for (gem_u32 cyc = 0; cyc < cycles; cyc++) {
        CarryChainIn ci{in[idx].s, in[idx].di, in[idx].cin ^ (cyc & 1), in[idx].bits};
        r = gem_eval_carrychain(ci);
    }
    o_out[idx] = r.o;
    co_out[idx] = r.co;
}

__global__ void k_macro_dsp48e2(const DspInput *__restrict__ in,
                                gem_u64 *__restrict__ p_out,
                                gem_u32 count,
                                gem_u32 cycles) {
    gem_u32 idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= count) return;

    Dsp48e2In di{in[idx].a, in[idx].d, in[idx].b, in[idx].c, in[idx].state, in[idx].use_pre};
    gem_u64 p = 0;
    #pragma unroll 4
    for (gem_u32 cyc = 0; cyc < cycles; cyc++) {
        p = gem_eval_dsp48e2_next_p(di, p);
    }
    p_out[idx] = p;
}

__global__ void k_macro_srlc32e(const SrlInput *__restrict__ in,
                                gem_u64 *__restrict__ state_out,
                                gem_u32 count,
                                gem_u32 cycles) {
    gem_u32 idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= count) return;

    gem_u64 state = 0;
    gem_u32 d = in[idx].d;
    gem_u32 ce = in[idx].ce;
    #pragma unroll 4
    for (gem_u32 cyc = 0; cyc < cycles; cyc++) {
        state = gem_eval_srlc32e_next(state, d, ce);
    }
    state_out[idx] = state;
}

// Warmup kernel
__global__ void k_warmup() {}

// ============================================================================
// MAIN BENCHMARK DRIVER
// ============================================================================
int main(int argc, char **argv) {
    gem_u32 count = 100000;
    gem_u32 cycles = 64;
    std::string mode = "all";
    std::string csv_file = "";

    for (int i = 1; i < argc; i++) {
        if (std::string(argv[i]) == "--n" && i + 1 < argc) {
            count = (gem_u32)std::stoul(argv[++i]);
        } else if (std::string(argv[i]) == "--cycles" && i + 1 < argc) {
            cycles = (gem_u32)std::stoul(argv[++i]);
        } else if (std::string(argv[i]) == "--mode" && i + 1 < argc) {
            mode = argv[++i];
        } else if (std::string(argv[i]) == "--csv" && i + 1 < argc) {
            csv_file = argv[++i];
        }
    }

    cudaDeviceProp prop;
    CUDA_CHECK(cudaGetDeviceProperties(&prop, 0));
    printf("======================================================================\n");
    printf("  GEM BENCHMARK ENGINE (Deliverable D)\n");
    printf("  Device: %s (SM %d.%d, %d SMs)\n", prop.name, prop.major, prop.minor, prop.multiProcessorCount);
    printf("  Batch size (N): %u | Simulation cycles (C): %u | Mode: %s\n", count, cycles, mode.c_str());
    printf("======================================================================\n\n");

    // Warmup GPU
    k_warmup<<<1, 1>>>();
    CUDA_CHECK(cudaDeviceSynchronize());

    gem_u32 threads = 256;
    gem_u32 blocks = (count + threads - 1) / threads;

    cudaEvent_t ev_start, ev_stop;
    CUDA_CHECK(cudaEventCreate(&ev_start));
    CUDA_CHECK(cudaEventCreate(&ev_stop));

    FILE *f_csv = nullptr;
    if (!csv_file.empty()) {
        f_csv = fopen(csv_file.c_str(), "a");
    }

    // ------------------------------------------------------------------------
    // 1. CARRYCHAIN BENCHMARK (60-bit 15-block chained adder)
    // ------------------------------------------------------------------------
    if (mode == "all" || mode == "carry") {
        std::vector<CarryInput> h_carry(count);
        for (gem_u32 i = 0; i < count; i++) {
            h_carry[i] = CarryInput{
                static_cast<gem_u64>(static_cast<gem_u64>(static_cast<gem_u32>(rand())) | (static_cast<gem_u64>(static_cast<gem_u32>(rand())) << 32)),
                static_cast<gem_u64>(static_cast<gem_u64>(static_cast<gem_u32>(rand())) | (static_cast<gem_u64>(static_cast<gem_u32>(rand())) << 32)),
                static_cast<gem_u32>(static_cast<gem_u32>(rand()) & 1u),
                60
            };
        }

        CarryInput *d_carry;
        gem_u64 *d_o, *d_co;
        CUDA_CHECK(cudaMalloc(&d_carry, count * sizeof(CarryInput)));
        CUDA_CHECK(cudaMalloc(&d_o, count * sizeof(gem_u64)));
        CUDA_CHECK(cudaMalloc(&d_co, count * sizeof(gem_u64)));

        CUDA_CHECK(cudaMemcpy(d_carry, h_carry.data(), count * sizeof(CarryInput), cudaMemcpyHostToDevice));

        // Baseline Timing
        CUDA_CHECK(cudaEventRecord(ev_start));
        k_baseline_carrychain<<<blocks, threads>>>(d_carry, d_o, d_co, count, cycles);
        CUDA_CHECK(cudaEventRecord(ev_stop));
        CUDA_CHECK(cudaEventSynchronize(ev_stop));
        float t_base = 0;
        CUDA_CHECK(cudaEventElapsedTime(&t_base, ev_start, ev_stop));

        // Macro Timing
        CUDA_CHECK(cudaEventRecord(ev_start));
        k_macro_carrychain<<<blocks, threads>>>(d_carry, d_o, d_co, count, cycles);
        CUDA_CHECK(cudaEventRecord(ev_stop));
        CUDA_CHECK(cudaEventSynchronize(ev_stop));
        float t_macro = 0;
        CUDA_CHECK(cudaEventElapsedTime(&t_macro, ev_start, ev_stop));

        float speedup = t_base / t_macro;
        double mevals = (double)count * cycles / (t_macro * 1000.0);

        printf("  [CARRYCHAIN 60-bit]\n");
        printf("    Synthetic 1-bit ripple  : %8.3f ms\n", t_base);
        printf("    Macro (64-bit fused)    : %8.3f ms\n", t_macro);
        printf("    Speedup                 : %8.2fx\n", speedup);
        printf("    Throughput              : %8.2f MEvals/sec\n\n", mevals);

        if (f_csv) {
            fprintf(f_csv, "CARRYCHAIN,%u,%u,%.3f,%.3f,%.2f,%.2f\n", count, cycles, t_base, t_macro, speedup, mevals);
        }

        CUDA_CHECK(cudaFree(d_carry));
        CUDA_CHECK(cudaFree(d_o));
        CUDA_CHECK(cudaFree(d_co));
    }

    // ------------------------------------------------------------------------
    // 2. DSP48E2 BENCHMARK (27x18 MAC)
    // ------------------------------------------------------------------------
    if (mode == "all" || mode == "dsp") {
        std::vector<DspInput> h_dsp(count);
        for (gem_u32 i = 0; i < count; i++) {
            h_dsp[i] = DspInput{
                static_cast<gem_u64>(static_cast<gem_u32>(rand()) & 0x7FFFFFFu),
                static_cast<gem_u64>(static_cast<gem_u32>(rand()) & 0x7FFFFFFu),
                static_cast<gem_u64>(static_cast<gem_u32>(rand()) & 0x3FFFFu),
                static_cast<gem_u64>(static_cast<gem_u64>(static_cast<gem_u32>(rand())) | (static_cast<gem_u64>(static_cast<gem_u32>(rand())) << 32)) & 0xFFFFFFFFFFFFULL,
                static_cast<gem_u32>(static_cast<gem_u32>(rand()) % 3u),
                static_cast<gem_u32>(static_cast<gem_u32>(rand()) & 1u)
            };
        }

        DspInput *d_dsp;
        gem_u64 *d_p;
        CUDA_CHECK(cudaMalloc(&d_dsp, count * sizeof(DspInput)));
        CUDA_CHECK(cudaMalloc(&d_p, count * sizeof(gem_u64)));

        CUDA_CHECK(cudaMemcpy(d_dsp, h_dsp.data(), count * sizeof(DspInput), cudaMemcpyHostToDevice));

        // Baseline Timing
        CUDA_CHECK(cudaEventRecord(ev_start));
        k_baseline_dsp48e2<<<blocks, threads>>>(d_dsp, d_p, count, cycles);
        CUDA_CHECK(cudaEventRecord(ev_stop));
        CUDA_CHECK(cudaEventSynchronize(ev_stop));
        float t_base = 0;
        CUDA_CHECK(cudaEventElapsedTime(&t_base, ev_start, ev_stop));

        // Macro Timing
        CUDA_CHECK(cudaEventRecord(ev_start));
        k_macro_dsp48e2<<<blocks, threads>>>(d_dsp, d_p, count, cycles);
        CUDA_CHECK(cudaEventRecord(ev_stop));
        CUDA_CHECK(cudaEventSynchronize(ev_stop));
        float t_macro = 0;
        CUDA_CHECK(cudaEventElapsedTime(&t_macro, ev_start, ev_stop));

        float speedup = t_base / t_macro;
        double mevals = (double)(count * cycles) / (t_macro * 1000.0);

        printf("  [DSP48E2 MAC %u cycles]\n", cycles);
        printf("    Synthetic bit-loop      : %8.3f ms\n", t_base);
        printf("    Macro (64-bit native)   : %8.3f ms\n", t_macro);
        printf("    Speedup                 : %8.2fx\n", speedup);
        printf("    Throughput              : %8.2f MEvals/sec\n\n", mevals);

        if (f_csv) {
            fprintf(f_csv, "DSP48E2,%u,%u,%.3f,%.3f,%.2f,%.2f\n", count, cycles, t_base, t_macro, speedup, mevals);
        }

        CUDA_CHECK(cudaFree(d_dsp));
        CUDA_CHECK(cudaFree(d_p));
    }

    // ------------------------------------------------------------------------
    // 3. SRLC32E BENCHMARK (32-bit Shift Register LUT)
    // ------------------------------------------------------------------------
    if (mode == "all" || mode == "srl") {
        std::vector<SrlInput> h_srl(count);
        for (gem_u32 i = 0; i < count; i++) {
            h_srl[i] = SrlInput{
                static_cast<gem_u32>(static_cast<gem_u32>(rand()) & 1u),
                static_cast<gem_u32>(static_cast<gem_u32>(rand()) & 1u),
                static_cast<gem_u32>(static_cast<gem_u32>(rand()) % 32u)
            };
        }

        SrlInput *d_srl;
        gem_u64 *d_state;
        CUDA_CHECK(cudaMalloc(&d_srl, count * sizeof(SrlInput)));
        CUDA_CHECK(cudaMalloc(&d_state, count * sizeof(gem_u64)));

        CUDA_CHECK(cudaMemcpy(d_srl, h_srl.data(), count * sizeof(SrlInput), cudaMemcpyHostToDevice));

        // Baseline Timing
        CUDA_CHECK(cudaEventRecord(ev_start));
        k_baseline_srlc32e<<<blocks, threads>>>(d_srl, d_state, count, cycles);
        CUDA_CHECK(cudaEventRecord(ev_stop));
        CUDA_CHECK(cudaEventSynchronize(ev_stop));
        float t_base = 0;
        CUDA_CHECK(cudaEventElapsedTime(&t_base, ev_start, ev_stop));

        // Macro Timing
        CUDA_CHECK(cudaEventRecord(ev_start));
        k_macro_srlc32e<<<blocks, threads>>>(d_srl, d_state, count, cycles);
        CUDA_CHECK(cudaEventRecord(ev_stop));
        CUDA_CHECK(cudaEventSynchronize(ev_stop));
        float t_macro = 0;
        CUDA_CHECK(cudaEventElapsedTime(&t_macro, ev_start, ev_stop));

        float speedup = t_base / t_macro;
        double mevals = (double)(count * cycles) / (t_macro * 1000.0);

        printf("  [SRLC32E Shift LUT %u cycles]\n", cycles);
        printf("    Synthetic 32 FF + mux   : %8.3f ms\n", t_base);
        printf("    Macro (64-bit barrel)   : %8.3f ms\n", t_macro);
        printf("    Speedup                 : %8.2fx\n", speedup);
        printf("    Throughput              : %8.2f MEvals/sec\n\n", mevals);

        if (f_csv) {
            fprintf(f_csv, "SRLC32E,%u,%u,%.3f,%.3f,%.2f,%.2f\n", count, cycles, t_base, t_macro, speedup, mevals);
        }

        CUDA_CHECK(cudaFree(d_srl));
        CUDA_CHECK(cudaFree(d_state));
    }

    if (f_csv) {
        fclose(f_csv);
    }

    CUDA_CHECK(cudaEventDestroy(ev_start));
    CUDA_CHECK(cudaEventDestroy(ev_stop));
    return 0;
}
