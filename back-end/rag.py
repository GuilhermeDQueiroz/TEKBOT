import os
import torch
import json
import numpy as np
import time
from datetime import datetime, timezone
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
from typing import Dict, List, Optional
from database import colecao_mensagens, colecao_interacoes, colecao_tickets
import google.generativeai as genai

# === Configuração de ambiente ===
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

try:
    GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GOOGLE_API_KEY:
        raise ValueError("A variável de ambiente GEMINI_API_KEY não foi definida.")
    genai.configure(api_key=GOOGLE_API_KEY)
    print("[OK] API do Gemini configurada.")
except Exception as e:
    print(f"[ERRO] Falha ao configurar a API do Gemini: {e}")

# === Carregar modelo de embeddings ===
print("[INFO] Carregando modelo de embeddings...")
modelo_embedding = SentenceTransformer('all-MiniLM-L6-v2')
print("[OK] Modelo de embeddings carregado.")


# ==========================
# CONTEXTO & HISTÓRICO
# ==========================
def obterHistoricoSessao(sessao_id: str, limite: int = 5) -> str:
    try:
        interacoes = list(
            colecao_interacoes.find({"sessao_id": sessao_id})
            .sort("timestamp", -1)
            .limit(limite)
        )
        if not interacoes:
            return ""
        interacoes.reverse()
        contexto_texto = "HISTÓRICO DA CONVERSA ATUAL:\n"
        for i, interacao in enumerate(interacoes, 1):
            contexto_texto += f"\n{i}. USUÁRIO: {interacao['pergunta']}\n"
            contexto_texto += f"   ASSISTENTE: {interacao['resposta']}\n"
        return contexto_texto
    except Exception as e:
        print(f"[ERRO] Falha ao obter histórico da sessão: {e}")
        return ""


def verificarContinuidade(pergunta: str, sessao_id: str) -> bool:
    try:
        if not colecao_interacoes.find_one({"sessao_id": sessao_id}):
            return False
        palavras_continuacao = [
            'continue', 'continuar', 'mais', 'detalhe', 'detalhes', 'explique melhor',
            'como assim', 'e depois', 'próximo', 'passo', 'então', 'e se', 'mas',
            'e', 'também', 'além disso', 'outra coisa'
        ]
        pergunta_lower = pergunta.lower()
        return any(p in pergunta_lower for p in palavras_continuacao)
    except Exception as e:
        print(f"[ERRO] Falha ao verificar continuidade: {e}")
        return False


def obterUltimaResposta(sessao_id: str) -> Optional[str]:
    try:
        ultima_interacao = colecao_interacoes.find_one(
            {"sessao_id": sessao_id},
            sort=[("timestamp", -1)]
        )
        return ultima_interacao.get('resposta') if ultima_interacao else None
    except Exception as e:
        print(f"[ERRO] Falha ao obter última resposta: {e}")
        return None


# ==========================
# BUSCA RELEVANTE (mensagens + interações)
# ==========================
def recuperarInfoRelevantes(pergunta: str, sessao_id: Optional[str] = None) -> List[Dict]:
    """Recupera documentos relevantes da base de conhecimento e interações anteriores"""
    try:
        if sessao_id and verificarContinuidade(pergunta, sessao_id):
            print("[INFO] Detectada continuação - usando apenas contexto da conversa")
            return []

        documentos = list(colecao_mensagens.find())
        interacoes_passadas = list(colecao_interacoes.find())

        todos_docs = []
        for d in documentos:
            todos_docs.append({
                "_id": d["_id"],
                "texto": d.get("pergunta", "") or d.get("texto", ""),
                "resposta": d.get("resposta", ""),
                "embedding": d.get("embedding", []),
                "tipo": "base"
            })
        for i in interacoes_passadas:
            todos_docs.append({
                "_id": i["_id"],
                "texto": i.get("pergunta", ""),
                "resposta": i.get("resposta", ""),
                "embedding": i.get("embedding", []),
                "tipo": "interacao"
            })

    except Exception as e:
        print(f"[ERRO] Acesso ao banco falhou: {e}")
        return []

    if not todos_docs:
        return []

    pergunta_embedding = modelo_embedding.encode([pergunta])[0].reshape(1, -1)
    documentos_com_similaridade = []

    for doc in todos_docs:
        if not doc["texto"]:
            continue

        if doc["embedding"]:
            doc_embedding = np.array(doc["embedding"]).reshape(1, -1)
        else:
            doc_embedding_np = modelo_embedding.encode([doc["texto"]])[0]
            doc_embedding = doc_embedding_np.reshape(1, -1)
            try:
                if doc["tipo"] == "base":
                    colecao_mensagens.update_one(
                        {"_id": doc["_id"]},
                        {"$set": {"embedding": doc_embedding_np.tolist()}}
                    )
                else:
                    colecao_interacoes.update_one(
                        {"_id": doc["_id"]},
                        {"$set": {"embedding": doc_embedding_np.tolist()}}
                    )
            except Exception as e:
                print(f"[WARN] Não foi possível salvar embedding: {e}")

        similaridade = cosine_similarity(pergunta_embedding, doc_embedding)[0][0]
        documentos_com_similaridade.append((doc, similaridade))

    documentos_com_similaridade.sort(key=lambda x: x[1], reverse=True)
    resultado = [doc for doc, sim in documentos_com_similaridade[:5] if sim > 0.6]

    print(f"[INFO] Encontrados {len(resultado)} documentos relevantes")
    return resultado


# ==========================
# GERAÇÃO DE RESPOSTA
# ==========================
def gerarRespostaComIa(
    contexto_relevante: List,
    pergunta: str,
    sessao_id: Optional[str] = None,
    incluir_historico: bool = True
) -> str:
    contexto_base = ""
    if contexto_relevante:
        contexto_base = "\n".join(
            f"P: {doc['texto']}\nR: {doc.get('resposta','')}"
            for doc in contexto_relevante
        )

    contexto_conversa = ""
    eh_continuacao = False
    if sessao_id and incluir_historico:
        contexto_conversa = obterHistoricoSessao(sessao_id, limite=5)
        eh_continuacao = verificarContinuidade(pergunta, sessao_id)

    if eh_continuacao:
        ultima_resposta = obterUltimaResposta(sessao_id)
        prompt = f"""
Você é um atendente especialista em sistema ERP.
O usuário pediu continuação da resposta anterior.

{contexto_conversa}

ÚLTIMA RESPOSTA:
{ultima_resposta}

NOVA PERGUNTA: {pergunta}

Continue ou detalhe a resposta anterior:
"""
    else:
        prompt = f"""
Você é um atendente especialista em sistema ERP.
Use histórico da conversa e conhecimento base.

{contexto_conversa}

CONHECIMENTO BASE RELEVANTE:
{contexto_base}

NOVA PERGUNTA: {pergunta}

Responda de forma clara e objetiva:
"""

    try:
        model = genai.GenerativeModel('models/gemini-2.5-pro')
        generation_config = {"temperature": 0.3, "max_output_tokens": 2048}
        response = model.generate_content(prompt, generation_config=generation_config)
        return response.text.strip()
    except Exception as e:
        print(f"[ERRO] Erro ao chamar a API Gemini: {e}")
        return "Erro ao gerar resposta com a IA do Gemini."


# ==========================
# REGISTRO DE INTERAÇÃO
# ==========================
def registrarInteracao(pergunta: str, resposta: str, contexto: List, sessao_id: Optional[str] = None):
    try:
        embedding = modelo_embedding.encode([pergunta])[0].tolist()
        interacao = {
            "tipo": "interacao",
            "pergunta": pergunta,
            "resposta": resposta,
            "contexto_utilizado": [
                {"_id": str(doc.get("_id", "")), "texto": doc.get("texto", "")}
                for doc in contexto if isinstance(doc, dict)
            ],
            "embedding": embedding,
            "sessao_id": sessao_id,
            "timestamp": datetime.now(timezone.utc)
        }
        colecao_interacoes.insert_one(interacao)
        print("[INFO] Interação registrada no banco de dados.")
    except Exception as e:
        print(f"[ERRO] Falha ao salvar interação: {e}")


# ==========================
# PIPELINE COMPLETO
# ==========================
def processarPergunta(pergunta: str, sessao_id: Optional[str] = None) -> str:
    contexto_relevante = recuperarInfoRelevantes(pergunta, sessao_id)
    resposta = ""

    if contexto_relevante:
        pergunta_embedding = modelo_embedding.encode([pergunta]).reshape(1, -1)
        doc_top = contexto_relevante[0]
        doc_embedding = modelo_embedding.encode([doc_top["texto"]]).reshape(1, -1)
        similaridade = cosine_similarity(pergunta_embedding, doc_embedding)[0][0]
        if similaridade > 0.9 and doc_top.get("resposta"):
            resposta = doc_top["resposta"]
            registrarInteracao(pergunta, resposta, [doc_top], sessao_id)
            return resposta

    resposta = gerarRespostaComIa(contexto_relevante, pergunta, sessao_id)
    registrarInteracao(pergunta, resposta, contexto_relevante, sessao_id)
    return resposta


# ================================================================
# SISTEMA HÍBRIDO DE PRIORIZAÇÃO DE TICKETS (REGRAS + CACHE + IA)
# ================================================================

class AnalisadorPrioridadeAvancado:
    """Sistema inteligente de 3 camadas para priorização rápida e precisa"""
    
    # === CAMADA 1: REGRAS DETERMINÍSTICAS APRIMORADAS ===
    
    # CRÍTICO - Apenas quando sistema REALMENTE parado/inacessível
    PALAVRAS_CRITICAS_SISTEMA_PARADO = [
        'sistema parado', 'sistema travado', 'sistema caiu', 'sistema down',
        'sistema fora do ar', 'sistema não abre', 'sistema não inicia',
        'não consigo acessar nada', 'tudo parado', 'completamente parado',
        'nada funciona', 'sistema travou completamente'
    ]
    
    PALAVRAS_CRITICAS_DADOS = [
        'perda de dados', 'dados perdidos', 'backup falhou',
        'banco de dados inacessível', 'banco caiu', 'dados corrompidos'
    ]
    
    PALAVRAS_CRITICAS_PRODUCAO = [
        'produção parada', 'fábrica parada', 'linha de produção parada',
        'operação completamente bloqueada', 'empresa parada'
    ]
    
    PALAVRAS_CRITICAS_SEGURANCA = [
        'invasão', 'hackeado', 'dados vazados', 'vulnerabilidade crítica'
    ]
    
    # ALTA - Problemas graves mas sistema ainda funciona parcialmente
    PALAVRAS_ALTAS_ERRO = [
        'erro grave', 'erro crítico', 'bug grave', 'bug crítico',
        'falha grave', 'exception', 'crash'
    ]
    
    PALAVRAS_ALTAS_FUNCIONALIDADE = [
        'não salva', 'não gera', 'não processa', 'não emite',
        'não importa', 'não exporta'
    ]
    
    PALAVRAS_ALTAS_BLOQUEIO = [
        'não consigo', 'bloqueado', 'impedido de', 'não permite'
    ]
    
    PALAVRAS_ALTAS_MULTIPLOS = [
        'todos os usuários', 'todos usuários', 'ninguém consegue',
        'departamento inteiro', 'equipe inteira', 'time inteiro'
    ]
    
    # MÉDIA - Problemas moderados
    PALAVRAS_MEDIAS = [
        'problema', 'dificuldade', 'erro', 'falha',
        'lento', 'demora', 'travando às vezes'
    ]
    
    # BAIXA - Não urgente
    PALAVRAS_BAIXAS_DUVIDA = [
        'como faço', 'como fazer', 'como eu', 'dúvida',
        'não sei', 'poderia me ajudar', 'gostaria de saber'
    ]
    
    PALAVRAS_BAIXAS_SUGESTAO = [
        'sugestão', 'melhoria', 'poderia ter', 'seria bom',
        'seria legal', 'gostaria que', 'sugiro'
    ]
    
    @staticmethod
    def analisar_por_regras(titulo: str, descricao: str, categoria: str) -> Dict:
        """
        CAMADA 1: Análise com regras mais precisas e contextuais
        """
        texto_completo = f"{titulo} {descricao}".lower()
        titulo_lower = titulo.lower()
        descricao_lower = descricao.lower()
        
        # ============================================
        # NÍVEL CRÍTICO (confiança 100%)
        # Apenas quando sistema REALMENTE parado
        # ============================================
        
        # Verificar combinações críticas no TEXTO COMPLETO
        for palavra in AnalisadorPrioridadeAvancado.PALAVRAS_CRITICAS_SISTEMA_PARADO:
            if palavra in texto_completo:
                return {
                    'prioridade': 'critica',
                    'urgencia': 10,
                    'impacto': 'critico',
                    'confianca': 100,
                    'metodo': 'regra_critica_sistema',
                    'justificativa': f'Sistema completamente parado: "{palavra}"',
                    'requer_atencao_imediata': True,
                    'tempo_estimado_resolucao': '15-30 minutos'
                }
        
        # Dados críticos
        for palavra in AnalisadorPrioridadeAvancado.PALAVRAS_CRITICAS_DADOS:
            if palavra in texto_completo:
                return {
                    'prioridade': 'critica',
                    'urgencia': 10,
                    'impacto': 'critico',
                    'confianca': 100,
                    'metodo': 'regra_critica_dados',
                    'justificativa': f'Problema crítico de dados: "{palavra}"',
                    'requer_atencao_imediata': True,
                    'tempo_estimado_resolucao': '30-60 minutos'
                }
        
        # Produção parada
        for palavra in AnalisadorPrioridadeAvancado.PALAVRAS_CRITICAS_PRODUCAO:
            if palavra in texto_completo:
                return {
                    'prioridade': 'critica',
                    'urgencia': 10,
                    'impacto': 'critico',
                    'confianca': 100,
                    'metodo': 'regra_critica_producao',
                    'justificativa': f'Produção parada: "{palavra}"',
                    'requer_atencao_imediata': True,
                    'tempo_estimado_resolucao': '15-30 minutos'
                }
        
        # Segurança
        for palavra in AnalisadorPrioridadeAvancado.PALAVRAS_CRITICAS_SEGURANCA:
            if palavra in texto_completo:
                return {
                    'prioridade': 'critica',
                    'urgencia': 10,
                    'impacto': 'critico',
                    'confianca': 100,
                    'metodo': 'regra_critica_seguranca',
                    'justificativa': f'Problema de segurança crítico: "{palavra}"',
                    'requer_atencao_imediata': True,
                    'tempo_estimado_resolucao': '30-60 minutos'
                }
        
        # ============================================
        # NÍVEL ALTO (confiança 85-90%)
        # Problemas graves mas com workaround
        # ============================================
        
        # Erros graves
        for palavra in AnalisadorPrioridadeAvancado.PALAVRAS_ALTAS_ERRO:
            if palavra in texto_completo:
                return {
                    'prioridade': 'alta',
                    'urgencia': 8,
                    'impacto': 'alto',
                    'confianca': 85,
                    'metodo': 'regra_alta_erro',
                    'justificativa': f'Erro grave detectado: "{palavra}"',
                    'tempo_estimado_resolucao': '1-2 horas'
                }
        
        # Funcionalidade não funciona
        funcionalidade_alta = False
        for palavra in AnalisadorPrioridadeAvancado.PALAVRAS_ALTAS_FUNCIONALIDADE:
            if palavra in texto_completo:
                funcionalidade_alta = True
                break
        
        if funcionalidade_alta:
            return {
                'prioridade': 'alta',
                'urgencia': 7,
                'impacto': 'alto',
                'confianca': 85,
                'metodo': 'regra_alta_funcionalidade',
                'justificativa': 'Funcionalidade importante não está funcionando',
                'tempo_estimado_resolucao': '2-4 horas'
            }
        
        # Múltiplos usuários afetados
        for palavra in AnalisadorPrioridadeAvancado.PALAVRAS_ALTAS_MULTIPLOS:
            if palavra in texto_completo:
                return {
                    'prioridade': 'alta',
                    'urgencia': 8,
                    'impacto': 'alto',
                    'confianca': 90,
                    'metodo': 'regra_alta_multiplos',
                    'justificativa': f'Múltiplos usuários afetados: "{palavra}"',
                    'tempo_estimado_resolucao': '1-2 horas'
                }
        
        # Categoria BUG
        if categoria and categoria.lower() == 'bug':
            # Verificar se realmente é grave
            if any(p in texto_completo for p in ['grave', 'crítico', 'sério', 'importante']):
                return {
                    'prioridade': 'alta',
                    'urgencia': 7,
                    'impacto': 'alto',
                    'confianca': 80,
                    'metodo': 'regra_bug_grave',
                    'justificativa': 'Bug grave reportado',
                    'tempo_estimado_resolucao': '2-4 horas'
                }
            else:
                # Bug sem indicação de gravidade = média
                return {
                    'prioridade': 'media',
                    'urgencia': 5,
                    'impacto': 'medio',
                    'confianca': 75,
                    'metodo': 'regra_bug_medio',
                    'justificativa': 'Bug reportado sem indicação de gravidade',
                    'tempo_estimado_resolucao': '4-8 horas'
                }
        
        # ============================================
        # NÍVEL BAIXO (confiança 85%)
        # IMPORTANTE: Verificar BAIXO antes de MÉDIO
        # ============================================
        
        # Dúvidas simples
        for palavra in AnalisadorPrioridadeAvancado.PALAVRAS_BAIXAS_DUVIDA:
            if palavra in titulo_lower or palavra in descricao_lower[:100]:  # Início da descrição
                return {
                    'prioridade': 'baixa',
                    'urgencia': 2,
                    'impacto': 'baixo',
                    'confianca': 85,
                    'metodo': 'regra_baixa_duvida',
                    'justificativa': 'Dúvida sobre uso do sistema',
                    'tempo_estimado_resolucao': '1-2 horas'
                }
        
        # Sugestões
        for palavra in AnalisadorPrioridadeAvancado.PALAVRAS_BAIXAS_SUGESTAO:
            if palavra in titulo_lower or palavra in descricao_lower[:100]:
                return {
                    'prioridade': 'baixa',
                    'urgencia': 2,
                    'impacto': 'baixo',
                    'confianca': 90,
                    'metodo': 'regra_baixa_sugestao',
                    'justificativa': 'Sugestão de melhoria (não urgente)',
                    'tempo_estimado_resolucao': '24-48 horas'
                }
        
        # Categoria dúvida ou feature
        if categoria and categoria.lower() in ['duvida', 'feature', 'outro']:
            return {
                'prioridade': 'baixa',
                'urgencia': 3,
                'impacto': 'baixo',
                'confianca': 80,
                'metodo': 'regra_categoria_baixa',
                'justificativa': f'Categoria "{categoria}" indica baixa urgência',
                'tempo_estimado_resolucao': '4-24 horas'
            }
        
        # ============================================
        # NÍVEL MÉDIO (confiança 70%)
        # Problemas moderados - PADRÃO
        # ============================================
        
        for palavra in AnalisadorPrioridadeAvancado.PALAVRAS_MEDIAS:
            if palavra in texto_completo:
                return {
                    'prioridade': 'media',
                    'urgencia': 5,
                    'impacto': 'medio',
                    'confianca': 70,
                    'metodo': 'regra_media',
                    'justificativa': f'Problema moderado detectado: "{palavra}"',
                    'tempo_estimado_resolucao': '4-8 horas'
                }
        
        # ============================================
        # ANÁLISE DE CONTEXTO (confiança 60%)
        # ============================================
        
        # CAIXA ALTA no título = urgência (mas não necessariamente crítico)
        if len(titulo) > 5 and sum(1 for c in titulo if c.isupper()) > len(titulo) * 0.7:
            # Verificar se realmente é crítico ou apenas urgente
            tem_palavra_critica = any(p in titulo_lower for p in ['parado', 'travado', 'caiu'])
            if tem_palavra_critica:
                return {
                    'prioridade': 'critica',
                    'urgencia': 9,
                    'impacto': 'critico',
                    'confianca': 90,
                    'metodo': 'regra_caixa_alta_critica',
                    'justificativa': 'CAIXA ALTA + palavra crítica = urgência máxima',
                    'tempo_estimado_resolucao': '15-30 minutos'
                }
            else:
                return {
                    'prioridade': 'alta',
                    'urgencia': 7,
                    'impacto': 'alto',
                    'confianca': 60,
                    'metodo': 'regra_caixa_alta',
                    'justificativa': 'Texto em CAIXA ALTA indica urgência do usuário',
                    'tempo_estimado_resolucao': '1-2 horas'
                }
        
        # Múltiplas exclamações = urgência
        if texto_completo.count('!') >= 3:
            return {
                'prioridade': 'alta',
                'urgencia': 7,
                'impacto': 'alto',
                'confianca': 55,
                'metodo': 'regra_exclamacoes',
                'justificativa': 'Múltiplas exclamações indicam urgência',
                'tempo_estimado_resolucao': '1-2 horas'
            }
        
        # ============================================
        # PADRÃO FINAL (baixa confiança)
        # ============================================
        return {
            'prioridade': 'media',
            'urgencia': 5,
            'impacto': 'medio',
            'confianca': 40,  # Baixa confiança = deve tentar cache ou IA
            'metodo': 'padrao',
            'justificativa': 'Sem padrão claro - classificado como médio por segurança',
            'tempo_estimado_resolucao': '4-8 horas'
        }
    
    @staticmethod
    def calcular_score(prioridade: str, urgencia: int, tempo_espera_minutos: float = 0) -> int:
        """Calcula score numérico para ordenação inteligente na fila"""
        base_scores = {
            'critica': 10000,
            'alta': 5000,
            'media': 1000,
            'baixa': 100
        }
        
        score = base_scores.get(prioridade, 1000)
        score += urgencia * 100
        score += min(tempo_espera_minutos, 1440) * 0.5
        
        return int(score)
        
def buscar_tickets_similares(titulo: str, descricao: str, limite: int = 5) -> List[Dict]:
    """Busca tickets anteriores similares usando embeddings (CACHE)"""
    try:
        texto_busca = f"{titulo} {descricao}"
        embedding_busca = modelo_embedding.encode([texto_busca])[0].reshape(1, -1)
        
        # Buscar apenas tickets resolvidos/fechados com embedding
        tickets = list(colecao_tickets.find({
            "embedding": {"$exists": True},
            "status": {"$in": ["resolvido", "fechado"]}
        }).limit(100))  # Limitar para performance
        
        if not tickets:
            return []
        
        tickets_similares = []
        for ticket in tickets:
            if "embedding" not in ticket or not ticket["embedding"]:
                continue
                
            ticket_embedding = np.array(ticket["embedding"]).reshape(1, -1)
            similaridade = cosine_similarity(embedding_busca, ticket_embedding)[0][0]
            
            if similaridade > 0.70:  # Threshold de 70%
                tickets_similares.append({
                    "ticket": ticket,
                    "similaridade": float(similaridade)
                })
        
        tickets_similares.sort(key=lambda x: x["similaridade"], reverse=True)
        return tickets_similares[:limite]
        
    except Exception as e:
        print(f"[ERRO] Falha ao buscar tickets similares: {e}")
        return []


def analisar_ticket_com_ia(titulo: str, descricao: str, categoria: Optional[str] = None) -> Dict:
    """
    CAMADA 3: Usa o Gemini para análise detalhada (apenas casos complexos)
    """
    
    prompt = f"""
Você é um especialista em triagem de tickets de suporte de sistemas ERP empresariais.
Analise o ticket abaixo e forneça uma avaliação detalhada e PRECISA.

**TICKET:**
Título: {titulo}
Descrição: {descricao}
Categoria informada: {categoria or "Não informada"}

**CRITÉRIOS CRÍTICOS DE PRIORIZAÇÃO:**

🔴 **CRÍTICA** (USE SEMPRE que identificar):
- Sistema PARADO, travado, fora do ar, não abre, não funciona COMPLETAMENTE
- Perda de dados, corrupção de arquivos, banco de dados inacessível
- Falha de segurança, invasão, vulnerabilidade crítica
- Produção PARADA, processo de negócio BLOQUEADO
- Múltiplos usuários ou departamentos IMPEDIDOS de trabalhar
- Faturamento, pagamentos ou operações financeiras BLOQUEADAS
- Palavras-chave: "parado", "travado", "não funciona nada", "sistema caiu", "não abre", "tudo parado", "emergência", "urgente", "crítico"

🟠 **ALTA** (Problemas graves mas com workaround possível):
- Funcionalidade IMPORTANTE quebrada mas sistema ainda utilizável
- Bug grave que afeta múltiplos usuários
- Erro que impede conclusão de tarefas importantes
- Performance muito lenta que prejudica o trabalho
- Relatório crítico não gerado

🟡 **MÉDIA** (Problemas moderados):
- Bug em funcionalidade secundária
- Erro que afeta poucos usuários
- Problema com workaround disponível
- Lentidão moderada
- Dúvida sobre uso de funcionalidade

🟢 **BAIXA** (Não urgente):
- Dúvida geral, pergunta sobre como usar
- Sugestão de melhoria
- Problema cosmético (visual)
- Documentação ou treinamento

**EXEMPLOS PRÁTICOS:**

"MEU SISTEMA ESTÁ PARADO" → CRÍTICA (urgência: 10, impacto: critico)
"Sistema travou e não abre mais" → CRÍTICA (urgência: 10, impacto: critico)
"Não consigo acessar o sistema" → CRÍTICA (urgência: 9, impacto: critico)
"Erro ao salvar nota fiscal" → ALTA (urgência: 8, impacto: alto)
"Relatório não gera" → ALTA (urgência: 7, impacto: alto)
"Como faço para cadastrar cliente?" → BAIXA (urgência: 2, impacto: baixo)
"Sistema está lento" → MÉDIA (urgência: 5, impacto: medio)

**ATENÇÃO ESPECIAL:**
- Se o título/descrição contém "PARADO", "TRAVADO", "NÃO FUNCIONA", "CAIU", "FORA DO AR" → automaticamente CRÍTICA
- Se menciona "PRODUÇÃO", "FATURAMENTO", "FINANCEIRO" + problema → aumentar prioridade
- Se usa CAIXA ALTA ou múltiplas exclamações → indica urgência real do usuário
- Se menciona "TODOS", "NINGUÉM CONSEGUE", "DEPARTAMENTO INTEIRO" → aumentar prioridade

**ANÁLISE SOLICITADA:**
Retorne APENAS um JSON válido (sem markdown, sem ```json) com:
{{
  "prioridade": "critica|alta|media|baixa",
  "categoria_sugerida": "tecnico|financeiro|duvida|bug|feature|outro",
  "urgencia": 1-10,
  "impacto": "critico|alto|medio|baixo",
  "palavras_chave": ["palavra1", "palavra2", "palavra3"],
  "resumo": "breve resumo objetivo do problema em 1 frase",
  "justificativa": "explicação clara de POR QUE essa prioridade foi escolhida",
  "tempo_estimado_resolucao": "ex: 15 minutos, 1-2 horas, 24 horas",
  "requer_atencao_imediata": true|false
}}

**SEJA RIGOROSO:** Se há indicação clara de sistema parado ou funcionalidade crítica bloqueada, não hesite em marcar como CRÍTICA.
"""

    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        
        generation_config = {
            "temperature": 0.1,
            "max_output_tokens": 1024,
            "top_p": 0.8,
            "top_k": 10
        }
        
        response = model.generate_content(prompt, generation_config=generation_config)
        response_text = response.text.strip()
        
        # Remover marcadores de código markdown
        if response_text.startswith("```json"):
            response_text = response_text.replace("```json", "").replace("```", "").strip()
        elif response_text.startswith("```"):
            response_text = response_text.replace("```", "").strip()
        
        analise = json.loads(response_text)
        
        # Validação adicional: forçar CRÍTICA se palavras-chave óbvias
        texto_completo = f"{titulo} {descricao}".lower()
        palavras_criticas = [
            "parado", "travado", "não funciona", "caiu", "fora do ar",
            "não abre", "sistema down", "tudo parado", "bloqueado",
            "não consigo acessar", "não entra", "emergência"
        ]
        
        if any(palavra in texto_completo for palavra in palavras_criticas):
            if analise.get("prioridade") not in ["critica", "alta"]:
                print(f"⚠️ CORREÇÃO: Detectadas palavras críticas, ajustando prioridade de '{analise.get('prioridade')}' para 'critica'")
                analise["prioridade"] = "critica"
                analise["urgencia"] = max(analise.get("urgencia", 5), 9)
                analise["impacto"] = "critico"
                analise["requer_atencao_imediata"] = True
        
        print(f"[IA] Análise concluída:")
        print(f"  - Prioridade: {analise.get('prioridade', 'N/A')}")
        print(f"  - Urgência: {analise.get('urgencia', 'N/A')}/10")
        print(f"  - Impacto: {analise.get('impacto', 'N/A')}")
        print(f"  - Justificativa: {analise.get('justificativa', 'N/A')}")
        
        return analise
        
    except json.JSONDecodeError as e:
        print(f"[ERRO] Falha ao parsear JSON da IA: {e}")
        print(f"[ERRO] Resposta recebida: {response_text}")
        
        # Fallback com análise básica
        texto_completo = f"{titulo} {descricao}".lower()
        palavras_criticas = ["parado", "travado", "não funciona", "caiu", "fora do ar"]
        
        if any(palavra in texto_completo for palavra in palavras_criticas):
            return {
                "prioridade": "critica",
                "urgencia": 10,
                "impacto": "critico",
                "requer_atencao_imediata": True,
                "justificativa": "Sistema parado detectado - prioridade crítica automática (fallback)",
                "tempo_estimado_resolucao": "15-30 minutos",
                "erro": "Falha no parsing, mas análise básica aplicada"
            }
        
        return {
            "prioridade": "media",
            "urgencia": 5,
            "impacto": "medio",
            "tempo_estimado_resolucao": "4-8 horas",
            "erro": "Falha ao analisar resposta da IA"
        }
        
    except Exception as e:
        print(f"[ERRO] Falha ao chamar IA: {e}")
        
        # Fallback básico
        texto_completo = f"{titulo} {descricao}".lower()
        palavras_criticas = ["parado", "travado", "não funciona", "caiu", "fora do ar"]
        
        if any(palavra in texto_completo for palavra in palavras_criticas):
            return {
                "prioridade": "critica",
                "urgencia": 10,
                "impacto": "critico",
                "requer_atencao_imediata": True,
                "justificativa": "Sistema parado detectado (fallback)",
                "tempo_estimado_resolucao": "15-30 minutos",
                "erro": str(e)
            }
        
        return {
            "prioridade": "media",
            "urgencia": 5,
            "impacto": "medio",
            "tempo_estimado_resolucao": "4-8 horas",
            "erro": str(e)
        }


def analisar_prioridade_hibrido(
    titulo: str,
    descricao: str,
    categoria: str,
    usar_ia: bool = True,
    usar_cache: bool = True
) -> Dict:
    """
    🚀 SISTEMA HÍBRIDO DE 3 CAMADAS (PRODUÇÃO):
    
    1. REGRAS (0-5ms) - 90% dos casos, alta confiança
    2. CACHE (10-50ms) - tickets similares já resolvidos
    3. IA (1-3s) - apenas casos complexos sem padrão claro
    
    Retorna análise completa com método usado e tempo de processamento
    """
    
    print(f"\n[PRIORIZAÇÃO HÍBRIDA] Analisando ticket...")
    tempo_inicio = time.time()
    
    # ============================================
    # CAMADA 1: REGRAS DETERMINÍSTICAS (SEMPRE)
    # ============================================
    analise_regras = AnalisadorPrioridadeAvancado.analisar_por_regras(
        titulo, descricao, categoria
    )
    
    print(f"  ✓ Regras: {analise_regras['prioridade'].upper()} (confiança: {analise_regras['confianca']}%)")
    
    # Se confiança alta (>= 85%), usar resultado das regras diretamente
    if analise_regras['confianca'] >= 85:
        tempo_total = int((time.time() - tempo_inicio) * 1000)
        print(f"  ✓ Alta confiança - decisão em {tempo_total}ms")
        
        score = AnalisadorPrioridadeAvancado.calcular_score(
            analise_regras['prioridade'],
            analise_regras['urgencia']
        )
        
        return {
            'prioridade': analise_regras['prioridade'],
            'urgencia': analise_regras['urgencia'],
            'impacto': analise_regras['impacto'],
            'score': score,
            'confianca': analise_regras['confianca'],
            'metodo': analise_regras['metodo'],
            'justificativa': analise_regras['justificativa'],
            'tempo_estimado_resolucao': analise_regras.get('tempo_estimado_resolucao', 'A definir'),
            'requer_atencao_imediata': analise_regras.get('requer_atencao_imediata', False),
            'tempo_processamento_ms': tempo_total,
            'analise_ia': None  # IA não foi usada
        }
    
    # ============================================
    # CAMADA 2: CACHE DE TICKETS SIMILARES
    # ============================================
    if usar_cache:
        try:
            print(f"  🔍 Buscando tickets similares...")
            tickets_similares = buscar_tickets_similares(titulo, descricao, limite=3)
            
            if tickets_similares and tickets_similares[0]['similaridade'] > 0.90:
                ticket_similar = tickets_similares[0]['ticket']
                tempo_total = int((time.time() - tempo_inicio) * 1000)
                
                print(f"  ✓ Cache hit! Similaridade: {tickets_similares[0]['similaridade']:.1%} em {tempo_total}ms")
                
                # Usar prioridade do ticket similar
                prioridade_cached = ticket_similar.get('prioridade', 'media')
                urgencia_cached = ticket_similar.get('analise_ia', {}).get('urgencia', 5)
                
                score = AnalisadorPrioridadeAvancado.calcular_score(
                    prioridade_cached,
                    urgencia_cached
                )
                
                return {
                    'prioridade': prioridade_cached,
                    'urgencia': urgencia_cached,
                    'impacto': ticket_similar.get('analise_ia', {}).get('impacto', 'medio'),
                    'score': score,
                    'confianca': 95,
                    'metodo': 'cache_similar',
                    'justificativa': f"Baseado em ticket similar: #{ticket_similar.get('numero_ticket', 'N/A')}",
                    'tempo_estimado_resolucao': ticket_similar.get('analise_ia', {}).get('tempo_estimado_resolucao', 'A definir'),
                    'tempo_processamento_ms': tempo_total,
                    'ticket_similar_id': str(ticket_similar['_id']),
                    'analise_ia': None
                }
        except Exception as e:
            print(f"  ⚠️ Cache falhou: {e}")
    
    # ============================================
    # CAMADA 3: IA GEMINI (apenas casos complexos)
    # ============================================
    if usar_ia:
        try:
            print(f"  🤖 Usando IA para análise detalhada...")
            
            analise_ia = analisar_ticket_com_ia(titulo, descricao, categoria)
            
            tempo_total = int((time.time() - tempo_inicio) * 1000)
            print(f"  ✓ IA concluída em {tempo_total}ms")
            
            # Combinar resultado da IA com validação das regras
            prioridade_final = analise_ia.get('prioridade', 'media')
            
            # IMPORTANTE: Se regras dizem CRÍTICA mas IA diz MÉDIA, confiar nas regras
            if analise_regras['prioridade'] == 'critica' and prioridade_final not in ['critica', 'alta']:
                print(f"  ⚠️ Correção: Regras indicam CRÍTICA, sobrescrevendo IA")
                prioridade_final = 'critica'
                analise_ia['urgencia'] = 10
                analise_ia['impacto'] = 'critico'
                analise_ia['requer_atencao_imediata'] = True
            
            score = AnalisadorPrioridadeAvancado.calcular_score(
                prioridade_final,
                analise_ia.get('urgencia', 5)
            )
            
            return {
                'prioridade': prioridade_final,
                'urgencia': analise_ia.get('urgencia', 5),
                'impacto': analise_ia.get('impacto', 'medio'),
                'score': score,
                'confianca': 95,
                'metodo': 'ia_gemini',
                'justificativa': analise_ia.get('justificativa', 'Análise detalhada por IA'),
                'tempo_estimado_resolucao': analise_ia.get('tempo_estimado_resolucao', 'A definir'),
                'requer_atencao_imediata': analise_ia.get('requer_atencao_imediata', False),
                'tempo_processamento_ms': tempo_total,
                'analise_ia': analise_ia
            }
            
        except Exception as e:
            print(f"  ❌ IA falhou: {e}")
    
    # ============================================
    # FALLBACK: Usar resultado das regras básicas
    # ============================================
    tempo_total = int((time.time() - tempo_inicio) * 1000)
    print(f"  ↩️ Fallback: usando regras básicas ({tempo_total}ms)")
    
    score = AnalisadorPrioridadeAvancado.calcular_score(
        analise_regras['prioridade'],
        analise_regras['urgencia']
    )
    
    return {
        'prioridade': analise_regras['prioridade'],
        'urgencia': analise_regras['urgencia'],
        'impacto': analise_regras['impacto'],
        'score': score,
        'confianca': analise_regras['confianca'],
        'metodo': 'regras_fallback',
        'justificativa': analise_regras['justificativa'],
        'tempo_estimado_resolucao': analise_regras.get('tempo_estimado_resolucao', 'A definir'),
        'tempo_processamento_ms': tempo_total,
        'analise_ia': None
    }


# ================================================================
# FUNÇÃO LEGACY (compatibilidade com código existente)
# ================================================================

def calcular_prioridade_inteligente(
    titulo: str, 
    descricao: str, 
    categoria: str,
    usar_ia: bool = True,
    cliente_email: Optional[str] = None
) -> Dict:
    """
    Função de compatibilidade - usa o novo sistema híbrido
    Mantida para não quebrar código existente
    """
    # Usar o novo sistema híbrido
    resultado = analisar_prioridade_hibrido(
        titulo, 
        descricao, 
        categoria, 
        usar_ia=usar_ia,
        usar_cache=True
    )
    
    # Buscar tickets similares para recomendações
    similares = buscar_tickets_similares(titulo, descricao, limite=3)
    resultado['tickets_similares'] = similares
    
    # Gerar recomendações
    recomendacoes = []
    
    if resultado['prioridade'] in ['critica', 'alta']:
        recomendacoes.append("⚠️ Requer atenção prioritária!")
    
    if similares:
        tempos = [s['ticket'].get('tempo_resolucao_minutos', 0) 
                 for s in similares if s['ticket'].get('tempo_resolucao_minutos')]
        if tempos:
            tempo_medio = sum(tempos) / len(tempos)
            recomendacoes.append(f"📊 Tickets similares resolvidos em ~{int(tempo_medio)} minutos")
    
    # Verificar se cliente é VIP
    if cliente_email:
        try:
            from database import colecao_usuarios
            usuario = colecao_usuarios.find_one({"email": cliente_email})
            if usuario and usuario.get("tipo_usuario") == "vip":
                resultado['score'] += 2000
                recomendacoes.append("⭐ Cliente VIP - prioridade aumentada")
        except:
            pass
    
    resultado['recomendacoes'] = recomendacoes
    
    return resultado


def adicionar_embedding_ao_ticket(ticket_id: str, titulo: str, descricao: str):
    """Adiciona embedding ao ticket para futuras buscas no cache"""
    try:
        from bson import ObjectId
        
        texto = f"{titulo} {descricao}"
        embedding = modelo_embedding.encode([texto])[0].tolist()
        
        colecao_tickets.update_one(
            {"_id": ObjectId(ticket_id)},
            {"$set": {"embedding": embedding}}
        )
        
        print(f"[EMBEDDING] Embedding adicionado ao ticket {ticket_id}")
        
    except Exception as e:
        print(f"[ERRO] Falha ao adicionar embedding: {e}")


def gerar_resposta_automatica_ticket(ticket: Dict) -> Optional[str]:
    """Tenta gerar uma resposta automática baseada em tickets similares"""
    
    similares = buscar_tickets_similares(
        ticket["titulo"], 
        ticket["descricao"],
        limite=3
    )
    
    if not similares or similares[0]["similaridade"] < 0.85:
        return None
    
    ticket_similar = similares[0]["ticket"]
    mensagens = ticket_similar.get("mensagens", [])
    respostas_atendente = [m for m in mensagens if m.get("is_atendente", False)]
    
    if not respostas_atendente:
        return None
    
    prompt = f"""
Você é um atendente de suporte técnico.

Um cliente abriu este ticket:
**Título:** {ticket["titulo"]}
**Descrição:** {ticket["descricao"]}

Encontramos um ticket similar resolvido:
**Solução anterior:** {respostas_atendente[0]["conteudo"]}

Adapte a solução anterior para o novo ticket.
Seja claro, profissional e direto.
"""
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        response = model.generate_content(
            prompt,
            generation_config={"temperature": 0.3, "max_output_tokens": 512}
        )
        
        resposta = response.text.strip()
        resposta_final = f"{resposta}\n\n---\n_💡 Resposta sugerida automaticamente. Um atendente irá revisar._"
        
        return resposta_final
        
    except Exception as e:
        print(f"[ERRO] Falha ao gerar resposta automática: {e}")
        return None


print("[✓] Sistema híbrido de priorização carregado!")
print("    • Camada 1: Regras determinísticas (0-5ms)")
print("    • Camada 2: Cache de tickets similares (10-50ms)")
print("    • Camada 3: IA Gemini (1-3s)")