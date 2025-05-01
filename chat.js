const chat = document.getElementById("chat");
const form = document.getElementById("chat-form");
const input = document.getElementById("user-input");

form.onsubmit = (e) => {
  e.preventDefault();
  const msg = input.value.trim();
  if (!msg) return;

  addMessage(msg, "right");
  input.value = "";

  setTimeout(() => addMessage("Essa é uma resposta automática!", "left"), 1000);
};

function addMessage(text, side) {
  chat.innerHTML += `
    <div class="message-wrapper ${side}">
      ${side === "left" ? `<img class="avatar" src="tekbot.png" alt="TekBot">` : ""}
      <div class="message-bubble ${side}">${text}</div>
      ${side === "right" ? `<img class="avatar" src="usuario.png" alt="Usuário">` : ""}
    </div>
  `;
  chat.scrollTop = chat.scrollHeight;
}
