// Абсолютный. Контент.

const chat = document.getElementById('chat');
const input = document.getElementById('input');
let firstTime = true;

export async function send(text) {
  const res = await fetch('/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, first_time: firstTime }),
  });
  const data = await res.json();
  firstTime = false;

  // Текст — в чат
  if (data.text) {
    const msg = document.createElement('div');
    msg.className = 'msg bot';
    msg.textContent = data.text;
    chat.appendChild(msg);
  }

  // Маркеры — в систему
  if (data.markers) {
    for (const m of data.markers) {
      applyMarker(m);
    }
  }
}

function applyMarker(marker) {
  const { kind, payload } = marker;
  if (kind === 'ui') {
    if (payload.сфера) setSphereState(payload.сфера);
    if (payload.ввод)  setInputState(payload.ввод);
  }
}