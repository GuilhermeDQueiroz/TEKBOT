from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# Modelo de Usuário
class Usuario(BaseModel):
    username: str
    email: str
    nome_completo: Optional[str] = None
    criado_em: Optional[datetime] = None
    atualizado_em: Optional[datetime] = None

# Modelo de Criação de Usuário
class UsuarioCriar(BaseModel):
    username: str
    email: str
    senha: str
    nome_completo: Optional[str] = None

# Modelo de Resposta de Usuário
class UsuarioResposta(BaseModel):
    username: str
    email: str
    nome_completo: Optional[str] = None

# Modelo de Token (JWT)
class Token(BaseModel):
    access_token: str
    token_type: str
    
# Modelo de Login de Usuário
class UsuarioLogin(BaseModel):
    email: str
    senha: str