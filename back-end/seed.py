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

def carregar_mensagens_xml(path):
    mensagens = []
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        for erro in root.findall("erro"):
            codigo = erro.get("codigo")
            descricao = erro.find("descricao").text.strip()
            solucao = "\n".join([passo.text.strip() for passo in erro.findall("solucao/passo")])
            mensagem = f"Rejeição {codigo}: {descricao}\nSoluções:\n{solucao}"
            if mensagem:
                mensagens.append(mensagem)
    except Exception as e:
        print(f"[ERRO] Falha ao ler '{path}': {e}")
    return mensagens

def carregar_mensagens_fp3(path):
    mensagens = []
    try:
        with open(path, "r", encoding="utf-8") as arquivo:
            conteudo = arquivo.read()

        # Extrai todas as soluções e descrições
        solucoes = re.findall(r'<m17[^>]*u="Solução: (.*?)"\s*/>', conteudo)
        descricoes = re.findall(r'<m18[^>]*u="Descrição: (.*?)"\s*/>', conteudo)

        for solucao, descricao in zip(solucoes, descricoes):
            solucao = solucao.replace('&#13;&#10;', '\n').replace('&#34;', '"').strip()
            descricao = descricao.replace('&#13;&#10;', '\n').replace('&#34;', '"').strip()
            mensagem = f"Descrição:\n{descricao}\n\nSolução:\n{solucao}"
            mensagens.append(mensagem)

    except Exception as e:
        print(f"[ERRO] Falha ao ler '{path}': {e}")
    return mensagens

def inserir_mensagens(colecao, mensagens):
    for texto in mensagens:
        try:
            if colecao.find_one({"texto": texto}):
                print(f"[SKIP] Já existe: {texto[:60]}...")
                continue

            embedding = modelo_embedding.encode([texto])[0]
            colecao.insert_one({
                "texto": texto,
                "embedding": embedding.tolist()
            })
            print(f"[OK] Inserido: {texto[:60]}...")
        except Exception as e:
            print(f"[ERRO] Falha ao inserir '{texto[:60]}...': {e}")

if __name__ == "__main__":
    print("[INFO] Conectando ao MongoDB...")
    colecao = conectar_mongodb(MONGO_URI)
    print("[OK] Conectado.")

    print("[INFO] Carregando mensagens...")
    mensagens = []

    if os.path.exists("mensagens.xml"):
        mensagens_xml = carregar_mensagens_xml("mensagens.xml")
        mensagens += mensagens_xml
        print(f"[OK] mensagens.xml carregado com {len(mensagens_xml)} mensagens.")

    if os.path.exists("mensagens.fp3"):
        mensagens_fp3 = carregar_mensagens_fp3("mensagens.fp3")
        mensagens += mensagens_fp3
        print(f"[OK] mensagens.fp3 carregado com {len(mensagens_fp3)} mensagens.")

    if not mensagens:
        print("[AVISO] Nenhuma mensagem para inserir.")
        sys.exit(0)

    print(f"[INFO] Total de mensagens a inserir: {len(mensagens)}")
    inserir_mensagens(colecao, mensagens)
    print("[FINALIZADO] Processo concluído.")
