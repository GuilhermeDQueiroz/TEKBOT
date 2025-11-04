<template>
  <div class="app-container">
    <!-- Sidebar -->
    <aside :class="['sidebar', { collapsed: !sidebarAberta }]">
      <div class="sidebar-header">
        <div class="sidebar-buttons">
        
          <button class="sidebar-toggle" @click="toggleSidebar" title="Fechar barra lateral">
            <span>☰</span>
          </button>
        </div>
        
      </div>
      <div class="sidebar-content" v-show="sidebarAberta">
        <!-- Botão Nova Conversa movido para cá -->
        <button class="new-chat-button" @click="novaConversa" title="Nova conversa">
          <span class="plus-icon">+</span>
          <span class="button-text">Nova Conversa</span>
        </button>
        
        <h3 class="sidebar-title">Conversas</h3>
        
        <div class="conversations-list">
          <div 
            v-for="conversa in conversas" 
            :key="conversa.id"
            :class="['conversation-item', { active: conversa.id === conversaAtiva }]"
          >
            <div class="conversation-info" @click="selecionarConversa(conversa.id)">
              <span class="conversation-title">{{ conversa.titulo }}</span>
              <span class="conversation-date">{{ conversa.data }}</span>
            </div>
            <button 
              class="delete-conversation-button" 
              @click.stop="excluirConversa(conversa.id)"
              title="Excluir conversa"
            >
              <font-awesome-icon icon="trash" />
            </button>
          </div>
        </div>
        
        <!-- Botão de sair movido para o rodapé -->
        <button class="sidebar-logout-button" @click="voltarParaLogin()" title="Sair">
          <font-awesome-icon icon="sign-out-alt" />
          <span>Sair</span>
        </button>
      </div>
    </aside>

    <!-- Chat Container -->
    <div class="chat-container">
      <header class="chat-header">
        <span class="chat-title">TekBot</span>
        <div class="header-buttons">
        <SwitchTemaComponent></SwitchTemaComponent>
          <button class="ticket-button" @click="abrirTicket" title="Abrir ticket">
            <font-awesome-icon icon="ticket-alt" /> Criar Ticket
          </button>
          
        </div>
        
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

// Estado da sidebar
const sidebarAberta = ref(true);

// Função para alternar sidebar
function toggleSidebar() {
  sidebarAberta.value = !sidebarAberta.value;
}

// Sistema de gerenciamento de conversas
const conversas = ref([]);
const conversaAtiva = ref(null);
const proximoId = ref(1);

// Armazena as mensagens de cada conversa
const mensagensPorConversa = ref({});

onMounted(() => {
  // Carrega conversas do localStorage
  carregarConversas();
  
  // ALTERADO: Sempre cria uma nova conversa ao fazer login
  criarNovaConversa();
});

function carregarConversas() {
  const conversasSalvas = localStorage.getItem('tekbot_conversas');
  const mensagensSalvas = localStorage.getItem('tekbot_mensagens');
  const proximoIdSalvo = localStorage.getItem('tekbot_proximo_id');
  
  if (conversasSalvas) {
    conversas.value = JSON.parse(conversasSalvas);
  }
  
  if (mensagensSalvas) {
    mensagensPorConversa.value = JSON.parse(mensagensSalvas);
  }
  
  if (proximoIdSalvo) {
    proximoId.value = parseInt(proximoIdSalvo);
  }
}

function salvarConversas() {
  localStorage.setItem('tekbot_conversas', JSON.stringify(conversas.value));
  localStorage.setItem('tekbot_mensagens', JSON.stringify(mensagensPorConversa.value));
  localStorage.setItem('tekbot_proximo_id', proximoId.value.toString());
}

function criarNovaConversa() {
  const novaConversa = {
    id: proximoId.value++,
    titulo: `Nova Conversa ${conversas.value.length + 1}`,
    data: obterDataFormatada(),
  };
  
  conversas.value.unshift(novaConversa);
  mensagensPorConversa.value[novaConversa.id] = [];
  
  salvarConversas();
  selecionarConversa(novaConversa.id);
}

function novaConversa() {
  // Salva o chat atual antes de criar um novo
  salvarChatAtual();
  criarNovaConversa();
}

function selecionarConversa(id) {
  // Salva o chat atual antes de trocar
  if (conversaAtiva.value !== null) {
    salvarChatAtual();
  }
  
  conversaAtiva.value = id;
  carregarMensagensConversa(id);
}

// Função para excluir conversa
function excluirConversa(id) {
  // Confirma se o usuário realmente quer excluir
  if (!confirm('Tem certeza que deseja excluir esta conversa?')) {
    return;
  }
  
  // Remove a conversa da lista
  const index = conversas.value.findIndex(c => c.id === id);
  if (index !== -1) {
    conversas.value.splice(index, 1);
  }
  
  // Remove as mensagens associadas
  delete mensagensPorConversa.value[id];
  
  // Salva as alterações
  salvarConversas();
  
  // Se a conversa excluída era a ativa, seleciona outra
  if (conversaAtiva.value === id) {
    if (conversas.value.length > 0) {
      // Seleciona a primeira conversa disponível
      selecionarConversa(conversas.value[0].id);
    } else {
      // Se não há mais conversas, cria uma nova
      criarNovaConversa();
    }
  }
}

// NOVA FUNÇÃO: Abrir ticket
function abrirTicket() {
  // Aqui você pode implementar a lógica para abrir um ticket
  // Por exemplo, abrir um modal, redirecionar para outra página, etc.
  alert('Funcionalidade de ticket será implementada aqui!');
  // Exemplo de redirecionamento:
  // router.push('/ticket');
}

function salvarChatAtual() {
  if (conversaAtiva.value === null || !chat.value) return;
  
  // Extrai todas as mensagens do DOM
  const mensagens = [];
  const messageWrappers = chat.value.querySelectorAll('.message-wrapper');
  
  messageWrappers.forEach(wrapper => {
    const bubble = wrapper.querySelector('.message-bubble');
    if (bubble && !bubble.classList.contains('typing-bubble')) {
      const side = wrapper.classList.contains('left') ? 'left' : 'right';
      mensagens.push({
        content: bubble.innerHTML,
        side: side
      });
    }
  });
  
  mensagensPorConversa.value[conversaAtiva.value] = mensagens;
  
  // Atualiza o título da conversa com base na primeira mensagem do usuário
  if (mensagens.length > 0) {
    const primeiraMensagemUsuario = mensagens.find(m => m.side === 'right');
    if (primeiraMensagemUsuario) {
      const conversa = conversas.value.find(c => c.id === conversaAtiva.value);
      if (conversa) {
        const textoLimpo = primeiraMensagemUsuario.content.replace(/<[^>]*>/g, '');
        conversa.titulo = textoLimpo.substring(0, 30) + (textoLimpo.length > 30 ? '...' : '');
      }
    }
  }
  
  salvarConversas();
}

function carregarMensagensConversa(id) {
  // Limpa o chat
  if (chat.value) {
    chat.value.innerHTML = '';
  }
  
  // Carrega as mensagens salvas
  const mensagens = mensagensPorConversa.value[id] || [];
  
  if (mensagens.length === 0) {
    // Mensagem de boas-vindas para novo chat
    appendMessage(
      "Olá! Eu sou o <strong>TekBot</strong> e estou aqui para te ajudar!",
      "left"
    );
  } else {
    // Restaura as mensagens salvas
    mensagens.forEach(msg => {
      appendMessage(msg.content, msg.side);
    });
  }
}

function obterDataFormatada() {
  const agora = new Date();
  const hoje = new Date();
  hoje.setHours(0, 0, 0, 0);
  
  const ontem = new Date(hoje);
  ontem.setDate(ontem.getDate() - 1);
  
  if (agora >= hoje) {
    return 'Hoje';
  } else if (agora >= ontem) {
    return 'Ontem';
  } else {
    return agora.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
  }
}

const submitForm = async () => {
  const msg = formData.msg;
  if (!msg) return;

  appendMessage(msg, "right");
  formData.msg = "";

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
    
    // Salva automaticamente após cada troca de mensagens
    salvarChatAtual();
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

  const typingIndicator = document.createElement("div");
  typingIndicator.className = "typing-indicator";

  for (let i = 0; i < 3; i++) {
    const dot = document.createElement("span");
    typingIndicator.appendChild(dot);
  }

  bubble.appendChild(typingIndicator);

  const style = document.createElement("style");
  style.textContent = `
    @keyframes bounce {
      0%, 60%, 100% {
        transform: translateY(0);
      }
      30% {
        transform: translateY(-8px);
      }
    }
  `;

  wrapper.appendChild(avatar);
  wrapper.appendChild(bubble);
  chat.value.appendChild(wrapper);
  chat.value.scrollTop = chat.value.scrollHeight;

  return wrapper;
}

function voltarParaLogin() {
  // Salva o chat atual antes de sair
  salvarChatAtual();
  localStorage.removeItem("userToken");
  router.replace("/");
}
</script>

<style scope>

/* Container principal que ocupa toda a tela */
.app-container {
  display: flex;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  position: relative;
}

/* Sidebar */
.sidebar {
  width: 280px;
  background-color: black;
  border-right: 1px solid #334155;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: width 0.3s ease, background-color 0.3s ease;
  position: relative;
  z-index: 1000;
}

.sidebar.collapsed {
  width: 60px;
  background-color: #1e293b;
}

.sidebar-header {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  padding: 0.75rem 1rem;
  background-color: black;
  transition: background-color 0.3s ease;
}

.sidebar.collapsed .sidebar-header {
  justify-content: center;
  padding: 0.75rem 0.5rem;
  background-color: #1e293b;
}

.sidebar-buttons {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

/* Botão Nova Conversa - Mesmas proporções das conversas */
.new-chat-button {
  background-color: transparent;
  color: white;
  border: 1px solid #334155;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  transition: all 0.2s;
  padding: 0.5rem 0.75rem;
  margin: 0.5rem;
  font-weight: 500;
  font-size: 0.9rem;
  margin-top: auto;
}

.new-chat-button:hover {
  background-color: #334155;
  border-color: #475569;
}

.new-chat-button .button-text {
  font-size: 0.9rem;
}

.sidebar-toggle {
  color: white;
  border: 1px none;
  border-radius: 6px;
  width: 32px;
  height: 32px;
  font-size: 1.5rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.3s, transform 0.2s;
  flex-shrink: 0;
}

.sidebar-toggle:active {
  transform: scale(0.95);
}

.sidebar-content {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
}

.sidebar-title {
  color: white;
  margin: 0;
  padding: 0.5rem 0.75rem;
  font-size: 0.85rem;
  font-weight: 600;
  background-color: transparent;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #9ca3af;
}

/* Botão de sair na sidebar */
.sidebar-logout-button {
  background-color: transparent;
  color: white;
  border: 1px solid #334155;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  transition: all 0.2s;
  padding: 0.5rem 0.75rem;
  margin: 0.5rem;
  font-weight: 500;
  font-size: 0.9rem;
  margin-top: auto;
}

.sidebar-logout-button:hover {
  background-color: #334155;
  border-color: #475569;
}

.sidebar-logout-button:active {
  transform: scale(0.98);
}

.conversations-list {
  flex: 1;
  overflow-y: auto;
  padding: 0.25rem 0.5rem;
}

.conversation-item {
  padding: 0.5rem 0.75rem;
  margin-bottom: 0.25rem;
  border-radius: 6px;
  cursor: pointer;
  transition: background-color 0.2s;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  position: relative;
}

.conversation-item:hover {
  background-color: #334155;
}

.conversation-item.active {
  background-color: #1e293b;
}

.conversation-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  min-width: 0;
}

.conversation-title {
  color: white;
  font-size: 0.9rem;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conversation-date {
  color: #9ca3af;
  font-size: 0.75rem;
}

.conversation-item.active .conversation-date {
  color: #e0f2fe;
}

/* Botão de excluir conversa com ícone de lixeira */
.delete-conversation-button {
  background-color: transparent;
  color: #9ca3af;
  border: none;
  border-radius: 4px;
  width: 20px;
  height: 20px;
  font-size: 0.9rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  flex-shrink: 0;
  opacity: 0;
  padding: 0;
}

.conversation-item:hover .delete-conversation-button {
  opacity: 1;
}

.delete-conversation-button:hover {
  background-color: #ef4444;
  color: white;
  transform: scale(1.1);
}

.delete-conversation-button:active {
  transform: scale(0.95);
}

/* Chat Container - agora ocupa o espaço restante */
.chat-container {
  flex: 1;
  background-color: white;
  display: flex;
  flex-direction: column;
  overflow: hidden;
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
  border-bottom: 1px solid #334155;
  position: relative;
}

.chat-title {
  color: #2196f3;
}

/* Container para os botões do header */
.header-buttons {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

/* Botão de ticket */
.ticket-button {
  background-color: #10b981;
  border: none;
  color: white;
  font-size: 1rem;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  transition: background-color 0.3s, transform 0.2s;
}

.ticket-button:hover {
  background-color: #059669;
  transform: translateY(-2px);
}

.ticket-button:active {
  transform: translateY(0);
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
  transition: background-color 0.3s, transform 0.2s;
}

.logout-button:hover {
  background-color: #1976d2;
  transform: translateY(-2px);
}

.logout-button:active {
  transform: translateY(0);
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
  border-radius: 15px;
  background-color: #1e293b;
  color: white;
  border: none;
  outline: none;
  font-family: "Rubik", sans-serif;
  font-size: 1rem;
  font-weight: 400;
  height: 100%;
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
  border-radius: 15px;
  font-weight: 600;
  font-size: 0.95rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: white;
  cursor: pointer;
  transition: background-color 0.2s ease-in-out;
  font-family: "Rubik", sans-serif;
  height: 100%;
}

.chat-button:hover {
  background-color: #1976d2;
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
  box-sizing: border-box;
  padding: 0;
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
