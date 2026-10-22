// calculator.html: the form, and what the law answers (MMS-525). The work
// is calc-core.mjs's, run in calc-worker.mjs; this file is the page around it.
import { program, results, InputError } from "./calc-core.mjs";

const spec = JSON.parse(document.getElementById("calc-spec").textContent);
const form = document.querySelector("form.calc");
const out = document.querySelector(".calc-out");
const status = form.querySelector(".status");
const go = form.querySelector(".go");
const list = form.querySelector(".allow-list");
const rowTpl = document.getElementById("allow-row");
const here = new URL(".", import.meta.url);
const law = spec.law;

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
// a citation that keeps its order inside Hebrew (tools/calculator.py cite_text)
// and, with `href`, a link to the clause on the takanon's page
const cite = (c, href) => {
  const text = c.split(" · ").map((x) => "⁦" + x.replace(/([א-ת])/g, "$1‎") + "⁩").join(" · ");
  return href ? el("a", { class: "cite", href, text }) : el("span", { class: "cite", text });
};
// an instrument by its title, linked to its page where the site has one
const instrument = (module, title) => {
  const href = spec.pages[module];
  return href ? el("a", { href, text: title }) : el("span", { text: title });
};

// ------------------------------------------------------------- loading L4

// L4 runs in a worker: loading the law takes the evaluator half a minute or
// more the first time, and the page stays usable meanwhile
const worker = new Worker(new URL("calc-worker.mjs", import.meta.url), { type: "module" });
const pending = new Map();
let seq = 0;
worker.onmessage = (e) => {
  const p = pending.get(e.data.id);
  pending.delete(e.data.id);
  if (e.data.error) p.reject(new Error(e.data.error)); else p.resolve(e.data.answer);
};
worker.onerror = (e) => {
  for (const p of pending.values()) p.reject(new Error(e.message || "worker"));
  pending.clear();
};
const ask = (source) => new Promise((resolve, reject) => {
  const id = ++seq;
  pending.set(id, { resolve, reject });
  worker.postMessage({ id, source, modules: new URL(spec.modules, here).href });
});

// asking a program that only imports the law loads it: the first click is
// then as fast as the next
const started = Date.now();
const loading = setInterval(() => {
  status.textContent = `טוען את הדין… ${Math.round((Date.now() - started) / 1000)} שניות `
    + "(בפעם הראשונה כחצי דקה עד שתי דקות).";
}, 1000);
const ready = ask(`IMPORT \`${law.module}\`\n`).then((a) => {
  if (!a.success) throw new Error((a.diagnostics || []).map((d) => d.message).join("\n"));
});
ready.then(() => { clearInterval(loading); status.textContent = "הדין נטען."; go.disabled = false; },
  (e) => { clearInterval(loading); status.textContent = "טעינת L4 נכשלה: " + e.message; status.classList.add("bad"); });

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

const setInput = (input, v) => {
  if (input.type === "checkbox") input.checked = !!v; else input.value = v;
};
form.querySelector(".example").addEventListener("click", () => {
  for (const f of spec.fields) setInput(form.querySelector(`[data-field="${CSS.escape(f.name)}"]`), spec.example.fields[f.name]);
  for (const f of law.fields) setInput(form.querySelector(`[data-case="${CSS.escape(f.name)}"]`), spec.example.case[f.name]);
  list.replaceChildren();
  for (const a of spec.example.allowances) addRow(a.kind, a.percent);
});

let lastMonth = "";

function readForm() {
  const get = (input) => (input.type === "checkbox" ? input.checked : input.value.trim());
  const fields = {}, kase = {};
  for (const f of spec.fields) fields[f.name] = get(form.querySelector(`[data-field="${CSS.escape(f.name)}"]`));
  for (const f of law.fields) kase[f.name] = get(form.querySelector(`[data-case="${CSS.escape(f.name)}"]`));
  const allowances = [...list.children].map((li) => ({
    kind: li.querySelector("select").value, percent: li.querySelector("input").value.trim(),
  }));
  return { fields, case: kase, allowances };
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

// Why the law gives what it gives for a pay item: the instrument that
// governs and the rule, and what every instrument that speaks says.
function why(it, unit) {
  if (!it.module) return el("p", { class: "why-none", text: "אף מסמך אינו מדבר על הפריט במקרה הזה." });
  const says = el("ul", { class: "says" }, ...it.modules.map((m, i) =>
    el("li", { class: m === it.module ? "gov" : "" }, instrument(m, it.titles[i]), " — ",
      ltr(unit(it.says[i])), m === it.module ? el("span", { class: "badge", text: "גובר" }) : null)));
  return el("div", { class: "why-body" },
    el("p", {}, "גובר: ", instrument(it.module, it.title), ". הכלל: ", el("span", { class: "rule", text: it.rule }), "."),
    el("p", { class: "hint", text: it.modules.length > 1 ? "כל מסמך שמדבר על הפריט, ומה הוא נותן:" : "המסמך היחיד שמדבר על הפריט:" }),
    says,
    it.contradicted ? el("p", { class: "contra" }, "המסמכים נותנים תשובות שונות; סדר העדיפות מכריע ביניהם. ",
      el("a", { href: spec.contradictions, text: "מקורות סותרים" })) : null);
}

function show(r, prog) {
  if (!r.ok) {
    return showErrors("L4 דחה את הערכים שהוזנו",
      [el("p", { text: "הבודק של L4 מצא שגיאה. ההודעה, כפי ש־L4 מדפיס אותה:" }),
       ...r.errors.map((e) => el("pre", { dir: "ltr", text: e.message }))]);
  }
  if (r.failed.length) {
    return showErrors("L4 לא השלים את החישוב",
      [el("p", { text: "ההערכה נכשלה. ההודעה, כפי ש־L4 מדפיס אותה:" }),
       ...r.failed.map((f) => el("pre", { dir: "ltr", text: f.message }))]);
  }
  const shekels = (v) => "₪ " + money(v);
  const tbody = el("tbody");
  // a component the root does not answer yet is §1.1's figure; where a
  // later circular re-rates it from the chosen month, it is not the month's
  // either: say so, and name the circulars (MMS-514)
  const month = lastMonth || "";
  const stale = r.components.filter((c) => !c.item && spec.superseded[c.name] && month >= spec.superseded[c.name].from);
  for (const c of r.components) {
    const it = c.item ? r.items[c.item] : null;
    const sup = stale.includes(c) ? spec.superseded[c.name] : null;
    const whence = it
      ? el("span", { class: "badge law", text: "לפי הדין" })
      : el("span", { class: "badge only", text: "לפי סעיף 1.1 בלבד" });
    const notes = [];
    if (it && c.figure !== c.value) notes.push(el("div", { class: "supnote" }, "סעיף 1.1 לבדו נותן ", ltr(shekels(c.figure)), "."));
    if (sup) {
      notes.push(el("div", { class: "supnote" }, "מחודש זה הוחלף בחוזר ",
        ...sup.by.flatMap((b, i) => [i ? " ואחריו " : "", el("a", { href: b.href, text: b.label })]),
        " — הסכום כאן הוא של סעיף 1.1 כפי שנכתב."));
    }
    tbody.append(el("tr", { class: "c" + (sup ? " superseded" : "") },
      el("td", {}, el("span", { class: "cl", text: c.label }), " ", cite(c.cite, c.href), ...notes),
      el("td", {}, whence),
      el("td", { class: "num" }, ltr(money(c.value)))));
    if (it) {
      tbody.append(el("tr", { class: "why" }, el("td", { colspan: "3" },
        el("details", {}, el("summary", { text: "למה? המסמכים שמדברים על הרכיב" }), why(it, shekels)))));
    }
    if (c.name === "percentage allowances") {
      for (const a of r.allowances) {
        tbody.append(el("tr", { class: "sub" },
          el("td", {}, el("span", { class: "cl", text: a.label }), " ", ltr(a.rate, "rate"), " ", cite(a.cite, a.href)),
          el("td", {}, el("span", { class: "badge only", text: "לפי סעיף 1.1 בלבד" })),
          el("td", { class: "num" }, ltr(money(a.value)))));
      }
    }
  }
  const table = el("table", { class: "comp" },
    el("thead", {}, el("tr", {}, ...["רכיב", "מקור התשובה", "₪"].map((t) => el("th", { text: t })))),
    tbody);
  // the root's other items: what the law answers for the case beyond §1.1's
  // components (not added to the month: which §1.1ו allowance each is, is a
  // reading still to make)
  const others = law.items.filter((i) => !i.component);
  const otherRows = others.map((i) => {
    const it = r.items[i.name];
    return el("li", {},
      el("div", { class: "item-head" }, el("span", { class: "cl", text: i.label }), " ",
        it.answer == null ? el("span", { class: "hint", text: "אין מסמך שמדבר על כך במקרה הזה" }) : ltr(it.answer, "num"),
        " ", el("code", { class: "l4n", dir: "ltr", text: i.name })),
      it.answer == null ? null : el("details", {}, el("summary", { text: "למה?" }), why(it, (v) => v)));
  });
  const tree = el("div", { class: "tree hide-lookups" }, traceNode(r.total.trace, true));
  const lookups = el("input", { type: "checkbox" });
  lookups.addEventListener("change", () => tree.classList.toggle("hide-lookups", !lookups.checked));
  out.replaceChildren(
    ...(stale.length ? [el("div", { class: "calc-warn", role: "note" },
      "החודש שנבחר מאוחר מהחוזרים שהחליפו את " + stale.map((c) => c.label).join(" ואת ")
      + ", ושורש הדין עוד אינו עונה עליה. הסכום שלה להלן הוא של סעיף 1.1 לבדו, ולכן גם הסכום הכולל אינו השכר של החודש הזה.")] : []),
    el("div", { class: "total" },
      el("span", { text: "מה שהדין נותן לחודש" }),
      el("strong", { dir: "ltr", text: shekels(r.total.value) }),
      el("code", { class: "l4n", dir: "ltr", text: law.rule })),
    el("div", { class: "scroll-x" }, table),
    others.length ? el("section", { class: "others" },
      el("h2", { text: "מה עוד הדין עונה למקרה הזה" }),
      el("p", { class: "hint", text: "פריטים ששורש הדין שואל עליהם ואינם נכללים בסכום שלמעלה: עוד לא נקבע לאיזו "
        + "תוספת אחוזית של סעיף 1.1ו כל אחד מהם שייך. שיעור — כחלק מהשכר המשולב (0.02 הם 2%)." }),
      el("ul", { class: "items" }, ...otherRows)) : null,
    el("details", { class: "trace" },
      el("summary", {}, el("h2", { text: "עקבות החישוב" })),
      el("p", { class: "hint", text: "כפי ש־L4 מחשב: כל שורה היא ביטוי בקוד והערך שהגיע אליו. "
        + "לחיצה על שורה פותחת את השלבים שלה ואת תתי־הביטויים שחושבו בדרך. "
        + "שורה שממשיכה ב־= היא אותו ביטוי אחרי צעד חישוב." }),
      el("label", { class: "hint" }, lookups, " הצג גם את שלבי איתור הכללים (⟶ <function>)"),
      tree,
      el("details", { class: "raw" }, el("summary", { text: "העקבות כטקסט, כפי ש־l4 מדפיס אותן" }),
        el("pre", { dir: "ltr", text: r.total.traceText || "" }))),
    el("details", { class: "raw" }, el("summary", { text: "הקוד שהמחשבון כתב והריץ" }),
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
  lastMonth = readForm().fields.month || "";
  go.disabled = true;
  status.textContent = "מחשב…";
  try {
    await ready;
    show(results(spec, prog, await ask(prog.text)), prog);
    status.textContent = "";
  } catch (e) {
    status.textContent = "ההרצה נכשלה: " + e.message;
    status.classList.add("bad");
  } finally {
    go.disabled = false;
  }
});
