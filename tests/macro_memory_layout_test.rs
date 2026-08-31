// Tests for Heterogeneous Macro CUDA Memory Layout Allocator

use gem::macro_layout::{MacroStorageLayout, MacroInstance, MacroKind};

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
            input_pins: vec![0, 1, 2, 3],
            output_pins: vec![100, 101, 102, 103],
            clock_pin: None,
            state_offset: None,
            io_offset: 0,
        },
        MacroInstance {
            kind: MacroKind::DSP48E2,
            instance_id: 0,
            cell_id: 11,
            input_pins: (4..52).collect(),
            output_pins: (104..152).collect(),
            clock_pin: Some(200),
            state_offset: None,
            io_offset: 0,
        },
        MacroInstance {
            kind: MacroKind::SRLC32E,
            instance_id: 0,
            cell_id: 12,
            input_pins: vec![53, 54, 55, 56, 57, 58, 59],
            output_pins: vec![153, 154],
            clock_pin: Some(200),
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
    assert_eq!(layout.carrychain_io_field_offset(0, 0), layout.carrychain_io_base);
    assert_eq!(layout.srl_io_field_offset(0, 0), layout.srl_io_base);
}
