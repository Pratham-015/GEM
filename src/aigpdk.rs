// SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
//! AIGPDK is a special artificial cell library used in GEM.

use netlistdb::{Direction, LeafPinProvider};
use compact_str::CompactString;
use sverilogparse::SVerilogRange;

/// This implements direction and width providers for
/// AIG PDK cells.
///
/// You can use it in netlistdb construction.
pub struct AIGPDKLeafPins();

/// The addr width of an SRAM.
///
/// The word width is always 32.
/// If you change this, make sure to change all other occurences in this
/// project as well as the definitions in PDK libraries.
pub const AIGPDK_SRAM_ADDR_WIDTH: usize = 13;

pub const AIGPDK_SRAM_SIZE: usize = 1 << 13;

impl LeafPinProvider for AIGPDKLeafPins {
    fn direction_of(
        &self,
        macro_name: &CompactString,
        pin_name: &CompactString, pin_idx: Option<isize>
    ) -> Direction {
        match (macro_name.as_str(), pin_name.as_str(), pin_idx) {
            ("INV" | "BUF", "A", None) => Direction::I,
            ("INV" | "BUF", "Y", None) => Direction::O,

            ("AND2_00_0" | "AND2_01_0" | "AND2_10_0" | "AND2_11_0" |
             "AND2_11_1", "A" | "B", None) => Direction::I,
            ("AND2_00_0" | "AND2_01_0" | "AND2_10_0" | "AND2_11_0" |
             "AND2_11_1", "Y", None) => Direction::O,

            ("DFF" | "LATCH", "CLK" | "D", None) => Direction::I,
            ("DFFSR", "CLK" | "D" | "S" | "R", None) => Direction::I,
            ("DFF" | "DFFSR" | "LATCH", "Q", None) => Direction::O,

            ("CKLNQD", "CP" | "E", None) => Direction::I,
            ("CKLNQD", "Q", None) => Direction::O,

            ("$__RAMGEM_ASYNC_", _, _) => {
                panic!("Async RAM (lib cell {}) not supported yet in GEM.", macro_name);
            },

            ("$__RAMGEM_SYNC_",
             "PORT_R_CLK" | "PORT_W_CLK",
             None) => Direction::I,
            ("$__RAMGEM_SYNC_",
             "PORT_R_ADDR" | "PORT_W_ADDR",
             Some(0..=12)) => Direction::I,
            ("$__RAMGEM_SYNC_",
             "PORT_W_WR_EN" | "PORT_W_WR_DATA",
             Some(0..=31)) => Direction::I,
            ("$__RAMGEM_SYNC_",
             "PORT_R_RD_DATA",
             Some(0..=31)) => Direction::O,

            // Xilinx macro cells GEM evaluates natively on the GPU rather
            // than flattening into AIG gates (see csrc/gem_macros.cuh).
            // GEM_DSP48E2 is the normalized PS subset emitted by the Yosys
            // techmap.  Full DSP48E2 ports are recognized below as a guarded
            // fallback.  AIG construction, typed dependencies, SoA storage,
            // and CUDA scheduling are implemented in aig.rs, macro_layout.rs,
            // flatten.rs, and csrc/kernel_v1_impl.cuh respectively.
            ("CARRY4", "CI" | "CIN" | "CYINIT", None) => Direction::I,
            ("CARRY4", "DI" | "S", Some(0..=3)) => Direction::I,
            ("CARRY4", "CO" | "O", Some(0..=3)) => Direction::O,

            ("GEM_DSP48E2", "CLK", None) => Direction::I,
            ("GEM_DSP48E2" | "DSP48E2", "USE_PRE", None) => Direction::I,
            ("GEM_DSP48E2", "A" | "D", Some(0..=26)) => Direction::I,
            ("GEM_DSP48E2", "B", Some(0..=17)) => Direction::I,
            ("GEM_DSP48E2", "C", Some(0..=47)) => Direction::I,
            ("GEM_DSP48E2" | "DSP48E2", "STATE", Some(0..=1)) => Direction::I,
            ("GEM_DSP48E2", "P", Some(0..=47)) => Direction::O,

            ("DSP48E2", "CLK" | "CARRYIN" | "CARRYCASCIN" | "MULTSIGNIN" |
                "CEA1" | "CEA2" | "CEAD" | "CEALUMODE" | "CEB1" | "CEB2" |
                "CEC" | "CECARRYIN" | "CECTRL" | "CED" | "CEINMODE" | "CEM" |
                "CEP" | "RSTA" | "RSTALLCARRYIN" | "RSTALUMODE" | "RSTB" |
                "RSTC" | "RSTCTRL" | "RSTD" | "RSTINMODE" | "RSTM" | "RSTP", None)
                => Direction::I,
            ("DSP48E2", "A" | "ACIN", Some(0..=29)) => Direction::I,
            ("DSP48E2", "D", Some(0..=26)) => Direction::I,
            ("DSP48E2", "B" | "BCIN", Some(0..=17)) => Direction::I,
            ("DSP48E2", "C" | "PCIN", Some(0..=47)) => Direction::I,
            ("DSP48E2", "OPMODE", Some(0..=8)) => Direction::I,
            ("DSP48E2", "ALUMODE", Some(0..=3)) => Direction::I,
            ("DSP48E2", "INMODE", Some(0..=4)) => Direction::I,
            ("DSP48E2", "CARRYINSEL", Some(0..=2)) => Direction::I,
            ("DSP48E2", "P" | "PCOUT", Some(0..=47)) => Direction::O,
            ("DSP48E2", "ACOUT", Some(0..=29)) => Direction::O,
            ("DSP48E2", "BCOUT", Some(0..=17)) => Direction::O,
            ("DSP48E2", "CARRYOUT", Some(0..=3)) => Direction::O,
            ("DSP48E2", "XOROUT", Some(0..=7)) => Direction::O,
            ("DSP48E2", "CARRYCASCOUT" | "MULTSIGNOUT" | "OVERFLOW" |
                "UNDERFLOW" | "PATTERNBDETECT" | "PATTERNDETECT", None)
                => Direction::O,

            ("SRLC32E", "CLK" | "CE" | "D", None) => Direction::I,
            ("SRLC32E", "A", Some(0..=4)) => Direction::I,
            ("SRLC32E", "Q" | "Q31", None) => Direction::O,

            _ => {
                use netlistdb::{GeneralPinName, HierName};
                panic!("Cannot recognize pin type {}, please make sure the verilog netlist is synthesized in GEM's aigpdk.",
                       (HierName::single(macro_name.clone()),
                        pin_name, pin_idx).dbg_fmt_pin());
            }
        }
    }

    fn width_of(
        &self,
        macro_name: &CompactString,
        pin_name: &CompactString
    ) -> Option<SVerilogRange> {
        match (macro_name.as_str(), pin_name.as_str()) {
            ("INV" | "BUF", "A" | "Y") => None,
            ("AND2_00_0" | "AND2_01_0" | "AND2_10_0" | "AND2_11_0" |
             "AND2_11_1", "A" | "B" | "Y") => None,
            ("DFF" | "DFFSR" | "LATCH", "CLK" | "D" | "Q" | "S" | "R") => None,
            ("CKLNQD", "CP" | "E" | "Q") => None,
            ("$__RAMGEM_SYNC_",
             "PORT_R_CLK" | "PORT_W_CLK") => None,
            ("$__RAMGEM_SYNC_",
             "PORT_R_ADDR" | "PORT_W_ADDR")
                => Some(SVerilogRange(12, 0)),
            ("$__RAMGEM_SYNC_",
             "PORT_W_WR_EN" | "PORT_W_WR_DATA" | "PORT_R_RD_DATA")
                => Some(SVerilogRange(31, 0)),

            ("CARRY4", "CI" | "CIN" | "CYINIT") => None,
            ("CARRY4", "DI" | "S" | "CO" | "O") => Some(SVerilogRange(3, 0)),

            ("GEM_DSP48E2", "CLK" | "USE_PRE") => None,
            ("GEM_DSP48E2", "A" | "D") => Some(SVerilogRange(26, 0)),
            ("GEM_DSP48E2", "B") => Some(SVerilogRange(17, 0)),
            ("GEM_DSP48E2", "C" | "P") => Some(SVerilogRange(47, 0)),
            ("GEM_DSP48E2", "STATE") => Some(SVerilogRange(1, 0)),

            ("DSP48E2", "CLK" | "CARRYIN" | "CARRYCASCIN" | "MULTSIGNIN" |
                "CEA1" | "CEA2" | "CEAD" | "CEALUMODE" | "CEB1" | "CEB2" |
                "CEC" | "CECARRYIN" | "CECTRL" | "CED" | "CEINMODE" | "CEM" |
                "CEP" | "RSTA" | "RSTALLCARRYIN" | "RSTALUMODE" | "RSTB" |
                "RSTC" | "RSTCTRL" | "RSTD" | "RSTINMODE" | "RSTM" | "RSTP" |
                "CARRYCASCOUT" | "MULTSIGNOUT" | "OVERFLOW" | "UNDERFLOW" |
                "PATTERNBDETECT" | "PATTERNDETECT") => None,
            ("DSP48E2", "A" | "ACIN" | "ACOUT") => Some(SVerilogRange(29, 0)),
            ("DSP48E2", "D") => Some(SVerilogRange(26, 0)),
            ("DSP48E2", "B" | "BCIN" | "BCOUT") => Some(SVerilogRange(17, 0)),
            ("DSP48E2", "C" | "P" | "PCIN" | "PCOUT") => Some(SVerilogRange(47, 0)),
            ("DSP48E2", "OPMODE") => Some(SVerilogRange(8, 0)),
            ("DSP48E2", "ALUMODE" | "CARRYOUT") => Some(SVerilogRange(3, 0)),
            ("DSP48E2", "INMODE") => Some(SVerilogRange(4, 0)),
            ("DSP48E2", "CARRYINSEL") => Some(SVerilogRange(2, 0)),
            ("DSP48E2", "XOROUT") => Some(SVerilogRange(7, 0)),

            ("SRLC32E", "CLK" | "CE" | "D" | "Q" | "Q31") => None,
            ("SRLC32E", "A") => Some(SVerilogRange(4, 0)),

            _ => None
        }
    }
}
