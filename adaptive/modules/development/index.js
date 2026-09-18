// adaptive/modules/development/index.js
// Сборка модуля разработки. Только события.

window.MonologDevelopment = window.MonologDevelopment || {};

window.MonologDevelopment.mount = function (container) {
  const B = window.MonologDevelopment.B;
  const C = window.MonologDevelopment.C;
  const D = window.MonologDevelopment.D;
  const A = window.MonologDevA;

  const panel = B.createPanel(container);
  const { branches, tree, editor, log } = panel;

  const branchNames = ["main", "structure", "dev"];
  C.renderBranches(branches, branchNames, D.getBranch(), function (name) {
    D.setBranch(name);
    C.renderBranches(branches, branchNames, name, arguments.callee);
    D.logTo(log, "ветка: " + name, "ok");
    loadTree(name);
  });

  function loadTree(branch) {
    D.logTo(log, "загрузка дерева: " + branch, "info");
    A.tree(branch).then(function (res) {
      if (!res || !res.ok) {
        D.logTo(log, "ошибка дерева: " + (res && res.status), "err");
        return;
      }
      const paths = (res.data && res.data.paths) || [];
      C.renderTree(tree, paths, function (path) {
        D.setPath(path);
        loadFile(branch, path);
      });
    });
  }

  const ed = C.createEditor();
  editor.appendChild(ed.pathRow);
  editor.appendChild(ed.ta);
  editor.appendChild(ed.buttons);

  function report(label, res) {
    const ok = res && res.ok;
    const body = res && res.data ? JSON.stringify(res.data).slice(0, 300) : "";
    D.logTo(log,
      label + " → " + (res && res.status) + (ok ? " ok" : " FAIL") + " " + body,
      ok ? "ok" : "err");
    return ok;
  }

  function loadFile(branch, path) {
    ed.pathInput.value = path;
    D.logTo(log, "загрузка: " + path, "info");
    A.read(branch, path).then(function (res) {
      if (!res || !res.ok) { report("read " + path, res); return; }
      ed.ta.value = (res.data && res.data.content) || "";
      D.logTo(log, "загружен: " + path, "ok");
    });
  }

  ed.btnLoad.addEventListener("click", function () {
    const path = ed.pathInput.value.trim();
    if (path) loadFile(D.getBranch(), path);
  });

  ed.btnSave.addEventListener("click", function () {
    const path = ed.pathInput.value.trim();
    if (!path) return;
    D.logTo(log, "save " + path, "info");
    A.save(D.getBranch(), path, ed.ta.value).then(function (res) {
      if (report("save", res)) loadTree(D.getBranch());
    });
  });

  ed.btnCheck.addEventListener("click", function () {
    const path = ed.pathInput.value.trim();
    if (!path) return;
    D.logTo(log, "check " + path, "info");
    A.check(D.getBranch(), path).then(function (res) { report("check", res); });
  });

  ed.btnCreate.addEventListener("click", function () {
    const path = ed.pathInput.value.trim();
    if (!path) { D.logTo(log, "укажи путь для нового файла", "err"); return; }
    D.logTo(log, "create " + path, "info");
    A.create(D.getBranch(), path, ed.ta.value).then(function (res) {
      if (report("create", res)) loadTree(D.getBranch());
    });
  });

  ed.btnDelete.addEventListener("click", function () {
    const path = ed.pathInput.value.trim();
    if (!path) { D.logTo(log, "укажи путь для удаления", "err"); return; }
    D.logTo(log, "delete " + path, "info");
    A.remove(D.getBranch(), path).then(function (res) {
      if (report("delete", res)) {
        ed.ta.value = "";
        loadTree(D.getBranch());
      }
    });
  });

  loadTree(D.getBranch());

  if (A && A.state) {
    ["A", "B", "C", "D"].forEach(function (l) {
      A.state("mount", l, true, "development");
    });
  }
  if (A && A.boot) A.boot("ready");

  return panel;
};