// journey/journey.js
// Журнал циклов. Панель + список.

window.MonologJourney = (function () {

  function log(host, text, kind) {
    const line = document.createElement('div');
    line.className = 'jrn-log-' + (kind || 'info');
    line.textContent = text;
    host.prepend(line);
  }

  function render(host, cycles) {
    host.innerHTML = '';
    if (!cycles || !cycles.length) {
      const empty = document.createElement('div');
      empty.className = 'jrn-empty';
      empty.textContent = 'журнал пуст';
      host.appendChild(empty);
      return;
    }
    cycles.forEach(function (c) {
      const card = document.createElement('div');
      card.className = 'jrn-card';

      const head = document.createElement('div');
      head.className = 'jrn-head';
      head.textContent = '#' + c.n + '  ' + (c.date || '');

      const sum = document.createElement('div');
      sum.className = 'jrn-summary';
      sum.textContent = c.summary || '';

      const tags = document.createElement('div');
      tags.className = 'jrn-tags';
      (c.tags || []).forEach(function (t) {
        const s = document.createElement('span');
        s.className = 'jrn-tag';
        s.textContent = t;
        tags.appendChild(s);
      });

      card.appendChild(head);
      card.appendChild(sum);
      card.appendChild(tags);
      host.appendChild(card);
    });
  }

  function load(list, logBox) {
    if (!window.MonologDevA || !window.MonologDevA.cycles) {
      log(logBox, 'MonologDevA не загружен', 'err');
      return;
    }
    log(logBox, 'загрузка журнала...', 'info');
    window.MonologDevA.cycles().then(function (res) {
      const status = res ? res.status : 'no-res';
      if (!res || !res.ok) {
        log(logBox, 'ошибка /cycles: ' + status, 'err');
        return;
      }
      const cycles = (res.data && res.data.cycles) || [];
      log(logBox, 'загружено циклов: ' + cycles.length, 'ok');
      render(list, cycles);
    });
  }

  function mount(container) {
    container.innerHTML = '';
    const wrap = document.createElement('div');
    wrap.className = 'jrn-wrap';

    const head = document.createElement('div');
    head.className = 'jrn-bar';

    const title = document.createElement('span');
    title.className = 'jrn-title';
    title.textContent = 'Журнал циклов';

    const btn = document.createElement('button');
    btn.className = 'jrn-btn';
    btn.textContent = 'Обновить';

    head.appendChild(title);
    head.appendChild(btn);

    const list = document.createElement('div');
    list.className = 'jrn-list';

    const logBox = document.createElement('div');
    logBox.className = 'jrn-log';

    wrap.appendChild(head);
    wrap.appendChild(list);
    wrap.appendChild(logBox);
    container.appendChild(wrap**);

    btn.addEventListener('click', function () { load(list, logBox); });

    load(list, logBox);
    return wrap;
  }

  return { mount: mount };
})();