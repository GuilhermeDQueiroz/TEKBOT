import os
import torch
import numpy as np
from datetime import datetime, timezone
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
from database import colecao_mensagens, colecao_interacoes
import google.generativeai as genai
from typing import List, Dict, Optional

# === Configuração de ambiente ===
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

try:
    GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GOOGLE_API_KEY:
        raise ValueError("A variável de ambiente GEMINI_API_KEY não foi definida.")
    genai.configure(api_key=GOOGLE_API_KEY)
    print("[OK] API do Gemini configurada.")
except Exception as e:
    print(f"[ERRO] Falha ao configurar a API do Gemini: {e}")

# === Carregar modelo de embeddings ===
print("[INFO] Carregando modelo de embeddings...")
modelo_embedding = SentenceTransformer('all-MiniLM-L6-v2')
print("[OK] Modelo de embeddings carregado.")


# ==========================
# CONTEXTO & HISTÓRICO
# ==========================
def obterHistoricoSessao(sessao_id: str, limite: int = 5) -> str:
    try:
        interacoes = list(
            colecao_interacoes.find({"sessao_id": sessao_id})
            .sort("timestamp", -1)
            .limit(limite)
        )
        if not interacoes:
            return ""
        interacoes.reverse()
        contexto_texto = "HISTÓRICO DA CONVERSA ATUAL:\n"
        for i, interacao in enumerate(interacoes, 1):
            contexto_texto += f"\n{i}. USUÁRIO: {interacao['pergunta']}\n"
            contexto_texto += f"   ASSISTENTE: {interacao['resposta']}\n"
        return contexto_texto
    except Exception as e:
        print(f"[ERRO] Falha ao obter histórico da sessão: {e}")
        return ""


def verificarContinuidade(pergunta: str, sessao_id: str) -> bool:
    try:
        if not colecao_interacoes.find_one({"sessao_id": sessao_id}):
            return False
        palavras_continuacao = [
            'continue', 'continuar', 'mais', 'detalhe', 'detalhes', 'explique melhor',
            'como assim', 'e depois', 'próximo', 'passo', 'então', 'e se', 'mas',
            'e', 'também', 'além disso', 'outra coisa'
        ]
        pergunta_lower = pergunta.lower()
        return any(p in pergunta_lower for p in palavras_continuacao)
    except Exception as e:
        print(f"[ERRO] Falha ao verificar continuidade: {e}")
        return False


def obterUltimaResposta(sessao_id: str) -> Optional[str]:
    try:
        ultima_interacao = colecao_interacoes.find_one(
            {"sessao_id": sessao_id},
            sort=[("timestamp", -1)]
        )
        return ultima_interacao.get('resposta') if ultima_interacao else None
    except Exception as e:
        print(f"[ERRO] Falha ao obter última resposta: {e}")
        return None


# ==========================
# BUSCA RELEVANTE (mensagens + interações)
# ==========================
def recuperarInfoRelevantes(pergunta: str, sessao_id: Optional[str] = None) -> List[Dict]:
    """Recupera documentos relevantes da base de conhecimento e interações anteriores"""
    try:
        if sessao_id and verificarContinuidade(pergunta, sessao_id):
            print("[INFO] Detectada continuação - usando apenas contexto da conversa")
            return []

        documentos = list(colecao_mensagens.find())
        interacoes_passadas = list(colecao_interacoes.find())

        todos_docs = []
        for d in documentos:
            todos_docs.append({
                "_id": d["_id"],
                "texto": d.get("pergunta", "") or d.get("texto", ""),
                "resposta": d.get("resposta", ""),
                "embedding": d.get("embedding", []),
                "tipo": "base"
            })
        for i in interacoes_passadas:
            todos_docs.append({
                "_id": i["_id"],
                "texto": i.get("pergunta", ""),
                "resposta": i.get("resposta", ""),
                "embedding": i.get("embedding", []),
                "tipo": "interacao"
            })

    except Exception as e:
        print(f"[ERRO] Acesso ao banco falhou: {e}")
        return []

    if not todos_docs:
        return []

    pergunta_embedding = modelo_embedding.encode([pergunta])[0].reshape(1, -1)
    documentos_com_similaridade = []

    for doc in todos_docs:
        if not doc["texto"]:
            continue

        if doc["embedding"]:
            doc_embedding = np.array(doc["embedding"]).reshape(1, -1)
        else:
            doc_embedding_np = modelo_embedding.encode([doc["texto"]])[0]
            doc_embedding = doc_embedding_np.reshape(1, -1)
            try:
                if doc["tipo"] == "base":
                    colecao_mensagens.update_one(
                        {"_id": doc["_id"]},
                        {"$set": {"embedding": doc_embedding_np.tolist()}}
                    )
                else:
                    colecao_interacoes.update_one(
                        {"_id": doc["_id"]},
                        {"$set": {"embedding": doc_embedding_np.tolist()}}
                    )
            except Exception as e:
                print(f"[WARN] Não foi possível salvar embedding: {e}")

        similaridade = cosine_similarity(pergunta_embedding, doc_embedding)[0][0]
        documentos_com_similaridade.append((doc, similaridade))

    documentos_com_similaridade.sort(key=lambda x: x[1], reverse=True)
    resultado = [doc for doc, sim in documentos_com_similaridade[:5] if sim > 0.6]

    print(f"[INFO] Encontrados {len(resultado)} documentos relevantes")
    return resultado


# ==========================
# GERAÇÃO DE RESPOSTA
# ==========================
def gerarRespostaComIa(
    contexto_relevante: List,
    pergunta: str,
    sessao_id: Optional[str] = None,
    incluir_historico: bool = True
) -> str:
    contexto_base = ""
    if contexto_relevante:
        contexto_base = "\n".join(
            f"P: {doc['texto']}\nR: {doc.get('resposta','')}"
            for doc in contexto_relevante
        )

    contexto_conversa = ""
    eh_continuacao = False
    if sessao_id and incluir_historico:
        contexto_conversa = obterHistoricoSessao(sessao_id, limite=5)
        eh_continuacao = verificarContinuidade(pergunta, sessao_id)

    if eh_continuacao:
        ultima_resposta = obterUltimaResposta(sessao_id)
        prompt = f"""
Você é um atendente especialista em sistema ERP.
O usuário pediu continuação da resposta anterior.

{contexto_conversa}

ÚLTIMA RESPOSTA:
{ultima_resposta}

NOVA PERGUNTA: {pergunta}

Continue ou detalhe a resposta anterior:
"""
    else:
        prompt = f"""
Você é um atendente especialista em sistema ERP.
Use histórico da conversa e conhecimento base.

{contexto_conversa}

CONHECIMENTO BASE RELEVANTE:
{contexto_base}

NOVA PERGUNTA: {pergunta}

Responda de forma clara e objetiva:
"""

    try:
        model = genai.GenerativeModel('models/gemini-2.5-pro')
        generation_config = {"temperature": 0.3, "max_output_tokens": 2048}
        response = model.generate_content(prompt, generation_config=generation_config)
        return response.text.strip()
    except Exception as e:
        print(f"[ERRO] Erro ao chamar a API Gemini: {e}")
        return "Erro ao gerar resposta com a IA do Gemini."


# ==========================
# REGISTRO DE INTERAÇÃO
# ==========================
def registrarInteracao(pergunta: str, resposta: str, contexto: List, sessao_id: Optional[str] = None):
    try:
        embedding = modelo_embedding.encode([pergunta])[0].tolist()
        interacao = {
            "tipo": "interacao",
            "pergunta": pergunta,
            "resposta": resposta,
            "contexto_utilizado": [
                {"_id": str(doc.get("_id", "")), "texto": doc.get("texto", "")}
                for doc in contexto if isinstance(doc, dict)
            ],
            "embedding": embedding,
            "sessao_id": sessao_id,
            "timestamp": datetime.now(timezone.utc)
        }
        colecao_interacoes.insert_one(interacao)
        print("[INFO] Interação registrada no banco de dados.")
    except Exception as e:
        print(f"[ERRO] Falha ao salvar interação: {e}")


# ==========================
# PIPELINE COMPLETO
# ==========================
def processarPergunta(pergunta: str, sessao_id: Optional[str] = None) -> str:
    contexto_relevante = recuperarInfoRelevantes(pergunta, sessao_id)
    resposta = ""

    if contexto_relevante:
        pergunta_embedding = modelo_embedding.encode([pergunta]).reshape(1, -1)
        doc_top = contexto_relevante[0]
        doc_embedding = modelo_embedding.encode([doc_top["texto"]]).reshape(1, -1)
        similaridade = cosine_similarity(pergunta_embedding, doc_embedding)[0][0]
        if similaridade > 0.9 and doc_top.get("resposta"):
            resposta = doc_top["resposta"]
            registrarInteracao(pergunta, resposta, [doc_top], sessao_id)
            return resposta

    resposta = gerarRespostaComIa(contexto_relevante, pergunta, sessao_id)
    registrarInteracao(pergunta, resposta, contexto_relevante, sessao_id)
    return resposta
