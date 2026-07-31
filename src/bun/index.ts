import { BrowserWindow, BrowserView, Updater, Utils } from "electrobun/bun";
import { existsSync, readdirSync, statSync, copyFileSync, mkdirSync, readFileSync, writeFileSync, chmodSync, unlinkSync } from "fs";
import { join, basename, resolve } from "path";

/** Vite HMR server port used during local frontend development. */
const DEV_SERVER_PORT = 5173;

/** URL for Vite development server with Hot Module Replacement (HMR). */
const DEV_SERVER_URL = `http://localhost:${DEV_SERVER_PORT}`;

/**
 * Resolves the entry point URL for the main browser view.
 * 
 * In 'dev' channel, attempts to ping the Vite dev server for HMR support.
 * Falls back to local application HTML scheme (`views://mainview/index.html`).
 *
 * @returns Promise resolving to the target view URL.
 */
async function getMainViewUrl(): Promise<string> {
	const channel = await Updater.localInfo.channel();
	if (channel === "dev") {
		try {
			await fetch(DEV_SERVER_URL, { method: "HEAD" });
			console.log(`HMR enabled: Using Vite dev server at ${DEV_SERVER_URL}`);
			return DEV_SERVER_URL;
		} catch {
			console.log(
				"Vite dev server not running. Run 'bun run dev:hmr' for HMR support.",
			);
		}
	}
	return "views://mainview/index.html";
}

const url = await getMainViewUrl();

/** Cached directory path for assets to avoid repeated filesystem traversals. */
let cachedAssetsDir: string | null = null;

/**
 * Locates the runtime `assets` directory by checking candidate paths for both
 * packaged production builds and development source directory trees.
 *
 * @returns Resolved absolute path to the assets directory.
 */
function getAssetsDir(): string {
	if (cachedAssetsDir) return cachedAssetsDir;

	// Candidates for production builds (bundled Resources folder)
	const prodCandidates = [
		join(process.cwd(), "assets"),
		join(process.cwd(), "Resources", "assets"),
		join(process.cwd(), "..", "Resources", "assets"),
		join(process.cwd(), "..", "assets"),
	];

	for (const cand of prodCandidates) {
		const res = resolve(cand);
		if (existsSync(res)) {
			cachedAssetsDir = res;
			return cachedAssetsDir;
		}
	}

	// Traverse parent directories to locate src/assets during development
	let current = process.cwd();
	for (let i = 0; i < 8; i++) {
		const testPath = join(current, "src", "assets");
		if (existsSync(testPath)) {
			cachedAssetsDir = resolve(testPath);
			return cachedAssetsDir;
		}
		const parent = join(current, "..");
		if (parent === current) break;
		current = parent;
	}

	// Default fallback path
	cachedAssetsDir = resolve(join(process.cwd(), "src", "assets"));
	return cachedAssetsDir;
}

/**
 * Recursively copies all files and directories from a source path to a destination path.
 *
 * @param srcDir - Source directory path.
 * @param dstDir - Target destination directory path.
 * @param onLog - Optional callback function to emit progress messages to the UI logger.
 */
function copyFolderRecursive(srcDir: string, dstDir: string, onLog?: (msg: string, color?: string) => void) {
	if (!existsSync(dstDir)) {
		mkdirSync(dstDir, { recursive: true });
	}
	const entries = readdirSync(srcDir);
	for (const entry of entries) {
		const srcPath = join(srcDir, entry);
		const dstPath = join(dstDir, entry);
		if (statSync(srcPath).isDirectory()) {
			copyFolderRecursive(srcPath, dstPath, onLog);
		} else {
			copyFileSync(srcPath, dstPath);
			if (onLog) {
				onLog(`  * 복사 완료: ${basename(dstPath)}`, "#88FF88");
			}
		}
	}
}

/**
 * Resolves the appropriate platform-specific xdelta3 executable binary.
 *
 * @param assetsDir - Absolute path to the main assets directory.
 * @returns Path to the existing or target xdelta3 binary executable.
 */
function getXdeltaExecutablePath(assetsDir: string): string {
	const platform = process.platform;
	let binaryName = "xdelta3.exe";
	if (platform === "darwin") binaryName = "xdelta3mac";
	if (platform === "linux") binaryName = "xdelta3linux";

	const candidatePaths = [
		join(assetsDir, binaryName),
		join(assetsDir, binaryName.replace("mac", "-mac").replace("linux", "-linux")),
		join(assetsDir, "xdelta3.exe"),
		join(assetsDir, "xdelta3"),
	];

	for (const p of candidatePaths) {
		if (existsSync(p)) return p;
	}
	return join(assetsDir, binaryName);
}

/**
 * Ensures POSIX executable permissions (`0o755`) are set on macOS and Linux systems.
 *
 * @param exePath - Absolute path to the binary executable.
 */
function ensureExecutablePermissions(exePath: string) {
	if (process.platform !== "win32" && existsSync(exePath)) {
		try {
			chmodSync(exePath, 0o755);
		} catch (e: any) {
			console.warn(`Could not set chmod on ${exePath}: ${e.message}`);
		}
	}
}

/**
 * Applies an xdelta3 patch to a target game data file using Bun process spawning.
 *
 * Creates a temporary output file (`.tmp`), invokes xdelta3 binary decoding,
 * and atomically replaces the original target file upon successful execution.
 *
 * @param targetFile - Target binary file to patch (e.g., `data.win` or `game.ios`).
 * @param deltaFile - Binary `.xdelta` patch file.
 * @param xdeltaExe - Path to the xdelta3 CLI executable binary.
 * @throws {Error} If target file missing or xdelta binary process returns non-zero exit code.
 */
function applyPatch(targetFile: string, deltaFile: string, xdeltaExe: string) {
	if (!existsSync(targetFile)) {
		throw new Error(`대상 파일이 손실되었습니다: ${targetFile}`);
	}

	ensureExecutablePermissions(xdeltaExe);
	const tmpFile = targetFile + ".tmp";
	if (existsSync(tmpFile)) unlinkSync(tmpFile);

	// Execute binary patching via xdelta3 CLI process
	const proc = Bun.spawnSync([xdeltaExe, "-d", "-s", targetFile, deltaFile, tmpFile]);

	if (proc.exitCode !== 0 || !existsSync(tmpFile)) {
		const stderrMsg = proc.stderr?.toString().trim() || `Exit code ${proc.exitCode}`;
		throw new Error(`xdelta3 patch failed: ${stderrMsg}`);
	}

	// Overwrite original file with patched output and clean up temp file
	copyFileSync(tmpFile, targetFile);
	unlinkSync(tmpFile);
}

/**
 * Generates platform-specific candidate directory names for a given game chapter.
 *
 * @param chapterNum - Chapter number (1 through 5).
 * @returns Array of candidate directory name strings.
 */
function getChapterTargetFolderNames(chapterNum: number): string[] {
	return [
		`chapter${chapterNum}_windows`,
		`chapter${chapterNum}_mac`,
		`chapter${chapterNum}_linux`,
		`chapter${chapterNum}`,
	];
}

/**
 * RPC bridge handling inter-process communication (IPC) between the Electrobun
 * backend (Bun main process) and the Electrobun frontend renderer (BrowserView).
 */
const rpc = BrowserView.defineRPC({
	maxRequestConcurrency: 10,
	maxRequestTime: Infinity,
	handlers: {
		requests: {
			/**
			 * Displays native file system dialog for selecting the target DELTARUNE installation folder.
			 *
			 * @returns Object containing chosen directory path or `null` if cancelled.
			 */
			selectFolder: async () => {
				const paths = await Utils.openFileDialog({
					startingFolder: process.env.USERPROFILE || process.env.HOME || "/",
					allowedFileTypes: "*",
					canChooseFiles: false,
					canChooseDirectory: true,
					allowsMultipleSelection: false,
				});
				if (paths && paths.length > 0 && paths[0] !== "" && paths[0] !== null) {
					return { path: paths[0] };
				}
				return { path: null };
			},

			/**
			 * Closes the application main window.
			 *
			 * @returns Status object indicating success.
			 */
			closeApp: async () => {
				mainWindow.close();
				return { success: true };
			},

			/**
			 * Moves main application window by specified coordinate offsets (used for frameless window dragging).
			 *
			 * @param param0 - Coordinate delta offsets.
			 * @returns Status object indicating success.
			 */
			moveWindowBy: async ({ deltaX, deltaY }: { deltaX: number; deltaY: number }) => {
				const pos = mainWindow.getPosition();
				mainWindow.setPosition(pos.x + deltaX, pos.y + deltaY);
				return { success: true };
			},

			/**
			 * Main patch execution handler.
			 * Performs validation of game files (launcher, chapters 1-5, language assets),
			 * applies xdelta3 binary patches, and copies Korean translation assets.
			 *
			 * @param param0 - Contains path to target DELTARUNE installation directory.
			 * @returns Detailed result object with success flag, statistics, and log entries.
			 */
			startPatch: async ({ targetDir }: { targetDir: string }) => {
				const assetsDir = getAssetsDir();
				const xdeltaDir = join(assetsDir, "xdelta");
				const xdeltaExe = getXdeltaExecutablePath(assetsDir);
				const logEvents: { msg: string; color?: string }[] = [];
				const sendProgress = (msg: string, color?: string) => {
					logEvents.push({ msg, color });
				};

				// Pre-execution existence checks
				if (!targetDir || !existsSync(targetDir)) {
					const err = `선택된 폴더가 존재하지 않거나 삭제되었습니다! (${targetDir})`;
					sendProgress(`* 오류: ${err}`, "#FF5555");
					return { success: false, error: err, logs: logEvents };
				}

				if (!existsSync(xdeltaExe)) {
					const err = `xdelta3 실행 파일을 찾을 수 없습니다: ${xdeltaExe}`;
					sendProgress(`* 오류: ${err}`, "#FF5555");
					return { success: false, error: err, logs: logEvents };
				}

				try {
					sendProgress("--- 설치 파일 엄격 검증 시작 ---", "#FFFF00");

					// 1. Verify launcher patch & target game binary (data.win / game.ios)
					const launcherDelta = join(xdeltaDir, "launcher.xdelta");
					if (!existsSync(launcherDelta)) {
						const err = `패처에서 런처 패치 파일이 존재하지 않습니다.`;
						sendProgress(`* 검증 실패: ${err}`, "#FF5555");
						return { success: false, error: err, logs: logEvents };
					}

					const possibleLauncherTargets = [
						join(targetDir, "data.win"),
						join(targetDir, "game.ios"),
						join(targetDir, "DELTARUNE.app", "Contents", "Resources", "game.ios"),
						join(targetDir, "DELTARUNE.app", "Contents", "Resources", "data.win"),
					];

					let validLauncherTarget: string | null = null;
					for (const launcherTarget of possibleLauncherTargets) {
						if (existsSync(launcherTarget)) {
							validLauncherTarget = launcherTarget;
							break;
						}
					}

					if (!validLauncherTarget) {
						const err = `런처 데이터(data.win / game.ios)를 찾을 수 없습니다.`;
						sendProgress(`* 검증 실패: ${err}`, "#FF5555");
						return { success: false, error: err, logs: logEvents };
					}

					sendProgress(`* 런처 데이터 검증 성공: ${basename(validLauncherTarget)}`, "#00FF00");

					// 2. Verify all chapter patch files and target chapter binaries (ch1 through ch5)
					const validChapterTargets: { chapter: number; targetFile: string; deltaFile: string }[] = [];

					for (let i = 1; i <= 5; i++) {
						const delta = join(xdeltaDir, `ch${i}.xdelta`);
						if (!existsSync(delta)) {
							const err = `챕터 ${i} 패치 파일(ch${i}.xdelta)이 존재하지 않습니다.`;
							sendProgress(`* 검증 실패: ${err}`, "#FF5555");
							return { success: false, error: err, logs: logEvents };
						}

						const folderCandidates = getChapterTargetFolderNames(i);
						let foundTarget: string | null = null;
						for (const folderName of folderCandidates) {
							const chapterBase = join(targetDir, folderName);
							const possibleTargets = [
								join(chapterBase, "data.win"),
								join(chapterBase, "game.ios"),
							];
							for (const targetFile of possibleTargets) {
								if (existsSync(targetFile)) {
									foundTarget = targetFile;
									break;
								}
							}
							if (foundTarget) break;
						}

						if (!foundTarget) {
							const err = `챕터 ${i} 설치 폴더 또는 대상 파일(data.win/game.ios)을 찾을 수 없습니다.`;
							sendProgress(`* 검증 실패: ${err}`, "#FF5555");
							return { success: false, error: err, logs: logEvents };
						}

						validChapterTargets.push({ chapter: i, targetFile: foundTarget, deltaFile: delta });
						sendProgress(`* 챕터 ${i} 검증 성공: ${basename(foundTarget)}`, "#00FF00");
					}

					// 3. Verify Korean translation language folder
					const langSrc = join(assetsDir, "lang");
					if (!existsSync(langSrc)) {
						const err = `패처에서 언어 폴더를 찾을 수 없습니다.`;
						sendProgress(`* 검증 실패: ${err}`, "#FF5555");
						return { success: false, error: err, logs: logEvents };
					}

					sendProgress(`* 언어 리소스 검증 성공`, "#00FF00");
					sendProgress("--- 모든 검증 완료! 패치 작업을 실행합니다 ---", "#00FF00");

					let patchedCount = 0;

					// Execute Launcher patch
					if (!existsSync(targetDir) || !existsSync(validLauncherTarget)) {
						throw new Error(`패치 도중 폴더 또는 파일이 손실되었습니다!`);
					}
					sendProgress("--- 런처 패치 적용 중 ---", "#FFFF00");
					applyPatch(validLauncherTarget, launcherDelta, xdeltaExe);
					sendProgress(`* 런처 패치 완료!`, "#00FF00");
					patchedCount++;

					// Execute Chapter patches
					for (const item of validChapterTargets) {
						if (!existsSync(targetDir) || !existsSync(item.targetFile)) {
							throw new Error(`패치 도중 챕터 ${item.chapter} 폴더 또는 파일이 손실되었습니다!`);
						}
						sendProgress(`--- 챕터 ${item.chapter} 패치 적용 중 ---`, "#FFFF00");
						applyPatch(item.targetFile, item.deltaFile, xdeltaExe);
						sendProgress(`* 챕터 ${item.chapter} 패치 완료!`, "#00FF00");
						patchedCount++;
					}

					// Copy language pack asset files to target DELTARUNE directory
					sendProgress("--- 언어 파일 복사 중 ---", "#FFFF00");
					let copiedLangCount = 0;
					const items = readdirSync(langSrc);
					for (const item of items) {
						if (!existsSync(targetDir)) {
							throw new Error(`복사 도중 대상 폴더가 손실되었습니다!`);
						}
						const srcPath = join(langSrc, item);
						const dstPath = join(targetDir, item);
						if (statSync(srcPath).isDirectory()) {
							copyFolderRecursive(srcPath, dstPath, sendProgress);
							copiedLangCount++;
						} else {
							copyFileSync(srcPath, dstPath);
							sendProgress(`  * 복사 완료: ${item}`, "#88FF88");
							copiedLangCount++;
						}
					}

					sendProgress("--- 패치가 성공적으로 완료되었습니다! ---", "#00FF00");
					return { success: true, patchedCount, copiedLangCount, logs: logEvents };
				} catch (e: any) {
					console.error("Patch execution failed:", e);
					sendProgress(`* 오류 발생: ${e.message}`, "#FF5555");
					return { success: false, error: e.message, logs: logEvents };
				}
			}
		},
		messages: {}
	}
});

/** Main application window instance configured with custom frameless styling and titlebar. */
const mainWindow = new BrowserWindow({
	title: "DELTARUNE 한글 패처",
	url,
	rpc,
	icon: join(getAssetsDir(), "icon.ico"),
	titleBarStyle: "hidden",
	styleMask: {
		Borderless: true,
		Titled: false,
		Closable: true,
		Miniaturizable: true,
		Resizable: false,
	},
	transparent: true,
	passthrough: false,
	frame: {
		width: 700,
		height: 600,
		x: 200,
		y: 200,
	},
});

