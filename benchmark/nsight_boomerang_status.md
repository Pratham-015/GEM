# Nsight Boomerang Profile

BLOCKED: `ERR_NVGPUCTRPERM` prevents performance-counter access.

IMPACT: warp occupancy, branch uniformity, DRAM utilization, and global-load/store sectors per request remain unmeasured.

REQUIRED ACTION: enable non-admin NVIDIA performance counters, then run:

```shell
python3 benchmark/profile_boomerang_ncu.py
```
