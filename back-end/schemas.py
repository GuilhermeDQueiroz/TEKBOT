from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

# ============= SCHEMAS DE USUÁRIO =============

class UsuarioCriar(BaseModel):
    """Schema para criar um novo usuário"""
    username: Optional[str] = None
    email: EmailStr
    senha: str = Field(..., min_length=6, description="Senha deve ter no mínimo 6 caracteres")

class UsuarioResposta(BaseModel):
    """Schema para resposta de usuário (sem dados sensíveis)"""
    email: EmailStr
    username: Optional[str] = None
    criado_em: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============= SCHEMAS DE AUTENTICAÇÃO =============

class Token(BaseModel):
    """Schema para token de autenticação"""
    access_token: str
    token_type: str = "bearer"

class RecuperacaoSenha(BaseModel):
    """Schema para solicitar recuperação de senha"""
    email: EmailStr

class RedefinirSenha(BaseModel):
    """Schema para redefinir senha com token"""
    token: str
    nova_senha: str = Field(..., min_length=6, description="Nova senha deve ter no mínimo 6 caracteres")


# ============= SCHEMAS DE CHATBOT/IA =============

class PerguntaEntrada(BaseModel):
    """Schema para entrada de pergunta do usuário"""
    pergunta: str = Field(..., min_length=1, max_length=1000, description="Pergunta do usuário")

class RespostaIA(BaseModel):
    """Schema para resposta da IA"""
    resposta: str
    sessao_id: Optional[str] = None
    timestamp: Optional[datetime] = None

class RequisicaoConsulta(BaseModel):
    """Schema para consulta no chatbot (compatibilidade)"""
    consulta: str = Field(..., min_length=1, max_length=1000)


# ============= SCHEMAS DE MENSAGENS/CONHECIMENTO =============

class MensagemEntrada(BaseModel):
    """Schema para adicionar mensagem/conhecimento à base"""
    texto: str = Field(..., min_length=1, description="Texto da mensagem")
    pergunta: Optional[str] = None
    resposta: Optional[str] = None
    tipo: Optional[str] = "base_conhecimento"

class MensagemResposta(BaseModel):
    """Schema para resposta de mensagem adicionada"""
    mensagem: str
    id: str


# ============= SCHEMAS DE SESSÕES (NOVOS) =============

class SessaoCriar(BaseModel):
    """Schema para criar nova sessão (vazio, pois dados vêm do token)"""
    pass

class SessaoResposta(BaseModel):
    """Schema para resposta de sessão"""
    id: str = Field(..., alias="_id")
    user_id: str
    titulo: str
    criado_em: datetime
    atualizado_em: datetime

    class Config:
        populate_by_name = True
        from_attributes = True

class SessaoListaItem(BaseModel):
    """Schema para item da lista de sessões"""
    id: str
    titulo: str
    atualizado_em: datetime
    total_mensagens: Optional[int] = 0


# ============= SCHEMAS DE INTERAÇÕES (NOVOS) =============

class InteracaoEntrada(BaseModel):
    """Schema para registrar interação"""
    sessao_id: str
    pergunta: str
    resposta: str
    documentos_relevantes: Optional[List[str]] = []

class InteracaoResposta(BaseModel):
    """Schema para resposta de interação"""
    id: str
    sessao_id: str
    pergunta: str
    resposta: str
    timestamp: datetime

    class Config:
        from_attributes = True

class HistoricoSessao(BaseModel):
    """Schema para histórico completo de uma sessão"""
    sessao_id: str
    titulo: str
    interacoes: List[InteracaoResposta]
    total: int


# ============= SCHEMAS DE TREINAMENTO =============

class TreinamentoEntrada(BaseModel):
    """Schema para adicionar novo conhecimento"""
    pergunta: str = Field(..., min_length=5, description="Pergunta de exemplo")
    resposta: str = Field(..., min_length=10, description="Resposta correta")

class TreinamentoResposta(BaseModel):
    """Schema para resposta de treinamento"""
    mensagem: str
    pergunta_id: Optional[str] = None


# ============= SCHEMAS DE VALIDAÇÃO =============

class ErroResposta(BaseModel):
    """Schema padrão para respostas de erro"""
    detail: str
    status_code: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class SucessoResposta(BaseModel):
    """Schema padrão para respostas de sucesso"""
    mensagem: str
    dados: Optional[dict] = None

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

# Schemas de Mensagens
class MensagemTicket(BaseModel):
    remetente_email: str
    remetente_nome: Optional[str] = None
    conteudo: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    is_atendente: bool = False
    anexos: Optional[List[str]] = []

# Schemas de Tickets
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

# Schemas de Dashboard
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