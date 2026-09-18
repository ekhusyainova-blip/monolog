// adaptive/modules/development/D.js
// Слой D — мета: лог, состояние.
// Только события.

window.MonologDevelopment = window.MonologDevelopment || {};
window.MonologDevelopment.D = {

  logTo(host, msg, kind) {
    const line = document.createElement('div');
    line.textContent = '[' + new Date().toLocaleTimeString() + '] ' + msg;
    if (kind === 'err') line.style.color = 'var(--err)';
    if (kind === 'ok') line.style.color = 'var(--ok)';
    host.prepend(line);
    while (host.children.length > 30) {
      host.removeChild(host.lastChild);
    }
  },

  state: {
    branch: 'main',
    currentPath: ''
  },

  setBranch(name) {
    this.state.branch = name;
  },

  setPath(p) {
    this.state.currentPath = p;
  },

  getBranch() {
    return this.state.branch;
  },

  getPath() {
    return this.state.currentPath;
  }
};