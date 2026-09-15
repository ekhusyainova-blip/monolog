(async () => {
  const log = (msg, isErr) => {
    console.log(msg);
    let box = document.getElementById('__debug');
    if (!box) {
      box = document.createElement('div');
      box.id = '__debug';
      box.style.cssText = 'position:fixed;left:0;right:0;bottom:0;max-height:40vh;overflow:auto;background:#111;color:#eee;font:12px monospace;padding:8px;z-index:9999;white-space:pre-wrap';
      document.body.appendChild(box);
    }
    box.textContent += (isErr ? 'ERR ' : '• ') + msg + '\n';
  };

  log('init start');
  window.addEventListener('error', e => log(e.message, true));

  if (!window.Monolog) {
    log('Monolog не создан', true);
    return;
  }
  if (!Monolog.core) {
    log('core не создан', true);
    return;
  }
  log('core есть');

  try {
    await Monolog.core.init();
    log('core готов');
  } catch (e) {
    log('core упал: ' + e.message, true);
    return;
  }

  if (!Monolog.adaptive) {
    log('adaptive не создан', true);
    return;
  }
  log('adaptive есть');

  try {
    await Monolog.adaptive.mount();
    log('adaptive смонтирован');
  } catch (e) {
    log('adaptive упал: ' + e.message, true);
    return;
  }

  log('готово');
})();