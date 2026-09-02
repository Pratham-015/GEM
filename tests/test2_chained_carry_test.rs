// SPDX-License-Identifier: Apache-2.0
// Test verifying 64-bit chained CARRY4 macros (16 cascaded blocks).

use gem::aig::AIG;
use gem::aigpdk::AIGPDKLeafPins;
use gem::macro_layout::MacroStorageLayout;
use gem::macro_layout::{MacroDependencyTiming, MacroPort};
use netlistdb::{Direction, NetlistDB};
use std::path::PathBuf;

#[test]
fn test_64bit_chained_carry_topology_and_dag() {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let netlist_path = manifest_dir.join("test2/chained_carry_gatelevel.gv");

    // 1. Parse into NetlistDB
    let db =
        NetlistDB::from_sverilog_file(&netlist_path, Some("chained_carry_64b"), &AIGPDKLeafPins())
            .expect("Failed to parse chained_carry_64b netlist");

    println!("Parsed 64-bit Chained Carry NetlistDB:");
    println!(
        "Cells: {}, Pins: {}, Nets: {}",
        db.num_cells, db.num_pins, db.num_nets
    );

    let mut carry4_count = 0;
    for cell_id in 1..db.num_cells {
        if db.celltypes[cell_id].as_str() == "CARRY4" {
            carry4_count += 1;
        }
    }
    assert_eq!(
        carry4_count, 16,
        "Expected exactly 16 CARRY4 macros in 64-bit adder"
    );

    // Verify all pins have resolved directions
    for pin_id in 0..db.num_pins {
        assert_ne!(
            db.pindirect[pin_id],
            Direction::Unknown,
            "Pin {} ({:?}) has Direction::Unknown",
            pin_id,
            db.pinnames[pin_id]
        );
    }

    // 2. Build AIG with CarryChain Fusion
    let aig = AIG::from_netlistdb(&db);
    println!(
        "AIG pins: {}, Primary outputs: {}",
        aig.num_aigpins,
        aig.primary_outputs.len()
    );
    assert_eq!(
        aig.macros.len(),
        2,
        "16 CARRY4 macros must be fused into 2 bounded segments (60b + 4b)"
    );

    let mut total_s_bits = 0;
    let mut total_di_bits = 0;
    let mut total_o_bits = 0;
    let mut total_co_bits = 0;

    for m in aig.macros.values() {
        total_s_bits += m.inputs.iter().filter(|p| p.port == MacroPort::CarryS).count();
        total_di_bits += m.inputs.iter().filter(|p| p.port == MacroPort::CarryDI).count();
        total_o_bits += m.outputs.iter().filter(|p| p.port == MacroPort::CarryO).count();
        total_co_bits += m.outputs.iter().filter(|p| p.port == MacroPort::CarryCO).count();
        assert!(m.validate().is_ok());
    }

    assert_eq!(total_s_bits, 64, "Total S input bits across fused segments must be 64");
    assert_eq!(total_di_bits, 64, "Total DI input bits across fused segments must be 64");
    assert_eq!(total_o_bits, 64, "Total O output bits across fused segments must be 64");
    assert_eq!(total_co_bits, 64, "Total CO output bits across fused segments must be 64");

    // The fused segments only require inter-segment dependencies at segment boundaries (bit 59 -> CI).
    let ripple_edges: Vec<_> = aig
        .macro_dependencies
        .edges
        .iter()
        .filter(|e| {
            e.producer_port == MacroPort::CarryCO
                && e.consumer_port == MacroPort::CarryCI
                && e.timing == MacroDependencyTiming::SameCycle
        })
        .collect();
    assert_eq!(
        ripple_edges.len(),
        1,
        "Fusing 16 CARRY4 blocks into two segments leaves exactly 1 inter-segment ripple edge"
    );
    assert_eq!(
        aig.macro_dependencies.combinational_levels.len(),
        2,
        "A fused 64-bit adder requires only 2 macro levels instead of 16"
    );

    // 3. Verify Memory Layout Allocation
    let macro_instances: Vec<_> = aig.macros.values().cloned().collect();
    let layout = MacroStorageLayout::build(macro_instances);
    assert_eq!(layout.num_carrychain, 2);
    assert_eq!(layout.total_io_words % 32, 0, "Warp padding verified");
    println!("Memory layout for fused carry chain allocated successfully.");
}
