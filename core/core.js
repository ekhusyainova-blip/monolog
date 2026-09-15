// core/core.js — шина ядра Monolog
// Core: состояние, API, экономика, чат.
// Про adaptive не знает. Отдаёт наружу window.Monolog.core.

window.Monolog = window.Monolog || {};

Monolog.core = {
  version: '2.1',
  state: {},
  ready: false,

  // --- события ---
  emit(evt, data) {
    document.dispatchEvent(new CustomEvent(evt, { detail: data }));
  },

  on(evt, fn) {
    document.addEventListener(evt, (e) => fn(e.detail));
  },

  // --- состояние ---
  set(key, value) {
    this.state[key] = value;
    this.emit('core:state', { key, value });
  },

  get(key) {
    return this.state[key];
  },

  // --- инициализация ---
  async init() {
    if (this.ready) return;
    try {
      await this.initDB();
      await this.initAPI();
      this.ready = true;
      this.emit('core:ready', { version: this.version });
    } catch (e) {
      console.error('[core] ошибка init:', e);
      throw e;
    }
  },

  // --- IndexedDB (заглушка, допишем позже) ---
  async initDB() {
    // TODO: открыть monolog_db_v5, прогнать миграции
    console.log('[core] DB init (заглушка)');
  },

  // --- API (заглушка, допишем позже) ---
  async initAPI() {
    // TODO: проверить /health, подгрузить провайдеров
    console.log('[core] API init (заглушка)');
  },

  // --- экономика (заглушка) ---
  economy: {
    plus(n) { console.log('[core] +', n); },
    minus(n) { console.log('[core] -', n); },
    balance() { return 0; }
  },

  // --- чат (заглушка) ---
  chat: {
    async send(text) {
      console.log('[core] chat.send:', text);
      return { reply: '' };
    }
  }
};