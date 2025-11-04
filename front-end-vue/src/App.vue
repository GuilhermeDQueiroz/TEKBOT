<script setup>
import { onMounted } from "vue";

let checkbox;
onMounted(() => {
  checkbox = document.getElementById("botao-tema");
  aplicarTemaSalvo();

  if (checkbox) {
    checkbox.addEventListener("change", alternarTema);
  }
});
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
</script>

<template>
  <head>
    <title>TekBot</title>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css" />
  </head>
  <main>
    <!--  <label class="switch">
      <input type="checkbox" id="botao-tema" ref="botaoTema" @change="alternarTema" />
      <span class="slider">
        <i class="fas fa-sun icone sol"></i>
        <i class="fas fa-moon icone lua"></i>
      </span>
    </label> -->
    <router-view />
  </main>
</template>

<style scope>
@import url("https://fonts.googleapis.com/css2?family=Rubik:wght@400;500;600;700&display=swap");

@keyframes bounce {

  0%,
  80%,
  100% {
    transform: scale(0.8);
    opacity: 0.6;
  }

  40% {
    transform: scale(1.2);
    opacity: 1; }
}
</style>
