function aplicarTemaSalvo() {
  const temaSalvo = localStorage.getItem("tema") || "claro";
  document.body.classList.add(temaSalvo);
  atualizarTextoBotao(temaSalvo);
}

function alternarTema() {
  const body = document.body;
  if (body.classList.contains("claro")) {
    body.classList.remove("claro");
    body.classList.add("escuro");
    localStorage.setItem("tema", "escuro");
    atualizarTextoBotao("escuro");
  } else {
    body.classList.remove("escuro");
    body.classList.add("claro");
    localStorage.setItem("tema", "claro");
    atualizarTextoBotao("claro");
  }
}

function atualizarTextoBotao(tema) {
  const botao = document.getElementById("botao-tema");
  if (botao) {
    botao.innerText = tema === "claro" ? "🌙" : "☀️";
  }
}

document.addEventListener("DOMContentLoaded", aplicarTemaSalvo);
