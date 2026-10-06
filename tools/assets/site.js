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
    // an alias (an element cited by eId, shown on its first paragraph)
    // marks the row it lives in when the page opens on it
    if (location.hash) {
      var t = document.getElementById(decodeURIComponent(location.hash.slice(1)));
      var row = t && t.closest(".row");
      if (row && row !== t) row.classList.add("hit");
    }
  });
})();
