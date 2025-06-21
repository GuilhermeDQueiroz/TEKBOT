from datetime import datetime, timedelta
from jose import JWTError, jwt
from typing import Optional
import os
from dotenv import load_dotenv

# Carregar as variáveis de ambiente
load_dotenv()

# Usando variáveis de ambiente ou valores padrão
CHAVE_SECRETA = os.getenv("SECRET_KEY", "default_secret_key_for_testing")  # Chave de segurança
ALGORITMO = os.getenv("ALGORITHM", "HS256")
TEMPO_EXPIRACAO_TOKEN_MINUTOS = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

def create_access_token(dados: dict, tempo_expiracao: Optional[timedelta] = None):
    # Copiar dados para não modificar o original
    dados_para_codificar = dados.copy()
    
    # Definir tempo de expiração
    if tempo_expiracao:
        expirar = datetime.utcnow() + tempo_expiracao
    else:
        expirar = datetime.utcnow() + timedelta(minutes=TEMPO_EXPIRACAO_TOKEN_MINUTOS)
    
    # Incluir a data de expiração no token
    dados_para_codificar.update({"exp": expirar})
    
    # Codificar o token com a chave secreta
    try:
        token_codificado = jwt.encode(dados_para_codificar, CHAVE_SECRETA, algorithm=ALGORITMO)
        return token_codificado
    except JWTError as e:
        raise HTTPException(status_code=500, detail="Erro ao gerar o token")
