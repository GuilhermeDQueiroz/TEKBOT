// Em front-end/js/login.js

const form = document.getElementById("login-form");
const inputEmail = document.getElementById("email");
const inputPassword = document.getElementById("password");

form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const email = inputEmail.value.trim();
    const senha = inputPassword.value.trim();
    
    if (!email || !senha) return;

    try {
        const response = await axios.post("http://127.0.0.1:8000/login", {
            email: email,
            senha: senha
        });


        if (response.data && response.data.access_token) {
            
            localStorage.setItem('authToken', response.data.access_token);
            
            window.location.href = '../html/chat.html';

        } else {
            throw new Error("Resposta do servidor inválida: token não encontrado.");
        }

    } catch (error) {
        console.error("Erro no login:", error);
        Swal.fire({
            icon: "error",
            title: "Erro ao logar!",
            text: "Verifique seu e-mail e senha e tente novamente.",
            heightAuto: false
        });
    }
});