<script setup>
import Login from "./components/Login.vue";
import Chat from "./components/Chat.vue";
import { ref } from "vue";

const botaoTema = ref(null);
const checkbox = botaoTema.value;

function aplicarTemaSalvo() {
  const temaSalvo = localStorage.getItem("tema") || "claro";
  document.body.classList.add(temaSalvo);

  
  if (checkbox) {
    checkbox.checked = temaSalvo === "escuro";
  }

  trocarImagemTema(temaSalvo); // ← atualiza imagem no carregamento
}

function alternarTema() {
  const body = document.body;

  if (checkbox.checked) {
    body.classList.remove("claro");
    body.classList.add("escuro");
    localStorage.setItem("tema", "escuro");
    trocarImagemTema("escuro"); // ← atualiza imagem ao trocar
  } else {
    body.classList.remove("escuro");
    body.classList.add("claro");
    localStorage.setItem("tema", "claro");
    trocarImagemTema("claro"); // ← atualiza imagem ao trocar
  }
}

function trocarImagemTema(tema) {
  const logo = document.getElementById("logo");
  if (!logo) return;

  if (tema === "escuro") {
    logo.src = "/src/assets/escuro.png"; // substitua pelo nome real da imagem escura
  } else {
    logo.src = "/src/assets/claro.png"; // substitua pelo nome real da imagem clara
  }
}

document.addEventListener("DOMContentLoaded", () => {
  aplicarTemaSalvo();

  if (checkbox) {
    checkbox.addEventListener("change", alternarTema);
  }
});
</script>

<template>
  <head>
    <title>TekBot</title>
    <meta charset="UTF-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <link
      rel="stylesheet"
      href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css"
    />
  </head>
  <main>
    <label class="switch">
      <input type="checkbox" id="botao-tema" ref="botaoTema" @change="alternarTema" />
      <span class="slider">
        <i class="fas fa-sun icone sol"></i>
        <i class="fas fa-moon icone lua"></i>
      </span>
    </label>
    <router-view />
  </main>
</template>

<style scope>
@import url("https://fonts.googleapis.com/css2?family=Rubik:wght@400;500;600;700&display=swap");

/*




body.redefinir-body {
  width: 100%;
  min-height: 100vh;
  margin: 0;
  padding: 1rem;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--bg-color, #fff);
  box-sizing: border-box;
}

.redefinir-container {
  background-color: white;
  border-radius: 1rem;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
  border: 1px solid #334155;
  padding: 2rem;
  max-width: 400px;
  width: 90%;
  display: flex;
  flex-direction: column;
  align-items: center;
  font-family: "Rubik", sans-serif;
  animation: fade-in 0.4s ease-in-out;
}

.redefinir-container h2 {
  font-size: 1.5rem;
  font-weight: 700;
  margin-bottom: 1.5rem;
  text-align: center;
  letter-spacing: 0.3px;
  color: #2196f3;
  width: 100%;
}

.redefinir-form {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.redefinir-input {
  padding: 0.75rem 1rem;
  border-radius: 10px;
  border: 1px solid #334155;
  background-color: #f1f5f9;
  color: #334155;
  font-size: 1rem;
  font-family: "Rubik", sans-serif;
  outline: none;
  transition: border-color 0.3s ease;
  width: calc(
    100% - 2rem
  ); /* subtrai as laterais para encaixar dentro do padding do container */
/*}
/*
.redefinir-input:focus {
  border-color: #2196f3;
}

.redefinir-btn {
  width: 100%;
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 10px;
  font-weight: 600;
  font-size: 0.95rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: white;
  background-color: #2196f3;
  cursor: pointer;
  transition: background-color 0.3s ease-in-out;
  font-family: "Rubik", sans-serif;
}

.redefinir-btn:hover {
  background-color: #4caf50;
}

.redefinir-mensagem {
  margin-top: 1rem;
  text-align: center;
  font-weight: 600;
  width: 100%;
  font-family: "Rubik", sans-serif;
  padding: 10px;
  border-radius: 8px;
}

.redefinir-mensagem.erro {
  background-color: #f8d7da;
  color: #721c24;
  border: 1px solid #f5c6cb;
}

.redefinir-mensagem.sucesso {
  background-color: #d4edda;
  color: #155724;
  border: 1px solid #c3e6cb;
}


 */
@keyframes bounce {
  0%,
  80%,
  100% {
    transform: scale(0.8);
    opacity: 0.6;
  }
  40% {
    transform: scale(1.2);
    opacity: 1;
  }
}
</style>
