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
})();
