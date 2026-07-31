import type { ElectrobunConfig } from "electrobun";

export default {
	app: {
		name: "DELTARUNE Korean Patcher",
		identifier: "kr.sungsoos.dtkrpatcher",
		version: "1.0.0",
	},
	build: {
		icon: "src/assets/icon.ico",
		copy: {
			"dist/index.html": "views/mainview/index.html",
			"dist/assets": "views/mainview/assets",
			"src/assets/xdelta": "assets/xdelta",
			"src/assets/lang": "assets/lang",
			"src/assets/xdelta3.exe": "assets/xdelta3.exe",
			"src/assets/xdelta3mac": "assets/xdelta3mac",
			"src/assets/xdelta3linux": "assets/xdelta3linux",
			"src/assets/icon.ico": "assets/icon.ico"
		},
		watchIgnore: ["dist/**"],
		mac: {
			bundleCEF: false,
			icon: "src/assets/icon.ico"
		},
		linux: {
			bundleCEF: false,
			icon: "src/assets/icon.ico"
		},
		win: {
			bundleCEF: false,
			icon: "src/assets/icon.ico"
		},
	},
} satisfies ElectrobunConfig;
