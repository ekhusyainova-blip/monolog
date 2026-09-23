// Диапазон. Сфера.

const sphere = document.getElementById('sphere');

export function(mode) {
  if (!mode) return;
  sphere.dataset.mode = mode;
  if (mode === 'say' || mode === 'warn') {
    setTimeout(() => sphere.dataset.mode = 'calm', 1300);
  }
}