from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
from pymongo import DESCENDING
from bson import ObjectId
from schemas import PrioridadeTicket, StatusTicket, CategoriaTicket
from database import colecao_tickets, colecao_usuarios


class AnalisadorPrioridade:
    """Análise inteligente de prioridade baseada em múltiplos critérios"""
    
    PALAVRAS_CRITICAS = [
        "urgente", "crítico", "sistema fora", "não funciona", "parado",
        "down", "erro crítico", "falha total", "perdendo dinheiro",
        "clientes reclamando", "produção parada", "emergência", "caiu",
        "pânico", "desespero", "ajuda imediata"
    ]
    
    PALAVRAS_ALTAS = [
        "importante", "problema grave", "erro", "falha", "bug",
        "não consigo", "bloqueado", "travado", "lento demais",
        "preciso urgente", "quanto antes", "sério"
    ]
    
    PALAVRAS_MEDIAS = [
        "problema", "dificuldade", "dúvida importante", "ajuda",
        "como faço", "não entendo", "suporte", "dúvida"
    ]
    
    @staticmethod
    def analisar_prioridade(titulo: str, descricao: str, categoria: str) -> PrioridadeTicket:
        """Determina a prioridade automaticamente"""
        texto = f"{titulo} {descricao}".lower()
        
        if any(p in texto for p in AnalisadorPrioridade.PALAVRAS_CRITICAS):
            return PrioridadeTicket.CRITICA
        
        if any(p in texto for p in AnalisadorPrioridade.PALAVRAS_ALTAS):
            return PrioridadeTicket.ALTA
        
        if categoria == CategoriaTicket.BUG.value:
            return PrioridadeTicket.ALTA
        
        if any(p in texto for p in AnalisadorPrioridade.PALAVRAS_MEDIAS):
            return PrioridadeTicket.MEDIA
        
        if texto.count("!") >= 3:
            return PrioridadeTicket.ALTA
        
        if sum(1 for c in titulo if c.isupper()) > len(titulo) * 0.5:
            return PrioridadeTicket.ALTA
        
        return PrioridadeTicket.BAIXA
    

    @staticmethod
    def calcular_score(ticket):
        """Calcula score de prioridade do ticket"""
        from datetime import datetime, timezone
        
        score = 0
        
        # 1. Prioridade base da IA
        prioridades = {
            "critica": 50,
            "urgente": 40,
            "alta": 30,
            "media": 20,
            "baixa": 10
        }
        score += prioridades.get(ticket.get("prioridade_ia", "media"), 20)
        
        # 2. Tempo de espera
        data_criacao = ticket.get("data_criacao", datetime.now())
        
        # Garantir que ambas as datas tenham o mesmo tipo
        if hasattr(data_criacao, 'tzinfo') and data_criacao.tzinfo is not None:
            tempo_espera = datetime.now(timezone.utc) - data_criacao
        else:
            tempo_espera = datetime.now() - data_criacao
        
        minutos_espera = tempo_espera.total_seconds() / 60
        score += min(minutos_espera, 100)
        
        # 3. Tipo do ticket
        tipos_peso = {
            "erro": 15,
            "bug": 15,
            "problema": 10,
            "duvida": 5,
            "sugestao": 3
        }
        score += tipos_peso.get(ticket.get("tipo", "duvida"), 5)
        
        # 4. Palavras-chave urgentes
        texto_completo = f"{ticket.get('titulo', '')} {ticket.get('descricao', '')}".lower()
        palavras_urgentes = ["urgente", "crítico", "parado", "travado", "não funciona", "erro grave"]
        
        for palavra in palavras_urgentes:
            if palavra in texto_completo:
                score += 10
        
        return int(score)
        
def gerar_numero_ticket() -> str:
    """Gera número único sequencial"""
    ultimo = colecao_tickets.find_one(sort=[("data_criacao", DESCENDING)])
    if ultimo and "numero_ticket" in ultimo:
        num = int(ultimo["numero_ticket"].split("-")[1]) + 1
    else:
        num = 1
    return f"TKT-{num:06d}"


def criar_ticket(
    titulo: str,
    descricao: str,
    categoria: str,
    email_cliente: str,
    prioridade_manual: Optional[str] = None,
    usar_ia: bool = True
) -> dict:
    """Cria novo ticket com análise inteligente de prioridade"""
    
    print(f"\n[TICKETS] Criando novo ticket...")
    print(f"  📝 Título: {titulo}")
    print(f"  📂 Categoria: {categoria}")
    print(f"  👤 Cliente: {email_cliente}")
    
    analise_completa = None
    
    if prioridade_manual:
        prioridade = prioridade_manual
        score_inicial = AnalisadorPrioridade.calcular_score_base(prioridade)
        print(f"  ⚠️ Prioridade (manual): {prioridade}")
    else:
        if usar_ia:
            try:
                from rag import calcular_prioridade_inteligente
                analise_completa = calcular_prioridade_inteligente(
                    titulo, descricao, categoria, 
                    usar_ia=True,
                    cliente_email=email_cliente
                )
                prioridade = analise_completa["prioridade"]
                score_inicial = analise_completa["score"]
                print(f"  🧠 Prioridade (IA): {prioridade}")
                print(f"  📊 Score inicial: {score_inicial}")
            except (ImportError, Exception) as e:
                print(f"  ⚠️ IA não disponível ({e}), usando análise básica")
                prioridade = AnalisadorPrioridade.analisar_prioridade(titulo, descricao, categoria).value
                score_inicial = AnalisadorPrioridade.calcular_score_base(prioridade)
        else:
            prioridade = AnalisadorPrioridade.analisar_prioridade(titulo, descricao, categoria).value
            score_inicial = AnalisadorPrioridade.calcular_score_base(prioridade)
            print(f"  🎯 Prioridade (regras): {prioridade}")
    
    numero = gerar_numero_ticket()
    print(f"  🎫 Número: {numero}")
    
    agora = datetime.now(timezone.utc)
    
    usuario = colecao_usuarios.find_one({"email": email_cliente})
    nome_cliente = usuario.get("nome_completo") if usuario else None
    
    ticket = {
        "numero_ticket": numero,
        "titulo": titulo,
        "descricao": descricao,
        "categoria": categoria,
        "prioridade": prioridade,
        "status": StatusTicket.ABERTO.value,
        "email_cliente": email_cliente,
        "nome_cliente": nome_cliente,
        "atendente_email": None,
        "atendente_nome": None,
        "data_criacao": agora,
        "data_atualizacao": agora,
        "data_atribuicao": None,
        "data_resolucao": None,
        "tempo_resposta_minutos": None,
        "tempo_resolucao_minutos": None,
        "mensagens": [{
            "remetente_email": email_cliente,
            "remetente_nome": nome_cliente,
            "conteudo": descricao,
            "timestamp": agora,
            "is_atendente": False,
            "anexos": []
        }],
        "observacoes": None,
        "score_prioridade": score_inicial,
        "analise_ia": analise_completa.get("analise_ia") if analise_completa else None,
        "tickets_similares": [
            {
                "numero": t["ticket"].get("numero_ticket"),
                "similaridade": t["similaridade"]
            }
            for t in analise_completa.get("tickets_similares", [])
        ] if analise_completa else [],
        "recomendacoes": analise_completa.get("recomendacoes", []) if analise_completa else []
    }
    
    try:
        resultado = colecao_tickets.insert_one(ticket)
        ticket["_id"] = resultado.inserted_id
        print(f"  ✅ Ticket {numero} salvo no MongoDB!")
        print(f"  🆔 ID: {resultado.inserted_id}")
        
        if usar_ia and analise_completa:
            try:
                from rag import adicionar_embedding_ao_ticket, gerar_resposta_automatica_ticket
                adicionar_embedding_ao_ticket(str(resultado.inserted_id), titulo, descricao)
                
                resposta_auto = gerar_resposta_automatica_ticket(ticket)
                if resposta_auto:
                    print(f"  🤖 Resposta automática gerada!")
                    ticket["resposta_automatica_sugerida"] = resposta_auto
            except Exception as e:
                print(f"  ⚠️ Funções extras da IA não disponíveis: {e}")
        
        verificacao = colecao_tickets.find_one({"_id": resultado.inserted_id})
        if verificacao:
            print(f"  ✓ Verificação: Ticket encontrado no banco!")
        
    except Exception as e:
        print(f"  ❌ ERRO ao salvar ticket: {e}")
        raise
    
    if prioridade in [PrioridadeTicket.CRITICA.value, PrioridadeTicket.ALTA.value]:
        print(f"\n🚨 ALERTA: Ticket {numero} com prioridade {prioridade.upper()} criado!")
        if analise_completa and analise_completa.get("recomendacoes"):
            for rec in analise_completa["recomendacoes"]:
                print(f"  {rec}")
    
    return ticket


def obter_fila_inteligente(
    atendente_email: Optional[str] = None,
    filtros: Optional[dict] = None,
    limit: int = 50
) -> List[dict]:
    """Retorna fila ordenada por prioridade inteligente"""
    
    tickets_ativos = colecao_tickets.find({
        "status": {"$in": [StatusTicket.ABERTO.value, StatusTicket.EM_ATENDIMENTO.value]}
    })
    
    for ticket in tickets_ativos:
        novo_score = AnalisadorPrioridade.calcular_score(ticket)
        colecao_tickets.update_one(
            {"_id": ticket["_id"]},
            {"$set": {"score_prioridade": novo_score}}
        )
    
    query = {}
    
    if filtros:
        if filtros.get("status"):
            query["status"] = {"$in": filtros["status"]}
        else:
            query["status"] = {"$in": [StatusTicket.ABERTO.value, StatusTicket.EM_ATENDIMENTO.value]}
        
        if filtros.get("prioridade"):
            query["prioridade"] = {"$in": filtros["prioridade"]}
        
        if filtros.get("categoria"):
            query["categoria"] = {"$in": filtros["categoria"]}
        
        if filtros.get("apenas_meus") and atendente_email:
            query["atendente_email"] = atendente_email
    else:
        query["status"] = {"$in": [StatusTicket.ABERTO.value, StatusTicket.EM_ATENDIMENTO.value]}
    
    if atendente_email and not filtros:
        query["atendente_email"] = atendente_email
    
    tickets = list(colecao_tickets.find(query).sort("score_prioridade", DESCENDING).limit(limit))
    
    print(f"[TICKETS] Fila carregada: {len(tickets)} tickets encontrados")
    
    return tickets


def atribuir_ticket(ticket_id: str, atendente_email: str) -> dict:
    """Atribui ticket a um atendente"""
    
    ticket = colecao_tickets.find_one({"_id": ObjectId(ticket_id)})
    if not ticket:
        raise ValueError("Ticket não encontrado")
    
    if ticket["status"] == StatusTicket.FECHADO.value:
        raise ValueError("Ticket já fechado")
    
    atendente = colecao_usuarios.find_one({"email": atendente_email})
    nome_atendente = atendente.get("nome_completo") if atendente else None
    
    agora = datetime.now(timezone.utc)
    update = {
        "atendente_email": atendente_email,
        "atendente_nome": nome_atendente,
        "status": StatusTicket.EM_ATENDIMENTO.value,
        "data_atualizacao": agora
    }
    
    if not ticket.get("data_atribuicao"):
        update["data_atribuicao"] = agora
        tempo = (agora - ticket["data_criacao"]).total_seconds() / 60
        update["tempo_resposta_minutos"] = int(tempo)
    
    colecao_tickets.update_one({"_id": ObjectId(ticket_id)}, {"$set": update})
    
    print(f"[TICKETS] Ticket {ticket['numero_ticket']} atribuído a {atendente_email}")
    
    return colecao_tickets.find_one({"_id": ObjectId(ticket_id)})


def adicionar_mensagem(
    ticket_id: str,
    remetente_email: str,
    conteudo: str,
    is_atendente: bool = False
) -> dict:
    """Adiciona mensagem ao ticket"""
    
    ticket = colecao_tickets.find_one({"_id": ObjectId(ticket_id)})
    if not ticket:
        raise ValueError("Ticket não encontrado")
    
    usuario = colecao_usuarios.find_one({"email": remetente_email})
    nome = usuario.get("nome_completo") if usuario else None
    
    mensagem = {
        "remetente_email": remetente_email,
        "remetente_nome": nome,
        "conteudo": conteudo,
        "timestamp": datetime.now(timezone.utc),
        "is_atendente": is_atendente,
        "anexos": []
    }
    
    colecao_tickets.update_one(
        {"_id": ObjectId(ticket_id)},
        {
            "$push": {"mensagens": mensagem},
            "$set": {"data_atualizacao": datetime.now(timezone.utc)}
        }
    )
    
    print(f"[TICKETS] Mensagem adicionada ao ticket {ticket['numero_ticket']}")
    
    return mensagem


def atualizar_status_ticket(
    ticket_id: str,
    novo_status: str,
    observacoes: Optional[str] = None
) -> dict:
    """Atualiza status do ticket"""
    
    ticket = colecao_tickets.find_one({"_id": ObjectId(ticket_id)})
    if not ticket:
        raise ValueError("Ticket não encontrado")
    
    agora = datetime.now(timezone.utc)
    update = {
        "status": novo_status,
        "data_atualizacao": agora
    }
    
    if observacoes:
        update["observacoes"] = observacoes
    
    if novo_status == StatusTicket.RESOLVIDO.value and not ticket.get("data_resolucao"):
        update["data_resolucao"] = agora
        tempo_total = (agora - ticket["data_criacao"]).total_seconds() / 60
        update["tempo_resolucao_minutos"] = int(tempo_total)
    
    colecao_tickets.update_one({"_id": ObjectId(ticket_id)}, {"$set": update})
    
    print(f"[TICKETS] Status do ticket {ticket['numero_ticket']} alterado para: {novo_status}")
    
    return colecao_tickets.find_one({"_id": ObjectId(ticket_id)})


def obter_ticket(ticket_id: str) -> Optional[dict]:
    """Busca ticket por ID"""
    try:
        return colecao_tickets.find_one({"_id": ObjectId(ticket_id)})
    except:
        return None


def obter_ticket_por_numero(numero_ticket: str) -> Optional[dict]:
    """Busca ticket por número"""
    return colecao_tickets.find_one({"numero_ticket": numero_ticket})


def listar_tickets_cliente(email_cliente: str, limit: int = 50) -> List[dict]:
    """Lista tickets de um cliente"""
    tickets = list(
        colecao_tickets.find({"email_cliente": email_cliente})
        .sort("data_criacao", DESCENDING)
        .limit(limit)
    )
    
    print(f"[TICKETS] Cliente {email_cliente} tem {len(tickets)} tickets")
    
    return tickets


def obter_estatisticas_atendente(atendente_email: str) -> dict:
    """Calcula estatísticas do atendente"""
    
    agora = datetime.now(timezone.utc)
    inicio_dia = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    inicio_semana = agora - timedelta(days=agora.weekday())
    
    total = colecao_tickets.count_documents({"atendente_email": atendente_email})
    em_atendimento = colecao_tickets.count_documents({
        "atendente_email": atendente_email,
        "status": StatusTicket.EM_ATENDIMENTO.value
    })
    resolvidos_hoje = colecao_tickets.count_documents({
        "atendente_email": atendente_email,
        "status": StatusTicket.RESOLVIDO.value,
        "data_resolucao": {"$gte": inicio_dia}
    })
    resolvidos_semana = colecao_tickets.count_documents({
        "atendente_email": atendente_email,
        "status": StatusTicket.RESOLVIDO.value,
        "data_resolucao": {"$gte": inicio_semana}
    })
    
    tickets_respondidos = list(colecao_tickets.find({
        "atendente_email": atendente_email,
        "tempo_resposta_minutos": {"$exists": True, "$ne": None}
    }))
    
    tempo_resposta = sum(t["tempo_resposta_minutos"] for t in tickets_respondidos) / len(tickets_respondidos) if tickets_respondidos else 0
    
    tickets_resolvidos = list(colecao_tickets.find({
        "atendente_email": atendente_email,
        "tempo_resolucao_minutos": {"$exists": True, "$ne": None}
    }))
    
    tempo_resolucao = sum(t["tempo_resolucao_minutos"] for t in tickets_resolvidos) / len(tickets_resolvidos) if tickets_resolvidos else 0
    
    taxa = (len(tickets_resolvidos) / total * 100) if total > 0 else 0
    
    return {
        "total_tickets_atribuidos": total,
        "tickets_em_atendimento": em_atendimento,
        "tickets_resolvidos_hoje": resolvidos_hoje,
        "tickets_resolvidos_semana": resolvidos_semana,
        "tempo_medio_resposta_minutos": round(tempo_resposta, 2),
        "tempo_medio_resolucao_minutos": round(tempo_resolucao, 2),
        "taxa_resolucao_percentual": round(taxa, 2)
    }


def obter_dashboard_metricas() -> dict:
    """Retorna métricas gerais do sistema"""
    
    agora = datetime.now(timezone.utc)
    inicio_dia = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    
    total = colecao_tickets.count_documents({})
    abertos = colecao_tickets.count_documents({"status": StatusTicket.ABERTO.value})
    em_atendimento = colecao_tickets.count_documents({"status": StatusTicket.EM_ATENDIMENTO.value})
    aguardando = colecao_tickets.count_documents({"status": StatusTicket.AGUARDANDO_CLIENTE.value})
    criados_hoje = colecao_tickets.count_documents({"data_criacao": {"$gte": inicio_dia}})
    resolvidos_hoje = colecao_tickets.count_documents({
        "status": StatusTicket.RESOLVIDO.value,
        "data_resolucao": {"$gte": inicio_dia}
    })
    criticos = colecao_tickets.count_documents({
        "prioridade": PrioridadeTicket.CRITICA.value,
        "status": {"$in": [StatusTicket.ABERTO.value, StatusTicket.EM_ATENDIMENTO.value]}
    })
    
    dist_prioridade = {}
    for p in PrioridadeTicket:
        dist_prioridade[p.value] = colecao_tickets.count_documents({"prioridade": p.value})
    
    dist_categoria = {}
    for c in CategoriaTicket:
        dist_categoria[c.value] = colecao_tickets.count_documents({"categoria": c.value})
    
    dist_status = {}
    for s in StatusTicket:
        dist_status[s.value] = colecao_tickets.count_documents({"status": s.value})
    
    tickets_resp = list(colecao_tickets.find({"tempo_resposta_minutos": {"$exists": True, "$ne": None}}))
    tempo_resposta = sum(t["tempo_resposta_minutos"] for t in tickets_resp) / len(tickets_resp) if tickets_resp else 0
    
    tickets_resol = list(colecao_tickets.find({"tempo_resolucao_minutos": {"$exists": True, "$ne": None}}))
    tempo_resolucao = sum(t["tempo_resolucao_minutos"] for t in tickets_resol) / len(tickets_resol) if tickets_resol else 0
    
    atendentes = len(colecao_tickets.distinct("atendente_email", {"atendente_email": {"$ne": None}}))
    
    return {
        "total_tickets": total,
        "tickets_abertos": abertos,
        "tickets_em_atendimento": em_atendimento,
        "tickets_aguardando": aguardando,
        "tickets_resolvidos_hoje": resolvidos_hoje,
        "tickets_criados_hoje": criados_hoje,
        "tempo_medio_resposta_minutos": round(tempo_resposta, 2),
        "tempo_medio_resolucao_minutos": round(tempo_resolucao, 2),
        "distribuicao_prioridade": dist_prioridade,
        "distribuicao_categoria": dist_categoria,
        "distribuicao_status": dist_status,
        "atendentes_online": atendentes,
        "tickets_criticos_pendentes": criticos
    }


print("[✓] Módulo tickets.py carregado com sucesso!")