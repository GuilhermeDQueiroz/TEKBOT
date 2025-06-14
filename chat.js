const chat = document.getElementById("chat");
const form = document.getElementById("chat-form");
const input = document.getElementById("user-input");

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = input.value.trim();
  if (!msg) return;

  appendMessage(msg, "right");
  input.value = "";

  // Mensagem de carregamento (opcional)
  const loadingWrapper = appendMessage("Digitando...", "left");

  try {
    const { data } = await axios.post("http://localhost:8000/ia/responder", {
      pergunta: msg,
    });

    // Remove a mensagem de carregamento
    chat.removeChild(loadingWrapper);

    appendMessage(data.resposta, "left");
  } catch (error) {
    console.error("Erro ao chamar a IA:", error);
    chat.removeChild(loadingWrapper);
    appendMessage("Erro ao processar a pergunta. Tente novamente.", "left");
  }
});

/**
 * Cria e anexa uma mensagem ao chat.
 * @param {string} message
 * @param {"left"|"right"} side
 * @returns {HTMLDivElement}
 */
function appendMessage(message, side) {
  const wrapperHtml = `
    <div class="message-wrapper ${side}">
      ${side === "left" ? `<img class="avatar" src="tekbot.png" alt="TekBot">` : ""}
      <div class="message-bubble ${side}">${message}</div>
      ${side === "right" ? `<img class="avatar" src="usuario.png" alt="Usuário">` : ""}
    </div>
  `;

  chat.insertAdjacentHTML("beforeend", wrapperHtml);

  chat.scrollTop = chat.scrollHeight;

  return chat.lastElementChild;
}
