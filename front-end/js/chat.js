const chat = document.getElementById("chat");
const form = document.getElementById("chat-form");
const input = document.getElementById("user-input");

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = input.value.trim();
  if (!msg) return;

  appendMessage(msg, "right");
  input.value = "";

  const loadingWrapper = appendMessage("Digitando...", "left");

  try {
    const { data } = await axios.post("http://localhost:8000/ia/responder", {
      pergunta: msg,
    });

    chat.removeChild(loadingWrapper);

    // ⚠️ Aqui convertemos '\\n' ou '\n' literal em <br>
    const respostaFormatada = data.resposta.replace(/\\n|\\r\\n|\\\\n|\n/g, "<br>");

    appendMessage(respostaFormatada, "left");
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
      ${side === "left" ? `<img class="avatar" src="../img/tekbot.png" alt="TekBot">` : ""}
      <div class="message-bubble ${side}">${message}</div>
      ${side === "right" ? `<img class="avatar" src="../img/usuario.png" alt="Usuário">` : ""}
    </div>
  `;

  chat.insertAdjacentHTML("beforeend", wrapperHtml);
  chat.scrollTop = chat.scrollHeight;

  return chat.lastElementChild;
}

function voltarParaLogin() {
  window.location.href = "../html/login.html"; // substitua pelo caminho correto da sua tela de login
}