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
    loginContainer.appendChild(mensagemContainer);
    return;
  }

  if (password.length < 6) {
    mensagemContainer.textContent = 'A senha deve ter no mínimo 6 caracteres.';
    mensagemContainer.classList.add('erro');
    loginContainer.appendChild(mensagemContainer);
    return;
  }

  try {
    const response = await axios.post("http://127.0.0.1:8000/register", {
      email: email,
      senha: password
    });

    mensagemContainer.textContent = 'Cadastro realizado com sucesso! Redirecionando...';
    mensagemContainer.classList.add('sucesso');
    loginContainer.appendChild(mensagemContainer);

    setTimeout(() => {
      window.location.href = '../html/login.html';
    }, 2000);

  } catch (error) {
    console.error('Erro no cadastro:', error);
    
    let mensagemErro = 'Erro ao realizar cadastro. Tente novamente.';
    
    if (error.response) {
      if (error.response.status === 400) {
        mensagemErro = error.response.data.detail || 'Email já cadastrado.';
      } else if (error.response.status === 500) {
        mensagemErro = 'Erro no servidor. Tente novamente mais tarde.';
      } else if (error.response.data?.detail) {
        mensagemErro = error.response.data.detail;
      }
    } else if (error.request) {
      mensagemErro = 'Não foi possível conectar ao servidor. Verifique sua conexão.';
    }
    
    mensagemContainer.textContent = mensagemErro;
    mensagemContainer.classList.add('erro');
    loginContainer.appendChild(mensagemContainer);
  }
});