from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer
from typing import List
from schemas import PerguntaEntrada, MensagemEntrada, RedefinirSenha, RecuperacaoSenha
from models import UsuarioLogin, Token
from auth import create_access_token
from rag import recuperarInfoRelevantes, gerarRespostaComIa, registrarInteracao, modelo_embedding
from pymongo import MongoClient
from dotenv import load_dotenv
from jose import JWTError, jwt
from bson import json_util
from datetime import timedelta
from email.message import EmailMessage
import os
import bcrypt
import json
import smtplib
import traceback
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from datetime import timedelta

# === Configurações ===
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
SECRET_KEY = os.getenv("SECRET_KEY", "sua_chave_secreta")  # Substitua por sua chave real
ALGORITHM = "HS256"

# Conecta ao MongoDB
client = MongoClient(MONGO_URI)
db = client["tekbot"]
colecao_usuarios = db["usuarios"]
colecao_mensagens = db["mensagens"]

# Inicializa FastAPI
app = FastAPI()

# Configurar o CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Autenticação
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def verificar_token(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
        return {"email": email}
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")


def enviarEmailRecuperacao(destinatario: str, token: str):
    email_remetente = os.getenv("EMAIL_REMETENTE")
    email_senha = os.getenv("EMAIL_SENHA")

    if not email_remetente or not email_senha:
        raise Exception("Variáveis de ambiente de e-mail não encontradas")

    msg = EmailMessage()
    msg["Subject"] = "Recuperação de senha - TekBot"
    msg["From"] = email_remetente
    msg["To"] = destinatario

    link = f"http://localhost:8000/html/redefinir-senha.html?token={token}"  # ajuste conforme seu front
    msg.set_content(f"""
Olá! Você solicitou a redefinição de senha do TekBot.

Clique no link abaixo para redefinir sua senha:
{link}

Se você não fez essa solicitação, ignore este e-mail.
""")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(email_remetente, email_senha)
        smtp.send_message(msg)


# === ROTAS ===

@app.post("/login", response_model=Token)
def login(usuario: UsuarioLogin):
    db_user = colecao_usuarios.find_one({"email": usuario.email})
    if not db_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")

    senha_valida = bcrypt.checkpw(usuario.senha.encode(), db_user["senha"].encode())
    if not senha_valida:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")

    access_token = create_access_token(dados={"sub": usuario.email})
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/register", response_model=UsuarioLogin)
def register_user(usuario: UsuarioLogin):
    if colecao_usuarios.find_one({"email": usuario.email}):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email já cadastrado")

    senha_hash = bcrypt.hashpw(usuario.senha.encode(), bcrypt.gensalt()).decode()
    colecao_usuarios.insert_one({
        "email": usuario.email,
        "senha": senha_hash
    })

    return usuario


@app.post("/pergunta")
def responder_pergunta(pergunta_entrada: PerguntaEntrada):
    try:
        pergunta = pergunta_entrada.pergunta
        contexto = recuperarInfoRelevantes(pergunta)
        resposta = gerarRespostaComIa(contexto, pergunta)
        registrarInteracao(pergunta, resposta, [doc.get("texto", "") for doc in contexto])
        return {"resposta": resposta}
    except Exception as e:
        print(f"[ERROR] Erro ao processar a pergunta: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro interno no servidor")


@app.post("/mensagens")
def adicionar_mensagem(mensagem: MensagemEntrada):
    try:
        texto = mensagem.texto.strip()
        if not texto:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Texto vazio não permitido")

        embedding = modelo_embedding.encode([texto])[0]
        doc = {
            "texto": texto,
            "embedding": embedding.tolist()
        }

        resultado = colecao_mensagens.insert_one(doc)

        return JSONResponse(
            content=json.loads(json_util.dumps({
                "mensagem": "Mensagem adicionada com sucesso",
                "id": resultado.inserted_id
            })),
            status_code=200
        )
    except Exception as e:
        print(f"[ERROR] Erro ao adicionar mensagem: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro ao salvar a mensagem")


@app.post("/ia/responder")
def responder(pergunta_req: PerguntaEntrada):
    pergunta = pergunta_req.pergunta.strip()

    try:
        documentos_relevantes = recuperarInfoRelevantes(pergunta)

        # Cálculo da similaridade para checar se já existe resposta alta
        pergunta_embedding = modelo_embedding.encode([pergunta]).reshape(1, -1)

        melhor_doc = None
        maior_similaridade = 0

        for doc in documentos_relevantes:

            embedding_doc = np.array(doc.get("embedding", []))
            if embedding_doc.size == 0:

                embedding_doc = modelo_embedding.encode([doc.get("texto", "")])[0]
            embedding_doc = embedding_doc.reshape(1, -1)

            sim = cosine_similarity(pergunta_embedding, embedding_doc)[0][0]
            if sim > maior_similaridade:
                maior_similaridade = sim
                melhor_doc = doc

        LIMIAR_SIMILARIDADE = 0.9  # ajuste conforme necessário

        if melhor_doc and maior_similaridade >= LIMIAR_SIMILARIDADE:
            # Retorna a resposta já existente para similaridade alta
            resposta = melhor_doc.get("resposta", melhor_doc.get("texto", ""))
            registrarInteracao(pergunta, resposta, [melhor_doc])
            return {"resposta": resposta}

        # gera resposta via IA
        resposta = gerarRespostaComIa(documentos_relevantes, pergunta)
        registrarInteracao(pergunta, resposta, documentos_relevantes)
        return {"resposta": resposta}

    except Exception as e:
        print(f"[ERROR] Erro ao responder com IA: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao processar a resposta.")


@app.get("/autenticar/login")
def get_usuario_autenticado(usuario: dict = Depends(verificar_token)):
    return {
        "autenticado": True,
        "usuario": usuario
    }


@app.post("/redefinir-senha")
def redefinir_senha(dados: RedefinirSenha):
    try:
        payload = jwt.decode(dados.token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=400, detail="Token inválido ou expirado")

        nova_senha_hash = bcrypt.hashpw(dados.nova_senha.encode(), bcrypt.gensalt()).decode()
        resultado = colecao_usuarios.update_one({"email": email}, {"$set": {"senha": nova_senha_hash}})
        if resultado.modified_count == 0:
            raise HTTPException(status_code=404, detail="Usuário não encontrado ou senha não atualizada")

        return {"mensagem": "Senha redefinida com sucesso"}
    except JWTError:
        raise HTTPException(status_code=400, detail="Token inválido ou expirado")
    

@app.post("/recuperar-senha")
def recuperar_senha(dados: RecuperacaoSenha):
    try:
        print("🔍 E-mail recebido:", dados.email)

        usuario = colecao_usuarios.find_one({"email": dados.email})
        if not usuario:
            print("❌ Usuário não encontrado")
            raise HTTPException(status_code=404, detail="Usuário não encontrado")

        print("✅ Usuário encontrado:", usuario["email"])

        # Aqui usa o parâmetro correto "tempo_expiracao"
        token = create_access_token(dados={"sub": dados.email}, tempo_expiracao=timedelta(minutes=15))
        print("🔐 Token gerado:", token)

        enviarEmailRecuperacao(dados.email, token)

        print("✅ E-mail enviado com sucesso")
        return {"mensagem": "E-mail de recuperação enviado com sucesso"}

    except Exception as e:
        print("🔥 ERRO AO ENVIAR E-MAIL:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao enviar o e-mail: {str(e)}")


from fastapi.staticfiles import StaticFiles
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.joinpath("front-end")

app.mount("/html", StaticFiles(directory=BASE_DIR.joinpath("html"), html=True), name="html_files")
app.mount("/css", StaticFiles(directory=BASE_DIR.joinpath("css")), name="css_files")
app.mount("/js", StaticFiles(directory=BASE_DIR.joinpath("js")), name="js_files")
app.mount("/img", StaticFiles(directory=BASE_DIR.joinpath("img")), name="img_files")