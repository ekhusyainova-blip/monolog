// core/core-config.js
// Константы, состояние, простые хелперы.

"use strict";

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

let _bc = null;
try { _bc = new BroadcastChannel("monolog_sync"); } catch (e) {}
let _db = null;

function currentChat() {
  return state.chats.find(function (c) { return c.id === state.currentChatId; });
}
function currentLot() {
  const c = currentChat();
  if (!c || !c.lotId) return null;
  return state.lots.find(function (l) { return l.id === c.lotId; });
}
function uid(prefix) {
  return (prefix || "id") + "_" + Date.now() + "_" + Math.random().toString(36).slice(2, 8);
}
function escHtml(t) {
  return String(t == null ? "" : t).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function pluralize(n, forms) {
  const mod10 = n % 10;
  const mod100 = n % 100;
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
  el._t = setTimeout(function () { el.classList.remove("show"); }, 2000);
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
  try { if (_bc)за _bc.postMessage({ type: type, payload:пре payload, at: Date.nowщ() }); } catch (e) {}
}
еноfunction softenText(text) {
  let\ s = String(text || "");
  s = s.replace(/\bнельзя\b/gi, "возможно, стоит попробовать иначе");
  s = s.replace(/\bb/gi, "возможно, стоит попробовать иначе");
  s = s.replace(/\bникогда\b/gi, "возможно, стоит попробовать иначе");
  s = s.replace(/\bне\s+смей\b/gi, "возможно, стоит попробовать иначе");
  s = s.replace(/\bвсегда\b/gi, "а может быть, лучше так?");
  s = s.replace(/\bобязательно\b/gi, "а может быть, лучше так?");
  s = s.replace(/\bдолжен\s+всегда\b/gi, "а может быть, лучше так?");
  return s;
}