from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

# ============= MODELS DE AUTENTICAÇÃO =============

class UsuarioLogin(BaseModel):
    """Model para login de usuário"""
    email: EmailStr
    senha: str

class Token(BaseModel):
    """Model para token JWT"""
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    """Model para dados extraídos do token"""
    email: Optional[str] = None
    user_id: Optional[str] = None


# ============= MODELS DE USUÁRIO =============

class Usuario(BaseModel):
    """Model completo de usuário"""
    id: Optional[str] = Field(None, alias="_id")
    email: EmailStr
    senha: str  # Hash da senha
    username: Optional[str] = None
    criado_em: Optional[datetime] = None
    ativo: bool = True

    class Config:
        populate_by_name = True
        from_attributes = True

class UsuarioPublico(BaseModel):
    """Model de usuário sem dados sensíveis"""
    id: str
    email: EmailStr
    username: Optional[str] = None
    criado_em: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============= MODELS DE SESSÃO =============

class Sessao(BaseModel):
    """Model de sessão de conversa"""
    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    titulo: str = "Nova Conversa"
    criado_em: datetime
    atualizado_em: datetime
    ativo: bool = True

    class Config:
        populate_by_name = True
        from_attributes = True


# ============= MODELS DE INTERAÇÃO =============

class Interacao(BaseModel):
    """Model de interação (pergunta/resposta)"""
    id: Optional[str] = Field(None, alias="_id")
    sessao_id: str
    user_id: str
    pergunta: str
    resposta: str
    documentos_relevantes: Optional[list] = []
    timestamp: datetime
    avaliacao: Optional[int] = None  # 1-5 estrelas

    class Config:
        populate_by_name = True
        from_attributes = True


# ============= MODELS DE MENSAGEM/CONHECIMENTO =============

class Mensagem(BaseModel):
    """Model de mensagem na base de conhecimento"""
    id: Optional[str] = Field(None, alias="_id")
    tipo: str = "base_conhecimento"
    texto: Optional[str] = None
    pergunta: Optional[str] = None
    resposta: Optional[str] = None
    embedding: Optional[list] = None
    user_id: Optional[str] = None
    criado_em: datetime
    ativo: bool = True

    class Config:
        populate_by_name = True
        from_attributes = True


# ============= MODELS DE RESPOSTA DE API =============

class RespostaAPI(BaseModel):
    """Model genérico para respostas de sucesso"""
    sucesso: bool = True
    mensagem: str
    dados: Optional[dict] = None

class ErroAPI(BaseModel):
    """Model genérico para respostas de erro"""
    sucesso: bool = False
    erro: str
    detalhes: Optional[str] = None
    codigo: int


# ============= MODELS DE ESTATÍSTICAS =============

class EstatisticasUsuario(BaseModel):
    """Model para estatísticas do usuário"""
    total_sessoes: int = 0
    total_mensagens: int = 0
    ultima_atividade: Optional[datetime] = None
    sessoes_ativas: int = 0

class EstatisticasSessao(BaseModel):
    """Model para estatísticas de uma sessão"""
    sessao_id: str
    total_interacoes: int
    duracao_minutos: Optional[float] = None
    primeira_mensagem: Optional[datetime] = None
    ultima_mensagem: Optional[datetime] = None