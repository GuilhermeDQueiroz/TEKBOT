import os
import json
import hmac
import hashlib
import traceback
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from datetime import datetime

app = FastAPI(title="Servidor Receptor de Webhook")

# Lê segredo do env — em produção coloque via secrets manager
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", None)

def validar_assinatura(body_bytes: bytes, signature_header: str) -> bool:
    """
    Valida HMAC-SHA256.
    Se WEBHOOK_SECRET não estiver setado, retorna True (modo permissivo), mas loga aviso.
    """
    if not WEBHOOK_SECRET:
        print("[WEBHOOK-RECEPTOR] ⚠️ WEBHOOK_SECRET não definido — aceitando assinatura (modo permissivo). Defina WEBHOOK_SECRET em produção.")
        return True

    if not signature_header:
        return False

    mac = hmac.new(WEBHOOK_SECRET.encode(), body_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac, signature_header)

@app.post("/webhook/receber")
async def receber_webhook(request: Request):
    try:
        body_bytes = await request.body()
        signature = request.headers.get("X-Webhook-Signature", "")
        if not validar_assinatura(body_bytes, signature):
            return JSONResponse(status_code=401, content={"erro": "Assinatura inválida"})

        payload = json.loads(body_bytes.decode("utf-8"))

        print("\n=== 📬 Webhook Recebido (/webhook/receber) ===")
        print(f"🕓 {datetime.now().isoformat()}")
        print(f"🔏 Assinatura: {signature}")
        print(f"📦 Payload: {payload}")
        print("=============================================\n")

        # Processamento (pode validar schema/filtrar etc)
        # Por simplicidade devolvemos um ack
        return JSONResponse(content={"status": "recebido", "mensagem": "Webhook processado com sucesso", "timestamp": datetime.now().isoformat()}, status_code=200)
    except Exception as e:
        print(f"❌ Erro ao processar webhook: {e}")
        traceback.print_exc()
        return JSONResponse(content={"erro": str(e)}, status_code=400)

@app.post("/teste")
async def teste_endpoint(request: Request):
    try:
        body_bytes = await request.body()
        signature = request.headers.get("X-Webhook-Signature", "")
        if body_bytes:
            try:
                dados = json.loads(body_bytes.decode("utf-8"))
            except Exception:
                dados = body_bytes.decode("utf-8", errors="replace")
        else:
            dados = None

        print("\n=== 🧪 Teste Recebido (/teste) ===")
        print(f"🕓 {datetime.now().isoformat()}")
        print(f"🔏 Assinatura: {signature}")
        print(f"📦 Dados: {dados}")
        print("=================================\n")

        return JSONResponse(content={"status": "ok", "mensagem": "Teste recebido com sucesso", "dados_recebidos": dados, "timestamp": datetime.now().isoformat()}, status_code=200)
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(content={"erro": str(e)}, status_code=400)
