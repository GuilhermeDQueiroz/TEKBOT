document.addEventListener("DOMContentLoaded", function () {
  const form = document.querySelector(".login-form");
  const container = document.querySelector(".login-container");

  function mostrarMensagem(texto, tipo) {
    // Remove qualquer mensagem anterior
    const mensagemExistente = container.querySelector(".mensagem-container");
    if (mensagemExistente) {
      mensagemExistente.remove();
    }

    const divMensagem = document.createElement("div");
    divMensagem.className = `mensagem-container ${tipo}`; // tipo = 'sucesso' ou 'erro'
    divMensagem.textContent = texto;

    // Permite fechar clicando na mensagem
    divMensagem.addEventListener("click", () => divMensagem.remove());

    container.appendChild(divMensagem);

    // Remove mensagem automaticamente após 5 segundos
    setTimeout(() => {
      if (divMensagem.parentNode) {
        divMensagem.parentNode.removeChild(divMensagem);
      }
    }, 5000);
  }

  form.addEventListener("submit", async function (event) {
    event.preventDefault();

    const email = document.getElementById("email").value.trim();

    if (!email) {
      mostrarMensagem("Por favor, insira um e-mail válido.", "erro");
      return;
    }

    try {
      const response = await fetch("http://localhost:8000/recuperar-senha", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ email })
      });

      const data = await response.json();

      if (response.ok) {
        mostrarMensagem("Um link de redefinição de senha foi enviado para seu e-mail.", "sucesso");
      } else {
        mostrarMensagem(data.detail || "Erro ao enviar o e-mail de recuperação.", "erro");
      }
    } catch (error) {
      console.error("Erro:", error);
      mostrarMensagem("Erro ao conectar com o servidor. Tente novamente mais tarde.", "erro");
    }
  });
});
