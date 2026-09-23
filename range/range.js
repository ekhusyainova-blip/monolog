// Диапазон. Ползунок.

const range = document.getElementById('range');
const label = document.getElementById('range-label');

const LABELS = ['Глубина', 'Калибровка', 'Сигнал'];
const STATES = ['slow', 'mid', 'fast'];

export function getSpeed() {
  return STATES[Number(range.value)];
}

range.addEventListener('input', () => {
  const v = Number(range.value);
  label.textContent = LABELS[v];
  document.body.dataset.speed = STATES[v];
});