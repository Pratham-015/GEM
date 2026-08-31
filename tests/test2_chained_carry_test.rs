// SPDX-License-Identifier: Apache-2.0
// Test verifying 64-bit chained CARRY4 macros (16 cascaded blocks).

use gem::aig::AIG;
use gem::aigpdk::AIGPDKLeafPins;
use gem::macro_layout::MacroStorageLayout;
use netlistdb::{Direction, NetlistDB};
use std::path::PathBuf;

#[test]
fn test_64bit_chained_carry_topology_and_dag() {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let netlist_path = manifest_dir.join("test2/gatelevel_chained_carry.gv");

    // 1. Parse into NetlistDB
    let db = NetlistDB::from_sverilog_file(
        &netlist_path,
        Some("chained_carry_64b"),
        &AIGPDKLeafPins(),
    ).expect("Failed to parse chained_carry_64b netlist");

    println!("Parsed 64-bit Chained Carry NetlistDB:");
    println!("Cells: {}, Pins: {}, Nets: {}", db.num_cells, db.num_pins, db.num_nets);

    let mut carry4_count = 0;
    for cell_id in 1..db.num_cells {
        if db.celltypes[cell_id].as_str() == "CARRY4" {
            carry4_count += 1;
        }
    }
    assert_eq!(carry4_count, 16, "Expected exactly 16 CARRY4 macros in 64-bit adder");

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

    // 2. Build AIG
    let aig = AIG::from_netlistdb(&db);
    println!("AIG pins: {}, Primary outputs: {}", aig.num_aigpins, aig.primary_outputs.len());
    assert_eq!(aig.macros.len(), 16, "AIG must record all 16 macro instances");

    // 3. Verify Memory Layout Allocation
    let macro_instances: Vec<_> = aig.macros.values().cloned().collect();
    let layout = MacroStorageLayout::build(macro_instances);
    assert_eq!(layout.num_carrychain, 16);
    assert_eq!(layout.total_io_words % 32, 0, "Warp padding verified");
    println!("Memory layout for 16-block carry chain allocated successfully.");
}
