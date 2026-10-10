// The code / rendered switch on a section page. Without script every row
// shows its code, which is the default the markup already carries.
(function () {
  var KEY = "l4-view";
  function show(view) {
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
            where.textContent = (n ? "§" + n.textContent + "  " : "") + (h ? h.textContent : "");
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
    if (location.hash) {
      var t = document.getElementById(decodeURIComponent(location.hash.slice(1)));
      var row = t && t.closest(".row");
      if (row && row !== t) row.classList.add("hit");
    }
  });

  // Long pages: an "On this page" outline of the headed rows, under the
  // current entry of the sidebar, and a back-to-top button. On the takanon's
  // one page the outline is the section in view; on a circular, the whole
  // document. The outline marks the heading the reader is at.
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
    ul.setAttribute("aria-label", "On this page");
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
    up.setAttribute("aria-label", "Back to the top");
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
