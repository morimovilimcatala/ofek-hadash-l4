// Run the committed l4.wasm in Node on a list of evaluations, one instance
// for all of them, as the page keeps one instance for every click:
//
//   node tests/wasm_eval.mjs <runs.json>
//
// runs.json is [{source, files: {module name: source}}, ...]; prints one
// JSON line per run: the evaluator's answer, and how long it took.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const assets = path.join(root, "tools", "assets");
const { instantiate } = await import(pathToFileURL(path.join(assets, "calc-core.mjs")));
const glue = (await import(pathToFileURL(path.join(assets, "l4wasm", "l4.mjs")))).default;

const runs = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const l4 = await instantiate(glue, await WebAssembly.compile(fs.readFileSync(path.join(assets, "l4wasm", "l4.wasm"))));
for (const r of runs) {
  const t0 = performance.now();
  const answer = await l4.evaluate(r.source, r.files);
  console.log(JSON.stringify({ seconds: (performance.now() - t0) / 1000, answer }));
}
