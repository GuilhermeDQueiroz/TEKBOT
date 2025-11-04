<template>
    <div>
        <label class="switch">
            <input type="checkbox" id="botao-tema" ref="botaoTema" @change="alternarTema" />
            <span class="slider">
                <i class="fas fa-sun icone sol"></i>
                <i class="fas fa-moon icone lua"></i>
            </span>
        </label>
    </div>
</template>

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

<style scoped>
.switch {
    position: relative;
    display: inline-block;
    width: 60px;
    height: 30px;
}

.switch input {
    opacity: 0;
    width: 0;
    height: 0;
}
</style>