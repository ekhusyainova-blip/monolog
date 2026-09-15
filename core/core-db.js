// core/core-db.js
// IndexedDB + тема + шрифт.

"use strict";

function openDB() {
  return new Promise(function (resolve, reject) {
    if (_db) return resolve(_db);
    try {
      const req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = function (e) {
        const db = e.target.result;
        if (!db.objectStoreNames.contains(STORE_LOTS)) db.createObjectStore(STORE_LOTS, { keyPath: "id" });
        if (!db.objectStoreNames.contains(STORE_CHATS)) db.createObjectStore(STORE_CHATS, { keyPath: "id" });
        if (!db.objectStoreNames.contains(STORE_RELEASES)) db.createObjectStore(STORE_RELEASES, { keyPath: "id" });
        if (!db.objectStoreNames.contains(STORE_ANALYTICS)) db.createObjectStore(STORE_ANALYTICS, { keyPath: "id" });
        if (!db.objectStoreNames.contains(STORE_NOTIFICATIONS)) db.createObjectStore(STORE_NOTIFICATIONS, { keyPath: "id" });
        if (!db.objectStoreNames.contains(STORE_PUBLIC)) db.createObjectStore(STORE_PUBLIC, { keyPath: "id" });
        if (!db.objectStoreNames.contains(STORE_META)) db.createObjectStore(STORE_META);
      };
      req.onsuccess = function (e) { _db = e.target.result; resolve(_db); };
      req.onerror = function () { reject(req.error); };
    } catch (e) { reject(e); }
  });
}

async function dbGetAll(store) {
  try {
    const db = await openDB();
    return new Promise(function (resolve) {
      const tx = db.transaction(store, "readonly");
      const req = tx.objectStore(store).getAll();
      req.onsuccess = function () { resolve(req.result || []); };
      req.onerror = function () { resolve([]); };
    });
  } catch (e) { return []; }
}

async function dbPut(store, val) {
  try {
    const db = await openDB();
    return new Promise(function (resolve) {
      const tx = db.transaction(store, "readwrite");
      tx.objectStore(store).put(val);
      tx.oncomplete = function () { resolve(true); };
      tx.onerror = function () { resolve(false); };
    });
  } catch (e) { return false; }
}

async function dbDel(store, key) {
  try {
    const db = await openDB();
    return new Promise(function (resolve) {
      const tx = db.transaction(store, "readwrite");
      tx.objectStore(store).delete(key);
      tx.oncomplete = function () { resolve(true); };
    });
  } catch (e) { return false; }
}

async function dbGetMeta(key) {
  try {
    const db = await openDB();
    return new Promise(function (resolve) {
      const tx = db.transaction(STORE_META, "readonly");
      const req = tx.objectStore(STORE_META).get(key);
      req.onsuccess = function () { resolve(req.result); };
      req.onerror = function () { resolve(null); };
    });
  } catch (e) { return null; }
}

async function dbSetMeta(key, val) {
  try {
    const db = await openDB();
    return new Promise(function (resolve) {
      const tx = db.transaction(STORE_META, "readwrite");
      tx.objectStore(STORE_META).put(val, key);
      tx.oncomplete = function () { resolve(true); };
    });
  } catch (e) { return false; }
}

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

function applyProfileGlobal() {
  document.querySelectorAll("#depthSeg button").forEach(function (el) {
    el.classList.toggle("active", el.dataset.depth === state.depthMode);
  });
  applyTheme();
  applyFontSize();
}