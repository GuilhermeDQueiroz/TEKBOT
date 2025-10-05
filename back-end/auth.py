import os
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from typing import Optional
from dotenv import load_dotenv
from passlib.context import CryptContext

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

if not SECRET_KEY:
    raise ValueError("Nenhuma SECRET_KEY definida no arquivo .env. O servidor não pode iniciar.")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ===============================================
# ==         FUNÇÕES PARA LIDAR COM SENHAS     ==
# ===============================================

def verificar_senha(senha_plana: str, senha_hash: str) -> bool:
    """Verifica se uma senha plana corresponde a um hash existente."""
    return pwd_context.verify(senha_plana, senha_hash)

def criar_hash_senha(senha: str) -> str:
    """Cria um hash seguro para uma nova senha."""
    return pwd_context.hash(senha)


# ===============================================
# ==         FUNÇÃO PARA CRIAR TOKENS JWT      ==
# ===============================================

def create_access_token(dados: dict, tempo_expiracao: Optional[timedelta] = None):
    para_encodar = dados.copy()
    
    if tempo_expiracao:
        expirar = datetime.now(timezone.utc) + tempo_expiracao
    else:
        expirar = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    para_encodar.update({"exp": expirar})
    
    token_codificado = jwt.encode(para_encodar, SECRET_KEY, algorithm=ALGORITHM)
    return token_codificado