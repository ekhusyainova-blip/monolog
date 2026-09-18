// adaptive/modules/development/A.js
// Слой A — запросы к backend.
// Только события. Без условий.

window.MonologDevelopment = window.MonologDevelopment || {};
window.MonologDevelopment.A = {

  async tree(branch) {
    const res = await fetch('/code/tree?branch=' + encodeURIComponent(branch || ''));
    return await res.json();
  },

  async branches() {
    const res = await fetch('/code/branches');
    return await res.json();
  },

  async read(path) {
    const res = await fetch('/code/read?path=' + encodeURIComponent(path));
    return await res.json();
  },

  async save(path, content) {
    const res = await fetch('/ai/apply_raw?path=' + encodeURIComponent(path) +
      '&message=Update', {
      method: 'POST',
      headers: { 'Content-Type': 'text/plain;charset=utf-8' },
      body: content,
    });
    return await res.json();
  },

  async check(path) {
    const res = await fetch('/code/check?path=' + encodeURIComponent(path));
    return await res.json();
  }
};