// SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

#include <crates/ulib/includes.hpp>
#include <cstdio>
#include <cooperative_groups.h>
// Word-level macro evaluation: CARRYCHAIN, DSP48E2, SRLC32E.
// Same source compiles as device code here and as host code in the CPU
// reference path, eliminating any host/device model divergence.
#include "gem_macros.cuh"
using namespace gem;

struct alignas(8) VectorRead2 {
  u32 c1, c2;

  __device__ __forceinline__ void read(const VectorRead2 *t) {
    *this = *t;
  }
};

struct alignas(16) VectorRead4 {
  u32 c1, c2, c3, c4;

  __device__ __forceinline__ void read(const VectorRead4 *t) {
    *this = *t;
  }
};

__device__ void simulate_block_v1(
  const u32 *__restrict__ script,
  usize script_size,
  const u32 *__restrict__ input_state,
  u32 *__restrict__ output_state,
  u32 *__restrict__ sram_data,
  u32 *__restrict__ shared_metadata,
  u32 *__restrict__ shared_writeouts,
  u32 *__restrict__ shared_state
  )
{
  int script_pi = 0;
  while(true) {
    VectorRead2 t2_1, t2_2;
    VectorRead4 t4_1, t4_2, t4_3, t4_4, t4_5;
    shared_metadata[threadIdx.x] = script[script_pi + threadIdx.x];
    script_pi += 256;
    t2_1.read(((const VectorRead2 *)(script + script_pi)) + threadIdx.x);
    __syncthreads();
    int num_stages = shared_metadata[0];
    if(!num_stages) {
      break;
    }
    int is_last_part = shared_metadata[1];
    int num_ios = shared_metadata[2];
    int io_offset = shared_metadata[3];
    int num_srams = shared_metadata[4];
    int sram_offset = shared_metadata[5];
    int num_global_read_rounds = shared_metadata[6];
    int num_output_duplicates = shared_metadata[7];
    u32 writeout_hook_i = shared_metadata[128 + threadIdx.x / 2];
    if(threadIdx.x % 2 == 0) {
      writeout_hook_i = writeout_hook_i & ((1 << 16) - 1);
    }
    else {
      writeout_hook_i = writeout_hook_i >> 16;
    }

    t4_1.read((const VectorRead4 *)(script + script_pi + 256 * 2 * num_global_read_rounds) + threadIdx.x);
    t4_2.read((const VectorRead4 *)(script + script_pi + 256 * 2 * num_global_read_rounds + 256 * 4) + threadIdx.x);
    t4_3.read((const VectorRead4 *)(script + script_pi + 256 * 2 * num_global_read_rounds + 256 * 4 * 2) + threadIdx.x);
    t4_4.read((const VectorRead4 *)(script + script_pi + 256 * 2 * num_global_read_rounds + 256 * 4 * 3) + threadIdx.x);
    t4_5.read((const VectorRead4 *)(script + script_pi + 256 * 2 * num_global_read_rounds + 256 * 4 * 4) + threadIdx.x);
    u32 t_global_rd_state = 0;
    for(int gr_i = 0; gr_i < num_global_read_rounds; gr_i += 2) {
      u32 idx = t2_1.c1;
      u32 mask = t2_1.c2;
      script_pi += 256 * 2;
      t2_2.read(((const VectorRead2 *)(script + script_pi)) + threadIdx.x);
      if(mask) {
        const u32 *real_input_array;
        if(idx >> 31) real_input_array = output_state - (1 << 31);
        else real_input_array = input_state;
        u32 value = real_input_array[idx];
        while(mask) {
          t_global_rd_state <<= 1;
          u32 lowbit = mask & -mask;
          if(value & lowbit) t_global_rd_state |= 1;
          mask ^= lowbit;
        }
      }

      if(gr_i + 1 >= num_global_read_rounds) break;
      idx = t2_2.c1;
      mask = t2_2.c2;
      script_pi += 256 * 2;
      t2_1.read(((const VectorRead2 *)(script + script_pi)) + threadIdx.x);
      if(mask) {
        const u32 *real_input_array;
        if(idx >> 31) real_input_array = output_state - (1 << 31);
        else real_input_array = input_state;
        u32 value = real_input_array[idx];
        while(mask) {
          t_global_rd_state <<= 1;
          u32 lowbit = mask & -mask;
          if(value & lowbit) t_global_rd_state |= 1;
          mask ^= lowbit;
        }
      }
    }
    shared_state[threadIdx.x] = t_global_rd_state;
    __syncthreads();

    for(int bs_i = 0; bs_i < num_stages; ++bs_i) {
      u32 hier_input = 0, hier_flag_xora = 0, hier_flag_xorb = 0, hier_flag_orb = 0;
#define GEMV1_SHUF_INPUT_K(k_outer, k_inner, t_shuffle) {           \
        u32 k = k_outer * 4 + k_inner;                              \
        u32 t_shuffle_1_idx = t_shuffle & ((1 << 16) - 1);          \
        u32 t_shuffle_2_idx = t_shuffle >> 16;                      \
                                                                    \
        hier_input |= (shared_state[t_shuffle_1_idx >> 5] >>        \
                       (t_shuffle_1_idx & 31) & 1) << (k * 2);      \
        hier_input |= (shared_state[t_shuffle_2_idx >> 5] >>        \
                       (t_shuffle_2_idx & 31) & 1) << (k * 2 + 1);  \
      }
#define GEMV1_SHUF_INPUT_K_4(k_outer, t_shuffle) {    \
        GEMV1_SHUF_INPUT_K(k_outer, 0, t_shuffle.c1); \
        GEMV1_SHUF_INPUT_K(k_outer, 1, t_shuffle.c2); \
        GEMV1_SHUF_INPUT_K(k_outer, 2, t_shuffle.c3); \
        GEMV1_SHUF_INPUT_K(k_outer, 3, t_shuffle.c4); \
      }
      script_pi += 256 * 4 * 5;
      GEMV1_SHUF_INPUT_K_4(0, t4_1);
      t4_1.read(((const VectorRead4 *)(script + script_pi)) + threadIdx.x);
      GEMV1_SHUF_INPUT_K_4(1, t4_2);
      t4_2.read(((const VectorRead4 *)(script + script_pi + 256 * 4)) + threadIdx.x);
      GEMV1_SHUF_INPUT_K_4(2, t4_3);
      t4_3.read(((const VectorRead4 *)(script + script_pi + 256 * 4 * 2)) + threadIdx.x);
      GEMV1_SHUF_INPUT_K_4(3, t4_4);
      t4_4.read(((const VectorRead4 *)(script + script_pi + 256 * 4 * 3)) + threadIdx.x);
#undef GEMV1_SHUF_INPUT_K
#undef GEMV1_SHUF_INPUT_K_4
      hier_flag_xora = t4_5.c1;
      hier_flag_xorb = t4_5.c2;
      hier_flag_orb = t4_5.c3;
      t4_5.read(((const VectorRead4 *)(script + script_pi + 256 * 4 * 4)) + threadIdx.x);

      __syncthreads();
      shared_state[threadIdx.x] = hier_input;
      __syncthreads();

      // hier[0]
      if(threadIdx.x >= 128) {
        u32 hier_input_a = shared_state[threadIdx.x - 128];
        u32 hier_input_b = hier_input;
        u32 ret = (hier_input_a ^ hier_flag_xora) & ((hier_input_b ^ hier_flag_xorb) | hier_flag_orb);
        shared_state[threadIdx.x] = ret;
      }
      __syncthreads();
      // hier[1..3]
      u32 tmp_cur_hi;
      for(int hi = 1; hi <= 3; ++hi) {
        int hier_width = 1 << (7 - hi);
        if(threadIdx.x >= hier_width && threadIdx.x < hier_width * 2) {
          u32 hier_input_a = shared_state[threadIdx.x + hier_width];
          u32 hier_input_b = shared_state[threadIdx.x + hier_width * 2];
          u32 ret = (hier_input_a ^ hier_flag_xora) & ((hier_input_b ^ hier_flag_xorb) | hier_flag_orb);
          tmp_cur_hi = ret;
          shared_state[threadIdx.x] = ret;
        }
        __syncthreads();
      }
      // hier[4..7], within the first warp.
      if(threadIdx.x < 32) {
        for(int hi = 4; hi <= 7; ++hi) {
          int hier_width = 1 << (7 - hi);
          u32 hier_input_a = __shfl_down_sync(0xffffffff, tmp_cur_hi, hier_width);
          u32 hier_input_b = __shfl_down_sync(0xffffffff, tmp_cur_hi, hier_width * 2);
          if(threadIdx.x >= hier_width && threadIdx.x < hier_width * 2) {
            tmp_cur_hi = (hier_input_a ^ hier_flag_xora) & ((hier_input_b ^ hier_flag_xorb) | hier_flag_orb);
          }
        }
        u32 v1 = __shfl_down_sync(0xffffffff, tmp_cur_hi, 1);
        // hier[8..12]
        if(threadIdx.x == 0) {
          u32 r8 = ((v1 << 16) ^ hier_flag_xora) & ((v1 ^ hier_flag_xorb) | hier_flag_orb) & 0xffff0000;
          u32 r9 = ((r8 >> 8) ^ hier_flag_xora) & (((r8 >> 16) ^ hier_flag_xorb) | hier_flag_orb) & 0xff00;
          u32 r10 = ((r9 >> 4) ^ hier_flag_xora) & (((r9 >> 8) ^ hier_flag_xorb) | hier_flag_orb) & 0xf0;
          u32 r11 = ((r10 >> 2) ^ hier_flag_xora) & (((r10 >> 4) ^ hier_flag_xorb) | hier_flag_orb) & 12 /* 0b1100 */;
          u32 r12 = ((r11 >> 1) ^ hier_flag_xora) & (((r11 >> 2) ^ hier_flag_xorb) | hier_flag_orb) & 2 /* 0b10 */;
          tmp_cur_hi = r8 | r9 | r10 | r11 | r12;
        }
        shared_state[threadIdx.x] = tmp_cur_hi;
      }
      __syncthreads();

      // write out
      if((writeout_hook_i >> 8) == bs_i) {
        shared_writeouts[threadIdx.x] = shared_state[writeout_hook_i & 255];
      }
    }
    __syncthreads();

    // sram & duplicate permutation
    u32 sram_duplicate_t = 0;
#define GEMV1_SHUF_SRAM_DUPL_K(k_outer, k_inner, t_shuffle) { \
      u32 k = k_outer * 4 + k_inner;                          \
      u32 t_shuffle_1_idx = t_shuffle & ((1 << 16) - 1);      \
      u32 t_shuffle_2_idx = t_shuffle >> 16;                  \
                                                              \
      sram_duplicate_t |=                                     \
        (shared_writeouts[t_shuffle_1_idx >> 5] >>            \
         (t_shuffle_1_idx & 31) & 1) << (k * 2);              \
      sram_duplicate_t |=                                     \
        (shared_writeouts[t_shuffle_2_idx >> 5] >>            \
         (t_shuffle_2_idx & 31) & 1) << (k * 2 + 1);          \
    }
#define GEMV1_SHUF_SRAM_DUPL_K_4(k_outer, t_shuffle) {  \
      GEMV1_SHUF_SRAM_DUPL_K(k_outer, 0, t_shuffle.c1); \
      GEMV1_SHUF_SRAM_DUPL_K(k_outer, 1, t_shuffle.c2); \
      GEMV1_SHUF_SRAM_DUPL_K(k_outer, 2, t_shuffle.c3); \
      GEMV1_SHUF_SRAM_DUPL_K(k_outer, 3, t_shuffle.c4); \
    }
    script_pi += 256 * 4 * 5;
    GEMV1_SHUF_SRAM_DUPL_K_4(0, t4_1);
    t4_1.read(((const VectorRead4 *)(script + script_pi)) + threadIdx.x);
    GEMV1_SHUF_SRAM_DUPL_K_4(1, t4_2);
    t4_2.read(((const VectorRead4 *)(script + script_pi + 256 * 4)) + threadIdx.x);
    GEMV1_SHUF_SRAM_DUPL_K_4(2, t4_3);
    t4_3.read(((const VectorRead4 *)(script + script_pi + 256 * 4 * 2)) + threadIdx.x);
    GEMV1_SHUF_SRAM_DUPL_K_4(3, t4_4);
    t4_4.read(((const VectorRead4 *)(script + script_pi + 256 * 4 * 3)) + threadIdx.x);
#undef GEMV1_SHUF_SRAM_DUPL_K_4
#undef GEMV1_SHUF_SRAM_DUPL_K
    sram_duplicate_t = (sram_duplicate_t & ~t4_5.c2) ^ t4_5.c1;
    t4_5.read(((const VectorRead4 *)(script + script_pi + 256 * 4 * 4)) + threadIdx.x);

    // sram read fires here.
    u32 *ram = nullptr;
    u32 r, w0;
    u32 port_w_addr_iv, port_w_wr_en, port_w_wr_data_iv;
    if(threadIdx.x < num_srams * 4) {
      u32 addrs = sram_duplicate_t;
      u32 last_tid = 32 + threadIdx.x / 32 * 32;
      u32 mask = (last_tid <= num_srams * 4)
        ? 0xffffffff : (0xffffffff >> (last_tid - num_srams * 4));
      port_w_wr_en = __shfl_down_sync(mask, sram_duplicate_t, 1);
      port_w_wr_data_iv = __shfl_down_sync(mask, sram_duplicate_t, 2);

      if(threadIdx.x % 4 == 0) {
        u32 sram_i = threadIdx.x / 4;
        u32 sram_st = sram_offset + sram_i * (1 << 13);
        // u32 sram_ed = sram_st + (1 << 13);
        u32 port_r_addr_iv = addrs & 0xffff;
        port_w_addr_iv = addrs >> 16;

        ram = sram_data + sram_st;
        r = ram[port_r_addr_iv];
        w0 = ram[port_w_addr_iv];
      }
    }
    // __syncthreads();

    // clock enable permutation
    u32 clken_perm = 0;
#define GEMV1_SHUF_CLKEN_K(k_outer, k_inner, t_shuffle) { \
      u32 k = k_outer * 4 + k_inner;                      \
      u32 t_shuffle_1_idx = t_shuffle & ((1 << 16) - 1);  \
      u32 t_shuffle_2_idx = t_shuffle >> 16;              \
                                                          \
      clken_perm |=                                       \
        (shared_writeouts[t_shuffle_1_idx >> 5] >>        \
         (t_shuffle_1_idx & 31) & 1) << (k * 2);          \
      clken_perm |=                                       \
        (shared_writeouts[t_shuffle_2_idx >> 5] >>        \
         (t_shuffle_2_idx & 31) & 1) << (k * 2 + 1);      \
    }
#define GEMV1_SHUF_CLKEN_K_4(k_outer, t_shuffle) {  \
      GEMV1_SHUF_CLKEN_K(k_outer, 0, t_shuffle.c1); \
      GEMV1_SHUF_CLKEN_K(k_outer, 1, t_shuffle.c2); \
      GEMV1_SHUF_CLKEN_K(k_outer, 2, t_shuffle.c3); \
      GEMV1_SHUF_CLKEN_K(k_outer, 3, t_shuffle.c4); \
    }
    script_pi += 256 * 4 * 5;
    GEMV1_SHUF_CLKEN_K_4(0, t4_1);
    GEMV1_SHUF_CLKEN_K_4(1, t4_2);
    GEMV1_SHUF_CLKEN_K_4(2, t4_3);
    GEMV1_SHUF_CLKEN_K_4(3, t4_4);
#undef GEMV1_SHUF_CLKEN_K
#undef GEMV1_SHUF_CLKEN_K_4

    // sram commit
    if(threadIdx.x < num_srams * 4) {
      if(threadIdx.x % 4 == 0) {
        u32 sram_i = threadIdx.x / 4;
        shared_writeouts[num_ios - num_srams + sram_i] = r;
        ram[port_w_addr_iv] = (w0 & ~port_w_wr_en) | (port_w_wr_data_iv & port_w_wr_en);
      }
    }
    else if(threadIdx.x < num_srams * 4 + num_output_duplicates) {
      shared_writeouts[num_ios - num_srams - num_output_duplicates + (threadIdx.x - num_srams * 4)] = sram_duplicate_t;
    }

    __syncthreads();
    u32 writeout_inv = shared_writeouts[threadIdx.x];

    clken_perm = (clken_perm & ~t4_5.c2) ^ t4_5.c1;
    writeout_inv ^= t4_5.c3;

    if(threadIdx.x < num_ios) {
      u32 old_wo = input_state[io_offset + threadIdx.x];
      u32 wo = (old_wo & ~clken_perm) | (writeout_inv & clken_perm);
      output_state[io_offset + threadIdx.x] = wo;
    }
    __syncthreads();

    if(is_last_part) break;
  }
  assert(script_size == script_pi);
}

__device__ __forceinline__ u32 macro_read_source(
  const u32 *__restrict__ state, u32 source)
{
  if(source & 0x80000000u) return source & 1u;
  u32 pos = source & 0x3fffffffu;
  return ((state[pos >> 5] >> (pos & 31)) & 1u) ^ ((source >> 30) & 1u);
}

__device__ __forceinline__ void macro_write_bit(
  u32 *__restrict__ state, u32 pos, u32 bit)
{
  u32 mask = 1u << (pos & 31);
  if(bit) atomicOr(state + (pos >> 5), mask);
  else atomicAnd(state + (pos >> 5), ~mask);
}

// Phase 1: gather every macro's Boolean inputs into the 64-bit SoA buffer.
// A grid barrier after this function prevents any macro output write from
// racing another macro's input gather in the same topological level.
template <u32 expected_kind>
__device__ void gather_macro_range(
  usize first_macro,
  usize num_macros,
  const u32 *__restrict__ offsets,
  const u32 *__restrict__ program,
  const u32 *__restrict__ state,
  u64 *__restrict__ io,
  u32 target_level,
  bool commit_phase)
{
  usize tid = (usize)blockIdx.x * blockDim.x + threadIdx.x;
  usize stride_threads = (usize)gridDim.x * blockDim.x;
  for(usize local_i = tid; local_i < num_macros; local_i += stride_threads) {
    usize mi = first_macro + local_i;
    const u32 *d = program + offsets[mi];
    u32 kind = d[0], io_off = d[2], io_stride = d[3];
    bool selected = commit_phase ? kind != GEM_MACRO_CARRYCHAIN
                                 : d[5] == target_level;
    if(!selected) continue;
    u32 n_in = d[6];
    // MacroStorageLayout groups descriptors by kind.  Dispatching one range
    // at a time keeps all active lanes on the same evaluator path instead of
    // mixing 1-bit carry/SRL work and 48-bit DSP work inside one warp.
    assert(kind == expected_kind);
    unsigned cohort_mask = __activemask();
    assert(__all_sync(cohort_mask, kind == expected_kind));
    gem_u64 f0 = 0, f1 = 0, f2 = 0, f3 = 0, f4 = 0;
    for(u32 k = 0; k < n_in; k += 2) {
      u32 bit = macro_read_source(state, d[7 + k]);
      u32 field_bit = d[7 + k + 1];
      if(kind == GEM_MACRO_CARRYCHAIN) {
        if(field_bit < 64u) f0 |= (gem_u64)bit << field_bit;
        else if(field_bit < 128u) f1 |= (gem_u64)bit << (field_bit - 64u);
        else f2 |= bit;
      } else if(kind == GEM_MACRO_DSP48E2) {
        if(field_bit < 27u) f0 |= (gem_u64)bit << field_bit;
        else if(field_bit < 54u) f1 |= (gem_u64)bit << (field_bit - 27u);
        else if(field_bit < 72u) f2 |= (gem_u64)bit << (field_bit - 54u);
        else if(field_bit < 120u) f3 |= (gem_u64)bit << (field_bit - 72u);
        else if(field_bit < 122u) f4 |= (gem_u64)bit << (field_bit - 120u);
        else f4 |= (gem_u64)bit << 2;
      } else {
        if(field_bit == 0u) f0 |= bit;
        else if(field_bit == 1u) f0 |= (gem_u64)bit << 1;
        else f0 |= (gem_u64)bit << field_bit;
      }
    }
    io[io_off] = f0;
    io[io_off + io_stride] = f1;
    if(kind != GEM_MACRO_SRLC32E) {
      io[io_off + 2u * io_stride] = f2;
    }
    if(kind == GEM_MACRO_DSP48E2) {
      io[io_off + 3u * io_stride] = f3;
      io[io_off + 4u * io_stride] = f4;
    }
  }
}

// Phase 2: one CUDA thread performs one native word-level macro operation.
template <u32 expected_kind>
__device__ void evaluate_macro_range(
  usize first_macro,
  usize num_macros,
  const u32 *__restrict__ offsets,
  const u32 *__restrict__ program,
  const u32 *__restrict__ edge_state,
  u32 *__restrict__ state,
  u64 *__restrict__ macro_state,
  const u64 *__restrict__ io,
  u64 *__restrict__ shared_macro_fields,
  u32 target_level,
  bool commit_phase)
{
  usize tid = (usize)blockIdx.x * blockDim.x + threadIdx.x;
  usize stride_threads = (usize)gridDim.x * blockDim.x;
  // The global I/O array is the required grid-wide exchange boundary: a
  // producer and consumer may reside in different CUDA blocks.  Once the
  // cooperative grid barrier has made it visible, stage a block tile in
  // shared memory.  This gives the native evaluators an explicit,
  // block-local global->shared->register path while preserving the SoA
  // coalescing of the global loads.  Every thread participates in both
  // barriers, including tail lanes, so partial macro cohorts cannot deadlock.
  usize rounds = (num_macros + stride_threads - 1u) / stride_threads;
  for(usize round = 0; round < rounds; ++round) {
    usize local_i = tid + round * stride_threads;
    bool active = local_i < num_macros;
    usize mi = first_macro + local_i;
    const u32 *d = active ? program + offsets[mi] : nullptr;
    u32 kind = active ? d[0] : expected_kind;
    bool selected = active && (commit_phase ? kind != GEM_MACRO_CARRYCHAIN
                                            : d[5] == target_level);
    // This ballot is part of dispatch, not a diagnostic assertion: it creates
    // the exact warp cohort for the current topological level.  Instances are
    // host-sorted by (kind, level), so almost every active warp is either fully
    // selected or fully idle, minimizing the one boundary warp per level.
    unsigned resident_mask = __activemask();
    unsigned selected_mask = __ballot_sync(resident_mask, selected);
    selected = (selected_mask & (1u << (threadIdx.x & 31u))) != 0u;
    u32 state_off = active ? d[1] : 0u;
    u32 io_off = active ? d[2] : 0u;
    u32 io_stride = active ? d[3] : 0u;
    u32 input_fields = expected_kind == GEM_MACRO_DSP48E2 ? 5u
                     : expected_kind == GEM_MACRO_CARRYCHAIN ? 3u : 1u;
    for(u32 field = 0; field < 5u; ++field) {
      shared_macro_fields[field * blockDim.x + threadIdx.x] =
        selected && field < input_fields ? io[io_off + field * io_stride] : 0ull;
    }
    shared_macro_fields[5u * blockDim.x + threadIdx.x] =
      selected && expected_kind != GEM_MACRO_CARRYCHAIN
        ? macro_state[state_off] : 0ull;
    __syncthreads();

    if(selected) {
      assert(kind == expected_kind);
      unsigned cohort_mask = __activemask();
      assert(__all_sync(cohort_mask, kind == expected_kind));
      bool clock_active = macro_read_source(edge_state, d[4]);
      u32 n_in = d[6];
      const u32 *out_desc = d + 7 + n_in;
      u32 n_out = *out_desc++;
      gem_u64 value0 = 0, value1 = 0;
      if(kind == GEM_MACRO_CARRYCHAIN) {
        u32 n_bits = 4u;
        for(u32 k = 0; k < n_in; k += 2) {
          u32 fb = d[7 + k + 1];
          if(fb < 64u && (fb + 1u) > n_bits) {
            n_bits = fb + 1u;
          }
        }
        CarryChainIn in = {
          shared_macro_fields[threadIdx.x],
          shared_macro_fields[blockDim.x + threadIdx.x],
          (gem_u32)(shared_macro_fields[2u * blockDim.x + threadIdx.x] & 1u),
          n_bits};
        CarryChainOut out = gem_eval_carrychain(in);
        value0 = out.o; value1 = out.co;
      } else if(kind == GEM_MACRO_DSP48E2) {
        gem_u64 ctrl = shared_macro_fields[4u * blockDim.x + threadIdx.x];
        Dsp48e2In in = {shared_macro_fields[threadIdx.x],
                        shared_macro_fields[blockDim.x + threadIdx.x],
                        shared_macro_fields[2u * blockDim.x + threadIdx.x],
                        shared_macro_fields[3u * blockDim.x + threadIdx.x],
                        (gem_u32)(ctrl & 3u), (gem_u32)((ctrl >> 2) & 1u)};
        gem_u64 visible = shared_macro_fields[5u * blockDim.x + threadIdx.x];
        if(commit_phase && clock_active) {
          visible = gem_eval_dsp48e2_next_p(in, visible);
          shared_macro_fields[5u * blockDim.x + threadIdx.x] = visible;
          macro_state[state_off] = visible;
        }
        value0 = visible;
      } else {
        gem_u64 ctrl = shared_macro_fields[threadIdx.x];
        gem_u64 visible = shared_macro_fields[5u * blockDim.x + threadIdx.x];
        if(commit_phase && clock_active) {
          visible = gem_eval_srlc32e_next(visible, ctrl & 1u, (ctrl >> 1) & 1u);
          shared_macro_fields[5u * blockDim.x + threadIdx.x] = visible;
          macro_state[state_off] = visible;
        }
        value0 = gem_eval_srlc32e_read(visible, (ctrl >> 2) & 31u);
      }
      for(u32 k = 0; k < n_out; k += 2) {
        u32 out_bit = out_desc[k + 1];
        u32 bit = out_bit < 64u ? ((value0 >> out_bit) & 1u)
                                : ((value1 >> (out_bit - 64u)) & 1u);
        macro_write_bit(state, out_desc[k], bit);
      }
    }
    __syncthreads();
  }
}

__global__ void simulate_v1_noninteractive_simple_scan(
  usize num_blocks,
  usize num_major_stages,
  usize num_macro_levels,
  const usize *__restrict__ blocks_start,
  const u32 *__restrict__ blocks_data,
  u32 *__restrict__ sram_data,
  usize num_cycles,
  usize state_size,
  u32 *__restrict__ states_noninteractive,
  usize num_carrychain_macros,
  usize num_dsp_macros,
  usize num_srl_macros,
  const u32 *__restrict__ macro_program_offsets,
  const u32 *__restrict__ macro_program_data,
  u64 *__restrict__ macro_state_data,
  u64 *__restrict__ macro_io_data
  )
{
  assert(num_blocks == gridDim.x);
  assert(256 == blockDim.x);
  __shared__ u32 shared_metadata[256];
  __shared__ u32 shared_writeouts[256];
  __shared__ u32 shared_state[256];
  __shared__ u32 script_starts[32], script_sizes[32];
  // Five input fields plus one state field per thread. CARRYCHAIN uses the
  // input prefix; DSP48E2/SRLC32E also stage persistent state for evaluation.
  __shared__ u64 shared_macro_fields[6 * 256];
  assert(num_major_stages <= 32);
  if(threadIdx.x < num_major_stages) {
    script_starts[threadIdx.x] = blocks_start[threadIdx.x * num_blocks + blockIdx.x];
    script_sizes[threadIdx.x] = blocks_start[threadIdx.x * num_blocks + blockIdx.x + 1] - script_starts[threadIdx.x];
  }
  __syncthreads();
  for(usize cycle_i = 0; cycle_i < num_cycles; ++cycle_i) {
    usize carry_first = 0;
    usize dsp_first = carry_first + num_carrychain_macros;
    usize srl_first = dsp_first + num_dsp_macros;

    // Preserve the unmodified Boolean-only Boomerang path exactly when no
    // heterogeneous nodes are present.
    if(srl_first + num_srl_macros == 0u) {
      for(usize stage_i = 0; stage_i < num_major_stages; ++stage_i) {
        simulate_block_v1(
          blocks_data + script_starts[stage_i], script_sizes[stage_i],
          states_noninteractive + cycle_i * state_size,
          states_noninteractive + (cycle_i + 1) * state_size,
          sram_data, shared_metadata, shared_writeouts, shared_state);
        cooperative_groups::this_grid().sync();
      }
      continue;
    }

    // VCD input frames initialize a fresh packed Boolean output row, so
    // publish the old DSP PREG values before any AIG consumer runs.  The
    // descriptor level UINT_MAX uniquely selects purely registered DSPs;
    // no input gather is needed when state is not committed.
    evaluate_macro_range<GEM_MACRO_DSP48E2>(dsp_first, num_dsp_macros,
      macro_program_offsets, macro_program_data,
      states_noninteractive + cycle_i * state_size,
      states_noninteractive + (cycle_i + 1) * state_size,
      macro_state_data, macro_io_data, shared_macro_fields, 0xffffffffu, false);
    cooperative_groups::this_grid().sync();

    // Explicit heterogeneous schedule: settle every same-cycle macro level
    // in dependency order, commit all sequential state from one snapshot, and
    // repeat the level walk so new registered outputs become visible.
    for(u32 edge_phase = 0; edge_phase < 2u; ++edge_phase) {
      for(usize macro_level = 0; macro_level <= num_macro_levels; ++macro_level) {
        for(usize stage_i = 0; stage_i < num_major_stages; ++stage_i) {
          simulate_block_v1(
            blocks_data + script_starts[stage_i],
            script_sizes[stage_i],
            states_noninteractive + cycle_i * state_size,
            states_noninteractive + (cycle_i + 1) * state_size,
            sram_data,
            shared_metadata, shared_writeouts, shared_state
            );
          cooperative_groups::this_grid().sync();
        }
        // The final AIG walk propagates the last macro level to outputs and
        // next-state inputs; there is no macro dispatch after it.
        if(macro_level == num_macro_levels) break;

        gather_macro_range<GEM_MACRO_CARRYCHAIN>(carry_first, num_carrychain_macros,
          macro_program_offsets, macro_program_data,
          states_noninteractive + (cycle_i + 1) * state_size, macro_io_data,
          (u32)macro_level, false);
        gather_macro_range<GEM_MACRO_DSP48E2>(dsp_first, num_dsp_macros,
          macro_program_offsets, macro_program_data,
          states_noninteractive + (cycle_i + 1) * state_size, macro_io_data,
          (u32)macro_level, false);
        gather_macro_range<GEM_MACRO_SRLC32E>(srl_first, num_srl_macros,
          macro_program_offsets, macro_program_data,
          states_noninteractive + (cycle_i + 1) * state_size, macro_io_data,
          (u32)macro_level, false);
        cooperative_groups::this_grid().sync();
        evaluate_macro_range<GEM_MACRO_CARRYCHAIN>(carry_first, num_carrychain_macros,
          macro_program_offsets, macro_program_data,
          states_noninteractive + cycle_i * state_size,
          states_noninteractive + (cycle_i + 1) * state_size,
          macro_state_data, macro_io_data, shared_macro_fields,
          (u32)macro_level, false);
        evaluate_macro_range<GEM_MACRO_DSP48E2>(dsp_first, num_dsp_macros,
          macro_program_offsets, macro_program_data,
          states_noninteractive + cycle_i * state_size,
          states_noninteractive + (cycle_i + 1) * state_size,
          macro_state_data, macro_io_data, shared_macro_fields,
          (u32)macro_level, false);
        evaluate_macro_range<GEM_MACRO_SRLC32E>(srl_first, num_srl_macros,
          macro_program_offsets, macro_program_data,
          states_noninteractive + cycle_i * state_size,
          states_noninteractive + (cycle_i + 1) * state_size,
          macro_state_data, macro_io_data, shared_macro_fields,
          (u32)macro_level, false);
        cooperative_groups::this_grid().sync();
      }

      if(edge_phase == 0u) {
        // Gather DSP and SRL inputs before either kind updates state.  This is
        // the single global rising edge shared by both primitive families.
        gather_macro_range<GEM_MACRO_DSP48E2>(dsp_first, num_dsp_macros,
          macro_program_offsets, macro_program_data,
          states_noninteractive + (cycle_i + 1) * state_size, macro_io_data,
          0u, true);
        gather_macro_range<GEM_MACRO_SRLC32E>(srl_first, num_srl_macros,
          macro_program_offsets, macro_program_data,
          states_noninteractive + (cycle_i + 1) * state_size, macro_io_data,
          0u, true);
        cooperative_groups::this_grid().sync();
        evaluate_macro_range<GEM_MACRO_DSP48E2>(dsp_first, num_dsp_macros,
          macro_program_offsets, macro_program_data,
          states_noninteractive + cycle_i * state_size,
          states_noninteractive + (cycle_i + 1) * state_size,
          macro_state_data, macro_io_data, shared_macro_fields, 0u, true);
        evaluate_macro_range<GEM_MACRO_SRLC32E>(srl_first, num_srl_macros,
          macro_program_offsets, macro_program_data,
          states_noninteractive + cycle_i * state_size,
          states_noninteractive + (cycle_i + 1) * state_size,
          macro_state_data, macro_io_data, shared_macro_fields, 0u, true);
        cooperative_groups::this_grid().sync();
      }
    }
  }
}
