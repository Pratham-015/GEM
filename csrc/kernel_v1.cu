// SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

#include "kernel_v1_impl.cuh"

#define checkCudaErrors(call)                                 \
  do {                                                        \
    cudaError_t err = call;                                   \
    if (err != cudaSuccess) {                                 \
      printf("CUDA error at %s %d: %s\n", __FILE__, __LINE__, \
             cudaGetErrorString(err));                        \
      exit(EXIT_FAILURE);                                     \
    }                                                         \
  } while (0)

extern "C"
void simulate_v1_noninteractive_simple_scan_cuda(
  usize num_blocks,
  usize num_major_stages,
  usize num_macro_levels,
  const usize *blocks_start,
  const u32 *blocks_data,
  u32 *sram_data,
  usize num_cycles,
  usize state_size,
  u32 *states_noninteractive,
  usize num_carrychain_macros,
  usize num_dsp_macros,
  usize num_srl_macros,
  const u32 *macro_program_offsets,
  const u32 *macro_program_data,
  u64 *macro_state_data,
  u64 *macro_io_data
  )
{
  void *arg_ptrs[16] = {
    (void *)&num_blocks, (void *)&num_major_stages, (void *)&num_macro_levels,
    (void *)&blocks_start, (void *)&blocks_data,
    (void *)&sram_data, (void *)&num_cycles, (void *)&state_size,
    (void *)&states_noninteractive,
    (void *)&num_carrychain_macros, (void *)&num_dsp_macros,
    (void *)&num_srl_macros, (void *)&macro_program_offsets,
    (void *)&macro_program_data,
    (void *)&macro_state_data, (void *)&macro_io_data
  };
  checkCudaErrors(cudaLaunchCooperativeKernel(
    (void *)simulate_v1_noninteractive_simple_scan, num_blocks, 256,
    arg_ptrs, 0, (cudaStream_t)0
    ));
}
