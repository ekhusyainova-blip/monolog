// adaptive/modules/development/C.js
// Слой C — рендер. Только события.

window.MonologDevelopment = window.MonologDevelopment || {};
window.MonologDevelopment.C = {

  renderBranches(host, branches, current, onPick) {
    host.innerHTML = '';
    branches.forEach(name => {
      const btn = document.createElement('button');
      btn.className = 'dev-branch-btn' + (name === current ? ' active' : '');
      btn.textContent = name;
      btn.addEventListener('click', () => onPick(name));
      host.appendChild(btn);
    });
  },

  renderTree(host, paths, onPick) {
    host.innerHTML = '';
    paths.forEach(p => {
      const el = document.createElement('div');
      el.className = 'dev-tree-item';
      el.textContent = p;
      el.title = p;
      el.addEventListener('click', () => onPick(p));
      host.appendChild(el);
    });
  },

  createEditor() {
    const pathRow = document.createElement('div');
    pathRow.className = 'dev-path-row';

    const pathInput = document.createElement('input');
    pathInput.className = 'dev-input dev-path';
    pathInput.placeholder = 'путь к файлу';

    const btnLoad = document.createElement('button');
    btnLoad.className = 'dev-btn';
    btnLoad.textContent = 'Открыть';

    pathRow.appendChild(pathInput);
    pathRow.appendChild(btnLoad);

    const ta = document.createElement('textarea');
    ta.className = 'dev-textarea';
    ta.placeholder = 'содержимое файла';

    const buttons = document.createElement('div');
    buttons.className = 'dev-buttons';

    const mkBtn = (text) => {
      const b = document.createElement('button');
      b.className = 'dev-btn';
      b.textContent = text;
      buttons.appendChild(b);
      return b;
    };

    const btnSave = mkBtn('Сохранить');
    const btnCheck = mkBtn('Проверить');
    const btnCheckAll = mkBtn('Проверить всё');
    const btnCreate = mkBtn('Создать');
    const btnDelete = mkBtn('Удалить');

    return { pathRow, pathInput, ta, buttons,
             btnLoad, btnSave, btnCheck, btnCheckAll, btnCreate, btnDelete };
  }
};