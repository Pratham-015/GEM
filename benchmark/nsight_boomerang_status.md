# Nsight Boomerang Profile

BLOCKED: `ERR_NVGPUCTRPERM` prevents metric discovery and collection.

IMPACT: production-kernel occupancy, warp divergence, bandwidth, and coalescing remain unmeasured.

REQUIRED ACTION: enable NVIDIA performance counters and run `python3 benchmark/profile_boomerang_ncu.py`.
