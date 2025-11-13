"""
Script de teste para o fluxo de webhook.
Gera HMAC usando WEBHOOK_SECRET se definido no env local,
ou usa a secret constante abaixo (apenas para testes locais).
"""

import os
import requests
import json
import time
import hmac
import hashlib
from datetime import datetime

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
TERCEIRO_URL = os.environ.get("TERCEIRO_URL", "http://localhost:8001")

# CREDENCIAIS DE TESTE (ajuste ou leia do env)
EMAIL_ADMIN = os.environ.get("TEST_EMAIL", "contato.thiagofreitasp@gmail.com")
SENHA_ADMIN = os.environ.get("TEST_SENHA", "12345678")

# SECRET usado para assinar (se não vier do env, usamos este para testes)
SECRET_KEY = os.environ.get("WEBHOOK_SECRET", "a0f8d5c3e2b1a9d7c5b4e3f2a1b0c9d8e7f6a5b4c3d2e1f0")

DEFAULT_TIMEOUT = 10

def gerar_signature(payload: dict, secret: str) -> str:
    payload_json = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hmac.new(secret.encode(), payload_json.encode(), hashlib.sha256).hexdigest()

def fazer_login():
    print("Fazendo login...")
    r = requests.post(f"{API_BASE_URL}/login", json={"email": EMAIL_ADMIN, "senha": SENHA_ADMIN}, timeout=DEFAULT_TIMEOUT)
    if r.status_code == 200:
        token = r.json().get("access_token")
        print("Token obtido.")
        return token
    print("Erro login:", r.status_code, r.text)
    return None

def configurar_webhook(token):
    config = {"url": f"{TERCEIRO_URL}/analise-sessao", "secret_key": SECRET_KEY, "ativo": True, "timeout_segundos": 30, "max_tentativas": 3}
    r = requests.post(f"{API_BASE_URL}/webhook/configurar", headers={"Authorization": f"Bearer {token}"}, json=config, timeout=DEFAULT_TIMEOUT)
    print("Configurar webhook ->", r.status_code, r.text)
    return r

def testar_conexao(token):
    r = requests.post(f"{API_BASE_URL}/webhook/testar", headers={"Authorization": f"Bearer {token}"}, timeout=DEFAULT_TIMEOUT)
    print("Teste conexão ->", r.status_code)
    try:
        print(r.json())
    except Exception:
        print(r.text)
    return r

def enviar_teste_para_terceiro():
    payload = {"mensagem": "Teste direto ao terceiro", "timestamp": datetime.utcnow().isoformat()}
    signature = gerar_signature(payload, SECRET_KEY)
    r = requests.post(f"{TERCEIRO_URL}/teste", json=payload, headers={"X-Webhook-Signature": signature, "Content-Type": "application/json"}, timeout=DEFAULT_TIMEOUT)
    print("Envio direto ao terceiro ->", r.status_code, r.text)

if __name__ == "__main__":
    tok = fazer_login()
    if not tok:
        raise SystemExit("Login falhou")
    configurar_webhook(tok)
    testar_conexao(tok)
    enviar_teste_para_terceiro()
