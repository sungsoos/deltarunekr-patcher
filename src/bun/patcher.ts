import { decode } from "vcdiff-decoder";
import { readFileSync, writeFileSync } from "fs";

/**
 * Applies a VCDIFF delta patch to a target binary file synchronously.
 *
 * Reads the original target file and the patch delta into memory buffers,
 * decodes the binary diff using `vcdiff-decoder`, and overwrites the target
 * file with the newly generated patched data.
 *
 * @param targetPath - Absolute or relative file path of the binary to be patched (e.g., `data.win`).
 * @param deltaPath - Absolute or relative file path of the `.xdelta` or `.vcdiff` patch file.
 */
export function applyVcdiffPatch(targetPath: string, deltaPath: string) {
	// Read source binary and delta patch into Buffer instances
	const sourceBuf = readFileSync(targetPath);
	const deltaBuf = readFileSync(deltaPath);

	// Decode binary delta against original source to reconstruct patched file contents
	const patchedBuf = decode(deltaBuf, sourceBuf);

	// Atomically write the reconstructed buffer back to target path
	writeFileSync(targetPath, Buffer.from(patchedBuf));
}

