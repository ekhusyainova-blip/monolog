// adaptive/adaptive.js — сборка интерфейса Monolog по манифесту
// Читает config.json и content.json, строит компоненты, подписывается на core.
// В IndexedDB напрямую не пишет — только через Monolog.core.

window.Monolog = window.Monolog || {};

Monolog.adaptive = {
  version: '2.2',
  config: null,
  content: null,

  async mount() {
    await this.loadManifests();
    this.renderHeader();
    this.renderMain();
    this.renderSheets();
    this.bindCore();
    console.log('[adaptive] смонтирован');
  },

  // --- загрузка манифестов ---
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

    if (item.type === 'orb') el.classList.add('orb');
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

    if (item.sheet) {
      el.addEventListener('click', () => this.openSheet(item.sheet));
    }

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
      if (item.type === 'note') el.textContent = this.text('ai-note') || '';
      main.appendChild(el);
    });
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
      sheet.appendChild(head);

      const body = document.createElement('div');
      body.className = 'sheet-body';
      sheet.appendChild(body);

      // --- menuSheet: рисуем пункты ---
      if (spec.id === 'menuSheet') {
        this.renderMenuItems(body);
      }

      // --- editorSheet: монтируем MonologEditor ---
      if (spec.id === 'editorSheet' && window.MonologEditor) {
        setTimeout(() => window.MonologEditor.mount(body), 0);
      }

      host.appendChild(sheet);
    });
  },

  // --- содержимое menuSheet ---
  renderMenuItems(body) {
    const items = [
      { id: 'editor',    label: 'Редактор',     target: 'editorSheet' },
      { id: 'settings',  label: 'Настройки',    target: 'settingsSheet' },
      { id: 'about',     label: 'О продукте',   target: 'aboutSheet' },
    ];

    const list = document.createElement('div');
    list.className = 'menu-list';

    items.forEach(it => {
      const btn = document.createElement('button');
      btn.className = 'menu-item';
      btn.dataset.id = it.id;
      btn.textContent = it.label;
      btn.addEventListener('click', () => this.openSheet(it.target));
      list.appendChild(btn);
    });

    body.appendChild(list);
  },

  openSheet(id) {
    const sheet = document.getElementById(id);
    if (!sheet) return;

    // закрыть все открытые
    document.querySelectorAll('.sheet').forEach(s => {
      if (s.id !== id) s.hidden = true;
    });

    sheet.hidden = false;
    this.emit('adaptive:sheet', { id, open: true });
  },

  closeSheet(id) {
    const sheet = document.getElementById(id);
    if (!sheet) return;
    sheet.hidden = true;
    this.emit('adaptive:sheet', { id, open: false });
  },

  // --- связь с core ---
  bindCore() {
    if (!Monolog.core) return;

    Monolog.core.on('core:state', (d) => {
      console.log('[adaptive] state:', d);
    });

    Monolog.core.on('app:ready', () => {
      console.log('[adaptive] app:ready получен');
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