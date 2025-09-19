<template>
  <label class="switch">
    <input type="checkbox" id="botao-tema" />
    <span class="slider">
      <i class="fas fa-sun icone sol"></i>
      <i class="fas fa-moon icone lua"></i>
    </span>
  </label>

  <div class="login-container">
    <h2 class="login-header">Recuperar senha</h2>
    <p class="help-text">
      Digite seu e-mail para receber o link de redefinição de senha.
    </p>
    <form class="login-form">
      <div class="input-group">
        <input
          type="email"
          id="email"
          name="email"
          required
          placeholder="Digite seu e-mail"
        />
      </div>
      <button type="submit" class="login-btn">Enviar link</button>
    </form>

    <div class="login-links">
      <router-link :to="{ name: 'Login' }">Voltar ao login</router-link>
    </div>
  </div>
</template>

<script setup></script>

<style scope></style>
