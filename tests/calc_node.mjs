// Run the salary calculator's core in Node, with the same l4.wasm and
// calc-core.mjs the page loads, on the cases in a JSON file:
//
//   node tests/calc_node.mjs <spec.json> <cases.json>
//
// cases.json is [{fields, allowances}, ...]; prints one JSON line per case:
// the results calc-core.mjs reads back from the evaluator.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const assets = path.join(root, "tools", "assets");
const { instantiate, program, results } = await import(pathToFileURL(path.join(assets, "calc-core.mjs")));
const glue = (await import(pathToFileURL(path.join(assets, "l4wasm", "l4.mjs")))).default;

const spec = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const cases = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const l4dir = path.dirname(path.join(root, spec.l4));
const main = fs.readFileSync(path.join(root, spec.l4), "utf8");
const files = {};
for (const name of spec.imports) {
  const f = path.join(l4dir, name + ".l4");
  if (fs.existsSync(f)) files[name] = fs.readFileSync(f, "utf8");
}
const module = await WebAssembly.compile(fs.readFileSync(path.join(assets, "l4wasm", "l4.wasm")));
const l4 = await instantiate(glue, module);
for (const c of cases) {
  const prog = program(spec, c);
  const answer = await l4.evaluate(main + prog.text, files);
  const r = results(spec, prog, answer);
  if (r.ok && r.total) r.total.raw = undefined;
  for (const x of [...(r.components || []), ...(r.allowances || [])]) x.raw = undefined;
  console.log(JSON.stringify(r));
}
