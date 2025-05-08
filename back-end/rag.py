import os
import torch
import numpy as np
from datetime import datetime, timezone
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from database import colecao_mensagens

# === Configuração de ambiente ===
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# === Carregar modelo de embeddings ===
print("[INFO] Carregando modelo de embeddings...")
modelo_embedding = SentenceTransformer('meta-llama/Meta-Llama-3-8B')
print("[OK] Modelo de embeddings carregado.")

# === Carregar modelo de linguagem T5 ===
print("[INFO] Carregando modelo T5 (FLAN-T5-base)...")
model_id = "meta-llama/Meta-Llama-3-8B"
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForSeq2SeqLM.from_pretrained(model_id)

tokenizer.pad_token = tokenizer.eos_token
model.resize_token_embeddings(len(tokenizer))
model.to(device)
print("[OK] Modelo T5 carregado.")

# === Funções ===

def gerar_resposta_com_ia(contexto_relevante, pergunta: str) -> str:
    contexto = "\n".join(f"- {doc.get('mensagens', '')}" for doc in contexto_relevante) \
               if contexto_relevante else "Nenhuma informação adicional foi encontrada no banco de dados."

    prompt = f"""
Você é um especialista em rotinas fiscais e erros da SEFAZ. Com base nas mensagens abaixo, ajude com uma explicação:

Contexto relevante:
{contexto}

Pergunta: {pergunta}

Resposta:
""".strip()

    inputs = tokenizer(prompt, return_tensors="pt").to(device)

    with torch.no_grad():
        outputs = model.generate(
            input_ids=inputs["input_ids"],
            attention_mask=inputs["attention_mask"],
            max_new_tokens=300,
            temperature=0.7,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id
        )

    resposta_gerada = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return resposta_gerada.replace(prompt, "").strip()
def recuperar_informacoes_relevantes(pergunta: str):
    try:
        documentos = list(colecao_mensagens.find({"tipo": {"$ne": "interacao"}}))
    except Exception as e:
        print(f"[ERRO] Não foi possível acessar o banco de dados: {e}")
        return []

    if not documentos:
        print("[INFO] Nenhum documento com mensagens encontrado.")
        return []

    pergunta_embedding = modelo_embedding.encode([pergunta])[0].reshape(1, -1)
    documentos_com_similaridade = []

    for doc in documentos:
        texto_doc = doc.get("mensagens", "")
        if not texto_doc:
            continue

        if "embedding" in doc:
            doc_embedding = np.array(doc["embedding"]).reshape(1, -1)
        else:
            doc_embedding_np = modelo_embedding.encode([texto_doc])[0]
            doc_embedding = doc_embedding_np.reshape(1, -1)
            try:
                colecao_mensagens.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"embedding": doc_embedding_np.tolist()}}
                )
            except Exception as e:
                print(f"[WARN] Falha ao atualizar embedding: {e}")

        similaridade = cosine_similarity(pergunta_embedding, doc_embedding)
        documentos_com_similaridade.append((doc, similaridade[0][0]))

    documentos_com_similaridade.sort(key=lambda x: x[1], reverse=True)
    documentos_relevantes = [doc for doc, _ in documentos_com_similaridade[:5]]

    return documentos_relevantes

def registrar_interacao(pergunta: str, resposta: str, contexto: list):
    interacao = {
        "tipo": "interacao",
        "pergunta": pergunta,
        "resposta": resposta,
        "contexto_utilizado": contexto,
        "data": datetime.now(timezone.utc)
    }

    try:
        colecao_mensagens.insert_one(interacao)
        print("[INFO] Interação registrada com sucesso.")
    except Exception as e:
        print(f"[ERRO] Falha ao registrar a interação: {e}")

# === Execução interativa via terminal ===
if __name__ == "__main__":
    print("\n[ASSISTENTE ERP - Tek-System Informática]")
    print("Pergunte sobre rotinas fiscais, erros de NFe, MDF-e, SPED, etc.")
    print("Digite 'sair' para encerrar.\n")

    while True:
        try:
            pergunta = input("Pergunta: ").strip()
            if not pergunta:
                continue
            if pergunta.lower() == 'sair':
                print("Encerrando assistente.")
                break

            documentos_relevantes = recuperar_informacoes_relevantes(pergunta)
            resposta = gerar_resposta_com_ia(documentos_relevantes, pergunta)
            registrar_interacao(pergunta, resposta, documentos_relevantes)

        except KeyboardInterrupt:
            print("\nEncerrando assistente por interrupção manual.")
            break
        except Exception as e:
            print(f"[ERRO] Ocorreu um erro durante a execução: {e}")
