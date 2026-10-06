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
    document.querySelectorAll(".toc-ch li a").forEach(function (a) {
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
          var toc = document.querySelector(".toc");
          if (toc && toc.scrollHeight > toc.clientHeight) {
            var r = a.getBoundingClientRect(), t = toc.getBoundingClientRect();
            if (r.top < t.top || r.bottom > t.bottom) a.scrollIntoView({ block: "nearest" });
          }
        });
      }, { rootMargin: "-120px 0px -70% 0px" });
      document.querySelectorAll(".tsec").forEach(function (s) { io.observe(s); });
    }
    if (window.matchMedia("(max-width: 1100px)").matches) {
      var d = document.querySelector(".toc details");
      if (d) d.open = false;
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
