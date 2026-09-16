(async () => {
  if (!window.Monolog || !Monolog.core) {
    console.error('[init] core не загружен');
    return;
  }

  try {
    await Monolog.core.init();
  } catch (e) {
    console.error('[init] ошибка core:', e);
    return;
  }

  if (Monolog.adaptive && typeof Monolog.adaptive.mount === 'function') {
    try {
      await Monolog.adaptive.mount();
    } catch (e) {
      console.error('[init] ошибка adaptive:', e);
      return;
    }
  }

  Monolog.core.emit('app:ready', {});
})(); 