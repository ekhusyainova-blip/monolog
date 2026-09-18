// adaptive/modules/development/D.js — фрагмент: boot ABCD
// Только события. Данные снаружи.
window.MonologDevD = window.MonologDevD || {};

MonologDevD.markLayers = function () {
  const layers = ["A", "B", "C", "D"];
  return Promise.all(
    layers.map(function (l) {
      return MonologDevA.state("mount", l, true, "development");
    })
  );
};

MonologDevD.mount = function (mountPoint) {
  // здесь твой существующий mount — не трогаем.
  // после успешного mount — boot-маркер.
  return MonologDevD.markLayers().then(function () {
    return MonologDevA.boot("ready");
  });
};