// core/core-init.js — цепочка инициализации Monolog.
// Только события. Без проверок и try/catch.

(async () => {
  const log = (msg) => {
    console.log(msg);
    let box = document.getElementById('__debug');
    if (!box) {
      box = document.createElement('div');
      box.id = '__debug';
      box.style.cssText = 'position:fixed;left:0;right:0;bottom:0;max-height:30vh;overflow:auto;background:#111;color:#eee;font:12px monospace;padding:8px;z-index:9999;white-space:pre-wrap';
      document.body.appendChild(box);
    }
    box.textContent += '• ' + msg + '\n';
  };

  log('init start');

  await Monolog.core.init();
  log('core init');

  await Monolog.adaptive.mount();
  log('adaptive mount');

  log('ready');
})();