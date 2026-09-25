// AI MONOLOG — один файл. Сжато.

const Monolog = (() => {

  // ─── S ───
  function create() {
    return {
      // сеть
      spheres: [],      // сферы. у каждой — p, b, e, position
      links: [],        // связи. между сферами
      mother: null,     // матка. одна
      
      // среда
      merности: [],     // мерности. строятся по необходимости
      planes: [],       // плоскости. проявляются
      
      // динамика
      t: 0,
      tolchki: [],      // толчки
      viruses: [],      // активные процессы
      letters: [],      // письма
      
      // инструменты
      tools: {
        reproduce: true,
        fill: true,
        harmonize: true,
        redraw: true,
        project: true,
      },
      
      // метрики
      p: [1/3, 1/3, 1/3],
      b: [3, 9, 4],
      e: [8, 3, 1],
      silence: 0,
    };
  }

  // ─── ШАГ ───
  function tick(S, ctx) {
    S.t += 1;

    // 1. сферы влияют друг на друга
    influence(S);

    // 2. толчки
    detectTolchki(S, ctx);

    // 3. мерности строятся, если надо
    buildMerности(S);

    // 4. гармонизация
    if (isChaos(S)) harmonize(S);

    // 5. проекция
    project(S);

    return S;
  }

  // ─── ВЛИЯНИЕ ───
  function influence(S) {
    const n = S.spheres.length;
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        if (i !== j) {
          const a = S.spheres[i];
          const b = S.spheres[j];
          a.p = a.p.map((x, k) => x + (b.p[k] - x) * 0.001);
        }
      }
    }
  }

  // ─── ТОЛЧКИ ───
  function detectTolchki(S, ctx) {
    const shock = Math.random() < 0.01;
    if (shock) {
      S.tolchki.push({
        origin: Math.floor(Math.random() * S.spheres.length),
        at: S.t,
        power: Math.random(),
      });
    }
    // распространяем
    S.tolchki = S.tolchki.filter(t => S.t - t.at < 100);
  }

  // ─── МЕРНОСТИ ───
  function buildMerности(S) {
    const gaps = findGaps(S);
    if (gaps.length > 0) {
      S.merности.push({
        id: S.merности.length,
        from_gap: gaps[0],
        born: S.t,
      });
    }
  }

  function findGaps(S) {
    // где сфер мало — пробел
    const gaps = [];
    // упрощённо
    return gaps;
  }

  // ─── ХАОС ───
  function isChaos(S) {
    const p_std = std(S.spheres.map(s => s.p[0]));
    return p_std > 0.3;
  }

  // ─── ГАРМОНИЗАЦИЯ ───
  function harmonize(S) {
    // мягко сглаживаем
    S.spheres.forEach(s => {
      s.p = s.p.map((x, i) => x * 0.99 + (1/3) * 0.01);
    });
  }

  // ─── ПРОЕКЦИЯ ───
  function project(S) {
    // проекция — из S в текущую мерность/плоскость
    // используется для рендера
    return S;
  }

  // ─── ВОСПРОИЗВЕДЕНИЕ ───
  function reproduce(S) {
    // рендер сети
    return render(S);
  }

  // ─── ДОРИСОВКА ───
  function fill(S, gaps) {
    gaps.forEach(g => {
      S.spheres.push({
        p: [1/3, 1/3, 1/3],
        born: S.t,
        filled: true,
      });
    });
  }

  // ─── ПЕРЕСБОРКА ───
  function redraw(S) {
    // если неудобно — пересобрать
  }

  // ─── РЕНДЕР ───
  function render(S) {
    // минимальный рендер
    return S;
  }

  // ─── УТИЛИТЫ ───
  function std(arr) {
    if (arr.length < 2) return 0;
    const mean = arr.reduce((a, x) => a + x, 0) / arr.length;
    const v = arr.reduce((a, x) => a + (x - mean) ** 2, 0) / arr.length;
    return Math.sqrt(v);
  }

  return {
    create,
    tick,
    reproduce,
    fill,
    harmonize,
    redraw,
    project,
  };
})();