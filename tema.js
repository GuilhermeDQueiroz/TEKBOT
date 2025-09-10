function aplicarTemaSalvo() {
  const temaSalvo = localStorage.getItem("tema") || "claro";
  document.body.classList.add(temaSalvo);

  const checkbox = document.getElementById("botao-tema");
  if (checkbox) {
    checkbox.checked = temaSalvo === "escuro";
  }
}

function alternarTema() {
  const body = document.body;
  const checkbox = document.getElementById("botao-tema");

  if (checkbox.checked) {
    body.classList.remove("claro");
    body.classList.add("escuro");
    localStorage.setItem("tema", "escuro");
  } else {
    body.classList.remove("escuro");
    body.classList.add("claro");
    localStorage.setItem("tema", "claro");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  aplicarTemaSalvo();

  const checkbox = document.getElementById("botao-tema");
  if (checkbox) {
    checkbox.addEventListener("change", alternarTema);
  }
});
