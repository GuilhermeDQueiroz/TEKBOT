import os
import torch
import numpy as np
<<<<<<< HEAD
=======
import requests
>>>>>>> Master
from datetime import datetime, timezone
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
from database import colecao_mensagens
<<<<<<< HEAD
import google.generativeai as genai

# === Configuração de ambiente ===
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Configuração da API do Gemini
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
print("[INFO] Utilizando a API do Gemini (Google AI)...")


# === Funções ===

def gerar_resposta_com_ia(contexto_relevante, pergunta):
    """Gera uma resposta usando a API do Gemini com base em um contexto."""
    if not contexto_relevante:
        return "Desculpe, não encontrei informações suficientes para responder à sua pergunta no momento."

=======

#Configuração de ambiente
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

#Carregar modelo de embeddings
print("[INFO] Carregando modelo de embeddings...")
modelo_embedding = SentenceTransformer('all-MiniLM-L6-v2')
print("[OK] Modelo de embeddings carregado.")

#Info sobre LLaMA via Ollama
print("[INFO] Utilizando LLaMA 3 via Ollama (localhost:11434)...")

#Histórico de conversas
historico_conversas = []

#Funções

def gerar_resposta_com_ia(contexto_relevante, pergunta):
    if not contexto_relevante:
        return "Desculpe, não encontrei informações suficientes para responder à sua pergunta no momento."

    #Monta o contexto baseado nos documentos encontrados
>>>>>>> Master
    contexto = "\n".join(
        f"Pergunta: {doc.get('pergunta', '')}\nResposta: {doc.get('resposta', '')}"
        for doc in contexto_relevante
    )

    prompt = f"""
<<<<<<< HEAD
Você é um atendente especialista em sistema ERP.
Com base no histórico abaixo, responda a próxima pergunta do usuário com clareza e objetividade.

Histórico de perguntas e respostas:
{contexto}

Nova pergunta do usuário: {pergunta}
Resposta:
"""
    try:
        # Seleciona o modelo do Gemini (gemini-1.5-flash é rápido e eficiente)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')

        # Configurações de geração para controlar a saída da IA
        generation_config = {
            "temperature": 0.3,
            "max_output_tokens": 512,
        }

        response = model.generate_content(
            prompt,
            generation_config=generation_config
        )

        return response.text.strip()

    except Exception as e:
        print(f"[ERRO] Erro ao chamar a API Gemini: {e}")
        return "Erro ao gerar resposta com a IA do Gemini."
=======
Você é um especialista em sistemas fiscais e SEFAZ.
Use as informações abaixo como base de conhecimento técnica para responder à pergunta do usuário com clareza e objetividade.

Base de conhecimento:
{contexto}

Pergunta: {pergunta}
Resposta objetiva, sem mencionar se a pergunta já foi feita antes:
"""

    #Requisição para o Ollama
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3",
            "prompt": prompt,
            "stream": False,
            "temperature": 0.7,
            "num_predict": 512
        }
    )

    if response.ok:
        return response.json()['response'].strip()
    else:
        return "Erro ao gerar resposta com LLaMA."
>>>>>>> Master


def recuperar_informacoes_relevantes(pergunta: str):
    try:
        documentos = list(colecao_mensagens.find({"tipo": {"$ne": "interacao"}}))
    except Exception as e:
        print(f"[ERRO] Acesso ao banco falhou: {e}")
        return []

    if not documentos:
        return []

    pergunta_embedding = modelo_embedding.encode([pergunta])[0].reshape(1, -1)
    documentos_com_similaridade = []

    for doc in documentos:
        pergunta_doc = doc.get("pergunta", "")
        if not pergunta_doc:
            continue

        if "embedding" in doc:
            doc_embedding = np.array(doc["embedding"]).reshape(1, -1)
        else:
<<<<<<< HEAD
            # Gera e salva o embedding se não existir no documento
=======
>>>>>>> Master
            doc_embedding_np = modelo_embedding.encode([pergunta_doc])[0]
            doc_embedding = doc_embedding_np.reshape(1, -1)
            try:
                colecao_mensagens.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"embedding": doc_embedding_np.tolist()}}
                )
            except Exception as e:
                print(f"[WARN] Não foi possível salvar embedding: {e}")

        similaridade = cosine_similarity(pergunta_embedding, doc_embedding)[0][0]
        documentos_com_similaridade.append((doc, similaridade))

    documentos_com_similaridade.sort(key=lambda x: x[1], reverse=True)
    return [doc for doc, sim in documentos_com_similaridade[:5] if sim > 0.6]


def registrar_interacao(pergunta: str, resposta: str, contexto: list):
    interacao = {
        "tipo": "interacao",
        "pergunta": pergunta,
        "resposta": resposta,
        "contexto_utilizado": [{"_id": doc["_id"], "pergunta": doc.get("pergunta")} for doc in contexto if isinstance(doc, dict)],
        "data": datetime.now(timezone.utc)
    }
<<<<<<< HEAD
=======

>>>>>>> Master
    try:
        colecao_mensagens.insert_one(interacao)
        print("[INFO] Interação salva no banco de dados.")
    except Exception as e:
        print(f"[ERRO] Falha ao salvar interação: {e}")


def treinar_nova_pergunta(pergunta: str, resposta: str):
<<<<<<< HEAD
    """Simula aprendizado incremental armazenando a pergunta e resposta como novo dado de conhecimento."""
=======
>>>>>>> Master
    try:
        embedding = modelo_embedding.encode([pergunta])[0].tolist()
        novo_conhecimento = {
            "tipo": "base_conhecimento",
            "pergunta": pergunta,
            "resposta": resposta,
            "embedding": embedding,
            "data": datetime.now(timezone.utc)
        }
        colecao_mensagens.insert_one(novo_conhecimento)
        print("[INFO] Nova pergunta/resposta registrada na base de conhecimento.")
    except Exception as e:
        print(f"[ERRO] Falha ao treinar nova pergunta: {e}")

<<<<<<< HEAD
# === Execução via terminal para testes ===
if __name__ == "__main__":
    print("\n[ASSISTENTE ERP - Tek-System IA com Gemini]")
=======
#Execução via terminal
if __name__ == "__main__":
    print("\n[ASSISTENTE ERP - Tek-System IA com LLaMA 3 via Ollama]")
>>>>>>> Master
    print("Pergunte sobre rotinas fiscais, NFe, SPED, SEFAZ.")
    print("Digite 'sair' para encerrar, ou 'aprender' para ensinar algo novo.\n")

    while True:
        try:
            pergunta = input("Pergunta: ").strip()
            if not pergunta:
                continue
            if pergunta.lower() == "sair":
                print("Encerrando assistente.")
                break
            if pergunta.lower().startswith("aprender"):
                nova_pergunta = input("Nova pergunta: ").strip()
                nova_resposta = input("Resposta correta: ").strip()
                treinar_nova_pergunta(nova_pergunta, nova_resposta)
                continue

            documentos_relevantes = recuperar_informacoes_relevantes(pergunta)

<<<<<<< HEAD
            # Otimização: Se a pergunta for muito similar a uma já existente, usa a resposta direta
            if documentos_relevantes:
                pergunta_embedding = modelo_embedding.encode([pergunta]).reshape(1, -1)
                doc_top = documentos_relevantes[0]
                doc_embedding = modelo_embedding.encode([doc_top.get("pergunta", "")]).reshape(1, -1)
                similaridade = cosine_similarity(pergunta_embedding, doc_embedding)[0][0]
                if similaridade > 0.9:
                    resposta = doc_top.get("resposta", "")
                    print(f"\n[RESPOSTA (base)]: {resposta}\n")
                    registrar_interacao(pergunta, resposta, [doc_top])
                    continue

=======
            # Refina para pegar a pergunta mais parecida (e evitar responder duplicado)
            pergunta_embedding = modelo_embedding.encode([pergunta]).reshape(1, -1)
            encontrou_pergunta_igual = False

            for doc in documentos_relevantes:
                doc_embedding = modelo_embedding.encode([doc.get("pergunta", "")]).reshape(1, -1)
                similaridade = cosine_similarity(pergunta_embedding, doc_embedding)[0][0]
                if similaridade >= 0.95:
                    # Garante que não é a mesma resposta anterior (evita redundância do tipo "você já perguntou...")
                    if doc.get("resposta", "").strip().lower().startswith("não retransmita") or "você já perguntou" in doc.get("resposta", "").lower():
                        continue
                    resposta = doc.get("resposta", "")
                    print(f"\n[RESPOSTA (base conhecida)]: {resposta}\n")
                    registrar_interacao(pergunta, resposta, [doc])
                    encontrou_pergunta_igual = True
                    break

            if encontrou_pergunta_igual:
                continue

            # Caso não encontre resposta diretamente relacionada, usa LLaMA com contexto
>>>>>>> Master
            resposta = gerar_resposta_com_ia(documentos_relevantes, pergunta)
            registrar_interacao(pergunta, resposta, documentos_relevantes)
            print(f"\n[RESPOSTA (IA)]: {resposta}\n")

        except KeyboardInterrupt:
            print("\nEncerrando assistente.")
            break
        except Exception as e:
<<<<<<< HEAD
            print(f"[ERRO]: {e}")
=======
            print(f"[ERRO]: {e}")
>>>>>>> Master
