// adaptive/modules/development/A.js
// Запросы модуля разработки. Только события.
// GET для чтения, POST для записи.

window.MonologDevA = (function () {

  async function get(path, params) {
    const q = new URLSearchParams(params || {}).toString();
    const url = q ? path + "?" + q : path;
    const r = await fetch(url, { method: "GET" });
    const text = await r.text();
    let data = null;
    try { data = JSON.parse(text); } catch (e) { data = { raw: text }; }
    return { status: r.status, ok: r.ok, data: data };
  }

  async function post(path, payload) {
    const r = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload || {}),
    });
    const text = await r.text();
    let data = null;
    try { data = JSON.parse(text); } catch (e) { data = { raw: text }; }
    return { status: r.status, ok: r.ok, data: data };
  }

  return {
    tree: function (branch) {
      return get("/code/tree", { branch: branch });
    },
    read: function (branch, path) {
      return get("/code/read", { branch: branch, path: path });
    },
    save: function (branch, path, content, sha) {
      return post("/code/save", {
        branch: branch, path: path, content: content, sha: sha,
      });
    },
    check: function (branch, path) {
      return post("/code/check", { branch: branch, path: path });
    },
    state: function (kind, layer, ok, detail) {
      return post("/state/event", {
        kind: kind, layer: layer, ok: ok, detail: detail,
      });
    },
    boot: function (phase) {
      return post("/state/boot", { phase: phase });
    },
  };
})();