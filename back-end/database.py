from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

cliente = MongoClient(os.getenv("MONGO_URI"))
banco_de_dados = cliente["tekbot"]

colecao_usuarios = banco_de_dados["usuarios"]
colecao_mensagens = banco_de_dados["mensagem"]

colecao_sessoes = banco_de_dados["sessoes"]
colecao_interacoes = banco_de_dados["interacoes"]
colecao_tickets = banco_de_dados["tickets"]