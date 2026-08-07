use std::collections::HashMap;
use std::fs::{self, File};
use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::process::Command as StdCommand;
use std::rc::Rc;
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;

use ini::Ini;
use serde_json::Value;
use slint::{Color, Model, ModelRc, SharedString, VecModel};

slint::include_modules!();

fn resource_path<P: AsRef<Path>>(relative_path: P) -> PathBuf {
    let rel = relative_path.as_ref();

    if let Ok(exe_path) = std::env::current_exe() {
        if let Some(exe_dir) = exe_path.parent() {
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

fn validate_deltarune_folder(target_dir: &Path) -> (bool, Option<String>) {
    if !target_dir.exists() {
        return (false, Some("폴더가 존재하지 않습니다.".to_string()));
    }

    let is_mac = cfg!(target_os = "macos");

    let possible_launcher_targets = [
        target_dir.join("data.win"),
        target_dir.join("game.ios"),
        target_dir
            .join("DELTARUNE.app")
            .join("Contents")
            .join("Resources")
            .join("game.ios"),
        target_dir
            .join("DELTARUNE.app")
            .join("Contents")
            .join("Resources")
            .join("data.win"),
    ];
    let has_launcher = possible_launcher_targets.iter().any(|t| t.exists());
    if !has_launcher {
        return (
            false,
            Some("런처 파일(data.win / game.ios)을 찾을 수 없습니다.".to_string()),
        );
    }

    for i in 1..=5 {
        let folder_candidates = if is_mac {
            vec![format!("chapter{}_mac", i), format!("chapter{}_windows", i), format!("chapter{}", i)]
        } else {
            vec![format!("chapter{}_windows", i), format!("chapter{}", i)]
        };

        let mut found_target = false;
        for fn_name in &folder_candidates {
            let cbase = target_dir.join(fn_name);
            if cbase.join("data.win").exists() || cbase.join("game.ios").exists() {
                found_target = true;
                break;
            }
        }

        if !found_target {
            return (
                false,
                Some(format!(
                    "챕터 {} 데이터 파일(chapter{}_[windows/mac]/data.win)이 존재하지 않습니다.",
                    i, i
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
            if let Ok(real_dir) = fs::canonicalize(&s_dir) {
                if !steam_libraries.contains(&real_dir) {
                    steam_libraries.push(real_dir.clone());
                }
                let vdf = real_dir.join("steamapps").join("libraryfolders.vdf");
                for parsed in is_libraryfolders_vdf(&vdf) {
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
            if let Ok(real_path) = fs::canonicalize(&common_path) {
                let (valid, _) = validate_deltarune_folder(&real_path);
                if valid {
                    return Some(real_path);
                }
            }
        }
    }

    None
}

fn redact_user_path(path_str: &str) -> String {
    let mut s = path_str.to_string();
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
        return Some(bundled);
    }

    if let Ok(path) = which::which("xdelta3") {
        return Some(path);
    }

    None
}

fn patchit(target_file: &Path, delta_file: &Path) -> Result<(), String> {
    let clean_target = redact_user_path(&target_file.to_string_lossy());
    let clean_delta = redact_user_path(&delta_file.to_string_lossy());

    if !target_file.exists() {
        return Err(format!("패치할 파일이 존재하지 않습니다: {}", clean_target));
    }
    if !delta_file.exists() {
        return Err(format!("델타 파일이 존재하지 않습니다: {}", clean_delta));
    }

    let delta_size = fs::metadata(delta_file).map(|m| m.len()).unwrap_or(0);
    let target_size = fs::metadata(target_file).map(|m| m.len()).unwrap_or(0);

    if delta_size == 0 {
        return Err(format!("패치 파일이 비어있습니다 (0 byte): {}", clean_delta));
    }
    if target_size == 0 {
        return Err(format!("대상 파일이 비어있습니다 (0 byte): {}", clean_target));
    }

    let tmp_file = target_file.with_extension(format!(
        "{}.tmp",
        target_file.extension().unwrap_or_default().to_string_lossy()
    ));

    if tmp_file.exists() {
        let _ = fs::remove_file(&tmp_file);
    }

    let mut patched_ok = false;

    let xdelta3_bin = get_xdelta3_binary();
    if let Some(ref bin) = xdelta3_bin {
        let output = StdCommand::new(bin)
            .args([
                "-d",
                "-f",
                "-s",
                target_file.to_str().unwrap_or_default(),
                delta_file.to_str().unwrap_or_default(),
                tmp_file.to_str().unwrap_or_default(),
            ])
            .output();

        if let Ok(out) = output {
            if out.status.success()
                && tmp_file.exists()
                && fs::metadata(&tmp_file).map(|m| m.len()).unwrap_or(0) > 0
            {
                patched_ok = true;
            }
        }
    }

    if !patched_ok {
        let res = std::panic::catch_unwind(|| {
            if let (Ok(patch_bytes), Ok(delta_bytes)) = (fs::read(target_file), fs::read(delta_file)) {
                let mut delta_cursor = std::io::Cursor::new(delta_bytes);
                let mut patch_cursor = std::io::Cursor::new(patch_bytes);
                let mut out_buf = Vec::new();

                if vcdiff_decoder::apply_patch(&mut delta_cursor, Some(&mut patch_cursor), &mut out_buf).is_ok() {
                    if fs::write(&tmp_file, out_buf).is_ok()
                        && tmp_file.exists()
                        && fs::metadata(&tmp_file).map(|m| m.len()).unwrap_or(0) > 0
                    {
                        return true;
                    }
                }
            }
            false
        });
        if let Ok(true) = res {
            patched_ok = true;
        }
    }

    if !patched_ok || !tmp_file.exists() {
        return Err("이미 패치되었거나 원본 파일 버전이 일치하지 않습니다.".to_string());
    }

    fs::copy(&tmp_file, target_file).map_err(|e| e.to_string())?;
    let _ = fs::remove_file(&tmp_file);

    Ok(())
}

fn copy_folder<F>(src_dir: &Path, dst_dir: &Path, log_cb: &F) -> Result<(), String>
where
    F: Fn(String, &'static str),
{
    if !dst_dir.exists() {
        fs::create_dir_all(dst_dir).map_err(|e| e.to_string())?;
    }
    if let Ok(entries) = fs::read_dir(src_dir) {
        for entry in entries.flatten() {
            let src_path = entry.path();
            let file_name = entry.file_name();
            let dst_path = dst_dir.join(&file_name);
            if src_path.is_dir() {
                copy_folder(&src_path, &dst_path, log_cb)?;
            } else {
                fs::copy(&src_path, &dst_path).map_err(|e| e.to_string())?;
                log_cb(
                    format!("  * 복사 완료: {}", file_name.to_string_lossy()),
                    "#88FF88",
                );
            }
        }
    }
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
    let deterwill_path = resource_path("assets/deterwill.json");
    let deterwill_path = if deterwill_path.exists() {
        deterwill_path
    } else {
        resource_path("patch/deterwill.json")
    };
    let deterwill_path = if deterwill_path.exists() {
        deterwill_path
    } else {
        resource_path("deterwill.json")
    };

    if !deterwill_path.exists() {
        log_cb(
            "* deterwill.json 치환 정의 파일을 찾을 수 없어 명칭 치환을 건너뜁니다.".to_string(),
            "#FFFF00",
        );
        return;
    }

    let file_content = match fs::read_to_string(&deterwill_path) {
        Ok(c) => c,
        Err(e) => {
            log_cb(format!("* 명칭 치환 파일 읽기 실패: {}", e), "#FF5555");
            return;
        }
    };

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
        target_dir.join("game.ios.tmp"),
    ];
    for i in 1..=5 {
        for fn_name in [
            format!("chapter{}_windows", i),
            format!("chapter{}_mac", i),
            format!("chapter{}", i),
        ] {
            tmp_candidates.push(target_dir.join(&fn_name).join("data.win.tmp"));
            tmp_candidates.push(target_dir.join(&fn_name).join("game.ios.tmp"));
            tmp_candidates.push(
                target_dir
                    .join(&fn_name)
                    .join("lang")
                    .join("lang_ja.json.tmp"),
            );
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
    let main_window = MainWindow::new()?;

    let logs_model = Rc::new(VecModel::<LogItem>::default());
    main_window.set_logs(ModelRc::from(logs_model.clone()));


    let mut initial_log = String::new();
    let selected_folder = Arc::new(Mutex::new(Option::<PathBuf>::None));

    if let Some(auto_path) = detect_deltarune() {
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

                    if let Some(p) = chosen {
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
            let _ = window.window().dispatch_event(slint::platform::WindowEvent::PointerPressed {
                position: slint::LogicalPosition::new(0.0, 0.0),
                button: slint::platform::PointerEventButton::Left,
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
                let on_error = |err_msg: String| {
                    log_cb(err_msg, "#FF5555");
                    let error_window_weak = error_window_weak.clone();
                    let _ = slint::invoke_from_event_loop(move || {
                        if let Some(w) = error_window_weak.upgrade() {
                            w.set_patch_enabled(true);
                        }
                    });
                };

                if !folder.exists() {
                    on_error(format!("* 오류: 선택된 폴더가 존재하지 않습니다! ({:?})", folder));
                    return;
                }

                clean_tmp_files(&folder);

                let patch_dir = resource_path("patch");
                let is_mac = cfg!(target_os = "macos");

                let xdelta_folder = if is_mac
                    && (patch_dir.join("xdelta_mac").exists()
                        || !patch_dir.join("xdelta").exists())
                {
                    "xdelta_mac"
                } else {
                    "xdelta"
                };
                let xdelta_dir = patch_dir.join(xdelta_folder);

                let lang_folder = if is_mac
                    && (patch_dir.join("lang_mac").exists()
                        || !patch_dir.join("lang").exists())
                {
                    "lang_mac"
                } else {
                    "lang"
                };
                let lang_src = patch_dir.join(lang_folder);

                let launcher_delta = xdelta_dir.join("launcher.xdelta");
                let mut valid_launcher_target = None;
                if launcher_delta.exists() {
                    let possible_targets = [
                        folder.join("data.win"),
                        folder.join("game.ios"),
                        folder
                            .join("DELTARUNE.app")
                            .join("Contents")
                            .join("Resources")
                            .join("game.ios"),
                        folder
                            .join("DELTARUNE.app")
                            .join("Contents")
                            .join("Resources")
                            .join("data.win"),
                    ];
                    for t in possible_targets {
                        if t.exists() {
                            valid_launcher_target = Some(t);
                            break;
                        }
                    }

                    if valid_launcher_target.is_none() {
                        on_error("* 검증 실패: 런처 데이터(data.win / game.ios)를 찾을 수 없습니다.".to_string());
                        return;
                    }
                }

                let mut valid_chapter_targets = Vec::new();
                for i in 1..=5 {
                    let delta = xdelta_dir.join(format!("ch{}.xdelta", i));
                    if !delta.exists() {
                        on_error(format!(
                            "* 검증 실패: 챕터 {} 패치 파일({}/ch{}.xdelta)이 존재하지 않습니다.",
                            i, xdelta_folder, i
                        ));
                        return;
                    }

                    let folder_candidates = if is_mac {
                        vec![
                            format!("chapter{}_mac", i),
                            format!("chapter{}_windows", i),
                            format!("chapter{}", i),
                        ]
                    } else {
                        vec![format!("chapter{}_windows", i), format!("chapter{}", i)]
                    };

                    let mut found_target = None;
                    for fn_name in &folder_candidates {
                        let cbase = folder.join(fn_name);
                        for tf_name in ["data.win", "game.ios"] {
                            let tf = cbase.join(tf_name);
                            if tf.exists() {
                                found_target = Some(tf);
                                break;
                            }
                        }
                        if found_target.is_some() {
                            break;
                        }
                    }

                    let found_target = match found_target {
                        Some(t) => t,
                        None => {
                            on_error(format!(
                                "* 검증 실패: 챕터 {} 대상 파일([target]/chapter{}_[mac/windows]/data.win)을 찾을 수 없습니다.",
                                i, i
                            ));
                            return;
                        }
                    };

                    valid_chapter_targets.push((i, found_target, delta));
                }

                if !lang_src.exists() {
                    on_error(format!(
                        "* 검증 실패: 패처에서 언어 폴더(./patch/{})를 찾을 수 없습니다.",
                        lang_folder
                    ));
                    return;
                }

                if let Some(target) = valid_launcher_target {
                    if launcher_delta.exists() {
                        log_cb("--- 런처 패치 적용 중 ---".to_string(), "#FFFF00");
                        if let Err(e) = patchit(&target, &launcher_delta) {
                            on_error(format!("* 오류: {}", e));
                            return;
                        }
                        log_cb("* 런처 패치 완료!".to_string(), "#00FF00");
                    }
                }

                for (ch_num, target_file, delta_file) in valid_chapter_targets {
                    log_cb(
                        format!("--- 챕터 {} 패치 적용 중 ---", ch_num),
                        "#FFFF00",
                    );
                    if let Err(e) = patchit(&target_file, &delta_file) {
                        on_error(format!("* 오류: {}", e));
                        return;
                    }
                    log_cb(format!("* 챕터 {} 패치 완료!", ch_num), "#00FF00");
                }

                log_cb("--- 언어 파일 복사 중 ---".to_string(), "#FFFF00");
                if let Err(e) = copy_folder(&lang_src, &folder, &log_cb) {
                    on_error(format!("* 언어 복사 오류: {}", e));
                    return;
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
