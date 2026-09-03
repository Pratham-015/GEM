# Nsight occupancy_stress Profile

VERIFIED on the production simulator kernel.

- Achieved occupancy: `33.29%`
- Theoretical occupancy: `33.33%`
- Launch: `40` blocks x `256` threads, `1.00` waves/SM
- Resources: `124` registers/thread, `16640` shared bytes/block
- Uniform branch targets: `99.16%`
- Derived divergent branch targets: `0.84%`
- Predicated-on threads per instruction: `73.26%`
- DRAM peak utilization: `0.01%`
- DRAM bandwidth: `10.22 MB/s`
- Global load/store sectors per request: `5.22` / `4.06`
- Profiled kernel duration: `141.798 ms`

Metrics: `sm__warps_active.avg.pct_of_peak_sustained_active, sm__sass_average_branch_targets_threads_uniform.pct, sm__average_thread_inst_executed_pred_on_per_inst_executed_realtime.pct, sm__sass_branch_targets_threads_divergent.sum, sm__sass_branch_targets_threads_uniform.sum, dram__throughput.avg.pct_of_peak_sustained_elapsed, dram__bytes.sum, dram__bytes.sum.per_second, l1tex__average_t_sectors_per_request_pipe_lsu_mem_global_op_ld.ratio, l1tex__average_t_sectors_per_request_pipe_lsu_mem_global_op_st.ratio, gpu__time_duration.sum`

Raw counters: [benchmark/nsight/nsight_occupancy_stress_40b.csv](nsight_occupancy_stress_40b.csv)
