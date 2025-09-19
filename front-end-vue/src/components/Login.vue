<template>
  <div class="login-container">
    <img id="logo" src="/src/assets/claro.png" alt="Logo TekBot" class="logo-img" />

    <h2 class="login-header">Login</h2>
    <form id="login-form" class="login-form" @submit.prevent="submitForm">
      <div class="input-group">
        <label for="email">E-mail:</label>
        <input
          type="email"
          id="email"
          name="email"
          v-model="formData.email"
          required
          placeholder="Digite seu e-mail"
        />
      </div>
      <div class="input-group">
        <label for="password">Senha:</label>
        <input
          type="password"
          id="password"
          name="password"
          v-model="formData.pswd"
          required
          placeholder="Digite sua senha"
        />
      </div>
      <button type="submit" class="login-btn">ENTRAR</button>
    </form>

    <!-- Links para cadastro e recuperação de senha -->
    <div class="login-links">
      <router-link :to="{ name: 'Cadastro' }">Cadastre-se</router-link>

      <router-link :to="{ name: 'RecuperarSenha' }">Esqueceu sua senha?</router-link>
    </div>
  </div>
</template>

<script setup>
import { reactive } from "vue";
import { useRouter } from "vue-router"; // Importe useRouter

const router = useRouter(); // Obtenha a instância do roteador

const formData = reactive({
  email: "",
  pswd: "",
});

const submitForm = async () => {
  try {
    // 1. Aqui, você faria a lógica de envio do formulário, por exemplo, uma chamada de API.
    console.log("Dados a serem enviados:", formData);

    // Simulação de uma chamada de API bem-sucedida
    const response = await new Promise((resolve) =>
      setTimeout(() => resolve({ success: true, userId: 123 }), 1000)
    );

    if (response.success) {
      console.log("Formulário enviado com sucesso! Redirecionando...");

      // 2. Redirecionamento: Duas formas de fazer

      // Opção 1: Usando o nome da rota (Recomendado)
      // É mais robusto, pois se o 'path' da rota mudar, o nome continua o mesmo.
      router.push({ name: "Chat" });
      //router.push({ name: 'Chat', params: { id: response.userId } });

      // Opção 2: Usando o caminho (path) da rota
      // router.push(`/sucesso/${response.userId}`);
    }
  } catch (error) {
    console.error("Erro ao enviar formulário:", error);
  }
};
</script>

<style scope>
.login-btn {
  background-color: #2196f3;
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 10px;
  font-weight: 600;
  font-size: 0.95rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: white;
  cursor: pointer;
  transition: background-color 0.2s ease-in-out;

  font-family: "Rubik", sans-serif;

  /* Centralização horizontal */
  display: block;
  margin: 0 auto;
}

.login-btn:hover {
  background-color: #4caf50;
}

.login-links {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  width: 100%;
  font-size: 0.875rem;
  margin-top: 1rem;
  text-align: center;
}

.login-links .link {
  color: #2196f3;
  text-decoration: none;
  transition: color 0.3s ease-in-out;
}

.login-links .link:hover {
  color: #4caf50;
}

.login-container {
  width: 100%;
  max-width: 400px;
  padding: 2rem;
  background-color: white;
  border-radius: 1rem;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
  border: 1px solid #334155;
  display: flex;
  flex-direction: column;
  align-items: center;
  font-family: "Rubik", sans-serif;
}

.login-header {
  font-size: 1.5rem;
  font-weight: 700;
  margin-bottom: 1.5rem;
  text-align: center;
  letter-spacing: 0.3px;
  color: #2196f3;
}

.login-form {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
</style>
