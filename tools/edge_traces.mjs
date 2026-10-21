// The evaluation trace of each edge case's expressions (tools/edge_traces.py,
// MMS-534), from the same l4.wasm the calculator runs:
//
//   node tools/edge_traces.mjs <spec.json>
//
// spec.json is [{id, main, files, exprs}]; prints {id: [{expr, value, traceText}]}.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const assets = path.join(path.dirname(fileURLToPath(import.meta.url)), "assets");
const { instantiate } = await import(pathToFileURL(path.join(assets, "calc-core.mjs")));
const glue = (await import(pathToFileURL(path.join(assets, "l4wasm", "l4.mjs")))).default;
const module = await WebAssembly.compile(fs.readFileSync(path.join(assets, "l4wasm", "l4.wasm")));
const l4 = await instantiate(glue, module);
const out = {};
for (const c of JSON.parse(fs.readFileSync(process.argv[2], "utf8"))) {
  const lines = c.main.split("\n").length;
  const src = c.main + "\n" + c.exprs.map((e) => "#EVALTRACE " + e).join("\n") + "\n";
  const answer = await l4.evaluate(src, c.files);
  // the directives appended after the file are the last results, in order
  const traced = (answer.results || []).filter((r) => r.range && r.range.start.line >= lines);
  out[c.id] = c.exprs.map((e, i) => ({
    expr: e,
    value: traced[i] ? traced[i].result : null,
    traceText: traced[i] ? traced[i].traceText || "" : "",
  }));
}
console.log(JSON.stringify(out));
