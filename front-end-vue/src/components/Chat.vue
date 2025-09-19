<template>
  <div class="chat-container">
    <header class="chat-header">
      <span class="chat-title">TekBot</span>
      <button class="logout-button" @click="voltarParaLogin()">
        <font-awesome-icon icon="sign-out-alt" /> Sair
      </button>
    </header>

    <main id="chat" ref="chat" class="chat-main">
      <!-- Mensagens vão aqui -->
    </main>

    <form id="chat-form" class="chat-form" @submit.prevent="submitForm">
      <input
        id="user-input"
        type="text"
        placeholder="Digite sua mensagem..."
        class="chat-input"
        autocomplete="off"
        required
        v-model="formData.msg"
      />
      <button type="submit" class="chat-button">Enviar</button>
    </form>
  </div>
</template>

<script setup>
import { onMounted, ref, reactive } from "vue";
import { useRouter } from "vue-router";
const router = useRouter();
const chat = ref(null);
const input = ref(null);

const formData = reactive({
  msg: "",
});

onMounted(() => {
  appendMessage(
    "Olá! Eu sou o <strong>TekBot</strong> e estou aqui para te ajudar!",
    "left"
  );
});

const submitForm = async () => {
  const msg = formData.msg;
  if (!msg) return;

  appendMessage(msg, "right");
  input.value = "";

  // Mostra animação de "Digitando..."
  const digitando = appendTypingMessage();

  try {
    const { data } = await axios.post("http://localhost:8000/ia/responder", {
      pergunta: msg,
    });

    chat.value.removeChild(digitando);

    // Converte \n em <br>
    const respostaFormatada = data.resposta.replace(/\\n|\\r\\n|\\\\n|\n/g, "<br>");
    appendMessage(respostaFormatada, "left");
  } catch (error) {
    console.error("Erro ao chamar a IA:", error);
    chat.value.removeChild(digitando);
    appendMessage("Erro ao processar a pergunta. Tente novamente.", "left");
  }
};

/**
 * Cria e anexa uma mensagem padrão ao chat.
 * @param {string} message
 * @param {"left"|"right"} side
 * @returns {HTMLDivElement}
 */
function appendMessage(message, side) {
  const wrapperHtml = `
    <div class="message-wrapper ${side}">
      ${
        side === "left"
          ? `<img class="avatar" src="/src/assets/tekbot.png" alt="TekBot">`
          : ""
      }
      <div class="message-bubble ${side}">${message}</div>
      ${
        side === "right"
          ? `<img class="avatar" src="/src/assets/usuario.png" alt="Usuário">`
          : ""
      }
    </div>
  `;
  chat.value.insertAdjacentHTML("beforeend", wrapperHtml);
  chat.value.scrollTop = chat.value.scrollHeight;
  return chat.value.lastElementChild;
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
  chat.value.appendChild(wrapper);
  chat.value.scrollTop = chat.value.scrollHeight;

  return wrapper;
}

function voltarParaLogin() {
  localStorage.removeItem("userToken");
  router.replace("/");
}
</script>

<style scope>
.chat-container {
  width: 80%;
  height: 80%;
  background-color: white;
  border-radius: 1rem;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #334155;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: var(--primary-color);
  color: white;
  padding: 1rem;
  font-size: 1.5rem;
  font-weight: bold;
  border-top-left-radius: 10px;
  border-top-right-radius: 10px;
}

.chat-title {
  margin-right: auto;
  color: #2196f3;
}

.logout-button {
  background-color: #2196f3;
  border: none;
  color: white;
  font-size: 1rem;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  transition: background-color 0.3s, color 0.3s;
}

.logout-button:hover {
  background-color: #1976d2;
}

.chat-main {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.chat-form {
  padding: 1rem;
  border-top: 1px solid #334155;
  display: flex;
  gap: 0.5rem;
  align-items: center;
  background-color: inherit;
}

.chat-input {
  flex: 1;
  padding: 0.75rem 1rem;
  border-radius: 10px;
  background-color: #1e293b;
  color: white;
  border: none;
  outline: none;
  font-family: "Rubik", sans-serif;
  font-size: 1rem;
  font-weight: 400;
}

.chat-input::placeholder {
  color: #9ca3af;
  font-size: 0.8rem;
}

.chat-input:focus {
  outline: 2px solid #2196f3;
}

.chat-button {
  background-color: #2196f3;
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 9999px;
  font-weight: 600;
  font-size: 0.95rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: white;
  cursor: pointer;
  transition: background-color 0.2s ease-in-out;
  font-family: "Rubik", sans-serif;
}

.chat-button:hover {
  background-color: #4caf50;
}

::-webkit-scrollbar {
  width: 8px;
}

::-webkit-scrollbar-thumb {
  background-color: #334155;
  border-radius: 8px;
}

@keyframes fade-in {
  from {
    opacity: 0;
    transform: translateY(10px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-fade-in {
  animation: fade-in 0.3s ease-out;
}

.message-wrapper {
  display: flex;
  animation: fade-in 0.3s ease-out;
}

.message-wrapper.right {
  justify-content: flex-end;
}

.message-wrapper.left {
  justify-content: flex-start;
}

.message-bubble {
  max-width: 28rem;
  padding: 0.75rem 1.25rem;
  border-radius: 1rem;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
  max-width: 80ch;
  word-wrap: break-word;
  overflow-wrap: break-word;
  white-space: pre-wrap;
  font-family: "Rubik", sans-serif;
  font-size: 0.95rem;
  line-height: 1.5;
}

.message-bubble.right {
  background-color: #2196f3;
  color: white;
  border-bottom-right-radius: 0;
}

.message-bubble.left {
  background-color: #334155;
  color: white;
  border-bottom-left-radius: 0;
}

.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  object-fit: cover;
  align-self: flex-end;
  padding-right: 4px;
  padding-left: 4px;
}

.input-group {
  display: flex;
  flex-direction: column;
}

.mensagem-container {
  margin-top: 20px;
  padding: 15px;
  border-radius: 8px;
  font-size: 16px;
  font-weight: bold;
  text-align: center;
  font-family: "Rubik", sans-serif;
}

.sucesso {
  background-color: #d4edda;
  color: #155724;
  border: 1px solid #c3e6cb;
}

.erro {
  background-color: #f8d7da;
  color: #721c24;
  border: 1px solid #f5c6cb;
}

.login-container,
.chat-container {
  background-color: inherit;
  color: inherit;
}

input,
button,
.chat-input {
  background-color: inherit;
  color: inherit;
  border: 1px solid #888;
}

.switch {
  position: fixed;
  top: 10px;
  right: 10px;
  width: 60px;
  height: 34px;
  display: inline-block;
  z-index: 1000;
}

.switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  background-color: #2196f3;
  border-radius: 34px;
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  transition: background-color 0.4s;
}

.slider:before {
  content: "";
  position: absolute;
  height: 26px;
  width: 26px;
  left: 4px;
  bottom: 4px;
  background-color: white;
  border-radius: 50%;
  transition: transform 0.4s;
  z-index: 2;
}

input:checked + .slider {
  background-color: #000;
}

input:checked + .slider:before {
  transform: translateX(26px);
}

.icone {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  font-size: 16px;
  z-index: 1;
  color: rgb(255, 255, 255);
  transition: opacity 0.3s, transform 0.3s;
  opacity: 0.7;
}

.icone.sol {
  left: 10px;
}

.icone.lua {
  right: 10px;
}

input:not(:checked) + .slider .sol {
  opacity: 10;
}

input:checked + .slider .lua {
  opacity: 10;
}
.typing-bubble {
  width: 86px;
  height: 46.8px;
  background-color: #334155;
  border-radius: 1rem;
  display: flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box; /* faz com que width/height incluam o padding */
  padding: 0; /* garante que nada seja somado */
}

.typing-indicator {
  display: flex;
  gap: 6px;
  align-items: center;
  justify-content: center;
  height: 100%;
}
.typing-indicator span {
  width: 6px;
  height: 6px;
  background-color: white;
  border-radius: 50%;
  opacity: 0.8;
  animation: bounce 1.2s infinite ease-in-out;
}

.typing-indicator span:nth-child(1) {
  animation-delay: -0.32s;
}
.typing-indicator span:nth-child(2) {
  animation-delay: -0.16s;
}
.typing-indicator span:nth-child(3) {
  animation-delay: 0s;
}
</style>
