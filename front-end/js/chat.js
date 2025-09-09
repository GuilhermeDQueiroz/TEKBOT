const chat = document.getElementById("chat");
const form = document.getElementById("chat-form");
const input = document.getElementById("user-input");

// Exibe mensagem de boas-vindas ao abrir a tela
window.addEventListener("DOMContentLoaded", () => {
  appendMessage("Olá! Eu sou o <strong>TekBot</strong> e estou aqui para te ajudar!", "left");
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = input.value.trim();
  if (!msg) return;

  appendMessage(msg, "right");
  input.value = "";

  // Mostra animação de "Digitando..."
  const digitando = appendTypingMessage();

  try {
    const { data } = await axios.post("http://localhost:8000/ia/responder", {
      pergunta: msg,
    });

    chat.removeChild(digitando);

    // Converte \n em <br>
    const respostaFormatada = data.resposta.replace(/\\n|\\r\\n|\\\\n|\n/g, "<br>");
    appendMessage(respostaFormatada, "left");
  } catch (error) {
    console.error("Erro ao chamar a IA:", error);
    chat.removeChild(digitando);
    appendMessage("Erro ao processar a pergunta. Tente novamente.", "left");
  }
});

/**
 * Cria e anexa uma mensagem padrão ao chat.
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

/**
 * Cria e anexa a animação "digitando..." ao chat.
 * @returns {HTMLDivElement}
 */
function appendTypingMessage() {
  const wrapper = document.createElement("div");
  wrapper.className = "message-wrapper left";

  const avatar = document.createElement("img");
  avatar.className = "avatar";
  avatar.src = "../img/tekbot.png";
  avatar.alt = "TekBot";

  const bubble = document.createElement("div");
  bubble.className = "message-bubble left typing-bubble";
  bubble.innerHTML = `
    <div class="typing-indicator">
      <span></span><span></span><span></span>
    </div>
  `;

  wrapper.appendChild(avatar);
  wrapper.appendChild(bubble);
  chat.appendChild(wrapper);
  chat.scrollTop = chat.scrollHeight;

  return wrapper;
}

function voltarParaLogin() {
  window.location.href = "../html/login.html";
}
