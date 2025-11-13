# main.py
import uuid
import tickets as tickets_module
from fastapi import FastAPI, HTTPException, status, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import Optional, List, Dict, Any
from webhook import webhook_manager
from schemas import (
    PerguntaEntrada, MensagemEntrada, RedefinirSenha, RecuperacaoSenha,
    TicketCriar, TicketResposta, TicketAtualizar, AdicionarMensagemTicket,
    AtribuirTicket, FiltroTickets, EstatisticasAtendente, DashboardMetricas,
    StatusTicket, PrioridadeTicket, CategoriaTicket, TipoUsuario, TreinamentoEntrada,
    WebhookConfig, WebhookConfigResposta, WebhookResposta, FeedbackAnalise,
    NivelFeedback, EstatisticasFeedback, ListaFeedbacks, WebhookTesteResposta,
    DadosSessao
)
from models import UsuarioLogin, Token
from auth import create_access_token
from rag import processarPergunta, modelo_embedding
from dotenv import load_dotenv
from jose import JWTError, jwt
from bson import json_util, ObjectId
from datetime import timedelta, datetime
from pydantic import BaseModel, EmailStr, Field, validator
from email.message import EmailMessage
import os
import bcrypt
import json
import smtplib
import traceback
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from database import (
    colecao_usuarios, colecao_mensagens, colecao_sessoes, colecao_interacoes,
    colecao_webhook_config, colecao_webhook_feedbacks, colecao_webhook_logs
)

# Opcional worker imports
import threading
import time

# Carregar .env
load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("Nenhuma SECRET_KEY definida no arquivo .env. O servidor não pode iniciar.")
ALGORITHM = "HS256"

# Diretório do front-end (definido cedo para evitar uso antes de declarar)
from pathlib import Path
FRONTEND_DIR = Path(__file__).resolve().parent.parent.joinpath("front-end")

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
            "atualizado_em": datetime.utcnow(),
            # status pode ser "ativa" ou "finalizada"
            "status": "ativa"
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
        
        return {"messagem": "Sessão deletada com sucesso"}

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


# NOVA ROTA: Fechar sessão e enfileirar envio para análise
@app.post("/sessoes/{sessao_id}/fechar")
def fechar_sessao(sessao_id: str, force: bool = False, usuario: dict = Depends(verificar_token)):
    """
    Fecha a sessão (marca finalizada) e enfileira o envio para análise via webhook.
    - force: se True, força reenvio mesmo que já tenha sido enviado antes.
    """
    try:
        # Verificar se existe
        sessao = colecao_sessoes.find_one({"_id": sessao_id})
        if not sessao:
            raise HTTPException(status_code=404, detail="Sessão não encontrada")

        # Permissão: dono da sessão ou atendente/admin
        user_db = colecao_usuarios.find_one({"email": usuario["email"]})
        tipo_usuario = user_db.get("tipo_usuario", TipoUsuario.CLIENTE.value)

        if tipo_usuario == TipoUsuario.CLIENTE.value:
            if sessao.get("user_id") != usuario["user_id"]:
                raise HTTPException(status_code=403, detail="Sem permissão")

        # Verificar se já foi enfileirada (evitar duplicatas), a menos que force=True
        if sessao.get("enfileirado_para_analise") and not force:
            return JSONResponse(content={"mensagem": "Sessão já enfileirada para análise", "sessao_id": sessao_id}, status_code=200)

        # Marcar como finalizada / atualizar timestamps
        update_fields = {
            "status": "finalizada",
            "atualizado_em": datetime.utcnow(),
            "finalizada_em": datetime.utcnow(),
            "enfileirado_para_analise": True,
            "enfileirado_em": datetime.utcnow()
        }

        colecao_sessoes.update_one({"_id": sessao_id}, {"$set": update_fields})

        # Enfileira o envio (assíncrono) - tenta usar enviar_webhook_async com fallback
        try:
            resultado = webhook_manager.enviar_webhook_async(sessao_id, force=force)
        except AttributeError:
            resultado = webhook_manager.enviar_webhook(sessao_id, force=force)

        # Retornar info útil ao cliente/front-end
        resposta = {
            "mensagem": "Sessão finalizada e envio enfileirado",
            "sessao_id": sessao_id,
            "enfileirado": resultado.get("sucesso", False),
            "detalhes": resultado
        }

        # 202 se enfileirado com sucesso, 200 caso contrário
        status_code = 202 if resultado.get("sucesso") else 200
        return JSONResponse(content=resposta, status_code=status_code)

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao fechar sessão: {str(e)}")


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


# ================================================================
# ROTAS DE TICKETS (mantive seu código original)
# ================================================================
@app.post("/tickets/criar", response_model=dict)
def criar_ticket_route(dados: TicketCriar, usuario: dict = Depends(verificar_token)):
    """Cria um novo ticket (cliente)"""
    try:
        ticket = tickets_module.criar_ticket(
            titulo=dados.titulo,
            descricao=dados.descricao,
            categoria=dados.categoria.value,
            email_cliente=usuario["email"],
            prioridade_manual=dados.prioridade_manual.value if dados.prioridade_manual else None,
            usar_ia=True
        )
        
        ticket["_id"] = str(ticket["_id"])
        return JSONResponse(content=json.loads(json_util.dumps(ticket)), status_code=201)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao criar ticket: {str(e)}")


@app.get("/tickets/fila", response_model=List[dict])
def obter_fila_tickets(
    status: Optional[List[StatusTicket]] = None,
    prioridade: Optional[List[PrioridadeTicket]] = None,
    categoria: Optional[List[CategoriaTicket]] = None,
    apenas_meus: bool = False,
    usuario: dict = Depends(verificar_token)
):
    """Obtém fila de tickets ordenada inteligentemente (atendentes)"""
    try:
        filtros = {}
        if status:
            filtros["status"] = [s.value for s in status]
        if prioridade:
            filtros["prioridade"] = [p.value for p in prioridade]
        if categoria:
            filtros["categoria"] = [c.value for c in categoria]
        if apenas_meus:
            filtros["apenas_meus"] = True
        
        atendente_email = usuario["email"] if apenas_meus else None
        tickets = tickets_module.obter_fila_inteligente(atendente_email=atendente_email, filtros=filtros)
        
        for ticket in tickets:
            ticket["_id"] = str(ticket["_id"])
        
        return JSONResponse(content=json.loads(json_util.dumps(tickets)), status_code=200)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao obter fila: {str(e)}")


@app.get("/tickets/meus", response_model=List[dict])
def listar_meus_tickets(usuario: dict = Depends(verificar_token)):
    try:
        tickets = tickets_module.listar_tickets_cliente(usuario["email"])
        for ticket in tickets:
            ticket["_id"] = str(ticket["_id"])
        
        return JSONResponse(content=json.loads(json_util.dumps(tickets)), status_code=200)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao listar tickets: {str(e)}")


@app.get("/tickets/{ticket_id}", response_model=dict)
def obter_ticket_detalhes(ticket_id: str, usuario: dict = Depends(verificar_token)):
    try:
        ticket = tickets_module.obter_ticket(ticket_id)
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket não encontrado")
        
        # Verificar permissão
        user_db = colecao_usuarios.find_one({"email": usuario["email"]})
        tipo_usuario = user_db.get("tipo_usuario", TipoUsuario.CLIENTE.value)
        
        if tipo_usuario == TipoUsuario.CLIENTE.value:
            if ticket["email_cliente"] != usuario["email"]:
                raise HTTPException(status_code=403, detail="Sem permissão")
        
        ticket["_id"] = str(ticket["_id"])
        return JSONResponse(content=json.loads(json_util.dumps(ticket)), status_code=200)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao obter ticket: {str(e)}")


@app.post("/tickets/{ticket_id}/atribuir")
def atribuir_ticket_route(ticket_id: str, usuario: dict = Depends(verificar_token)):
    try:
        user_db = colecao_usuarios.find_one({"email": usuario["email"]})
        tipo = user_db.get("tipo_usuario", TipoUsuario.CLIENTE.value)
        
        if tipo not in [TipoUsuario.ATENDENTE.value, TipoUsuario.ADMIN.value]:
            raise HTTPException(status_code=403, detail="Apenas atendentes")
        
        ticket = tickets_module.atribuir_ticket(ticket_id, usuario["email"])
        ticket["_id"] = str(ticket["_id"])
        
        return JSONResponse(content=json.loads(json_util.dumps(ticket)), status_code=200)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao atribuir: {str(e)}")


@app.post("/tickets/{ticket_id}/mensagem")
def adicionar_mensagem_route(ticket_id: str, dados: AdicionarMensagemTicket, usuario: dict = Depends(verificar_token)):
    try:
        ticket = tickets_module.obter_ticket(ticket_id)
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket não encontrado")
        
        user_db = colecao_usuarios.find_one({"email": usuario["email"]})
        tipo = user_db.get("tipo_usuario", TipoUsuario.CLIENTE.value)
        
        is_atendente = tipo in [TipoUsuario.ATENDENTE.value, TipoUsuario.ADMIN.value]
        
        if not is_atendente and ticket["email_cliente"] != usuario["email"]:
            raise HTTPException(status_code=403, detail="Sem permissão")
        
        mensagem = tickets_module.adicionar_mensagem(ticket_id=ticket_id, remetente_email=usuario["email"], conteudo=dados.conteudo, is_atendente=is_atendente)
        
        return JSONResponse(content=json.loads(json_util.dumps(mensagem)), status_code=201)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao adicionar mensagem: {str(e)}")


@app.patch("/tickets/{ticket_id}/status")
def atualizar_status_route(ticket_id: str, dados: TicketAtualizar, usuario: dict = Depends(verificar_token)):
    try:
        user_db = colecao_usuarios.find_one({"email": usuario["email"]})
        tipo = user_db.get("tipo_usuario", TipoUsuario.CLIENTE.value)
        
        if tipo not in [TipoUsuario.ATENDENTE.value, TipoUsuario.ADMIN.value]:
            raise HTTPException(status_code=403, detail="Apenas atendentes")
        
        ticket = tickets_module.atualizar_status_ticket(ticket_id=ticket_id, novo_status=dados.status.value if dados.status else None, observacoes=dados.observacoes)
        
        ticket["_id"] = str(ticket["_id"])
        return JSONResponse(content=json.loads(json_util.dumps(ticket)), status_code=200)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar: {str(e)}")


# === ROTAS DE GERENCIAMENTO DE USUÁRIOS ===

@app.post("/usuarios/tornar-atendente")
def tornar_atendente(email: EmailStr, usuario: dict = Depends(verificar_token)):
    try:
        user_db = colecao_usuarios.find_one({"email": usuario["email"]})
        if user_db.get("tipo_usuario") != TipoUsuario.ADMIN.value:
            raise HTTPException(status_code=403, detail="Apenas admins")
        
        result = colecao_usuarios.update_one({"email": email}, {"$set": {"tipo_usuario": TipoUsuario.ATENDENTE.value}})
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
        
        return {"mensagem": f"Usuário {email} agora é atendente"}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# === ROTAS DE TREINAMENTO === (mantidas conforme trecho anterior)
@app.post("/treinamento/adicionar-publico")
def adicionar_treinamento_publico(dados: TreinamentoEntrada):
    try:
        print("🔥 SALVANDO TREINAMENTO...")
        
        pergunta_embedding = modelo_embedding.encode([dados.pergunta])[0].tolist()
        
        documento = {
            "tipo": "treinamento",
            "pergunta": dados.pergunta,
            "resposta": dados.resposta,
            "embedding": pergunta_embedding,
            "contexto_utilizado": [],
            "sessao_id": "treinamento_dev",
            "data": datetime.utcnow(),
            "categoria": dados.categoria,
            "tags": dados.tags if dados.tags else [],
            "criado_por": "desenvolvedor",
            "ativo": True
        }
        
        resultado = colecao_interacoes.insert_one(documento)
        print(f"✅ SALVO! ID: {resultado.inserted_id}")
        
        return {
            "mensagem": "Treinamento adicionado com sucesso!",
            "id": str(resultado.inserted_id),
            "pergunta": dados.pergunta,
            "embedding_gerado": True
        }
    except Exception as e:
        print(f"❌ ERRO: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")


@app.get("/treinamento/listar-publico")
def listar_treinamentos_publico(skip: int = 0, limit: int = 50, categoria: Optional[str] = None):
    try:
        filtro = {"tipo": "treinamento", "ativo": True}
        if categoria:
            filtro["categoria"] = categoria
        
        treinamentos = list(colecao_interacoes.find(filtro).sort("data", -1).skip(skip).limit(limit))
        
        for t in treinamentos:
            t["_id"] = str(t["_id"])
            t.pop("embedding", None)
            t["criado_em"] = t.pop("data", None)
        
        total = colecao_interacoes.count_documents(filtro)
        
        return {"treinamentos": treinamentos, "total": total, "skip": skip, "limit": limit}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/treinamento", response_class=FileResponse, include_in_schema=False)
async def get_treinamento_page():
    return FileResponse(FRONTEND_DIR / "html" / "treinamento.html")


# === ROTAS DE WEBHOOK (config/test/status/enviar/callback/logs/estatisticas) ===

@app.post("/webhook/configurar", response_model=WebhookConfigResposta)
def configurar_webhook_route(config: WebhookConfig, usuario: dict = Depends(verificar_token)):
    """
    Configura webhook para envio de sessões (apenas ADMIN)
    """
    try:
        # Verificar permissão de admin
        user_db = colecao_usuarios.find_one({"email": usuario["email"]})
        if user_db.get("tipo_usuario") != TipoUsuario.ADMIN.value:
            raise HTTPException(status_code=403, detail="Apenas admins podem configurar webhook")
        
        resultado = webhook_manager.configurar_webhook(
            url=str(config.url),
            secret_key=config.secret_key,
            ativo=config.ativo,
            timeout_segundos=config.timeout_segundos,
            max_tentativas=config.max_tentativas
        )
        
        return JSONResponse(content=json.loads(json_util.dumps(resultado)), status_code=201)
    
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao configurar webhook: {str(e)}")


@app.get("/webhook/config")
def obter_config_webhook_route(usuario: dict = Depends(verificar_token)):
    """Retorna configuração atual do webhook (apenas ADMIN)"""
    try:
        user_db = colecao_usuarios.find_one({"email": usuario["email"]})
        if user_db.get("tipo_usuario") != TipoUsuario.ADMIN.value:
            raise HTTPException(status_code=403, detail="Apenas admins")
        
        config = webhook_manager.obter_config()
        if not config:
            raise HTTPException(status_code=404, detail="Webhook não configurado")
        
        # Remover secret_key da resposta por segurança
        config_safe = {k: v for k, v in config.items() if k != "secret_key"}
        config_safe["secret_key_presente"] = True
        
        return JSONResponse(content=json.loads(json_util.dumps(config_safe)), status_code=200)
    
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/webhook/testar", response_model=None)
def testar_webhook_route(usuario: dict = Depends(verificar_token)):
    """
    Testa conexão com webhook configurado (chama webhook_manager.testar_webhook()).
    """
    try:
        user_db = colecao_usuarios.find_one({"email": usuario["email"]})
        if user_db.get("tipo_usuario") != TipoUsuario.ADMIN.value:
            raise HTTPException(status_code=403, detail="Apenas admins")

        resultado = webhook_manager.testar_webhook()

        return JSONResponse(content=resultado, status_code=200 if resultado.get("sucesso") else 500)

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/webhook/status/{sessao_id}")
def status_envio(sessao_id: str, limit: int = 10, usuario: dict = Depends(verificar_token)):
    """
    Retorna os últimos `limit` logs para a sessao_id informada (útil para debug).
    """
    try:
        user_db = colecao_usuarios.find_one({"email": usuario["email"]})
        if user_db.get("tipo_usuario") != TipoUsuario.ADMIN.value:
            raise HTTPException(status_code=403, detail="Apenas admins")

        logs = list(colecao_webhook_logs.find({"sessao_id": sessao_id}).sort("timestamp", -1).limit(limit))
        # normalizar ObjectId e datetimes para JSON-friendly
        for l in logs:
            l["_id"] = str(l.get("_id"))
            if isinstance(l.get("timestamp"), datetime):
                l["timestamp"] = l["timestamp"].isoformat()
            if isinstance(l.get("tempo_resposta_ms"), (int, float)):
                l["tempo_resposta_ms"] = int(l["tempo_resposta_ms"])

        return JSONResponse(content={"sucesso": True, "logs": logs}, status_code=200)

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/webhook/enviar-sessao/{sessao_id}")
def enviar_sessao_route(sessao_id: str, force: bool = False, usuario: dict = Depends(verificar_token)):
    """
    Enfileira o envio de uma sessão para análise (async) - apenas admins
    """
    try:
        user_db = colecao_usuarios.find_one({"email": usuario["email"]})
        if user_db.get("tipo_usuario") != TipoUsuario.ADMIN.value:
            raise HTTPException(status_code=403, detail="Apenas admins")

        resultado = webhook_manager.enviar_webhook_async(sessao_id, force=force)
        status_code = 202 if resultado.get("sucesso") else 400

        return JSONResponse(content=resultado, status_code=status_code)

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/webhook/ativar")
def ativar_webhook_route(usuario: dict = Depends(verificar_token)):
    """Ativa webhook"""
    try:
        user_db = colecao_usuarios.find_one({"email": usuario["email"]})
        if user_db.get("tipo_usuario") != TipoUsuario.ADMIN.value:
            raise HTTPException(status_code=403, detail="Apenas admins")
        
        webhook_manager.ativar_webhook()
        return {"mensagem": "Webhook ativado"}
    
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/webhook/desativar")
def desativar_webhook_route(usuario: dict = Depends(verificar_token)):
    """Desativa webhook"""
    try:
        user_db = colecao_usuarios.find_one({"email": usuario["email"]})
        if user_db.get("tipo_usuario") != TipoUsuario.ADMIN.value:
            raise HTTPException(status_code=403, detail="Apenas admins")
        
        webhook_manager.desativar_webhook()
        return {"mensagem": "Webhook desativado"}
    
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/webhook/enviar-sessao/executar/{sessao_id}")
def enviar_sessao_sync_route(sessao_id: str, force: bool = False, usuario: dict = Depends(verificar_token)):
    """
    Envia SÍNCRONO (bloqueante) — mantém endpoint legado que você já tinha.
    Usar apenas quando precisar do resultado imediato.
    """
    try:
        # Verificar se sessão existe e pertence ao usuário
        sessao = colecao_sessoes.find_one({"_id": sessao_id})
        if not sessao:
            raise HTTPException(status_code=404, detail="Sessão não encontrada")
        
        # Verificar permissão
        user_db = colecao_usuarios.find_one({"email": usuario["email"]})
        tipo_usuario = user_db.get("tipo_usuario", TipoUsuario.CLIENTE.value)
        
        # Apenas dono da sessão ou admin/atendente pode enviar
        if tipo_usuario == TipoUsuario.CLIENTE.value:
            if sessao["user_id"] != usuario["user_id"]:
                raise HTTPException(status_code=403, detail="Sem permissão")
        
        # Enviar (síncrono)
        resultado = webhook_manager.enviar_webhook(sessao_id, force=force)
        
        return JSONResponse(content=json.loads(json_util.dumps(resultado)), status_code=200 if resultado.get("sucesso") else 400)
    
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao enviar: {str(e)}")


@app.post("/webhook/callback", include_in_schema=False)
def webhook_callback_route(
    dados: WebhookResposta,
    signature: str = Header(..., alias="X-Webhook-Signature", description="Assinatura HMAC-SHA256")
):
    """
    Endpoint para receber feedback do webhook terceiro (público — valida assinatura)
    """
    try:
        # Converter Pydantic para dict
        dados_dict = dados.dict()
        
        # Processar feedback
        resultado = webhook_manager.receber_feedback(dados_dict, signature)
        
        if not resultado["sucesso"]:
            raise HTTPException(status_code=400, detail=resultado.get("erro", "Erro ao processar feedback"))
        
        return JSONResponse(content=resultado, status_code=200)
    
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/webhook/feedbacks/{sessao_id}")
def obter_feedbacks_sessao_route(sessao_id: str, usuario: dict = Depends(verificar_token)):
    """
    Retorna todos os feedbacks recebidos de uma sessão
    """
    try:
        # Verificar se sessão existe e permissão
        sessao = colecao_sessoes.find_one({"_id": sessao_id})
        if not sessao:
            raise HTTPException(status_code=404, detail="Sessão não encontrada")
        
        user_db = colecao_usuarios.find_one({"email": usuario["email"]})
        tipo_usuario = user_db.get("tipo_usuario", TipoUsuario.CLIENTE.value)
        
        # Verificar permissão
        if tipo_usuario == TipoUsuario.CLIENTE.value:
            if sessao["user_id"] != usuario["user_id"]:
                raise HTTPException(status_code=403, detail="Sem permissão")
        
        feedbacks = webhook_manager.obter_feedbacks_sessao(sessao_id)
        
        return JSONResponse(content=json.loads(json_util.dumps(feedbacks)), status_code=200)
    
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/webhook/logs/{sessao_id}")
def obter_logs_webhook_route(sessao_id: str, usuario: dict = Depends(verificar_token)):
    """Retorna logs de envio de webhook de uma sessão (apenas admin)"""
    try:
        user_db = colecao_usuarios.find_one({"email": usuario["email"]})
        if user_db.get("tipo_usuario") != TipoUsuario.ADMIN.value:
            raise HTTPException(status_code=403, detail="Apenas admins")
        
        logs = webhook_manager.obter_logs_sessao(sessao_id)
        
        return JSONResponse(content=json.loads(json_util.dumps(logs)), status_code=200)
    
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/webhook/estatisticas", response_model=EstatisticasFeedback)
def obter_estatisticas_webhook_route(usuario: dict = Depends(verificar_token)):
    """
    Retorna estatísticas gerais dos feedbacks recebidos
    """
    try:
        user_db = colecao_usuarios.find_one({"email": usuario["email"]})
        tipo_usuario = user_db.get("tipo_usuario", TipoUsuario.CLIENTE.value)
        
        # Atendentes e admins podem ver estatísticas gerais
        if tipo_usuario not in [TipoUsuario.ATENDENTE.value, TipoUsuario.ADMIN.value]:
            raise HTTPException(status_code=403, detail="Apenas atendentes e admins")
        
        estatisticas = webhook_manager.obter_estatisticas()
        
        return JSONResponse(content=json.loads(json_util.dumps(estatisticas)), status_code=200)
    
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/webhook/feedbacks", response_model=ListaFeedbacks)
def listar_todos_feedbacks_route(pagina: int = 1, tamanho_pagina: int = 20, nivel: Optional[NivelFeedback] = None, usuario: dict = Depends(verificar_token)):
    """
    Lista todos os feedbacks com paginação e filtros
    """
    try:
        user_db = colecao_usuarios.find_one({"email": usuario["email"]})
        tipo_usuario = user_db.get("tipo_usuario", TipoUsuario.CLIENTE.value)
        
        if tipo_usuario not in [TipoUsuario.ATENDENTE.value, TipoUsuario.ADMIN.value]:
            raise HTTPException(status_code=403, detail="Apenas atendentes e admins")
        
        # Validar parâmetros
        if tamanho_pagina > 100:
            tamanho_pagina = 100
        if pagina < 1:
            pagina = 1
        
        # Construir filtro
        filtro = {}
        if nivel:
            filtro["nivel"] = nivel.value
        
        # Buscar feedbacks
        skip = (pagina - 1) * tamanho_pagina
        feedbacks = list(colecao_webhook_feedbacks.find(filtro).sort("recebido_em", -1).skip(skip).limit(tamanho_pagina))
        
        # Formatar
        for f in feedbacks:
            f["_id"] = str(f["_id"])
        
        total = colecao_webhook_feedbacks.count_documents(filtro)
        
        resultado = {"feedbacks": feedbacks, "total": total, "pagina": pagina, "tamanho_pagina": tamanho_pagina}
        
        return JSONResponse(content=json.loads(json_util.dumps(resultado)), status_code=200)
    
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/webhook/config")
def remover_config_webhook_route(usuario: dict = Depends(verificar_token)):
    """Remove configuração do webhook (apenas admin)"""
    try:
        user_db = colecao_usuarios.find_one({"email": usuario["email"]})
        if user_db.get("tipo_usuario") != TipoUsuario.ADMIN.value:
            raise HTTPException(status_code=403, detail="Apenas admins")
        
        # Usar coleção definida no seu modulo database
        resultado = colecao_webhook_config.delete_many({})
        
        return {"mensagem": f"Webhook removido ({resultado.deleted_count} configuração(ões))"}
    
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# === PÁGINAS ESTÁTICAS E REDIRECIONAMENTO ===

@app.get("/webhook", response_class=FileResponse, include_in_schema=False)
async def get_webhook_page():
    """Página de gerenciamento de webhook (apenas admins)"""
    return FileResponse(FRONTEND_DIR / "html" / "webhook.html")


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


print("[✓] Rotas de Webhook registradas!")


# ---------------------------------------------------------------------
# Worker: auto-close sessions after inactivity (atomic lock via Mongo)
# ---------------------------------------------------------------------
def worker_auto_close_atomic(inatividade_minutos: int = 5, intervalo_segundos: int = 60, batch_size: int = 200):
    """
    Fecha sessões inativas e enfileira envio para análise.
    Usa lock atômico via find_one_and_update para evitar duplicatas em múltiplas instâncias.
    """
    print(f"[AUTO-CLOSE] Iniciando worker (inatividade={inatividade_minutos}min, intervalo={intervalo_segundos}s)")
    while True:
        try:
            limite = datetime.utcnow() - timedelta(minutes=inatividade_minutos)
            # candidatos: status != finalizada, atualizado_em < limite, não enfileirado, sem processing_lock
            query = {
                "status": {"$ne": "finalizada"},
                "atualizado_em": {"$lt": limite},
                "enfileirado_para_analise": {"$ne": True},
                "processing_lock": {"$ne": True}
            }

            candidatos = list(colecao_sessoes.find(query).limit(batch_size))
            if candidatos:
                print(f"[AUTO-CLOSE] {len(candidatos)} candidato(s) encontrados para fechamento.")

            for s in candidatos:
                sid = s["_id"]

                # Tenta adquirir lock atômico
                locked = colecao_sessoes.find_one_and_update(
                    {"_id": sid, "processing_lock": {"$ne": True}},
                    {"$set": {"processing_lock": True, "processing_started_at": datetime.utcnow()}},
                    return_document=False
                )

                if locked is None:
                    # outro processo pegou
                    print(f"[AUTO-CLOSE] Lock não adquirido para sessão {sid}, pulando.")
                    continue

                try:
                    # opcional: exigir que haja interações
                    total_interacoes = colecao_interacoes.count_documents({"sessao_id": sid})
                    if total_interacoes == 0:
                        # remove lock e pula
                        colecao_sessoes.update_one({"_id": sid}, {"$unset": {"processing_lock": "", "processing_started_at": ""}})
                        print(f"[AUTO-CLOSE] Sessão {sid} sem interações — pulando.")
                        continue

                    # marcar finalizada e enfileirada
                    now = datetime.utcnow()
                    colecao_sessoes.update_one(
                        {"_id": sid},
                        {"$set": {
                            "status": "finalizada",
                            "atualizado_em": now,
                            "finalizada_em": now,
                            "enfileirado_para_analise": True,
                            "enfileirado_em": now
                        }, "$unset": {"processing_lock": "", "processing_started_at": ""}}
                    )

                    # chamar envio (async preferível)
                    try:
                        resultado = webhook_manager.enviar_webhook_async(sid, force=False)
                    except AttributeError:
                        resultado = webhook_manager.enviar_webhook(sid, force=False)

                    print(f"[AUTO-CLOSE] Sessão {sid} processada/enfileirada -> sucesso={resultado.get('sucesso', False)}")

                except Exception as e:
                    print(f"[AUTO-CLOSE] Erro processando sessão {sid}: {e}")
                    traceback.print_exc()
                    # garantir unlock
                    colecao_sessoes.update_one({"_id": sid}, {"$unset": {"processing_lock": "", "processing_started_at": ""}})

        except Exception as e:
            print(f"[AUTO-CLOSE] Erro no loop do worker: {e}")
            traceback.print_exc()

        time.sleep(intervalo_segundos)


# Iniciar worker se habilitado via ENV
_enable_auto_close = os.getenv("ENABLE_AUTO_CLOSE", "0").lower() in ("1", "true", "yes")
if _enable_auto_close:
    try:
        _inatividade = int(os.getenv("AUTO_CLOSE_INATIVIDADE_MINUTOS", "5"))
        _intervalo = int(os.getenv("AUTO_CLOSE_INTERVAL_SECONDS", "60"))
        _batch = int(os.getenv("AUTO_CLOSE_BATCH_SIZE", "200"))
    except Exception:
        _inatividade, _intervalo, _batch = 5, 60, 200

    t = threading.Thread(target=worker_auto_close_atomic, args=(_inatividade, _intervalo, _batch), daemon=True, name="auto-close-worker")
    t.start()
    print(f"[AUTO-CLOSE] Worker rodando (thread {t.name})")
else:
    print("[AUTO-CLOSE] Worker desativado. Para ativar defina ENABLE_AUTO_CLOSE=1 no ambiente.")


# ---------------------------------------------------------------------
# Montagem estática e rotas de frontend
# ---------------------------------------------------------------------
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


print("[✓] Aplicação inicializada com rotas e worker (auto-close).")
