// adaptive/adaptive.js — сборка интерфейса Monolog.
// Только события. Без if и проверок.

window.Monolog = window.Monolog || {};

Monolog.adaptive = {
  version: '3.0',

  ui: {
    header: {
      items: [
        { id: 'orb', type: 'orb', side: 'left', label: 'Состояние', target: 'orbSheet' },
        { id: 'index', type: 'index', side: 'left', label: 'Индекс', target: 'indexSheet' },
        { id: 'menu', type: 'button', side: 'right', label: 'Меню', target: 'menuSheet' }
      ]
    },
    main: {
      items: [
        { id: 'ai-note', type: 'note', text: 'Monolog — когнитивный партнёр. Отражаю, не веду.' },
        { id: 'chat', type: 'chat' }
      ]
    },
    sheets: [
      { id: 'menuSheet', title: 'Меню' },
      { id: 'editorSheet', title: 'Редактор' },
      { id: 'orbSheet', title: 'Состояние' },
      { id: 'indexSheet', title: 'Индекс' }
    ],
    menuItems: [
      { id: 'editor', label: 'Редактор', target: 'editorSheet' },
      { id: 'index', label: 'Индекс', target: 'indexSheet' }
    ]
  },

  async mount() {
    this.renderHeader();
    this.renderMain();
    this.renderSheets();
    this.bindCore();
    console.log('[adaptive] смонтирован');
  },

  renderHeader() {
    const header = document.getElementById('app-header');
    header.innerHTML = '';
    const left = document.createElement('div');
    left.className = 'header-side header-left';
    const right = document.createElement('div');
    right.className = 'header-side header-right';

    this.ui.header.items.forEach(item => {
      const el = document.createElement('button');
      el.className = 'header-item header-item-' + item.type;
      el.textContent = item.label;
      el.addEventListener('click', () => this.openSheet(item.target));
      (item.side === 'left' ? left : right).appendChild(el);
    });

    header.appendChild(left);
    header.appendChild(right);
  },

  renderMain() {
    const main = document.getElementById('app-main');
    main.innerHTML = '';

    this.ui.main.items.forEach(item => {
      const el = document.createElement('div');
      el.className = 'main-item main-item-' + item.type;
      el.dataset.id = item.id;

      if (item.type === 'note') {
        el.textContent = item.text;
      }

      if (item.type === 'chat') {
        const ta = document.createElement('textarea');
        ta.className = 'chat-input';
        ta.placeholder = 'Напиши сообщение...';

        const btn = document.createElement('button');
        btn.className = 'chat-send';
        btn.textContent = 'Отправить';

        const replies = document.createElement('div');
        replies.className = 'chat-replies';
        replies.id = 'chat-replies';

        btn.addEventListener('click', async () => {
          const text = ta.value.trim();
          const reply = await Monolog.core.chat.send(text);
          replies.textContent = reply;
        });

        el.appendChild(ta);
        el.appendChild(btn);
        el.appendChild(replies);
      }

      main.appendChild(el);
    });
  },

  renderSheets() {
    const host = document.getElementById('app-sheets');
    host.innerHTML = '';

    this.ui.sheets.forEach(spec => {
      const sheet = document.createElement('div');
      sheet.className = 'sheet';
      sheet.id = spec.id;
      sheet.hidden = true;

      const head = document.createElement('div');
      head.className = 'sheet-head';
      head.textContent = spec.title;

      const body = document.createElement('div');
      body.className = 'sheet-body';

      if (spec.id === 'menuSheet') {
        this.renderMenuItems(body);
      }

      sheet.appendChild(head);
      sheet.appendChild(body);
      host.appendChild(sheet);
    });
  },

  renderMenuItems(body) {
    const list = document.createElement('div');
    list.className = 'menu-list';

    this.ui.menuItems.forEach(it => {
      const btn = document.createElement('button');
      btn.className = 'menu-item';
      btn.textContent = it.label;
      btn.addEventListener('click', () => this.openSheet(it.target));
      list.appendChild(btn);
    });

    body.appendChild(list);
  },

  openSheet(id) {
    document.querySelectorAll('.sheet').forEach(s => {
      s.hidden = s.id !== id;
    });
    this.emit('adaptive:sheet', { id, open: true });
  },

  bindCore() {
    Monolog.core.on('core:state', (d) => console.log('[adaptive] state:', d));
    Monolog.core.on('core:chat_reply', (d) => console.log('[adaptive] reply:', d.text));
  },

  emit(evt, data) {
    document.dispatchEvent(new CustomEvent(evt, { detail: data }));
  }
};