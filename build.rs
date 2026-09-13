use flate2::write::GzEncoder;
use flate2::Compression;
use std::env;
use std::fs::File;
use std::path::{Path, PathBuf};

fn compress_file(src: &Path, dst: &Path) {
    let mut input = File::open(src).unwrap_or_else(|e| panic!("Failed to open {:?}: {}", src, e));
    let output = File::create(dst).unwrap_or_else(|e| panic!("Failed to create {:?}: {}", dst, e));
    let mut encoder = GzEncoder::new(output, Compression::default());
    std::io::copy(&mut input, &mut encoder).unwrap();
    encoder.finish().unwrap();
}

fn main() {
    slint_build::compile("ui/appwindow.slint").unwrap();

    let out_dir = PathBuf::from(env::var("OUT_DIR").unwrap());
    let manifest_dir = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap());
    let target_os = env::var("CARGO_CFG_TARGET_OS").unwrap_or_default();
    let is_mac = target_os == "macos";

    // 패치 파일 압축하여 임베딩용 디렉터리에 저장
    let comp_dir = out_dir.join("compressed_patch");
    let _ = std::fs::create_dir_all(&comp_dir);

    let patch_src = manifest_dir.join("patch");
    if patch_src.exists() {
        let deterwill = patch_src.join("deterwill.json");
        if deterwill.exists() {
            compress_file(&deterwill, &comp_dir.join("deterwill.json.gz"));
        }

        let xdelta_folder = if is_mac { "xdelta_mac" } else { "xdelta" };
        let xdelta_src = patch_src.join(xdelta_folder);
        compress_file(&xdelta_src.join("launcher.xdelta"), &comp_dir.join("launcher.xdelta.gz"));
        for i in 1..=5 {
            compress_file(
                &xdelta_src.join(format!("ch{}.xdelta", i)),
                &comp_dir.join(format!("ch{}.xdelta.gz", i)),
            );
        }

        let lang_folder = if is_mac { "lang_mac" } else { "lang" };
        for i in 1..=5 {
            let ch_sub = if is_mac {
                format!("chapter{}_mac", i)
            } else {
                format!("chapter{}_windows", i)
            };
            let lang_file = patch_src.join(lang_folder).join(&ch_sub).join("lang").join("lang_ja.json");
            compress_file(&lang_file, &comp_dir.join(format!("ch{}_lang_ja.json.gz", i)));
        }

        // 비디오 파일 압축 (원본 무손실 압축)
        let ch3_sub = if is_mac { "chapter3_mac" } else { "chapter3_windows" };
        let ch3_vid = patch_src.join(lang_folder).join(ch3_sub).join("vid");
        compress_file(
            &ch3_vid.join("tennaIntroF1_compressed_28.mp4"),
            &comp_dir.join("ch3_tenna.mp4.gz"),
        );
        compress_file(
            &ch3_vid.join("tennaIntroKRf1_compressed_28.mp4"),
            &comp_dir.join("ch3_tenna_kr.mp4.gz"),
        );

        let ch5_sub = if is_mac { "chapter5_mac" } else { "chapter5_windows" };
        let ch5_vid = patch_src.join(lang_folder).join(ch5_sub).join("vid");
        compress_file(
            &ch5_vid.join("ch5_intro_jp.mp4"),
            &comp_dir.join("ch5_intro.mp4.gz"),
        );
    }

    // get target output dir
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
