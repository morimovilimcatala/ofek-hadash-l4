// Run the salary calculator's core in Node, with the same l4.wasm,
// calc-core.mjs and shipped modules (assets/calc/modules.json, written by
// tools/calculator.py `ship`) the page loads, on the cases in a JSON file:
//
//   node tests/calc_node.mjs <spec.json> <modules.json> <cases.json>
//
// cases.json is [{fields, case, allowances}, ...]; prints one JSON line per
// case: the results calc-core.mjs reads back from the evaluator. One
// instance answers every case, as the page's one instance answers every click.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const assets = path.join(root, "tools", "assets");
const { instantiate, program, results } = await import(pathToFileURL(path.join(assets, "calc-core.mjs")));
const glue = (await import(pathToFileURL(path.join(assets, "l4wasm", "l4.mjs")))).default;

const spec = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const files = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const cases = JSON.parse(fs.readFileSync(process.argv[4], "utf8"));
const module = await WebAssembly.compile(fs.readFileSync(path.join(assets, "l4wasm", "l4.wasm")));
const l4 = await instantiate(glue, module);
for (const c of cases) {
  const prog = program(spec, c);
  const t0 = performance.now();
  const answer = await l4.evaluate(prog.text, files, { keep: true });
  const r = results(spec, prog, answer);
  r.seconds = (performance.now() - t0) / 1000;
  if (r.ok && r.total) r.total.raw = undefined;
  for (const x of [...(r.components || []), ...(r.allowances || [])]) x.raw = undefined;
  console.log(JSON.stringify(r));
}
