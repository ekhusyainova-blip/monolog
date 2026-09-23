// Диапазон. Ввод.

const form = document.getElementById('form');
const input = document.getElementById('input');

// Enter — отправка
input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    form.requestSubmit();
  }
});

// Автовысота
input.addEventListener('input', () => {
  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 180) + 'px';
});

// Видимость — диапазон
export function setInputState(state) {
  form.dataset.state = state; // "visible" | "hidden"
}