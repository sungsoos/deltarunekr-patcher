#![windows_subsystem = "windows"]

use std::borrow::Cow;
use std::collections::HashMap;
use std::fs::{self, File};
use std::io::{BufRead, BufReader, Read, Write};
use std::path::{Path, PathBuf};
use std::process::Command as StdCommand;
use std::rc::Rc;
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;

use flate2::read::GzDecoder;
use ini::Ini;
use serde_json::Value;
use slint::winit_030::WinitWindowAccessor;
use slint::{Color, Model, ModelRc, SharedString, VecModel};

slint::include_modules!();

// -- 내장 패치 데이터 --

fn decompress_gz(bytes: &[u8]) -> Vec<u8> {
    let mut decoder = GzDecoder::new(bytes);
    let mut out = Vec::new();
    let _ = decoder.read_to_end(&mut out);
    out
}

fn decompress_gz_str(bytes: &[u8]) -> String {
    let bytes = decompress_gz(bytes);
    String::from_utf8(bytes).unwrap_or_default()
}

fn decompress_gz_to_file(bytes: &[u8], dst: &Path) -> Result<(), String> {
    let mut decoder = GzDecoder::new(bytes);
    let mut file = File::create(dst).map_err(|e| format!("파일 생성 실패 ({:?}): {}", dst, e))?;
    std::io::copy(&mut decoder, &mut file).map_err(|e| format!("압축 해제 실패 ({:?}): {}", dst, e))?;
    Ok(())
}

mod embedded_patch {
    pub static DETERWILL: &[u8] = include_bytes!(concat!(env!("OUT_DIR"), "/compressed_patch/deterwill.json.gz"));

    pub static LAUNCHER_XDELTA: &[u8] = include_bytes!(concat!(env!("OUT_DIR"), "/compressed_patch/launcher.xdelta.gz"));
    pub static CH1_XDELTA: &[u8] = include_bytes!(concat!(env!("OUT_DIR"), "/compressed_patch/ch1.xdelta.gz"));
    pub static CH2_XDELTA: &[u8] = include_bytes!(concat!(env!("OUT_DIR"), "/compressed_patch/ch2.xdelta.gz"));
    pub static CH3_XDELTA: &[u8] = include_bytes!(concat!(env!("OUT_DIR"), "/compressed_patch/ch3.xdelta.gz"));
    pub static CH4_XDELTA: &[u8] = include_bytes!(concat!(env!("OUT_DIR"), "/compressed_patch/ch4.xdelta.gz"));
    pub static CH5_XDELTA: &[u8] = include_bytes!(concat!(env!("OUT_DIR"), "/compressed_patch/ch5.xdelta.gz"));

    pub static CH1_LANG_JA: &[u8] = include_bytes!(concat!(env!("OUT_DIR"), "/compressed_patch/ch1_lang_ja.json.gz"));
    pub static CH2_LANG_JA: &[u8] = include_bytes!(concat!(env!("OUT_DIR"), "/compressed_patch/ch2_lang_ja.json.gz"));
    pub static CH3_LANG_JA: &[u8] = include_bytes!(concat!(env!("OUT_DIR"), "/compressed_patch/ch3_lang_ja.json.gz"));
    pub static CH4_LANG_JA: &[u8] = include_bytes!(concat!(env!("OUT_DIR"), "/compressed_patch/ch4_lang_ja.json.gz"));
    pub static CH5_LANG_JA: &[u8] = include_bytes!(concat!(env!("OUT_DIR"), "/compressed_patch/ch5_lang_ja.json.gz"));

    pub static CH3_VID_TENNA: &[u8] = include_bytes!(concat!(env!("OUT_DIR"), "/compressed_patch/ch3_tenna.mp4.gz"));
    pub static CH3_VID_TENNA_KR: &[u8] = include_bytes!(concat!(env!("OUT_DIR"), "/compressed_patch/ch3_tenna_kr.mp4.gz"));
    pub static CH5_VID_INTRO: &[u8] = include_bytes!(concat!(env!("OUT_DIR"), "/compressed_patch/ch5_intro.mp4.gz"));
}

fn get_xdelta_data(ch: usize) -> Option<Cow<'static, [u8]>> {
    let is_mac = cfg!(target_os = "macos");
    let folder = if is_mac { "xdelta_mac" } else { "xdelta" };
    let filename = if ch == 0 {
        "launcher.xdelta".to_string()
    } else {
        format!("ch{}.xdelta", ch)
    };
    let disk_file = resource_path(format!("patch/{}/{}", folder, filename));
    if disk_file.exists() {
        if let Ok(data) = fs::read(&disk_file) {
            return Some(Cow::Owned(data));
        }
    }

    let raw = match ch {
        0 => embedded_patch::LAUNCHER_XDELTA,
        1 => embedded_patch::CH1_XDELTA,
        2 => embedded_patch::CH2_XDELTA,
        3 => embedded_patch::CH3_XDELTA,
        4 => embedded_patch::CH4_XDELTA,
        5 => embedded_patch::CH5_XDELTA,
        _ => return None,
    };
    Some(Cow::Owned(decompress_gz(raw)))
}

fn get_chapter_lang_ja(ch: usize) -> Option<Cow<'static, str>> {
    let is_mac = cfg!(target_os = "macos");
    let lang_folder = if is_mac { "lang_mac" } else { "lang" };
    let ch_sub = if is_mac {
        format!("chapter{}_mac", ch)
    } else {
        format!("chapter{}_windows", ch)
    };
    let disk_file = resource_path(format!("patch/{}/{}/lang/lang_ja.json", lang_folder, ch_sub));
    if disk_file.exists() {
        if let Ok(content) = fs::read_to_string(&disk_file) {
            return Some(Cow::Owned(content));
        }
    }

    let raw = match ch {
        1 => embedded_patch::CH1_LANG_JA,
        2 => embedded_patch::CH2_LANG_JA,
        3 => embedded_patch::CH3_LANG_JA,
        4 => embedded_patch::CH4_LANG_JA,
        5 => embedded_patch::CH5_LANG_JA,
        _ => return None,
    };
    Some(Cow::Owned(decompress_gz_str(raw)))
}

fn get_deterwill_content() -> Cow<'static, str> {
    let p = resource_path("assets/deterwill.json");
    if p.exists() {
        if let Ok(c) = fs::read_to_string(&p) {
            return Cow::Owned(c);
        }
    }
    let p2 = resource_path("patch/deterwill.json");
    if p2.exists() {
        if let Ok(c) = fs::read_to_string(&p2) {
            return Cow::Owned(c);
        }
    }
    Cow::Owned(decompress_gz_str(embedded_patch::DETERWILL))
}

fn deploy_video_file<F>(url: &str, fallback_gz: &[u8], dst: &Path, log_cb: &F)
where
    F: Fn(String, &'static str),
{
    let file_name = dst.file_name().unwrap_or_default().to_string_lossy();
    log_cb(format!("* 비디오 다운로드 시도 중: {}...", file_name), "#FFFF00");

    let mut download_ok = false;
    let agent = ureq::builder()
        .timeout_connect(Duration::from_secs(5))
        .timeout_read(Duration::from_secs(60))
        .build();

    let tmp_dst = dst.with_extension("download_tmp");
    match agent.get(url).call() {
        Ok(resp) if resp.status() == 200 => {
            if let Ok(mut file) = File::create(&tmp_dst) {
                let mut reader = resp.into_reader();
                if std::io::copy(&mut reader, &mut file).is_ok() {
                    let _ = fs::rename(&tmp_dst, dst);
                    download_ok = true;
                    log_cb(format!("  * 원본 비디오 다운로드 완료: {}", file_name), "#88FF88");
                }
            }
        }
        Ok(resp) => {
            log_cb(format!("  * 다운로드 서버 응답 코드 ({}): {}", resp.status(), file_name), "#FFAA00");
        }
        Err(e) => {
            log_cb(format!("  * 다운로드 연결 실패 ({}): {}", e, file_name), "#FFAA00");
        }
    }

    let _ = fs::remove_file(&tmp_dst);

    if !download_ok {
        log_cb(format!("  * 내장 비디오로 대체 ({})", file_name), "#FFAA00");
        let _ = decompress_gz_to_file(fallback_gz, dst);
    }
}

fn deploy_chapter_assets<F>(ch_num: usize, dst_chapter_dir: &Path, log_cb: &F) -> Result<(), String>
where
    F: Fn(String, &'static str),
{
    // 언어 파일 복사
    let lang_dir = dst_chapter_dir.join("lang");
    fs::create_dir_all(&lang_dir).map_err(|e| format!("폴더 생성 실패 ({:?}): {}", lang_dir, e))?;

    if let Some(lang_content) = get_chapter_lang_ja(ch_num) {
        let lang_file = lang_dir.join("lang_ja.json");
        fs::write(&lang_file, lang_content.as_bytes())
            .map_err(|e| format!("언어 파일 작성 실패 ({:?}): {}", lang_file, e))?;
    }

    // 서버에서 비디오 파일 다운로드 및 복사
    // 하드코딩 조아
    if ch_num == 3 {
        let vid_dir = dst_chapter_dir.join("vid");
        fs::create_dir_all(&vid_dir).map_err(|e| format!("폴더 생성 실패 ({:?}): {}", vid_dir, e))?;
        deploy_video_file(
            "https://dtkr.sungsoos.kr/patch/lang/chapter3_windows/vid/tennaIntroF1_compressed_28.mp4",
            embedded_patch::CH3_VID_TENNA,
            &vid_dir.join("tennaIntroF1_compressed_28.mp4"),
            log_cb,
        );
        deploy_video_file(
            "https://dtkr.sungsoos.kr/patch/lang/chapter3_windows/vid/tennaIntroKRf1_compressed_28.mp4",
            embedded_patch::CH3_VID_TENNA_KR,
            &vid_dir.join("tennaIntroKRf1_compressed_28.mp4"),
            log_cb,
        );
    } else if ch_num == 5 {
        let vid_dir = dst_chapter_dir.join("vid");
        fs::create_dir_all(&vid_dir).map_err(|e| format!("폴더 생성 실패 ({:?}): {}", vid_dir, e))?;
        deploy_video_file(
            "https://dtkr.sungsoos.kr/patch/lang/chapter5_windows/vid/ch5_intro_jp.mp4",
            embedded_patch::CH5_VID_INTRO,
            &vid_dir.join("ch5_intro_jp.mp4"),
            log_cb,
        );
    }

    Ok(())
}

fn resource_path<P: AsRef<Path>>(relative_path: P) -> PathBuf {
    let rel = relative_path.as_ref();

    if let Ok(exe_path) = std::env::current_exe() {
        if let Some(exe_dir) = exe_path.parent() {
            let direct = exe_dir.join(rel);
            if direct.exists() {
                return direct;
            }

            // macOS .app bundle Contents/Resources 지원
            if let Some(contents) = exe_dir.parent() {
                let res_cand = contents.join("Resources").join(rel);
                if res_cand.exists() {
                    return res_cand;
                }
            }

            let mut curr = exe_dir.to_path_buf();
            for _ in 0..6 {
                let cand = curr.join(rel);
                if cand.exists() {
                    return cand;
                }
                if let Some(parent) = curr.parent() {
                    curr = parent.to_path_buf();
                } else {
                    break;
                }
            }
        }
    }

    if let Ok(cwd) = std::env::current_dir() {
        let mut curr = cwd;
        for _ in 0..6 {
            let cand = curr.join(rel);
            if cand.exists() {
                return cand;
            }
            if let Some(parent) = curr.parent() {
                curr = parent.to_path_buf();
            } else {
                break;
            }
        }
    }

    PathBuf::from(rel)
}

fn get_assets_dir() -> PathBuf {
    resource_path("assets")
}

fn is_libraryfolders_vdf(vdf_path: &Path) -> Vec<PathBuf> {
    let mut paths = Vec::new();
    if !vdf_path.exists() {
        return paths;
    }
    if let Ok(file) = File::open(vdf_path) {
        let reader = BufReader::new(file);
        for line in reader.lines().flatten() {
            let line_str = line.trim();
            if line_str.contains("\"path\"") {
                let parts: Vec<&str> = line_str.split("\"path\"").collect();
                if parts.len() > 1 {
                    let path_val = parts[1].replace('"', "").trim().to_string();
                    let p = PathBuf::from(&path_val);
                    if p.exists() && !paths.contains(&p) {
                        paths.push(p);
                    }
                }
            }
        }
    }
    paths
}

fn clean_path(path: &Path) -> PathBuf {
    let s = path.to_string_lossy();
    if let Some(stripped) = s.strip_prefix(r"\\?\UNC\") {
        PathBuf::from(format!(r"\\{}", stripped))
    } else if let Some(stripped) = s.strip_prefix(r"\\?\") {
        PathBuf::from(stripped)
    } else {
        path.to_path_buf()
    }
}

fn canonicalize_clean(path: &Path) -> std::io::Result<PathBuf> {
    let p = fs::canonicalize(path)?;
    Ok(clean_path(&p))
}

fn resolve_game_folder(dir: &Path) -> PathBuf {
    let cleaned = clean_path(dir);
    if cfg!(target_os = "macos") {
        let cand_app_resources = cleaned.join("DELTARUNE.app").join("Contents").join("Resources");
        if cand_app_resources.exists() {
            return cand_app_resources;
        }
        let cand_resources = cleaned.join("Contents").join("Resources");
        if cand_resources.exists() {
            return cand_resources;
        }
    }
    cleaned
}

fn find_launcher_data_file(target_dir: &Path, is_mac: bool) -> Option<PathBuf> {
    if !target_dir.exists() {
        return None;
    }

    if is_mac {
        for name in ["game.ios", "data.ios", "data.win"] {
            let p = target_dir.join(name);
            if p.exists() {
                return Some(p);
            }
        }

        let cand_app = target_dir.join("DELTARUNE.app").join("Contents").join("Resources");
        if cand_app.exists() {
            for name in ["game.ios", "data.ios", "data.win"] {
                let p = cand_app.join(name);
                if p.exists() {
                    return Some(p);
                }
            }
        }
    } else {
        let p = target_dir.join("data.win");
        if p.exists() {
            return Some(p);
        }
    }

    None
}

fn find_chapter_data_file(chapter_dir: &Path, is_mac: bool) -> Option<PathBuf> {
    if !chapter_dir.exists() {
        return None;
    }

    if is_mac {
        for name in ["game.ios", "data.ios", "data.win"] {
            let p = chapter_dir.join(name);
            if p.exists() {
                return Some(p);
            }
        }
    } else {
        let p = chapter_dir.join("data.win");
        if p.exists() {
            return Some(p);
        }
    }

    None
}

fn validate_deltarune_folder(raw_dir: &Path) -> (bool, Option<String>) {
    if !raw_dir.exists() {
        return (false, Some("폴더가 존재하지 않습니다.".to_string()));
    }

    let is_mac = cfg!(target_os = "macos");
    let resolved = resolve_game_folder(raw_dir);
    let target_dir = resolved.as_path();

    if find_launcher_data_file(target_dir, is_mac).is_none() {
        let expected = if is_mac { "game.ios" } else { "data.win" };
        return (
            false,
            Some(format!("런처 파일({})을 찾을 수 없습니다.", expected)),
        );
    }

    for i in 1..=5 {
        let folder_candidates = if is_mac {
            vec![
                format!("chapter{}_mac", i),
                format!("chapter{}", i),
            ]
        } else {
            vec![
                format!("chapter{}_windows", i),
                format!("chapter{}", i),
            ]
        };

        let mut found = false;
        for fn_name in &folder_candidates {
            let cbase = target_dir.join(fn_name);
            if find_chapter_data_file(&cbase, is_mac).is_some() {
                found = true;
                break;
            }
        }

        if !found {
            let (exp_folder, exp_file) = if is_mac {
                (format!("chapter{}_mac", i), "game.ios")
            } else {
                (format!("chapter{}_windows", i), "data.win")
            };
            return (
                false,
                Some(format!(
                    "챕터 {} 데이터 파일({}/{})이 존재하지 않습니다.",
                    i, exp_folder, exp_file
                )),
            );
        }
    }

    (true, None)
}

fn detect_deltarune() -> Option<PathBuf> {
    let mut candidate_steam_dirs: Vec<PathBuf> = Vec::new();

    #[cfg(target_os = "windows")]
    {
        use winreg::enums::*;
        use winreg::RegKey;

        let hk_list = [HKEY_LOCAL_MACHINE, HKEY_CURRENT_USER];
        let subkeys = [
            r"SOFTWARE\WOW6432Node\Valve\Steam",
            r"SOFTWARE\Valve\Steam",
        ];
        for hkey in hk_list {
            for subkey in subkeys {
                if let Ok(k) = RegKey::predef(hkey).open_subkey(subkey) {
                    if let Ok(val) = k.get_value::<String, _>("InstallPath") {
                        let p = PathBuf::from(val);
                        if p.exists() {
                            candidate_steam_dirs.push(p);
                        }
                    }
                }
            }
        }

        for drive in ["C", "D", "E", "F"] {
            candidate_steam_dirs.push(PathBuf::from(format!(r"{}:\Program Files (x86)\Steam", drive)));
            candidate_steam_dirs.push(PathBuf::from(format!(r"{}:\Program Files\Steam", drive)));
            candidate_steam_dirs.push(PathBuf::from(format!(r"{}:\Steam", drive)));
            candidate_steam_dirs.push(PathBuf::from(format!(r"{}:\SteamLibrary", drive)));
        }
    }

    #[cfg(target_os = "macos")]
    {
        if let Some(home) = dirs::home_dir() {
            candidate_steam_dirs.push(home.join("Library").join("Application Support").join("Steam"));
        }
    }

    #[cfg(not(any(target_os = "windows", target_os = "macos")))]
    {
        if let Some(home) = dirs::home_dir() {
            candidate_steam_dirs.push(home.join(".steam").join("steam"));
            candidate_steam_dirs.push(home.join(".steam").join("root"));
            candidate_steam_dirs.push(home.join(".local").join("share").join("Steam"));
            candidate_steam_dirs.push(
                home.join(".var")
                    .join("app")
                    .join("com.valvesoftware.Steam")
                    .join("data")
                    .join("Steam"),
            );
        }
    }

    let mut steam_libraries: Vec<PathBuf> = Vec::new();
    for s_dir in candidate_steam_dirs {
        if s_dir.exists() {
            if let Ok(real_dir) = canonicalize_clean(&s_dir) {
                if !steam_libraries.contains(&real_dir) {
                    steam_libraries.push(real_dir.clone());
                }
                let vdf = real_dir.join("steamapps").join("libraryfolders.vdf");
                for parsed in is_libraryfolders_vdf(&vdf) {
                    let parsed = clean_path(&parsed);
                    if !steam_libraries.contains(&parsed) {
                        steam_libraries.push(parsed);
                    }
                }
            }
        }
    }

    for lib in steam_libraries {
        for folder_name in ["DELTARUNE", "Deltarune", "deltarune"] {
            let common_path = lib.join("steamapps").join("common").join(folder_name);
            if let Ok(real_path) = canonicalize_clean(&common_path) {
                let resolved = resolve_game_folder(&real_path);
                let (valid, _) = validate_deltarune_folder(&resolved);
                if valid {
                    return Some(clean_path(&resolved));
                }
            }
        }
    }

    None
}

fn redact_user_path(path_str: &str) -> String {
    let mut s = path_str.to_string();
    if let Some(stripped) = s.strip_prefix(r"\\?\UNC\") {
        s = format!(r"\\{}", stripped);
    } else if let Some(stripped) = s.strip_prefix(r"\\?\") {
        s = stripped.to_string();
    }
    if let Some(home) = dirs::home_dir() {
        if let Some(home_str) = home.to_str() {
            s = s.replace(home_str, "~");
        }
    }
    let username = whoami::username();
    if !username.is_empty() {
        let re = regex::RegexBuilder::new(&regex::escape(&username))
            .case_insensitive(true)
            .build();
        if let Ok(re) = re {
            s = re.replace_all(&s, "<user>").to_string();
        }
    }
    s
}

fn get_xdelta3_binary() -> Option<PathBuf> {
    let assets_dir = get_assets_dir();
    let bundled = if cfg!(target_os = "windows") {
        assets_dir.join("bin").join("xdelta3_win.exe")
    } else if cfg!(target_os = "macos") {
        assets_dir.join("bin").join("xdelta3_mac")
    } else {
        assets_dir.join("bin").join("xdelta3_linux")
    };

    if bundled.exists() {
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            if let Ok(meta) = fs::metadata(&bundled) {
                let mut perms = meta.permissions();
                if perms.mode() & 0o111 == 0 {
                    perms.set_mode(perms.mode() | 0o755);
                    let _ = fs::set_permissions(&bundled, perms);
                }
            }
        }
        return Some(bundled);
    }

    if let Ok(path) = which::which("xdelta3") {
        return Some(path);
    }

    None
}

struct PatchError {
    detail: String,
    summary: String,
}

fn decode_with_oxidelta(
    source: &[u8],
    delta_bytes: &[u8],
    tmp_path: &Path,
    verify_checksum: bool,
) -> Result<(), String> {
    let mut decoder = oxidelta::compress::decoder::DeltaDecoder::with_checksum(
        std::io::Cursor::new(delta_bytes),
        verify_checksum,
    );
    let out_file = fs::File::create(tmp_path)
        .map_err(|e| format!("임시 출력 파일 생성 실패: {}", e))?;
    let mut writer = std::io::BufWriter::new(out_file);
    let mut src: &[u8] = source;
    decoder
        .decode_to(&mut src, &mut writer)
        .map_err(|e| format!("디코딩 오류: {}", e))?;
    writer
        .flush()
        .map_err(|e| format!("임시 파일 플러시 실패: {}", e))?;
    Ok(())
}

fn patchit(target_file: &Path, delta_bytes: &[u8], delta_name: &str) -> Result<(), PatchError> {
    let target_file = clean_path(target_file);
    let clean_target = redact_user_path(&target_file.to_string_lossy());

    if !target_file.exists() {
        return Err(PatchError {
            detail: String::new(),
            summary: format!("패치할 파일이 존재하지 않습니다: {}", clean_target),
        });
    }
    if delta_bytes.is_empty() {
        return Err(PatchError {
            detail: String::new(),
            summary: format!("델타 패치 데이터가 비어있습니다: {}", delta_name),
        });
    }

    let target_size = fs::metadata(&target_file).map(|m| m.len()).unwrap_or(0);
    if target_size == 0 {
        return Err(PatchError {
            detail: String::new(),
            summary: format!("대상 파일이 비어있습니다 (0 byte): {}", clean_target),
        });
    }

    let tmp_file = clean_path(&target_file.with_extension(format!(
        "{}.tmp",
        target_file.extension().unwrap_or_default().to_string_lossy()
    )));

    if tmp_file.exists() {
        let _ = fs::remove_file(&tmp_file);
    }

    let mut patched_ok = false;
    let mut detail_logs: Vec<String> = Vec::new();

    match fs::read(&target_file) {
        Ok(source) => {
            // 체크섬 검증
            match decode_with_oxidelta(&source, delta_bytes, &tmp_file, true) {
                Ok(_) if tmp_file.exists() && fs::metadata(&tmp_file).map(|m| m.len()).unwrap_or(0) > 0 => {
                    patched_ok = true;
                }
                Err(e) => {
                    detail_logs.push(format!("oxidelta 1차 디코딩 실패: {}", e));
                    let _ = fs::remove_file(&tmp_file);

                    // 체크섬 무시
                    match decode_with_oxidelta(&source, delta_bytes, &tmp_file, false) {
                        Ok(_) if tmp_file.exists() && fs::metadata(&tmp_file).map(|m| m.len()).unwrap_or(0) > 0 => {
                            patched_ok = true;
                        }
                        Err(e2) => {
                            detail_logs.push(format!("oxidelta 체크섬 무시 디코딩 실패: {}", e2));
                            let _ = fs::remove_file(&tmp_file);
                        }
                        _ => {}
                    }
                }
                _ => {}
            }
        }
        Err(e) => {
            detail_logs.push(format!("원본 파일 읽기 실패 ({}): {}", clean_target, e));
        }
    }

    // xdelta3 CLI를 시도
    if !patched_ok {
        if let Some(ref bin) = get_xdelta3_binary() {
            let delta_tmp = clean_path(&std::env::temp_dir().join(format!(
                "xdelta_tmp_{}_{}",
                delta_name,
                std::process::id()
            )));
            if let Ok(_) = fs::write(&delta_tmp, delta_bytes) {
                let mut cmd = StdCommand::new(bin);
                cmd.args([
                    "-d",
                    "-f",
                    "-s",
                    target_file.to_str().unwrap_or_default(),
                    delta_tmp.to_str().unwrap_or_default(),
                    tmp_file.to_str().unwrap_or_default(),
                ])
                .stdin(std::process::Stdio::null());

                #[cfg(windows)]
                {
                    use std::os::windows::process::CommandExt;
                    cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW
                }

                if let Ok(out) = cmd.output() {
                    let stdout = String::from_utf8_lossy(&out.stdout).trim().to_string();
                    let stderr = String::from_utf8_lossy(&out.stderr).trim().to_string();
                    if out.status.success()
                        && tmp_file.exists()
                        && fs::metadata(&tmp_file).map(|m| m.len()).unwrap_or(0) > 0
                    {
                        patched_ok = true;
                    } else {
                        detail_logs.push(format!("xdelta3 CLI 실패 (코드 {:?}): {} {}", out.status.code(), stderr, stdout));
                    }
                }
                let _ = fs::remove_file(&delta_tmp);
            }
        }
    }

    if !patched_ok || !tmp_file.exists() {
        return Err(PatchError {
            detail: detail_logs.join("\n"),
            summary: "이미 패치되었거나 원본 파일 버전이 일치하지 않습니다.".to_string(),
        });
    }

    if let Err(e) = fs::copy(&tmp_file, &target_file) {
        let _ = fs::remove_file(&tmp_file);
        return Err(PatchError {
            detail: format!("패치 임시 파일 복사 실패: {}", e),
            summary: format!("패치 파일 복사 실패 ({})", e),
        });
    }
    let _ = fs::remove_file(&tmp_file);

    Ok(())
}


fn adjust_josa(word: &str, josa: &str) -> String {
    if word.is_empty() {
        return format!("{}{}", word, josa);
    }
    let last_char = match word.chars().last() {
        Some(c) => c,
        None => return format!("{}{}", word, josa),
    };

    if !('가'..='힣').contains(&last_char) {
        return format!("{}{}", word, josa);
    }

    let jongseong_idx = (last_char as u32 - '가' as u32) % 28;
    let has_jongseong = jongseong_idx > 0;
    let is_rieul = jongseong_idx == 8;

    match josa {
        "을" | "를" => format!("{}{}", word, if has_jongseong { "을" } else { "를" }),
        "이" | "가" => format!("{}{}", word, if has_jongseong { "이" } else { "가" }),
        "은" | "는" => format!("{}{}", word, if has_jongseong { "은" } else { "는" }),
        "과" | "와" => format!("{}{}", word, if has_jongseong { "과" } else { "와" }),
        "으로" | "로" => {
            if has_jongseong && !is_rieul {
                format!("{}으로", word)
            } else {
                format!("{}로", word)
            }
        }
        _ => format!("{}{}", word, josa),
    }
}

fn replace_word_with_josa(text: &str, old_word: &str, new_word: &str) -> String {
    let safe_old = regex::escape(old_word);
    let pattern_str = format!(r"{}(을|를|이|가|은|는|으로|로|과|와)?", safe_old);
    let re = match regex::Regex::new(&pattern_str) {
        Ok(r) => r,
        Err(_) => return text.to_string(),
    };

    re.replace_all(text, |caps: &regex::Captures| {
        if let Some(josa) = caps.get(1) {
            adjust_josa(new_word, josa.as_str())
        } else {
            new_word.to_string()
        }
    })
    .to_string()
}

fn update_true_config<F>(log_cb: &F)
where
    F: Fn(String, &'static str),
{
    let mut config_paths = Vec::new();

    #[cfg(target_os = "windows")]
    {
        if let Some(local_app) = dirs::data_local_dir() {
            config_paths.push(local_app.join("DELTARUNE").join("true_config.ini"));
        }
    }
    #[cfg(target_os = "macos")]
    {
        if let Some(home) = dirs::home_dir() {
            config_paths.push(
                home.join("Library")
                    .join("Application Support")
                    .join("com.tobyfox.deltarune")
                    .join("true_config.ini"),
            );
            config_paths.push(
                home.join("Library")
                    .join("Application Support")
                    .join("DELTARUNE")
                    .join("true_config.ini"),
            );
        }
    }
    #[cfg(not(any(target_os = "windows", target_os = "macos")))]
    {
        if let Some(home) = dirs::home_dir() {
            config_paths.push(
                home.join(".local")
                    .join("share")
                    .join("DELTARUNE")
                    .join("true_config.ini"),
            );
            config_paths.push(
                home.join(".config")
                    .join("DELTARUNE")
                    .join("true_config.ini"),
            );
        }
    }

    for config_path in config_paths {
        if let Some(parent) = config_path.parent() {
            let _ = fs::create_dir_all(parent);
        }

        let mut conf = Ini::new();
        if config_path.exists() {
            if let Ok(loaded) = Ini::load_from_file(&config_path) {
                conf = loaded;
            }
        }

        conf.with_section(Some("LANG"))
            .set("LANG", "\"ja\"")
            .set("KRDUB", "\"1\"");

        if conf.write_to_file(&config_path).is_ok() {
            log_cb(
                format!(
                    "* true_config.ini 설정 변경 완료 ({})",
                    redact_user_path(&config_path.to_string_lossy())
                ),
                "#88FF88",
            );
        } else {
            log_cb(
                format!(
                    "* true_config.ini 설정 변경 실패 ({})",
                    redact_user_path(&config_path.to_string_lossy())
                ),
                "#FFFF00",
            );
        }
    }
}

pub struct CustomWords {
    pub enabled: bool,
    pub determination: String,
    pub will: String,
    pub dess: String,
}

fn apply_custom_words<F>(target_dir: &Path, custom_words: &CustomWords, log_cb: &F)
where
    F: Fn(String, &'static str),
{
    let file_content = get_deterwill_content();

    let deterwill: Value = match serde_json::from_str(&file_content) {
        Ok(v) => v,
        Err(e) => {
            log_cb(format!("* deterwill.json 파싱 오류: {}", e), "#FF5555");
            return;
        }
    };

    let mut default_map = HashMap::new();
    default_map.insert("determination", "의지");
    default_map.insert("will", "결의");
    default_map.insert("dess", "데스");

    let is_mac = cfg!(target_os = "macos");

    for ch_num in 1..=5 {
        let ch_str = ch_num.to_string();
        if deterwill.get(&ch_str).is_none() {
            continue;
        }

        let folder_candidates = if is_mac {
            vec![
                format!("chapter{}_mac", ch_num),
                format!("chapter{}_windows", ch_num),
                format!("chapter{}", ch_num),
            ]
        } else {
            vec![
                format!("chapter{}_windows", ch_num),
                format!("chapter{}", ch_num),
            ]
        };

        let mut lang_path = None;
        for fn_name in &folder_candidates {
            let cand_lang = target_dir
                .join(fn_name)
                .join("lang")
                .join("lang_ja.json");
            if cand_lang.exists() {
                lang_path = Some(cand_lang);
                break;
            }
        }

        let lang_path = match lang_path {
            Some(p) => p,
            None => continue,
        };

        let lang_content = match fs::read_to_string(&lang_path) {
            Ok(c) => c,
            Err(_) => continue,
        };

        let mut lang_data: HashMap<String, Value> = match serde_json::from_str(&lang_content) {
            Ok(v) => v,
            Err(_) => continue,
        };

        let mut modified = false;

        for (cat, old_word) in &default_map {
            let new_word = match *cat {
                "determination" => custom_words.determination.as_str(),
                "will" => custom_words.will.as_str(),
                "dess" => custom_words.dess.as_str(),
                _ => *old_word,
            };

            if new_word.is_empty() || new_word == *old_word {
                continue;
            }

            if let Some(keys_array) = deterwill[&ch_str].get(cat).and_then(|v| v.as_array()) {
                for key_val in keys_array {
                    if let Some(key) = key_val.as_str() {
                        if let Some(val) = lang_data.get_mut(key) {
                            if let Some(original_text) = val.as_str() {
                                let new_text = replace_word_with_josa(original_text, old_word, new_word);
                                if original_text != new_text {
                                    *val = Value::String(new_text);
                                    modified = true;
                                }
                            }
                        }
                    }
                }
            }
        }

        if modified {
            if let Ok(formatted) = serde_json::to_string_pretty(&lang_data) {
                let _ = fs::write(&lang_path, formatted);
                log_cb(
                    format!("* 챕터 {} 사용자 정의 명칭 치환 적용 완료", ch_num),
                    "#00FF00",
                );
            }
        }
    }
}

fn clean_tmp_files(target_dir: &Path) {
    if !target_dir.exists() {
        return;
    }
    let mut tmp_candidates = vec![
        target_dir.join("data.win.tmp"),
        target_dir.join("data.ios.tmp"),
        target_dir.join("game.ios.tmp"),
        target_dir.join("DELTARUNE.app").join("Contents").join("Resources").join("data.ios.tmp"),
        target_dir.join("DELTARUNE.app").join("Contents").join("Resources").join("data.win.tmp"),
        target_dir.join("DELTARUNE.app").join("Contents").join("Resources").join("game.ios.tmp"),
    ];
    for i in 1..=5 {
        for fn_name in [
            format!("chapter{}_windows", i),
            format!("chapter{}_mac", i),
            format!("chapter{}", i),
        ] {
            let cbase = target_dir.join(&fn_name);
            tmp_candidates.push(cbase.join("data.win.tmp"));
            tmp_candidates.push(cbase.join("data.ios.tmp"));
            tmp_candidates.push(cbase.join("game.ios.tmp"));
            tmp_candidates.push(cbase.join("lang").join("lang_ja.json.tmp"));
        }
    }

    for fpath in tmp_candidates {
        if fpath.exists() {
            let _ = fs::remove_file(fpath);
        }
    }
}

fn parse_hex_color(hex: &str) -> Color {
    let hex = hex.trim_start_matches('#');
    if hex.len() == 6 {
        let r = u8::from_str_radix(&hex[0..2], 16).unwrap_or(255);
        let g = u8::from_str_radix(&hex[2..4], 16).unwrap_or(255);
        let b = u8::from_str_radix(&hex[4..6], 16).unwrap_or(255);
        Color::from_argb_u8(255, r, g, b)
    } else {
        Color::from_argb_u8(255, 255, 255, 255)
    }
}

fn main() -> Result<(), slint::PlatformError> {
    let _ = slint::BackendSelector::new()
        .with_winit_window_attributes_hook(|attributes| attributes.with_decorations(false))
        .select();

    let main_window = MainWindow::new()?;
    main_window.window().with_winit_window(|winit_window| {
        winit_window.set_decorations(false);
    });

    let logs_model = Rc::new(VecModel::<LogItem>::default());
    main_window.set_logs(ModelRc::from(logs_model.clone()));

    let mut initial_log = String::new();
    let selected_folder = Arc::new(Mutex::new(Option::<PathBuf>::None));

    if let Some(auto_path) = detect_deltarune() {
        let auto_path = clean_path(&auto_path);
        let path_str = auto_path.to_string_lossy().to_string();
        *selected_folder.lock().unwrap() = Some(auto_path);
        main_window.set_folder_path(SharedString::from(format!(
            "* 선택된 폴더: {}",
            redact_user_path(&path_str)
        )));
        main_window.set_patch_enabled(true);

        logs_model.push(LogItem {
            msg: SharedString::from("* DELTARUNE 한글 패처"),
            color: parse_hex_color("#FFFFFF"),
        });
        logs_model.push(LogItem {
            msg: SharedString::from(format!("* DELTARUNE 설치 폴더 자동 감지 성공: {}", path_str)),
            color: parse_hex_color("#00FF00"),
        });
        initial_log.push_str("* DELTARUNE 한글 패처\n");
        initial_log.push_str(&format!("* DELTARUNE 설치 폴더 자동 감지 성공: {}\n", path_str));
    } else {
        logs_model.push(LogItem {
            msg: SharedString::from("* DELTARUNE 한글 패처"),
            color: parse_hex_color("#FFFFFF"),
        });
        logs_model.push(LogItem {
            msg: SharedString::from("* 패치를 적용할 DELTARUNE 폴더를 선택해주세요."),
            color: parse_hex_color("#FFFFFF"),
        });
        initial_log.push_str("* DELTARUNE 한글 패처\n");
        initial_log.push_str("* 패치를 적용할 DELTARUNE 폴더를 선택해주세요.\n");
    }
    main_window.set_log_text(SharedString::from(initial_log));
    main_window.invoke_scroll_to_bottom();

    let rainbow_colors = [
        parse_hex_color("#FF0000"),
        parse_hex_color("#FF8800"),
        parse_hex_color("#FFFF00"),
        parse_hex_color("#00FF00"),
        parse_hex_color("#0088FF"),
        parse_hex_color("#8800FF"),
    ];

    let timer = slint::Timer::default();
    let main_window_weak = main_window.as_weak();
    let mut phase = 0;
    timer.start(
        slint::TimerMode::Repeated,
        Duration::from_millis(150),
        move || {
            if let Some(window) = main_window_weak.upgrade() {
                if window.get_patch_enabled() {
                    window.set_patch_button_color(rainbow_colors[phase]);
                    phase = (phase + 1) % rainbow_colors.len();
                } else {
                    window.set_patch_button_color(parse_hex_color("#555555"));
                }
            }
        },
    );

    let window_weak = main_window.as_weak();
    let folder_ref = selected_folder.clone();
    main_window.on_select_folder(move || {
        let window_weak = window_weak.clone();
        let folder_ref = folder_ref.clone();

        thread::spawn(move || {
            let chosen = rfd::FileDialog::new()
                .set_title("DELTARUNE 설치 폴더 선택")
                .pick_folder();

            slint::invoke_from_event_loop(move || {
                if let Some(window) = window_weak.upgrade() {
                    let logs_model: ModelRc<LogItem> = window.get_logs();
                    let vec_model = logs_model
                        .as_any()
                        .downcast_ref::<VecModel<LogItem>>()
                        .expect("VecModel");

                    if let Some(chosen_dir) = chosen {
                        let p = resolve_game_folder(&chosen_dir);
                        let (valid, err_msg) = validate_deltarune_folder(&p);
                        if valid {
                            *folder_ref.lock().unwrap() = Some(p.clone());
                            let path_msg = format!("* 선택된 폴더: {}", redact_user_path(&p.to_string_lossy()));
                            window.set_folder_path(SharedString::from(&path_msg));
                            window.set_patch_enabled(true);
                            vec_model.push(LogItem {
                                msg: SharedString::from(&path_msg),
                                color: parse_hex_color("#00FF00"),
                            });
                            let mut current = window.get_log_text().to_string();
                            current.push_str(&path_msg);
                            current.push('\n');
                            window.set_log_text(SharedString::from(current));
                        } else {
                            *folder_ref.lock().unwrap() = None;
                            window.set_patch_enabled(false);
                            let err_line = format!(
                                "* 검증 실패: {} - {}",
                                redact_user_path(&p.to_string_lossy()),
                                err_msg.unwrap_or_default()
                            );
                            vec_model.push(LogItem {
                                msg: SharedString::from(&err_line),
                                color: parse_hex_color("#FF5555"),
                            });
                            let mut current = window.get_log_text().to_string();
                            current.push_str(&err_line);
                            current.push('\n');
                            window.set_log_text(SharedString::from(current));
                        }
                    } else {
                        let cancel_msg = "* 폴더 선택 취소";
                        vec_model.push(LogItem {
                            msg: SharedString::from(cancel_msg),
                            color: parse_hex_color("#AAAAAA"),
                        });
                        let mut current = window.get_log_text().to_string();
                        current.push_str(cancel_msg);
                        current.push('\n');
                        window.set_log_text(SharedString::from(current));
                    }
                }
            })
            .unwrap();
        });
    });


    let window_weak = main_window.as_weak();
    main_window.on_drag_window(move || {
        if let Some(window) = window_weak.upgrade() {
            window.window().with_winit_window(|winit_window| {
                let _ = winit_window.drag_window();
            });
        }
    });

    let window_weak = main_window.as_weak();
    main_window.on_toggle_advanced(move || {
        if let Some(window) = window_weak.upgrade() {
            window.set_adv_open(!window.get_adv_open());
        }
    });

    let clipboard = Arc::new(Mutex::new(arboard::Clipboard::new().ok()));

    let window_weak = main_window.as_weak();
    let clipboard_ref = clipboard.clone();
    main_window.on_copy_log(move || {
        if let Some(window) = window_weak.upgrade() {
            let logs_model: ModelRc<LogItem> = window.get_logs();
            let count = logs_model.row_count();
            let mut full_text = String::new();
            for i in 0..count {
                if let Some(item) = logs_model.row_data(i) {
                    full_text.push_str(&item.msg);
                    full_text.push('\n');
                }
            }
            let mut guard = clipboard_ref.lock().unwrap();
            if guard.is_none() {
                *guard = arboard::Clipboard::new().ok();
            }
            if let Some(ref mut cb) = *guard {
                let _ = cb.set_text(full_text);
                let vec_model = logs_model
                    .as_any()
                    .downcast_ref::<VecModel<LogItem>>()
                    .expect("VecModel");
                vec_model.push(LogItem {
                    msg: SharedString::from("* 로그가 클립보드에 복사되었습니다!"),
                    color: parse_hex_color("#FFFFFF"),
                });
            }
        }
    });

    let window_weak = main_window.as_weak();
    let folder_ref = selected_folder.clone();
    main_window.on_start_patch(move || {
        let window_weak = window_weak.clone();
        let folder = match folder_ref.lock().unwrap().clone() {
            Some(f) => f,
            None => return,
        };

        if let Some(window) = window_weak.upgrade() {
            window.set_patch_enabled(false);
            let custom_words = CustomWords {
                enabled: window.get_adv_open(),
                determination: window.get_custom_det().to_string(),
                will: window.get_custom_will().to_string(),
                dess: window.get_custom_dess().to_string(),
            };

            let window_weak_thread = window_weak.clone();
            let folder_ref_thread = folder_ref.clone();

            thread::spawn(move || {
                let folder_ref = folder_ref_thread;
                let log_window_weak = window_weak_thread.clone();
                let log_cb = move |msg: String, hex_color: &'static str| {
                    let window_weak_cb = log_window_weak.clone();
                    let msg_str = msg;
                    let _ = slint::invoke_from_event_loop(move || {
                        if let Some(window) = window_weak_cb.upgrade() {
                            let logs_model: ModelRc<LogItem> = window.get_logs();
                            let vec_model = logs_model
                                .as_any()
                                .downcast_ref::<VecModel<LogItem>>()
                                .expect("VecModel");
                            vec_model.push(LogItem {
                                msg: SharedString::from(&msg_str),
                                color: parse_hex_color(hex_color),
                            });
                            let mut current = window.get_log_text().to_string();
                            current.push_str(&msg_str);
                            current.push('\n');
                            window.set_log_text(SharedString::from(current));
                            window.invoke_scroll_to_bottom();
                        }
                    });
                };


                log_cb("--- 패치 작업 시작 ---".to_string(), "#FFFF00");

                let error_window_weak = window_weak_thread.clone();
                let on_error_detailed = |detail: String, summary: String| {
                    if !detail.trim().is_empty() {
                        for line in detail.lines() {
                            if !line.trim().is_empty() {
                                log_cb(line.to_string(), "#FF5555");
                            }
                        }
                        log_cb("------------------------".to_string(), "#888888");
                    }
                    let summary_line = if summary.starts_with('*') {
                        summary
                    } else {
                        format!("* 오류: {}", summary)
                    };
                    log_cb(summary_line, "#FF5555");
                    let error_window_weak = error_window_weak.clone();
                    let _ = slint::invoke_from_event_loop(move || {
                        if let Some(w) = error_window_weak.upgrade() {
                            w.set_patch_enabled(true);
                        }
                    });
                };
                let on_error = |summary: String| {
                    on_error_detailed(String::new(), summary);
                };

                if !folder.exists() {
                    on_error(format!("* 오류: 선택된 폴더가 존재하지 않습니다! ({:?})", folder));
                    return;
                }

                clean_tmp_files(&folder);

                let is_mac = cfg!(target_os = "macos");

                // 런처 패치 확인 (메모리 내장 데이터 또는 로컬 파일)
                let launcher_delta = get_xdelta_data(0);
                let valid_launcher_target = if launcher_delta.is_some() {
                    let target = find_launcher_data_file(&folder, is_mac);
                    if target.is_none() {
                        let expected = if is_mac { "game.ios" } else { "data.win" };
                        on_error(format!("* 검증 실패: 런처 데이터({})를 찾을 수 없습니다.", expected));
                        return;
                    }
                    target
                } else {
                    None
                };

                let mut valid_chapter_targets = Vec::new();
                for i in 1..=5 {
                    let delta = match get_xdelta_data(i) {
                        Some(d) => d,
                        None => {
                            on_error(format!("* 검증 실패: 챕터 {} 패치 데이터를 찾을 수 없습니다.", i));
                            return;
                        }
                    };

                    let folder_candidates = if is_mac {
                        vec![
                            format!("chapter{}_mac", i),
                            format!("chapter{}", i),
                        ]
                    } else {
                        vec![
                            format!("chapter{}_windows", i),
                            format!("chapter{}", i),
                        ]
                    };

                    let mut found_target = None;
                    for fn_name in &folder_candidates {
                        let cbase = folder.join(fn_name);
                        if let Some(target) = find_chapter_data_file(&cbase, is_mac) {
                            found_target = Some(target);
                            break;
                        }
                    }

                    let found_target = match found_target {
                        Some(t) => t,
                        None => {
                            let (exp_folder, exp_file) = if is_mac {
                                (format!("chapter{}_mac", i), "game.ios")
                            } else {
                                (format!("chapter{}_windows", i), "data.win")
                            };
                            on_error(format!(
                                "* 검증 실패: 챕터 {} 대상 파일([target]/{}/{})을 찾을 수 없습니다.",
                                i, exp_folder, exp_file
                            ));
                            return;
                        }
                    };

                    valid_chapter_targets.push((i, found_target, delta));
                }

                if let Some(target) = valid_launcher_target {
                    if let Some(ref delta) = launcher_delta {
                        log_cb("--- 런처 패치 적용 중 ---".to_string(), "#FFFF00");
                        if let Err(e) = patchit(&target, delta, "launcher.xdelta") {
                            on_error_detailed(e.detail, e.summary);
                            return;
                        }
                        log_cb("* 런처 패치 완료!".to_string(), "#00FF00");
                    }
                }

                for (ch_num, target_file, delta) in &valid_chapter_targets {
                    log_cb(
                        format!("--- 챕터 {} 패치 적용 중 ---", ch_num),
                        "#FFFF00",
                    );
                    if let Err(e) = patchit(target_file, delta, &format!("ch{}.xdelta", ch_num)) {
                        on_error_detailed(e.detail, e.summary);
                        return;
                    }
                    log_cb(format!("* 챕터 {} 패치 완료!", ch_num), "#00FF00");
                }

                log_cb("--- 언어 파일 및 리소스 복사 중 ---".to_string(), "#FFFF00");
                for (ch_num, _, _) in &valid_chapter_targets {
                    let dst_chapter_dir = if is_mac {
                        folder.join(format!("chapter{}_mac", ch_num))
                    } else {
                        folder.join(format!("chapter{}_windows", ch_num))
                    };

                    if let Err(e) = deploy_chapter_assets(*ch_num, &dst_chapter_dir, &log_cb) {
                        on_error(format!("* 언어/리소스 복사 오류: {}", e));
                        return;
                    }
                }

                if custom_words.enabled
                    || custom_words.determination != "의지"
                    || custom_words.will != "결의"
                    || custom_words.dess != "데스"
                {
                    log_cb(
                        "--- 고급 설정 (사용자 정의 명칭 치환) 적용 중 ---".to_string(),
                        "#FFFF00",
                    );
                    apply_custom_words(&folder, &custom_words, &log_cb);
                }

                log_cb(
                    "--- 게임 설정 (true_config.ini) 최신화 중 ---".to_string(),
                    "#FFFF00",
                );
                update_true_config(&log_cb);

                log_cb(
                    "--- 패치가 성공적으로 완료되었습니다! ---".to_string(),
                    "#00FF00",
                );
                log_cb(
                    "* 한글 패치가 성공적으로 완료되었습니다!".to_string(),
                    "#00FF00",
                );

                let window_weak = window_weak.clone();
                let folder_ref_dlg = folder_ref.clone();
                let _ = slint::invoke_from_event_loop(move || {
                    if let Some(window) = window_weak.upgrade() {
                        window.set_patch_enabled(true);

                        if let Ok(dialog) = PatchFinishedWindow::new() {
                            dialog.window().with_winit_window(|winit_window| {
                                winit_window.set_decorations(false);
                            });
                            let dialog_weak = dialog.as_weak();
                            dialog.on_launch_steam(move || {
                                let _ = open::that("steam://rungameid/1671210");
                                if let Some(d) = dialog_weak.upgrade() {
                                    let _ = d.hide();
                                }
                            });

                            let dialog_weak = dialog.as_weak();
                            let folder_ref = folder_ref_dlg.clone();
                            dialog.on_launch_direct(move || {
                                if let Some(ref folder) = *folder_ref.lock().unwrap() {
                                    if cfg!(target_os = "windows") {
                                        let exe = folder.join("DELTARUNE.exe");
                                        if exe.exists() {
                                            let _ = StdCommand::new(exe).current_dir(folder).spawn();
                                        }
                                    } else if cfg!(target_os = "macos") {
                                        let app = folder.join("DELTARUNE.app");
                                        if app.exists() {
                                            let _ = StdCommand::new("open").arg(app).spawn();
                                        } else if folder.extension().map_or(false, |e| e == "app") {
                                            let _ = StdCommand::new("open").arg(folder).spawn();
                                        }
                                    } else {
                                        let exe = folder.join("DELTARUNE");
                                        if exe.exists() {
                                            let _ = StdCommand::new(exe).current_dir(folder).spawn();
                                        }
                                    }
                                }
                                if let Some(d) = dialog_weak.upgrade() {
                                    let _ = d.hide();
                                }
                            });

                            let dialog_weak = dialog.as_weak();
                            dialog.on_close_modal(move || {
                                if let Some(d) = dialog_weak.upgrade() {
                                    let _ = d.hide();
                                }
                            });

                            let _ = dialog.show();
                        }
                    }
                });
            });
        }
    });

    let window_weak = main_window.as_weak();
    main_window.on_close_window(move || {
        if let Some(window) = window_weak.upgrade() {
            let _ = window.hide();
        }
    });

    main_window.run()
}

