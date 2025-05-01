const chat = document.getElementById("chat");
const form = document.getElementById("chat-form");
const input = document.getElementById("user-input");

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const msg = input.value.trim();
  if (!msg) return;

  appendMessage(msg, "right");
  input.value = "";

  setTimeout(() => {
    appendMessage("Essa é uma resposta automática!", "left");
  }, 1000);
});

function appendMessage(message, side) {
  const wrapper = document.createElement("div");
  wrapper.className = `message-wrapper ${side}`;

  const bubble = document.createElement("div");
  bubble.className = `message-bubble ${side}`;
  bubble.innerHTML = `${message}`;

  wrapper.appendChild(bubble);
  chat.appendChild(wrapper);
  chat.scrollTop = chat.scrollHeight;
}
