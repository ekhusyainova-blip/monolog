// adaptive/modules/development/index.js
// Сборка модуля разработки из A, B, C, D.

window.MonologDevelopment = window.MonologDevelopment || {};
window.MonologDevelopment.mount = async function(container) {
  const A = window.MonologDevelopment.A;
  const B = window.MonologDevelopment.B;
  const C = window.MonologDevelopment.C;
  const D = window.MonologDevelopment.D;

  const ui = B.createPanel(container);
  D.logTo(ui.log, 'модуль разработки запущен');

  // загрузка веток
  const br = await A.branches();
  C.renderBranches(ui.branches, br.branches || ['main'], D.getBranch(), async (name) => {
    D.setBranch(name);
    D.logTo(ui.log, 'ветка: ' + name);
    const tr = await A.tree(name);
    C.renderTree(ui.tree, tr.paths || [], loadFile);
  });

  // редактор
  const ed = C.createEditor();
  ui.editor.appendChild(ed.pathInput);
  ui.editor.appendChild(ed.ta);
  ui.editor.appendChild(ed.buttons);

  async function loadFile(path) {
    const data = await A.read(path);
    if (!data.exists) {
      D.logTo(ui.log, 'не найден: ' + path, 'err');
      return;
    }
    D.setPath(path);
    ed.pathInput.value = path;
    ed.ta.value = data.content || '';
    D.logTo(ui.log, 'загружен: ' + path, 'ok');
  }

  ed.btnLoad.addEventListener('click', () => {
    const p = ed.pathInput.value.trim();
    if (p) loadFile(p);
  });

  ed.btnSave.addEventListener('click', async () => {
    const p = ed.pathInput.value.trim();
    const r = await A.save(p, ed.ta.value);
    D.logTo(ui.log, r.ok ? 'сохранено: ' + p : 'ошибка сохранения', r.ok ? 'ok' : 'err');
  });

  ed.btnCheck.addEventListener('click', async () => {
    const p = ed.pathInput.value.trim();
    const r = await A.check(p);
    D.logTo(ui.log, r.valid ? 'синтаксис ок' : 'ошибка: ' + (r.error || ''), r.valid ? 'ok' : 'err');
  });

  // первичная загрузка дерева
  const tr = await A.tree(D.getBranch());
  C.renderTree(ui.tree, tr.paths || [], loadFile);
};