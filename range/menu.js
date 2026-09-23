// Диапазон. Меню.

const menu = document.getElementById('menu');

export function openMenu()  { menu.classList.add('open'); }
export function closeMenu() { menu.classList.remove('open'); }

// Свайп влево — открыть
let startX = 0;
document.addEventListener('touchstart', (e) => {
  startX = e.touches[0].clientX;
});
document.addEventListener('touchend', (e) => {
  const dx = e.changedTouches[0].clientX - startX;
  if (dx < -80) openMenu();
  if (dx > 80)  closeMenu();
});