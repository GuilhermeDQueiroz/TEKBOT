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

    // Opcional: configurar o marked (padrões)
    // Você pode ajustar opções aqui se quiser:
    // marked.setOptions({ gfm: true, breaks: true });

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
                    // antes convertíamos \n -> <br>, agora deixamos o texto cru para o marked tratar que aceita quebras (opção breaks pode ser ativada)
                    appendMessage(interacao.resposta, "left");
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
            // usar texto cru; marked fará o parsing do Markdown
            appendMessage(data.resposta, "left");

        } catch (error) {
            console.error("Erro ao chamar a IA:", error);
            appendMessage("Desculpe, ocorreu um erro. Tente novamente.", "left");
        }
    });

    // ===============================================================
    // ==           4. FUNCIONALIDADE DE CRIAR TICKET               ==
    // ===============================================================

    const criarTicketBtn = document.getElementById('criar-ticket-btn');
    const modalTicket = document.getElementById('modal-ticket');
    const fecharModalTicket = document.getElementById('fechar-modal-ticket');
    const cancelarTicket = document.getElementById('cancelar-ticket');
    const confirmarTicket = document.getElementById('confirmar-ticket');
    const formTicket = document.getElementById('form-ticket');

    if (criarTicketBtn) {
        criarTicketBtn.addEventListener('click', () => {
            console.log('Abrindo modal de criar ticket');
            console.log('Sessão ativa atual:', sessaoIdAtiva);
            modalTicket.style.display = 'flex';
            document.getElementById('ticket-titulo').focus();
        });
    }

    const fecharModalTicketFn = () => {
        modalTicket.style.display = 'none';
        formTicket.reset();
    };

    if (fecharModalTicket) {
        fecharModalTicket.addEventListener('click', fecharModalTicketFn);
    }

    if (cancelarTicket) {
        cancelarTicket.addEventListener('click', fecharModalTicketFn);
    }

    modalTicket.addEventListener('click', (e) => {
        if (e.target === modalTicket) {
            fecharModalTicketFn();
        }
    });

    if (confirmarTicket) {
        confirmarTicket.addEventListener('click', async () => {
            const titulo = document.getElementById('ticket-titulo').value.trim();
            const categoria = document.getElementById('ticket-categoria').value;
            const descricao = document.getElementById('ticket-descricao').value.trim();
            const incluirHistorico = document.getElementById('ticket-incluir-historico').checked;

            console.log('=== DADOS DO FORMULÁRIO ===');
            console.log('Título:', titulo);
            console.log('Categoria:', categoria);
            console.log('Descrição:', descricao);
            console.log('Incluir histórico:', incluirHistorico);
            console.log('Sessão ativa:', sessaoIdAtiva);

            // Validação
            if (!titulo) {
                alert('Por favor, preencha o título do ticket.');
                document.getElementById('ticket-titulo').focus();
                return;
            }

            if (titulo.length < 5) {
                alert('O título deve ter pelo menos 5 caracteres.');
                document.getElementById('ticket-titulo').focus();
                return;
            }

            if (!categoria) {
                alert('Por favor, selecione uma categoria.');
                document.getElementById('ticket-categoria').focus();
                return;
            }

            if (!descricao) {
                alert('Por favor, preencha a descrição do ticket.');
                document.getElementById('ticket-descricao').focus();
                return;
            }

            if (descricao.length < 20) {
                alert('A descrição deve ter pelo menos 20 caracteres para melhor análise.');
                document.getElementById('ticket-descricao').focus();
                return;
            }

            try {
                confirmarTicket.disabled = true;
                confirmarTicket.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Criando ticket...';

                let historicoTexto = '';
                
                if (incluirHistorico && sessaoIdAtiva) {
                    try {
                        console.log('Obtendo histórico da sessão:', sessaoIdAtiva);
                        const { data: historicoData } = await axiosApi.get(`/sessoes/${sessaoIdAtiva}/historico`);
                        console.log('Histórico obtido:', historicoData);
                        
                        if (historicoData && historicoData.length > 0) {
                            historicoTexto = '\n\n=== HISTÓRICO DA CONVERSA ===\n\n';
                            historicoData.forEach((interacao, index) => {
                                historicoTexto += `[${index + 1}] Usuário: ${interacao.pergunta}\n`;
                                historicoTexto += `Bot: ${interacao.resposta}\n\n`;
                            });
                        }
                    } catch (error) {
                        console.warn('Não foi possível obter o histórico:', error);
                    }
                }

                const ticketData = {
                    titulo: titulo,
                    categoria: categoria,
                    descricao: descricao + historicoTexto,
                    sessao_id: sessaoIdAtiva
                };

                console.log('=== ENVIANDO PARA API ===');
                console.log('Dados:', ticketData);

                const response = await axiosApi.post('/tickets/criar', ticketData);
                
                console.log('=== RESPOSTA DA API ===');
                console.log('Status:', response.status);
                console.log('Dados:', response.data);
                
                const ticketCriado = response.data;

                fecharModalTicketFn();
                
                const numeroTicket = ticketCriado.numero_ticket || ticketCriado._id || 'N/A';
                
                // ========================================
                // MENSAGEM SIMPLIFICADA PARA O CLIENTE
                // Apenas número do ticket e confirmação
                // ========================================
                let mensagemSucesso = `Seu ticket <strong>#${numeroTicket}</strong> foi criado com sucesso!<br><br>`;
                mensagemSucesso += `Nossa equipe de suporte entrará em contato em breve.`;
                
                await mostrarModalSucesso('Ticket Criado!', mensagemSucesso);

                // Mensagem simples no chat
                let mensagemChat = `✅ <strong>Ticket #${numeroTicket} criado com sucesso!</strong><br>`;
                mensagemChat += `<em>Nossa equipe entrará em contato em breve.</em>`;
                
                appendMessage(mensagemChat, "left");

                // ========================================
                // LOG COMPLETO NO CONSOLE (PARA DEBUG)
                // Toda análise da IA fica aqui
                // ========================================
                console.log('=== ANÁLISE COMPLETA DA IA (NÃO VISÍVEL AO CLIENTE) ===');
                console.log('✓ Ticket criado:', numeroTicket);
                console.log('✓ Prioridade definida:', ticketCriado.prioridade);
                console.log('✓ Score:', ticketCriado.score_prioridade);
                console.log('✓ Categoria:', ticketCriado.categoria);
                
                if (ticketCriado.analise_ia) {
                    console.log('✓ Urgência:', ticketCriado.analise_ia.urgencia, '/10');
                    console.log('✓ Impacto:', ticketCriado.analise_ia.impacto);
                    console.log('✓ Justificativa:', ticketCriado.analise_ia.justificativa);
                    console.log('✓ Resumo:', ticketCriado.analise_ia.resumo);
                    console.log('✓ Tempo estimado:', ticketCriado.analise_ia.tempo_estimado_resolucao);
                    console.log('✓ Requer atenção imediata:', ticketCriado.analise_ia.requer_atencao_imediata);
                }
                
                if (ticketCriado.recomendacoes && ticketCriado.recomendacoes.length > 0) {
                    console.log('✓ Recomendações:', ticketCriado.recomendacoes);
                }
                
                if (ticketCriado.tickets_similares && ticketCriado.tickets_similares.length > 0) {
                    console.log('✓ Tickets similares encontrados:', ticketCriado.tickets_similares.length);
                    ticketCriado.tickets_similares.forEach((similar, idx) => {
                        console.log(`  ${idx + 1}. #${similar.numero} - Similaridade: ${(similar.similaridade * 100).toFixed(1)}%`);
                    });
                }

            } catch (error) {
                console.error('=== ERRO AO CRIAR TICKET ===');
                console.error('Erro completo:', error);
                console.error('Resposta:', error.response);
                
                let mensagemErro = 'Erro ao criar ticket. Tente novamente.';
                
                if (error.response) {
                    console.error('Status:', error.response.status);
                    console.error('Data:', error.response.data);
                    
                    if (error.response.status === 404) {
                        mensagemErro = 'Rota não encontrada. Verifique se o backend está rodando.';
                    } else if (error.response.status === 401) {
                        mensagemErro = 'Sessão expirou. Redirecionando para login...';
                        setTimeout(() => {
                            window.location.href = '/login';
                        }, 2000);
                    } else if (error.response.status === 422) {
                        const detalhes = error.response.data?.detail;
                        if (Array.isArray(detalhes)) {
                            mensagemErro = 'Dados inválidos:\n' + detalhes.map(d => `- ${d.msg}`).join('\n');
                        } else {
                            mensagemErro = 'Dados inválidos no formulário.';
                        }
                    } else if (error.response.data?.detail) {
                        mensagemErro = error.response.data.detail;
                    } else if (error.response.data?.message) {
                        mensagemErro = error.response.data.message;
                    }
                } else if (error.request) {
                    console.error('Sem resposta do servidor');
                    mensagemErro = 'Não foi possível conectar ao servidor. Verifique sua conexão.';
                } else {
                    console.error('Erro:', error.message);
                    mensagemErro = error.message;
                }
                
                alert(mensagemErro);
                
            } finally {
                confirmarTicket.disabled = false;
                confirmarTicket.innerHTML = '<i class="fas fa-paper-plane"></i> Criar Ticket';
            }
        });
    }

    function mostrarModalSucesso(titulo, mensagem) {
        return new Promise((resolve) => {
            const overlay = document.createElement('div');
            overlay.className = 'modal-overlay';
            
            overlay.innerHTML = `
                <div class="modal-container">
                    <div class="modal-header">
                        <div class="modal-icon modal-icon-success">
                            <i class="fas fa-check-circle"></i>
                        </div>
                        <h3 class="modal-title">${titulo}</h3>
                    </div>
                    <div class="modal-body">
                        ${mensagem}
                    </div>
                    <div class="modal-footer">
                        <button class="modal-btn modal-btn-success">OK</button>
                    </div>
                </div>
            `;
            
            document.body.appendChild(overlay);
            
            const btnOk = overlay.querySelector('.modal-btn-success');
            
            function fecharModal() {
                overlay.remove();
                resolve(true);
            }
            
            btnOk.addEventListener('click', fecharModal);
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) fecharModal();
            });
        });
    }

    // ===============================================================
    // ==                 5. EVENTOS E INICIALIZAÇÃO                ==
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
// ==         FUNÇÕES GLOBAIS (FORA DO DOMContentLoaded)         ==
// ===============================================================

function appendMessage(message, side) {
    const chat = document.getElementById("chat");
    const wrapperHtml = `
    <div class="message-wrapper ${side}">
      ${side === "left" ? `<img class="avatar" src="../img/tekbot.png" alt="TekBot">` : ""}
      <div class="message-bubble ${side}">${/* aqui usaremos marked para converter Markdown */ ''}</div>
      ${side === "right" ? `<img class="avatar" src="../img/usuario.png" alt="Usuário">` : ""}
    </div>
  `;
    // Inserimos o wrapper e depois preenchemos o conteúdo do bubble com marked
    chat.insertAdjacentHTML("beforeend", wrapperHtml);

    // Pega o último elemento criado (mensagem)
    const last = chat.lastElementChild;
    if (last) {
        const bubble = last.querySelector('.message-bubble');
        try {
            // Usamos marked.parse para transformar Markdown (ex: **negrito**) em HTML
            bubble.innerHTML = marked.parse(String(message));
        } catch (err) {
            // Se algo der errado, mostramos o texto cru
            console.error('Erro ao parsear Markdown:', err);
            bubble.textContent = message;
        }
    }

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

function appendMessage(message, side) {
    const chat = document.getElementById("chat");
    const wrapperHtml = `
    <div class="message-wrapper ${side}">
      ${side === "left" ? `<img class="avatar" src="../img/tekbot.png" alt="TekBot">` : ""}
      <div class="message-bubble ${side}"></div>
      ${side === "right" ? `<img class="avatar" src="../img/usuario.png" alt="Usuário">` : ""}
    </div>
  `;
    // Inserimos o wrapper e depois preenchemos o conteúdo do bubble com marked
    chat.insertAdjacentHTML("beforeend", wrapperHtml);

    // Pega o último elemento criado (mensagem)
    const last = chat.lastElementChild;
    if (last) {
        const bubble = last.querySelector('.message-bubble');
        try {
            // Usa marked.parse para transformar Markdown (ex: **negrito**) em HTML
            bubble.innerHTML = marked.parse(String(message));
        } catch (err) {
            // Se algo der errado, mostramos o texto cru
            console.error('Erro ao parsear Markdown:', err);
            bubble.textContent = message;
        }
    }

    chat.scrollTop = chat.scrollHeight;
    return chat.lastElementChild;
}
