from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer
from typing import List
from schemas import PerguntaEntrada, MensagemEntrada
from models import UsuarioLogin, Token
from auth import create_access_token
from rag import recuperar_informacoes_relevantes, gerar_resposta_com_ia, registrar_interacao, modelo_embedding
from pymongo import MongoClient
from dotenv import load_dotenv
from jose import JWTError, jwt
import os
import bcrypt

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
        contexto = recuperar_informacoes_relevantes(pergunta)
        resposta = gerar_resposta_com_ia(contexto, pergunta)
        registrar_interacao(pergunta, resposta, [doc.get("texto", "") for doc in contexto])
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

        colecao_mensagens.insert_one({
            "texto": texto,
            "embedding": embedding.tolist()
        })

        return {"mensagem": "Mensagem adicionada com sucesso"}
    except Exception as e:
        print(f"[ERROR] Erro ao adicionar mensagem: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro ao salvar a mensagem")


@app.post("/ia/responder")
def responder_ia(pergunta_entrada: PerguntaEntrada):
    try:
        pergunta = pergunta_entrada.pergunta
        contexto = recuperar_informacoes_relevantes(pergunta)
        resposta = gerar_resposta_com_ia(contexto, pergunta)
        registrar_interacao(pergunta, resposta, [doc.get("texto", "") for doc in contexto])
        return JSONResponse(content={"resposta": resposta}, status_code=200)
    except Exception as e:
        print(f"[ERROR] Erro ao responder com IA: {e}")
        return JSONResponse(content={"erro": "Erro ao processar a pergunta"}, status_code=500)


# ✅ NOVA ROTA PARA RETORNAR USUÁRIO AUTENTICADO
@app.get("/autenticar/login")
def get_usuario_autenticado(usuario: dict = Depends(verificar_token)):
    return {
        "autenticado": True,
        "usuario": usuario
    }
