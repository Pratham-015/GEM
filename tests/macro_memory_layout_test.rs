// Tests for Heterogeneous Macro CUDA Memory Layout Allocator

use gem::macro_layout::{MacroInstance, MacroKind, MacroStorageLayout};

#[test]
fn test_macro_storage_layout_empty() {
    let layout = MacroStorageLayout::build(vec![]);
    assert_eq!(layout.total_state_words, 0);
    assert_eq!(layout.total_io_words, 0);
    assert_eq!(layout.state_bytes(), 0);
    assert_eq!(layout.io_bytes(), 0);
    assert_eq!(layout.instances.len(), 0);
}

#[test]
fn test_macro_storage_layout_alignment_and_offsets() {
    let instances = vec![
        MacroInstance {
            kind: MacroKind::CarryChain,
            instance_id: 0,
            cell_id: 10,
            inputs: vec![],
            outputs: vec![],
            clock: None,
            state_offset: None,
            io_offset: 0,
        },
        MacroInstance {
            kind: MacroKind::DSP48E2,
            instance_id: 0,
            cell_id: 11,
            inputs: vec![],
            outputs: vec![],
            clock: None,
            state_offset: None,
            io_offset: 0,
        },
        MacroInstance {
            kind: MacroKind::SRLC32E,
            instance_id: 0,
            cell_id: 12,
            inputs: vec![],
            outputs: vec![],
            clock: None,
            state_offset: None,
            io_offset: 0,
        },
    ];

    let layout = MacroStorageLayout::build(instances);
    assert_eq!(layout.instances.len(), 3);
    assert_eq!(layout.num_carrychain, 1);
    assert_eq!(layout.num_dsp, 1);
    assert_eq!(layout.num_srl, 1);

    // Check that sequential state offsets are padded to 32-word warp boundaries
    assert!(layout.total_state_words >= 64);
    assert_eq!(layout.total_state_words % 32, 0);
    assert_eq!(layout.total_io_words % 32, 0);

    // Byte sizes must be 64-bit aligned (multiple of 8)
    assert_eq!(layout.state_bytes() % 8, 0);
    assert_eq!(layout.io_bytes() % 8, 0);

    // Verify field offsets
    assert_eq!(layout.dsp_io_field_offset(0, 0), layout.dsp_io_base);
    assert_eq!(
        layout.carrychain_io_field_offset(0, 0),
        layout.carrychain_io_base
    );
    assert_eq!(layout.srl_io_field_offset(0, 0), layout.srl_io_base);
}

#[test]
fn test_multiple_stateful_instances_do_not_alias() {
    let make = |kind, cell_id| MacroInstance {
        kind,
        instance_id: 0,
        cell_id,
        inputs: vec![],
        outputs: vec![],
        clock: None,
        state_offset: None,
        io_offset: 0,
    };
    let layout = MacroStorageLayout::build(vec![
        make(MacroKind::SRLC32E, 30),
        make(MacroKind::DSP48E2, 20),
        make(MacroKind::DSP48E2, 21),
        make(MacroKind::SRLC32E, 31),
        make(MacroKind::CarryChain, 10),
        make(MacroKind::CarryChain, 11),
    ]);
    let mut state_offsets: Vec<_> = layout
        .instances
        .iter()
        .filter_map(|m| m.state_offset)
        .collect();
    state_offsets.sort_unstable();
    state_offsets.dedup();
    assert_eq!(
        state_offsets.len(),
        4,
        "DSP/SRL persistent states must not alias"
    );
    assert_eq!(
        layout
            .instances
            .iter()
            .map(|m| m.kind as u32)
            .collect::<Vec<_>>(),
        vec![0, 0, 1, 1, 2, 2],
        "program order must be kind-grouped for SoA access"
    );
    for kind in [
        MacroKind::CarryChain,
        MacroKind::DSP48E2,
        MacroKind::SRLC32E,
    ] {
        assert_eq!(layout.io_stride(kind) % 32, 0);
    }
}

#[test]
fn test_warp_scale_soa_addresses_are_contiguous_and_non_overlapping() {
    let make = |kind, cell_id| MacroInstance {
        kind,
        instance_id: 0,
        cell_id,
        inputs: vec![],
        outputs: vec![],
        clock: None,
        state_offset: None,
        io_offset: 0,
    };
    let mut instances = Vec::new();
    for id in 0..65 {
        instances.push(make(MacroKind::CarryChain, 1000 + id));
        instances.push(make(MacroKind::DSP48E2, 2000 + id));
        instances.push(make(MacroKind::SRLC32E, 3000 + id));
    }
    let layout = MacroStorageLayout::build(instances);

    // 65 lanes round to three complete warps.  For every field, adjacent
    // instance IDs must be adjacent u64 addresses; fields must be separated by
    // exactly the padded stride and kind sections must never overlap.
    for kind in [
        MacroKind::CarryChain,
        MacroKind::DSP48E2,
        MacroKind::SRLC32E,
    ] {
        assert_eq!(layout.io_stride(kind), 96);
        for field in 0..kind.io_words_per_instance() {
            let offsets: Vec<_> = (0..65)
                .map(|id| match kind {
                    MacroKind::CarryChain => layout.carrychain_io_field_offset(id, field),
                    MacroKind::DSP48E2 => layout.dsp_io_field_offset(id, field),
                    MacroKind::SRLC32E => layout.srl_io_field_offset(id, field),
                })
                .collect();
            assert!(offsets.windows(2).all(|pair| pair[1] == pair[0] + 1));
        }
    }
    assert_eq!(layout.carrychain_io_base % 32, 0);
    assert_eq!(layout.dsp_io_base % 32, 0);
    assert_eq!(layout.srl_io_base % 32, 0);
    assert!(layout.carrychain_io_base < layout.dsp_io_base);
    assert!(layout.dsp_io_base < layout.srl_io_base);
    assert_eq!(layout.total_io_words % 32, 0);
}
