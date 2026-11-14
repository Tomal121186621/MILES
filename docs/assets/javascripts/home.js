/* Home page: road animation, counters, stage explorer, validation bars. Re-runs on instant navigation. */
(function () {
  var stop = [];

  function roads(canvas) {
    var ctx = canvas.getContext("2d"), data, lines = [], cars = [], raf, scale = 1, ox = 0, oy = 0;
    var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    function fit() {
      var r = canvas.getBoundingClientRect(), d = window.devicePixelRatio || 1;
      canvas.width = r.width * d; canvas.height = r.height * d; ctx.setTransform(d, 0, 0, d, 0, 0);
      if (!data) return;
      // fill the hero; keep the network on the right on wide screens
      scale = Math.max(r.width * (r.width > 900 ? 0.62 : 1) / data.w, r.height / data.h) * 1.05;
      ox = r.width - data.w * scale + (r.width > 900 ? 0 : (data.w * scale - r.width) / 2);
      oy = (r.height - data.h * scale) / 2;
      lines.forEach(function (l) {
        l.p = []; l.len = 0;
        for (var i = 0; i < l.raw.length; i += 2) l.p.push([ox + l.raw[i] * scale, oy + l.raw[i + 1] * scale]);
        l.cum = [0];
        for (var j = 1; j < l.p.length; j++) { l.len += Math.hypot(l.p[j][0] - l.p[j - 1][0], l.p[j][1] - l.p[j - 1][1]); l.cum.push(l.len); }
      });
    }
    function at(l, s) {
      var i = 1; while (i < l.cum.length - 1 && l.cum[i] < s) i++;
      var a = l.p[i - 1], b = l.p[i], t = (s - l.cum[i - 1]) / ((l.cum[i] - l.cum[i - 1]) || 1);
      return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
    }
    function draw() {
      var r = canvas.getBoundingClientRect();
      ctx.clearRect(0, 0, r.width, r.height);
      ctx.lineCap = "round"; ctx.lineJoin = "round";
      lines.forEach(function (l) {
        ctx.strokeStyle = l.c === 2 ? "rgba(242,140,40,.32)" : "rgba(150,170,210,.16)";
        ctx.lineWidth = l.c === 2 ? 1.4 : .8;
        ctx.beginPath(); l.p.forEach(function (q, i) { i ? ctx.lineTo(q[0], q[1]) : ctx.moveTo(q[0], q[1]); }); ctx.stroke();
      });
      cars.forEach(function (c) {
        c.s += c.v * (c.l.c === 2 ? 1.5 : 1); if (c.s > c.l.len) { c.s = 0; c.l = pick(); }
        var q = at(c.l, c.dir ? c.l.len - c.s : c.s);
        ctx.fillStyle = c.l.c === 2 ? "rgba(255,170,80,.95)" : "rgba(200,215,240,.7)";
        ctx.beginPath(); ctx.arc(q[0], q[1], c.l.c === 2 ? 1.6 : 1.1, 0, 6.283); ctx.fill();
      });
      if (!reduce) raf = requestAnimationFrame(draw);
    }
    function pick() {
      var tot = 0, r; lines.forEach(function (l) { tot += l.len * (l.c === 2 ? 3 : 1); });
      r = Math.random() * tot;
      for (var i = 0; i < lines.length; i++) { r -= lines[i].len * (lines[i].c === 2 ? 3 : 1); if (r <= 0) return lines[i]; }
      return lines[0];
    }
    fetch(canvas.dataset.src).then(function (x) { return x.json(); }).then(function (j) {
      data = j; lines = j.l.map(function (a) { return { c: a[0], raw: a.slice(1) }; });
      fit();
      var n = Math.min(900, Math.round(canvas.getBoundingClientRect().width * .6));
      for (var i = 0; i < n; i++) { var l = pick(); cars.push({ l: l, s: Math.random() * l.len, v: .25 + Math.random() * .55, dir: Math.random() < .5 }); }
      draw();
    });
    var onR = function () { fit(); if (reduce) draw(); };
    window.addEventListener("resize", onR);
    stop.push(function () { cancelAnimationFrame(raf); window.removeEventListener("resize", onR); });
  }

  function counters(root) {
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) {
        if (!e.isIntersecting) return; io.unobserve(e.target);
        var el = e.target, to = +el.dataset.count, dec = +(el.dataset.dec || 0), suf = el.dataset.suffix || "", t0 = null;
        function step(t) {
          t0 = t0 || t; var k = Math.min(1, (t - t0) / 1200), v = to * (1 - Math.pow(1 - k, 3));
          el.textContent = v.toLocaleString("en-US", { minimumFractionDigits: dec, maximumFractionDigits: dec }) + suf;
          if (k < 1) requestAnimationFrame(step);
        }
        requestAnimationFrame(step);
      });
    }, { threshold: .4 });
    root.querySelectorAll("[data-count]").forEach(function (el) { io.observe(el); });
    var rv = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add("is-in"); rv.unobserve(e.target); } });
    }, { threshold: .15 });
    root.querySelectorAll(".mh-reveal").forEach(function (el) { rv.observe(el); });
  }

  function bar(el, ok, close, out, label) {
    var n = ok + close + out;
    el.innerHTML = (label ? "<div class='mh-bars__lab'><span>" + label + "</span><span>" + ok + " of " + n + " within</span></div>" : "") +
      "<div class='mh-bars__track'>" +
      [["ok", ok, "within the limit"], ["close", close, "within twice the limit"], ["out", out, "outside"]].map(function (s) {
        return s[1] ? "<span class='" + s[0] + "' style='width:" + (100 * s[1] / n) + "%' title='" + s[1] + " of " + n + " " + s[2] + "'>" +
          (s[1] / n > .07 ? s[1] : "") + "</span>" : "";
      }).join("") + "</div>";
  }

  function pipeline(root) {
    var tabs = root.querySelectorAll(".mh-pipe button"), panels = root.querySelectorAll(".mh-panel"), fill = root.querySelector(".mh-pipe__bar span"), i = 0, timer;
    function show(k) {
      i = k;
      tabs.forEach(function (t, j) { t.classList.toggle("is-on", j === k); t.classList.toggle("is-done", j < k); t.setAttribute("aria-selected", j === k); });
      panels.forEach(function (p, j) { p.classList.toggle("is-on", j === k); });
      if (fill) fill.style.width = (100 * k / (tabs.length - 1)) + "%";
    }
    tabs.forEach(function (t, j) { t.addEventListener("click", function () { clearInterval(timer); show(j); }); });
    root.querySelectorAll(".mh-score").forEach(function (a) {
      var d = document.createElement("div"); a.appendChild(d);
      bar(d, +a.dataset.ok, +a.dataset.close, +a.dataset.out);
      var p = document.createElement("p"); p.innerHTML = "<b>" + a.dataset.ok + "</b> of " + (+a.dataset.ok + +a.dataset.close + +a.dataset.out) + " comparisons within the acceptance limit"; a.appendChild(p);
    });
    var io = new IntersectionObserver(function (es) {
      if (es[0].isIntersecting && !timer) timer = setInterval(function () { show((i + 1) % tabs.length); }, 7000);
    }, { threshold: .5 });
    var pipe = root.querySelector(".mh-pipe"); if (pipe) io.observe(pipe);
    stop.push(function () { clearInterval(timer); });
  }

  function init() {
    stop.forEach(function (f) { f(); }); stop = [];
    document.querySelectorAll(".miles-bars > div[data-name]").forEach(function (d) { bar(d, +d.dataset.ok, +d.dataset.close, +d.dataset.out, d.dataset.name); });
    var root = document.querySelector(".mh");
    if (!root) return;
    var c = document.getElementById("mh-roads"); if (c) roads(c);
    counters(root); pipeline(root);
    root.querySelectorAll("#mh-bars > div[data-name]").forEach(function (d) { bar(d, +d.dataset.ok, +d.dataset.close, +d.dataset.out, d.dataset.name); });
    var cp = root.querySelector(".mh-copy");
    if (cp) cp.addEventListener("click", function () {
      var txt = root.querySelector(".mh-term code").innerText.split("\n").filter(function (l) { return l.indexOf("$ ") === 0; }).map(function (l) { return l.slice(2); }).join("\n");
      navigator.clipboard && navigator.clipboard.writeText(txt); cp.classList.add("is-done"); setTimeout(function () { cp.classList.remove("is-done"); }, 1500);
    });
  }

  if (window.document$) document$.subscribe(init); else document.addEventListener("DOMContentLoaded", init);
})();
