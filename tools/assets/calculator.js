// calculator.html: the form, and what L4 answers. The work is calc-core.mjs's;
// this file is the page around it.
import { instantiate, program, results, InputError } from "./calc-core.mjs";

const spec = JSON.parse(document.getElementById("calc-spec").textContent);
const form = document.querySelector("form.calc");
const out = document.querySelector(".calc-out");
const status = form.querySelector(".status");
const go = form.querySelector(".go");
const list = form.querySelector(".allow-list");
const rowTpl = document.getElementById("allow-row");
const here = new URL(".", import.meta.url);

const el = (tag, attrs = {}, ...kids) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v; else if (k === "text") e.textContent = v; else e.setAttribute(k, v);
  }
  for (const k of kids) if (k != null) e.append(k);
  return e;
};

// "12575.2" -> "12,575.2": grouping only; the digits are L4's, never rounded
const money = (v) => {
  const m = /^(-?)(\d+)(\.\d+)?$/.exec(v || "");
  return m ? m[1] + m[2].replace(/\B(?=(\d{3})+(?!\d))/g, ",") + (m[3] || "") : v;
};
const ltr = (text, cls = "") => el("bdi", { dir: "ltr", class: cls, text });

// ------------------------------------------------------------- loading L4

let l4 = null, sources = null;
const ready = (async () => {
  const glue = (await import(new URL("l4wasm/l4.mjs", here))).default;
  const url = new URL("l4wasm/l4.wasm", here);
  let module;
  try { module = await WebAssembly.compileStreaming(fetch(url)); }
  catch { module = await WebAssembly.compile(await (await fetch(url)).arrayBuffer()); }
  const text = async (p) => { const r = await fetch(new URL(p, here)); if (!r.ok) throw new Error(p); return r.text(); };
  const files = {};
  for (const [name, path] of Object.entries(spec.files)) files[name] = await text(path);
  sources = { main: await text(spec.source), files };
  if (!sources.main.endsWith("\n")) sources.main += "\n";
  l4 = await instantiate(glue, module);
})();
ready.then(() => { status.textContent = "L4 מוכן."; go.disabled = false; },
  (e) => { status.textContent = "טעינת L4 נכשלה: " + e.message; status.classList.add("bad"); });

// ------------------------------------------------------------------- form

function addRow(kind = "", percent = "") {
  const li = rowTpl.content.firstElementChild.cloneNode(true);
  if (kind) li.querySelector("select").value = kind;
  li.querySelector("input").value = percent;
  li.querySelector(".del").addEventListener("click", () => li.remove());
  list.append(li);
  return li;
}
form.querySelector(".add").addEventListener("click", () => addRow().querySelector("select").focus());

form.querySelector(".example").addEventListener("click", () => {
  for (const f of spec.fields) {
    const input = form.querySelector(`[data-field="${CSS.escape(f.name)}"]`);
    const v = spec.example.fields[f.name];
    if (input.type === "checkbox") input.checked = !!v; else input.value = v;
  }
  list.replaceChildren();
  for (const a of spec.example.allowances) addRow(a.kind, a.percent);
});

function readForm() {
  const fields = {};
  for (const f of spec.fields) {
    const input = form.querySelector(`[data-field="${CSS.escape(f.name)}"]`);
    fields[f.name] = input.type === "checkbox" ? input.checked : input.value.trim();
  }
  const allowances = [...list.children].map((li) => ({
    kind: li.querySelector("select").value, percent: li.querySelector("input").value.trim(),
  }));
  return { fields, allowances };
}

// ---------------------------------------------------------------- results

const isLookup = (t) => t.steps.length === 1 && !t.steps[0].subs.length && t.value === "<function>";

// one node of the trace: the expression, the value it reached, and (opened
// on demand, since a salary's trace runs to thousands of steps) the steps it
// took and the sub-expressions each forced
function traceNode(t, open = false) {
  if (!t.steps.length) return el("div", { class: "tleaf" }, el("span", { class: "tv", dir: "ltr", text: "• " + t.value }));
  const sum = el("summary", {},
    el("code", { class: "te", dir: "ltr", text: t.steps[0].expr }),
    el("span", { class: "tv" + (t.error ? " err" : ""), dir: "ltr", text: "⟶ " + t.value }));
  const d = el("details", { class: "tn" + (isLookup(t) ? " lookup" : "") }, sum);
  let filled = false;
  const fill = () => {
    if (filled) return;
    filled = true;
    const body = el("div", { class: "tb" });
    t.steps.forEach((s, i) => {
      if (i) body.append(el("div", { class: "tstep" }, el("code", { dir: "ltr", text: "= " + s.expr })));
      for (const sub of s.subs) body.append(traceNode(sub));
    });
    d.append(body);
  };
  d.addEventListener("toggle", () => d.open && fill());
  if (open) { fill(); d.open = true; }
  return d;
}

function showErrors(title, items) {
  out.replaceChildren(el("div", { class: "calc-err", role: "alert" }, el("h2", { text: title }), ...items));
  out.hidden = false;
}

function show(r, prog) {
  if (!r.ok) {
    const ours = r.errors.some((e) => e.ours);
    return showErrors(ours ? "L4 דחה את הערכים שהוזנו" : "L4 דחה את הקוד של §1.1",
      [el("p", { text: ours
        ? "הבודק של L4 מצא שגיאה בקוד שהמחשבון כתב מן הטופס. ההודעה, כפי ש־L4 מדפיס אותה:"
        : "הבודק של L4 מצא שגיאה בקובץ עצמו. ההודעה, כפי ש־L4 מדפיס אותה:" }),
       ...r.errors.map((e) => el("pre", { dir: "ltr", text: e.message }))]);
  }
  if (r.failed.length) {
    return showErrors("L4 לא השלים את החישוב",
      [el("p", { text: "ההערכה נכשלה. ההודעה, כפי ש־L4 מדפיס אותה:" }),
       ...r.failed.map((f) => el("pre", { dir: "ltr", text: f.message }))]);
  }
  const tbody = el("tbody");
  for (const c of r.components) {
    tbody.append(el("tr", { class: "c" },
      el("td", {}, el("span", { class: "cl", text: c.label })),
      el("td", {}, ltr(c.cite, "cite")),
      el("td", {}, el("code", { class: "l4n", dir: "ltr", text: c.name })),
      el("td", { class: "num" }, ltr(money(c.value)))));
    if (c.name === "percentage allowances") {
      for (const a of r.allowances) {
        tbody.append(el("tr", { class: "sub" },
          el("td", {}, el("span", { class: "cl", text: a.label }), " ", ltr(a.rate, "rate")),
          el("td", {}, ltr(a.cite, "cite")),
          el("td", {}, el("code", { class: "l4n", dir: "ltr", text: spec.allowance.rule })),
          el("td", { class: "num" }, ltr(money(a.value)))));
      }
    }
  }
  const table = el("table", { class: "comp" },
    el("thead", {}, el("tr", {}, ...["רכיב", "סעיף", "הכלל ב־L4", "₪"].map((t) => el("th", { text: t })))),
    tbody);
  const tree = el("div", { class: "tree hide-lookups" }, traceNode(r.total.trace, true));
  const lookups = el("input", { type: "checkbox" });
  lookups.addEventListener("change", () => tree.classList.toggle("hide-lookups", !lookups.checked));
  out.replaceChildren(
    el("div", { class: "total" },
      el("span", {}, `${spec.root.label} `, ltr(spec.root.cite, "cite")),
      el("strong", { dir: "ltr", text: "₪ " + money(r.total.value) }),
      el("code", { class: "l4n", dir: "ltr", text: spec.root.name })),
    el("div", { class: "scroll-x" }, table),
    el("details", { class: "trace", open: "" },
      el("summary", {}, el("h2", { text: "עקבות החישוב" })),
      el("p", { class: "hint", text: "כפי ש־L4 מחשב: כל שורה היא ביטוי בקוד והערך שהגיע אליו. "
        + "לחיצה על שורה פותחת את השלבים שלה ואת תתי־הביטויים שחושבו בדרך. "
        + "שורה שממשיכה ב־= היא אותו ביטוי אחרי צעד חישוב." }),
      el("label", { class: "hint" }, lookups, " הצג גם את שלבי איתור הכללים (⟶ <function>)"),
      tree,
      el("details", { class: "raw" }, el("summary", { text: "העקבות כטקסט, כפי ש־l4 מדפיס אותן" }),
        el("pre", { dir: "ltr", text: r.total.traceText || "" }))),
    el("details", { class: "raw" }, el("summary", { text: "הקוד שהמחשבון הוסיף לקובץ והריץ" }),
      el("pre", { dir: "ltr", text: prog.text.trim() })));
  out.hidden = false;
}

form.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  status.classList.remove("bad");
  let prog;
  try { prog = program(spec, readForm()); }
  catch (e) {
    status.textContent = e instanceof InputError ? e.message : "שגיאה: " + e.message;
    status.classList.add("bad");
    return;
  }
  go.disabled = true;
  status.textContent = "מחשב…";
  try {
    await ready;
    const answer = await l4.evaluate(sources.main + prog.text, sources.files);
    show(results(spec, prog, answer), prog);
    status.textContent = "";
  } catch (e) {
    status.textContent = "ההרצה נכשלה: " + e.message;
    status.classList.add("bad");
  } finally {
    go.disabled = false;
  }
});
