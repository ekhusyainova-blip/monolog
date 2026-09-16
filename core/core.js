// core/core.js — шина ядра Monolog
// Core: состояние, API, экономика, чат.
// Про adaptive не знает. Отдаёт наружу window.Monolog.core.

window.Monolog = window.Monolog || {};

Monolog.core = {
  version: '2.1',
  state: {
    index: 0,
    orb: 'calm'
  },
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
      this.emit('core:state', { key: 'index', value: this.state.index });
      this.emit('core:state', { key: 'orb', value: this.state.orb });
    } catch (e) {
      console.error('[core] ошибка init:', e);
      throw e;
    }
  },

  // --- IndexedDB ---
  async initDB() {
    // TODO: открыть monolog_db_v5, прогнать миграции
    console.log('[core] DB init (заглушка)');
  },

  // --- API ---
  async initAPI() {
    try {
      const res = await fetch('/health');
      if (res.ok) {
        const data = await res.json();
        console.log('[core] health:', data);
      }
    } catch (e) {
      console.warn('[core] health недоступен:', e.message);
    }
  },

  // --- экономика ---
  economy: {
    plus(n) { Monolog.core.set('index', Monolog.core.get('index') + n); },
    minus(n) { Monolog.core.set('index', Monolog.core.get('index') - n); },
    balance() { return Monolog.core.get('index'); }
  },

  // --- чат ---
  chat: {
    async send(text) {
      if (!text || !text.trim()) return { reply: '' };
      try {
        const res = await fetch('/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: text })
        });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        return { reply: data.reply_text || data.reply || '' };
      } catch (e) {
        console.error('[core] chat ошибка:', e.message);
        return { reply: 'Ошибка сети. Попробуй ещё раз.' };
      }
    }
  }
};