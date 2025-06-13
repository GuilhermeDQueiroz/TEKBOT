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
  const loading = appendMessage("Digitando...", "left");

  try {
    const response = await axios.post("http://localhost:8000/ia/responder", {
      pergunta: msg
    });

    // Remove a mensagem de carregamento
    chat.removeChild(loading);

    appendMessage(response.data.resposta, "left");
  } catch (error) {
    console.error("Erro ao chamar a IA:", error);
    chat.removeChild(loading);
    appendMessage("Erro ao processar a pergunta. Tente novamente.", "left");
  }
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

  return wrapper; // útil para remover mensagens (ex: carregamento)
}
