function aplicarTemaSalvo() {
  const temaSalvo = localStorage.getItem("tema") || "claro";
  document.body.classList.add(temaSalvo);

  const checkbox = document.getElementById("botao-tema");
  if (checkbox) {
    checkbox.checked = temaSalvo === "escuro";
  }

  trocarImagemTema(temaSalvo); // ← atualiza imagem no carregamento
}

function alternarTema() {
  const body = document.body;
  const checkbox = document.getElementById("botao-tema");

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
    logo.src = "../img/escuro.png"; // substitua pelo nome real da imagem escura
  } else {
    logo.src = "../img/claro.png"; // substitua pelo nome real da imagem clara
  }
}

document.addEventListener("DOMContentLoaded", () => {
  aplicarTemaSalvo();

  const checkbox = document.getElementById("botao-tema");
  if (checkbox) {
    checkbox.addEventListener("change", alternarTema);
  }
});
