from pymongo import MongoClient
import os

# Carregar variáveis de ambiente
from dotenv import load_dotenv

load_dotenv()

# Conectar ao MongoDB
cliente = MongoClient(os.getenv("MONGO_URI"))
banco_de_dados = cliente["tekbot"]  # Banco de dados do chatbot
colecao_usuarios = banco_de_dados["users"]
colecao_mensagens = banco_de_dados["messages"]
