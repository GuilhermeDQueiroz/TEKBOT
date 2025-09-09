document.getElementById('cadastro-form').addEventListener('submit', async function (event) {
  event.preventDefault();

  const email = document.getElementById('email').value.trim();
  const password = document.getElementById('password').value;
  const confirmPassword = document.getElementById('confirm-password').value;
  const loginContainer = document.getElementById('login-container');

  const mensagemAntiga = document.getElementById('mensagem-container');
  if (mensagemAntiga) {
    mensagemAntiga.remove();
  }

  const mensagemContainer = document.createElement('div');
  mensagemContainer.id = 'mensagem-container';
  mensagemContainer.classList.add('mensagem-container');

  if (password !== confirmPassword) {
    mensagemContainer.textContent = 'As senhas não coincidem. Por favor, tente novamente.';
    mensagemContainer.classList.add('erro');
  } else {
    try {
      const response = await axios.post("http://127.0.0.1:8000/register", {
        email: email,
        senha: password
      });
      mensagemContainer.textContent = 'Cadastro realizado com sucesso!';
      mensagemContainer.classList.add('sucesso');
      setTimeout(() => {
        window.location.href = '../html/login.html';
      }, 2000);

    } catch (error) {
      alert('login com erro')
    }
  }

  loginContainer.appendChild(mensagemContainer);
});