// adaptive/editor.js
// Автономный модуль MonologEditor.
// Монтируется в любой контейнер. Не знает, куда встроен.
// Минимальная версия: textarea + path + message + Save + лог + автопроверка.

window.MonologEditor = (() => {
  const STYLES = `
    .me-wrap {
      display: flex;
      flex-direction: column;
      gap: 8px;
      padding: 12px;
      height: 100%;
      box-sizing: border-box;
      font-family: var(--font, system-ui, sans-serif);
      color: var(--fg, #e8e8ec);
      background: var(--bg, #0e0e11);
    }
    .me-input {
      background: var(--bg-soft, #16161b);
      border: 1px solid var(--line, #26262e);
      border-radius: 8px;
      color: var(--fg, #e8e8ec);
      padding: 8px 10px;
      font-size: 14px;
      font-family: var(--font-mono, monospace);
      outline: none;
    }
    .me-input:focus { border-color: var(--accent, #7c8cff); }
    .me-textarea {
      flex: 1;
      min-height: 200px;
      resize: vertical;
      background: var(--bg-soft, #16161b);
      border: 1px solid var(--line, #26262e);
      border-radius: 8px;
      color: var(--fg, #e8e8ec);
      padding: 10px;
      font-family: var(--font-mono, monospace);
      font-size: 13px;
      line-height: 1.5;
      outline: none;
      white-space: pre;
      overflow: auto;
    }
    .me-textarea:focus { border-color: var(--accent, #7c8cff); }
    .me-btn {
      padding: 10px 16px;
      border-radius: 8px;
      border: 1px solid var(--accent, #7c8cff);
      background: var(--accent-soft, #3a3f66);
      color: var(--fg, #e8e8ec);
      font-size: 14px;
      font-weight: 500;
      cursor: pointer;
    }
    .me-btn:hover { background: var(--accent, #7c8cff); color: #fff; }
    .me-btn:disabled { opacity: .5; cursor: wait; }
    .me-log {
      font-family: var(--font-mono, monospace);
      font-size: 12px;
      color: var(--fg-dim, #9a9aa6);
      max-height: 120px;
      overflow-y: auto;
      border-top: 1px solid var(--line, #26262e);
      padding-top: 8px;
    }
    .me-log-line { padding: 2px 0; }
    .me-log-ok { color: var(--ok, #5bd67a); }
    .me-log-err { color: var(--err, #ff6b6b); }
  `;

  function injectStyles() {
    if (document.getElementById('__me_styles')) return;
    const s = document.createElement('style');
    s.id = '__me_styles';
    s.textContent = STYLES;
    document.head.appendChild(s);
  }

  function logLine(logEl, text, kind = '') {
    const line = document.createElement('div');
    line.className = 'me-log-line' + (kind ? ' me-log-' + kind : '');
    const time = new Date().toLocaleTimeString();
    line.textContent = `[${time}] ${text}`;
    logEl.prepend(line);
    while (logEl.children.length > 5) {
      logEl.removeChild(logEl.lastChild);
    }
  }

  function emit(name, detail) {
    document.dispatchEvent(new CustomEvent(name, { detail }));
  }

  async function checkFile(path) {
    const res = await fetch('/code/check?path=' + encodeURIComponent(path));
    if (!res.ok) return { valid: false, error: 'HTTP ' + res.status };
    return await res.json();
  }

  function mount(container) {
    if (!container) {
      console.warn('[MonologEditor] нет контейнера');
      return;
    }
    injectStyles();
    container.innerHTML = '';

    const wrap = document.createElement('div');
    wrap.className = 'me-wrap';

    const pathInput = document.createElement('input');
    pathInput.className = 'me-input';
    pathInput.placeholder = 'путь к файлу, напр. core_backend/routers/example.py';

    const msgInput = document.createElement('input');
    msgInput.className = 'me-input';
    msgInput.placeholder = 'сообщение коммита (опционально)';

    const ta = document.createElement('textarea');
    ta.className = 'me-textarea';
    ta.placeholder = 'вставь содержимое файла сюда';

    const btn = document.createElement('button');
    btn.className = 'me-btn';
    btn.textContent = 'Save';

    const logEl = document.createElement('div');
    logEl.className = 'me-log';

    wrap.appendChild(pathInput);
    wrap.appendChild(msgInput);
    wrap.appendChild(ta);
    wrap.appendChild(btn);
    wrap.appendChild(logEl);
    container.appendChild(wrap);

    btn.addEventListener('click', async () => {
      const path = pathInput.value.trim();
      const message = msgInput.value.trim() || 'Update ' + path;
      const content = ta.value;
      if (!path || !content) {
        logLine(logEl, 'нужны path и content', 'err');
        return;
      }
      btn.disabled = true;
      logLine(logEl, 'сохраняю ' + path + ' ...');
      try {
        const url = '/ai/apply_raw?path=' + encodeURIComponent(path) +
                    '&message=' + encodeURIComponent(message);
        const res = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'text/plain;charset=utf-8' },
          body: content,
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          logLine(logEl, 'ошибка: ' + (data.detail || res.status), 'err');
          emit('editor:error', { path, error: data.detail || res.status });
          btn.disabled = false;
          return;
        }
        logLine(logEl, 'сохранено: ' + path, 'ok');
        emit('editor:saved', { path, message });

        // автопроверка
        logLine(logEl, 'проверяю синтаксис ...');
        const check = await checkFile(path);
        if (check.valid) {
          logLine(logEl, 'синтаксис ок', 'ok');
          emit('editor:check_result', { path, valid: true });
        } else {
          logLine(logEl,
            'ошибка синтаксиса: ' + (check.error || '?') +
            (check.line ? ' (строка ' + check.line + ')' : ''),
            'err');
          emit('editor:check_result', { path, valid: false, info: check });
        }
      } catch (e) {
        logLine(logEl, 'сеть: ' + e.message, 'err');
        emit('editor:error', { path, error: e.message });
      }
      btn.disabled = false;
    });

    logLine(logEl, 'редактор готов');
  }

  return { mount };
})();