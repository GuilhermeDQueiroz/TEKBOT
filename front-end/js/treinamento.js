// ================================================================
// TREINAMENTO DA IA - JavaScript (SEM AUTENTICAÇÃO)
// ================================================================

const API_URL = 'http://localhost:8000';

// Estado da aplicação
const state = {
    tags: [],
    treinamentos: [],
    loading: false
};

// ================================================================
// INICIALIZAÇÃO
// ================================================================

document.addEventListener('DOMContentLoaded', () => {
    
    inicializarTabs();
    inicializarFormulario();
    inicializarTags();
});

// ================================================================
// TABS
// ================================================================

function inicializarTabs() {
    const tabs = document.querySelectorAll('.tab');
    
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const tabName = tab.dataset.tab;
            
            // Atualizar tabs ativos
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            
            tab.classList.add('active');
            document.getElementById(tabName).classList.add('active');
            
            // Carregar dados se for a aba de lista
            if (tabName === 'lista') {
                carregarTreinamentos();
            }
        });
    });
}

// ================================================================
// FORMULÁRIO
// ================================================================

function inicializarFormulario() {
    const form = document.getElementById('formTreinamento');
    
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        await salvarTreinamento();
    });
}

async function salvarTreinamento() {
    const btnSalvar = document.getElementById('btnSalvar');
    const pergunta = document.getElementById('pergunta').value.trim();
    const resposta = document.getElementById('resposta').value.trim();
    const categoria = document.getElementById('categoria').value;
    
    // Validação
    if (pergunta.length < 10) {
        mostrarAlerta('A pergunta deve ter no mínimo 10 caracteres', 'error');
        return;
    }
    
    if (resposta.length < 10) {
        mostrarAlerta('A resposta deve ter no mínimo 10 caracteres', 'error');
        return;
    }
    
    // Desabilitar botão
    btnSalvar.disabled = true;
    btnSalvar.innerHTML = '<span>⏳</span> Salvando...';
    
    try {
        const dados = {
            pergunta: pergunta,
            resposta: resposta,
            categoria: categoria || null,
            tags: state.tags
        };
        
        
        const response = await fetch(`${API_URL}/treinamento/adicionar-publico`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(dados)
        });
        
        const resultado = await response.json();
        
        if (!response.ok) {
            throw new Error(resultado.detail || 'Erro ao salvar treinamento');
        }
        
        
        mostrarAlerta('✅ Treinamento adicionado com sucesso! O embedding foi gerado automaticamente.', 'success');
        
        // Limpar formulário
        document.getElementById('formTreinamento').reset();
        state.tags = [];
        atualizarTagsVisuais();
        
        // Refocar no primeiro campo
        setTimeout(() => {
            document.getElementById('pergunta').focus();
        }, 100);
        
    } catch (error) {
        mostrarAlerta('❌ ' + error.message, 'error');
    } finally {
        btnSalvar.disabled = false;
        btnSalvar.innerHTML = '<span>💾</span> Salvar Treinamento';
    }
}

// ================================================================
// SISTEMA DE TAGS
// ================================================================

function inicializarTags() {
    const input = document.getElementById('tagsInput');
    const container = document.getElementById('tagsContainer');
    
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ',') {
            e.preventDefault();
            adicionarTag(input.value.trim());
            input.value = '';
        }
    });
    
    input.addEventListener('blur', () => {
        if (input.value.trim()) {
            adicionarTag(input.value.trim());
            input.value = '';
        }
    });
    
    container.addEventListener('click', () => {
        input.focus();
    });
}

function adicionarTag(texto) {
    if (!texto || state.tags.includes(texto.toLowerCase())) {
        return;
    }
    
    state.tags.push(texto.toLowerCase());
    atualizarTagsVisuais();
}

function removerTag(index) {
    state.tags.splice(index, 1);
    atualizarTagsVisuais();
}

function atualizarTagsVisuais() {
    const container = document.getElementById('tagsContainer');
    const input = document.getElementById('tagsInput');
    
    // Remover tags antigas
    container.querySelectorAll('.tag').forEach(tag => tag.remove());
    
    // Adicionar novas tags
    state.tags.forEach((tag, index) => {
        const tagElement = document.createElement('div');
        tagElement.className = 'tag';
        tagElement.innerHTML = `
            ${tag}
            <button type="button" onclick="removerTag(${index})">×</button>
        `;
        container.insertBefore(tagElement, input);
    });
}

// Expor função para HTML
window.removerTag = removerTag;

// ================================================================
// LISTA DE TREINAMENTOS
// ================================================================

async function carregarTreinamentos() {
    const loading = document.getElementById('loadingLista');
    const lista = document.getElementById('listaTreinamentos');
    
    loading.classList.add('active');
    lista.innerHTML = '';
    
    try {
        const response = await fetch(`${API_URL}/treinamento/listar-publico?limit=100`);
        
        if (!response.ok) {
            throw new Error('Erro ao carregar treinamentos');
        }
        
        const dados = await response.json();
        
        
        state.treinamentos = dados.treinamentos || [];
        
        // Renderizar lista
        if (state.treinamentos.length === 0) {
            lista.innerHTML = `
                <div style="text-align: center; padding: 60px 20px; color: #999;">
                    <div style="font-size: 48px; margin-bottom: 15px;">📚</div>
                    <p>Nenhum treinamento cadastrado ainda.</p>
                    <p style="font-size: 14px; margin-top: 10px;">Comece adicionando novos conhecimentos para a IA!</p>
                </div>
            `;
        } else {
            state.treinamentos.forEach(treinamento => {
                lista.appendChild(criarItemTreinamento(treinamento));
            });
        }
        
    } catch (error) {
        lista.innerHTML = `
            <div style="text-align: center; padding: 40px; color: #dc3545;">
                <p>❌ Erro ao carregar treinamentos</p>
                <p style="font-size: 14px; margin-top: 10px;">${error.message}</p>
            </div>
        `;
    } finally {
        loading.classList.remove('active');
    }
}

function criarItemTreinamento(treinamento) {
    const item = document.createElement('div');
    item.className = 'training-item';
    
    const dataFormatada = new Date(treinamento.criado_em).toLocaleDateString('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
    
    const tagsHTML = treinamento.tags && treinamento.tags.length > 0
        ? `<div class="tags">
            ${treinamento.tags.map(tag => `<span class="tag">${tag}</span>`).join('')}
           </div>`
        : '';
    
    item.innerHTML = `
        <h3>❓ ${treinamento.pergunta}</h3>
        <p><strong>Resposta:</strong> ${treinamento.resposta}</p>
        <div class="meta">
            <span>📅 ${dataFormatada}</span>
            ${treinamento.criado_por ? `<span>👤 ${treinamento.criado_por}</span>` : '<span>👤 Desenvolvedor</span>'}
            ${treinamento.categoria ? `<span>🏷️ ${treinamento.categoria}</span>` : ''}
        </div>
        ${tagsHTML}
    `;
    
    return item;
}

// ================================================================
// ALERTAS
// ================================================================

function mostrarAlerta(mensagem, tipo) {
    const container = document.getElementById('alertContainer');
    
    const icones = {
        success: '✅',
        error: '❌',
        info: 'ℹ️'
    };
    
    const alert = document.createElement('div');
    alert.className = `alert alert-${tipo}`;
    alert.innerHTML = `
        <span style="font-size: 20px;">${icones[tipo]}</span>
        <span>${mensagem}</span>
    `;
    
    container.appendChild(alert);
    
    // Remover após 5 segundos
    setTimeout(() => {
        alert.style.transition = 'opacity 0.3s';
        alert.style.opacity = '0';
        setTimeout(() => alert.remove(), 300);
    }, 5000);
    
    // Scroll suave para o topo
    window.scrollTo({ top: 0, behavior: 'smooth' });
}