// adaptive/modules/development/A.js
// Запросы модуля разработки. Только события.
// Данные приходят снаружи. Решение — за ИИ/ядром.
window.MonologDevA = (function () {
  const base = "";

  async function call(path, payload) {
    const r = await fetch(base + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload || {}),
    });
    const text = await r.text();
    let data = null;
    try { data = JSON.parse(text); } catch (e) { data = { raw: text }; }
    return { status: r.status, ok: r.ok, data: data };
  }

  function state(kind, layer, ok, detail) {
    return call("/state/event", {
      kind: kind, layer: layer, ok: ok, detail: detail,
    });
  }

  return {
    tree: function (branch) {
      return call("/code/tree", { branch: branch });
    },
    read: function (branch, path) {
      return call("/code/read", { branch: branch, path: path });
    },
    save: function (branch, path, content, sha) {
      return call("/code/save", {
        branch: branch, path: path, content: content, sha: sha,
      });
    },
    check: function (branch, path) {
      return call("/code/check", { branch: branch, path: path });
    },
    state: state,
    boot: function (phase) {
      return call("/state/boot", { phase: phase });
    },
  };
})();