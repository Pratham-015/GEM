// SPDX-License-Identifier: Apache-2.0
// Integration test verifying Deliverables A & B on the test2 heterogeneous circuit.
// Python counterpart: test2/heterogeneous_integration_check.py
//   Runs Yosys synthesis (test2/heterogeneous_integration_synth.ys) to produce
//   the .gv file loaded here and validates macro cell counts in the netlist.

use gem::aig::AIG;
use gem::aigpdk::AIGPDKLeafPins;
use gem::macro_layout::{MacroKind, MacroPort, MacroStorageLayout};
use netlistdb::{Direction, NetlistDB};
use std::path::PathBuf;

#[test]
fn test_heterogeneous_pipeline_integration() {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let netlist_path = manifest_dir.join("test2/heterogeneous_integration_gatelevel.gv");

    // 1. Parse into NetlistDB
    let db = NetlistDB::from_sverilog_file(&netlist_path, Some("mixed_circuit"), &AIGPDKLeafPins())
        .expect("Failed to parse test2 mixed_circuit structural netlist");

    println!("=== Parsed test2 NetlistDB ===");
    println!(
        "Cells: {}, Pins: {}, Nets: {}",
        db.num_cells, db.num_pins, db.num_nets
    );

    // Verify all pins have resolved directions (no Direction::Unknown)
    for pin_id in 0..db.num_pins {
        assert_ne!(
            db.pindirect[pin_id],
            Direction::Unknown,
            "Pin {} ({:?}) has Direction::Unknown!",
            pin_id,
            db.pinnames[pin_id]
        );
    }

    // Verify all macro cell types are present in the NetlistDB
    let mut found_carry4 = false;
    let mut found_dsp = false;
    let mut found_srl = false;
    let mut and2_count = 0;
    let mut dff_count = 0;

    for cell_id in 1..db.num_cells {
        let ctype = db.celltypes[cell_id].as_str();
        if ctype == "CARRY4" {
            found_carry4 = true;
        } else if ctype == "GEM_DSP48E2" {
            found_dsp = true;
        } else if ctype == "SRLC32E" {
            found_srl = true;
        } else if ctype == "DFF" {
            dff_count += 1;
        } else if ctype.starts_with("AND2_") {
            and2_count += 1;
        }
    }

    assert!(found_carry4, "CARRY4 macro missing in NetlistDB");
    assert!(found_dsp, "DSP48E2 macro missing in NetlistDB");
    assert!(found_srl, "SRLC32E macro missing in NetlistDB");
    assert_eq!(dff_count, 4, "Expected 4 DFF cells");
    assert!(
        and2_count >= 15,
        "Expected >= 15 AIG cells for glue logic, found {}",
        and2_count
    );

    // 2. Build AIG graph with macro integration
    let aig = AIG::from_netlistdb(&db);
    println!("=== Constructed AIG Graph ===");
    println!(
        "AIG pins: {}, Primary outputs: {}",
        aig.num_aigpins,
        aig.primary_outputs.len()
    );

    let carry = aig
        .macros
        .values()
        .find(|m| m.kind == MacroKind::CarryChain)
        .unwrap();
    assert_eq!(carry.inputs.len(), 10);
    assert_eq!(carry.outputs.len(), 8);
    assert_eq!(
        carry
            .inputs
            .iter()
            .find(|p| p.port == MacroPort::CarryCYINIT)
            .unwrap()
            .signal_iv,
        0,
        "literal zero must survive frontend conversion"
    );

    let dsp = aig
        .macros
        .values()
        .find(|m| m.kind == MacroKind::DSP48E2)
        .unwrap();
    assert_eq!(
        dsp.inputs
            .iter()
            .filter(|p| p.port == MacroPort::DspA)
            .count(),
        27
    );
    assert_eq!(
        dsp.inputs
            .iter()
            .filter(|p| p.port == MacroPort::DspB)
            .count(),
        18
    );
    assert_eq!(
        dsp.inputs
            .iter()
            .filter(|p| p.port == MacroPort::DspC)
            .count(),
        48
    );
    assert_eq!(
        dsp.inputs
            .iter()
            .filter(|p| p.port == MacroPort::DspD)
            .count(),
        27
    );
    assert_eq!(
        dsp.outputs
            .iter()
            .filter(|p| p.port == MacroPort::DspP)
            .count(),
        48
    );
    assert!(dsp.clock.is_some());

    let srl = aig
        .macros
        .values()
        .find(|m| m.kind == MacroKind::SRLC32E)
        .unwrap();
    assert_eq!(
        srl.inputs
            .iter()
            .filter(|p| p.port == MacroPort::SrlA)
            .count(),
        5
    );
    assert!(srl.outputs.iter().any(|p| p.port == MacroPort::SrlQ));
    assert!(srl.outputs.iter().any(|p| p.port == MacroPort::SrlQ31));
    assert!(srl.clock.is_some());

    // 3. Build 64-bit aligned MacroStorageLayout
    let macro_instances: Vec<_> = aig.macros.values().cloned().collect();
    let layout = MacroStorageLayout::build(macro_instances);

    println!("=== Macro Memory Layout ===");
    println!("Total state words (u64): {}", layout.total_state_words);
    println!("Total I/O words (u64): {}", layout.total_io_words);
    println!("DSP instances: {}", layout.num_dsp);
    println!("CarryChain instances: {}", layout.num_carrychain);
    println!("SRLC32E instances: {}", layout.num_srl);

    assert_eq!(layout.num_carrychain, 1);
    assert_eq!(layout.num_dsp, 1);
    assert_eq!(layout.num_srl, 1);
    assert_eq!(
        layout.state_bytes() % 8,
        0,
        "State buffer must be 64-bit aligned"
    );
    assert_eq!(
        layout.io_bytes() % 8,
        0,
        "I/O buffer must be 64-bit aligned"
    );
    assert_eq!(
        layout.total_state_words % 32,
        0,
        "State words must be warp-padded"
    );
    assert_eq!(
        layout.total_io_words % 32,
        0,
        "I/O words must be warp-padded"
    );

    println!("Host macro graph and storage-layout checks passed; production CUDA execution is verified separately by verif/integrated_macro_test.py");
}
