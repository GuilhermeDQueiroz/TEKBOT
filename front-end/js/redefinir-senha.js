// front-end/js/redefinirsenha.js
document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("form-redefinir");
  const mensagemDiv = document.getElementById("mensagem");

  const urlParams = new URLSearchParams(window.location.search);
  const token = urlParams.get("token");

  if (!token) {
    mensagemDiv.textContent = "Token inválido ou expirado.";
    mensagemDiv.className = "redefinir-mensagem erro";
    form.style.display = "none";
    return;
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const senha = document.getElementById("novaSenha").value.trim();
    const confirmar = document.getElementById("confirmarSenha").value.trim();

    if (senha.length < 6) {
      mensagemDiv.textContent = "A senha deve ter pelo menos 6 caracteres.";
      mensagemDiv.className = "redefinir-mensagem erro";
      return;
    }

    if (senha !== confirmar) {
      mensagemDiv.textContent = "As senhas não coincidem.";
      mensagemDiv.className = "redefinir-mensagem erro";
      return;
    }

    try {
      const resposta = await fetch("http://localhost:8000/redefinir-senha", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nova_senha: senha, token: token }),
      });

      const resultado = await resposta.json();

      if (resposta.ok) {
        mensagemDiv.textContent = "Senha redefinida com sucesso!";
        mensagemDiv.className = "redefinir-mensagem sucesso";
        form.reset();
        form.style.display = "none";
      } else {
        mensagemDiv.textContent = resultado.detail || "Erro ao redefinir senha.";
        mensagemDiv.className = "redefinir-mensagem erro";
      }
    } catch (erro) {
      mensagemDiv.textContent = "Erro ao conectar com o servidor.";
      mensagemDiv.className = "redefinir-mensagem erro";
      console.error(erro);
    }
  });
});
