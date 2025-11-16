import os
import hmac
import hashlib
import json
import requests
import time
import traceback
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, timezone
from bson import ObjectId
from urllib.parse import urlparse, urlunparse
from concurrent.futures import ThreadPoolExecutor, Future
from jsonschema import validate as json_validate, ValidationError

from database import (
    colecao_sessoes,
    colecao_interacoes,
    colecao_usuarios,
    colecao_webhook_config,
    colecao_webhook_feedbacks,
    colecao_webhook_logs
)

# Thread pool para envio assíncrono
executor = ThreadPoolExecutor(max_workers=int(os.environ.get("WEBHOOK_WORKERS", 4)))

# Schema do payload enriquecido (contrato) - mantém compatibilidade com o anterior
PAYLOAD_SCHEMA = {
    "type": "object",
    "properties": {
        "evento": {"type": "string"},
        "timestamp": {"type": "string"},
        "dados": {
            "type": "object",
            "properties": {
                "sessao_id": {"type": "string"},
                "user_email": {"type": "string"},
                "titulo": {"type": "string"},
                "resumo": {"type": "string"},
                "dialogo_formatado": {"type": "string"},
                "total_interacoes": {"type": "integer"},
                "data_criacao": {"type": "string"},
                "data_ultima_interacao": {"type": "string"},
                "metricas": {"type": "object"},
                "sentimentos": {"type": "object"},
                "interacoes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "pergunta": {"type": "string"},
                            "resposta": {"type": "string"},
                            "timestamp": {"type": "string"}
                        },
                        "required": ["pergunta", "resposta", "timestamp"]
                    }
                }
            },
            "required": ["sessao_id", "user_email", "total_interacoes", "interacoes"]
        }
    },
    "required": ["evento", "timestamp", "dados"]
}


# ================================================================
# Helpers: geração de título, resumo, sentimento e métricas
# ================================================================

KEY_URGENCY = [
    'urgente', 'agora', 'imediato', 'parado', 'falha', 'fora do ar', 'erro crítico', 'crítico', 'não funciona', 'travou', 'caiu'
]

KEY_FRUSTRACAO = [
    'estou cansado', 'estou insatisfeito', 'não resolve', 'pior', 'inaceitável', 'frustrado', 'frustração', 'raiva'
]


def _maybe_objectid(val: Any) -> Any:
    if isinstance(val, str):
        try:
            return ObjectId(val)
        except Exception:
            return val
    return val


def gerar_titulo_inteligente(interacoes: List[Dict]) -> str:
    """Gera título curto a partir da primeira pergunta relevante ou extrai palavras-chave."""
    if not interacoes:
        return 'Sem título'

    first = interacoes[0]
    candidata = (first.get('pergunta') or '').strip()
    if candidata:
        tit = candidata[:80]
        return tit + ('...' if len(candidata) > 80 else '')

    # fallback: pegar a primeira palavra de alguma pergunta
    for i in interacoes:
        p = i.get('pergunta', '').strip()
        if p:
            return (p[:80] + ('...' if len(p) > 80 else ''))

    return 'Sem título'


def gerar_resumo_simples(interacoes: List[Dict], max_chars: int = 300) -> str:
    """Cria um resumo simples concatenando as perguntas mais importantes e truncando."""
    if not interacoes:
        return ''

    parts = []
    for it in interacoes:
        q = (it.get('pergunta') or '').strip()
        a = (it.get('resposta') or '').strip()
        if q:
            parts.append(f"Usuário: {q}")
        if a:
            parts.append(f"Assistente: {a}")
        if len(' '.join(parts)) > max_chars:
            break

    resumo = ' — '.join(parts)
    if len(resumo) > max_chars:
        resumo = resumo[:max_chars].rsplit(' ', 1)[0] + '...'
    return resumo


def analisar_sentimento_urgencia(interacoes: List[Dict]) -> Dict:
    """Heurística simples para urgência e sinais de frustração."""
    texto = ' '.join([(i.get('pergunta','') + ' ' + i.get('resposta','')) for i in interacoes]).lower()
    urgencia = 0
    frustracao = 0

    for k in KEY_URGENCY:
        if k in texto:
            urgencia += 2
    for k in KEY_FRUSTRACAO:
        if k in texto:
            frustracao += 2

    # ajustar por número de interações (muitas interações sem solução -> aumenta frustração)
    if len(interacoes) >= 6:
        frustracao += 1

    # normalizar em 0-10
    urgencia = min(10, urgencia)
    frustracao = min(10, frustracao)

    return {
        'urgencia_score': urgencia,
        'frustracao_score': frustracao,
        'observacoes': 'heuristica_simples'
    }


def calcular_metricas_temporais(interacoes: List[Dict], sessao_criada: Optional[datetime], sessao_atualizada: Optional[datetime]) -> Dict:
    tempos = []
    timestamps = []
    for it in interacoes:
        ts = it.get('timestamp')
        try:
            dt = datetime.fromisoformat(ts)
            timestamps.append(dt)
        except Exception:
            pass

    timestamps.sort()
    if timestamps:
        duracao = (timestamps[-1] - timestamps[0]).total_seconds()
    elif sessao_criada and sessao_atualizada:
        duracao = (sessao_atualizada - sessao_criada).total_seconds()
    else:
        duracao = 0

    # tempo médio entre mensagens
    if len(timestamps) > 1:
        diffs = [(t2 - t1).total_seconds() for t1, t2 in zip(timestamps[:-1], timestamps[1:])]
        tempo_medio = sum(diffs) / len(diffs)
    else:
        tempo_medio = 0

    total_mensagens_cliente = sum(1 for it in interacoes if (it.get('pergunta') or '').strip())
    total_mensagens_bot = sum(1 for it in interacoes if (it.get('resposta') or '').strip())

    return {
        'duracao_segundos': int(duracao),
        'tempo_medio_segundos': float(tempo_medio),
        'total_mensagens_cliente': total_mensagens_cliente,
        'total_mensagens_bot': total_mensagens_bot,
        'total_interacoes_registradas': len(interacoes)
    }


# ================================================================
# GERENCIADOR DE WEBHOOK (V2) - melhorias para enviar sessão completa
# ================================================================

class WebhookManagerV2:
    def __init__(self):
        self.max_tentativas = int(os.environ.get("WEBHOOK_MAX_TENTATIVAS", 3))
        self.timeout_padrao = int(os.environ.get("WEBHOOK_TIMEOUT", 30))
        self.jitter_fraction = float(os.environ.get("WEBHOOK_JITTER_FRACTION", 0.1))

    # -----------------------
    # Configuração
    # -----------------------
    def configurar_webhook(self, url: str, secret_key: str, ativo: bool = True, timeout_segundos: int = 30, max_tentativas: int = 3) -> Dict:
        colecao_webhook_config.delete_many({})
        config = {
            "url": url,
            "secret_key": secret_key,
            "ativo": ativo,
            "timeout_segundos": timeout_segundos,
            "max_tentativas": max_tentativas,
            "criado_em": datetime.now(timezone.utc),
            "atualizado_em": datetime.now(timezone.utc),
            "total_envios": 0,
            "total_sucessos": 0,
            "total_falhas": 0
        }
        resultado = colecao_webhook_config.insert_one(config)
        config["_id"] = str(resultado.inserted_id)
        print(f"[WEBHOOK V2] ✅ Configurado: {url}")
        return config

    def obter_config(self) -> Optional[Dict]:
        config = colecao_webhook_config.find_one({"ativo": True})
        if config:
            config["_id"] = str(config["_id"])
        return config

    # -----------------------
    # coleta enriquecida
    # -----------------------
    def coletar_dados_sessao(self, sessao_id: str, max_interacoes: int = 1000) -> Optional[Dict]:
        sessao_query = _maybe_objectid(sessao_id)
        sessao = colecao_sessoes.find_one({"_id": sessao_query})
        if not sessao:
            print(f"[WEBHOOK V2] ❌ Sessão {sessao_id} não encontrada")
            return None

        user_query = _maybe_objectid(sessao.get("user_id"))
        usuario = colecao_usuarios.find_one({"_id": user_query}) if user_query else None
        user_email = usuario.get("email", "desconhecido") if usuario else "desconhecido"

        raw_interacoes = list(colecao_interacoes.find({"sessao_id": sessao_id}).sort("timestamp", 1).limit(max_interacoes))

        interacoes_formatadas = []
        for interacao in raw_interacoes:
            ts = interacao.get('timestamp')
            if isinstance(ts, (datetime,)):
                ts_iso = ts.isoformat()
            else:
                try:
                    ts_iso = str(ts)
                except Exception:
                    ts_iso = datetime.now(timezone.utc).isoformat()

            interacoes_formatadas.append({
                "pergunta": interacao.get("pergunta", ""),
                "resposta": interacao.get("resposta", ""),
                "timestamp": ts_iso
            })

        # título inteligente (first user message fallback)
        titulo = gerar_titulo_inteligente(interacoes_formatadas)

        # resumo simples
        resumo = gerar_resumo_simples(interacoes_formatadas)

        # diálogo formatado (sequência User/Bot)
        dialogo_lines = []
        for it in interacoes_formatadas:
            if it.get('pergunta'):
                dialogo_lines.append(f"Usuário: {it.get('pergunta')}")
            if it.get('resposta'):
                dialogo_lines.append(f"Assistente: {it.get('resposta')}")
        dialogo_formatado = '\n'.join(dialogo_lines)

        # métricas temporais
        sessao_criada = sessao.get('criado_em')
        sessao_atualizada = sessao.get('atualizado_em')
        metricas = calcular_metricas_temporais(interacoes_formatadas, sessao_criada, sessao_atualizada)

        sentimentos = analisar_sentimento_urgencia(interacoes_formatadas)

        dados_sessao = {
            "sessao_id": sessao_id,
            "user_email": user_email,
            "titulo": titulo,
            "resumo": resumo,
            "dialogo_formatado": dialogo_formatado,
            "total_interacoes": len(interacoes_formatadas),
            "data_criacao": (sessao.get('criado_em') or datetime.now(timezone.utc)).isoformat(),
            "data_ultima_interacao": (sessao.get('atualizado_em') or datetime.now(timezone.utc)).isoformat(),
            "metricas": metricas,
            "sentimentos": sentimentos,
            "interacoes": interacoes_formatadas
        }

        return dados_sessao

    # -----------------------
    # assinatura
    # -----------------------
    def gerar_assinatura(self, payload: Dict, secret_key: str) -> str:
        payload_json = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
        signature = hmac.new(secret_key.encode(), payload_json.encode(), hashlib.sha256).hexdigest()
        return signature

    def validar_assinatura_resposta(self, payload: Dict, signature: str, secret_key: str) -> bool:
        assinatura_esperada = self.gerar_assinatura(payload, secret_key)
        return hmac.compare_digest(signature, assinatura_esperada)

    # -----------------------
    # validação de schema
    # -----------------------
    def validar_schema_payload(self, payload: Dict) -> Optional[str]:
        try:
            json_validate(instance=payload, schema=PAYLOAD_SCHEMA)
            return None
        except ValidationError as e:
            return str(e)

    # -----------------------
    # envio (síncrono)
    # -----------------------
    def enviar_webhook(self, sessao_id: str, force: bool = False) -> Dict:
        print(f"\n[WEBHOOK V2] 📤 Iniciando envio da sessão {sessao_id}...")

        config = self.obter_config()
        if not config:
            return {"sucesso": False, "erro": "Webhook não configurado"}

        if not force:
            log_existente = colecao_webhook_logs.find_one({"sessao_id": sessao_id, "status": "sucesso"})
            if log_existente:
                return {"sucesso": False, "erro": "Sessão já enviada", "log_id": str(log_existente["_id"]) }

        dados_sessao = self.coletar_dados_sessao(sessao_id)
        if not dados_sessao:
            return {"sucesso": False, "erro": "Sessão não encontrada"}

        payload = {
            "evento": "sessao_finalizada",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dados": dados_sessao
        }

        # validar schema antes de enviar (se falhar, enviamos mesmo assim com aviso)
        schema_err = self.validar_schema_payload(payload)
        if schema_err:
            print(f"[WEBHOOK V2] ⚠️ Payload não passou no schema: {schema_err}")
            # opcional: retornar erro ou continuar com aviso. Aqui continuamos para compatibilidade,
            # mas registramos um log e adicionamos um campo `schema_warning`
            payload['schema_warning'] = schema_err

        signature = self.gerar_assinatura(payload, config["secret_key"])
        payload["signature"] = signature

        max_tentativas = int(config.get("max_tentativas", self.max_tentativas))
        timeout = int(config.get("timeout_segundos", self.timeout_padrao))

        resultado = None
        for tentativa in range(1, max_tentativas + 1):
            print(f"[WEBHOOK V2] 🔄 Tentativa {tentativa}/{max_tentativas}...")
            resultado = self._enviar_requisicao(config["url"], payload, timeout, tentativa, sessao_id)
            if resultado.get("sucesso"):
                try:
                    colecao_webhook_config.update_one({"_id": ObjectId(config["_id"])},
                                                     {"$inc": {"total_envios": 1, "total_sucessos": 1},
                                                      "$set": {"atualizado_em": datetime.now(timezone.utc)}})
                except Exception as e:
                    print(f"[WEBHOOK V2] ❌ Erro ao atualizar estatísticas: {e}")
                return resultado

            # backoff com jitter
            if tentativa < max_tentativas:
                base = 2 ** tentativa
                jitter = base * self.jitter_fraction
                espera = base + (jitter * (0.5 - (time.time() % 1)))
                print(f"[WEBHOOK V2] ⏳ Aguardando {espera:.1f}s antes da próxima tentativa...")
                time.sleep(max(0.5, espera))

        # falha
        try:
            colecao_webhook_config.update_one({"_id": ObjectId(config["_id"])},
                                             {"$inc": {"total_envios": 1, "total_falhas": 1},
                                              "$set": {"atualizado_em": datetime.now(timezone.utc)}})
        except Exception as e:
            print(f"[WEBHOOK V2] ❌ Erro ao atualizar estatísticas após falhas: {e}")

        return {"sucesso": False, "erro": f"Falha após {max_tentativas} tentativas", "ultima_tentativa": resultado}

    # -----------------------
    # envio assíncrono
    # -----------------------
    def enviar_webhook_async(self, sessao_id: str, force: bool = False) -> Dict:
        print(f"[WEBHOOK V2] 🚀 Enfileirando envio assíncrono da sessão {sessao_id}...")
        future: Future = executor.submit(self.enviar_webhook, sessao_id, force)
        return {"sucesso": True, "mensagem": "Enfileirado", "sessao_id": sessao_id}

    # -----------------------
    # enviar requisição real
    # -----------------------
    def _enviar_requisicao(self, url: str, payload: Dict, timeout: int, tentativa: int, sessao_id: str) -> Dict:
        inicio = time.time()
        log = {"sessao_id": sessao_id, "tentativa": tentativa, "url_destino": url, "timestamp": datetime.now(timezone.utc)}
        try:
            headers = {"Content-Type": "application/json", "User-Agent": "TekBot-Webhook/2.0", "X-Webhook-Signature": payload.get("signature", "")}
            response = requests.post(url, json=payload, headers=headers, timeout=timeout)
            tempo_resposta = int((time.time() - inicio) * 1000)
            log.update({"tempo_resposta_ms": tempo_resposta, "codigo_http": response.status_code})

            if 200 <= response.status_code < 300:
                log["status"] = "sucesso"
                try:
                    resposta_data = response.json()
                    log["resposta"] = resposta_data
                    if isinstance(resposta_data, dict) and "analise" in resposta_data:
                        self._salvar_feedback(sessao_id, resposta_data)
                except Exception:
                    log["resposta"] = response.text
                colecao_webhook_logs.insert_one(log)
                return {"sucesso": True, "codigo_http": response.status_code, "tempo_resposta_ms": tempo_resposta, "resposta": log.get("resposta")}
            else:
                log["status"] = "falha"
                log["erro"] = f"HTTP {response.status_code}: {response.text[:200]}"
                colecao_webhook_logs.insert_one(log)
                return {"sucesso": False, "codigo_http": response.status_code, "erro": log["erro"]}
        except requests.Timeout:
            log["status"] = "timeout"
            log["erro"] = f"Timeout após {timeout}s"
            colecao_webhook_logs.insert_one(log)
            return {"sucesso": False, "erro": "Timeout"}
        except Exception as e:
            log["status"] = "falha"
            log["erro"] = str(e)
            try:
                colecao_webhook_logs.insert_one(log)
            except Exception:
                print("[WEBHOOK V2] ❌ Falha ao inserir log no DB")
            return {"sucesso": False, "erro": str(e)}

    # -----------------------
    # feedback
    # -----------------------
    def _salvar_feedback(self, sessao_id: str, resposta: Dict):
        try:
            analise = resposta.get("analise", {})
            feedback = {
                "sessao_id": sessao_id,
                "nivel": analise.get("nivel", "medio"),
                "pontuacao": analise.get("pontuacao", 5.0),
                "comentarios": analise.get("comentarios"),
                "metricas": analise.get("metricas"),
                "sugestoes": analise.get("sugestoes", []),
                "data_analise": datetime.fromisoformat(resposta.get("timestamp_analise", datetime.now(timezone.utc).isoformat())),
                "analisado_por": resposta.get("analisado_por"),
                "recebido_em": datetime.now(timezone.utc)
            }

            sessao = colecao_sessoes.find_one({"_id": _maybe_objectid(sessao_id)})
            if sessao:
                usuario = colecao_usuarios.find_one({"_id": _maybe_objectid(sessao.get("user_id"))})
                if usuario:
                    feedback["user_email"] = usuario.get("email", "desconhecido")

            colecao_webhook_feedbacks.insert_one(feedback)
            print(f"[WEBHOOK V2] 💾 Feedback salvo: {analise.get('nivel','medio').upper()} ({analise.get('pontuacao',0)})")
        except Exception as e:
            print(f"[WEBHOOK V2] ❌ Erro ao salvar feedback: {e}")

    # -----------------------
    # receber feedback (callback)
    # -----------------------
    def receber_feedback(self, dados_feedback: Dict, signature: str) -> Dict:
        print(f"[WEBHOOK V2] 📥 Recebendo feedback...")
        config = self.obter_config()
        if not config:
            return {"sucesso": False, "erro": "Webhook não configurado"}

        if not self.validar_assinatura_resposta(dados_feedback, signature, config["secret_key"]):
            print("[WEBHOOK V2] ⚠️ Assinatura inválida no callback!")
            return {"sucesso": False, "erro": "Assinatura inválida"}

        self._salvar_feedback(sessao_id=dados_feedback.get("sessao_id") or dados_feedback.get('dados',{}).get('sessao_id'), resposta=dados_feedback)
        return {"sucesso": True, "mensagem": "Feedback recebido e processado"}

    # -----------------------
    # TESTE: checar /teste no receptor
    # -----------------------
    def testar_webhook(self) -> Dict:
        print("[WEBHOOK V2] 🧪 Testando conexão...")

        config = self.obter_config()
        if not config:
            return {"sucesso": False, "erro": "Webhook não configurado"}

        try:
            parsed = urlparse(config["url"])
            base_url = urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))
            url_teste = f"{base_url}/teste"
        except Exception:
            url_teste = config["url"].rstrip("/") + "/teste"

        payload = {"mensagem": "Teste de webhook", "timestamp": datetime.now(timezone.utc).isoformat()}

        try:
            signature = self.gerar_assinatura(payload, config["secret_key"])
        except Exception:
            signature = ""

        try:
            inicio = time.time()
            response = requests.post(url_teste, json=payload, headers={"Content-Type": "application/json", "X-Webhook-Signature": signature}, timeout=config.get("timeout_segundos", self.timeout_padrao))
            tempo_resposta = int((time.time() - inicio) * 1000)

            if 200 <= response.status_code < 300:
                print(f"[WEBHOOK V2] ✅ Teste bem-sucedido! ({tempo_resposta}ms) -> {url_teste}")
                return {"sucesso": True, "codigo_http": response.status_code, "tempo_resposta_ms": tempo_resposta, "mensagem": "Webhook respondeu corretamente", "url_testada": url_teste}
            else:
                print(f"[WEBHOOK V2] ❌ Falhou: HTTP {response.status_code} -> {url_teste}")
                return {"sucesso": False, "codigo_http": response.status_code, "erro": f"HTTP {response.status_code}", "url_testada": url_teste, "resposta_texto": response.text[:1000]}
        except Exception as e:
            print(f"[WEBHOOK V2] ❌ Erro ao testar URL {url_teste}: {e}")
            traceback.print_exc()
            return {"sucesso": False, "erro": str(e), "url_testada": url_teste}


# instância global (para compatibilidade com outros módulos)
webhook_manager = WebhookManagerV2()

# conveniência

def configurar_webhook(url: str, secret_key: str, **kwargs) -> Dict:
    return webhook_manager.configurar_webhook(url, secret_key, **kwargs)


def enviar_sessao_para_analise(sessao_id: str, force: bool = False, async_send: bool = False) -> Dict:
    if async_send:
        return webhook_manager.enviar_webhook_async(sessao_id, force)
    return webhook_manager.enviar_webhook(sessao_id, force)


def receber_feedback_analise(dados: Dict, signature: str) -> Dict:
    return webhook_manager.receber_feedback(dados, signature)


def obter_feedback_sessao(sessao_id: str) -> List[Dict]:
    return list(colecao_webhook_feedbacks.find({"sessao_id": sessao_id}).sort("recebido_em", -1))
