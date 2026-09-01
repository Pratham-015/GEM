// SPDX-License-Identifier: Apache-2.0
use gem::aigpdk::AIGPDKLeafPins;
use netlistdb::{Direction, NetlistDB};
use std::path::PathBuf;

#[test]
fn test_parse_macro_gatelevel_netlist() {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let netlist_path = manifest_dir.join("test3/flowB_macropreserve_gatelevel.gv");

    let db = NetlistDB::from_sverilog_file(
        &netlist_path,
        Some("signal_processor"),
        &AIGPDKLeafPins(),
    ).expect("Failed to parse structural netlist with macros");

    println!("Parsed NetlistDB with {} cells, {} pins, {} nets",
             db.num_cells, db.num_pins, db.num_nets);

    // Check that cells are recognized
    let mut found_dsp = false;
    let mut found_carry4 = false;
    let mut found_srlc32e = false;
    let mut found_dff = false;
    let mut found_and = false;

    for cell_id in 1..db.num_cells {
        let ctype = db.celltypes[cell_id].as_str();
        match ctype {
            "DSP48E2" => found_dsp = true,
            "CARRY4" => found_carry4 = true,
            "SRLC32E" => found_srlc32e = true,
            "DFF" => found_dff = true,
            "AND2_00_0" => found_and = true,
            _ => {}
        }
    }

    assert!(found_dsp, "DSP48E2 cell was not found in netlistdb");
    assert!(found_carry4, "CARRY4 cell was not found in netlistdb");
    assert!(found_srlc32e, "SRLC32E cell was not found in netlistdb");
    assert!(found_dff, "DFF cell was not found in netlistdb");
    assert!(found_and, "AND2_00_0 cell was not found in netlistdb");

    // Check that no pin direction is Unknown
    for pin_id in 0..db.num_pins {
        assert_ne!(
            db.pindirect[pin_id],
            Direction::Unknown,
            "Pin {} ({:?}) has Direction::Unknown",
            pin_id,
            db.pinnames[pin_id]
        );
    }
}

