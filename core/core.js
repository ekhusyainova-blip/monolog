// core/core.js
// Ядро Monolog: состояние, IndexedDB, API, экономика, чат, init.

"use strict";

// --- Константы ---
const API_BASE = window.location.origin;
const LS_KEY = "monolog_api_key";
const LS_AUTHOR = "monolog_author_key";
const LS_MANAGE = "monolog_manage_key";
const LS_PROVIDER = "monolog_provider";
const LS_FONT = "monolog_font_size";
const LS_DEPTH = "monolog_depth_mode";
const LS_MODE = "monolog_mode";
const LS_UID = "monolog_uid";
const LS_NOTIF_SEEN = "monolog_notif_seen_at";
const DB_NAME = "monolog_db_v5";
const DB_VERSION = 1;
const STORE_LOTS = "lots";
const STORE_CHATS = "chats";
const STORE_RELEASES = "releases";
const STORE_ANALYTICS = "analytics";
const STORE_NOTIFICATIONS = "notifications";
const STORE_PUBLIC = "public_cache";
const STORE_META = "meta";
const SOFT_LIMIT = 4000;
const HARD_LIMIT = 8000;
const MODE_LABELS = { analyst: "Аналитик", strategist: "Стратег", neutral: "Симбиоз" };
const PROVIDERS_FALLBACK = [
  { id: "groq", name: "Groq" },
  { id: "openrouter", name: "OpenRouter" },
  { id: "cerebras", name: "Cerebras" },
  { id: "sambanova", name: "SambaNova" },
];

// --- Глобальное состояние ---
const state = {
  apiKey: "",
  authorKey: "",
  manageKey: "",
  provider: "groq",
  depthMode: "auto",
  fontSize: 14,
  uid: "",
  lots: [],
  chats: [],
  releases: [],
  notifications: [],
  publicTemplates: [],
  publicLots: [],
  myPublicIds: [],
  currentChatId: null,
  attachments: [],
  sessionStart: Date.now(),
  mode: "analyst",
  editingLotId: null,
  editorContext: null,
  placeholderIndex: 0,
  dashboardMetrics: null,
  lastNotifSeenAt: 0,
  mapSteps: [],
  exchangeTab: "templates",
  publishContext: null,
  balance: 0,
  providersCache: PROVIDERS_FALLBACK,
};

// --- Глобальные хелперы ---
let _bc = null;
try { _bc = new BroadcastChannel("monolog_sync"); } catch (e) {}
let _db = null;

function currentChat() { return state.chats.find(c => c.id === state.currentChatId); }
function currentLot() {
  const c = currentChat();
  if (!c || !c.lotId) return null;
  return state.lots.find(l => l.id === c.lotId);
}

function uid(prefix) {
  return (prefix || "id") + "_" + Date.now() + "_" + Math.random().toString(36).slice(2, 8);
}
function escHtml(t) {
  return String(t == null ? "" : t).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function pluralize(n, forms) {
  const mod10 = n % 10, mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return forms[0];
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return forms[1];
  return forms[2];
}
function toast(text) {
  const el = document.getElementById("toast");
  if (!el) return;
  el.textContent = text;
  el.classList.add("show");
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove("show"), 2000);
}
function renderMarkdown(text) {
  const safe = text == null ? "" : String(text);
  if (typeof marked !== "undefined" && marked && typeof marked.parse === "function") {
    try { return marked.parse(safe); } catch (e) {}
  }
  const esc = safe.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return "<p>" + esc.replace(/\n\n/g, "</p><p>").replace(/\n/g, "<br>") + "</p>";
}
function broadcast(type, payload) {
  try { if (_bc) _bc.postMessage({ type, payload, at: Date.now() }); } catch (e) {}
}
function softenText(text) {
  let s = String(text || "");
  s = s.replace(/\bнельзя\b/gi, "возможно, стоит попробовать иначе");
  s = s.replace(/\bзапрещено\b/gi, "возможно, стоит попробовать иначе");
  s = s.replace(/\bникогда\b/gi, "возможно, стоит попробовать иначе");
  s = s.replace(/\bне\s+смей\b/gi, "возможно, стоит попробовать иначе");
  s = s.replace(/\bвсегда\b/gi, "а может быть, лучше так?");
  s = s.replace(/\bобязательно\b/gi, "а может быть, лучше так?");
  s = s.replace(/\bдолжен\s+всегда\b/gi, "а может быть, лучше так?");
  return s;
}

// --- IndexedDB ---
function openDB() {
  return new Promise((resolve, reject) => {
    if (_db) return resolve(_db);
    try {
      const req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = (e) => {
        const db = e.target.result;
        if (!db.objectStoreNames.contains(STORE_LOTS)) db.createObjectStore(STORE_LOTS, { keyPath: "id" });
        if (!db.objectStoreNames.contains(STORE_CHATS)) db.createObjectStore(STORE_CHATS, { keyPath: "id" });
        if (!db.objectStoreNames.contains(STORE_RELEASES)) db.createObjectStore(STORE_RELEASES, { keyPath: "id" });
        if (!db.objectStoreNames.contains(STORE_ANALYTICS)) db.createObjectStore(STORE_ANALYTICS, { keyPath: "id" });
        if (!db.objectStoreNames.contains(STORE_NOTIFICATIONS)) db.createObjectStore(STORE_NOTIFICATIONS, { keyPath: "id" });
        if (!db.objectStoreNames.contains(STORE_PUBLIC)) db.createObjectStore(STORE_PUBLIC, { keyPath: "id" });
        if (!db.objectStoreNames.contains(STORE_META)) db.createObjectStore(STORE_META);
      };
      req.onsuccess = (e) => { _db = e.target.result; resolve(_db); };
      req.onerror = () => reject(req.error);
    } catch (e) { reject(e); }
  });
}
async function dbGetAll(store) {
  try {
    const db = await openDB();
    return new Promise((resolve) => {
      const tx = db.transaction(store, "readonly");
      const req = tx.objectStore(store).getAll();
      req.onsuccess = () => resolve(req.result || []);
      req.onerror = () => resolve([]);
    });
  } catch (e) { return []; }
}
async function dbPut(store, val) {
  try {
    const db = await openDB();
    return new Promise((resolve) => {
      const tx = db.transaction(store, "readwrite");
      tx.objectStore(store).put(val);
      tx.oncomplete = () => resolve(true);
      tx.onerror = () => resolve(false);
    });
  } catch (e) { return false; }
}
async function dbDel(store, key) {
  try {
    const db = await openDB();
    return new Promise((resolve) => {
      const tx = db.transaction(store, "readwrite");
      tx.objectStore(store).delete(key);
      tx.oncomplete = () => resolve(true);
    });
  } catch (e) { return false; }
}
async function dbGetMeta(key) {
  try {
    const db = await openDB();
    return new Promise((resolve) => {
      const tx = db.transaction(STORE_META, "readonly");
      const req = tx.objectStore(STORE_META).get(key);
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => resolve(null);
    });
  } catch (e) { return null; }
}
async function dbSetMeta(key, val) {
  try {
    const db = await openDB();
    return new Promise((resolve) => {
      const tx = db.transaction(STORE_META, "readwrite");
      tx.objectStore(STORE_META).put(val, key);
      tx.oncomplete = () => resolve(true);
    });
  } catch (e) { return false; }
}

// --- Тема и шрифт ---
function applyTheme() {
  let theme;
  if (state.depthMode === "auto") {
    const hour = new Date().getHours();
    theme = (hour >= 7 && hour < 20) ? "light" : "dark";
  } else {
    theme = state.depthMode === "deep" ? "dark" : "light";
  }
  document.documentElement.setAttribute("data-theme", theme);
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", theme === "dark" ? "#0F1115" : "#F7F8FA");
}
function applyFontSize() {
  document.documentElement.style.setProperty("--font-size", state.fontSize + "px");
}
function applyProfile() {
  document.querySelectorAll("#depthSeg button").forEach(el => {
    el.classList.toggle("active", el.dataset.depth === state.depthMode);
  });
  applyTheme();
  applyFontSize();
}

// --- Чат ---
function addRow(role, content, options) {
  options = options || {};
  const chat = document.getElementById("chat");
  if (!chat) return null;
  const row = document.createElement("div");
  row.className = "row " + role;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (role === "agent") {
    const badge = document.createElement("div");
    badge.className = "mode-badge " + state.mode;
    const dot = document.createElement("span");
    dot.className = "dot";
    badge.appendChild(dot);
    const label = document.createElement("span");
    label.textContent = MODE_LABELS[state.mode];
    badge.appendChild(label);
    bubble.appendChild(badge);
    const body = document.createElement("div");
    body.innerHTML = renderMarkdown(softenText(content));
    bubble.appendChild(body);
    const actions = document.createElement("div");
    actions.className = "msg-actions";
    const copyBtn = document.createElement("button");
    copyBtn.className = "msg-action";
    copyBtn.type = "button";
    copyBtn.title = "Копировать";
    copyBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';
    copyBtn.addEventListener("click", () => {
      if (navigator.clipboard) navigator.clipboard.writeText(content || "");
      toast("Скопировано");
    });
    actions.appendChild(copyBtn);
    const impBtn = document.createElement("button");
    impBtn.className = "msg-action";
    impBtn.type = "button";
    impBtn.title = "Важное";
    impBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 16.8 5.8 21.3l2.4-7.4L2 9.4h7.6z"/></svg>';
    const c = currentChat();
    const msgId = options.msgId != null ? options.msgId : (c ? c.history.length : 0);
    if (c && c.important && c.important[msgId]) impBtn.classList.add("active");
    impBtn.addEventListener("click", () => {
      if (!c) return;
      c.important = c.important || {};
      if (c.important[msgId]) delete c.important[msgId];
      else c.important[msgId] = true;
      impBtn.classList.toggle("active");
      persistChat(c);
    });
    actions.appendChild(impBtn);
    bubble.appendChild(actions);
  } else {
    bubble.textContent = content;
  }
  row.appendChild(bubble);
  chat.appendChild(row);
  chat.scrollTop = chat.scrollHeight;
  return { row, bubble };
}

function renderCurrentChat() {
  const c = currentChat();
  if (!c) return;
  c.history = c.history || [];
  const chat = document.getElementById("chat");
  chat.innerHTML = "";
  if (!c.history.length) {
    if (typeof renderDemo === "function") renderDemo();
  } else {
    c.history.forEach((m, idx) => {
      addRow(m.role === "user" ? "user" : "agent", m.content || "", { msgId: idx });
    });
    chat.scrollTop = chat.scrollHeight;
  }
  if (c.lastMetrics) {
    if (typeof updateIndexBtn === "function") updateIndexBtn();
    if (typeof updateHeaderDynamic === "function") updateHeaderDynamic();
    if (typeof renderAiNote === "function") renderAiNote();
  }
}

async function sendWithRetry(payload, tries) {
  tries = tries == null ? 2 : tries;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 120000);
  try {
    const r = await fetch(API_BASE + "/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    return r;
  } catch (e) {
    clearTimeout(timeoutId);
    if (tries > 0 && (e.name === "TypeError" || e.name === "AbortError")) {
      await new Promise(r => setTimeout(r, 1500));
      return sendWithRetry(payload, tries - 1);
    }
    throw e;
  }
}

async function send() {
  const input = document.getElementById("input");
  const btn = document.getElementById("sendBtn");
  const text = (input.value || "").trim();
  const c = currentChat();
  if (!c || (!text && !state.attachments.length)) return;
  if (text.length > HARD_LIMIT) { toast("Слишком длинный запрос. Сократите или прикрепите файл."); return; }

  const demoBlock = document.querySelector(".demo-block");
  if (demoBlock) demoBlock.remove();

  const userDisplay = text || ("[Вложение: " + state.attachments.map(a => a.name).join(", ") + "]");
  input.value = "";
  input.style.height = "auto";
  if (typeof updateCharCounter === "function") updateCharCounter();
  addRow("user", userDisplay);

  const attachmentsPayload = state.attachments.slice();
  state.attachments = [];
  if (typeof renderAttachPreview === "function") renderAttachPreview();
  btn.disabled = true;

  const thinking = addRow("agent", "");
  const orb = document.getElementById("orbBtn");
  if (orb) orb.classList.add("thinking");
  const thinkingBody = thinking.bubble.querySelector("div:not(.mode-badge):not(.msg-actions)");
  if (thinkingBody) thinkingBody.innerHTML = '<span class="typing"><span></span><span></span><span></span></span>';

  const lot = currentLot();
  const carried = {
    passport: lot && lot.goal ? { level: "micro", title: lot.name, goal: lot.goal } : {},
    profile: {},
    artifacts: lot ? (lot.documents || []).slice(-3) : [],
  };

  const startedAt = Date.now();
  let success = false, errorCode = null;

  try {
    const r = await sendWithRetry({
      message: text || "Проанализируй вложения.",
      attachments: attachmentsPayload,
      carried_metrics: carried,
      api_key: state.apiKey || null,
      provider: state.provider || "groq",
      management_key: state.manageKey || null,
    });
    let data = null;
    try { data = await r.json(); } catch (e) {}

    const chat = document.getElementById("chat");
    if (thinking.row && thinking.row.parentNode === chat) chat.removeChild(thinking.row);
    if (orb) orb.classList.remove("thinking");

    if (!r.ok) {
      errorCode = r.status;
      const msg = (data && data.detail) || r.statusText;
      addRow("agent", "⚠ " + softenText(msg));
      if (typeof addNotification === "function") {
        if (r.status === 429) await addNotification({ level: "warn", text: msg, action: "open_settings", actionLabel: "Проверить ключ" });
        else if (r.status === 403 || r.status === 401) await addNotification({ level: "warn", text: "Ключ не принят. Проверьте ключ в настройках.", action: "open_settings", actionLabel: "Открыть настройки" });
        else if (r.status === 413) await addNotification({ level: "warn", text: "Запрос слишком длинный. Сократите или прикрепите файл." });
        else if (r.status >= 500) await addNotification({ level: "warn", text: "Сервер провайдера не ответил. Попробуйте ещё раз через минуту." });
      }
    } else if (data) {
      success = true;
      c.sessionCount = (c.sessionCount || 0) + 1;
      const newMsgId = c.history.length;
      addRow("agent", data.reply_text || "", { msgId: newMsgId });
      c.lastMetrics = data.metrics || {};
      c.history.push({ role: "user", content: userDisplay });
      c.history.push({ role: "assistant", content: data.reply_text || "" });
      c.updatedAt = new Date().toISOString();

      const delta = (data.metrics && data.metrics.index_delta);
      if (typeof delta === "number" && delta !== 0) {
        c.indexHistory = c.indexHistory || [];
        c.indexHistory.push({ at: new Date().toISOString(), delta, kind: "meta", name: "изменение" });
        if (c.indexHistory.length > 200) c.indexHistory.shift();
        state.balance = (state.balance || 0) + delta;
        await dbSetMeta("balance", state.balance);
        if (typeof addNotification === "function") {
          if (delta > 0) await addNotification({ level: "ok", text: "Индекс пополнен: +" + delta.toFixed(1) + "." });
          else if (delta < 0) await addNotification({ level: "info", text: "Списание индекса: " + delta.toFixed(1) + "." });
        }
      }
      persistChat(c);
      if (typeof updateIndexBtn === "function") updateIndexBtn(typeof delta === "number" ? delta : 0);
      if (typeof updateHeaderDynamic === "function") updateHeaderDynamic();
      if (typeof renderAiNote === "function") renderAiNote();
      if (typeof scanForAlerts === "function") scanForAlerts(data.metrics || {});
      broadcast("chat_updated", { chatId: c.id });
      if (typeof regenerateMapForCurrent === "function") regenerateMapForCurrent();
    } else {
      addRow("agent", "Пустой ответ сервера.");
    }
  } catch (e) {
    const chat = document.getElementById("chat");
    if (thinking.row && thinking.row.parentNode === chat) chat.removeChild(thinking.row);
    if (orb) orb.classList.remove("thinking");
    let msg = "Не удалось связаться с сервером.";
    if (e && e.name === "AbortError") msg = "Превышено время ожидания. Попробуйте ещё раз.";
    else if (e && e.name === "TypeError") msg = "Проверьте соединение.";
    addRow("agent", msg);
    errorCode = "network";
    if (typeof addNotification === "function") await addNotification({ level: "warn", text: msg });
  } finally {
    btn.disabled = false;
    input.focus();
    const duration = Date.now() - startedAt;
    const an = {
      id: uid("an"),
      at: new Date().toISOString(),
      provider: state.provider,
      model: null,
      key_source: state.apiKey ? "user" : "developer",
      msg_len: (text || "").length,
      lot_id: c.lotId || null,
      duration_ms: duration,
      success,
      error: errorCode,
    };
    await dbPut(STORE_ANALYTICS, an);
    state._lastAnalytics = (state._lastAnalytics || []).slice(-20).concat([an]);
  }
}

// --- Чаты / Лоты ---
function createChatObj(title, lotId) {
  return {
    id: uid("chat"),
    title: title || "Новый чат",
    lotId: lotId || null,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    history: [],
    lastMetrics: null,
    sessionCount: 0,
    important: {},
    indexHistory: [],
    priorities: [],
    documents: [],
  };
}
function createLotObj(name, goal, price) {
  return {
    id: uid("lot"),
    name: name || "Лот",
    goal: goal || null,
    price: price || null,
    createdAt: new Date().toISOString(),
    archived: false,
    documents: [],
    ideas: [],
    chatIds: [],
    indexHistory: [],
    indexTotal: 0,
    publicId: null,
  };
}
async function persistChat(c) {
  if (!c) return;
  await dbPut(STORE_CHATS, c);
  await dbSetMeta("currentChatId", c.id);
}
async function persistLot(l) {
  if (!l) return;
  await dbPut(STORE_LOTS, l);
}

// --- Загрузка данных ---
async function loadData() {
  state.lots = await dbGetAll(STORE_LOTS);
  state.chats = await dbGetAll(STORE_CHATS);
  state.releases = await dbGetAll(STORE_RELEASES);
  state.notifications = await dbGetAll(STORE_NOTIFICATIONS);
  const currentId = await dbGetMeta("currentChatId");
  if (currentId && state.chats.find(c => c.id === currentId)) {
    state.currentChatId = currentId;
  } else if (state.chats.length) {
    state.currentChatId = state.chats[0].id;
  } else {
    const fresh = createChatObj("Новый чат");
    await dbPut(STORE_CHATS, fresh);
    state.chats.push(fresh);
    state.currentChatId = fresh.id;
    await dbSetMeta("currentChatId", fresh.id);
  }
  const seen = await dbGetMeta("lastNotifSeenAt");
  if (seen) state.lastNotifSeenAt = seen;
  try { const ls = localStorage.getItem(LS_NOTIF_SEEN); if (ls) state.lastNotifSeenAt = ls; } catch (e) {}
  const bal = await dbGetMeta("balance");
  if (typeof bal === "number") state.balance = bal;
}

// --- Применение темы/шрифта ---
function applyProfileGlobal() {
  document.querySelectorAll("#depthSeg button").forEach(el => {
    el.classList.toggle("active", el.dataset.depth === state.depthMode);
  });
  applyTheme();
  applyFontSize();
}

// --- Char counter ---
function updateCharCounter() {
  const input = document.getElementById("input");
  const counter = document.getElementById("charCounter");
  if (!input || !counter) return;
  const len = (input.value || "").length;
  if (len === 0) { counter.textContent = ""; counter.className = "char-counter"; return; }
  counter.textContent = len + " / " + HARD_LIMIT;
  counter.className = "char-counter";
  if (len > HARD_LIMIT) counter.classList.add("critical");
  else if (len > SOFT_LIMIT) counter.classList.add("warn");
}

// --- Attach ---
function renderAttachPreview() {
  const box = document.getElementById("attachPreview");
  if (!box) return;
  box.innerHTML = "";
  state.attachments.forEach((a, idx) => {
    const chip = document.createElement("div");
    chip.className = "attach-chip";
    chip.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg><span class="name">' + escHtml(a.name) + '</span><button class="remove" type="button">×</button>';
    chip.querySelector(".remove").addEventListener("click", () => {
      state.attachments.splice(idx, 1);
      renderAttachPreview();
    });
    box.appendChild(chip);
  });
}
async function handleFiles(files) {
  const list = Array.from(files || []);
  for (const f of list) {
    if (state.attachments.length >= 3) break;
    if (f.size > 5 * 1024 * 1024) continue;
    let text = "";
    try { text = await f.text(); } catch (e) { text = ""; }
    if (text.length > 3000) text = text.slice(0, 3000) + "...[обрезано]";
    state.attachments.push({ name: f.name, type: f.type, text });
  }
  renderAttachPreview();
}

// --- Провайдеры ---
function renderProviderGrid() {
  const grid = document.getElementById("providerGrid");
  if (!grid) return;
  grid.innerHTML = "";
  state.providersCache.forEach(pr => {
    const btn = document.createElement("button");
    btn.className = "provider-btn" + (state.provider === pr.id ? " active" : "");
    btn.type = "button";
    btn.innerHTML = '<span class="name">' + escHtml(pr.name) + '</span>';
    btn.addEventListener("click", () => {
      state.provider = pr.id;
      try { localStorage.setItem(LS_PROVIDER, pr.id); } catch (e) {}
      renderProviderGrid();
    });
    grid.appendChild(btn);
  });
}
function setupEyeButtons() {
  document.querySelectorAll(".eye-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.eye;
      const input = document.getElementById(id);
      if (!input) return;
      if (input.type === "password") {
        input.type = "text";
        btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><path d="M1 1l22 22"/></svg>';
      } else {
        input.type = "password";
        btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>';
      }
    });
  });
}

// --- Шторки и модалки ---
function openSheet(id) {
  const bg = document.getElementById("sheetBg");
  if (bg) bg.classList.add("open");
  const el = document.getElementById(id);
  if (el) el.classList.add("open");
}
function closeAllSheets() {
  const bg = document.getElementById("sheetBg");
  if (bg) bg.classList.remove("open");
  document.querySelectorAll(".sheet").forEach(s => s.classList.remove("open"));
  document.querySelectorAll(".modal-bg").forEach(m => m.classList.remove("open"));
}
function setupSwipeToClose(sheetEl, handleEl) {
  if (!sheetEl || !handleEl) return;
  let startY = 0, currentY = 0, dragging = false;
  function onStart(e) { dragging = true; startY = (e.touches ? e.touches[0].clientY : e.clientY); sheetEl.style.transition = "none"; }
  function onMove(e) { if (!dragging) return; currentY = (e.touches ? e.touches[0].clientY : e.clientY); const dy = Math.max(0, currentY - startY); sheetEl.style.transform = "translateY(" + dy + "px)"; }
  function onEnd() {
    if (!dragging) return;
    dragging = false;
    sheetEl.style.transition = "";
    sheetEl.style.transform = "";
    if (currentY - startY > 70) closeAllSheets();
  }
  handleEl.addEventListener("touchstart", onStart, { passive: true });
  handleEl.addEventListener("touchmove", onMove, { passive: true });
  handleEl.addEventListener("touchend", onEnd);
  handleEl.addEventListener("mousedown", onStart);
  window.addEventListener("mousemove", onMove);
  window.addEventListener("mouseup", onEnd);
}

// --- Init ---
async function init() {
  setTimeout(() => {
    const sp = document.getElementById("splash");
    if (sp) sp.classList.add("hide");
  }, 500);

  try {
    try {
      state.apiKey = localStorage.getItem(LS_KEY) || "";
      state.authorKey = localStorage.getItem(LS_AUTHOR) || "";
      state.manageKey = localStorage.getItem(LS_MANAGE) || "";
      state.provider = localStorage.getItem(LS_PROVIDER) || "groq";
      state.depthMode = localStorage.getItem(LS_DEPTH) || "auto";
      const fs = parseInt(localStorage.getItem(LS_FONT) || "14", 10);
      state.fontSize = isNaN(fs) ? 14 : fs;
      const mode = localStorage.getItem(LS_MODE);
      if (mode === "analyst" || mode === "strategist" || mode === "neutral") state.mode = mode;
      state.uid = localStorage.getItem(LS_UID) || "";
      if (!state.uid) { state.uid = "u_" + Date.now() + "_" + Math.random().toString(36).slice(2, 8); localStorage.setItem(LS_UID, state.uid); }
    } catch (e) {}

    applyProfileGlobal();
    if (typeof renderOrb === "function") renderOrb();
    document.documentElement.setAttribute("data-mode", state.mode);

    await loadData();
    renderCurrentChat();
    if (typeof updateMenu === "function") updateMenu();
    if (typeof updateIndexBtn === "function") updateIndexBtn();
    if (typeof updateHeaderDynamic === "function") updateHeaderDynamic();
    if (typeof renderAiNote === "function") renderAiNote();
    if (typeof regenerateMapForCurrent === "function") regenerateMapForCurrent();

    // Sheets — swipe
    [
      "orbSheet", "menuSheet", "indexSheet", "profileSheet", "metricsSheet",
      "notificationsSheet", "exchangeSheet", "myTemplatesSheet", "myPublicSheet",
      "lotsSheet", "lotCardSheet", "mapSheet", "ideasSheet", "importantSheet",
      "dashboardSheet", "managementSheet", "releasesSheet", "releaseModalSheet",
      "devReportSheet", "documentsSheet", "chatsSheet", "blogSheet",
      "aboutSheet", "businessSheet", "editorSheet"
    ].forEach(id => {
      const s = document.getElementById(id);
      const h = s ? s.querySelector(".sheet-handle") : null;
      if (s && h) setupSwipeToClose(s, h);
    });

    // Сфера — обработчики
    const orbBtn = document.getElementById("orbBtn");
    if (orbBtn) {
      let orbPressTimer = null, orbMoved = false;
      orbBtn.addEventListener("pointerdown", () => {
        orbMoved = false;
        orbPressTimer = setTimeout(() => {
          orbPressTimer = null;
          if (typeof switchMode === "function") switchMode();
        }, 550);
      });
      orbBtn.addEventListener("pointermove", () => {
        orbMoved = true;
        if (orbPressTimer) { clearTimeout(orbPressTimer); orbPressTimer = null; }
      });
      ["pointerup", "pointerleave", "pointercancel"].forEach(ev => {
        orbBtn.addEventListener(ev, () => {
          if (orbPressTimer) { clearTimeout(orbPressTimer); orbPressTimer = null; }
          if (!orbMoved && ev === "pointerup") {
            if (typeof renderOrbSheet === "function") renderOrbSheet();
            openSheet("orbSheet");
          }
        });
      });
    }

    // Header buttons — только те, что в core
    const indexBtn = document.getElementById("indexBtn");
    if (indexBtn) indexBtn.addEventListener("click", () => {
      if (typeof renderIndexSheet === "function") renderIndexSheet("all");
      openSheet("indexSheet");
    });
    const metricsBtn = document.getElementById("metricsBtn");
    if (metricsBtn) metricsBtn.addEventListener("click", () => {
      if (typeof renderMetricsSheet === "function") renderMetricsSheet();
      openSheet("metricsSheet");
    });
    const exchangeBtn = document.getElementById("exchangeBtn");
    if (exchangeBtn) exchangeBtn.addEventListener("click", async () => {
      if (typeof loadExchange === "function") await loadExchange();
      if (typeof renderExchange === "function") renderExchange();
      openSheet("exchangeSheet");
    });
    const notifBtn = document.getElementById("notifBtn");
    if (notifBtn) notifBtn.addEventListener("click", () => {
      if (typeof renderNotificationsList === "function") renderNotificationsList();
      openSheet("notificationsSheet");
      setTimeout(() => { if (typeof markNotificationsSeen === "function") markNotificationsSeen(); }, 800);
    });
    const profileBtn = document.getElementById("profileBtn");
    if (profileBtn) profileBtn.addEventListener("click", () => {
      if (typeof renderProfile === "function") renderProfile();
      openSheet("profileSheet");
    });
    const menuBtn = document.getElementById("menuBtn");
    if (menuBtn) menuBtn.addEventListener("click", () => {
      if (typeof updateMenu === "function") updateMenu();
      openSheet("menuSheet");
    });
    const settingsBtn = document.getElementById("settingsBtn");
    if (settingsBtn) settingsBtn.addEventListener("click", () => {
      const k = document.getElementById("keyInput"); if (k) k.value = state.apiKey || "";
      const mk = document.getElementById("manageKeyInput"); if (mk) mk.value = state.manageKey || "";
      const ak = document.getElementById("authorKeyInput"); if (ak) ak.value = state.authorKey || "";
      const rk = document.getElementById("rememberKey"); if (rk) rk.checked = !!localStorage.getItem(LS_KEY);
      const rmk = document.getElementById("rememberManageKey"); if (rmk) rmk.checked = !!localStorage.getItem(LS_MANAGE);
      const rak = document.getElementById("rememberAuthorKey"); if (rak) rak.checked = !!localStorage.getItem(LS_AUTHOR);
      const fsr = document.getElementById("fontSizeRange"); if (fsr) fsr.value = state.fontSize;
      const fsv = document.getElementById("fontSizeValue"); if (fsv) fsv.textContent = state.fontSize;
      const mks = document.getElementById("manageKeyStatus"); if (mks) mks.textContent = "";
      applyProfileGlobal();
      renderProviderGrid();
      const mb = document.getElementById("modalBg"); if (mb) mb.classList.add("open");
    });

    // Index tabs
    document.querySelectorAll("#indexTabs .tab").forEach(t => {
      t.addEventListener("click", () => {
        document.querySelectorAll("#indexTabs .tab").forEach(x => x.classList.remove("active"));
        t.classList.add("active");
        if (typeof renderIndexSheet === "function") renderIndexSheet(t.dataset.indexTab);
      });
    });
    document.querySelectorAll("#exchangeTabs .tab").forEach(t => {
      t.addEventListener("click", () => {
        document.querySelectorAll("#exchangeTabs .tab").forEach(x => x.classList.remove("active"));
        t.classList.add("active");
        state.exchangeTab = t.dataset.exchangeTab;
        if (typeof renderExchange === "function") renderExchange();
      });
    });

    // Меню — переходы
    const on = (id, fn) => { const el = document.getElementById(id); if (el) el.addEventListener("click", fn); };
    on("menuNewChat", async () => {
      closeAllSheets();
      const fresh = createChatObj("Новый чат");
      await dbPut(STORE_CHATS, fresh);
      state.chats.push(fresh);
      if (typeof switchChat === "function") await switchChat(fresh.id);
    });
    on("menuLots", () => { closeAllSheets(); setTimeout(() => { if (typeof renderLotsList === "function") renderLotsList(); openSheet("lotsSheet"); }, 200); });
    on("menuIdeas", () => { closeAllSheets(); setTimeout(() => { if (typeof renderIdeasList === "function") renderIdeasList(); openSheet("ideasSheet"); }, 200); });
    on("menuDocuments", () => { closeAllSheets(); setTimeout(() => { if (typeof renderDocumentsList === "function") renderDocumentsList(); openSheet("documentsSheet"); }, 200); });
    on("menuChats", () => { closeAllSheets(); setTimeout(() => { if (typeof renderChatsList === "function") renderChatsList(); openSheet("chatsSheet"); }, 200); });
    on("menuImportant", () => { closeAllSheets(); setTimeout(() => { if (typeof renderImportantList === "function") renderImportantList(); openSheet("importantSheet"); }, 200); });
    on("menuExchange", async () => { closeAllSheets(); if (typeof loadExchange === "function") await loadExchange(); setTimeout(() => { if (typeof renderExchange === "function") renderExchange(); openSheet("exchangeSheet"); }, 200); });
    on("menuMyTemplates", () => { closeAllSheets(); setTimeout(() => { if (typeof renderMyTemplates === "function") renderMyTemplates(); openSheet("myTemplatesSheet"); }, 200); });
    on("menuMyPublic", async () => { closeAllSheets(); if (typeof loadExchange === "function") await loadExchange(); setTimeout(() => { if (typeof renderMyPublic === "function") renderMyPublic(); openSheet("myPublicSheet"); }, 200); });
    on("menuDashboard", () => { closeAllSheets(); setTimeout(async () => { if (typeof renderDashboard === "function") await renderDashboard(); openSheet("dashboardSheet"); }, 200); });
    on("menuManagement", () => { closeAllSheets(); setTimeout(async () => { if (typeof renderManagement === "function") await renderManagement(); openSheet("managementSheet"); }, 200); });
    on("menuBlog", () => { closeAllSheets(); setTimeout(() => {
      if (typeof updateMenu === "function") updateMenu();
      const box = document.getElementById("blogList");
      if (box) box.innerHTML = '<div class="empty-note">Блог появится здесь. Публикация доступна с ключом автора.</div>';
      openSheet("blogSheet");
    }, 200); });
    on("menuAbout", () => { closeAllSheets(); setTimeout(() => { if (typeof renderAbout === "function") renderAbout(); openSheet("aboutSheet"); }, 200); });
    on("menuBusiness", () => { closeAllSheets(); setTimeout(() => { if (typeof renderBusiness === "function") renderBusiness(); openSheet("businessSheet"); }, 200); });

    // Управление из сферы
    on("orbManageCode", () => {
      closeAllSheets();
      setTimeout(() => {
        const cpi = document.getElementById("codePathInput"); if (cpi) cpi.value = "";
        const cps = document.getElementById("codePathStatus"); if (cps) cps.textContent = "";
        const cpm = document.getElementById("codePathModalBg"); if (cpm) cpm.classList.add("open");
      }, 200);
    });
    on("orbManageRelease", () => {
      closeAllSheets();
      setTimeout(() => { if (typeof renderReleasesList === "function") renderReleasesList(); openSheet("releasesSheet"); }, 200);
    });
    on("orbManageDevReport", () => {
      closeAllSheets();
      setTimeout(async () => { if (typeof renderDevReport === "function") await renderDevReport(); openSheet("devReportSheet"); }, 200);
    });

    // Lots tabs
    document.querySelectorAll("#lotsTabs .tab").forEach(t => {
      t.addEventListener("click", () => {
        document.querySelectorAll("#lotsTabs .tab").forEach(x => x.classList.remove("active"));
        t.classList.add("active");
        const ap = document.getElementById("lotsActivePane");
        const rp = document.getElementById("lotsArchivePane");
        if (ap) ap.style.display = t.dataset.tab === "active" ? "block" : "none";
        if (rp) rp.style.display = t.dataset.tab === "archive" ? "block" : "none";
      });
    });
    on("lotsAddBtn", () => { closeAllSheets(); setTimeout(() => { if (typeof openLotModal === "function") openLotModal(null); }, 200); });

    // Модалка лота
    on("lotModalClose", closeAllSheets);
    on("lotCancel", closeAllSheets);
    const lotMb = document.getElementById("lotModalBg");
    if (lotMb) lotMb.addEventListener("click", (e) => { if (e.target === e.currentTarget) closeAllSheets(); });
    on("lotSave", () => { if (typeof saveLot === "function") saveLot(); });
    on("lotDelete", () => { if (typeof deleteLot === "function") deleteLot(); });

    // Релиз
    on("releaseNewBtn", () => { if (typeof openReleaseModal === "function") openReleaseModal(); });
    on("releaseModalCancel", closeAllSheets);
    on("releasePublishBtn", () => { if (typeof publishRelease === "function") publishRelease(); });

    // Публикация
    on("publishModalClose", closeAllSheets);
    on("publishCancel", closeAllSheets);
    const pmb = document.getElementById("publishModalBg");
    if (pmb) pmb.addEventListener("click", (e) => { if (e.target === e.currentTarget) closeAllSheets(); });
    on("publishConfirm", () => { if (typeof confirmPublish === "function") confirmPublish(); });

    // Код
    on("codePathClose", closeAllSheets);
    on("codePathCancel", closeAllSheets);
    const cpm = document.getElementById("codePathModalBg");
    if (cpm) cpm.addEventListener("click", (e) => { if (e.target === e.currentTarget) closeAllSheets(); });
    on("codePathOpen", async () => {
      const path = (document.getElementById("codePathInput").value || "").trim();
      const status = document.getElementById("codePathStatus");
      if (!path) { status.textContent = "Введите путь"; return; }
      if (!state.authorKey) { status.textContent = "Введите ключ автора"; return; }
      status.textContent = "Загружаю...";
      try {
        const r = await fetch(API_BASE + "/code/read?path=" + encodeURIComponent(path), {
          headers: { "X-Author-Key": state.authorKey },
        });
        const data = await r.json();
        if (!r.ok) throw new Error(data.detail || ("HTTP " + r.status));
        if (!data.exists) status.textContent = "Файл не найден.";
        else { closeAllSheets(); if (typeof openEditor === "function") openEditor({ type: "code", name: path, body: data.content || "", path: path }); }
      } catch (e) { status.textContent = "Ошибка: " + e.message; }
    });

    // Настройки
    on("modalClose", closeAllSheets);
    const mbg = document.getElementById("modalBg");
    if (mbg) mbg.addEventListener("click", (e) => { if (e.target === e.currentTarget) closeAllSheets(); });
    document.querySelectorAll("#depthSeg button").forEach(el => {
      el.addEventListener("click", () => { state.depthMode = el.dataset.depth; applyProfileGlobal(); });
    });
    const fsr = document.getElementById("fontSizeRange");
    if (fsr) fsr.addEventListener("input", (e) => {
      const size = parseInt(e.target.value, 10);
      state.fontSize = size;
      const fsv = document.getElementById("fontSizeValue");
      if (fsv) fsv.textContent = size;
      applyFontSize();
    });
    on("saveSettings", () => {
      state.apiKey = (document.getElementById("keyInput").value || "").trim();
      state.manageKey = (document.getElementById("manageKeyInput").value || "").trim();
      state.authorKey = (document.getElementById("authorKeyInput").value || "").trim();
      if (document.getElementById("rememberKey").checked && state.apiKey) localStorage.setItem(LS_KEY, state.apiKey);
      else if (!document.getElementById("rememberKey").checked) localStorage.removeItem(LS_KEY);
      if (document.getElementById("rememberManageKey").checked && state.manageKey) localStorage.setItem(LS_MANAGE, state.manageKey);
      else if (!document.getElementById("rememberManageKey").checked) localStorage.removeItem(LS_MANAGE);
      if (document.getElementById("rememberAuthorKey").checked && state.authorKey) localStorage.setItem(LS_AUTHOR, state.authorKey);
      else if (!document.getElementById("rememberAuthorKey").checked) localStorage.removeItem(LS_AUTHOR);
      try {
        localStorage.setItem(LS_PROVIDER, state.provider);
        localStorage.setItem(LS_FONT, String(state.fontSize));
        localStorage.setItem(LS_DEPTH, state.depthMode);
      } catch (e) {}
      if (typeof updateMenu === "function") updateMenu();
      closeAllSheets();
      broadcast("settings_updated", {});
      toast("Настройки сохранены");
    });
    on("exportData", () => {
      const blob = new Blob([JSON.stringify({ lots: state.lots, chats: state.chats, releases: state.releases, notifications: state.notifications, balance: state.balance }, null, 2)], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "monolog_export_" + Date.now() + ".json";
      a.click();
      URL.revokeObjectURL(a.href);
    });
    on("importData", () => { const f = document.getElementById("importFile"); if (f) f.click(); });
    const ifile = document.getElementById("importFile");
    if (ifile) ifile.addEventListener("change", (e) => {
      const file = e.target.files && e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = async () => {
        try {
          const data = JSON.parse(reader.result);
          if (Array.isArray(data.lots)) for (const l of data.lots) await dbPut(STORE_LOTS, l);
          if (Array.isArray(data.chats)) for (const c of data.chats) await dbPut(STORE_CHATS, c);
          if (Array.isArray(data.releases)) for (const r of data.releases) await dbPut(STORE_RELEASES, r);
          if (typeof data.balance === "number") { state.balance = data.balance; await dbSetMeta("balance", state.balance); }
          location.reload();
        } catch (err) { alert("Некорректный файл"); }
      };
      reader.readAsText(file);
    });

    // Редактор
    on("editorCopyBtn", () => {
      const body = document.getElementById("editorBody").value || "";
      if (navigator.clipboard) navigator.clipboard.writeText(body);
      toast("Скопировано");
    });
    on("editorDownloadBtn", () => {
      const name = (document.getElementById("editorName").value || "document").trim();
      const body = document.getElementById("editorBody").value || "";
      const safe = name.replace(/[^\w\-а-яА-Я]+/gi, "_") || "document";
      const blob = new Blob([body], { type: "text/markdown;charset=utf-8" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = safe + ".md";
      a.click();
      URL.revokeObjectURL(a.href);
    });
    on("editorSaveBtn", () => { if (typeof saveEditorToLot === "function") saveEditorToLot(); });
    on("editorPublishPublicBtn", () => {
      const name = (document.getElementById("editorName").value || "").trim();
      const body = (document.getElementById("editorBody").value || "").trim();
      if (!name || !body) { toast("Нужны название и текст"); return; }
      if (typeof openPublishModal === "function") openPublishModal("template", { name, content: body, tags: [] });
    });
    on("editorPublishBlogBtn", async () => {
      const title = (document.getElementById("editorName").value || "").trim();
      const body = (document.getElementById("editorBody").value || "").trim();
      const status = document.getElementById("editorStatus");
      if (!title || !body) { status.textContent = "Нужны заголовок и текст"; return; }
      if (!state.authorKey) { status.textContent = "Введите ключ автора"; return; }
      status.textContent = "Публикую...";
      try {
        const r = await fetch(API_BASE + "/blog/publish", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-Author-Key": state.authorKey },
          body: JSON.stringify({ title, body, tags: [], author: "Автор" }),
        });
        const data = await r.json();
        if (!r.ok) throw new Error(data.detail || ("HTTP " + r.status));
        status.textContent = "Опубликовано";
        toast("Опубликовано");
        setTimeout(() => closeAllSheets(), 700);
      } catch (e) { status.textContent = "Ошибка: " + e.message; }
    });
    on("editorCodeSave", async () => {
      const ctx = state.editorContext || {};
      const path = ctx.path || (document.getElementById("editorName").value || "").trim();
      const body = document.getElementById("editorBody").value || "";
      const status = document.getElementById("editorStatus");
      if (!path || !body) { status.textContent = "Нужен путь и текст"; return; }
      if (!state.authorKey) { status.textContent = "Введите ключ автора"; return; }
      status.textContent = "Сохраняю...";
      try {
        const r = await fetch(API_BASE + "/code/save", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-Author-Key": state.authorKey },
          body: JSON.stringify({ path, content: body, message: "Update " + path }),
        });
        const data = await r.json();
        if (!r.ok) throw new Error(data.detail || ("HTTP " + r.status));
        status.textContent = "Сохранено в dev";
      } catch (e) { status.textContent = "Ошибка: " + e.message; }
    });

    // Документы — создать
    on("documentsAddBtn", () => {
      closeAllSheets();
      setTimeout(() => {
        const c = currentChat();
        if (typeof openEditor === "function") openEditor({ type: "document", lotId: c && c.lotId, name: "", body: "" });
      }, 200);
    });

    // Поле ввода
    const sendBtn = document.getElementById("sendBtn");
    const input = document.getElementById("input");
    const fileInput = document.getElementById("fileInput");
    if (sendBtn) sendBtn.addEventListener("click", send);
    if (input) {
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
      });
      input.addEventListener("input", () => {
        input.style.height = "auto";
        const sh = input.scrollHeight;
        const maxH = 120;
        input.style.height = Math.min(sh, maxH) + "px";
        input.style.overflowY = sh > maxH ? "auto" : "hidden";
        updateCharCounter();
      });
      setInterval(() => {
        state.placeholderIndex = (state.placeholderIndex + 1) % 4;
        if (!input.value) input.placeholder = ["Коротко — Monolog достроит", "Что сейчас важнее всего?", "Опишите задачу — одним предложением", "Над чем работаете?"][state.placeholderIndex];
      }, 8000);
    }
    const attachBtn = document.getElementById("attachBtn");
    if (attachBtn) attachBtn.addEventListener("click", () => { if (fileInput) fileInput.click(); });
    if (fileInput) fileInput.addEventListener("change", (e) => { handleFiles(e.target.files); fileInput.value = ""; });

    // Закрытие шторок
    const sbg = document.getElementById("sheetBg");
    if (sbg) sbg.addEventListener("click", closeAllSheets);
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeAllSheets(); });
    setupEyeButtons();

    if (window.visualViewport) {
      const setVh = () => { document.documentElement.style.setProperty("--vh", window.visualViewport.height + "px"); };
      window.visualViewport.addEventListener("resize", setVh);
      window.visualViewport.addEventListener("scroll", setVh);
      setVh();
    }

    if (_bc) {
      _bc.addEventListener("message", async (e) => {
        const msg = e.data || {};
        if (["chat_updated", "lots_updated", "settings_updated", "reset", "notif_added", "releases_updated"].indexOf(msg.type) !== -1) {
          state.lots = await dbGetAll(STORE_LOTS);
          state.chats = await dbGetAll(STORE_CHATS);
          state.releases = await dbGetAll(STORE_RELEASES);
          state.notifications = await dbGetAll(STORE_NOTIFICATIONS);
          const bal = await dbGetMeta("balance");
          if (typeof bal === "number") state.balance = bal;
          renderCurrentChat();
          if (typeof updateMenu === "function") updateMenu();
          if (typeof updateIndexBtn === "function") updateIndexBtn();
          if (typeof updateHeaderDynamic === "function") updateHeaderDynamic();
          if (document.getElementById("notificationsSheet").classList.contains("open") && typeof renderNotificationsList === "function") renderNotificationsList();
        }
      });
    }

    setInterval(async () => {
      const lots = await dbGetAll(STORE_LOTS);
      const chats = await dbGetAll(STORE_CHATS);
      const releases = await dbGetAll(STORE_RELEASES);
      const notifs = await dbGetAll(STORE_NOTIFICATIONS);
      const bal = await dbGetMeta("balance");
      const changed = JSON.stringify(lots.length + ":" + chats.length + ":" + releases.length + ":" + notifs.length + ":" + (bal || 0)) !== JSON.stringify(state.lots.length + ":" + state.chats.length + ":" + state.releases.length + ":" + state.notifications.length + ":" + (state.balance || 0));
      if (changed) {
        state.lots = lots;
        state.chats = chats;
        state.releases = releases;
        state.notifications = notifs;
        if (typeof bal === "number") state.balance = bal;
        renderCurrentChat();
        if (typeof updateMenu === "function") updateMenu();
        if (typeof updateIndexBtn === "function") updateIndexBtn();
        if (typeof updateHeaderDynamic === "function") updateHeaderDynamic();
      }
    }, 4000);

    try {
      const r = await fetch(API_BASE + "/providers");
      if (r.ok) {
        const data = await r.json();
        if (data.providers && data.providers.length) state.providersCache = data.providers;
      }
    } catch (e) {}

    if (typeof loadExchange === "function") loadExchange();

    // Экспорт ядра
    window.MonologCore = {
      state,
      API_BASE,
      uid,
      escHtml,
      pluralize,
      toast,
      renderMarkdown,
      softenText,
      broadcast,
      openDB,
      dbGetAll,
      dbPut,
      dbDel,
      dbGetMeta,
      dbSetMeta,
      applyTheme,
      applyFontSize,
      applyProfile: applyProfileGlobal,
      currentChat,
      currentLot,
      addRow,
      renderCurrentChat,
      send,
      createChatObj,
      createLotObj,
      persistChat,
      persistLot,
      loadData,
      updateCharCounter,
      renderAttachPreview,
      handleFiles,
      renderProviderGrid,
      setupEyeButtons,
      openSheet,
      closeAllSheets,
      setupSwipeToClose,
      init,
      STORE_LOTS,
      STORE_CHATS,
      STORE_RELEASES,
      STORE_ANALYTICS,
      STORE_NOTIFICATIONS,
      STORE_PUBLIC,
      STORE_META,
      LS_KEY,
      LS_AUTHOR,
      LS_MANAGE,
      LS_PROVIDER,
      LS_FONT,
      LS_DEPTH,
      LS_MODE,
      LS_UID,
      LS_NOTIF_SEEN,
      SOFT_LIMIT,
      HARD_LIMIT,
      MODE_LABELS,
      PROVIDERS_FALLBACK,
    };

  } catch (e) {
    console.error("core init error", e);
    const chat = document.getElementById("chat");
    if (chat) chat.innerHTML = '<div class="empty-note" style="padding:20px;">Ошибка запуска: ' + escHtml(e.message || String(e)) + '</div>';
    const sp = document.getElementById("splash");
    if (sp) sp.classList.add("hide");
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
