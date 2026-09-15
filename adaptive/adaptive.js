// adaptive/adaptive.js
// Компоненты интерфейса Monolog.
// Ждёт события monolog-ready от core.js.

"use strict";

function bootstrapAdaptive() {
  const C = window.MonologCore;
  if (!C) {
    console.error("MonologCore не загружен — adaptive.js не может стартовать");
    return;
  }

  const {
    state, API_BASE, uid, escHtml, pluralize, toast, renderMarkdown, softenText,
    broadcast, dbGetAll, dbPut, dbDel, dbGetMeta, dbSetMeta,
    currentChat, currentLot, addRow, renderCurrentChat, send,
    createChatObj, createLotObj, persistChat, persistLot,
    updateCharCounter, renderAttachPreview, handleFiles,
    openSheet, closeAllSheets,
    STORE_LOTS, STORE_CHATS, STORE_RELEASES, STORE_ANALYTICS,
    STORE_NOTIFICATIONS, STORE_PUBLIC, STORE_META,
    LS_NOTIF_SEEN,
    MODE_LABELS,
  } = C;

  // --- Сфера ---
  function getUserStatus() {
    const c = currentChat();
    const m = (c && c.lastMetrics) || {};
    const si = typeof m.stability_index === "number" ? m.stability_index : null;
    const pulse = m.cognitive_pulse || null;
    if (pulse === "fast") return { key: "active", label: "активно думает" };
    if (pulse === "slow") return { key: "calm", label: "спокойно" };
    if (si != null && si < 0.5) return { key: "doubt", label: "сомневается" };
    return { key: "ready", label: "готов" };
  }

  const ORB_TINTS = [
    "rgba(255, 235, 242, 0.5)",
    "rgba(235, 240, 255, 0.5)",
    "rgba(235, 255, 240, 0.5)",
    "rgba(255, 245, 230, 0.5)",
    "rgba(245, 235, 255, 0.5)",
    "rgba(230, 250, 255, 0.5)"
  ];

  function renderOrb() {
    const orb = document.getElementById("orbBtn");
    if (!orb) return;
    const status = getUserStatus();
    orb.className = "orb " + state.mode + " status-" + status.key;
    const tint = ORB_TINTS[Math.floor(Math.random() * ORB_TINTS.length)];
    orb.style.setProperty("--orb-tint", tint);
  }

  function canSwitchMode() { return !!state.manageKey; }
  function switchMode() {
    if (!canSwitchMode()) { toast("Переключение режима доступно только с ключом Управления"); return; }
    const modes = ["analyst", "strategist", "neutral"];
    const idx = modes.indexOf(state.mode);
    state.mode = modes[(idx + 1) % modes.length];
    renderOrb();
    try { localStorage.setItem("monolog_mode", state.mode); } catch (e) {}
    toast(MODE_LABELS[state.mode]);
  }

  function renderOrbSheet() {
    const box = document.getElementById("orbContent");
    const sub = document.getElementById("orbSub");
    const title = document.getElementById("orbTitle");
    if (!box) return;
    const status = getUserStatus();
    if (canSwitchMode()) { title.textContent = "Состояние"; sub.textContent = "Что нужно сейчас"; }
    else { title.textContent = "Что нужно сейчас"; sub.textContent = "Текущий статус"; }
    let html = "";
    const c = currentChat();
    const m = (c && c.lastMetrics) || {};
    if (m.ai_note) html += '<div class="info-block">' + escHtml(softenText(m.ai_note)) + '</div>';
    html += '<div class="artifact-item" style="cursor:default;">';
    html += '<div class="artifact-item-head"><span class="artifact-item-name">' + (canSwitchMode() ? "Режим" : "Статус") + '</span><span class="artifact-item-stage">' + escHtml(canSwitchMode() ? MODE_LABELS[state.mode] : status.label) + '</span></div>';
    if (canSwitchMode()) html += '<div class="artifact-item-meta"><span>Долгий тап — переключить режим</span></div>';
    html += '</div>';
    if (m.stability_index != null) html += '<div class="artifact-item" style="cursor:default;"><div class="artifact-item-head"><span class="artifact-item-name">Стабильность</span><span class="artifact-item-stage">' + Number(m.stability_index).toFixed(2) + '</span></div></div>';
    if (m.mind_scale) html += '<div class="artifact-item" style="cursor:default;"><div class="artifact-item-head"><span class="artifact-item-name">Глубина</span><span class="artifact-item-stage">' + escHtml(m.mind_scale) + '</span></div></div>';
    const n = typeof state.balance === "number" ? state.balance : 0;
    html += '<div class="artifact-item" style="cursor:default;"><div class="artifact-item-head"><span class="artifact-item-name">Индекс</span><span class="artifact-item-stage">' + (n >= 0 ? "+" : "") + n.toFixed(1) + '</span></div></div>';
    box.innerHTML = html;
    const manage = document.getElementById("orbManageSection");
    if (manage) manage.style.display = state.manageKey ? "block" : "none";
  }

  // --- AI note ---
  function renderAiNote() {
    const note = document.getElementById("aiNote");
    const body = document.getElementById("aiNoteBody");
    if (!note || !body) return;
    const c = currentChat();
    const m = (c && c.lastMetrics) || {};
    const text = m.ai_note || (m.reminder && m.reminder.text) || null;
    if (text) { body.textContent = softenText(text); note.classList.add("show"); }
    else note.classList.remove("show");
  }

  // --- Header ---
  function updateIndexBtn(delta) {
    const n = typeof state.balance === "number" ? state.balance : 0;
    const btn = document.getElementById("indexBtn");
    if (!btn) return;
    const sign = n >= 0 ? "+" : "";
    btn.textContent = sign + n.toFixed(1);
    btn.classList.remove("positive", "negative");
    if (n > 0) btn.classList.add("positive");
    else if (n < 0) btn.classList.add("negative");
    if (typeof delta === "number" && delta !== 0) {
      btn.classList.remove("pulse");
      void btn.offsetWidth;
      btn.classList.add("pulse");
    }
  }

  function updateHeaderDynamic() {
    const c = currentChat();
    const m = (c && c.lastMetrics) || {};
    const rp = m.reset_proposal;
    const header = document.getElementById("headerRight");
    if (!header) return;
    const existing = header.querySelector(".reset-btn");
    if (rp && rp.recommended && !existing) {
      const btn = document.createElement("button");
      btn.className = "icon-btn dynamic reset-btn";
      btn.id = "resetBtn";
      btn.type = "button";
      btn.title = "Сбросить контекст";
      btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/></svg>';
      btn.addEventListener("click", () => confirmReset(rp));
      header.appendChild(btn);
    } else if (!rp && existing) existing.remove();
    updateNotifBadge();
    updateProfileBadge();
  }
  function updateNotifBadge() {
    const btn = document.getElementById("notifBtn");
    if (!btn) return;
    const unseen = state.notifications.filter(n => (n.at || "").localeCompare(state.lastNotifSeenAt) > 0);
    if (unseen.length > 0) btn.classList.add("has-badge");
    else btn.classList.remove("has-badge");
    const hasCrit = unseen.some(n => n.level === "crit");
    btn.classList.toggle("critical", hasCrit);
  }
  function updateProfileBadge() {
    const btn = document.getElementById("profileBtn");
    if (!btn) return;
    const c = currentChat();
    const learning = c && c.learningTemplate;
    if (learning) btn.classList.add("has-badge");
    else btn.classList.remove("has-badge");
  }
  function confirmReset(rp) {
    if (confirm((rp.reason || "Monolog рекомендует сбросить контекст") + "\n\nСбросить?")) {
      const c = currentChat();
      if (!c) return;
      const point = rp.reset_point || "";
      const match = String(point).match(/#?(\d+)/);
      if (match) {
        const idx = parseInt(match[1], 10);
        if (idx >= 0 && idx < c.history.length) c.history = c.history.slice(0, idx);
      } else c.history = [];
      const chat = document.getElementById("chat");
      if (chat) chat.innerHTML = "";
      renderCurrentChat();
      persistChat(c);
      broadcast("reset", { chatId: c.id });
      toast("Контекст сброшен");
    }
  }

  // --- Notifications ---
  async function addNotification({ level, text, action, actionLabel }) {
    const n = {
      id: uid("notif"),
      at: new Date().toISOString(),
      level: level || "info",
      text: softenText(text),
      action: action || null,
      actionLabel: actionLabel || null,
    };
    state.notifications.push(n);
    if (state.notifications.length > 200) state.notifications = state.notifications.slice(-200);
    await dbPut(STORE_NOTIFICATIONS, n);
    updateNotifBadge();
    broadcast("notif_added", n);
  }
  function renderNotificationsList() {
    const box = document.getElementById("notificationsList");
    if (!box) return;
    box.innerHTML = "";
    if (!state.notifications.length) {
      box.innerHTML = '<div class="empty-note">Уведомлений нет. Всё спокойно.</div>';
      return;
    }
    const sorted = state.notifications.slice().sort((a, b) => (b.at || "").localeCompare(a.at || ""));
    sorted.forEach(n => {
      const el = document.createElement("div");
      el.className = "notif-item " + (n.level || "info");
      el.innerHTML = '<div class="notif-body">' +
        '<div class="notif-text">' + escHtml(n.text) + '</div>' +
        '<div class="notif-meta"><span>' + (n.at ? new Date(n.at).toLocaleString("ru-RU") : "") + '</span></div>' +
        (n.action && n.actionLabel ? '<button class="notif-action" type="button" data-action="' + escHtml(n.action) + '">' + escHtml(n.actionLabel) + '</button>' : '') +
        '</div>';
      box.appendChild(el);
    });
    box.querySelectorAll(".notif-action").forEach(btn => {
      btn.addEventListener("click", () => handleNotifAction(btn.dataset.action));
    });
  }
  function handleNotifAction(action) {
    if (action === "open_settings") { closeAllSheets(); setTimeout(() => document.getElementById("settingsBtn").click(), 200); }
    else if (action === "open_chat") closeAllSheets();
    else if (action === "open_lots") { closeAllSheets(); setTimeout(() => { renderLotsList(); openSheet("lotsSheet"); }, 200); }
    else if (action === "open_map") { closeAllSheets(); setTimeout(() => { renderMap(); openSheet("mapSheet"); }, 200); }
    else if (action === "open_exchange") { closeAllSheets(); setTimeout(() => { renderExchange(); openSheet("exchangeSheet"); }, 200); }
    else if (action === "mark_seen") markNotificationsSeen();
  }
  function markNotificationsSeen() {
    state.lastNotifSeenAt = new Date().toISOString();
    try { localStorage.setItem(LS_NOTIF_SEEN, state.lastNotifSeenAt); } catch (e) {}
    updateNotifBadge();
  }

  // --- Меню ---
  function updateMenu() {
    const lotList = state.lots.filter(l => !l.archived);
    const lotsDesc = document.getElementById("menuLotsDesc");
    if (lotsDesc) lotsDesc.textContent = lotList.length + " " + pluralize(lotList.length, ["Лот", "Лота", "Лотов"]);
    const lotsCount = document.getElementById("menuLotsCount");
    if (lotsCount) lotsCount.textContent = lotList.length;

    const activeChats = state.chats.filter(ch => !ch.lotId);
    const chatsDesc = document.getElementById("menuChatsDesc");
    if (chatsDesc) chatsDesc.textContent = activeChats.length ? (activeChats.length + " " + pluralize(activeChats.length, ["чат", "чата", "чатов"])) : "Не привязанные";
    const chatsCount = document.getElementById("menuChatsCount");
    if (chatsCount) chatsCount.textContent = activeChats.length;

    const docsTotal = state.lots.reduce((sum, l) => sum + ((l.documents || []).length), 0);
    const docsDesc = document.getElementById("menuDocumentsDesc");
    if (docsDesc) docsDesc.textContent = docsTotal + " " + pluralize(docsTotal, ["документ", "документа", "документов"]);
    const docsCount = document.getElementById("menuDocumentsCount");
    if (docsCount) docsCount.textContent = docsTotal;

    const newIdeas = state.lots.reduce((sum, l) => sum + ((l.ideas || []).filter(i => i.status === "new").length), 0);
    const ideasCount = document.getElementById("menuIdeasCount");
    if (ideasCount) {
      if (newIdeas > 0) { ideasCount.classList.remove("hidden"); ideasCount.textContent = newIdeas; }
      else ideasCount.classList.add("hidden");
    }

    const c = currentChat();
    const impCount = c && c.important ? Object.keys(c.important).length : 0;
    const impBadge = document.getElementById("menuImportantCount");
    if (impBadge) {
      if (impCount > 0) { impBadge.classList.remove("hidden"); impBadge.textContent = impCount; }
      else impBadge.classList.add("hidden");
    }

    const myCount = state.myPublicIds.length;
    const myBadge = document.getElementById("menuMyPublicCount");
    if (myBadge) {
      if (myCount > 0) { myBadge.classList.remove("hidden"); myBadge.textContent = myCount; }
      else myBadge.classList.add("hidden");
    }

    const myTemplates = collectMyTemplates();
    const myTplBadge = document.getElementById("menuMyTemplatesCount");
    if (myTplBadge) {
      if (myTemplates.length > 0) { myTplBadge.classList.remove("hidden"); myTplBadge.textContent = myTemplates.length; }
      else myTplBadge.classList.add("hidden");
    }

    const exCount = state.publicTemplates.length + state.publicLots.length;
    const exBadge = document.getElementById("menuExchangeCount");
    if (exBadge) {
      if (exCount > 0) { exBadge.classList.remove("hidden"); exBadge.textContent = exCount; }
      else exBadge.classList.add("hidden");
    }

    const blogTabNew = document.getElementById("blogTabNew");
    if (blogTabNew) blogTabNew.style.display = state.authorKey ? "" : "none";
  }

  // --- Мои шаблоны ---
  function collectMyTemplates() {
    const result = [];
    state.lots.forEach(l => {
      (l.documents || []).forEach((d, idx) => {
        result.push({
          id: d.id || (l.id + "_" + idx),
          name: d.name || "Документ",
          content: d.content || "",
          lotId: l.id,
          lotName: l.name,
          idx,
          publicId: d.publicId || null,
          source: "lot",
        });
      });
    });
    state.chats.forEach(c => {
      (c.documents || []).forEach((d, idx) => {
        result.push({
          id: d.id || (c.id + "_" + idx),
          name: d.name || "Документ",
          content: d.content || "",
          chatId: c.id,
          chatTitle: c.title,
          idx,
          publicId: d.publicId || null,
          source: "chat",
        });
      });
    });
    return result;
  }
  function renderMyTemplates() {
    const box = document.getElementById("myTemplatesContent");
    if (!box) return;
    box.innerHTML = "";
    const items = collectMyTemplates();
    if (!items.length) {
      box.innerHTML = '<div class="empty-note">Пока нет шаблонов. Создайте документ в Лоте или чате — и он появится здесь.</div>';
      return;
    }
    items.forEach(item => {
      const el = document.createElement("div");
      el.className = "artifact-item";
      const where = item.source === "lot" ? ("Лот: " + escHtml(item.lotName)) : ("Чат: " + escHtml(item.chatTitle || "—"));
      const statusBadge = item.publicId ? '<span class="artifact-item-stage public">Опубликован</span>' : '<span class="artifact-item-stage">Черновик</span>';
      el.innerHTML = '<div class="artifact-item-head"><span class="artifact-item-name">' + escHtml(item.name) + '</span>' + statusBadge + '</div>' +
        '<div class="artifact-item-meta"><span>' + where + '</span></div>' +
        (item.publicId ? '' : '<div class="public-actions" style="margin-top:8px;"><button class="take" data-id="' + escHtml(item.id) + '">Опубликовать</button></div>');
      box.appendChild(el);
    });
    box.querySelectorAll("button[data-id]").forEach(btn => {
      btn.addEventListener("click", () => {
        const id = btn.dataset.id;
        const item = items.find(x => x.id === id);
        if (!item) return;
        openPublishModal("template_from_doc", item);
      });
    });
  }

  // --- Метрики ---
  function metricCard(name, value, opts) {
    opts = opts || {};
    const level = opts.level || "ok";
    const alertClass = level === "crit" ? "crit" : level === "warn" ? "warn" : "ok";
    const cardClass = level === "crit" ? " crit" : level === "warn" ? " warn" : "";
    let html = '<div class="metric-card' + cardClass + '">';
    html += '<div class="metric-head"><div class="metric-name">' + escHtml(name) + '</div>';
    html += '<div class="metric-value">' + escHtml(String(value)) + '</div></div>';
    if (opts.bar != null) html += '<div class="metric-bar"><div class="metric-bar-fill" style="width:' + Math.max(0, Math.min(100, opts.bar * 100)) + '%"></div></div>';
    if (opts.desc) html += '<div class="metric-desc">' + escHtml(opts.desc) + '</div>';
    if (opts.alert) html += '<div class="metric-alert ' + alertClass + '"><span class="dot"></span>' + escHtml(opts.alert) + '</div>';
    html += '</div>';
    return html;
  }
  function humanBar(hc) {
    const humanPct = Math.round(hc * 100), aiPct = 100 - humanPct;
    return '<div class="human-bar"><div class="human" style="width:' + humanPct + '%">' + humanPct + '%</div><div class="ai" style="width:' + aiPct + '%">' + aiPct + '%</div></div>';
  }
  function buildMetricById(id, m) {
    const si = typeof m.stability_index === "number" ? m.stability_index : null;
    const hc = typeof m.human_contribution === "number" ? m.human_contribution : null;
    switch (id) {
      case "stability":
        return metricCard("Стабильность", si != null ? si.toFixed(2) : "—", {
          bar: si,
          level: si != null && si < 0.5 ? "crit" : si != null && si < 0.75 ? "warn" : "ok",
          desc: si != null ? (si >= 0.75 ? "Решение устойчиво." : si >= 0.5 ? "Есть нерешённые коллизии." : "Неустойчивое решение.") : "Появится после первого диалога.",
          alert: si != null && si < 0.5 ? "Обратить внимание" : null,
        });
      case "mind":
        return metricCard("Глубина", escHtml(m.mind_scale || "—"), { desc: "Уровень задачи." });
      case "pulse":
        return metricCard("Пульс", escHtml(m.cognitive_pulse || "—"), { desc: m.cognitive_pulse === "fast" ? "Быстрый темп." : "Ровный темп." });
      case "human": {
        let extra = "";
        if (hc != null) extra = humanBar(hc);
        return metricCard("Вклад человек / ИИ", hc != null ? Math.round(hc * 100) + "% / " + Math.round((1 - hc) * 100) + "%" : "—", { desc: "Соотношение вкладов." }) + extra;
      }
      case "balance": {
        const bal = state.balance || 0;
        return metricCard("Индекс полезности", (bal >= 0 ? "+" : "") + bal.toFixed(1), {
          level: bal < 0 ? "crit" : "ok",
          desc: "Накопленный вклад.",
          alert: bal < 0 ? "Индекс в минусе" : null,
        });
      }
      case "dominant":
        if (m.dominant_trait && m.dominant_trait.detected) return metricCard("Импульс", escHtml(m.dominant_trait.influence || "—"), { level: "warn", desc: m.dominant_trait.hint || "", alert: "Обратить внимание" });
        return "";
      case "social": {
        const sa = m.social_adaptation || {};
        return metricCard("Социальная адаптация", escHtml(sa.level || "inactive"), { desc: sa.reason || "" });
      }
      case "public": {
        const pi = m.public_index || {};
        return metricCard("Публичный индекс", String(pi.reputation || 0), { desc: "Отдал: " + (pi.given || 0) + " · Взял: " + (pi.taken || 0) });
      }
      default:
        return "";
    }
  }
  function renderMetricsSheet() {
    const box = document.getElementById("metricsContent");
    if (!box) return;
    const c = currentChat();
    const m = (c && c.lastMetrics) || {};
    let html = "";
    ["stability", "mind", "pulse", "human", "balance", "public", "dominant", "social"].forEach(id => { html += buildMetricById(id, m); });
    html += '<div style="margin-top:16px;font-size:11px;color:var(--muted);">Запросов в сессии: ' + ((c && c.sessionCount) || 0) + '</div>';
    box.innerHTML = html;
  }

  // --- Индекс ---
  function renderIndexSheet(tab) {
    tab = tab || "all";
    const c = currentChat();
    const n = typeof state.balance === "number" ? state.balance : 0;
    const sign = n >= 0 ? "+" : "";
    const bal = document.getElementById("indexBalance");
    if (bal) bal.textContent = sign + n.toFixed(1);
    const list = document.getElementById("indexList");
    if (!list) return;
    const history = (c && c.indexHistory) || [];
    let filtered = history;
    if (tab === "income") filtered = history.filter(h => (h.delta || 0) > 0);
    else if (tab === "expense") filtered = history.filter(h => (h.delta || 0) < 0);
    if (!filtered.length) {
      list.innerHTML = '<div class="empty-note">История пуста.</div>';
      return;
    }
    list.innerHTML = "";
    filtered.slice().reverse().forEach(h => {
      const el = document.createElement("div");
      el.className = "artifact-item";
      el.style.cursor = "default";
      const color = (h.delta || 0) > 0 ? "var(--success)" : "var(--critical)";
      el.innerHTML = '<div class="artifact-item-head"><span class="artifact-item-name">' + escHtml(h.name || "—") + '</span>' +
        '<span style="color:' + color + ';font-weight:600;">' + ((h.delta || 0) > 0 ? "+" : "") + (h.delta || 0).toFixed(1) + '</span></div>' +
        '<div class="artifact-item-meta"><span>' + escHtml(h.kind || "—") + '</span><span>' + (h.at ? new Date(h.at).toLocaleString("ru-RU") : "") + '</span></div>';
      list.appendChild(el);
    });
  }

  // --- Профиль ---
  function renderProfile() {
    const box = document.getElementById("profileContent");
    if (!box) return;
    const c = currentChat();
    const m = (c && c.lastMetrics) || {};
    let html = '<h3>Профиль</h3><div class="sheet-sub">Когнитивная карта</div>';
    const pi = m.public_index || {};
    html += '<div class="reputation-card">';
    html += '<div style="font-size:10.5px;text-transform:uppercase;letter-spacing:0.08em;color:var(--muted);font-weight:600;margin-bottom:6px;">Публичный индекс</div>';
    html += '<div class="reputation-value">' + (pi.reputation || 0) + '</div>';
    html += '<div class="reputation-row"><span class="label">Отдал</span><span class="value">' + (pi.given || 0) + '</span></div>';
    html += '<div class="reputation-row"><span class="label">Взял</span><span class="value">' + (pi.taken || 0) + '</span></div>';
    html += '<div class="reputation-row"><span class="label">Оценка</span><span class="value">' + (pi.help_score || 0) + '</span></div>';
    html += '</div>';
    const si = typeof m.stability_index === "number" ? m.stability_index : null;
    if (si != null) html += '<div class="artifact-item" style="cursor:default;"><div class="artifact-item-head"><span class="artifact-item-name">Стабильность</span><span class="artifact-item-stage">' + si.toFixed(2) + '</span></div></div>';
    const profile = m.profile || {};
    const patterns = profile.patterns || [];
    if (patterns.length) {
      html += '<div style="font-size:10.5px;text-transform:uppercase;letter-spacing:0.08em;color:var(--muted);font-weight:600;margin:16px 0 8px;">Паттерны мышления</div>';
      html += '<div style="display:flex;flex-wrap:wrap;gap:6px;">' + patterns.map(p => '<span style="padding:4px 10px;background:var(--accent-soft);color:var(--accent);border-radius:999px;font-size:12px;">' + escHtml(p) + '</span>').join("") + '</div>';
    }
    const distortions = profile.distortions || [];
    if (distortions.length) {
      html += '<div style="font-size:10.5px;text-transform:uppercase;letter-spacing:0.08em;color:var(--muted);font-weight:600;margin:16px 0 8px;">Искажения</div>';
      html += '<div style="display:flex;flex-wrap:wrap;gap:6px;">' + distortions.map(p => '<span style="padding:4px 10px;background:var(--warning-soft);color:var(--warning);border-radius:999px;font-size:12px;">' + escHtml(p) + '</span>').join("") + '</div>';
    }
    html += '<div style="font-size:10.5px;text-transform:uppercase;letter-spacing:0.08em;color:var(--muted);font-weight:600;margin:16px 0 8px;">Карта</div>';
    html += '<button class="open-editor-btn" id="profileMapBtn" type="button" style="width:100%;justify-content:center;margin-top:0;">Открыть карту местности</button>';
    box.innerHTML = html;
    const btn = document.getElementById("profileMapBtn");
    if (btn) btn.addEventListener("click", () => { closeAllSheets(); setTimeout(() => { renderMap(); openSheet("mapSheet"); }, 200); });
  }

  // --- Карта ---
  function renderMap() {
    const box = document.getElementById("mapContent");
    if (!box) return;
    const c = currentChat();
    const lot = currentLot();
    const m = (c && c.lastMetrics) || {};
    const lotName = lot ? lot.name : "Без Лота";
    const task = (c && c.history && c.history.length) ? (c.history[c.history.length - 2] && c.history[c.history.length - 2].content || "—") : "Начало";
    let html = "";
    html += '<div class="map-card">';
    html += '<div class="map-where">Лот</div>';
    html += '<div class="map-title">' + escHtml(lotName) + '</div>';
    html += '<div class="map-where">Чем занимаемся</div>';
    html += '<div style="font-size:13.5px;margin-bottom:14px;line-height:1.5;">' + escHtml(String(task).slice(0, 140)) + '</div>';
    html += '<div class="map-where">Прогресс</div>';
    const balance = state.balance || 0;
    const price = lot && lot.price ? parseFloat(String(lot.price).replace(/[^\d.-]/g, "")) : 0;
    if (price > 0) {
      const pct = Math.max(0, Math.min(100, Math.round(balance / price * 100)));
      html += '<div style="font-size:13px;margin-bottom:6px;">' + pct + '% до Лота — индекс ' + balance.toFixed(1) + ' из ' + price + '</div>';
      html += '<div class="metric-bar"><div class="metric-bar-fill" style="width:' + pct + '%"></div></div>';
    } else {
      html += '<div style="font-size:13px;color:var(--muted);">Цена Лота не задана.</div>';
    }
    html += '</div>';
    const steps = state.mapSteps || [];
    if (steps.length) {
      html += '<div class="map-card"><div class="map-where">План действий</div><div class="map-steps">';
      steps.forEach(s => {
        const cls = (s.state || "todo") + (s.dynamic ? " dynamic" : "");
        html += '<div class="map-step ' + cls + '"><div class="dot"></div><div><div class="map-step-text">' + escHtml(s.text || "") + '</div>';
        if (s.eta || s.dynamic) html += '<div class="map-step-meta">' + (s.eta ? escHtml(s.eta) : "") + (s.dynamic ? ' <span class="dynamic-label">· динамический</span>' : "") + '</div>';
        html += '</div></div>';
      });
      html += '</div></div>';
    } else {
      html += '<div class="map-card"><div class="empty-note">План появится после первых шагов.</div></div>';
    }
    box.innerHTML = html;
  }
  function regenerateMapForCurrent() {
    const lot = currentLot();
    const steps = [];
    steps.push({ text: "Определить Лот", state: lot ? "done" : "current", eta: lot ? null : "сейчас" });
    if (lot) {
      steps.push({ text: "Собрать цель и план", state: "done", eta: null });
      steps.push({ text: "Идти шагами к цели", state: "current", eta: "динамический" });
      steps.push({ text: "Получить Лот", state: "todo", eta: "динамический" });
    } else {
      steps.push({ text: "Выбрать направление", state: "todo", eta: "динамический" });
      steps.push({ text: "Получить первый Лот", state: "todo", eta: "динамический", dynamic: true });
    }
    state.mapSteps = steps;
  }

  // --- Лоты ---
  function renderLotsList() {
    const activeBox = document.getElementById("lotsActiveList");
    const archiveBox = document.getElementById("lotsArchiveList");
    if (!activeBox || !archiveBox) return;
    activeBox.innerHTML = "";
    archiveBox.innerHTML = "";
    const active = state.lots.filter(l => !l.archived);
    const archived = state.lots.filter(l => l.archived);
    if (!active.length) activeBox.innerHTML = '<div class="empty-note">Пока нет активных Лотов.</div>';
    else active.forEach(l => activeBox.appendChild(renderLotItem(l)));
    if (!archived.length) archiveBox.innerHTML = '<div class="empty-note">Архив пуст.</div>';
    else archived.forEach(l => archiveBox.appendChild(renderLotItem(l)));
  }
  function renderLotItem(l) {
    const item = document.createElement("div");
    item.className = "artifact-item";
    const chatsCount = (l.chatIds || []).length;
    const docsCount = (l.documents || []).length;
    const publicBadge = l.publicId ? '<span class="artifact-item-stage public">Опубликован</span>' : '<span class="artifact-item-stage">' + (l.price ? escHtml(String(l.price)) : "—") + '</span>';
    item.innerHTML = '<div class="artifact-item-head"><span class="artifact-item-name">' + escHtml(l.name) + '</span>' + publicBadge + '</div>' +
      '<div class="artifact-item-meta">' + (l.goal ? '<span>' + escHtml(l.goal.slice(0, 60)) + '</span>' : '') +
      '<span>' + chatsCount + ' ' + pluralize(chatsCount, ["чат", "чата", "чатов"]) + '</span>' +
      '<span>' + docsCount + ' ' + pluralize(docsCount, ["документ", "документа", "документов"]) + '</span></div>';
    item.addEventListener("click", () => openLotCard(l.id));
    let pressTimer = null;
    item.addEventListener("pointerdown", () => {
      pressTimer = setTimeout(() => { pressTimer = null; openLotModal(l.id); }, 550);
    });
    ["pointerup", "pointerleave", "pointercancel"].forEach(ev => {
      item.addEventListener(ev, () => { if (pressTimer) { clearTimeout(pressTimer); pressTimer = null; } });
    });
    return item;
  }
  function openLotCard(lotId) {
    const l = state.lots.find(x => x.id === lotId);
    if (!l) return;
    const box = document.getElementById("lotCardContent");
    const chats = state.chats.filter(c => c.lotId === l.id);
    const docs = l.documents || [];
    const ideas = l.ideas || [];
    let html = '<h3>' + escHtml(l.name) + '</h3>';
    html += '<div class="sheet-sub">' + (l.goal ? escHtml(l.goal) : "Цель не задана") + '</div>';
    if (l.price) html += '<div class="artifact-item-stage" style="margin-bottom:14px;">Стоимость: ' + escHtml(String(l.price)) + '</div>';
    if (l.publicId) html += '<div class="artifact-item-stage public" style="margin-bottom:14px;">Опубликован в Обмене</div>';
    html += '<button class="open-editor-btn" id="lotMapBtn" type="button" style="width:100%;justify-content:center;margin-top:0;margin-bottom:14px;">Открыть карту Лота</button>';
    if (!l.publicId) html += '<button class="open-editor-btn public" id="lotPublishBtn" type="button" style="width:100%;justify-content:center;margin-top:0;margin-bottom:14px;">Опубликовать в Обмен</button>';
    html += '<div style="font-size:10.5px;text-transform:uppercase;letter-spacing:0.08em;color:var(--muted);font-weight:600;margin:14px 0 8px;">Чаты</div>';
    if (!chats.length) html += '<div class="empty-note">Пока нет чатов.</div>';
    else html += '<div id="lotChatsList"></div>';
    html += '<div style="font-size:10.5px;text-transform:uppercase;letter-spacing:0.08em;color:var(--muted);font-weight:600;margin:18px 0 8px;">Документы</div>';
    if (!docs.length) html += '<div class="empty-note">Пока нет документов.</div>';
    else html += '<div id="lotDocsList"></div>';
    html += '<div style="font-size:10.5px;text-transform:uppercase;letter-spacing:0.08em;color:var(--muted);font-weight:600;margin:18px 0 8px;">Идеи</div>';
    if (!ideas.length) html += '<div class="empty-note">Пока нет идей.</div>';
    else html += '<div id="lotIdeasList"></div>';
    box.innerHTML = html;

    const mapBtn = document.getElementById("lotMapBtn");
    if (mapBtn) mapBtn.addEventListener("click", () => { closeAllSheets(); setTimeout(() => { renderMap(); openSheet("mapSheet"); }, 200); });
    const pubBtn = document.getElementById("lotPublishBtn");
    if (pubBtn) pubBtn.addEventListener("click", () => openPublishModal("lot", l));

    const chatsList = document.getElementById("lotChatsList");
    if (chatsList) chats.forEach(c => {
      const row = document.createElement("div");
      row.className = "artifact-item";
      row.innerHTML = '<div class="artifact-item-name">' + escHtml(c.title) + '</div>';
      row.addEventListener("click", () => { switchChat(c.id); closeAllSheets(); });
      chatsList.appendChild(row);
    });
    const docsList = document.getElementById("lotDocsList");
    if (docsList) docs.forEach((d, idx) => {
      const row = document.createElement("div");
      row.className = "artifact-item";
      row.innerHTML = '<div class="artifact-item-name">' + escHtml(d.name || "Документ") + '</div>';
      row.addEventListener("click", () => {
        closeAllSheets();
        setTimeout(() => openEditor({ type: "document", lotId: l.id, docIndex: idx, name: d.name || "", body: d.content || "" }), 200);
      });
      docsList.appendChild(row);
    });
    const ideasList = document.getElementById("lotIdeasList");
    if (ideasList) ideas.forEach((it) => {
      const row = document.createElement("div");
      row.className = "idea-row";
      const status = it.status || "new";
      row.innerHTML = '<div class="idea-status ' + status + '"></div><div class="idea-text' + (status === "done" ? " done" : "") + '">' + escHtml(it.text || "") + '</div>';
      row.addEventListener("click", () => {
        const next = { new: "in_progress", in_progress: "done", done: "new", archived: "new" };
        it.status = next[status] || "new";
        persistLot(l);
        openLotCard(l.id);
      });
      ideasList.appendChild(row);
    });
    openSheet("lotCardSheet");
  }
  function openLotModal(editId) {
    state.editingLotId = editId;
    const l = editId ? state.lots.find(x => x.id === editId) : null;
    document.getElementById("lotModalTitle").textContent = l ? "Редактировать Лот" : "Новый Лот";
    document.getElementById("lotNameInput").value = l ? l.name : "";
    document.getElementById("lotGoalInput").value = l && l.goal ? l.goal : "";
    document.getElementById("lotPriceInput").value = l && l.price ? l.price : "";
    document.getElementById("lotDangerRow").style.display = l ? "flex" : "none";
    document.getElementById("lotModalBg").classList.add("open");
    setTimeout(() => document.getElementById("lotNameInput").focus(), 100);
  }
  async function saveLot() {
    const name = (document.getElementById("lotNameInput").value || "").trim() || "Лот";
    const goal = (document.getElementById("lotGoalInput").value || "").trim();
    const price = (document.getElementById("lotPriceInput").value || "").trim();
    if (state.editingLotId) {
      const l = state.lots.find(x => x.id === state.editingLotId);
      if (l) { l.name = name; l.goal = goal || null; l.price = price || null; await persistLot(l); }
    } else {
      const fresh = createLotObj(name, goal, price);
      await dbPut(STORE_LOTS, fresh);
      state.lots.push(fresh);
    }
    updateMenu();
    closeAllSheets();
    broadcast("lots_updated", {});
    toast("Сохранено");
  }
  async function deleteLot() {
    if (!state.editingLotId) return;
    const l = state.lots.find(x => x.id === state.editingLotId);
    if (!l) return;
    if (!confirm("Удалить Лот «" + l.name + "»?")) return;
    const chatsToRemove = state.chats.filter(c => c.lotId === l.id);
    for (const c of chatsToRemove) await dbDel(STORE_CHATS, c.id);
    state.chats = state.chats.filter(c => c.lotId !== l.id);
    await dbDel(STORE_LOTS, l.id);
    state.lots = state.lots.filter(x => x.id !== l.id);
    if (!state.chats.length) {
      const fresh = createChatObj("Новый чат");
      await dbPut(STORE_CHATS, fresh);
      state.chats.push(fresh);
      state.currentChatId = fresh.id;
      await dbSetMeta("currentChatId", fresh.id);
    }
    const chat = document.getElementById("chat");
    if (chat) chat.innerHTML = "";
    renderCurrentChat();
    updateMenu();
    closeAllSheets();
    broadcast("lots_updated", {});
    toast("Лот удалён");
  }

  // --- Чаты ---
  async function switchChat(chatId) {
    if (chatId === state.currentChatId) return;
    state.currentChatId = chatId;
    await dbSetMeta("currentChatId", chatId);
    const chat = document.getElementById("chat");
    if (chat) chat.innerHTML = "";
    renderCurrentChat();
    updateMenu();
    regenerateMapForCurrent();
  }
  function renderChatsList() {
    const box = document.getElementById("chatsList");
    if (!box) return;
    box.innerHTML = "";
    const unattached = state.chats.filter(c => !c.lotId);
    if (!unattached.length) { box.innerHTML = '<div class="empty-note">Пока нет чатов без Лота.</div>'; return; }
    unattached.forEach(c => {
      const item = document.createElement("div");
      item.className = "artifact-item";
      item.innerHTML = '<div class="artifact-item-name">' + escHtml(c.title) + '</div>' +
        '<div class="artifact-item-meta"><span>' + (c.history ? c.history.length : 0) + ' сообщений</span></div>';
      item.addEventListener("click", () => { switchChat(c.id); closeAllSheets(); });
      box.appendChild(item);
    });
  }

  // --- Идеи / Документы / Важное ---
  function renderIdeasList() {
    const box = document.getElementById("ideasList");
    if (!box) return;
    box.innerHTML = "";
    const all = [];
    state.lots.forEach(l => (l.ideas || []).forEach((it, idx) => all.push({ lotId: l.id, idx, idea: it })));
    if (!all.length) { box.innerHTML = '<div class="empty-note">Пока нет идей.</div>'; return; }
    all.forEach(item => {
      const row = document.createElement("div");
      row.className = "idea-row";
      const status = item.idea.status || "new";
      row.innerHTML = '<div class="idea-status ' + status + '"></div><div class="idea-text' + (status === "done" ? " done" : "") + '">' + escHtml(item.idea.text || "") + '</div>';
      row.addEventListener("click", async () => {
        const next = { new: "in_progress", in_progress: "done", done: "new", archived: "new" };
        const l = state.lots.find(x => x.id === item.lotId);
        if (l) { l.ideas[item.idx].status = next[status] || "new"; await persistLot(l); renderIdeasList(); updateMenu(); }
      });
      box.appendChild(row);
    });
  }
  function renderDocumentsList() {
    const box = document.getElementById("documentsList");
    if (!box) return;
    box.innerHTML = "";
    const all = [];
    state.lots.forEach(l => (l.documents || []).forEach((d, idx) => all.push({ lotId: l.id, lotName: l.name, idx, doc: d })));
    const c = currentChat();
    const freeDocs = (c && c.documents) || [];
    if (!all.length && !freeDocs.length) { box.innerHTML = '<div class="empty-note">Пока нет документов.</div>'; return; }
    all.forEach(item => {
      const el = document.createElement("div");
      el.className = "artifact-item";
      el.innerHTML = '<div class="artifact-item-name">' + escHtml(item.doc.name || "Документ") + '</div><div class="artifact-item-meta"><span>' + escHtml(item.lotName) + '</span></div>';
      el.addEventListener("click", () => { closeAllSheets(); setTimeout(() => openEditor({ type: "document", lotId: item.lotId, docIndex: item.idx, name: item.doc.name || "", body: item.doc.content || "" }), 200); });
      box.appendChild(el);
    });
    freeDocs.forEach((d, idx) => {
      const el = document.createElement("div");
      el.className = "artifact-item";
      el.innerHTML = '<div class="artifact-item-name">' + escHtml(d.name || "Документ") + '</div><div class="artifact-item-meta"><span>Без Лота</span></div>';
      el.addEventListener("click", () => { closeAllSheets(); setTimeout(() => openEditor({ type: "document", docIndex: idx, name: d.name || "", body: d.content || "" }), 200); });
      box.appendChild(el);
    });
  }
  function renderImportantList() {
    const box = document.getElementById("importantList");
    if (!box) return;
    box.innerHTML = "";
    const c = currentChat();
    if (!c || !c.important || !Object.keys(c.important).length) { box.innerHTML = '<div class="empty-note">Пока нет важных сообщений.</div>'; return; }
    const ids = Object.keys(c.important).map(Number).sort((a, b) => b - a);
    ids.forEach(id => {
      const msg = c.history[id];
      if (!msg) return;
      const row = document.createElement("div");
      row.className = "artifact-item";
      row.innerHTML = '<div class="artifact-item-name">' + escHtml(msg.role === "user" ? "Вы" : "Monolog") + '</div>' +
        '<div class="artifact-item-meta"><span>' + escHtml((msg.content || "").slice(0, 140)) + '</span></div>';
      box.appendChild(row);
    });
  }

  // --- Обмен ---
  async function loadExchange(sort) {
    sort = sort || "new";
    try {
      const requests = [
        fetch(API_BASE + "/public/templates?sort=" + sort + "&limit=100"),
        fetch(API_BASE + "/public/lots?sort=" + sort + "&limit=100"),
      ];
      if (state.uid) requests.push(fetch(API_BASE + "/public/profile/" + state.uid));
      const [tRes, lRes, pRes] = await Promise.all(requests);
      if (tRes.ok) { const d = await tRes.json(); state.publicTemplates = d.templates || []; }
      if (lRes.ok) { const d = await lRes.json(); state.publicLots = d.lots || []; }
      state.myPublicIds = state.publicTemplates.filter(t => t.uid === state.uid).map(t => t.id)
        .concat(state.publicLots.filter(l => l.uid === state.uid).map(l => l.id));
      if (pRes && pRes.ok) {
        const p = await pRes.json();
        const c = currentChat();
        if (c) {
          c.lastMetrics = c.lastMetrics || {};
          c.lastMetrics.public_index = { given: p.given || 0, taken: p.taken || 0, help_score: p.help_score || 0, reputation: p.reputation || 0 };
          persistChat(c);
        }
      }
      updateMenu();
    } catch (e) {
      console.warn("exchange load failed", e);
    }
  }
  function renderExchange() {
    const box = document.getElementById("exchangeContent");
    if (!box) return;
    box.innerHTML = "";
    if (state.exchangeTab === "templates") {
      if (!state.publicTemplates.length) { box.innerHTML = '<div class="empty-note">Публичных шаблонов пока нет. Станьте первым.</div>'; return; }
      state.publicTemplates.forEach(t => box.appendChild(renderPublicTemplate(t)));
    } else {
      if (!state.publicLots.length) { box.innerHTML = '<div class="empty-note">Публичных Лотов пока нет.</div>'; return; }
      state.publicLots.forEach(l => box.appendChild(renderPublicLot(l)));
    }
  }
  function renderPublicTemplate(t) {
    const el = document.createElement("div");
    el.className = "public-item";
    const isMine = t.uid === state.uid;
    el.innerHTML = '<div class="public-item-head"><span class="public-item-name">' + escHtml(t.name) + '</span><span class="artifact-item-stage public">' + (isMine ? "Мой" : "Чужой") + '</span></div>' +
      (t.content ? '<div class="public-item-meta"><span>' + escHtml(String(t.content).slice(0, 120)) + '</span></div>' : '') +
      '<div class="public-item-meta"><span>Взяли: ' + (t.taken_count || 0) + '</span><span>Помогло: ' + Math.round((t.help_score || 0) * 100) + '%</span></div>' +
      ((t.tags && t.tags.length) ? '<div class="public-item-tags">' + t.tags.map(tg => '<span class="public-item-tag">' + escHtml(tg) + '</span>').join("") + '</div>' : '') +
      '<div class="public-actions">' +
      (isMine ? '' : '<button class="take">Взять</button>') +
      '<button class="help">Помогло</button>' +
      '<button class="nohelp">Не помогло</button>' +
      '</div>';
    el.querySelectorAll("button").forEach(b => {
      b.addEventListener("click", () => {
        if (b.classList.contains("take")) takePublic(t.id, "template");
        else if (b.classList.contains("help")) reviewPublic(t.id, "template", "help");
        else if (b.classList.contains("nohelp")) reviewPublic(t.id, "template", "nohelp");
      });
    });
    return el;
  }
  function renderPublicLot(l) {
    const el = document.createElement("div");
    el.className = "public-item";
    const isMine = l.uid === state.uid;
    el.innerHTML = '<div class="public-item-head"><span class="public-item-name">' + escHtml(l.name) + '</span><span class="artifact-item-stage public">' + (isMine ? "Мой" : "Чужой") + '</span></div>' +
      (l.goal ? '<div class="public-item-meta"><span>' + escHtml(String(l.goal).slice(0, 120)) + '</span></div>' : '') +
      (l.price ? '<div class="public-item-meta"><span>Стоимость: ' + escHtml(String(l.price)) + '</span></div>' : '') +
      '<div class="public-item-meta"><span>Взяли: ' + (l.taken_count || 0) + '</span></div>' +
      '<div class="public-actions">' +
      (isMine ? '' : '<button class="take">Взять как образец</button>') +
      '<button class="help">Помогло</button>' +
      '<button class="nohelp">Не помогло</button>' +
      '</div>';
    el.querySelectorAll("button").forEach(b => {
      b.addEventListener("click", () => {
        if (b.classList.contains("take")) takePublic(l.id, "lot");
        else if (b.classList.contains("help")) reviewPublic(l.id, "lot", "help");
        else if (b.classList.contains("nohelp")) reviewPublic(l.id, "lot", "nohelp");
      });
    });
    return el;
  }
  async function takePublic(targetId, targetType) {
    if (!state.uid) { toast("Нужен идентификатор"); return; }
    try {
      const r = await fetch(API_BASE + "/public/take", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_id: targetId, target_type: targetType, uid: state.uid }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || ("HTTP " + r.status));
      if (data.self) { toast("Это ваша публикация"); return; }
      const delta = (typeof data.index_delta === "number") ? data.index_delta : (targetType === "template" ? -1 : -2);
      const c = currentChat();
      if (c) {
        c.indexHistory = c.indexHistory || [];
        c.indexHistory.push({ at: new Date().toISOString(), delta, kind: "public_take", name: "взятие из Обмена" });
        persistChat(c);
      }
      state.balance = (state.balance || 0) + delta;
      await dbSetMeta("balance", state.balance);
      updateIndexBtn(delta);
      toast("Взято. Индекс: " + (delta > 0 ? "+" : "") + delta);
      await addNotification({ level: "info", text: "Вы взяли публичный " + (targetType === "template" ? "шаблон" : "Лот") + ". Списание индекса: " + delta });
      await loadExchange();
      renderExchange();
    } catch (e) { toast("Ошибка: " + e.message); }
  }
  async function reviewPublic(targetId, targetType, verdict) {
    if (!state.uid) { toast("Нужен идентификатор"); return; }
    try {
      const r = await fetch(API_BASE + "/public/review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_id: targetId, target_type: targetType, verdict, uid: state.uid }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || ("HTTP " + r.status));
      toast("Спасибо");
      await loadExchange();
      renderExchange();
    } catch (e) { toast("Ошибка: " + e.message); }
  }
  function openPublishModal(kind, obj) {
    state.publishContext = { kind, obj };
    const title = document.getElementById("publishModalTitle");
    const nameInput = document.getElementById("publishNameInput");
    const tagsInput = document.getElementById("publishTagsInput");
    const status = document.getElementById("publishStatus");
    if (kind === "template") { title.textContent = "Публикация шаблона"; nameInput.value = obj.name || ""; tagsInput.value = (obj.tags || []).join(", "); }
    else if (kind === "template_from_doc") { title.textContent = "Публикация шаблона"; nameInput.value = obj.name || ""; tagsInput.value = ""; }
    else { title.textContent = "Публикация Лота"; nameInput.value = obj.name || ""; tagsInput.value = ""; }
    status.textContent = "";
    document.getElementById("publishModalBg").classList.add("open");
  }
  async function confirmPublish() {
    const ctx = state.publishContext;
    if (!ctx) return;
    const name = (document.getElementById("publishNameInput").value || "").trim();
    const tags = (document.getElementById("publishTagsInput").value || "").split(",").map(s => s.trim()).filter(Boolean);
    const status = document.getElementById("publishStatus");
    if (!name) { status.textContent = "Нужно название"; return; }
    status.textContent = "Публикую...";
    try {
      let url, body;
      if (ctx.kind === "template" || ctx.kind === "template_from_doc") {
        const content = ctx.obj.content || ctx.obj.body || "";
        url = API_BASE + "/public/templates";
        body = { uid: state.uid, template: { name, content, kind: "pattern", tags } };
      } else {
        url = API_BASE + "/public/lots";
        body = { uid: state.uid, lot: { name, goal: ctx.obj.goal || "", price: ctx.obj.price || "" } };
      }
      const r = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || ("HTTP " + r.status));
      if (ctx.kind === "lot") {
        ctx.obj.publicId = (data.lot && data.lot.id) || null;
        await persistLot(ctx.obj);
      } else if (ctx.kind === "template_from_doc") {
        const item = ctx.obj;
        if (item.source === "lot") {
          const l = state.lots.find(x => x.id === item.lotId);
          if (l && l.documents && l.documents[item.idx]) {
            l.documents[item.idx].publicId = (data.template && data.template.id) || null;
            await persistLot(l);
          }
        } else if (item.source === "chat") {
          const cc = state.chats.find(x => x.id === item.chatId);
          if (cc && cc.documents && cc.documents[item.idx]) {
            cc.documents[item.idx].publicId = (data.template && data.template.id) || null;
            await persistChat(cc);
          }
        }
      }
      status.textContent = "Опубликовано";
      toast("Опубликовано");
      await addNotification({ level: "public", text: "Публикация успешна: " + name });
      closeAllSheets();
      await loadExchange();
    } catch (e) { status.textContent = "Ошибка: " + e.message; }
  }
  function renderMyPublic() {
    const box = document.getElementById("myPublicContent");
    if (!box) return;
    box.innerHTML = "";
    const mine = state.publicTemplates.filter(t => t.uid === state.uid).concat(state.publicLots.filter(l => l.uid === state.uid));
    if (!mine.length) { box.innerHTML = '<div class="empty-note">Пока ничего не опубликовано.</div>'; return; }
    mine.forEach(m => {
      const el = document.createElement("div");
      el.className = "public-item";
      el.innerHTML = '<div class="public-item-head"><span class="public-item-name">' + escHtml(m.name) + '</span><span class="artifact-item-stage public">Публикация</span></div>' +
        '<div class="public-item-meta"><span>Взяли: ' + (m.taken_count || 0) + '</span><span>Помогло: ' + Math.round((m.help_score || 0) * 100) + '%</span></div>';
      box.appendChild(el);
    });
  }

  // --- Дэшборд ---
  const ALL_METRICS = [
    { id: "stability", name: "Стабильность" },
    { id: "mind", name: "Глубина" },
    { id: "pulse", name: "Пульс" },
    { id: "human", name: "Вклад человек / ИИ" },
    { id: "balance", name: "Индекс полезности" },
    { id: "public", name: "Публичный индекс" },
    { id: "dominant", name: "Импульс" },
    { id: "social", name: "Социальная адаптация" },
  ];
  async function renderDashboard() {
    const box = document.getElementById("dashboardContent");
    if (!box) return;
    if (!state.dashboardMetrics) state.dashboardMetrics = ["stability", "mind", "pulse", "human", "balance", "public"];
    const c = currentChat();
    const m = (c && c.lastMetrics) || {};
    let html = "";
    state.dashboardMetrics.forEach(id => { html += buildMetricById(id, m); });
    html += '<div class="dash-toggle">';
    html += '<button class="dash-toggle-btn" id="dashToggleBtn" type="button">Показать список метрик<svg class="arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg></button>';
    html += '<div class="dash-dropdown" id="dashDropdown">';
    ALL_METRICS.forEach(metric => {
      const checked = state.dashboardMetrics.indexOf(metric.id) !== -1 ? "checked" : "";
      html += '<label class="dash-metric-opt"><input type="checkbox" data-metric="' + metric.id + '" ' + checked + ' /><span>' + escHtml(metric.name) + '</span></label>';
    });
    html += '</div></div>';
    box.innerHTML = html;
    const toggle = document.getElementById("dashToggleBtn");
    if (toggle) toggle.addEventListener("click", () => {
      document.getElementById("dashDropdown").classList.toggle("open");
      toggle.classList.toggle("open");
    });
    box.querySelectorAll(".dash-metric-opt input").forEach(inp => {
      inp.addEventListener("change", () => {
        const id = inp.dataset.metric;
        if (inp.checked) {
          if (state.dashboardMetrics.indexOf(id) === -1) state.dashboardMetrics.push(id);
        } else {
          state.dashboardMetrics = state.dashboardMetrics.filter(x => x !== id);
        }
        renderDashboard();
      });
    });
  }

  // --- Управление ---
  async function renderManagement() {
    const box = document.getElementById("managementContent");
    if (!box) return;
    if (!state.manageKey) {
      box.innerHTML = '<div class="management-note">Введите ключ Управления в настройках, чтобы открыть расширенные возможности.</div>';
      return;
    }
    let html = '<div class="management-note">Расширенное управление доступно с валидным ключом Управления.</div>';
    html += '<div class="row-actions" style="margin-top:10px;"><button class="open-editor-btn" id="mgmtCheckBtn" type="button" style="margin-top:0;width:100%;justify-content:center;">Проверить ключ на сервере</button></div>';
    html += '<div class="doc-status" id="mgmtStatus"></div>';
    box.innerHTML = html;
    const btn = document.getElementById("mgmtCheckBtn");
    const status = document.getElementById("mgmtStatus");
    if (btn) btn.addEventListener("click", async () => {
      status.textContent = "Проверяю...";
      try {
        const r = await fetch(API_BASE + "/management/check", { method: "POST", headers: { "X-Management-Key": state.manageKey } });
        const data = await r.json();
        if (r.ok && data.ok) status.textContent = "Ключ валиден. Расширенное управление активно.";
        else status.textContent = "Ключ не принят сервером: " + (data.detail || r.status);
      } catch (e) { status.textContent = "Ошибка: " + e.message; }
    });
  }

  // --- Релизы ---
  function createReleaseObj(description, type) {
    return { id: uid("rel"), at: new Date().toISOString(), description: description || "Ручной релиз", type: type || "manual", level: "info", patches: [], applied: true };
  }
  function renderReleasesList() {
    const box = document.getElementById("releasesList");
    if (!box) return;
    box.innerHTML = "";
    if (!state.releases.length) { box.innerHTML = '<div class="empty-note">Релизов пока нет.</div>'; return; }
    const sorted = state.releases.slice().sort((a, b) => (b.at || "").localeCompare(a.at || ""));
    sorted.forEach(r => {
      const el = document.createElement("div");
      el.className = "release-item";
      const level = r.level === "crit" ? "crit" : r.type === "auto" ? "auto" : "manual";
      el.innerHTML = '<div class="release-item-head"><span class="release-item-name">' + escHtml(r.description || "Релиз") + '</span>' +
        '<span class="release-status ' + level + '">' + escHtml((r.type || "manual") === "auto" ? "Авто" : "Ручной") + '</span></div>' +
        '<div class="release-comment">' + (r.at ? new Date(r.at).toLocaleString("ru-RU") : "") + '</div>';
      el.addEventListener("click", () => {
        if (confirm("Откатить к релизу?\n\n" + (r.description || ""))) toast("Откат помечен");
      });
      box.appendChild(el);
    });
  }
  function openReleaseModal() {
    document.getElementById("releaseCommentInput").value = "";
    document.getElementById("releasePublishStatus").textContent = "";
    document.getElementById("releaseModalSheet").classList.add("open");
    document.getElementById("sheetBg").classList.add("open");
  }
  async function publishRelease() {
    const comment = (document.getElementById("releaseCommentInput").value || "").trim();
    const status = document.getElementById("releasePublishStatus");
    status.textContent = "Готовлю релиз...";
    const release = createReleaseObj(comment || "Ручной релиз по запросу автора", "manual");
    state.releases.push(release);
    await dbPut(STORE_RELEASES, release);
    await addNotification({ level: "ok", text: "Релиз выпущен. " + (comment || "Без комментария"), action: "open_chat", actionLabel: "К диалогу" });
    renderReleasesList();
    status.textContent = "Готово";
    setTimeout(() => closeAllSheets(), 600);
    broadcast("releases_updated", {});
  }

  // --- Отчёт разработчика ---
  async function renderDevReport() {
    const box = document.getElementById("devReportList");
    if (!box) return;
    const analytics = await dbGetAll(STORE_ANALYTICS);
    const total = analytics.length;
    const ok = analytics.filter(a => a.success).length;
    const avgDuration = analytics.length ? Math.round(analytics.reduce((s, a) => s + (a.duration_ms || 0), 0) / analytics.length) : 0;
    const byProvider = {};
    analytics.forEach(a => { byProvider[a.provider] = (byProvider[a.provider] || 0) + 1; });
    if (!total) { box.innerHTML = '<div class="empty-note">Отчёт появится после сессий.</div>'; return; }
    let html = "";
    html += '<div class="artifact-item" style="cursor:default;"><div class="artifact-item-head"><span class="artifact-item-name">Всего</span><span class="artifact-item-stage">' + total + '</span></div></div>';
    html += '<div class="artifact-item" style="cursor:default;"><div class="artifact-item-head"><span class="artifact-item-name">Успех / Ошибка</span><span class="artifact-item-stage">' + ok + " / " + (total - ok) + '</span></div></div>';
    html += '<div class="artifact-item" style="cursor:default;"><div class="artifact-item-head"><span class="artifact-item-name">Среднее время</span><span class="artifact-item-stage">' + avgDuration + ' мс</span></div></div>';
    Object.keys(byProvider).forEach(pid => {
      html += '<div class="artifact-item" style="cursor:default;"><div class="artifact-item-head"><span class="artifact-item-name">' + escHtml(pid) + '</span><span class="artifact-item-stage">' + byProvider[pid] + '</span></div></div>';
    });
    box.innerHTML = html;
  }

  // --- О продукте / Бизнес ---
  function renderAbout() {
    document.getElementById("aboutContent").innerHTML =
      '<div class="info-block"><strong>Ядро (не меняется)</strong><br>Человек в центре. Отражаю, не веду. Прямота. Лоты — единица обмена. Ошибка → данные → класс → шаблон.</div>' +
      '<div class="info-block"><strong>Адаптивная часть (меняется)</strong><br>Интерфейс. Метрики. Тон. Модели. Правила показа. Форматы выбора.</div>' +
      '<div class="info-block"><strong>Обмен (2.0)</strong><br>Публичные шаблоны и Лоты. Взял — плати индексом. Отдал — получай. Публичный индекс — репутация.</div>' +
      '<div class="info-block"><strong>Слои A/B/C/D</strong><br>A · Факты — что известно. B · Интерпретации — что это значит. C · Решения — что делать. D · Мета — как мы думаем.</div>';
  }
  function renderBusiness() {
    document.getElementById("businessContent").innerHTML =
      '<div class="info-block"><strong>API Monolog</strong><br>Встраивание когнитивного партнёра в корпоративные системы.</div>' +
      '<div class="info-block"><strong>Что даёт бизнесу</strong><br>• Единый когнитивный интерфейс для команды<br>• Корпоративные Лоты — цели компании<br>• Обучение сотрудников шаблонам<br>• Аналитика принятий решений</div>' +
      '<div class="info-block"><strong>Модель монетизации</strong><br>• Pay-per-call · Pay-per-user · Enterprise</div>' +
      '<div class="info-block" style="color:var(--muted);font-style:italic;">Раздел в разработке.</div>';
  }

  // --- Редактор ---
  function openEditor(context) {
    state.editorContext = context || {};
    const name = context.name || "";
    const body = context.body || "";
    const isCode = context.type === "code";
    const isBlog = context.type === "blog_post";
    document.getElementById("editorName").value = name;
    const ta = document.getElementById("editorBody");
    ta.value = body;
    if (isCode) ta.classList.add("code");
    else ta.classList.remove("code");
    document.getElementById("editorStatus").textContent = "";
    document.getElementById("editorTitle").textContent = isCode ? "Редактор кода" : (isBlog ? "Редактор статьи" : "Редактор документа");
    document.getElementById("editorSub").textContent = isCode ? "Правьте код и сохраните в dev" : "Правьте текст";
    document.getElementById("editorCodeRow").style.display = isCode ? "flex" : "none";
    document.getElementById("editorPublishRow").style.display = isCode ? "none" : "flex";
    document.getElementById("editorPublishPublicBtn").style.display = isBlog ? "none" : "inline-flex";
    document.getElementById("editorBlogRow").style.display = isBlog ? "flex" : "none";
    openSheet("editorSheet");
  }
  async function saveEditorToLot() {
    const name = (document.getElementById("editorName").value || "").trim();
    const body = (document.getElementById("editorBody").value || "").trim();
    const status = document.getElementById("editorStatus");
    if (!name || !body) { status.textContent = "Нужны название и текст"; return; }
    const ctx = state.editorContext || {};
    const lotId = ctx.lotId;
    if (lotId) {
      const l = state.lots.find(x => x.id === lotId);
      if (!l) return;
      l.documents = l.documents || [];
      if (typeof ctx.docIndex === "number" && l.documents[ctx.docIndex]) {
        l.documents[ctx.docIndex].name = name;
        l.documents[ctx.docIndex].content = body;
      } else {
        l.documents.push({ id: uid("doc"), name, type: "документ", content: body, createdAt: new Date().toISOString(), publicId: null });
      }
      await persistLot(l);
    } else {
      const c = currentChat();
      if (!c) { status.textContent = "Нет чата"; return; }
      c.documents = c.documents || [];
      if (typeof ctx.docIndex === "number" && c.documents[ctx.docIndex]) {
        c.documents[ctx.docIndex].name = name;
        c.documents[ctx.docIndex].content = body;
      } else {
        c.documents.push({ id: uid("doc"), name, type: "документ", content: body, createdAt: new Date().toISOString(), publicId: null });
      }
      await persistChat(c);
    }
    updateMenu();
    status.textContent = "Сохранено";
    toast("Сохранено");
    setTimeout(() => closeAllSheets(), 600);
  }

  // --- Scan for alerts ---
  function scanForAlerts(metrics) {
    const m = metrics || {};
    const c = currentChat();
    if (!c) return;
    if (typeof m.index_delta === "number" && m.index_delta < 0) {
      const balance = state.balance || 0;
      if (balance < 0) addNotification({ level: "crit", text: "Индекс ушёл в минус. Лоты временно недоступны. Приложите усилие — получите навык или создайте шаблон.", action: "open_map", actionLabel: "Открыть карту" });
      else if (balance < 10) addNotification({ level: "warn", text: "Индекс приближается к нулю. Мы на грани. Сделайте вклад — навык или шаблон.", action: "open_chat", actionLabel: "К диалогу" });
    }
    const analytics = state._lastAnalytics || [];
    const errorCount = analytics.slice(-5).filter(a => a.success === false).length;
    if (errorCount >= 2) addNotification({ level: "warn", text: "Несколько запросов не прошли. Проверьте ключ.", action: "open_settings", actionLabel: "Настройки" });
    if (m.reset_proposal && m.reset_proposal.recommended) addNotification({ level: "info", text: "Monolog рекомендует сбросить контекст этой ветки. Причина: " + (m.reset_proposal.reason || "накопление помех"), action: "open_chat", actionLabel: "К диалогу" });
    if (m.learning_template && m.learning_template.active) {
      addNotification({ level: "info", text: "Шаблона нет. Записываем шаблон. Время: " + (m.learning_template.eta || "несколько шагов") + ". Что получите: " + (m.learning_template.benefit || "готовое решение") });
      if (c) c.learningTemplate = true;
      persistChat(c);
      updateProfileBadge();
    } else if (c && c.learningTemplate) {
      c.learningTemplate = false;
      persistChat(c);
      updateProfileBadge();
      addNotification({ level: "ok", text: "Шаблон записан. Теперь решение будет быстрее." });
    }
  }

  // --- Экспорт в core, чтобы core мог вызывать adaptive-функции ---
  window.MonologAdaptive = {
    getUserStatus,
    renderOrb,
    switchMode,
    renderOrbSheet,
    renderAiNote,
    updateIndexBtn,
    updateHeaderDynamic,
    updateNotifBadge,
    updateProfileBadge,
    confirmReset,
    addNotification,
    renderNotificationsList,
    markNotificationsSeen,
    updateMenu,
    collectMyTemplates,
    renderMyTemplates,
    metricCard,
    humanBar,
    buildMetricById,
    renderMetricsSheet,
    renderIndexSheet,
    renderProfile,
    renderMap,
    regenerateMapForCurrent,
    renderLotsList,
    renderLotItem,
    openLotCard,
    openLotModal,
    saveLot,
    deleteLot,
    switchChat,
    renderChatsList,
    renderIdeasList,
    renderDocumentsList,
    renderImportantList,
    loadExchange,
    renderExchange,
    takePublic,
    reviewPublic,
    openPublishModal,
    confirmPublish,
    renderMyPublic,
    renderDashboard,
    renderManagement,
    renderReleasesList,
    openReleaseModal,
    publishRelease,
    renderDevReport,
    renderAbout,
    renderBusiness,
    openEditor,
    saveEditorToLot,
    scanForAlerts,
  };

  // --- Прокидываем в core для использования ---
  C.renderOrb = renderOrb;
  C.switchMode = switchMode;
  C.renderOrbSheet = renderOrbSheet;
  C.renderAiNote = renderAiNote;
  C.updateIndexBtn = updateIndexBtn;
  C.updateHeaderDynamic = updateHeaderDynamic;
  C.addNotification = addNotification;
  C.renderNotificationsList = renderNotificationsList;
  C.markNotificationsSeen = markNotificationsSeen;
  C.updateMenu = updateMenu;
  C.renderMetricsSheet = renderMetricsSheet;
  C.renderIndexSheet = renderIndexSheet;
  C.renderProfile = renderProfile;
  C.renderMap = renderMap;
  C.regenerateMapForCurrent = regenerateMapForCurrent;
  C.renderLotsList = renderLotsList;
  C.openLotModal = openLotModal;
  C.saveLot = saveLot;
  C.deleteLot = deleteLot;
  C.switchChat = switchChat;
  C.renderChatsList = renderChatsList;
  C.renderIdeasList = renderIdeasList;
  C.renderDocumentsList = renderDocumentsList;
  C.renderImportantList = renderImportantList;
  C.loadExchange = loadExchange;
  C.renderExchange = renderExchange;
  C.openPublishModal = openPublishModal;
  C.confirmPublish = confirmPublish;
  C.renderMyPublic = renderMyPublic;
  C.renderMyTemplates = renderMyTemplates;
  C.renderDashboard = renderDashboard;
  C.renderManagement = renderManagement;
  C.renderReleasesList = renderReleasesList;
  C.openReleaseModal = openReleaseModal;
  C.publishRelease = publishRelease;
  C.renderDevReport = renderDevReport;
  C.renderAbout = renderAbout;
  C.renderBusiness = renderBusiness;
  C.openEditor = openEditor;
  C.saveEditorToLot = saveEditorToLot;
  C.scanForAlerts = scanForAlerts;

  // --- Bootstrap ---
  renderOrb();
  document.documentElement.setAttribute("data-mode", state.mode);
  updateIndexBtn();
  updateHeaderDynamic();
  renderAiNote();
  regenerateMapForCurrent();
  updateMenu();
}

// Ждём событие monolog-ready от core.js
if (window.MonologCore) {
  bootstrapAdaptive();
} else {
  window.addEventListener("monolog-ready", bootstrapAdaptive, { once: true });
  // Резервная страховка: если событие уже прошло
  setTimeout(() => {
    if (window.MonologCore && !window.MonologAdaptive) bootstrapAdaptive();
  }, 1000);
}