#!/usr/bin/env node
// Post-link step of toolchain/build-wasm.sh (MMS-761): GHC's post-link.mjs
// writes two string helpers that pass a wasm i32 address straight to a
// Uint8Array view. JavaScript receives an i32 as a SIGNED number, so an
// address at or above 2 GiB becomes a negative offset and the view throws
// RangeError. This rewrites both helpers to read the address and the length
// as unsigned (`>>> 0`), and fails if either is not found exactly once —
// a new GHC that writes them differently has to be looked at, not skipped.
// Upstream: GHC issue #28132; drop this step once the GHC pinned has it.
import { readFileSync, writeFileSync } from "node:fs";

const file = process.argv[2];
if (!file) { console.error("usage: unsigned-glue.mjs <l4.mjs>"); process.exit(2); }
const rewrites = [
  ["new Uint8Array(__exports.memory.buffer, $1, $2)",
   "new Uint8Array(__exports.memory.buffer, $1 >>> 0, $2 >>> 0)"],
  ["new Uint8Array(__exports.memory.buffer, $2, $3)",
   "new Uint8Array(__exports.memory.buffer, $2 >>> 0, $3 >>> 0)"],
];
let text = readFileSync(file, "utf8");
for (const [from, to] of rewrites) {
  const n = text.split(from).length - 1;
  if (n !== 1) {
    console.error(`unsigned-glue: expected exactly one ${from} in ${file}, found ${n}`);
    process.exit(1);
  }
  text = text.replace(from, () => to);
}
writeFileSync(file, text);
console.log(`unsigned-glue: ${rewrites.length} string helpers in ${file} read pointers as unsigned`);
