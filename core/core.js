// core/core.js — шина ядра Monolog.
// Только события. Без условий и проверок.

window.Monolog = window.Monolog || {};

Monolog.core = {
  version: '2.2',
  state: {
    index: 0,
    orb: 'calm'
  },
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
    this.emit('core:state', { key: 'index', value: this.state.index });
    this.emit('core:state', { key: 'orb', value: this.state.orb });
  },

  economy: {
    plus(n) {
      this.set('index', this.get('index') + n);
    },
    minus(n) {
      this.set('index', this.get('index') - n);
    },
    balance() {
      return this.get('index');
    }
  },

  chat: {
    async send(text, onReply) {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text })
      });
      const data = await res.json();
      onReply(data.reply_text || data.reply || '');
      this.emit('core:chat_reply', { text: data.reply_text || data.reply || '' });
    }
  }
};