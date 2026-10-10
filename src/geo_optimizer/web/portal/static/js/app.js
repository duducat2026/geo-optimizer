/* GEO 优化平台前端脚本 —— 无外部依赖 */
(function () {
  "use strict";

  /* ---- 处理日志控制台 ----
   * 服务端已按时间倒排返回日志，直接重建控制台内容
   */
  function renderConsoleLogs(consoleBox, logs) {
    if (!consoleBox || !logs) return;
    consoleBox.textContent = "";
    logs.forEach(function (log) {
      var line = document.createElement("div");
      line.className = "line lv-" + (log.level || "info");
      var t = document.createElement("span");
      t.className = "t";
      t.textContent = log.time;
      line.appendChild(t);
      line.appendChild(document.createTextNode(" " + log.message));
      if (log.detail) {
        var d = document.createElement("span");
        d.className = "d";
        d.textContent = " " + log.detail;
        line.appendChild(d);
      }
      consoleBox.appendChild(line);
    });
  }

  /* 点击展示全部历史日志（保留期内） */
  function initLogHistory() {
    var btn = document.getElementById("task-logs-history");
    var consoleBox = document.getElementById("task-console");
    if (!btn || !consoleBox) return;

    btn.addEventListener("click", function () {
      var taskId = consoleBox.getAttribute("data-task-id");
      fetch("/eval/" + encodeURIComponent(taskId) + "/logs", {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      })
        .then(function (resp) { return resp.json(); })
        .then(function (data) {
          renderConsoleLogs(consoleBox, data.logs);
          btn.hidden = true;
          consoleBox.setAttribute("data-expanded", "1");
        })
        .catch(function () { /* 保持现状 */ });
    });
  }

  /* ---- 任务进度轮询 ----
   * eval_detail 页面放置：
   *   <div id="task-poll" data-task-id="..." data-status="running"></div>
   * 终态（completed/failed）时刷新页面，由服务端渲染完整结果。
   */
  function initTaskPolling() {
    var holder = document.getElementById("task-poll");
    if (!holder) return;

    var status = holder.getAttribute("data-status");
    if (status !== "pending" && status !== "running") return;

    var taskId = holder.getAttribute("data-task-id");
    var bar = document.getElementById("task-progress-bar");
    var msg = document.getElementById("task-progress-msg");
    var consoleBox = document.getElementById("task-console");
    var historyBtn = document.getElementById("task-logs-history");

    function tick() {
      fetch("/eval/" + encodeURIComponent(taskId) + "/status", {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      })
        .then(function (resp) {
          if (!resp.ok) throw new Error("status " + resp.status);
          return resp.json();
        })
        .then(function (data) {
          if (bar) bar.style.width = (data.progress || 0) + "%";
          if (msg && (data.message_text || data.message)) {
            msg.textContent = data.message_text || data.message;
          }
          /* 已展开历史时不再用近期日志覆盖 */
          if (consoleBox && !consoleBox.getAttribute("data-expanded")) {
            renderConsoleLogs(consoleBox, data.logs);
            if (historyBtn && data.logs) {
              historyBtn.hidden = !(data.log_total > data.logs.length);
            }
          }
          if (data.status === "completed" || data.status === "failed") {
            window.location.reload();
          } else {
            setTimeout(tick, 5000);
          }
        })
        .catch(function () {
          setTimeout(tick, 5000);
        });
    }

    setTimeout(tick, 5000);
  }

  /* ---- 删除确认 ----
   * 表单加 data-confirm="提示文案" 即启用
   */
  function initConfirmForms() {
    var forms = document.querySelectorAll("form[data-confirm]");
    Array.prototype.forEach.call(forms, function (form) {
      form.addEventListener("submit", function (e) {
        var text = form.getAttribute("data-confirm") || "Confirm?";
        if (!window.confirm(text)) e.preventDefault();
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initTaskPolling();
    initLogHistory();
    initConfirmForms();
  });
})();
