// core/core.js — шина ядра Monolog.
// Только события. Без if и проверок.

window.Monolog = window.Monolog || {};

Monolog.core = {
  version: '3.0',
  state: {},
  ready: false,

  emit(evt, data) {
    document.dispatchEvent(new CustomEvent(evt, { detail: data }));
  },

  on(evt, fn) {
    document.addEventListener(evt, (e) => fn(e.detail));
  },

  set(key, value) {
    this.state[key] = value;
    this.emit('core:state', { key, value });
  },

  get(key) {
    return this.state[key];
  },

  async init() {
    this.ready = true;
    this.emit('core:ready', { version: this.version });
  },

  economy: {
    plus(n) {
      this.set('index', (this.get('index') || 0) + n);
    },
    minus(n) {
      this.set('index', (this.get('index') || 0) - n);
    },
    balance() {
      return this.get('index') || 0;
    }
  },

  chat: {
    async send(text) {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text })
      });
      const data = await res.json();
      const reply = data.reply_text || data.reply || '';
      this.emit('core:chat_reply', { text: reply });
      return reply;
    }
  }
};