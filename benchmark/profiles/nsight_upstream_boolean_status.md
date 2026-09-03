# Nsight upstream_boolean Profile

VERIFIED on the production simulator kernel.

- Achieved occupancy: `16.78%`
- Theoretical occupancy: `33.33%`
- Launch: `4` blocks x `256` threads, `0.10` waves/SM
- Resources: `90` registers/thread, `4352` shared bytes/block
- Uniform branch targets: `98.06%`
- Derived divergent branch targets: `1.94%`
- Predicated-on threads per instruction: `88.53%`
- DRAM peak utilization: `0.01%`
- DRAM bandwidth: `11.82 MB/s`
- Global load/store sectors per request: `11.71` / `4.20`
- Profiled kernel duration: `41.848 ms`

Metrics: `sm__warps_active.avg.pct_of_peak_sustained_active, sm__sass_average_branch_targets_threads_uniform.pct, sm__average_thread_inst_executed_pred_on_per_inst_executed_realtime.pct, sm__sass_branch_targets_threads_divergent.sum, sm__sass_branch_targets_threads_uniform.sum, dram__throughput.avg.pct_of_peak_sustained_elapsed, dram__bytes.sum, dram__bytes.sum.per_second, l1tex__average_t_sectors_per_request_pipe_lsu_mem_global_op_ld.ratio, l1tex__average_t_sectors_per_request_pipe_lsu_mem_global_op_st.ratio, gpu__time_duration.sum`

Raw counters: [benchmark/profiles/nsight_upstream_boolean.csv](nsight_upstream_boolean.csv)
