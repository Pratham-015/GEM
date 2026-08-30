// SPDX-License-Identifier: Apache-2.0
use gem::aig::AIG;
use gem::aigpdk::AIGPDKLeafPins;
use netlistdb::{Direction, NetlistDB};
use std::path::PathBuf;

#[test]
fn test_half_adder_netlist_and_aig_construction() {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let netlist_path = manifest_dir.join("verif/rtl/test_designs/half_adder_gatelevel.gv");

    // 1. Parse into NetlistDB
    let db = NetlistDB::from_sverilog_file(
        &netlist_path,
        Some("half_adder"),
        &AIGPDKLeafPins(),
    ).expect("Failed to parse half_adder structural netlist");

    println!("Parsed Half Adder NetlistDB: {} cells, {} pins, {} nets",
             db.num_cells, db.num_pins, db.num_nets);

    // Verify cell types
    let mut and2_count = 0;
    for cell_id in 1..db.num_cells {
        let ctype = db.celltypes[cell_id].as_str();
        if ctype.starts_with("AND2_") {
            and2_count += 1;
        }
    }
    assert_eq!(and2_count, 3, "Expected 3 AND2 cells in half_adder AIG netlist");

    // Ensure all pin directions are resolved
    for pin_id in 0..db.num_pins {
        assert_ne!(
            db.pindirect[pin_id],
            Direction::Unknown,
            "Pin {} ({:?}) has Direction::Unknown",
            pin_id,
            db.pinnames[pin_id]
        );
    }

    // 2. Build AIG from NetlistDB
    let aig = AIG::from_netlistdb(&db);
    println!("Constructed AIG with {} pins, {} primary outputs",
             aig.num_aigpins, aig.primary_outputs.len());

    assert_eq!(aig.primary_outputs.len(), 2, "Expected 2 primary outputs (Sum, Carry)");
}

