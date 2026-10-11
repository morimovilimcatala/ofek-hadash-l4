// The salary calculator's core, shared by the page (calculator.js) and the
// Node test (tests/calc_node.mjs): load the L4 evaluator compiled to
// WebAssembly, write the form's values as L4 beside §1.1's own source, run
// it, and read the results back. It computes nothing itself: every figure it
// returns is one the L4 evaluator printed.

// ---------------------------------------------------------------- the module

// GHC's WASM backend builds a WASI "reactor". The evaluator needs no files,
// clock or arguments of its own, so WASI is a set of stubs; the clock is
// real so that the RTS's timers work. (legalese/l4-ide jl4-wasm/README.md.)
function wasiStubs(exp) {
  const view = () => new DataView(exp.memory.buffer);
  return {
    clock_time_get: (_id, _prec, out) => { view().setBigUint64(out, BigInt(Date.now()) * 1000000n, true); return 0; },
    clock_res_get: (_id, out) => { view().setBigUint64(out, 1000n, true); return 0; },
    fd_write: () => 0, fd_read: () => 0, fd_close: () => 0, fd_seek: () => 0,
    fd_fdstat_get: () => 0, fd_fdstat_set_flags: () => 0, fd_filestat_get: () => 0,
    fd_filestat_set_size: () => 0, fd_prestat_get: () => 8, fd_prestat_dir_name: () => 8,
    path_create_directory: () => 63, path_filestat_get: () => 63, path_open: () => 63,
    poll_oneoff: () => 0, sched_yield: () => 0, random_get: (buf, len) => {
      const b = new Uint8Array(exp.memory.buffer, buf, len);
      for (let i = 0; i < len; i++) b[i] = Math.floor(Math.random() * 256);
      return 0;
    },
    proc_exit: (code) => { throw new Error("proc_exit " + code); },
    args_sizes_get: (c, s) => { view().setUint32(c, 0, true); view().setUint32(s, 0, true); return 0; },
    args_get: () => 0,
    environ_sizes_get: (c, s) => { view().setUint32(c, 0, true); view().setUint32(s, 0, true); return 0; },
    environ_get: () => 0,
  };
}

// `glue` is the default export of l4.mjs (GHC's post-link.mjs output);
// `module` a compiled WebAssembly.Module of l4.wasm.
export async function instantiate(glue, module) {
  const exp = {};
  const wasi = new Proxy(wasiStubs(exp), { get: (t, k) => (k in t ? t[k] : () => 52) }); // ENOSYS
  const inst = await WebAssembly.instantiate(module, {
    wasi_snapshot_preview1: wasi,
    ghc_wasm_jsffi: glue(exp),
  });
  Object.assign(exp, inst.exports);
  inst.exports._initialize();
  return {
    // run the source's directives; `files` are the modules it imports
    async evaluate(source, files) {
      const pairs = Object.entries(files || {});
      return JSON.parse(await inst.exports.l4_eval_files(source, JSON.stringify(pairs)));
    },
  };
}

// --------------------------------------------------------------- the program

const CALC_MONTH = "calculator month";
const CALC_ALLOWANCES = "calculator allowances";

export class InputError extends Error {}

const tick = (n) => "`" + n + "`";

function number(raw, what) {
  const s = String(raw ?? "").replace(/[,\s₪]/g, "");
  if (!/^\d+(\.\d+)?$/.test(s)) throw new InputError(`${what}: יש להזין מספר אי־שלילי (למשל 10000 או 0.5).`);
  return s;
}

function literal(field, raw) {
  if (field.type === "BOOLEAN") return raw ? "TRUE" : "FALSE";
  if (field.type === "DATE") {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(raw || ""));
    if (!m) throw new InputError(`${field.label}: יש לבחור תאריך.`);
    return `DATE_FROM_DMY ${+m[3]} ${+m[2]} ${+m[1]}`;
  }
  if (field.type === "NUMBER") return number(raw, field.label);
  throw new Error("a field of an unknown type: " + field.type);
}

// The arguments of a rule, by the type of each parameter.
function args(params, values) {
  return params.map((p) => {
    if (!(p.type in values)) throw new Error(`no value for a parameter of type ${p.type}`);
    const v = values[p.type];
    return /^`[^`]*`$/.test(v) ? v : `(${v})`;   // "f 10% x" does not parse; "f (10%) x" does
  }).join(" ");
}

// `input` = {fields: {name: value}, allowances: [{kind, percent}]}.
// Returns the L4 to append to §1.1's source and what each directive is.
export function program(spec, input) {
  const L = [];
  const a = spec.allowance;
  const kinds = new Set(a.kinds.map((k) => k.name));
  L.push("", "", "-- calculator.html: the form's values, and what the page asks of them");
  L.push(`GIVETH A ${tick(spec.record)}`, `DECIDE ${tick(CALC_MONTH)} IS`, `    ${tick(spec.record)} WITH`);
  for (const f of spec.fields) L.push(`        ${tick(f.name)} IS ${literal(f, input.fields[f.name])}`);
  const held = (input.allowances || []).map((h, i) => {
    if (!kinds.has(h.kind)) throw new InputError("תוספת שאינה ברשימה.");
    const rate = number(h.percent, `שיעור התוספת ה־${i + 1}`) + "%";
    const n = `calculator allowance ${i + 1}`;
    L.push(`GIVETH A ${tick(a.record)}`, `DECIDE ${tick(n)} IS`, `    ${tick(a.record)} WITH`,
      `        ${tick(a.kindField)} IS ${tick(h.kind)}`, `        ${tick(a.rateField)} IS ${rate}`);
    return { kind: h.kind, rate, name: n };
  });
  L.push(`GIVETH A LIST OF ${tick(a.record)}`, `DECIDE ${tick(CALC_ALLOWANCES)} IS`,
    "    LIST" + (held.length ? " " + held.map((h) => tick(h.name)).join(", ") : ""));
  const values = { [spec.record]: tick(CALC_MONTH), ["LIST OF " + a.record]: tick(CALC_ALLOWANCES) };
  const directives = [];
  const directive = (kind, text, extra) => {
    directives.push({ kind, line: spec.lines + L.length, ...extra });   // 0-based line it lands on
    L.push(text);
  };
  for (const c of spec.components) directive("component", `#EVAL ${tick(c.name)} ${args(c.params, values)}`, { name: c.name });
  held.forEach((h, i) => {
    const v = { ...values, [a.params[0].type]: tick(h.kind), NUMBER: h.rate };
    directive("allowance", `#EVAL ${tick(a.rule)} ${args(a.params, v)}`, { index: i, allowance: h.kind, rate: h.rate });
  });
  directive("total", `#EVALTRACE ${tick(spec.root.name)} ${args(spec.root.params, values)}`, {});
  return { text: L.join("\n") + "\n", directives };
}

// --------------------------------------------------------------- the results

// Read the evaluator's answer back against the directives `program` wrote.
// {ok: false, errors: [{line, message, ours}]} or {ok: true, total, ...}.
export function results(spec, prog, answer) {
  if (!answer.success) {
    return {
      ok: false,
      errors: (answer.diagnostics || []).map((d) => ({
        line: d.range ? d.range.start.line : null,
        ours: d.range ? d.range.start.line >= spec.lines : false,
        message: d.message,
      })),
    };
  }
  const at = new Map((answer.results || []).filter((r) => r.range).map((r) => [r.range.start.line, r]));
  const read = (d) => {
    const r = at.get(d.line);
    if (!r) return { value: null, failed: true, message: "no result" };
    return { value: r.success ? r.result.trim() : null, failed: !r.success, message: r.success ? "" : r.result, raw: r };
  };
  const out = { ok: true, components: [], allowances: [], total: null };
  for (const d of prog.directives) {
    const r = read(d);
    if (d.kind === "component") {
      const c = spec.components.find((c) => c.name === d.name);
      out.components.push({ ...c, ...r });
    } else if (d.kind === "allowance") {
      const k = spec.allowance.kinds.find((k) => k.name === d.allowance);
      out.allowances.push({ ...k, rate: d.rate, ...r });
    } else {
      out.total = { ...r, trace: r.raw && r.raw.trace, traceText: r.raw && r.raw.traceText };
    }
  }
  out.failed = [...out.components, ...out.allowances, out.total].filter((r) => r.failed);
  return out;
}
