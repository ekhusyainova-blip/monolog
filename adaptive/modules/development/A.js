// adaptive/modules/development/A.js
// Запросы. GET — чтение, POST — запись.

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
    tree: (branch) => get("/code/tree", { branch }),
    read: (branch, path) => get("/code/read", { branch, path }),
    save: (branch, path, content, sha) =>
      post("/code/save", { branch, path, content, sha }),
    check: (branch, path) => post("/code/check", { branch, path }),
    checkAll: (branch, limit) =>
      post("/code/check-all", { branch, limit: limit || 500 }),
    create: (branch, path, content) =>
      post("/code/create", { branch, path, content: content || "" }),
    remove: (branch, path) => post("/code/delete", { branch, path }),
    state: (kind, layer, ok, detail) =>
      post("/state/event", { kind, layer, ok, detail }),
    boot: (phase) => post("/state/boot", { phase }),
    cycles: () => get("/cycles", {}),
    cycleAdd: (payload) => post("/cycles/add", payload),
  };
})();