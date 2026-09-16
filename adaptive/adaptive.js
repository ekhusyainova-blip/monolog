// adaptive/adaptive.js — сборка интерфейса Monolog по манифесту
// Читает config.json и content.json, строит компоненты, подписывается на core.

window.Monolog = window.Monolog || {};

Monolog.adaptive = {
  version: '2.1',
  config: null,
  content: null,
  openSheetId: null,

  async mount() {
    await this.loadManifests();
    this.renderHeader();
    this.renderMain();
    this.renderSheets();
    this.bindCore();
    console.log('[adaptive] смонтирован');
  },

  async loadManifests() {
    try {
      this.config = await fetch('adaptive/config.json').then(r => r.json());
      this.content = await fetch('adaptive/content.json').then(r => r.json());
    } catch (e) {
      console.error('[adaptive] не загрузились манифесты:', e);
      throw e;
    }
  },

  // --- header ---
  renderHeader() {
    const header = document.getElementById('app-header');
    if (!header || !this.config?.header?.items) return;
    header.innerHTML = '';

    const left = document.createElement('div');
    left.className = 'header-side header-left';
    const right = document.createElement('div');
    right.className = 'header-side header-right';

    this.config.header.items.forEach(item => {
      const el = this.createHeaderItem(item);
      (item.side === 'left' ? left : right).appendChild(el);
    });

    header.appendChild(left);
    header.appendChild(right);
  },

  createHeaderItem(item) {
    const el = document.createElement('button');
    el.className = `header-item header-item-${item.type}`;
    el.dataset.id = item.id;

    const label = this.text(item.labelKey) || item.id;
    el.setAttribute('aria-label', label);
    el.title = label;

    if (item.type === 'orb') el.classList.add('orb', 'state-calm');
    if (item.type === 'index') {
      el.classList.add('index');
      el.textContent = '0';
    }
    if (item.type === 'button') el.textContent = label;

    if (item.badge) {
      const badge = document.createElement('span');
      badge.className = 'badge';
      badge.hidden = true;
      el.appendChild(badge);
    }

    if (item.sheet) el.addEventListener('click', () => this.toggleSheet(item.sheet));

    return el;
  },

  // --- main ---
  renderMain() {
    const main = document.getElementById('app-main');
    if (!main || !this.config?.main?.items) return;
    main.innerHTML = '';

    this.config.main.items.forEach(item => {
      const el = document.createElement('div');
      el.className = `main-item main-item-${item.type}`;
      el.dataset.id = item.id;

      if (item.type === 'note') {
        el.textContent = this.text('ai-note') || '';
      }

      if (item.type === 'chat') {
        el.appendChild(this.buildChat());
      }

      main.appendChild(el);
    });
  },

  buildChat() {
    const wrap = document.createElement('div');
    wrap.className = 'chat';

    const log = document.createElement('div');
    log.className = 'chat-log';
    log.id = 'chat-log';

    const form = document.createElement('form');
    form.className = 'chat-form';
    form.id = 'chat-form';

    const input = document.createElement('textarea');
    input.className = 'chat-input';
    input.id = 'chat-input';
    input.rows = 1;
    input.placeholder = 'Напиши сообщение…';

    const btn = document.createElement('button');
    btn.type = 'submit';
    btn.className = 'btn btn-primary chat-send';
    btn.textContent = 'Отправить';

    form.appendChild(input);
    form.appendChild(btn);

    form.addEventListener('submit', (e) => {
      e.preventDefault();
      this.sendChat();
    });

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.sendChat();
      }
    });

    wrap.appendChild(log);
    wrap.appendChild(form);
    return wrap;
  },

  appendMessage(role, text) {
    const log = document.getElementById('chat-log');
    if (!log) return;
    const msg = document.createElement('div');
    msg.className = `chat-msg chat-msg-${role}`;
    msg.textContent = text;
    log.appendChild(msg);
    log.scrollTop = log.scrollHeight;
  },

  async sendChat() {
    const input = document.getElementById('chat-input');
    if (!input) return;
    const text = input.value.trim();
    if (!text) return;

    input.value = '';
    this.appendMessage('user', text);
    Monolog.core.set('orb', 'active');

    const res = await Monolog.core.chat.send(text);
    const reply = res?.reply || '';
    this.appendMessage('ai', reply || 'Пустой ответ.');
    Monolog.core.set('orb', reply ? 'calm' : 'doubt');
  },

  // --- sheets ---
  renderSheets() {
    const host = document.getElementById('app-sheets');
    if (!host || !this.config?.sheets) return;
    host.innerHTML = '';

    this.config.sheets.forEach(spec => {
      const sheet = document.createElement('div');
      sheet.className = 'sheet';
      if (spec.fullscreen) sheet.classList.add('sheet-fullscreen');
      sheet.id = spec.id;
      sheet.dataset.component = spec.component;
      sheet.hidden = true;

      const head = document.createElement('div');
      head.className = 'sheet-head';
      head.textContent = this.text(spec.titleKey) || spec.id;
      head.addEventListener('click', () => this.closeSheet(spec.id));
      sheet.appendChild(head);

      const body = document.createElement('div');
      body.className = 'sheet-body';
      sheet.appendChild(body);

      host.appendChild(sheet);
    });
  },

  openSheet(id) {
    const sheet = document.getElementById(id);
    if (!sheet) return;
    if (this.openSheetId && this.openSheetId !== id) {
      const prev = document.getElementById(this.openSheetId);
      if (prev) prev.hidden = true;
    }
    sheet.hidden = false;
    this.openSheetId = id;
    this.emit('adaptive:sheet', { id, open: true });
  },

  closeSheet(id) {
    const sheet = document.getElementById(id);
    if (!sheet) return;
    sheet.hidden = true;
    if (this.openSheetId === id) this.openSheetId = null;
    this.emit('adaptive:sheet', { id, open: false });
  },

  toggleSheet(id) {
    if (this.openSheetId === id) this.closeSheet(id);
    else this.openSheet(id);
  },

  // --- связь с core ---
  bindCore() {
    if (!Monolog.core) return;

    Monolog.core.on('core:state', (d) => {
      if (d.key === 'index') {
        const el = document.querySelector('.header-item-index');
        if (el) el.textContent = d.value;
      }
      if (d.key === 'orb') {
        const el = document.querySelector('.header-item-orb');
        if (el) {
          el.classList.remove('state-calm', 'state-doubt', 'state-active', 'state-need');
          el.classList.add('state-' + (d.value || 'calm'));
        }
      }
    });
  },

  // --- утилиты ---
  text(key) {
    if (!key) return '';
    return this.content?.[key] || '';
  },

  emit(evt, data) {
    document.dispatchEvent(new CustomEvent(evt, { detail: data }));
  }
};