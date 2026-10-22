// The salary calculator's evaluator, off the page's thread: loading the law
// (salary-root and every module it reaches) takes the evaluator half a
// minute or more the first time, and the page must stay usable meanwhile.
// One instance answers every request, one at a time, keeping the imports'
// evaluation between them (calc-core.mjs `evaluate`, `keep`).
import { instantiate } from "./calc-core.mjs";

const here = new URL(".", import.meta.url);
const ready = (async () => {
  const glue = (await import(new URL("l4wasm/l4.mjs", here))).default;
  const url = new URL("l4wasm/l4.wasm", here);
  let module;
  try { module = await WebAssembly.compileStreaming(fetch(url)); }
  catch { module = await WebAssembly.compile(await (await fetch(url)).arrayBuffer()); }
  return instantiate(glue, module);
})();

let files = null;
let queue = Promise.resolve();
self.onmessage = (e) => {
  const { id, source, modules } = e.data;
  queue = queue.then(async () => {
    try {
      const l4 = await ready;
      if (!files) {
        const r = await fetch(modules);
        if (!r.ok) throw new Error(modules);
        files = await r.json();
      }
      self.postMessage({ id, answer: await l4.evaluate(source, files, { keep: true }) });
    } catch (err) {
      self.postMessage({ id, error: String((err && err.message) || err) });
    }
  });
};
