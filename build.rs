use std::env;
use std::path::PathBuf;

fn main() {
    slint_build::compile("ui/appwindow.slint").unwrap();

    let out_dir = PathBuf::from(env::var("OUT_DIR").unwrap());
    let manifest_dir = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap());
    let target_os = env::var("CARGO_CFG_TARGET_OS").unwrap_or_default();
    let is_mac = target_os == "macos";

    // get target output dir (로컬 개발 실행 지원용)
    if let Some(target_dir) = out_dir.ancestors().nth(3) {
        let options = fs_extra::dir::CopyOptions {
            overwrite: true,
            skip_exist: false,
            buffer_size: 64000,
            copy_inside: false,
            content_only: false,
            depth: 0,
        };

        let patch_src = manifest_dir.join("patch");
        let assets_src = manifest_dir.join("assets");

        if patch_src.exists() {
            let target_patch = target_dir.join("patch");
            let _ = std::fs::create_dir_all(&target_patch);

            let deterwill = patch_src.join("deterwill.json");
            if deterwill.exists() {
                let _ = std::fs::copy(&deterwill, target_patch.join("deterwill.json"));
            }

            if is_mac {
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
            let bin_dir = target_dir.join("assets").join("bin");
            if is_mac {
                let _ = std::fs::remove_file(bin_dir.join("xdelta3_win.exe"));
                let _ = std::fs::remove_file(bin_dir.join("xdelta3_linux"));
            } else if target_os == "windows" {
                let _ = std::fs::remove_file(bin_dir.join("xdelta3_mac"));
                let _ = std::fs::remove_file(bin_dir.join("xdelta3_linux"));
            } else {
                let _ = std::fs::remove_file(bin_dir.join("xdelta3_win.exe"));
                let _ = std::fs::remove_file(bin_dir.join("xdelta3_mac"));
            }
        }
    }

    println!("cargo:rerun-if-changed=patch");
    println!("cargo:rerun-if-changed=assets");
}
