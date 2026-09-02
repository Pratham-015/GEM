// SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
/// RepCut implementation

use crate::aig::{DriverType, AIG};
use crate::staging::StagedAIG;
use indexmap::{IndexMap, IndexSet};
use cachedhash::CachedHash;
use std::collections::HashMap;
use std::sync::Arc;
use std::fmt;
use rayon::prelude::*;
use rand::prelude::*;
use rand_chacha::ChaCha20Rng;

const REPCUT_HYPERGRAPH_EDGE_SIZE_LIMIT: usize = 1000;
const REPCUT_BITSET_BLOCK_SIZE: usize = 4096;

#[derive(Hash, PartialEq, Eq, Debug)]
struct EndpointSetSegment {
    bs_set: [u64; REPCUT_BITSET_BLOCK_SIZE / 64],
}
impl Default for EndpointSetSegment {
    fn default() -> Self {
        EndpointSetSegment {
            bs_set: [0; REPCUT_BITSET_BLOCK_SIZE / 64]
        }
    }
}

#[derive(Hash, PartialEq, Eq, Debug)]
struct EndpointSet {
    s: Vec<Option<Arc<CachedHash<EndpointSetSegment>>>>,
}

pub struct RCHyperGraph {
    num_vertices: usize,
    clusters: IndexMap<CachedHash<EndpointSet>, usize>,
    endpoint_weights: Vec<u64>,
}

impl EndpointSet {
    fn popcount(&self) -> usize {
        self.s.iter().map(|o| {
            match o {
                Some(ess) =>
                    ess.bs_set.iter().map(|u| u.count_ones())
                    .sum::<u32>() as usize,
                None => 0
            }
        }).sum()
    }
}

impl RCHyperGraph {
    pub fn from_staged_aig(aig: &AIG, staged: &StagedAIG) -> RCHyperGraph {
        let timer_repcut_endpoint_process = clilog::stimer!("repcut endpoint process");
        let num_blocks = (
            staged.num_endpoint_groups() + REPCUT_BITSET_BLOCK_SIZE - 1
        ) / REPCUT_BITSET_BLOCK_SIZE;
        let mut segments_blockid_nodeid = vec![
            Vec::<Option<Arc<CachedHash<EndpointSetSegment>>>>::new();
            num_blocks
        ];
        segments_blockid_nodeid.par_iter_mut().enumerate().for_each(|(i_block, vs)| {
            *vs = vec![None; aig.num_aigpins + 1];
            let endpoint_block_st = i_block * REPCUT_BITSET_BLOCK_SIZE;
            let endpoint_block_ed = staged.num_endpoint_groups()
                .min(endpoint_block_st + REPCUT_BITSET_BLOCK_SIZE);
            let mut endpoint_pins = Vec::new();
            for endpt_i in endpoint_block_st..endpoint_block_ed {
                staged.get_endpoint_group(aig, endpt_i).for_each_input(|i| {
                    endpoint_pins.push(i);
                });
            }
            let order_blk = aig.topo_traverse_generic(
                Some(&endpoint_pins),
                staged.primary_inputs.as_ref()
            );
            let mut unique_segs =
                IndexSet::<Arc<CachedHash<EndpointSetSegment>>>::new();
            let mut ess_init: HashMap<usize, EndpointSetSegment> =
                HashMap::new();
            for endpt_i in endpoint_block_st..endpoint_block_ed {
                let idx_offset = endpt_i - endpoint_block_st;
                staged.get_endpoint_group(aig, endpt_i).for_each_input(|i| {
                    let ess = ess_init.entry(i).or_default();
                    ess.bs_set[idx_offset / 64] |= 1 << (idx_offset % 64);
                });
            }
            for order_i in (0..order_blk.len()).rev() {
                let i = order_blk[order_i];
                let mut ess =
                    ess_init.remove(&i).unwrap_or_default();
                let fs = aig.fanouts_start[i];
                let fe = aig.fanouts_start[i + 1];
                for fi in fs..fe {
                    let j = aig.fanouts[fi];
                    if let Some(vj) = &mut vs[j] {
                        for bs_k in 0..REPCUT_BITSET_BLOCK_SIZE / 64 {
                            ess.bs_set[bs_k] |= vj.bs_set[bs_k];
                        }
                    }
                }
                let ess = Arc::new(
                    CachedHash::new(ess)
                );
                let (idx, _) = unique_segs.insert_full(ess);
                vs[i] = Some(unique_segs.get_index(idx).unwrap().clone());
            }
            // println!("vs: {:?}", vs);
        });
        // println!("sbn: {:?}", segments_blockid_nodeid);
        let mut clusters = IndexMap::<_, usize>::new();
        for i in 1..aig.num_aigpins {
            let es = CachedHash::new(EndpointSet {
                s: (0..num_blocks)
                    .map(|k| segments_blockid_nodeid[k][i]
                         .clone()).collect()
            });
            if es.popcount() >= 2 {
                *clusters.entry(es).or_default() += 1;
            }
        }
        clilog::finish!(timer_repcut_endpoint_process);

        let mut endpoint_pins_all = Vec::new();
        for endpt_i in 0..staged.num_endpoint_groups() {
            staged.get_endpoint_group(aig, endpt_i).for_each_input(|i| {
                endpoint_pins_all.push(i);
            });
        }
        let order_all = aig.topo_traverse_generic(
            Some(&endpoint_pins_all),
            staged.primary_inputs.as_ref()
        );
        let mut node_weights = vec![0.0f32; aig.num_aigpins + 1];
        for &i in &order_all {
            node_weights[i] = 1.;
            if let DriverType::AndGate(a, b) = aig.drivers[i] {
                if (a >> 1) != 0 {
                    node_weights[i] += node_weights[a >> 1] / ((
                        aig.fanouts_start[(a >> 1) + 1] - aig.fanouts_start[a >> 1]
                    ) as f32);
                }
                if (b >> 1) != 0 {
                    node_weights[i] += node_weights[b >> 1] / ((
                        aig.fanouts_start[(b >> 1) + 1] - aig.fanouts_start[b >> 1]
                    ) as f32);
                }
            }
        }
        let mut num_fanouts_to_endpt = vec![0usize; aig.num_aigpins + 1];
        for endpt_i in 0..staged.num_endpoint_groups() {
            staged.get_endpoint_group(aig, endpt_i).for_each_input(|i| {
                num_fanouts_to_endpt[i] += 1;
            });
        }
        let endpoint_weights = (0..staged.num_endpoint_groups()).map(|endpt_i| {
            let mut tot = 0.0;
            staged.get_endpoint_group(aig, endpt_i).for_each_input(|i| {
                tot += node_weights[i] / (num_fanouts_to_endpt[i] as f32)
            });
            (tot + 0.5) as u64
        }).collect();

        // println!("clusters: {:#?}, endpoint_weights: {:#?}", clusters, endpoint_weights);
        RCHyperGraph {
            num_vertices: staged.num_endpoint_groups(),
            clusters, endpoint_weights
        }
    }

    /// Make an edge list.
    ///
    /// (weight, node indices)
    pub fn num_vertices(&self) -> usize {
        self.num_vertices
    }

    pub fn to_edges(&self) -> Vec<(usize, Vec<usize>)> {
        self.clusters.par_iter().enumerate().map(|(i, (s, v))| {
            let mut rng = ChaCha20Rng::seed_from_u64(8026727 + i as u64);
            let mut edgend = Vec::<usize>::new();
            let mut num_prev_nodes = 0;
            for segment_i in 0..s.s.len() {
                let bs_set = match &s.s[segment_i] {
                    Some(seg) => &seg.bs_set,
                    None => continue
                };
                for bs_i in 0..REPCUT_BITSET_BLOCK_SIZE / 64 {
                    if bs_set[bs_i] == 0 {
                        continue
                    }
                    for k in 0..64 {
                        if (bs_set[bs_i] >> k & 1) != 0 {
                            let nd = segment_i * REPCUT_BITSET_BLOCK_SIZE + bs_i * 64 + k;
                            if edgend.len() < REPCUT_HYPERGRAPH_EDGE_SIZE_LIMIT {
                                edgend.push(nd);
                            }
                            else if rng.gen_range(0..num_prev_nodes) < REPCUT_HYPERGRAPH_EDGE_SIZE_LIMIT {
                                edgend[rng.gen_range(0..REPCUT_HYPERGRAPH_EDGE_SIZE_LIMIT)] = nd;
                            }
                            num_prev_nodes += 1;
                        }
                    }
                }
            }
            (*v, edgend)
        }).collect()
    }

    /// Run partition on this hypergraph.
    pub fn partition(&self, num_parts: usize) -> Vec<usize> {
        assert!(num_parts > 0, "partition count must be non-zero");
        if self.num_vertices == 0 {
            return Vec::new();
        }

        // mt-kahypar is optional in this build.  The old fallback returned
        // partition zero for every endpoint, silently defeating requested
        // parallelism and leaving all but one CUDA block idle.  Use a
        // deterministic longest-processing-time assignment instead: heavier
        // endpoint cones are placed first on the currently lightest part.
        // Partition::build_one subsequently validates every part against the
        // Boomerang PE resource limits, so this affects load balance only, not
        // simulator semantics.
        let actual_parts = num_parts.min(self.num_vertices);
        let mut order = (0..self.num_vertices).collect::<Vec<_>>();
        order.sort_by_key(|&vertex| {
            (std::cmp::Reverse(self.endpoint_weights[vertex]), vertex)
        });
        let mut loads = vec![0u64; actual_parts];
        let mut assignments = vec![0usize; self.num_vertices];
        for vertex in order {
            let part = loads
                .iter()
                .enumerate()
                .min_by_key(|&(part, load)| (*load, part))
                .unwrap()
                .0;
            assignments[vertex] = part;
            loads[part] = loads[part].saturating_add(self.endpoint_weights[vertex].max(1));
        }
        assignments
    }
}

impl fmt::Display for RCHyperGraph {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        writeln!(f, "{} {} 11", self.clusters.len(), self.endpoint_weights.len())?;
        for (v, edgend) in self.to_edges() {
            write!(f, "{}", v)?;
            for nd in edgend {
                write!(f, " {}", nd + 1)?;
            }
            writeln!(f)?;
        }
        for w in &self.endpoint_weights {
            writeln!(f, "{}", w)?;
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fallback_partitioner_uses_and_balances_requested_parts() {
        let graph = RCHyperGraph {
            num_vertices: 8,
            clusters: IndexMap::new(),
            endpoint_weights: vec![9, 8, 7, 6, 5, 4, 3, 2],
        };
        let assignments = graph.partition(4);
        assert_eq!(assignments.len(), 8);
        assert_eq!(assignments.iter().copied().max(), Some(3));
        let mut loads = vec![0u64; 4];
        for (vertex, &part) in assignments.iter().enumerate() {
            loads[part] += graph.endpoint_weights[vertex];
        }
        assert!(loads.iter().all(|&load| load > 0));
        assert!(loads.iter().max().unwrap() - loads.iter().min().unwrap() <= 3);
        assert_eq!(assignments, graph.partition(4));
    }
}
