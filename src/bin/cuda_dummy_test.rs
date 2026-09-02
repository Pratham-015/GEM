// SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
//! this binary only measures performance for 10000 cycles. it does not
//! input or output actual VCD.

use gem::aig::{DriverType, AIG};
use gem::aigpdk::AIGPDKLeafPins;
use gem::flatten::FlattenedScriptV1;
use gem::pe::Partition;
use gem::staging::build_staged_aigs;
use netlistdb::NetlistDB;
use std::path::PathBuf;
use std::time::Instant;
use ulib::{AsUPtr, AsUPtrMut, Device, UVec};

#[derive(clap::Parser, Debug)]
struct SimulatorArgs {
    /// Gate-level verilog path synthesized in our provided library.
    ///
    /// If your design is still at RTL level, you should synthesize it
    /// in yosys first.
    netlist_verilog: PathBuf,
    /// Top module type in netlist to analyze.
    ///
    /// If not specified, we will guess it from the hierarchy.
    #[clap(long)]
    top_module: Option<String>,
    /// Level split thresholds.
    #[clap(long, value_delimiter = ',')]
    level_split: Vec<usize>,
    /// Input path for the serialized partitions.
    gemparts: PathBuf,
    /// the number of CUDA blocks to map and execute with.
    ///
    /// should not exceed GPU maximum simutaneous occupancy.
    num_blocks: usize,
    /// the number of dummy cycles to execute.
    num_dummy_cycles: usize,
    /// Number of untimed production-kernel launches before measurement.
    #[clap(long, default_value_t = 1)]
    warmup_runs: usize,
    /// Number of independently reset, timed production-kernel launches.
    #[clap(long, default_value_t = 1)]
    repetitions: usize,
    /// Deterministic seed used to populate primary-input and clock-flag bits.
    #[clap(long, default_value_t = 1)]
    seed: u64,
}

mod ucci {
    include!(concat!(env!("OUT_DIR"), "/uccbind/kernel_v1.rs"));
}

fn benchmark_input_states(script: &FlattenedScriptV1, num_cycles: usize, seed: u64) -> Vec<u32> {
    let state_words = script.reg_io_state_size as usize;
    let mut states = vec![0u32; state_words * (num_cycles + 1)];
    if seed == 0 {
        return states;
    }
    let mut input_positions = script.input_map.values().copied().collect::<Vec<_>>();
    input_positions.sort_unstable();
    input_positions.dedup();
    let mut rng = seed;
    for cycle in 0..=num_cycles {
        for &position in &input_positions {
            // xorshift64*: deterministic, inexpensive, and independent of the
            // host rand crate/version. Only true primary inputs and synthesized
            // clock-edge flags are initialized; macro outputs remain zero until
            // the production kernel publishes them.
            rng ^= rng >> 12;
            rng ^= rng << 25;
            rng ^= rng >> 27;
            let bit = (rng.wrapping_mul(0x2545_f491_4f6c_dd1d) >> 63) as u32;
            if bit != 0 {
                let position = position as usize;
                states[cycle * state_words + (position >> 5)] |= 1u32 << (position & 31);
            }
        }
    }
    states
}

fn main() {
    clilog::init_stderr_color_debug();
    clilog::enable_timer("cuda_dummy_test");
    clilog::enable_timer("gem");
    clilog::set_max_print_count(clilog::Level::Warn, "NL_SV_LIT", 1);
    let args = <SimulatorArgs as clap::Parser>::parse();
    clilog::info!("Simulator args:\n{:#?}", args);

    let netlistdb = NetlistDB::from_sverilog_file(
        &args.netlist_verilog,
        args.top_module.as_deref(),
        &AIGPDKLeafPins(),
    )
    .expect("cannot build netlist");

    let aig = AIG::from_netlistdb(&netlistdb);

    // print some statistics for listing
    let order = aig.topo_traverse_generic(None, None);
    let mut level_id = vec![0; aig.num_aigpins + 1];
    for &i in &order {
        if let DriverType::AndGate(a, b) = aig.drivers[i] {
            if a >= 2 {
                level_id[i] = level_id[i].max(level_id[a >> 1] + 1);
            }
            if b >= 2 {
                level_id[i] = level_id[i].max(level_id[b >> 1] + 1);
            }
        }
    }
    let max_level = level_id.iter().copied().max().unwrap();
    println!(
        "netlist has {} pins, {} aig pins, {} and gates",
        netlistdb.num_pins,
        aig.num_aigpins,
        aig.and_gate_cache.len()
    );
    println!("netlist logic depth: {}", max_level);

    let stageds = build_staged_aigs(&aig, &args.level_split);

    let f = std::fs::File::open(&args.gemparts).unwrap();
    let mut buf = std::io::BufReader::new(f);
    let parts_in_stages: Vec<Vec<Partition>> = serde_bare::from_reader(&mut buf).unwrap();
    clilog::info!(
        "# of effective partitions in each stage: {:?}",
        parts_in_stages
            .iter()
            .map(|ps| ps.len())
            .collect::<Vec<_>>()
    );

    let mut input_layout = Vec::new();
    for (i, driv) in aig.drivers.iter().enumerate() {
        if let DriverType::InputPort(_)
        | DriverType::InputClockFlag(_, _)
        | DriverType::Macro(_, _, _) = driv
        {
            input_layout.push(i);
        }
    }

    let mut script = FlattenedScriptV1::from(
        &aig,
        &stageds
            .iter()
            .map(|(_, _, staged)| staged)
            .collect::<Vec<_>>(),
        &parts_in_stages
            .iter()
            .map(|ps| ps.as_slice())
            .collect::<Vec<_>>(),
        args.num_blocks,
        input_layout,
    );

    use std::collections::hash_map::DefaultHasher;
    use std::hash::{Hash, Hasher};
    let mut s = DefaultHasher::new();
    script.blocks_data.hash(&mut s);
    println!("Script hash: {}", s.finish());

    // do simulation
    clilog::info!("total number of cycles: {}", args.num_dummy_cycles);
    let device = Device::CUDA(0);
    assert!(args.repetitions > 0, "--repetitions must be positive");
    let input_states = benchmark_input_states(&script, args.num_dummy_cycles, args.seed);
    let mut input_hasher = DefaultHasher::new();
    input_states.hash(&mut input_hasher);
    println!("Benchmark input hash: {}", input_hasher.finish());
    let mut input_states_uvec: UVec<_> = input_states.clone().into();
    input_states_uvec.as_mut_uptr(device);
    let mut sram_storage = UVec::new_zeroed(script.sram_storage_size as usize, device);
    script
        .validate_macro_abi()
        .unwrap_or_else(|e| panic!("invalid macro CUDA ABI: {e}"));
    script.macro_state_data.as_mut_uptr(device);
    script.macro_io_data.as_mut_uptr(device);
    script.macro_program_offsets.as_mut_uptr(device);
    script.macro_program_data.as_mut_uptr(device);
    assert_eq!(
        script.macro_state_data.as_uptr(device) as usize % std::mem::align_of::<u64>(),
        0,
        "macro state device buffer is not 64-bit aligned"
    );
    assert_ne!(script.macro_state_data.as_uptr(device) as usize, 0);
    assert_eq!(
        script.macro_io_data.as_uptr(device) as usize % std::mem::align_of::<u64>(),
        0,
        "macro I/O device buffer is not 64-bit aligned"
    );
    assert_ne!(script.macro_io_data.as_uptr(device) as usize, 0);
    device.synchronize();
    for warmup in 0..args.warmup_runs {
        ucci::simulate_v1_noninteractive_simple_scan(
            args.num_blocks,
            script.num_major_stages,
            script.num_macro_levels,
            &script.blocks_start,
            &script.blocks_data,
            &mut sram_storage,
            args.num_dummy_cycles,
            script.reg_io_state_size as usize,
            &mut input_states_uvec,
            script.macro_storage.num_carrychain,
            script.macro_storage.num_dsp,
            script.macro_storage.num_srl,
            &script.macro_program_offsets,
            &script.macro_program_data,
            &mut script.macro_state_data,
            &mut script.macro_io_data,
            device,
        );
        device.synchronize();
        println!(
            "GEM_BENCH_WARMUP run={} cycles={}",
            warmup, args.num_dummy_cycles
        );
    }

    for repetition in 0..args.repetitions {
        // Reset outside the measured interval. This makes every sample start
        // from identical primary inputs, SRAM, DSP PREG, and SRL state.
        input_states_uvec = input_states.clone().into();
        input_states_uvec.as_mut_uptr(device);
        sram_storage = UVec::new_zeroed(script.sram_storage_size as usize, device);
        script.macro_state_data =
            UVec::new_zeroed(script.macro_storage.total_state_words.max(1), device);
        script.macro_io_data = UVec::new_zeroed(script.macro_storage.total_io_words.max(1), device);
        device.synchronize();

        let start = Instant::now();
        ucci::simulate_v1_noninteractive_simple_scan(
            args.num_blocks,
            script.num_major_stages,
            script.num_macro_levels,
            &script.blocks_start,
            &script.blocks_data,
            &mut sram_storage,
            args.num_dummy_cycles,
            script.reg_io_state_size as usize,
            &mut input_states_uvec,
            script.macro_storage.num_carrychain,
            script.macro_storage.num_dsp,
            script.macro_storage.num_srl,
            &script.macro_program_offsets,
            &script.macro_program_data,
            &mut script.macro_state_data,
            &mut script.macro_io_data,
            device,
        );
        device.synchronize();
        let elapsed = start.elapsed();
        let elapsed_ms = elapsed.as_secs_f64() * 1000.0;
        let cycles_per_second = args.num_dummy_cycles as f64 / elapsed.as_secs_f64();
        println!(
            "GEM_BENCH_SAMPLE repetition={} cycles={} elapsed_ms={:.6} cycles_per_second={:.3}",
            repetition, args.num_dummy_cycles, elapsed_ms, cycles_per_second
        );
    }
}
