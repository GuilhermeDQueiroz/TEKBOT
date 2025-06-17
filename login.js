const form = document.getElementById("login-form");
const inputEmail = document.getElementById("email");
const inputPassword = document.getElementById("password");

form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const email = inputEmail.value.trim();
    const senha = inputPassword.value.trim();
    if (!email) return;

    try {
        const response = await axios.post("http://127.0.0.1:8000/login", {
            email: email,
            senha: senha
        });

        window.location = '/chat.html';
    } catch (error) {
        Swal.fire({
            icon: "error",
            title: "Erro ao logar!",
            text: "Tente novamente!",
            heightAuto:false
        });
    }
});