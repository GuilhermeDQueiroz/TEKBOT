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
colecao_feedback_ia = banco_de_dados["feedback_ia"]
colecao_tickets = banco_de_dados["tickets"]
# COLEÇÕES WEBHOOK
colecao_webhook_config = banco_de_dados["webhook_config"]
colecao_webhook_feedbacks = banco_de_dados["webhook_feedbacks"]
colecao_webhook_logs = banco_de_dados["webhook_logs"]