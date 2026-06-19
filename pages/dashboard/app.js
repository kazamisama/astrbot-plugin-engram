/* Engram Dashboard WebUI
 * Talks to the plugin backend through the AstrBot plugin-page bridge
 * (window.AstrBotPluginPage). The bridge prefixes "/<plugin_name>/" so
 * we only pass "page/xxx". Backend routes live under
 * /astrbot_plugin_engram/page/* (see page_api.py).
 */
(function () {
  "use strict";

  var bridge = window.AstrBotPluginPage;

  function toast(msg) {
    var el = document.getElementById("toast");
    el.textContent = msg;
    el.classList.add("show");
    setTimeout(function () { el.classList.remove("show"); }, 2200);
  }

  function endpoint(path) {
    var p = String(path).replace(/^\/+/, "");
    return p.indexOf("page/") === 0 ? p : "page/" + p;
  }

  async function apiGet(path, params) {
    if (!bridge) throw new Error("AstrBot 插件桥不可用，请在 AstrBot 后台打开本页面。");
    return bridge.apiGet(endpoint(path), params || {});
  }
  async function apiPost(path, body) {
    if (!bridge) throw new Error("AstrBot 插件桥不可用，请在 AstrBot 后台打开本页面。");
    return bridge.apiPost(endpoint(path), body || {});
  }

  function unwrap(resp) {
    // backend returns {status:"ok"|"error", data?, message?}
    if (resp && resp.status === "error") {
      throw new Error(resp.message || "后端返回错误");
    }
    if (resp && "data" in resp) return resp.data;
    return resp;
  }

  // ---------- tabs ----------
  document.querySelectorAll(".tab").forEach(function (tab) {
    tab.addEventListener("click", function () {
      document.querySelectorAll(".tab").forEach(function (t) { t.classList.remove("active"); });
      document.querySelectorAll(".panel").forEach(function (p) { p.classList.remove("active"); });
      tab.classList.add("active");
      var name = tab.getAttribute("data-tab");
      document.querySelector('.panel[data-panel="' + name + '"]').classList.add("active");
    });
  });

  // ---------- health ----------
  async function loadHealth() {
    var el = document.getElementById("health");
    try {
      var d = unwrap(await apiGet("page/health"));
      el.textContent = "v" + (d.version || "?") + " · " + (d.language || "") +
        (d.service_ready ? " · 已就绪" : " · 初始化中");
      el.className = "status ok";
    } catch (e) {
      el.textContent = "未连接：" + e.message;
      el.className = "status err";
    }
  }

  // ---------- overview ----------
  var STAT_LABELS = {
    engrams: "记忆条目", fts: "全文索引", entities: "语义实体",
    atoms: "记忆原子", prospective_pending: "待触发", prospective_fired: "已触发"
  };
  async function loadStats() {
    var box = document.getElementById("stat-cards");
    box.innerHTML = '<div class="card"><div class="lbl">加载中…</div></div>';
    try {
      var d = unwrap(await apiGet("page/stats"));
      box.innerHTML = "";
      Object.keys(d).forEach(function (k) {
        var v = d[k];
        if (typeof v !== "number") return;
        var card = document.createElement("div");
        card.className = "card";
        card.innerHTML = '<div class="num">' + v + '</div><div class="lbl">' +
          (STAT_LABELS[k] || k) + "</div>";
        box.appendChild(card);
      });
      if (!box.children.length) box.innerHTML = '<div class="card"><div class="lbl">暂无数据</div></div>';
    } catch (e) {
      box.innerHTML = '<div class="card"><div class="lbl" style="color:var(--danger)">' + e.message + "</div></div>";
    }
  }

  // ---------- memories ----------
  async function loadMemories() {
    var actor = document.getElementById("mem-actor").value.trim();
    var k = document.getElementById("mem-k").value || 50;
    var tbody = document.getElementById("mem-rows");
    tbody.innerHTML = '<tr><td colspan="3">加载中…</td></tr>';
    try {
      var d = unwrap(await apiGet("page/memories", { actor_id: actor, k: k, offset: 0 }));
      var items = (d && d.items) || [];
      if (!items.length) { tbody.innerHTML = '<tr><td colspan="3">暂无记忆</td></tr>'; return; }
      tbody.innerHTML = "";
      items.forEach(function (it) {
        var tr = document.createElement("tr");
        tr.innerHTML =
          '<td class="id-cell">' + (it.id == null ? "" : it.id) + "</td>" +
          "<td>" + escapeHtml(it.summary || "") + "</td>" +
          "<td>" + escapeHtml(it.actor_id || "") + "</td>";
        tr.querySelector(".id-cell").addEventListener("click", function () { showDetail(it.id); });
        tbody.appendChild(tr);
      });
    } catch (e) {
      tbody.innerHTML = '<tr><td colspan="3" style="color:var(--danger)">' + e.message + "</td></tr>";
    }
  }

  async function showDetail(eid) {
    var el = document.getElementById("mem-detail");
    el.innerHTML = "加载详情…";
    try {
      var d = unwrap(await apiGet("page/memories/detail", { eid: eid }));
      el.innerHTML = '<pre class="out">' + escapeHtml(JSON.stringify(d, null, 2)) + "</pre>";
    } catch (e) {
      el.innerHTML = '<span style="color:var(--danger)">' + e.message + "</span>";
    }
  }

  // ---------- recall ----------
  async function runRecall() {
    var out = document.getElementById("rc-out");
    out.textContent = "召回中…";
    try {
      var d = unwrap(await apiPost("page/recall/test", {
        query: document.getElementById("rc-query").value,
        mode: document.getElementById("rc-mode").value,
        k: Number(document.getElementById("rc-k").value) || 5
      }));
      out.textContent = JSON.stringify(d, null, 2);
    } catch (e) {
      out.textContent = "错误：" + e.message;
    }
  }

  // ---------- backups ----------
  async function loadBackups() {
    var tbody = document.getElementById("bk-rows");
    tbody.innerHTML = '<tr><td colspan="4">加载中…</td></tr>';
    try {
      var d = unwrap(await apiGet("page/backups"));
      var items = (d && d.items) || (Array.isArray(d) ? d : []);
      if (!items.length) { tbody.innerHTML = '<tr><td colspan="4">暂无备份</td></tr>'; return; }
      tbody.innerHTML = "";
      items.forEach(function (b) {
        var bid = b.id || b.backup_id || b.name || "";
        var tr = document.createElement("tr");
        tr.innerHTML =
          '<td class="id-cell">' + escapeHtml(String(bid)) + "</td>" +
          "<td>" + escapeHtml(String(b.created || b.time || b.mtime || "")) + "</td>" +
          "<td>" + escapeHtml(String(b.size || b.bytes || "")) + "</td>" +
          '<td><button class="btn btn-danger" data-bid="' + escapeHtml(String(bid)) + '">恢复</button></td>';
        tr.querySelector("button").addEventListener("click", function () { restoreBackup(bid); });
        tbody.appendChild(tr);
      });
    } catch (e) {
      tbody.innerHTML = '<tr><td colspan="4" style="color:var(--danger)">' + e.message + "</td></tr>";
    }
  }

  async function restoreBackup(bid) {
    if (!confirm("确定用备份 " + bid + " 覆盖当前数据库吗？此操作不可逆。")) return;
    try {
      unwrap(await apiPost("page/backups/restore", { backup_id: bid }));
      toast("恢复请求已提交：" + bid);
    } catch (e) {
      toast("恢复失败：" + e.message);
    }
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  // ---------- wire ----------
  document.getElementById("btn-refresh-stats").addEventListener("click", loadStats);
  document.getElementById("btn-load-mem").addEventListener("click", loadMemories);
  document.getElementById("btn-recall").addEventListener("click", runRecall);
  document.getElementById("btn-load-backups").addEventListener("click", loadBackups);

  async function init() {
    if (bridge && bridge.ready) {
      try { await bridge.ready(); } catch (e) { /* non-fatal */ }
    }
    await loadHealth();
    await loadStats();
  }
  init();
})();