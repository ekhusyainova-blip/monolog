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
    (cycles || []).forEach(function (c) {
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

  function mount(container) {
    container.innerHTML = '';
    const wrap = document.createElement('div');
    wrap.className = 'jrn-wrap';

    const title = document.createElement('h3');
    title.className = 'jrn-title';
    title.textContent = 'Журнал циклов';

    const list = document.createElement('div');
    list.class