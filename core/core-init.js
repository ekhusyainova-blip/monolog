// core/core-init.js — инициализация Monolog.
// Только события. Без if и try/catch.

(async () => {
  const log = (msg) => {
    console.log(msg);
    document.getElementById('__debug').textContent += '• ' + msg + '\n';
  };

  window.addEventListener('error', (e) => {
    log('ERR ' + e.message);
  });

  log('init start');

  await Monolog.core.init();
  log('core init');

  await Monolog.adaptive.mount();
  log('adaptive mount');

  log('ready');
})();