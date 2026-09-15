// core/core-init.js
// Провайдеры, шторки, экспорт ядра, обработчики, init.

"use strict";

function renderProviderGrid() {
  const grid = document.getElementById("providerGrid");
  if (!grid) return;
  grid.innerHTML = "";
  state.providersCache.forEach(function (pr) {
    const btn = document.createElement("button");
    btn.className = "provider-btn" + (state.provider === pr.id ? " active" : "");
    btn.type = "button";
    btn.innerHTML = '<span class="name">' + escHtml(pr.name) + '</span>';
    btn.addEventListener("click", function () {
      state.provider = pr.id;
      try { localStorage.setItem(LS_PROVIDER, pr.id); } catch (e) {}
      renderProviderGrid();
    });
    grid.appendChild(btn);
  });
}

function setupEyeButtons() {
  document.querySelectorAll(".eye-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
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

function openSheet(id) {
  const bg = document.getElementById("sheetBg");
  if (bg) bg.classList.add("open");
  const el = document.getElementById(id);
  if (el) el.classList.add("open");
}

function closeAllSheets() {
  const bg = document.getElementById("sheetBg");
  if (bg) bg.classList.remove("open");
  document.querySelectorAll(".sheet").forEach(function (s) { s.classList.remove("open"); });
  document.querySelectorAll(".modal-bg").forEach(function (m) { m.classList.remove("open"); });
}

function setupSwipeToClose(sheetEl, handleEl) {
  if (!sheetEl || !handleEl) return;
  let startY = 0, currentY = 0, dragging = false;
  function onStart(e) {
    dragging = true;
    startY = (e.touches ? e.touches[0].clientY : e.clientY);
    sheetEl.style.transition = "none";
  }
  function onMove(e) {
    if (!dragging) return;
    currentY = (e.touches ? e.touches[0].clientY : e.clientY);
    const dy = Math.max(0, currentY - startY);
    sheetEl.style.transform = "translateY(" + dy + "px)";
  }
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

// --- Экспорт ядра ---
window.MonologCore = {
  state: state,
  API_BASE: API_BASE,
  uid: uid,
  escHtml: escHtml,
  pluralize: pluralize,
  toast: toast,
  renderMarkdown: renderMarkdown,
  softenText: softenText,
  broadcast: broadcast,
  openDB: openDB,
  dbGetAll: dbGetAll,
  dbPut: dbPut,
  dbDel: dbDel,
  dbGetMeta: dbGetMeta,
  dbSetMeta: dbSetMeta,
  applyTheme: applyTheme,
  applyFontSize: applyFontSize,
  applyProfile: applyProfileGlobal,
  currentChat: currentChat,
  currentLot: currentLot,
  addRow: addRow,
  renderCurrentChat: renderCurrentChat,
  send: send,
  createChatObj: createChatObj,
  createLotObj: createLotObj,
  persistChat: persistChat,
  persistLot: persistLot,
  loadData: loadData,
  updateCharCounter: updateCharCounter,
  renderAttachPreview: renderAttachPreview,
  handleFiles: handleFiles,
  renderProviderGrid: renderProviderGrid,
  setupEyeButtons: setupEyeButtons,
  openSheet: openSheet,
  closeAllSheets: closeAllSheets,
  setupSwipeToClose: setupSwipeToClose,
  STORE_LOTS: STORE_LOTS,
  STORE_CHATS: STORE_CHATS,
  STORE_RELEASES: STORE_RELEASES,
  STORE_ANALYTICS: STORE_ANALYTICS,
  STORE_NOTIFICATIONS: STORE_NOTIFICATIONS,
  STORE_PUBLIC: STORE_PUBLIC,
  STORE_META: STORE_META,
  LS_KEY: LS_KEY,
  LS_AUTHOR: LS_AUTHOR,
  LS_MANAGE: LS_MANAGE,
  LS_PROVIDER: LS_PROVIDER,
  LS_FONT: LS_FONT,
  LS_DEPTH: LS_DEPTH,
  LS_MODE: LS_MODE,
  LS_UID: LS_UID,
  LS_NOTIF_SEEN: LS_NOTIF_SEEN,
  SOFT_LIMIT: SOFT_LIMIT,
  HARD_LIMIT: HARD_LIMIT,
  MODE_LABELS: MODE_LABELS,
  PROVIDERS_FALLBACK: PROVIDERS_FALLBACK,
};

// --- Init ---
async function init() {
  setTimeout(function () {
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
      if (!state.uid) {
        state.uid = "u_" + Date.now() + "_" + Math.random().toString(36).slice(2, 8);
        localStorage.setItem(LS_UID, state.uid);
      }
    } catch (e) {}

    applyProfileGlobal();
    document.documentElement.setAttribute("data-mode", state.mode);

    await loadData();
    renderCurrentChat();

    [
      "orbSheet", "menuSheet", "indexSheet", "profileSheet", "metricsSheet",
      "notificationsSheet", "exchangeSheet", "myTemplatesSheet", "myPublicSheet",
      "lotsSheet", "lotCardSheet", "mapSheet", "ideasSheet", "importantSheet",
      "dashboardSheet", "managementSheet", "releasesSheet", "releaseModalSheet",
      "devReportSheet", "documentsSheet", "chatsSheet", "blogSheet",
      "aboutSheet", "businessSheet", "editorSheet"
    ].forEach(function (id) {
      const s = document.getElementById(id);
      const h = s ? s.querySelector(".sheet-handle") : null;
      if (s && h) setupSwipeToClose(s, h);
    });

    // Сфера
    const orbBtn = document.getElementById("orbBtn");
    if (orbBtn) {
      let orbPressTimer = null;
      let orbMoved = false;
      orbBtn.addEventListener("pointerdown", function () {
        orbMoved = false;
        orbPressTimer = setTimeout(function () {
          orbPressTimer = null;
          if (window.MonologAdaptive && window.MonologAdaptive.switchMode) window.MonologAdaptive.switchMode();
        }, 550);
      });
      orbBtn.addEventListener("pointermove", function () {
        orbMoved = true;
        if (orbPressTimer) { clearTimeout(orbPressTimer); orbPressTimer = null; }
      });
      ["pointerup", "pointerleave", "pointercancel"].forEach(function (ev) {
        orbBtn.addEventListener(ev, function () {
          if (orbPressTimer) { clearTimeout(orbPressTimer); orbPressTimer = null; }
          if (!orbMoved && ev === "pointerup") {
            if (window.MonologAdaptive && window.MonologAdaptive.renderOrbSheet) window.MonologAdaptive.renderOrbSheet();
            openSheet("orbSheet");
          }
        });
      });
    }

    // Header кнопки
    const indexBtn = document.getElementById("indexBtn");
    if (indexBtn) indexBtn.addEventListener("click", function () {
      if (window.MonologAdaptive && window.MonologAdaptive.renderIndexSheet) window.MonologAdaptive.renderIndexSheet("all");
      openSheet("indexSheet");
    });
    const metricsBtn = document.getElementById("metricsBtn");
    if (metricsBtn) metricsBtn.addEventListener("click", function () {
      if (window.MonologAdaptive && window.MonologAdaptive.renderMetricsSheet) window.MonologAdaptive.renderMetricsSheet();
      openSheet("metricsSheet");
    });
    const exchangeBtn = document.getElementById("exchangeBtn");
    if (exchangeBtn) exchangeBtn.addEventListener("click", async function () {
      if (window.MonologAdaptive && window.MonologAdaptive.loadExchange) await window.MonologAdaptive.loadExchange();
      if (window.MonologAdaptive && window.MonologAdaptive.renderExchange) window.MonologAdaptive.renderExchange();
      openSheet("exchangeSheet");
    });
    const notifBtn = document.getElementById("notifBtn");
    if (notifBtn) notifBtn.addEventListener("click", function () {
      if (window.MonologAdaptive && window.MonologAdaptive.renderNotificationsList) window.MonologAdaptive.renderNotificationsList();
      openSheet("notificationsSheet");
      setTimeout(function () {
        if (window.MonologAdaptive && window.MonologAdaptive.markNotificationsSeen) window.MonologAdaptive.markNotificationsSeen();
      }, 800);
    });
    const profileBtn = document.getElementById("profileBtn");
    if (profileBtn) profileBtn.addEventListener("click", function () {
      if (window.MonologAdaptive && window.MonologAdaptive.renderProfile) window.MonologAdaptive.renderProfile();
      openSheet("profileSheet");
    });
    const menuBtn = document.getElementById("menuBtn");
    if (menuBtn) menuBtn.addEventListener("click", function () {
      if (window.MonologAdaptive && window.MonologAdaptive.updateMenu) window.MonologAdaptive.updateMenu();
      openSheet("menuSheet");
    });
    const settingsBtn = document.getElementById("settingsBtn");
    if (settingsBtn) settingsBtn.addEventListener("click", function () {
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

    // Табы
    document.querySelectorAll("#indexTabs .tab").forEach(function (t) {
      t.addEventListener("click", function () {
        document.querySelectorAll("#indexTabs .tab").forEach(function (x) { x.classList.remove("active"); });
        t.classList.add("active");
        if (window.MonologAdaptive && window.MonologAdaptive.renderIndexSheet) window.MonologAdaptive.renderIndexSheet(t.dataset.indexTab);
      });
    });
    document.querySelectorAll("#exchangeTabs .tab").forEach(function (t) {
      t.addEventListener("click", function () {
        document.querySelectorAll("#exchangeTabs .tab").forEach(function (x) { x.classList.remove("active"); });
        t.classList.add("active");
        state.exchangeTab = t.dataset.exchangeTab;
        if (window.MonologAdaptive && window.MonologAdaptive.renderExchange) window.MonologAdaptive.renderExchange();
      });
    });

    // Меню
    const on = function (id, fn) { const el = document.getElementById(id); if (el) el.addEventListener("click", fn); };
    on("menuNewChat", async function () {
      closeAllSheets();
      const fresh = createChatObj("Новый чат");
      await dbPut(STORE_CHATS, fresh);
      state.chats.push(fresh);
      if (window.MonologAdaptive && window.MonologAdaptive.switchChat) await window.MonologAdaptive.switchChat(fresh.id);
    });
    on("menuLots", function () { closeAllSheets(); setTimeout(function () { if (window.MonologAdaptive && window.MonologAdaptive.renderLotsList) window.MonologAdaptive.renderLotsList(); openSheet("lotsSheet"); }, 200); });
    on("menuIdeas", function () { closeAllSheets(); setTimeout(function () { if (window.MonologAdaptive && window.MonologAdaptive.renderIdeasList) window.MonologAdaptive.renderIdeasList(); openSheet("ideasSheet"); }, 200); });
    on("menuDocuments", function () { closeAllSheets(); setTimeout(function () { if (window.MonologAdaptive && window.MonologAdaptive.renderDocumentsList) window.MonologAdaptive.renderDocumentsList(); openSheet("documentsSheet"); }, 200); });
    on("menuChats", function () { closeAllSheets(); setTimeout(function () { if (window.MonologAdaptive && window.MonologAdaptive.renderChatsList) window.MonologAdaptive.renderChatsList(); openSheet("chatsSheet"); }, 200); });
    on("menuImportant", function () { closeAllSheets(); setTimeout(function () { if (window.MonologAdaptive && window.MonologAdaptive.renderImportantList) window.MonologAdaptive.renderImportantList(); openSheet("importantSheet"); }, 200); });
    on("menuExchange", async function () { closeAllSheets(); if (window.MonologAdaptive && window.MonologAdaptive.loadExchange) await window.MonologAdaptive.loadExchange(); setTimeout(function () { if (window.MonologAdaptive && window.MonologAdaptive.renderExchange) window.MonologAdaptive.renderExchange(); openSheet("exchangeSheet"); }, 200); });
    on("menuMyTemplates", function () { closeAllSheets(); setTimeout(function () { if (window.MonologAdaptive && window.MonologAdaptive.renderMyTemplates) window.MonologAdaptive.renderMyTemplates(); openSheet("myTemplatesSheet"); }, 200); });
    on("menuMyPublic", async function () { closeAllSheets(); if (window.MonologAdaptive && window.MonologAdaptive.loadExchange) await window.MonologAdaptive.loadExchange(); setTimeout(function () { if (window.MonologAdaptive && window.MonologAdaptive.renderMyPublic) window.MonologAdaptive.renderMyPublic(); openSheet("myPublicSheet"); }, 200); });
    on("menuDashboard", function () { closeAllSheets(); setTimeout(async function () { if (window.MonologAdaptive && window.MonologAdaptive.renderDashboard) await window.MonologAdaptive.renderDashboard(); openSheet("dashboardSheet"); }, 200); });
    on("menuManagement", function () { closeAllSheets(); setTimeout(async function () { if (window.MonologAdaptive && window.MonologAdaptive.renderManagement) await window.MonologAdaptive.renderManagement(); openSheet("managementSheet"); }, 200); });
    on("menuBlog", function () { closeAllSheets(); setTimeout(function () {
      if (window.MonologAdaptive && window.MonologAdaptive.updateMenu) window.MonologAdaptive.updateMenu();
      const box = document.getElementById("blogList");
      if (box) box.innerHTML = '<div class="empty-note">Блог появится здесь. Публикация доступна с ключом автора.</div>';
      openSheet("blogSheet");
    }, 200); });
    on("menuAbout", function () { closeAllSheets(); setTimeout(function () { if (window.MonologAdaptive && window.MonologAdaptive.renderAbout) window.MonologAdaptive.renderAbout(); openSheet("aboutSheet"); }, 200); });
    on("menuBusiness", function () { closeAllSheets(); setTimeout(function () { if (window.MonologAdaptive && window.MonologAdaptive.renderBusiness) window.MonologAdaptive.renderBusiness(); openSheet("businessSheet"); }, 200); });

    on("orbManageCode", function () {
      closeAllSheets();
      setTimeout(function () {
        const cpi = document.getElementById("codePathInput"); if (cpi) cpi.value = "";
        const cps = document.getElementById("codePathStatus"); if (cps) cps.textContent = "";
        const cpm = document.getElementById("codePathModalBg"); if (cpm) cpm.classList.add("open");
      }, 200);
    });
    on("orbManageRelease", function () {
      closeAllSheets();
      setTimeout(function () { if (window.MonologAdaptive && window.MonologAdaptive.renderReleasesList) window.MonologAdaptive.renderReleasesList(); openSheet("releasesSheet"); }, 200);
    });
    on("orbManageDevReport", function () {
      closeAllSheets();
      setTimeout(async function () { if (window.MonologAdaptive && window.MonologAdaptive.renderDevReport) await window.MonologAdaptive.renderDevReport(); openSheet("devReportSheet"); }, 200);
    });

    document.querySelectorAll("#lotsTabs .tab").forEach(function (t) {
      t.addEventListener("click", function () {
        document.querySelectorAll("#lotsTabs .tab").forEach(function (x) { x.classList.remove("active"); });
        t.classList.add("active");
        const ap = document.getElementById("lotsActivePane");
        const rp = document.getElementById("lotsArchivePane");
        if (ap) ap.style.display = t.dataset.tab === "active" ? "block" : "none";
        if (rp) rp.style.display = t.dataset.tab === "archive" ? "block" : "none";
      });
    });
    on("lotsAddBtn", function () { closeAllSheets(); setTimeout(function () { if (window.MonologAdaptive && window.MonologAdaptive.openLotModal) window.MonologAdaptive.openLotModal(null); }, 200); });

    on("lotModalClose", closeAllSheets);
    on("lotCancel", closeAllSheets);
    const lotMb = document.getElementById("lotModalBg");
    if (lotMb) lotMb.addEventListener("click", function (e) { if (e.target === e.currentTarget) closeAllSheets(); });
    on("lotSave", function () { if (window.MonologAdaptive && window.MonologAdaptive.saveLot) window.MonologAdaptive.saveLot(); });
    on("lotDelete", function () { if (window.MonologAdaptive && window.MonologAdaptive.deleteLot) window.MonologAdaptive.deleteLot(); });

    on("releaseNewBtn", function () { if (window.MonologAdaptive && window.MonologAdaptive.openReleaseModal) window.MonologAdaptive.openReleaseModal(); });
    on("releaseModalCancel", closeAllSheets);
    on("releasePublishBtn", function () { if (window.MonologAdaptive && window.MonologAdaptive.publishRelease) window.MonologAdaptive.publishRelease(); });

    on("publishModalClose", closeAllSheets);
    on("publishCancel", closeAllSheets);
    const pmb = document.getElementById("publishModalBg");
    if (pmb) pmb.addEventListener("click", function (e) { if (e.target === e.currentTarget) closeAllSheets(); });
    on("publishConfirm", function () { if (window.MonologAdaptive && window.MonologAdaptive.confirmPublish) window.MonologAdaptive.confirmPublish(); });

    on("codePathClose", closeAllSheets);
    on("codePathCancel", closeAllSheets);
    const cpm = document.getElementById("codePathModalBg");
    if (cpm) cpm.addEventListener("click", function (e) { if (e.target === e.currentTarget) closeAllSheets(); });
    on("codePathOpen", async function () {
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
        else {
          closeAllSheets();
          if (window.MonologAdaptive && window.MonologAdaptive.openEditor) {
            window.MonologAdaptive.openEditor({ type: "code", name: path, body: data.content || "", path: path });
          }
        }
      } catch (e) { status.textContent = "Ошибка: " + e.message; }
    });

    on("modalClose", closeAllSheets);
    const mbg = document.getElementById("modalBg");
    if (mbg) mbg.addEventListener("click", function (e) { if (e.target === e.currentTarget) closeAllSheets(); });
    document.querySelectorAll("#depthSeg button").forEach(function (el) {
      el.addEventListener("click", function () { state.depthMode = el.dataset.depth; applyProfileGlobal(); });
    });
    const fsr = document.getElementById("fontSizeRange");
    if (fsr) fsr.addEventListener("input", function (e) {
      const size = parseInt(e.target.value, 10);
      state.fontSize = size;
      const fsv = document.getElementById("fontSizeValue");
      if (fsv) fsv.textContent = size;
      applyFontSize();
    });
    on("saveSettings", function () {
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
      if (window.MonologAdaptive && window.MonologAdaptive.updateMenu) window.MonologAdaptive.updateMenu();
      closeAllSheets();
      broadcast("settings_updated", {});
      toast("Настройки сохранены");
    });
    on("exportData", function () {
      const blob = new Blob([JSON.stringify({ lots: state.lots, chats: state.chats, releases: state.releases, notifications: state.notifications, balance: state.balance }, null, 2)], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "monolog_export_" + Date.now() + ".json";
      a.click();
      URL.revokeObjectURL(a.href);
    });
    on("importData", function () { const f = document.getElementById("importFile"); if (f) f.click(); });
    const ifile = document.getElementById("importFile");
    if (ifile) ifile.addEventListener("change", function (e) {
      const file = e.target.files && e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = async function () {
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

    on("editorCopyBtn", function () {
      const body = document.getElementById("editorBody").value || "";
      if (navigator.clipboard) navigator.clipboard.writeText(body);
      toast("Скопировано");
    });
    on("editorDownloadBtn", function () {
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
    on("editorSaveBtn", function () { if (window.MonologAdaptive && window.MonologAdaptive.saveEditorToLot) window.MonologAdaptive.saveEditorToLot(); });
    on("editorPublishPublicBtn", function () {
      const name = (document.getElementById("editorName").value || "").trim();
      const body = (document.getElementById("editorBody").value || "").trim();
      if (!name || !body) { toast("Нужны название и текст"); return; }
      if (window.MonologAdaptive && window.MonologAdaptive.openPublishModal) {
        window.MonologAdaptive.openPublishModal("template", { name: name, content: body, tags: [] });
      }
    });
    on("editorPublishBlogBtn", async function () {
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
          body: JSON.stringify({ title: title, body: body, tags: [], author: "Автор" }),
        });
        const data = await r.json();
        if (!r.ok) throw new Error(data.detail || ("HTTP " + r.status));
        status.textContent = "Опубликовано";
        toast("Опубликовано");
        setTimeout(function () { closeAllSheets(); }, 700);
      } catch (e) { status.textContent = "Ошибка: " + e.message; }
    });
    on("editorCodeSave", async function () {
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
          body: JSON.stringify({ path: path, content: body, message: "Update " + path }),
        });
        const data = await r.json();
        if (!r.ok) throw new Error(data.detail || ("HTTP " + r.status));
        status.textContent = "Сохранено в dev";
      } catch (e) { status.textContent = "Ошибка: " + e.message; }
    });

    on("documentsAddBtn", function () {
      closeAllSheets();
      setTimeout(function () {
        const c = currentChat();
        if (window.MonologAdaptive && window.MonologAdaptive.openEditor) {
          window.MonologAdaptive.openEditor({ type: "document", lotId: c && c.lotId, name: "", body: "" });
        }
      }, 200);
    });

    const sendBtn = document.getElementById("sendBtn");
    const input = document.getElementById("input");
    const fileInput = document.getElementById("fileInput");
    if (sendBtn) sendBtn.addEventListener("click", send);
    if (input) {
      input.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
      });
      input.addEventListener("input", function () {
        input.style.height = "auto";
        const sh = input.scrollHeight;
        const maxH = 120;
        input.style.height = Math.min(sh, maxH) + "px";
        input.style.overflowY = sh > maxH ? "auto" : "hidden";
        updateCharCounter();
      });
      setInterval(function () {
        state.placeholderIndex = (state.placeholderIndex + 1) % 4;
        if (!input.value) {
          input.placeholder = ["Коротко — Monolog достроит", "Что сейчас важнее всего?", "Опишите задачу — одним предложением", "Над чем работаете?"][state.placeholderIndex];
        }
      }, 8000);
    }
    const attachBtn = document.getElementById("attachBtn");
    if (attachBtn) attachBtn.addEventListener("click", function () { if (fileInput) fileInput.click(); });
    if (fileInput) fileInput.addEventListener("change", function (e) { handleFiles(e.target.files); fileInput.value = ""; });

    const sbg = document.getElementById("sheetBg");
    if (sbg) sbg.addEventListener("click", closeAllSheets);
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeAllSheets(); });
    setupEyeButtons();

    if (window.visualViewport) {
      const setVh = function () { document.documentElement.style.setProperty("--vh", window.visualViewport.height + "px"); };
      window.visualViewport.addEventListener("resize", setVh);
      window.visualViewport.addEventListener("scroll", setVh);
      setVh();
    }

    if (_bc) {
      _bc.addEventListener("message", async function (e) {
        const msg = e.data || {};
        if (["chat_updated", "lots_updated", "settings_updated", "reset", "notif_added", "releases_updated"].indexOf(msg.type) !== -1) {
          state.lots = await dbGetAll(STORE_LOTS);
          state.chats = await dbGetAll(STORE_CHATS);
          state.releases = await dbGetAll(STORE_RELEASES);
          state.notifications = await dbGetAll(STORE_NOTIFICATIONS);
          const bal = await dbGetMeta("balance");
          if (typeof bal === "number") state.balance = bal;
          renderCurrentChat();
          if (window.MonologAdaptive && window.MonologAdaptive.updateMenu) window.MonologAdaptive.updateMenu();
          if (window.MonologAdaptive && window.MonologAdaptive.updateIndexBtn) window.MonologAdaptive.updateIndexBtn();
          if (window.MonologAdaptive && window.MonologAdaptive.updateHeaderDynamic) window.MonologAdaptive.updateHeaderDynamic();
          const ns = document.getElementById("notificationsSheet");
          if (ns && ns.classList.contains("open") && window.MonologAdaptive && window.MonologAdaptive.renderNotificationsList) {
            window.MonologAdaptive.renderNotificationsList();
          }
        }
      });
    }

    setInterval(async function () {
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
        if (typeof window.MonologAdaptive !== "undefined" && window.MonologAdaptive.updateMenu) window.MonologAdaptive.updateMenu();
        if (typeof window.MonologAdaptive !== "undefined" && window.MonologAdaptive.updateIndexBtn) window.MonologAdaptive.updateIndexBtn();
        if (typeof window.MonologAdaptive !== "undefined" && window.MonologAdaptive.updateHeaderDynamic) window.MonologAdaptive.updateHeaderDynamic();
      }
    }, 4000);

    try {
      const r = await fetch(API_BASE + "/providers");
      if (r.ok) {
        const data = await r.json();
        if (data.providers && data.providers.length) state.providersCache = data.providers;
      }
    } catch (e) {}

    if (typeof window.MonologAdaptive !== "undefined" && window.MonologAdaptive.loadExchange) window.MonologAdaptive.loadExchange();

    window.dispatchEvent(new Event("monolog-ready"));

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