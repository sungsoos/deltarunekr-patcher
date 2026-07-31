import { Electroview } from "electrobun/view";
import "./style.css";

/** Currently selected DELTARUNE game root directory path. */
let selectedFolder: string | null = null;

/** History log messages array containing message text and color styling. */
let logMessages: { msg: string; color: string }[] = [];

/** Flag indicating whether the frameless window is currently being dragged. */
let isDragging = false;

/** Initial screen X coordinate when window drag started. */
let startX = 0;

/** Initial screen Y coordinate when window drag started. */
let startY = 0;

/**
 * Electroview RPC interface instance defining client-side RPC configuration.
 */
const rpc = Electroview.defineRPC({
	maxRequestConcurrency: 10,
	maxRequestTime: Infinity,
	handlers: {
		requests: {},
		messages: {}
	}
});

/** Electrobun view manager initialized with RPC configuration. */
const electroview = new Electroview({ rpc });

/** Main container DOM element. */
const app = document.getElementById("app")!;

/**
 * Re-renders the entire main application HTML structure and updates event handlers.
 */
function render() {
	app.innerHTML = `
		<div class="patcher-window">
			<header class="patcher-titlebar" id="titlebar">
				<div class="titlebar-drag-area">
					<h1 class="patcher-title">* DELTARUNE 한글 패처</h1>
				</div>
				<div class="titlebar-controls">
					<button id="btn-close-window" class="window-close-btn" title="닫기">x</button>
				</div>
			</header>

			<section class="folder-section">
				<button id="btn-select-folder" class="pixel-btn">폴더 선택</button>
				<span id="folder-path-display" class="folder-display">* 선택된 폴더: ${selectedFolder ? truncatePath(selectedFolder) : "없음"}</span>
			</section>

			<section class="log-section">
				<div id="log-container" class="log-container"></div>
			</section>

			<footer class="patcher-footer">
				<button id="btn-close" class="pixel-btn secondary">닫기</button>
				<div class="right-buttons">
					<button id="btn-copy-log" class="pixel-btn secondary">로그 복사</button>
					<button id="btn-start-patch" class="pixel-btn primary" ${!selectedFolder ? "disabled" : ""}>패치 적용</button>
				</div>
			</footer>
		</div>
	`;

	setupEventListeners();
	renderLogs();
}

/**
 * Truncates long file system paths with ellipses for clean UI display.
 *
 * @param path - Full file system path to truncate.
 * @param maxLen - Maximum character length allowed before truncation (default: 38).
 * @returns Truncated path string with leading ellipsis if necessary.
 */
function truncatePath(path: string, maxLen = 38): string {
	if (path.length <= maxLen) return path;
	return "..." + path.slice(-(maxLen - 3));
}

/**
 * Appends a log line to the log memory buffer and directly appends it to the DOM log element.
 *
 * @param msg - Log message text to display.
 * @param color - Hex color code string for styling (default: `#FFFFFF`).
 */
function addLog(msg: string, color = "#FFFFFF") {
	logMessages.push({ msg, color });
	const logContainer = document.getElementById("log-container");
	if (logContainer) {
		const line = document.createElement("div");
		line.className = "log-line";
		line.style.color = color;
		line.textContent = msg;
		logContainer.appendChild(line);
		logContainer.scrollTop = logContainer.scrollHeight;
	}
}

/**
 * Flushes and re-renders all buffered log messages in the DOM log container.
 */
function renderLogs() {
	const logContainer = document.getElementById("log-container");
	if (!logContainer) return;
	logContainer.innerHTML = "";
	for (const item of logMessages) {
		const line = document.createElement("div");
		line.className = "log-line";
		line.style.color = item.color;
		line.textContent = item.msg;
		logContainer.appendChild(line);
	}
	logContainer.scrollTop = logContainer.scrollHeight;
}

/**
 * Attaches DOM event listeners for buttons, titlebar window dragging, and RPC triggers.
 */
function setupEventListeners() {
	/** Sends RPC request to request main application window closure. */
	const closeApp = async () => {
		try {
			await electroview.rpc?.request.closeApp({});
		} catch (e) {
			window.close();
		}
	};

	// Close window buttons
	document.getElementById("btn-close-window")?.addEventListener("click", (e) => {
		e.stopPropagation();
		closeApp();
	});

	document.getElementById("btn-close")?.addEventListener("click", (e) => {
		e.stopPropagation();
		closeApp();
	});

	// Frameless window dragging logic via mouse movement deltas
	const titlebar = document.getElementById("titlebar");
	if (titlebar) {
		titlebar.addEventListener("mousedown", (e) => {
			if ((e.target as HTMLElement).tagName === "BUTTON") return;
			isDragging = true;
			startX = e.screenX;
			startY = e.screenY;
		});

		window.addEventListener("mousemove", (e) => {
			if (!isDragging) return;
			const deltaX = e.screenX - startX;
			const deltaY = e.screenY - startY;
			startX = e.screenX;
			startY = e.screenY;
			electroview.rpc?.request.moveWindowBy({ deltaX, deltaY });
		});

		window.addEventListener("mouseup", () => {
			isDragging = false;
		});
	}

	// Folder selector dialog RPC button trigger
	document.getElementById("btn-select-folder")?.addEventListener("click", async (e) => {
		e.preventDefault();
		e.stopPropagation();
		try {
			const res: any = await electroview.rpc?.request.selectFolder({});
			if (res && res.path) {
				selectedFolder = res.path;
				addLog(`* 선택된 폴더: ${selectedFolder}`);
				render();
			} else {
				addLog("* 폴더 선택 취소", "#BBBBBB");
			}
		} catch (err: any) {
			addLog(`* 폴더 선택 오류: ${err.message}`, "#FF5555");
		}
	});

	// Start patch RPC execution trigger
	document.getElementById("btn-start-patch")?.addEventListener("click", async () => {
		if (!selectedFolder) return;
		addLog("--- 패치 작업 시작 ---", "#FFFF00");
		try {
			const res: any = await electroview.rpc?.request.startPatch({ targetDir: selectedFolder });
			if (res && res.logs && Array.isArray(res.logs)) {
				for (const item of res.logs) {
					addLog(item.msg, item.color || "#FFFFFF");
				}
			}
			if (res && res.success) {
				addLog("* 한글 패치가 성공적으로 완료되었습니다!", "#00FF00");
			} else {
				addLog(`* 패치 실패: ${res?.error || "오류"}`, "#FF5555");
			}
		} catch (err: any) {
			addLog(`* 오류 발생: ${err.message}`, "#FF5555");
		}
	});

	// Copy current log output to system clipboard
	document.getElementById("btn-copy-log")?.addEventListener("click", async () => {
		try {
			const plainText = logMessages.map(l => l.msg).join("\n");
			await navigator.clipboard.writeText(plainText);
			addLog("* 로그가 클립보드에 복사되었습니다!");
		} catch (err) {
			addLog("* 로그 복사 실패!", "#FF5555");
		}
	});
}

/**
 * Initializes patcher application state and renders initial view UI.
 */
function initPatcher() {
	render();
	addLog("* DELTARUNE 한글 패처에 오신 것을 환영합니다.");
	addLog("* 패치를 적용할 DELTARUNE 폴더를 선택해주세요.");
}

// Bootstrap application on DOM ready
if (document.readyState === "loading") {
	window.addEventListener("DOMContentLoaded", initPatcher);
} else {
	initPatcher();
}
