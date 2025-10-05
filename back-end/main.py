import uuid
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import List
from schemas import PerguntaEntrada, MensagemEntrada, RedefinirSenha, RecuperacaoSenha
from models import UsuarioLogin, Token
from auth import create_access_token
from rag import processarPergunta
from dotenv import load_dotenv
from jose import JWTError, jwt
from bson import json_util
from datetime import timedelta, datetime
from email.message import EmailMessage
import os
import bcrypt
import json
import smtplib
import traceback
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from database import colecao_usuarios, colecao_mensagens, colecao_sessoes, colecao_interacoes

load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("Nenhuma SECRET_KEY definida no arquivo .env. O servidor não pode iniciar.")
ALGORITHM = "HS256"

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === FUNÇÕES DE HASH DE SENHA ===

def criar_hash_senha(senha: str) -> str:
    """Cria um hash bcrypt da senha"""
    senha_bytes = senha.encode('utf-8')
    salt = bcrypt.gensalt()
    senha_hash = bcrypt.hashpw(senha_bytes, salt)
    return senha_hash.decode('utf-8')


def verificar_senha(senha_plana: str, senha_hash: str) -> bool:
    """Verifica se a senha corresponde ao hash"""
    senha_bytes = senha_plana.encode('utf-8')
    senha_hash_bytes = senha_hash.encode('utf-8')
    return bcrypt.checkpw(senha_bytes, senha_hash_bytes)


# === Autenticação ===
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def verificar_token(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
        
        usuario = colecao_usuarios.find_one({"email": email})
        if not usuario:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário não encontrado")
        
        return {
            "email": email,
            "user_id": str(usuario["_id"])
        }
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")


# === FUNÇÃO DE ENVIO DE EMAIL ===

def enviarEmailRecuperacao(email_destinatario: str, token: str):
    """Envia email de recuperação de senha"""
    try:
        EMAIL_REMETENTE = os.getenv("EMAIL_REMETENTE")
        EMAIL_SENHA = os.getenv("EMAIL_SENHA")
        
        if not EMAIL_REMETENTE or not EMAIL_SENHA:
            raise ValueError("Credenciais de email não configuradas")
        
        link_recuperacao = f"http://localhost:8000/redefinir-senha?token={token}"
        
        mensagem = EmailMessage()
        mensagem["From"] = EMAIL_REMETENTE
        mensagem["To"] = email_destinatario
        mensagem["Subject"] = "Recuperação de Senha - TekBot"
        mensagem.set_content(f"""
        Olá,
        
        Você solicitou a recuperação de senha para sua conta no TekBot.
        
        Clique no link abaixo para redefinir sua senha:
        {link_recuperacao}
        
        Este link expira em 15 minutos.
        
        Se você não solicitou esta recuperação, ignore este email.
        
        Atenciosamente,
        Equipe TekBot
        """)
        
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_REMETENTE, EMAIL_SENHA)
            smtp.send_message(mensagem)
            
    except Exception as e:
        print(f"Erro ao enviar email: {str(e)}")
        raise


# === ROTAS DE AUTENTICAÇÃO ===

@app.post("/login", response_model=Token)
def login(usuario: UsuarioLogin):
    db_user = colecao_usuarios.find_one({"email": usuario.email})
    if not db_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")

    if not verificar_senha(usuario.senha, db_user["senha"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")

    access_token = create_access_token(dados={"sub": usuario.email})
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/register")
def register_user(usuario: UsuarioLogin):
    if colecao_usuarios.find_one({"email": usuario.email}):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email já cadastrado")

    senha_hash = criar_hash_senha(usuario.senha)
    
    colecao_usuarios.insert_one({
        "email": usuario.email,
        "senha": senha_hash,
        "criado_em": datetime.utcnow()
    })

    return {"email": usuario.email, "mensagem": "Usuário criado com sucesso"}


@app.get("/autenticar/login")
def get_usuario_autenticado(usuario: dict = Depends(verificar_token)):
    return {"autenticado": True, "usuario": usuario}


@app.post("/recuperar-senha")
def recuperar_senha(dados: RecuperacaoSenha):
    try:
        usuario = colecao_usuarios.find_one({"email": dados.email})
        if not usuario:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")

        token = create_access_token(dados={"sub": dados.email}, tempo_expiracao=timedelta(minutes=15))
        enviarEmailRecuperacao(dados.email, token)

        return {"mensagem": "E-mail de recuperação enviado com sucesso"}

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao enviar o e-mail: {str(e)}")


@app.get("/redefinir-senha", response_class=FileResponse, include_in_schema=False)
async def get_redefinir_senha_page():
    return FileResponse(FRONTEND_DIR / "html" / "redefinir-senha.html")


@app.post("/redefinir-senha")
def redefinir_senha(dados: RedefinirSenha):
    try:
        payload = jwt.decode(dados.token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=400, detail="Token inválido ou expirado")

        nova_senha_hash = criar_hash_senha(dados.nova_senha)
        
        resultado = colecao_usuarios.update_one(
            {"email": email}, 
            {"$set": {"senha": nova_senha_hash}}
        )
        
        if resultado.modified_count == 0:
            raise HTTPException(status_code=404, detail="Usuário não encontrado ou senha não atualizada")

        return {"mensagem": "Senha redefinida com sucesso"}
    except JWTError:
        raise HTTPException(status_code=400, detail="Token inválido ou expirado")


# === ROTAS DE SESSÕES ===

@app.post("/sessoes/criar")
def criar_sessao(usuario: dict = Depends(verificar_token)):
    try:
        sessao_id = str(uuid.uuid4())

        nova_sessao = {
            "_id": sessao_id,
            "user_id": usuario["user_id"],
            "titulo": "Nova Conversa",
            "criado_em": datetime.utcnow(),
            "atualizado_em": datetime.utcnow()
        }
        
        colecao_sessoes.insert_one(nova_sessao)
        
        return JSONResponse(content=json.loads(json_util.dumps(nova_sessao)), status_code=201)

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao criar sessão: {str(e)}")


@app.get("/sessoes")
def listar_sessoes(usuario: dict = Depends(verificar_token)):
    try:
        sessoes = list(colecao_sessoes.find(
            {"user_id": usuario["user_id"]}
        ).sort("atualizado_em", -1))
        
        return JSONResponse(content=json.loads(json_util.dumps(sessoes)), status_code=200)

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao listar sessões: {str(e)}")


@app.get("/sessoes/{sessao_id}")
def obter_sessao(sessao_id: str, usuario: dict = Depends(verificar_token)):
    try:
        sessao = colecao_sessoes.find_one({
            "_id": sessao_id,
            "user_id": usuario["user_id"]
        })
        
        if not sessao:
            raise HTTPException(status_code=404, detail="Sessão não encontrada")
        
        return JSONResponse(content=json.loads(json_util.dumps(sessao)), status_code=200)

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao obter sessão: {str(e)}")


@app.delete("/sessoes/{sessao_id}")
def deletar_sessao(sessao_id: str, usuario: dict = Depends(verificar_token)):
    try:
        sessao = colecao_sessoes.find_one({"_id": sessao_id, "user_id": usuario["user_id"]})
        if not sessao:
            raise HTTPException(status_code=404, detail="Sessão não encontrada")
        
        colecao_sessoes.delete_one({"_id": sessao_id, "user_id": usuario["user_id"]})
        colecao_interacoes.delete_many({"sessao_id": sessao_id})
        
        return {"mensagem": "Sessão deletada com sucesso"}

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao deletar sessão: {str(e)}")


@app.get("/sessoes/{sessao_id}/historico")
def obter_historico_sessao(sessao_id: str, usuario: dict = Depends(verificar_token)):
    try:
        if not colecao_sessoes.find_one({"_id": sessao_id, "user_id": usuario["user_id"]}):
            raise HTTPException(status_code=404, detail="Sessão não encontrada")
        
        interacoes = list(colecao_interacoes.find({"sessao_id": sessao_id}).sort("timestamp", 1))
        
        return JSONResponse(content=json.loads(json_util.dumps(interacoes)), status_code=200)

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao obter histórico: {str(e)}")


# === ROTAS DE IA ===

@app.post("/ia/responder")
def responder(pergunta_req: PerguntaEntrada, sessao_id: str, usuario: dict = Depends(verificar_token)):
    pergunta = pergunta_req.pergunta.strip()
    try:
        if not colecao_sessoes.find_one({"_id": sessao_id, "user_id": usuario["user_id"]}):
            raise HTTPException(status_code=404, detail="Sessão não encontrada")

        resposta = processarPergunta(pergunta)

        interacao = {
            "sessao_id": sessao_id,
            "user_id": usuario["user_id"],
            "pergunta": pergunta,
            "resposta": resposta,
            "timestamp": datetime.utcnow()
        }
        colecao_interacoes.insert_one(interacao)

        update_data = {"$set": {"atualizado_em": datetime.utcnow()}}
        if colecao_interacoes.count_documents({"sessao_id": sessao_id}) == 1:
            titulo = pergunta[:50] + ("..." if len(pergunta) > 50 else "")
            update_data["$set"]["titulo"] = titulo
        
        colecao_sessoes.update_one({"_id": sessao_id}, update_data)

        return {"resposta": resposta}

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Erro interno ao processar a resposta.")


# === ROTAS ANTIGAS (COMPATIBILIDADE) ===

@app.post("/pergunta")
def responder_pergunta(pergunta_entrada: PerguntaEntrada, usuario: dict = Depends(verificar_token)):
    from rag import registrarInteracao
    try:
        pergunta = pergunta_entrada.pergunta
        resposta = processarPergunta(pergunta)
        registrarInteracao(pergunta, resposta, [])
        return {"resposta": resposta}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Erro interno no servidor")


@app.post("/mensagens")
def adicionar_mensagem(mensagem: MensagemEntrada, usuario: dict = Depends(verificar_token)):
    from rag import modelo_embedding
    try:
        texto = mensagem.texto.strip()
        if not texto:
            raise HTTPException(status_code=400, detail="Texto vazio não permitido")

        embedding = modelo_embedding.encode([texto])[0]
        doc = {
            "texto": texto,
            "tipo": "base_conhecimento",
            "embedding": embedding.tolist(),
            "user_id": usuario["user_id"],
            "criado_em": datetime.utcnow()
        }

        resultado = colecao_mensagens.insert_one(doc)

        return JSONResponse(
            content=json.loads(json_util.dumps({
                "mensagem": "Mensagem adicionada com sucesso à base de conhecimento",
                "id": resultado.inserted_id
            })),
            status_code=200
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Erro ao salvar a mensagem")


# === ARQUIVOS ESTÁTICOS ===

from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent.parent.joinpath("front-end")

app.mount("/css", StaticFiles(directory=FRONTEND_DIR / "css"), name="css")
app.mount("/js", StaticFiles(directory=FRONTEND_DIR / "js"), name="js")
app.mount("/img", StaticFiles(directory=FRONTEND_DIR / "img"), name="img")


@app.get("/", response_class=RedirectResponse, include_in_schema=False)
async def root_redirect():
    return "/login"


@app.get("/login", response_class=FileResponse, include_in_schema=False)
async def get_login_page():
    return FileResponse(FRONTEND_DIR / "html" / "login.html")


@app.get("/chat", response_class=FileResponse, include_in_schema=False)
async def get_chat_page():
    return FileResponse(FRONTEND_DIR / "html" / "chat.html")
