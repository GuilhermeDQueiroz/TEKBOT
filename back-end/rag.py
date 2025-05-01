from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
import torch
import numpy as np
from database import colecao_mensagens  # Sua coleção MongoDB
import time

# Inicializar o modelo de embeddings
print("[INFO] Carregando modelo de embeddings...")
modelo_embedding = SentenceTransformer('all-MiniLM-L6-v2')
print("[OK] Modelo de embeddings carregado.")

# Função para escolher o melhor tipo de tensor suportado pela GPU
def detectar_tipo_tensor():
    if not torch.cuda.is_available():
        print("[INFO] CUDA não disponível. Usando CPU com float32.")
        return torch.float32
    try:
        torch.tensor([1.0], dtype=torch.bfloat16, device="cuda")
        print("[INFO] Usando torch.bfloat16 com CUDA.")
        return torch.bfloat16
    except:
        try:
            torch.tensor([1.0], dtype=torch.float16, device="cuda")
            print("[INFO] bfloat16 não suportado. Usando torch.float16.")
            return torch.float16
        except:
            print("[INFO] Nenhuma aceleração suportada. Usando torch.float32.")
            return torch.float32

# Detectar tipo de tensor compatível
tipo_tensor = detectar_tipo_tensor()
dispositivo = "cuda" if torch.cuda.is_available() else "cpu"

# Inicializar o modelo de geração de texto LLaMA 3
print("[INFO] Carregando modelo de geração de texto LLaMA 3...")
model_id = "meta-llama/Meta-Llama-3-8B-Instruct"
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(
    model_id,
    torch_dtype=tipo_tensor,
    device_map="auto" if dispositivo == "cuda" else "cpu"
)
print("[OK] Modelo de geração carregado.")

def gerar_resposta_com_ia(contexto_relevante, pergunta):
    """
    Gera uma resposta com base nos documentos relevantes e na pergunta.
    """
    print("[INFO] Gerando resposta com base no contexto e pergunta.")
    contexto = "\n".join(doc["texto"] for doc in contexto_relevante)
    prompt = f"Com base nas informações abaixo, responda à pergunta de forma concisa e clara:\n\n{contexto}\n\nPergunta: {pergunta}\nResposta:"

    inputs = tokenizer(prompt, return_tensors="pt").to(device=model.device)
    inicio = time.time()
    outputs = model.generate(**inputs, max_new_tokens=256, temperature=0.7, top_p=0.9)
    fim = time.time()

    print(f"[OK] Resposta gerada em {fim - inicio:.2f}s")
    resposta_gerada = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return resposta_gerada

def recuperar_informacoes_relevantes(pergunta: str):
    """
    Busca os documentos mais relevantes com base na similaridade de embeddings.
    Usa cache de embeddings no MongoDB.
    """
    print(f"[INFO] Gerando embedding da pergunta: '{pergunta}'")
    inicio = time.time()
    pergunta_embedding = modelo_embedding.encode([pergunta])
    fim = time.time()
    print(f"[INFO] Embedding da pergunta gerado em {fim - inicio:.2f}s")

    documentos = list(colecao_mensagens.find({}))
    print(f"[INFO] {len(documentos)} documentos carregados do banco.")

    documentos_com_similaridade = []

    for doc in documentos:
        if "embedding" in doc:
            doc_embedding = np.array(doc["embedding"]).reshape(1, -1)
            print(f"[DEBUG] Usando embedding em cache para documento: {doc['_id']}")
        else:
            print(f"[DEBUG] Gerando novo embedding para documento: {doc['_id']}")
            doc_embedding_np = modelo_embedding.encode([doc["texto"]])[0]
            doc_embedding = doc_embedding_np.reshape(1, -1)
            colecao_mensagens.update_one(
                {"_id": doc["_id"]},
                {"$set": {"embedding": doc_embedding_np.tolist()}}
            )

        similaridade = cosine_similarity(pergunta_embedding, doc_embedding)
        documentos_com_similaridade.append((doc, similaridade[0][0]))

    documentos_com_similaridade.sort(key=lambda x: x[1], reverse=True)
    print("[INFO] Documentos ordenados por similaridade.")
    
    documentos_relevantes = [doc for doc, _ in documentos_com_similaridade[:3]]
    for idx, doc in enumerate(documentos_relevantes):
        print(f"[TOP {idx+1}] Documento: {doc.get('texto')[:80]}...")  # Mostra início do texto

    return documentos_relevantes
