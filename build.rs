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

    let target_os = env::var("CARGO_CFG_TARGET_OS").unwrap_or_default();
    let is_mac = target_os == "macos";

    if patch_src.exists() {
        let target_patch = target_dir.join("patch");
        let _ = std::fs::create_dir_all(&target_patch);

        let deterwill = patch_src.join("deterwill.json");
        if deterwill.exists() {
            let _ = std::fs::copy(&deterwill, target_patch.join("deterwill.json"));
        }

        if is_mac {
            // macOS: mac 패치만 복사
            let lang_mac = patch_src.join("lang_mac");
            if lang_mac.exists() {
                let _ = fs_extra::dir::copy(&lang_mac, &target_patch, &options);
            }
            let xdelta_mac = patch_src.join("xdelta_mac");
            if xdelta_mac.exists() {
                let _ = fs_extra::dir::copy(&xdelta_mac, &target_patch, &options);
            }
            let _ = std::fs::remove_dir_all(target_patch.join("lang"));
            let _ = std::fs::remove_dir_all(target_patch.join("xdelta"));
        } else {
            // Windows/Linux: 일반 패치만 복사 (macOS 패치 제외)
            let lang = patch_src.join("lang");
            if lang.exists() {
                let _ = fs_extra::dir::copy(&lang, &target_patch, &options);
            }
            let xdelta = patch_src.join("xdelta");
            if xdelta.exists() {
                let _ = fs_extra::dir::copy(&xdelta, &target_patch, &options);
            }
            let _ = std::fs::remove_dir_all(target_patch.join("lang_mac"));
            let _ = std::fs::remove_dir_all(target_patch.join("xdelta_mac"));
        }
    }
    if assets_src.exists() {
        let _ = fs_extra::dir::copy(&assets_src, target_dir, &options);
    }

    println!("cargo:rerun-if-changed=patch");
    println!("cargo:rerun-if-changed=assets");
}
