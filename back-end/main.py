from fastapi import FastAPI, HTTPException, status, Depends
from pydantic import BaseModel
from datetime import datetime
from auth import create_access_token  # Importando a função correta
from models import UsuarioLogin, Token  # Importando o modelo de login
from typing import Dict
from schemas import RequisicaoConsulta 
from rag import recuperar_informacoes_relevantes, gerar_resposta_com_ia


app = FastAPI()

# Mock de banco de dados para armazenar usuários
fake_users_db: Dict[str, dict] = {
    "usuario@example.com": {"email": "usuario@example.com", "senha": "senha123"}
}

# Função de Login
@app.post("/login", response_model=Token)
def login(usuario: UsuarioLogin):
    print(f"Tentando fazer login com o e-mail: {usuario.email}")
    
    # Verificar se o e-mail está no banco de dados
    db_user = fake_users_db.get(usuario.email)
    print(f"Usuário encontrado no banco de dados: {db_user}")
    
    # Verificar se o usuário existe e se a senha fornecida é válida
    if not db_user or db_user["senha"] != usuario.senha:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Credenciais inválidas"
        )
    
    # Criar o token de acesso
    access_token = create_access_token(dados={"sub": usuario.email})
    print(f"Token gerado: {access_token}")
    
    return {"access_token": access_token, "token_type": "bearer"}

# Função para registrar um novo usuário (exemplo)
@app.post("/register", response_model=UsuarioLogin)
def register_user(usuario: UsuarioLogin):
    if usuario.email in fake_users_db:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email já cadastrado")
    
    # Adiciona o usuário ao "banco de dados"
    fake_users_db[usuario.email] = {"email": usuario.email, "senha": usuario.senha}
    
    return {"email": usuario.email, "senha": usuario.senha}

@app.post("/chatbot")
async def chatbot(resposta_usuario: RequisicaoConsulta):
    """
    Rota do chatbot que usa RAG para gerar respostas baseadas na consulta do usuário.
    """
    consulta = resposta_usuario.consulta
    
    # Passo 1: Buscar dados relevantes no banco usando o retriever
    contexto_relevante = recuperar_informacoes_relevantes(consulta)
    
    # Concatenar o texto dos documentos recuperados
    contexto_completo = "\n".join([doc["texto"] for doc in contexto_relevante])
    
    # Passo 2: Gerar resposta com IA utilizando o gerador
    resposta_gerada = gerar_resposta_com_ia(contexto_completo, consulta)
    
    return {"resposta": resposta_gerada}