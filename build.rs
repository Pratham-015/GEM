//! this build script compiles GEM kernels
// SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

fn main() {
    println!("Building cuda source files for GEM...");
    println!("cargo:rerun-if-changed=csrc");
    println!("cargo:rerun-if-env-changed=GEM_MAXRREGCOUNT");

    #[cfg(feature = "cuda")] {
        let csrc_headers = ucc::import_csrc();
        let mut cl_cuda = ucc::cl_cuda();
        cl_cuda.ccbin(false);
        cl_cuda.flag("-lineinfo");
        let max_registers = std::env::var("GEM_MAXRREGCOUNT")
            .unwrap_or_else(|_| "128".to_string());
        if !matches!(max_registers.as_str(), "64" | "80" | "96" | "112" | "128") {
            panic!("GEM_MAXRREGCOUNT must be one of 64, 80, 96, 112, or 128");
        }
        cl_cuda.flag(&format!("-maxrregcount={max_registers}"));
        cl_cuda.debug(false).opt_level(3)
            .include(&csrc_headers)
            .files(["csrc/kernel_v1.cu"]);
        cl_cuda.compile("gemcu");
        println!("cargo:rustc-link-lib=static=gemcu");
        println!("cargo:rustc-link-lib=dylib=cudart");
        ucc::bindgen(["csrc/kernel_v1.cu"], "kernel_v1.rs");
        ucc::export_csrc();
        ucc::make_compile_commands(&[&cl_cuda]);
    }
}
