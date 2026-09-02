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

    // 2. Build AIG
    let aig = AIG::from_netlistdb(&db);
    println!(
        "AIG pins: {}, Primary outputs: {}",
        aig.num_aigpins,
        aig.primary_outputs.len()
    );
    assert_eq!(
        aig.macros.len(),
        16,
        "AIG must record all 16 macro instances"
    );

    // Every physical bit retains its named port identity.  In particular,
    // O[0] and CO[0] must not collapse to the same anonymous output index.
    for m in aig.macros.values() {
        assert_eq!(
            m.inputs
                .iter()
                .filter(|p| p.port == MacroPort::CarryS)
                .count(),
            4
        );
        assert_eq!(
            m.inputs
                .iter()
                .filter(|p| p.port == MacroPort::CarryDI)
                .count(),
            4
        );
        assert_eq!(
            m.outputs
                .iter()
                .filter(|p| p.port == MacroPort::CarryO)
                .count(),
            4
        );
        assert_eq!(
            m.outputs
                .iter()
                .filter(|p| p.port == MacroPort::CarryCO)
                .count(),
            4
        );
        assert!(m.validate().is_ok());
    }

    // The 16 CARRY4 ripple is a true heterogeneous DAG, not merely 16 counted
    // metadata records.  Each CO[3] -> CI connection must be an explicit edge.
    let ripple_edges: Vec<_> = aig
        .macro_dependencies
        .edges
        .iter()
        .filter(|e| {
            e.producer_port == MacroPort::CarryCO
                && e.producer_bit == 3
                && e.consumer_port == MacroPort::CarryCI
                && e.timing == MacroDependencyTiming::SameCycle
        })
        .collect();
    assert_eq!(
        ripple_edges.len(),
        15,
        "missing CARRY4-to-CARRY4 dependencies"
    );
    assert_eq!(
        aig.macro_dependencies.combinational_levels.len(),
        16,
        "a 16-cell ripple must require 16 same-cycle macro levels"
    );
    assert!(aig
        .macro_dependencies
        .combinational_levels
        .iter()
        .all(|l| l.len() == 1));

    // 3. Verify Memory Layout Allocation
    let macro_instances: Vec<_> = aig.macros.values().cloned().collect();
    let layout = MacroStorageLayout::build(macro_instances);
    assert_eq!(layout.num_carrychain, 16);
    assert_eq!(layout.total_io_words % 32, 0, "Warp padding verified");
    println!("Memory layout for 16-block carry chain allocated successfully.");
}
