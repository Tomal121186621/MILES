/* Home page: stage explorer and copy button. Re-runs on instant navigation. */
(function () {
  var stop = [];

  function pipeline(root) {
    var tabs = root.querySelectorAll(".mh-pipe button"), panels = root.querySelectorAll(".mh-panel"), fill = root.querySelector(".mh-pipe__bar span"), i = 0, timer;
    function show(k) {
      i = k;
      tabs.forEach(function (t, j) { t.classList.toggle("is-on", j === k); t.classList.toggle("is-done", j < k); t.setAttribute("aria-selected", j === k); });
      panels.forEach(function (p, j) { p.classList.toggle("is-on", j === k); });
      if (fill) fill.style.width = (100 * k / (tabs.length - 1)) + "%";
    }
    tabs.forEach(function (t, j) { t.addEventListener("click", function () { clearInterval(timer); show(j); }); });
    stop.push(function () { clearInterval(timer); });
  }

  // video: one frame per simulated minute from 04:00, 30 frames per second; loop from 06:00
  function clock(root) {
    var v = root.querySelector(".mh-video"), out = root.querySelector(".mh-clock b"), raf;
    if (!v || !out) return;
    var START = 4;
    function tick() {
      var m = 240 + Math.floor(v.currentTime * 30), h = Math.floor(m / 60) % 24;
      out.textContent = (h < 10 ? "0" : "") + h + ":" + (m % 60 < 10 ? "0" : "") + (m % 60);
      raf = requestAnimationFrame(tick);
    }
    function start() { if (v.currentTime < START) v.currentTime = START; }
    v.addEventListener("loadedmetadata", start); if (v.readyState >= 1) start();
    v.addEventListener("ended", function () { v.currentTime = START; v.play(); });
    tick();
    stop.push(function () { cancelAnimationFrame(raf); });
  }

  function init() {
    stop.forEach(function (f) { f(); }); stop = [];
    var root = document.querySelector(".mh");
    if (!root) return;
    pipeline(root); clock(root);
    var cp = root.querySelector(".mh-copy");
    if (cp) cp.addEventListener("click", function () {
      var txt = root.querySelector(".mh-term code").innerText.split("\n").filter(function (l) { return l.indexOf("$ ") === 0; }).map(function (l) { return l.slice(2); }).join("\n");
      navigator.clipboard && navigator.clipboard.writeText(txt); cp.classList.add("is-done"); setTimeout(function () { cp.classList.remove("is-done"); }, 1500);
    });
  }

  if (window.document$) document$.subscribe(init); else document.addEventListener("DOMContentLoaded", init);
})();
