use std::env;
use std::path::PathBuf;

fn main() {
    slint_build::compile("ui/appwindow.slint").unwrap();

    let out_dir = PathBuf::from(env::var("OUT_DIR").unwrap());
    // get target output dir
    let target_dir = out_dir
        .ancestors()
        .nth(3)
        .expect("Failed to locate target directory");

    let options = fs_extra::dir::CopyOptions {
        overwrite: true,
        skip_exist: false,
        buffer_size: 64000,
        copy_inside: false,
        content_only: false,
        depth: 0,
    };

    let manifest_dir = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap());
    let patch_src = manifest_dir.join("patch");
    let assets_src = manifest_dir.join("assets");

    if patch_src.exists() {
        let _ = fs_extra::dir::copy(&patch_src, target_dir, &options);
    }
    if assets_src.exists() {
        let _ = fs_extra::dir::copy(&assets_src, target_dir, &options);
    }

    println!("cargo:rerun-if-changed=patch");
    println!("cargo:rerun-if-changed=assets");
}
