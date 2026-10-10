/* GEO 文档页共享交互：阅读进度、目录滚动跟随、代码复制、滚动浮现 */
(function () {
  "use strict";

  /* 1. 阅读进度条 */
  var bar = document.querySelector(".read-progress");
  if (bar) {
    var onScroll = function () {
      var h = document.documentElement;
      var max = h.scrollHeight - h.clientHeight;
      bar.style.width = (max > 0 ? (h.scrollTop / max) * 100 : 0) + "%";
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  /* 2. 目录滚动跟随（scroll spy） */
  var links = Array.prototype.slice.call(document.querySelectorAll(".doc-toc a[href^='#']"));
  if (links.length && "IntersectionObserver" in window) {
    var byId = {};
    links.forEach(function (a) {
      var id = decodeURIComponent(a.getAttribute("href").slice(1));
      var el = document.getElementById(id);
      if (el) { byId[id] = a; }
    });
    var setActive = function (id) {
      links.forEach(function (a) { a.classList.remove("on"); });
      var link = byId[id];
      if (link) { link.classList.add("on"); }
    };
    var visible = [];
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        var idx = visible.indexOf(e.target.id);
        if (e.isIntersecting) {
          if (idx === -1) { visible.push(e.target.id); }
        } else if (idx !== -1) {
          visible.splice(idx, 1);
        }
      });
      if (visible.length) {
        /* 取文档顺序中最靠前的可见章节 */
        var ordered = Object.keys(byId).filter(function (id) { return visible.indexOf(id) !== -1; });
        setActive(ordered[0]);
      }
    }, { rootMargin: "-70px 0px -62% 0px", threshold: 0 });
    Object.keys(byId).forEach(function (id) { io.observe(document.getElementById(id)); });
    if (links.length) { links[0].classList.add("on"); }
  }

  /* 3. 代码块复制 */
  document.querySelectorAll(".code-copy").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var panel = btn.closest(".code-panel");
      var code = panel ? panel.querySelector("pre") : null;
      if (!code) { return; }
      var text = code.innerText;
      var done = function () {
        var orig = btn.dataset.label || btn.textContent;
        btn.dataset.label = orig;
        btn.textContent = btn.dataset.copied || "✓ copied";
        btn.classList.add("done");
        setTimeout(function () {
          btn.textContent = orig;
          btn.classList.remove("done");
        }, 1800);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done);
      } else {
        var ta = document.createElement("textarea");
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
        done();
      }
    });
  });

  /* 4. 滚动浮现 */
  if ("IntersectionObserver" in window) {
    var rio = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add("in"); rio.unobserve(e.target); }
      });
    }, { threshold: 0.08 });
    document.querySelectorAll(".rv").forEach(function (el) { rio.observe(el); });
  } else {
    document.querySelectorAll(".rv").forEach(function (el) { el.classList.add("in"); });
  }
})();
