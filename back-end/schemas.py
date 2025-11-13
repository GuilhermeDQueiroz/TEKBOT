# ============= SCHEMAS COMPLETOS COM WEBHOOK =============
# Cole este arquivo inteiro substituindo o seu schemas.py
# Ou copie apenas a seção de WEBHOOK e adicione ao final do seu schemas.py

from pydantic import BaseModel, EmailStr, Field, validator, HttpUrl
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum

# ============= SCHEMAS DE USUÁRIO =============

class UsuarioCriar(BaseModel):
    username: Optional[str] = None
    email: EmailStr
    senha: str = Field(..., min_length=6)

class UsuarioResposta(BaseModel):
    email: EmailStr
    username: Optional[str] = None
    criado_em: Optional[datetime] = None
    class Config:
        from_attributes = True

# ============= SCHEMAS DE AUTENTICAÇÃO =============

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class RecuperacaoSenha(BaseModel):
    email: EmailStr

class RedefinirSenha(BaseModel):
    token: str
    nova_senha: str = Field(..., min_length=6)

# ============= SCHEMAS DE CHATBOT/IA =============

class PerguntaEntrada(BaseModel):
    pergunta: str = Field(..., min_length=1, max_length=1000)

class RespostaIA(BaseModel):
    resposta: str
    sessao_id: Optional[str] = None
    timestamp: Optional[datetime] = None

class RequisicaoConsulta(BaseModel):
    consulta: str = Field(..., min_length=1, max_length=1000)

# ============= SCHEMAS DE MENSAGENS/CONHECIMENTO =============

class MensagemEntrada(BaseModel):
    texto: str = Field(..., min_length=1)
    pergunta: Optional[str] = None
    resposta: Optional[str] = None
    tipo: Optional[str] = "base_conhecimento"

class MensagemResposta(BaseModel):
    mensagem: str
    id: str

# ============= SCHEMAS DE SESSÕES =============

class SessaoCriar(BaseModel):
    pass

class SessaoResposta(BaseModel):
    id: str = Field(..., alias="_id")
    user_id: str
    titulo: str
    criado_em: datetime
    atualizado_em: datetime
    class Config:
        populate_by_name = True
        from_attributes = True

class SessaoListaItem(BaseModel):
    id: str
    titulo: str
    atualizado_em: datetime
    total_mensagens: Optional[int] = 0

# ============= SCHEMAS DE INTERAÇÕES =============

class InteracaoEntrada(BaseModel):
    sessao_id: str
    pergunta: str
    resposta: str
    documentos_relevantes: Optional[List[str]] = []

class InteracaoResposta(BaseModel):
    id: str
    sessao_id: str
    pergunta: str
    resposta: str
    timestamp: datetime
    class Config:
        from_attributes = True

class HistoricoSessao(BaseModel):
    sessao_id: str
    titulo: str
    interacoes: List[InteracaoResposta]
    total: int

# ============= SCHEMAS DE TREINAMENTO =============

class TreinamentoEntrada(BaseModel):
    pergunta: str = Field(..., min_length=10, max_length=1000)
    resposta: str = Field(..., min_length=10, max_length=5000)
    categoria: Optional[str] = Field(None)
    tags: Optional[List[str]] = Field(default=[])
    
    @validator('pergunta')
    def validar_pergunta(cls, v):
        if not v or v.strip() == "":
            raise ValueError("Pergunta não pode estar vazia")
        return v.strip()
    
    @validator('resposta')
    def validar_resposta(cls, v):
        if not v or v.strip() == "":
            raise ValueError("Resposta não pode estar vazia")
        return v.strip()

class TreinamentoResposta(BaseModel):
    mensagem: str
    pergunta_id: Optional[str] = None

# ============= SCHEMAS DE VALIDAÇÃO =============

class ErroResposta(BaseModel):
    detail: str
    status_code: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class SucessoResposta(BaseModel):
    mensagem: str
    dados: Optional[dict] = None

# ============= SCHEMAS DE TICKETS =============

class PrioridadeTicket(str, Enum):
    BAIXA = "baixa"
    MEDIA = "media"
    ALTA = "alta"
    CRITICA = "critica"

class StatusTicket(str, Enum):
    ABERTO = "aberto"
    EM_ATENDIMENTO = "em_atendimento"
    AGUARDANDO_CLIENTE = "aguardando_cliente"
    RESOLVIDO = "resolvido"
    FECHADO = "fechado"

class CategoriaTicket(str, Enum):
    TECNICO = "tecnico"
    FINANCEIRO = "financeiro"
    DUVIDA = "duvida"
    BUG = "bug"
    FEATURE = "feature"
    OUTRO = "outro"

class TipoUsuario(str, Enum):
    CLIENTE = "cliente"
    ATENDENTE = "atendente"
    ADMIN = "admin"

class MensagemTicket(BaseModel):
    remetente_email: str
    remetente_nome: Optional[str] = None
    conteudo: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    is_atendente: bool = False
    anexos: Optional[List[str]] = []

class TicketCriar(BaseModel):
    titulo: str = Field(..., min_length=5, max_length=200)
    descricao: str = Field(..., min_length=10)
    categoria: CategoriaTicket = CategoriaTicket.DUVIDA
    prioridade_manual: Optional[PrioridadeTicket] = None

class TicketAtualizar(BaseModel):
    status: Optional[StatusTicket] = None
    prioridade: Optional[PrioridadeTicket] = None
    observacoes: Optional[str] = None

class TicketResposta(BaseModel):
    id: str
    numero_ticket: str
    titulo: str
    descricao: str
    categoria: CategoriaTicket
    prioridade: PrioridadeTicket
    status: StatusTicket
    email_cliente: str
    nome_cliente: Optional[str] = None
    atendente_email: Optional[str] = None
    atendente_nome: Optional[str] = None
    data_criacao: datetime
    data_atualizacao: datetime
    data_atribuicao: Optional[datetime] = None
    data_resolucao: Optional[datetime] = None
    tempo_resposta_minutos: Optional[int] = None
    tempo_resolucao_minutos: Optional[int] = None
    mensagens: List[MensagemTicket] = []
    observacoes: Optional[str] = None
    score_prioridade: float = 0

class AdicionarMensagemTicket(BaseModel):
    conteudo: str = Field(..., min_length=1)

class AtribuirTicket(BaseModel):
    ticket_id: str

class FiltroTickets(BaseModel):
    status: Optional[List[StatusTicket]] = None
    prioridade: Optional[List[PrioridadeTicket]] = None
    categoria: Optional[List[CategoriaTicket]] = None
    apenas_meus: bool = False

class EstatisticasAtendente(BaseModel):
    total_tickets_atribuidos: int
    tickets_em_atendimento: int
    tickets_resolvidos_hoje: int
    tickets_resolvidos_semana: int
    tempo_medio_resposta_minutos: float
    tempo_medio_resolucao_minutos: float
    taxa_resolucao_percentual: float

class DashboardMetricas(BaseModel):
    total_tickets: int
    tickets_abertos: int
    tickets_em_atendimento: int
    tickets_aguardando: int
    tickets_resolvidos_hoje: int
    tickets_criados_hoje: int
    tempo_medio_resposta_minutos: float
    tempo_medio_resolucao_minutos: float
    distribuicao_prioridade: dict
    distribuicao_categoria: dict
    distribuicao_status: dict
    atendentes_online: int
    tickets_criticos_pendentes: int

class TopAtendente(BaseModel):
    email: str
    nome: Optional[str] = None
    tickets_resolvidos: int
    tempo_medio_minutos: float
    taxa_resolucao: float

class UsuarioInfo(BaseModel):
    email: EmailStr
    tipo_usuario: TipoUsuario = TipoUsuario.CLIENTE
    nome_completo: Optional[str] = None
    criado_em: datetime

class AtualizarPerfilAtendente(BaseModel):
    nome_completo: Optional[str] = None
    telefone: Optional[str] = None
    disponivel: bool = True

# ============= SCHEMAS DE WEBHOOK =============

class NivelFeedback(str, Enum):
    """Níveis de feedback possíveis"""
    BAIXO = "baixo"
    MEDIO = "medio"
    ALTO = "alto"

class StatusWebhook(str, Enum):
    """Status do envio de webhook"""
    PENDENTE = "pendente"
    ENVIADO = "enviado"
    SUCESSO = "sucesso"
    FALHA = "falha"
    TIMEOUT = "timeout"

class WebhookConfig(BaseModel):
    """Configuração do webhook"""
    url: HttpUrl = Field(..., description="URL do webhook do terceiro")
    secret_key: str = Field(..., min_length=32, description="Chave secreta para assinatura")
    ativo: bool = Field(default=True)
    timeout_segundos: int = Field(default=30, ge=5, le=120)
    max_tentativas: int = Field(default=3, ge=1, le=10)
    
    @validator('secret_key')
    def validar_secret_key(cls, v):
        if len(v) < 32:
            raise ValueError("Secret key deve ter no mínimo 32 caracteres")
        return v

class WebhookConfigResposta(BaseModel):
    """Resposta ao configurar webhook"""
    id: str
    url: str
    ativo: bool
    criado_em: datetime
    atualizado_em: datetime

class DadosSessao(BaseModel):
    """Dados da sessão enviados ao webhook"""
    sessao_id: str
    user_email: str
    titulo: str
    total_interacoes: int
    data_criacao: str
    data_ultima_interacao: str
    interacoes: List[Dict]

class FeedbackAnalise(BaseModel):
    """Feedback detalhado da análise"""
    nivel: NivelFeedback = Field(..., description="Nível do feedback: baixo, medio ou alto")
    pontuacao: float = Field(..., ge=0, le=10, description="Pontuação de 0 a 10")
    comentarios: Optional[str] = Field(None, description="Comentários adicionais")
    metricas: Optional[Dict] = Field(None, description="Métricas adicionais")
    sugestoes: Optional[List[str]] = Field(None, description="Sugestões de melhoria")

class WebhookResposta(BaseModel):
    """Resposta esperada do webhook terceiro"""
    sessao_id: str
    analise: FeedbackAnalise
    timestamp_analise: datetime = Field(default_factory=datetime.utcnow)
    analisado_por: Optional[str] = Field(None)

class FeedbackSessaoCompleto(BaseModel):
    """Feedback completo armazenado no banco"""
    id: str = Field(..., alias="_id")
    sessao_id: str
    user_email: str
    nivel: NivelFeedback
    pontuacao: float
    comentarios: Optional[str]
    metricas: Optional[Dict]
    sugestoes: Optional[List[str]]
    data_analise: datetime
    analisado_por: Optional[str]
    
    class Config:
        populate_by_name = True

class EstatisticasFeedback(BaseModel):
    """Estatísticas dos feedbacks recebidos"""
    total_sessoes_analisadas: int
    distribuicao_nivel: Dict[str, int]
    pontuacao_media: float
    pontuacao_mediana: float
    sessoes_alto_nivel: int
    sessoes_medio_nivel: int
    sessoes_baixo_nivel: int
    ultima_atualizacao: datetime

class ListaFeedbacks(BaseModel):
    """Lista de feedbacks com paginação"""
    feedbacks: List[FeedbackSessaoCompleto]
    total: int
    pagina: int
    tamanho_pagina: int

class WebhookTesteResposta(BaseModel):
    """Resposta do teste de webhook"""
    sucesso: bool
    mensagem: str
    tempo_resposta_ms: int
    codigo_http: int

class LogWebhook(BaseModel):
    """Log de envio de webhook"""
    sessao_id: str
    status: StatusWebhook
    tentativa: int
    url_destino: str
    tempo_resposta_ms: Optional[int]
    codigo_http: Optional[int]
    erro: Optional[str]
    timestamp: datetime = Field(default_factory=datetime.utcnow)