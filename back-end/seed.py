from pymongo import MongoClient, errors
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import os
import sys
import xml.etree.ElementTree as ET
import re

# === Carrega variáveis de ambiente ===
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    print("[ERRO] Variável de ambiente MONGO_URI não definida.")
    sys.exit(1)

# === Inicializa modelo de embedding ===
print("[INFO] Carregando modelo de embeddings...")
modelo_embedding = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
print("[OK] Modelo carregado com sucesso.")

def conectar_mongodb(uri):
    try:
        client = MongoClient(uri)
        db = client["tekbot"]
        return db["mensagens"]
    except errors.ConnectionFailure as e:
        print(f"[ERRO] Falha na conexão com o MongoDB: {e}")
        sys.exit(1)

def carregarMensagemXml(path):
    mensagens = []
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        for item in root.findall("mensagem"):
            pergunta_el = item.find("pergunta")
            resposta_el = item.find("resposta")

            if pergunta_el is not None and resposta_el is not None:
                pergunta = pergunta_el.text.strip()
                resposta = resposta_el.text.strip()
                mensagens.append({"pergunta": pergunta, "resposta": resposta})
    except Exception as e:
        print(f"[ERRO] Falha ao ler '{path}': {e}")
    return mensagens

def carregarMensagemFp3(path):
    mensagens = []
    try:
        with open(path, "r", encoding="utf-8") as arquivo:
            conteudo = arquivo.read()

        solucoes = re.findall(r'<m17[^>]*u="Solução: (.*?)"\s*/>', conteudo)
        descricoes = re.findall(r'<m18[^>]*u="Descrição: (.*?)"\s*/>', conteudo)

        for solucao, descricao in zip(solucoes, descricoes):
            solucao = solucao.replace('&#13;&#10;', '\n').replace('&#34;', '"').strip()
            descricao = descricao.replace('&#13;&#10;', '\n').replace('&#34;', '"').strip()
            mensagens.append({
                "pergunta": descricao,
                "resposta": solucao
            })

    except Exception as e:
        print(f"[ERRO] Falha ao ler '{path}': {e}")
    return mensagens

def inserir_mensagens(colecao, mensagens):
    for item in mensagens:
        pergunta = item["pergunta"]
        resposta = item["resposta"]
        try:
            if colecao.find_one({"pergunta": pergunta}):
                print(f"[SKIP] Já existe: {pergunta[:60]}...")
                continue

            embedding = modelo_embedding.encode([pergunta])[0]
            colecao.insert_one({
                "pergunta": pergunta,
                "resposta": resposta,
                "embedding": embedding.tolist()
            })
            print(f"[OK] Inserido: {pergunta[:60]}...")

        except Exception as e:
            print(f"[ERRO] Falha ao inserir '{pergunta[:60]}...': {e}")

if __name__ == "__main__":
    print("[INFO] Conectando ao MongoDB...")
    colecao = conectar_mongodb(MONGO_URI)
    print("[OK] Conectado.")

    print("[INFO] Carregando mensagens...")
    mensagens = []

    if os.path.exists("mensagens_rag.xml"):
        mensagens_xml = carregarMensagemXml("mensagens_rag.xml")
        mensagens += mensagens_xml
        print(f"[OK] mensagens_rag.xml carregado com {len(mensagens_xml)} mensagens.")

    if os.path.exists("mensagens.fp3"):
        mensagens_fp3 = carregarMensagemFp3("mensagens.fp3")
        mensagens += mensagens_fp3
        print(f"[OK] mensagens.fp3 carregado com {len(mensagens_fp3)} mensagens.")

    if not mensagens:
        print("[AVISO] Nenhuma mensagem para inserir.")
        sys.exit(0)

    print(f"[INFO] Total de mensagens a inserir: {len(mensagens)}")
    inserir_mensagens(colecao, mensagens)
    print("[FINALIZADO] Processo concluído.")
