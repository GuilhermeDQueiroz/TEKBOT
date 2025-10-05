document.addEventListener('DOMContentLoaded', () => {

    const sessoesListaEl = document.getElementById("sessoes-lista");
    const chatEl = document.getElementById("chat");
    const chatFormEl = document.getElementById("chat-form");
    const userInputEl = document.getElementById("user-input");
    const novaSessaoBtnEl = document.getElementById("nova-sessao-btn");
    const logoutBtnEl = document.getElementById("logout-btn");

    let sessaoIdAtiva = null;

    // ===============================================================
    // ==         ⭐ 1. LÓGICA CENTRAL DE AUTENTICAÇÃO ⭐          ==
    // ===============================================================

    const token = localStorage.getItem('authToken');
    if (!token) {
        console.warn("Nenhum token encontrado, redirecionando para login.");
        window.location.href = '/login';
    }

    const axiosApi = axios.create({
        baseURL: "http://127.0.0.1:8000",
        headers: {
            'Authorization': `Bearer ${token}`
        }
    });

    axiosApi.interceptors.response.use(
        (response) => response,
        (error) => {
            if (error.response && error.response.status === 401) {
                localStorage.removeItem('authToken');
                alert("Sua sessão expirou. Por favor, faça o login novamente.");
                window.location.href = "/login";
            }
            return Promise.reject(error);
        }
    );

    // ===============================================================
    // ==        2. FUNÇÕES DE GERENCIAMENTO DE SESSÕES             ==
    // ===============================================================

    const criarElementoSessao = (sessao) => {
        const sessaoItem = document.createElement('div');
        sessaoItem.className = 'sessao-item';
        
        const sessaoId = sessao._id || sessao.id || String(sessao);
        console.log('Criando elemento para sessão:', sessaoId, sessao);
        
        sessaoItem.dataset.id = sessaoId;
        
        const titulo = document.createElement('span');
        titulo.className = 'sessao-titulo';
        titulo.textContent = sessao.titulo || 'Nova Conversa';
        titulo.onclick = () => ativarSessao(sessaoId);
        
        const btnDeletar = document.createElement('button');
        btnDeletar.className = 'sessao-deletar';
        btnDeletar.innerHTML = '<i class="fas fa-trash"></i>';
        btnDeletar.onclick = (e) => {
            e.stopPropagation();
            deletarSessao(sessaoId);
        };
        
        sessaoItem.appendChild(titulo);
        sessaoItem.appendChild(btnDeletar);
        
        return sessaoItem;
    };

    const carregarSessoes = async (ativarPrimeira = true) => {
        try {
            const { data: sessoes } = await axiosApi.get('/sessoes');
            console.log('Sessões carregadas do servidor:', sessoes);
            
            sessoesListaEl.innerHTML = '';
            
            if (sessoes.length > 0) {
                const sessoesValidas = sessoes.filter(sessao => {
                    const temId = sessao._id || sessao.id;
                    if (!temId) {
                        console.warn('Sessão sem ID encontrada:', sessao);
                        return false;
                    }
                    return true;
                });
                
                console.log(`${sessoesValidas.length} de ${sessoes.length} sessões são válidas`);
                
                sessoesValidas.forEach(sessao => {
                    const sessaoItem = criarElementoSessao(sessao);
                    sessoesListaEl.appendChild(sessaoItem);
                });
                
                if (ativarPrimeira) {
                    chatEl.innerHTML = '';
                    appendMessage("Olá! Sou o <strong>TekBot</strong>. Como posso te ajudar hoje?", "left");
                }
            } else {
                chatEl.innerHTML = '';
                appendMessage("Olá! Sou o <strong>TekBot</strong>. Como posso te ajudar hoje?", "left");
            }
        } catch (error) {
            console.error("Erro ao carregar sessões:", error);
            alert("Erro ao carregar conversas. Verifique sua conexão.");
        }
    };

    const criarNovaSessaoInicial = async () => {
        try {
            const { data: novaSessao } = await axiosApi.post('/sessoes/criar');
            
            const sessaoItem = criarElementoSessao(novaSessao);
            sessoesListaEl.insertBefore(sessaoItem, sessoesListaEl.firstChild);
            
            ativarSessao(novaSessao._id);
        } catch (error) {
            console.error("Erro ao criar sessão inicial:", error);
        }
    };

    const criarNovaSessaoParaMensagem = async () => {
        try {
            console.log('Criando nova sessão...');
            const { data: novaSessao } = await axiosApi.post('/sessoes/criar');
            console.log('Sessão criada:', novaSessao);
            
            sessaoIdAtiva = novaSessao._id;
            
            const sessaoItem = criarElementoSessao(novaSessao);
            sessoesListaEl.insertBefore(sessaoItem, sessoesListaEl.firstChild);
            
            document.querySelectorAll('.sessao-item').forEach(item => {
                item.classList.toggle('ativa', item.dataset.id === sessaoIdAtiva);
            });
            
            console.log('Nova sessão ativa:', sessaoIdAtiva);
            return sessaoIdAtiva;
        } catch (error) {
            console.error("Erro ao criar nova sessão para mensagem:", error);
            throw error;
        }
    };

    const criarNovaSessao = async () => {
        try {
            const { data: novaSessao } = await axiosApi.post('/sessoes/criar');
            const sessaoItem = criarElementoSessao(novaSessao);
            sessoesListaEl.insertBefore(sessaoItem, sessoesListaEl.firstChild);
            ativarSessao(novaSessao._id);
        } catch (error) {
            console.error("Erro ao criar nova sessão:", error);
        }
    };

const deletarSessao = async (id) => {
    if (!id || id === 'undefined' || id === 'null' || id.includes('[object')) {
        console.error('ID de sessão inválido para deletar:', id);
        alert('Erro: Esta sessão está corrompida. Recarregue a página.');
        return;
    }

    const confirmar = await mostrarModalConfirmacao(
        'Excluir Conversa',
        'Tem certeza que deseja excluir esta conversa? Esta ação não pode ser desfeita.'
    );

    if (!confirmar) return;

    try {
        console.log(`Tentando deletar sessão: ${id}`);
        
        const response = await axiosApi.delete(`/sessoes/${id}`);
        console.log('Sessão deletada com sucesso:', response);
        
        const sessaoItem = document.querySelector(`.sessao-item[data-id="${id}"]`);
        if (sessaoItem) {
            sessaoItem.remove();
        }

        if (sessaoIdAtiva === id) {
            const primeiraRestante = sessoesListaEl.querySelector('.sessao-item');
            if (primeiraRestante) {
                ativarSessao(primeiraRestante.dataset.id);
            } else {
                sessaoIdAtiva = null;
                chatEl.innerHTML = '';
                appendMessage("Olá! Sou o <strong>TekBot</strong>. Como posso te ajudar hoje?", "left");
            }
        }
    } catch (error) {
        console.error("Erro detalhado ao deletar sessão:", error);
        console.error("ID da sessão:", id);
        console.error("Status da resposta:", error.response?.status);
        console.error("Dados da resposta:", error.response?.data);
        
        let mensagemErro = "Erro ao deletar a conversa.";
        
        if (error.response) {
            if (error.response.status === 404) {
                mensagemErro = "Esta conversa não existe mais.";
                const sessaoItem = document.querySelector(`.sessao-item[data-id="${id}"]`);
                if (sessaoItem) {
                    sessaoItem.remove();
                }
            } else if (error.response.status === 403) {
                mensagemErro = "Você não tem permissão para deletar esta conversa.";
            } else if (error.response.data?.detail) {
                mensagemErro = error.response.data.detail;
            }
        }
        
        alert(mensagemErro);
    }
};

function mostrarModalConfirmacao(titulo, mensagem) {
    return new Promise((resolve) => {
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        
        overlay.innerHTML = `
            <div class="modal-container">
                <div class="modal-header">
                    <div class="modal-icon">
                        <i class="fas fa-exclamation-triangle"></i>
                    </div>
                    <h3 class="modal-title">${titulo}</h3>
                </div>
                <div class="modal-body">
                    ${mensagem}
                </div>
                <div class="modal-footer">
                    <button class="modal-btn modal-btn-cancel">Cancelar</button>
                    <button class="modal-btn modal-btn-confirm">Excluir</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(overlay);
        
        const btnCancel = overlay.querySelector('.modal-btn-cancel');
        const btnConfirm = overlay.querySelector('.modal-btn-confirm');
        
        function fecharModal(resultado) {
            overlay.remove();
            resolve(resultado);
        }
        
        btnCancel.addEventListener('click', () => fecharModal(false));
        btnConfirm.addEventListener('click', () => fecharModal(true));
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) fecharModal(false);
        });
    });
}

    const ativarSessao = async (id) => {
        if (!id || id === 'undefined' || id === 'null' || id.includes('[object')) {
            console.error('ID de sessão inválido:', id);
            alert('Erro: ID de sessão inválido. Recarregando a página...');
            window.location.reload();
            return;
        }

        sessaoIdAtiva = id;
        chatEl.innerHTML = '';

        document.querySelectorAll('.sessao-item').forEach(item => {
            item.classList.toggle('ativa', item.dataset.id === id);
        });

        try {
            const { data: historico } = await axiosApi.get(`/sessoes/${id}/historico`);
            if (historico.length === 0) {
                appendMessage("Olá! Sou o <strong>TekBot</strong>. Como posso te ajudar hoje?", "left");
            } else {
                historico.forEach(interacao => {
                    appendMessage(interacao.pergunta, "right");
                    appendMessage(interacao.resposta.replace(/\n/g, "<br>"), "left");
                });
            }
        } catch (error) {
            console.error("Erro ao carregar histórico:", error);
        }
    };

    // ===============================================================
    // ==              3. LÓGICA DE ENVIO DE MENSAGEM               ==
    // ===============================================================

    chatFormEl.addEventListener("submit", async (e) => {
        e.preventDefault();
        const msg = userInputEl.value.trim();
        if (!msg) return;

        try {
            if (!sessaoIdAtiva) {
                console.log('Criando nova sessão para primeira mensagem...');
                await criarNovaSessaoParaMensagem();
            }

            if (!sessaoIdAtiva) {
                throw new Error('Não foi possível criar uma sessão');
            }

            appendMessage(msg, "right");
            userInputEl.value = "";
            const digitandoEl = appendTypingMessage();

            const { data } = await axiosApi.post(`/ia/responder?sessao_id=${sessaoIdAtiva}`, {
                pergunta: msg,
            });

            chatEl.removeChild(digitandoEl);
            const respostaFormatada = data.resposta.replace(/\n/g, "<br>");
            appendMessage(respostaFormatada, "left");

        } catch (error) {
            console.error("Erro ao chamar a IA:", error);
            appendMessage("Desculpe, ocorreu um erro. Tente novamente.", "left");
        }
    });

    // ===============================================================
    // ==                 4. EVENTOS E INICIALIZAÇÃO                ==
    // ===============================================================

    const fazerLogout = () => {
        localStorage.removeItem('authToken');
        window.location.href = "../html/login.html";
    };

    const limparSessaoCorrente = () => {
        const todosItens = sessoesListaEl.querySelectorAll('.sessao-item');
        todosItens.forEach(item => {
            const id = item.dataset.id;
            if (!id || id === 'undefined' || id === 'null' || id.includes('[object')) {
                console.log('Removendo sessão corrompida da interface:', id);
                item.remove();
            }
        });
        
        if (sessoesListaEl.children.length === 0) {
            criarNovaSessaoInicial();
        }
    };

    window.cleanSessions = limparSessaoCorrente;
    window.debugSessions = () => {
        console.log('=== DEBUG SESSÕES ===');
        console.log('Sessão ativa:', sessaoIdAtiva);
        console.log('Total de sessões na UI:', sessoesListaEl.children.length);
        const todosItens = Array.from(sessoesListaEl.querySelectorAll('.sessao-item'));
        todosItens.forEach((item, index) => {
            console.log(`Sessão ${index + 1}:`, {
                id: item.dataset.id,
                texto: item.querySelector('.sessao-titulo')?.textContent,
                ativa: item.classList.contains('ativa')
            });
        });
    };

    novaSessaoBtnEl.addEventListener('click', criarNovaSessao);
    logoutBtnEl.addEventListener('click', fazerLogout);

    const toggleSidebarBtn = document.getElementById('toggle-sidebar-btn');
    const sidebar = document.querySelector('.sidebar');
    const mainContainer = document.querySelector('.main-container');
    
    if (toggleSidebarBtn) {
        toggleSidebarBtn.addEventListener('click', () => {
            sidebar.classList.toggle('fechada');
            mainContainer.classList.toggle('sidebar-fechada');
        });
    }

    carregarSessoes();

});


// ===============================================================
// ==         SUAS FUNÇÕES PARA MANIPULAR A INTERFACE           ==
// ===============================================================

function appendMessage(message, side) {
    const chat = document.getElementById("chat");
    const wrapperHtml = `
    <div class="message-wrapper ${side}">
      ${side === "left" ? `<img class="avatar" src="../img/tekbot.png" alt="TekBot">` : ""}
      <div class="message-bubble ${side}">${message}</div>
      ${side === "right" ? `<img class="avatar" src="../img/usuario.png" alt="Usuário">` : ""}
    </div>
  `;
    chat.insertAdjacentHTML("beforeend", wrapperHtml);
    chat.scrollTop = chat.scrollHeight;
    return chat.lastElementChild;
}

function appendTypingMessage() {
    const chat = document.getElementById("chat");
    const wrapper = document.createElement("div");
    wrapper.className = "message-wrapper left";
    const avatar = document.createElement("img");
    avatar.className = "avatar";
    avatar.src = "../img/tekbot.png";
    avatar.alt = "TekBot";
    const bubble = document.createElement("div");
    bubble.className = "message-bubble left typing-bubble";
    bubble.innerHTML = `
    <div class="typing-indicator">
      <span></span><span></span><span></span>
    </div>
  `;
    wrapper.appendChild(avatar);
    wrapper.appendChild(bubble);
    chat.appendChild(wrapper);
    chat.scrollTop = chat.scrollHeight;
    return wrapper;
}