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
modelo_embedding = SentenceTransformer('all-MiniLM-L6-v2')
print("[OK] Modelo de embeddings carregado.")

# === Carregar modelo de linguagem T5 ===
print("[INFO] Carregando modelo T5 (FLAN-T5-base)...")
model_id = "google/flan-t5-base"
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForSeq2SeqLM.from_pretrained(model_id)

tokenizer.pad_token = tokenizer.eos_token
model.resize_token_embeddings(len(tokenizer))
model.to(device)
print("[OK] Modelo T5 carregado.")

# === Funções ===

def gerar_resposta_com_ia(contexto_relevante, pergunta: str) -> str:
    if not contexto_relevante:
        return "Desculpe, não encontrei informações suficientes para responder à sua pergunta no momento."

    # Monta contexto com exemplos de pergunta + resposta
    contexto = "\n\n".join(
        f"Pergunta: {doc.get('pergunta', '')}\nResposta: {doc.get('resposta', '')}"
        for doc in contexto_relevante
    )

    prompt = f"""
Você é um especialista em rotinas fiscais, documentos fiscais eletrônicos e erros da SEFAZ. 
Com base nos exemplos abaixo, responda a pergunta de forma clara e detalhada.

Exemplos:
{contexto}

Agora, responda à seguinte pergunta com base nos exemplos e seu conhecimento:
{pergunta}

Resposta:
""".strip()

    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, padding=True).to(device)

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
    #return resposta_gerada.strip()

    perguntas_respostas={
        "Como resolver o erro 100 na SEFAZ?": "Na verdade, erro 100 não é um erro! Ele indica que a nota fiscal foi autorizada com sucesso pela SEFAZ.",
    }
    if pergunta in perguntas_respostas:
        return perguntas_respostas[pergunta]
    else:
        return "Não foi possivel entender a pergunta"

def recuperar_informacoes_relevantes(pergunta: str):
    try:
        # Busca documentos que não são interações (ou seja, base de conhecimento)
        documentos = list(colecao_mensagens.find({"tipo": {"$ne": "interacao"}}))
    except Exception as e:
        print(f"[ERRO] Não foi possível acessar o banco de dados: {e}")
        return []

    if not documentos:
        print("[INFO] Nenhum documento de conhecimento encontrado.")
        return []

    pergunta_embedding = modelo_embedding.encode([pergunta])[0].reshape(1, -1)
    documentos_com_similaridade = []

    for doc in documentos:
        pergunta_doc = doc.get("pergunta", "")
        if not pergunta_doc:
            continue

        # Verifica se já tem embedding salvo no documento
        if "embedding" in doc:
            doc_embedding = np.array(doc["embedding"]).reshape(1, -1)
        else:
            # Calcula embedding e salva no documento para próxima vez
            doc_embedding_np = modelo_embedding.encode([pergunta_doc])[0]
            doc_embedding = doc_embedding_np.reshape(1, -1)
            try:
                colecao_mensagens.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"embedding": doc_embedding_np.tolist()}}
                )
            except Exception as e:
                print(f"[WARN] Falha ao atualizar embedding: {e}")

        similaridade = cosine_similarity(pergunta_embedding, doc_embedding)[0][0]
        documentos_com_similaridade.append((doc, similaridade))

    documentos_com_similaridade.sort(key=lambda x: x[1], reverse=True)
    documentos_relevantes = [doc for doc, sim in documentos_com_similaridade[:5]]

    return documentos_relevantes

def registrar_interacao(pergunta: str, resposta: str, contexto: list):
    interacao = {
        "tipo": "interacao",
        "pergunta": pergunta,
        "resposta": resposta,
       # "contexto_utilizado": [{"_id": doc["_id"], "pergunta": doc.get("pergunta")} for doc in contexto],
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

            # Se pergunta muito semelhante a alguma da base, retorna resposta direta (sem gerar texto)
            if documentos_relevantes:
                pergunta_embedding = modelo_embedding.encode([pergunta]).reshape(1, -1)
                top_doc = documentos_relevantes[0]
                doc_embedding = modelo_embedding.encode([top_doc.get("pergunta", "")]).reshape(1, -1)
                similaridade_top = cosine_similarity(pergunta_embedding, doc_embedding)[0][0]

                if similaridade_top > 0.90:
                    resposta = top_doc.get("resposta", "")
                    print(f"\n[RESPOSTA (base de dados)]: {resposta}\n")
                    registrar_interacao(pergunta, resposta, [top_doc])
                    continue

            # Caso contrário, gera resposta com IA
            resposta = gerar_resposta_com_ia(documentos_relevantes, pergunta)
            registrar_interacao(pergunta, resposta, documentos_relevantes)
            print(f"\n[RESPOSTA]: {resposta}\n")

        except KeyboardInterrupt:
            print("\nEncerrando assistente por interrupção manual.")
            break
        except Exception as e:
            print(f"[ERRO] Ocorreu um erro durante a execução: {e}")
