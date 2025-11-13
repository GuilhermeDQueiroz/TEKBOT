"""
Servidor de Análise Emulado (TESTE)
Executar: python servidor_simples.py
"""

import os
import json
import hmac
import hashlib
import random
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict
from datetime import datetime
import uvicorn

app = FastAPI(title="Servidor Emulado de Análise (TEST)")

EMULADO_VALIDATE_SIGNATURE = os.environ.get("EMULADO_VALIDATE_SIGNATURE", "0") == "1"
EMULADO_SECRET = os.environ.get("WEBHOOK_SECRET", None)  # shared secret

class DadosSessao(BaseModel):
    sessao_id: str
    user_email: str
    titulo: str
    total_interacoes: int
    interacoes: List[Dict]

class WebhookPayload(BaseModel):
    evento: str
    timestamp: str
    dados: DadosSessao
    signature: str

def validar_assinatura_simples(body_bytes: bytes, signature: str) -> bool:
    if not EMULADO_VALIDATE_SIGNATURE:
        return True
    if not EMULADO_SECRET or not signature:
        return False
    mac = hmac.new(EMULADO_SECRET.encode(), body_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac, signature)

def analisar_sessao_simples(dados: DadosSessao) -> Dict:
    total = dados.total_interacoes
    if total <= 3:
        nivel = "alto"; pontuacao = random.uniform(8.0, 10.0); comentario = "✅ Excelente!"
        sugestoes = ["Manter"]
    elif total <= 7:
        nivel = "medio"; pontuacao = random.uniform(5.0, 7.9); comentario = "⚠️ Satisfatório"
        sugestoes = ["Melhorar eficiência"]
    else:
        nivel = "baixo"; pontuacao = random.uniform(2.0, 4.9); comentario = "❌ Demorado"
        sugestoes = ["Revisar processo"]
    return {
        "nivel": nivel, "pontuacao": round(pontuacao, 2),
        "comentarios": comentario, "metricas": {"total_interacoes": total}, "sugestoes": sugestoes
    }

@app.get("/")
def home():
    return {"servico": "Servidor Emulado", "versao": "1.0", "status": "online", "porta": 8001}

@app.post("/analise-sessao")
def analisar_sessao(payload: WebhookPayload, request=None):
    # Nota: FastAPI já validou body conforme WebhookPayload
    # Se quiser validar HMAC, leia raw body — aqui simplificamos (FastAPI parseou)
    # Em produção valide via header e raw body
    print(f"[EMULADO] Recebido analise para sessao {payload.dados.sessao_id}")
    analise = analisar_sessao_simples(payload.dados)
    resposta = {"sessao_id": payload.dados.sessao_id, "analise": analise, "timestamp_analise": datetime.utcnow().isoformat() + "Z", "analisado_por": "emulado_v1"}
    return resposta

@app.post("/teste")
def teste_simples(dados: Dict):
    print(f"[EMULADO] Teste recebido: {dados}")
    return {"status": "ok", "dados_recebidos": dados, "timestamp": datetime.utcnow().isoformat()}

if __name__ == "__main__":
    print("Iniciando servidor emulado em http://localhost:8001")
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
