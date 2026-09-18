// adaptive/modules/development/B.js
// Слой B — базовый интерфейс модуля разработки.
// Создаёт контейнер панели. Только события.

window.MonologDevelopment = window.MonologDevelopment || {};
window.MonologDevelopment.B = {

  createPanel(container) {
    container.innerHTML = '';

    const wrap = document.createElement('div');
    wrap.className = 'dev-wrap';

    const branches = document.createElement('div');
    branches.className = 'dev-branches';

    const tree = document.createElement('div');
    tree.className = 'dev-tree';

    const editor = document.createElement('div');
    editor.className = 'dev-editor';

    const log = document.createElement('div');
    log.className = 'dev-log';

    wrap.appendChild(branches);
    wrap.appendChild(tree);
    wrap.appendChild(editor);
    wrap.appendChild(log);
    container.appendChild(wrap);

    return { wrap, branches, tree, editor, log };
  }
};