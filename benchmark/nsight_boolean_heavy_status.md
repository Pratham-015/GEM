# Nsight boolean_heavy Profile

VERIFIED on the production simulator kernel.

- Achieved occupancy: `16.67%`
- Theoretical occupancy: `33.33%`
- Launch: `4` blocks x `256` threads, `0.10` waves/SM
- Resources: `124` registers/thread, `16640` shared bytes/block
- Uniform branch targets: `98.11%`
- Derived divergent branch targets: `1.89%`
- Predicated-on threads per instruction: `88.61%`
- DRAM peak utilization: `0.01%`
- DRAM bandwidth: `13.55 MB/s`
- Global load/store sectors per request: `11.76` / `4.20`
- Profiled kernel duration: `41.430 ms`

Metrics: `sm__warps_active.avg.pct_of_peak_sustained_active, sm__sass_average_branch_targets_threads_uniform.pct, sm__average_thread_inst_executed_pred_on_per_inst_executed_realtime.pct, sm__sass_branch_targets_threads_divergent.sum, sm__sass_branch_targets_threads_uniform.sum, dram__throughput.avg.pct_of_peak_sustained_elapsed, dram__bytes.sum, dram__bytes.sum.per_second, l1tex__average_t_sectors_per_request_pipe_lsu_mem_global_op_ld.ratio, l1tex__average_t_sectors_per_request_pipe_lsu_mem_global_op_st.ratio, gpu__time_duration.sum`

Raw counters: [benchmark/nsight_boolean_heavy.csv](nsight_boolean_heavy.csv)
