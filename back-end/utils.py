from datetime import datetime
from pymongo.errors import DuplicateKeyError

# Função para salvar um usuário no MongoDB
from database import users_collection

def criar_usuario(dados_usuario):
    try:
        # Criar o usuário no MongoDB
        usuario = users_collection.insert_one(dados_usuario)
        return usuario.inserted_id
    except DuplicateKeyError:
        return None

# Função para buscar um usuário por e-mail
def buscar_usuario_por_email(email):
    return users_collection.find_one({"email": email})

# Função para salvar uma mensagem no MongoDB
from database import messages_collection

def salvar_mensagem(dados_mensagem):
    dados_mensagem["timestamp"] = datetime.utcnow()
    messages_collection.insert_one(dados_mensagem)
