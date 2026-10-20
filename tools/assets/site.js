// The code / rendered switch on a section page. Without script every row
// shows its code, which is the default the markup already carries.
(function () {
  var KEY = "l4-view";
  // The prose views are not in the page: each section's are fetched from its
  // .prose.json (build_site.prose_json) the first time the reader asks.
  var prose = {};
  function loadProse() {
    document.querySelectorAll(".view.rendered[data-s]:not([data-done])").forEach(function (el) {
      el.setAttribute("data-done", "");
      var sec = el.closest("[data-prose]");
      var url = sec && sec.getAttribute("data-prose");
      if (url && !prose[url]) {
        prose[url] = fetch(url).then(function (r) {
          if (!r.ok) throw new Error(r.status);
          return r.json();
        });
      }
      (url ? prose[url] : Promise.resolve({})).then(function (m) {
        var h = m[el.getAttribute("data-s")];
        if (h) { el.classList.add("l4-doc"); el.innerHTML = h; }
        else {
          el.classList.add("empty");
          el.textContent = "אין לו פרוזה משלו: זהו טיפוס, בדיקה או חלק מכלל שמוצג ליד פסקה אחרת.";
        }
      }, function () {
        el.classList.add("empty");
        el.textContent = "הפרוזה לא נטענה.";
      });
    });
  }
  function show(view) {
    if (view === "rendered") loadProse();
    document.querySelectorAll(".view").forEach(function (el) {
      el.hidden = !el.classList.contains(view);
    });
    document.querySelectorAll(".switch button").forEach(function (b) {
      b.setAttribute("aria-pressed", String(b.dataset.view === view));
    });
    try { localStorage.setItem(KEY, view); } catch (e) {}
  }
  // the sidebar is a drawer below 1100px: the header button opens it, the
  // scrim, the close button, Escape or following a link closes it
  document.addEventListener("DOMContentLoaded", function () {
    var nav = document.getElementById("sidenav");
    var open = document.querySelector(".sn-open");
    var scrim = document.querySelector(".sn-scrim");
    if (!nav || !open) return;
    function set(on) {
      nav.classList.toggle("open", on);
      if (scrim) scrim.hidden = !on;
      open.setAttribute("aria-expanded", String(on));
    }
    open.addEventListener("click", function () { set(true); });
    if (scrim) scrim.addEventListener("click", function () { set(false); });
    var close = nav.querySelector(".sn-close");
    if (close) close.addEventListener("click", function () { set(false); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") set(false); });
    nav.addEventListener("click", function (e) { if (e.target.closest("a")) set(false); });
    // the current document's link is in view when the page opens
    var cur = nav.querySelector('[aria-current="page"]');
    if (cur) cur.scrollIntoView({ block: "center" });
  });
  document.addEventListener("DOMContentLoaded", function () {
    var buttons = document.querySelectorAll(".switch button");
    if (!buttons.length) return;
    buttons.forEach(function (b) {
      b.addEventListener("click", function () { show(b.dataset.view); });
    });
    var saved = null;
    try { saved = localStorage.getItem(KEY); } catch (e) {}
    if (saved === "rendered" || saved === "code-view") show(saved);
    // the contents rail follows the reader: the section in view is marked
    // there and named in the toolbar
    var where = document.querySelector(".tb-where");
    var links = {};
    document.querySelectorAll('.sidenav a[href^="#"]').forEach(function (a) {
      links[decodeURIComponent(a.getAttribute("href").slice(1))] = a;
    });
    if (window.IntersectionObserver && Object.keys(links).length) {
      var current = null;
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) {
          if (!e.isIntersecting) return;
          var a = links[e.target.id];
          if (!a || a === current) return;
          if (current) current.classList.remove("current");
          a.classList.add("current");
          current = a;
          if (where) {
            var n = a.querySelector(".secnum"), h = a.querySelector(".sh");
            // an agreement's preamble and sign-off are named, not numbered: no §
            where.textContent = (n ? (/^\d/.test(n.textContent) ? "§" : "") + n.textContent + "  " : "") + (h ? h.textContent : "");
          }
          // open the chapter that holds it, close the one left behind
          var det = a.closest("details");
          document.querySelectorAll(".sidenav .toc-ch > details[open]").forEach(function (d) {
            if (d !== det) d.open = false;
          });
          if (det) det.open = true;
          var toc = document.querySelector(".sidenav");
          if (toc && toc.scrollHeight > toc.clientHeight) {
            var r = a.getBoundingClientRect(), t = toc.getBoundingClientRect();
            if (r.top < t.top || r.bottom > t.bottom) a.scrollIntoView({ block: "nearest" });
          }
        });
      }, { rootMargin: "-120px 0px -70% 0px" });
      document.querySelectorAll(".tsec").forEach(function (s) { io.observe(s); });
    }

    // an alias (an element cited by eId, shown on its first paragraph)
    // marks the row it lives in when the page opens on it
    settleOnHash();
    if (location.hash) {
      var t = document.getElementById(decodeURIComponent(location.hash.slice(1)));
      var row = t && t.closest(".row");
      if (row && row !== t) row.classList.add("hit");
    }
  });

  // Rows off the screen are not laid out (content-visibility in site.css):
  // each is a box of an estimated height until the reader nears it. Jumping
  // to an anchor lays out the rows around it, which moves it, so the jump is
  // repeated until the target holds still at the place the browser aimed it
  // at — and abandoned the moment the reader scrolls.
  function settle(el) {
    if (!el) return;
    var frames = 0, still = 0, stop = false;
    function cancel() { stop = true; }
    ["wheel", "touchstart", "keydown", "mousedown"].forEach(function (t) {
      window.addEventListener(t, cancel, { once: true, passive: true });
    });
    (function step() {
      if (stop || frames++ > 90) return;
      var want = parseFloat(getComputedStyle(el).scrollMarginTop) || 0;
      var y = window.scrollY;
      if (Math.abs(el.getBoundingClientRect().top - want) > 1) el.scrollIntoView({ block: "start" });
      // held still, or already as far as the page scrolls
      if (window.scrollY === y) { if (++still >= 6) return; } else still = 0;
      requestAnimationFrame(step);
    })();
  }
  function settleOnHash() {
    if (!location.hash) return;
    var el = document.getElementById(decodeURIComponent(location.hash.slice(1)));
    if (el && !el.matches("details.finding")) settle(el);
  }
  window.addEventListener("hashchange", settleOnHash);
  window.addEventListener("load", settleOnHash);

  // Long pages: an "On this page" outline of the headed rows, under the
  // current entry of the sidebar, and a back-to-top button. On a takanon
  // chapter page the outline is the section in view; on a circular, the
  // whole document. The outline marks the heading the reader is at.
  function outlineOf(scope) {
    var rows = scope.querySelectorAll(".row.label");
    var items = [];
    rows.forEach(function (r) {
      var h = r.querySelector(".h");
      if (!h || !r.id || r.id === "preamble" || r.id === "conclusions") return;
      var n = r.querySelector(".num");
      var d = /\bd(\d)\b/.exec(r.className);
      items.push({ id: r.id, num: n ? n.textContent : "", h: h.textContent, depth: d ? +d[1] : 0 });
    });
    return items;
  }
  function renderOutline(items, after) {
    var old = document.querySelector(".sn-outline");
    if (old) old.remove();
    if (!after || items.length < 3) return null;
    var ul = document.createElement("ul");
    ul.className = "sn-outline";
    ul.setAttribute("aria-label", "בעמוד זה");
    var min = Math.min.apply(null, items.map(function (i) { return i.depth; }));
    items.forEach(function (i) {
      if (i.depth > min + 1) return;
      var li = document.createElement("li");
      li.className = "o" + (i.depth - min);
      var a = document.createElement("a");
      a.href = "#" + i.id;
      a.innerHTML = '<span class="secnum" dir="ltr"></span><span class="sh" lang="he" dir="rtl"></span>';
      a.firstChild.textContent = i.num;
      a.lastChild.textContent = i.h;
      a.title = (i.num ? i.num + " " : "") + i.h;
      li.appendChild(a);
      ul.appendChild(li);
    });
    after.insertAdjacentElement("afterend", ul);
    return ul;
  }
  var outlineIO = null;
  function watchOutline(ul) {
    if (outlineIO) { outlineIO.disconnect(); outlineIO = null; }
    if (!ul || !window.IntersectionObserver) return;
    var links = {};
    ul.querySelectorAll("a").forEach(function (a) { links[decodeURIComponent(a.getAttribute("href").slice(1))] = a; });
    var cur = null;
    outlineIO = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        var a = links[e.target.id];
        if (!a || a === cur) return;
        if (cur) cur.classList.remove("here");
        a.classList.add("here");
        cur = a;
      });
    }, { rootMargin: "-120px 0px -70% 0px" });
    Object.keys(links).forEach(function (id) {
      var el = document.getElementById(id);
      if (el) outlineIO.observe(el);
    });
  }
  document.addEventListener("DOMContentLoaded", function () {
    var nav = document.getElementById("sidenav");
    // a circular: the whole page, under its own entry
    var cur = nav && nav.querySelector('a[aria-current="page"]');
    if (cur) watchOutline(renderOutline(outlineOf(document.querySelector("main")), cur));
    // the takanon: the section in view, under its entry, as the scrollspy moves
    if (nav && nav.querySelector('a[href^="#"]')) {
      var shown = null;
      new MutationObserver(function () {
        var a = nav.querySelector('a.current[href^="#"]');
        if (!a || a === shown) return;
        shown = a;
        var sec = document.getElementById(decodeURIComponent(a.getAttribute("href").slice(1)));
        if (sec) watchOutline(renderOutline(outlineOf(sec), a));
      }).observe(nav, { subtree: true, attributes: true, attributeFilter: ["class"] });
    }
    // back to the top
    var up = document.createElement("button");
    up.type = "button";
    up.className = "to-top";
    up.setAttribute("aria-label", "חזרה לראש העמוד");
    up.innerHTML = '<svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M10 15V5M5 10l5-5 5 5" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    up.hidden = true;
    up.addEventListener("click", function () { window.scrollTo({ top: 0, behavior: "smooth" }); });
    document.body.appendChild(up);
    var tick = false;
    window.addEventListener("scroll", function () {
      if (tick) return;
      tick = true;
      requestAnimationFrame(function () { up.hidden = window.scrollY < 900; tick = false; });
    }, { passive: true });
  });
})();

// The findings page: filter by kind, stage, collection and words; fold and
// unfold; a link to a finding opens it (and clears a filter hiding it).
(function () {
  function init() {
    var root = document.querySelector(".findings");
    if (!root) return;
    var cards = [].slice.call(root.querySelectorAll("details.finding"));
    var groups = [].slice.call(root.querySelectorAll(".fgroup"));
    var dims = ["sev", "kind", "stage", "col"];
    var sel = { sev: {}, kind: {}, stage: {}, col: {} };
    var q = "";
    var shown = document.getElementById("fshown");
    var none = document.querySelector(".fnone");
    function any(o) { for (var k in o) if (o[k]) return true; return false; }
    function apply() {
      var n = 0;
      cards.forEach(function (c) {
        var ok = dims.every(function (d) { return !any(sel[d]) || sel[d][c.dataset[d]]; })
          && (!q || c.textContent.toLowerCase().indexOf(q) >= 0);
        c.hidden = !ok;
        if (ok) n++;
      });
      groups.forEach(function (g) {
        var v = g.querySelectorAll("details.finding:not([hidden])").length;
        g.hidden = !v;
        var s = g.querySelector(".gcount");
        if (s) s.textContent = v;
      });
      // the sidebar's index of the groups follows the filter
      var side = {};
      groups.forEach(function (g) {
        var a = g.id && document.querySelector('.sidenav a[href="#' + g.id + '"]');
        if (!a) return;
        var v = g.hidden ? 0 : +((g.querySelector(".gcount") || {}).textContent || 0);
        a.parentNode.hidden = !v;
        var c = a.querySelector(".n");
        if (c) c.textContent = v;
        side[g.dataset.col] = (side[g.dataset.col] || 0) + v;
      });
      document.querySelectorAll(".sidenav .sn-group[data-col]").forEach(function (li) {
        var v = side[li.dataset.col] || 0;
        li.hidden = !v;
        var c = li.querySelector("summary .n");
        if (c) c.textContent = v;
      });
      if (shown) shown.textContent = n;
      if (none) none.hidden = n > 0;
      document.querySelectorAll(".ffilter .chips").forEach(function (box) {
        box.querySelectorAll(".chip").forEach(function (b) {
          b.setAttribute("aria-pressed", sel[box.dataset.dim][b.dataset.v] ? "true" : "false");
        });
      });
    }
    function reset() {
      dims.forEach(function (d) { sel[d] = {}; });
      q = "";
      var box = document.getElementById("fq");
      if (box) box.value = "";
    }
    document.querySelectorAll(".ffilter .chips").forEach(function (box) {
      box.addEventListener("click", function (e) {
        var b = e.target.closest(".chip");
        if (!b) return;
        var d = box.dataset.dim;
        sel[d][b.dataset.v] = !sel[d][b.dataset.v];
        apply();
      });
    });
    // a part of the severity meter filters to its grade (MMS-504)
    document.querySelectorAll(".sevseg").forEach(function (b) {
      b.addEventListener("click", function () {
        reset();
        sel.sev[b.dataset.sev] = true;
        apply();
        var bar = document.querySelector(".ffilter");
        if (bar) bar.scrollIntoView({ block: "start" });
      });
    });
    document.querySelectorAll(".mcell").forEach(function (b) {
      b.addEventListener("click", function () {
        reset();
        sel.kind[b.dataset.kind] = true;
        sel.stage[b.dataset.stage] = true;
        apply();
        var bar = document.querySelector(".ffilter");
        if (bar) bar.scrollIntoView({ block: "start" });
      });
    });
    var t = null;
    var input = document.getElementById("fq");
    if (input) input.addEventListener("input", function () {
      clearTimeout(t);
      t = setTimeout(function () { q = input.value.trim().toLowerCase(); apply(); }, 150);
    });
    function setAll(open) {
      cards.forEach(function (c) { if (!c.hidden) c.open = open; });
    }
    var o = document.getElementById("fopen"), c = document.getElementById("fclose"), r = document.getElementById("freset");
    if (o) o.addEventListener("click", function () { setAll(true); });
    if (c) c.addEventListener("click", function () { setAll(false); });
    if (r) r.addEventListener("click", function () { reset(); apply(); });
    function openHash() {
      var id = decodeURIComponent(location.hash.slice(1));
      var el = id && document.getElementById(id);
      if (!el || !el.matches("details.finding")) return;
      if (el.hidden) { reset(); apply(); }
      el.open = true;
      el.scrollIntoView({ block: "start" });
    }
    window.addEventListener("hashchange", openHash);
    openHash();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
