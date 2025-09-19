<template>
  <label class="switch">
    <input type="checkbox" id="botao-tema" />
    <span class="slider">
      <i class="fas fa-sun icone sol"></i>
      <i class="fas fa-moon icone lua"></i>
    </span>
  </label>

  <div class="login-container" id="login-container" ref="loginContainer">
    <h2 class="login-header">Cadastro</h2>
    <form class="login-form" id="cadastro-form" @submit.prevent="submitForm">
      <div class="input-group">
        <label for="email">E-mail:</label>
        <input
          type="email"
          id="email"
          name="email"
          required
          placeholder="Digite seu e-mail"
          v-model="formData.email"
        />
      </div>
      <div class="input-group">
        <label for="password">Senha:</label>
        <input
          type="password"
          id="password"
          name="password"
          required
          placeholder="Digite sua senha"
          v-model="formData.pswd"
        />
      </div>
      <div class="input-group">
        <label for="confirm-password">Confirmar Senha:</label>
        <input
          type="password"
          id="confirm-password"
          name="confirm-password"
          required
          placeholder="Confirme sua senha"
          v-model="formData.confirmPswd"
        />
      </div>
      <button type="submit" class="login-btn">Cadastrar</button>
    </form>

    <div class="login-links">
      <router-link :to="{ name: 'Login' }">Já tem uma conta? Faça login</router-link>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from "vue";
const loginContainer = ref(null);
const formData = reactive({
  email: "",
  pswd: "",
  confirmPswd: "",
});
async function submitForm(event) {
  const mensagemAntiga = document.getElementById("mensagem-container");
  if (mensagemAntiga) {
    mensagemAntiga.remove();
  }

  const mensagemContainer = document.createElement("div");
  mensagemContainer.id = "mensagem-container";
  mensagemContainer.classList.add("mensagem-container");

  if (formData.pswd !== formData.confirmPswd) {
    mensagemContainer.textContent =
      "As senhas não coincidem. Por favor, tente novamente.";
    mensagemContainer.classList.add("erro");
  } else {
    try {
      const response = await axios.post("http://127.0.0.1:8000/register", {
        email: formData.email,
        senha: formData.pswd,
      });
      mensagemContainer.textContent = "Cadastro realizado com sucesso!";
      mensagemContainer.classList.add("sucesso");
      setTimeout(() => {
       router.replace({ name: "Login" });
      }, 2000);
    } catch (error) {
      alert("login com erro");
    }
  }

  loginContainer.value.appendChild(mensagemContainer);
}
</script>

<style scope></style>
