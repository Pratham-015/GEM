// SPDX-License-Identifier: Apache-2.0
//! 64-bit aligned heterogeneous memory layout for GPU macro evaluation.
//!
//! Word-level hardware macros (DSP48E2, CARRYCHAIN, SRLC32E) require
//! 64-bit aligned memory, distinct from the bit-packed u32 boolean state.
//! This module defines the layout allocator that computes per-macro
//! VRAM offsets and sizes with 32-word (warp) padding for coalesced
//! LDG.E.64 / STG.E.64 transactions.

use serde::{Deserialize, Serialize};

/// The kind of hardware macro.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum MacroKind {
    /// Fused CARRY4 carry chain — combinational (COMB).
    /// Evaluates S/DI/CIN → O/CO via a single 64-bit add.
    CarryChain,
    /// DSP48E2 simplified subset — sequential (SEQ), PREG=1.
    /// Only P (48-bit register) is clocked; pure next-state function.
    DSP48E2,
    /// SRLC32E 32-bit shift register LUT — combinational (COMB).
    /// Q is a combinational read of state[A]; state update is clocked.
    SRLC32E,
}

impl MacroKind {
    /// Returns true if this macro needs a combinational dispatch barrier
    /// (i.e. its output is consumed by downstream boolean logic in the
    /// same cycle, requiring a mid-cycle evaluation pass).
    pub fn is_combinational(self) -> bool {
        matches!(self, MacroKind::CarryChain | MacroKind::SRLC32E)
    }

    /// Number of 64-bit words in the per-cycle I/O buffer per instance.
    ///
    /// Layout:
    /// - CarryChain : [s, di, cin_n (packed), o, co] = 5 words, rounded to 8
    /// - DSP48E2    : [a, d, b, c, state_usepre (packed), p_out] = 6 words, rounded to 8
    /// - SRLC32E    : [d_ce_a (packed), q_q31 (packed)] = 2 words, rounded to 4
    pub fn io_words_per_instance(self) -> usize {
        match self {
            MacroKind::CarryChain => 8,
            MacroKind::DSP48E2   => 8,
            MacroKind::SRLC32E   => 4,
        }
    }

    /// Number of 64-bit words in the persistent state per instance.
    /// Only sequential macros have state (SRLC32E shift register, DSP P reg).
    /// COMB macros (CarryChain) return 0.
    pub fn state_words_per_instance(self) -> usize {
        match self {
            MacroKind::CarryChain => 0,
            MacroKind::DSP48E2   => 1,  // 48-bit P register
            MacroKind::SRLC32E   => 1,  // 32-bit shift register
        }
    }
}

/// A single macro instance with its assigned memory layout offsets.
///
/// Input/output AIG pin indices are stored here for the flattener to
/// build permutation tables pointing into the global boolean state.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MacroInstance {
    /// Kind of this macro.
    pub kind: MacroKind,
    /// Unique index of this instance within the `MacroStorageLayout`.
    pub instance_id: usize,
    /// Cell ID in the NetlistDB / AIG.
    pub cell_id: usize,
    /// AIG pin indices (without invert bit) for the word-level input ports.
    /// The order matches the evaluation function's argument layout:
    /// - CarryChain: [s_aigpin, di_aigpin, cin_aigpin, n_value]
    /// - DSP48E2   : [a_aigpin, d_aigpin, b_aigpin, c_aigpin, state_aigpin, use_pre_aigpin]
    /// - SRLC32E   : [d_aigpin, ce_aigpin, a0..a4_aigpins (5 bits)]
    pub input_pins: Vec<usize>,
    /// AIG pin indices (without invert bit) for word-level output ports.
    /// - CarryChain: [o_aigpin, co_aigpin]
    /// - DSP48E2   : [p_aigpin]
    /// - SRLC32E   : [q_aigpin, q31_aigpin]
    pub output_pins: Vec<usize>,
    /// AIG pin index for the clock (if sequential).
    pub clock_pin: Option<usize>,
    /// Offset (in 64-bit words) into the macro state buffer.
    /// `None` for combinational macros (CarryChain).
    /// Populated by `MacroStorageLayout::build`.
    pub state_offset: Option<usize>,
    /// Offset (in 64-bit words) into the per-cycle macro I/O buffer.
    /// Populated by `MacroStorageLayout::build`.
    pub io_offset: usize,
}

/// Global 64-bit memory layout descriptor for all macros in the design.
///
/// Memory is partitioned into two buffers in GPU VRAM:
///
/// ```text
/// macro_state_data[total_state_words]:  u64
///   [0..32)     DSP48E2 P registers   (instances 0..31, lane = instance % 32)
///   [32..64)    DSP48E2 P registers   (instances 32..63, ...)
///   ...         (padded to 32-word warp boundaries)
///   [dsp_end)   SRLC32E shift regs    (same warp-padded structure)
///
/// macro_io_data[total_io_words]:  u64
///   Per-cycle input and output buffers, also warp-padded.
///   CarryChain (8 words/instance * ceil(num_cc / 32) warps) first,
///   then DSP48E2 (8 words/instance), then SRLC32E (4 words/instance).
/// ```
///
/// Within each section, the layout is **Structure-of-Arrays** (SoA) per warp
/// of 32 instances. Thread `i` in the warp accesses element `i` of its
/// section contiguously, ensuring a single 128-byte (2 × LDG.E.64 × 32
/// threads) transaction per warp per macro field.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct MacroStorageLayout {
    /// Total 64-bit words in the persistent state buffer.
    pub total_state_words: usize,
    /// Total 64-bit words in the per-cycle I/O buffer.
    pub total_io_words: usize,

    // ---- state section bases ----
    /// Base offset (u64 words) of DSP48E2 P registers in state buffer.
    pub dsp_state_base: usize,
    /// Base offset (u64 words) of SRLC32E shift registers in state buffer.
    pub srl_state_base: usize,

    // ---- I/O section bases ----
    /// Base offset (u64 words) of CarryChain I/O slots.
    pub carrychain_io_base: usize,
    /// Base offset (u64 words) of DSP48E2 I/O slots.
    pub dsp_io_base: usize,
    /// Base offset (u64 words) of SRLC32E I/O slots.
    pub srl_io_base: usize,

    // ---- instance counts ----
    pub num_dsp: usize,
    pub num_carrychain: usize,
    pub num_srl: usize,

    /// All instances with fully populated offsets.
    pub instances: Vec<MacroInstance>,
}

impl MacroStorageLayout {
    /// Round `count` up to the next multiple of `WARP` (= 32).
    const WARP: usize = 32;
    fn warp_pad(count: usize) -> usize {
        (count + Self::WARP - 1) / Self::WARP * Self::WARP
    }

    /// Build the layout from a list of raw macro instances (offsets are
    /// computed here and stored back into the returned instances).
    pub fn build(mut instances: Vec<MacroInstance>) -> MacroStorageLayout {
        let mut num_dsp = 0usize;
        let mut num_carrychain = 0usize;
        let mut num_srl = 0usize;

        // Assign per-kind indices
        for inst in &mut instances {
            match inst.kind {
                MacroKind::DSP48E2   => { inst.instance_id = num_dsp;        num_dsp += 1; }
                MacroKind::CarryChain => { inst.instance_id = num_carrychain; num_carrychain += 1; }
                MacroKind::SRLC32E   => { inst.instance_id = num_srl;         num_srl += 1; }
            }
        }

        // ---- State buffer layout ----
        // DSP state section: warp_pad(num_dsp) words
        let dsp_state_base = 0;
        let dsp_state_words = Self::warp_pad(num_dsp);
        // SRLC32E state section: warp_pad(num_srl) words
        let srl_state_base = dsp_state_base + dsp_state_words;
        let srl_state_words = Self::warp_pad(num_srl);
        let total_state_words = srl_state_base + srl_state_words;

        // ---- I/O buffer layout ----
        // Each macro kind uses (io_words_per_instance * warp_pad(count)) words
        // in its section, with instances interleaved: instance 0 in slot 0,
        // instance 1 in slot 1, ..., forming SoA per field within each warp.
        //
        // We layout fields per-warp:
        //   section_base + field_word * warp_pad(n) + instance_id
        //
        // CarryChain: 8 fields × warp_pad(num_cc) words
        let carrychain_io_base = 0;
        let carrychain_io_words = MacroKind::CarryChain.io_words_per_instance() * Self::warp_pad(num_carrychain);
        // DSP48E2: 8 fields × warp_pad(num_dsp) words
        let dsp_io_base = carrychain_io_base + carrychain_io_words;
        let dsp_io_words = MacroKind::DSP48E2.io_words_per_instance() * Self::warp_pad(num_dsp);
        // SRLC32E: 4 fields × warp_pad(num_srl) words
        let srl_io_base = dsp_io_base + dsp_io_words;
        let srl_io_words = MacroKind::SRLC32E.io_words_per_instance() * Self::warp_pad(num_srl);
        let total_io_words = srl_io_base + srl_io_words;

        // Assign offsets to each instance
        for inst in &mut instances {
            match inst.kind {
                MacroKind::DSP48E2 => {
                    let id = inst.instance_id;
                    inst.state_offset = Some(dsp_state_base + id);
                    // I/O: fields stride by warp_pad(num_dsp)
                    inst.io_offset = dsp_io_base + id;
                }
                MacroKind::CarryChain => {
                    let id = inst.instance_id;
                    inst.state_offset = None;
                    inst.io_offset = carrychain_io_base + id;
                }
                MacroKind::SRLC32E => {
                    let id = inst.instance_id;
                    inst.state_offset = Some(srl_state_base + id);
                    inst.io_offset = srl_io_base + id;
                }
            }
        }

        MacroStorageLayout {
            total_state_words,
            total_io_words,
            dsp_state_base,
            srl_state_base,
            carrychain_io_base,
            dsp_io_base,
            srl_io_base,
            num_dsp,
            num_carrychain,
            num_srl,
            instances,
        }
    }

    /// Total bytes for the state buffer (each word is 8 bytes).
    pub fn state_bytes(&self) -> usize {
        self.total_state_words * 8
    }

    /// Total bytes for the I/O buffer (each word is 8 bytes).
    pub fn io_bytes(&self) -> usize {
        self.total_io_words * 8
    }

    /// Given a DSP instance id (0..num_dsp), compute the I/O field base
    /// offset for field `field_idx` (0..8).
    pub fn dsp_io_field_offset(&self, instance_id: usize, field_idx: usize) -> usize {
        self.dsp_io_base + field_idx * Self::warp_pad(self.num_dsp) + instance_id
    }

    /// Given a CarryChain instance id (0..num_cc), compute the I/O field base
    /// offset for field `field_idx` (0..8).
    pub fn carrychain_io_field_offset(&self, instance_id: usize, field_idx: usize) -> usize {
        self.carrychain_io_base + field_idx * Self::warp_pad(self.num_carrychain) + instance_id
    }

    /// Given a SRLC32E instance id (0..num_srl), compute the I/O field base
    /// offset for field `field_idx` (0..4).
    pub fn srl_io_field_offset(&self, instance_id: usize, field_idx: usize) -> usize {
        self.srl_io_base + field_idx * Self::warp_pad(self.num_srl) + instance_id
    }
}

