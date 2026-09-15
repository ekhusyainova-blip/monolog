(async () => {
  if (!window.Monolog || !Monolog.core) {
    console.error('[init] core не загружен');
    return;
  }

  try {
    await Monolog.core.init();
    console.log('[init] core готов');
  } catch (e) {
    console.error('[init] ошибка core:', e);
    return;
  }

  if (Monolog.adaptive && typeof Monolog.adaptive.mount === 'function') {
    try {
      await Monolog.adaptive.mount();
      console.log('[init] adaptive смонтирован');
    } catch (e) {
      console.error('[init] ошибка adaptive:', e);
      return;
    }
  } else {
    console.warn('[init] adaptive не найден — пропускаем');
  }

  Monolog.core.emit('app:ready', {});
})();