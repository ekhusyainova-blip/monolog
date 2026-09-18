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

// --- дописано: boot-маркер ABCD в /state ---
// Старый mount выше не трогаем. Только маркеры.
(function () {
  if (!window.MonologDevD) window.MonologDevD = {};

  const _mountOld = MonologDevD.mount;

  MonologDevD.markLayers = function () {
    const layers = ["A", "B", "C", "D"];
    return Promise.all(
      layers.map(function (l) {
        return MonologDevA.state("mount", l, true, "development");
      })
    );
  };

  MonologDevD.mount = function (mountPoint) {
    const result = _mountOld
      ? _mountOld.call(MonologDevD, mountPoint)
      : Promise.resolve();
    return Promise.resolve(result).then(function () {
      return MonologDevD.markLayers();
    }).then(function () {
      return MonologDevA.boot("ready");
    });
  };
})();