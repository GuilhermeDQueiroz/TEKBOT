import os
import torch
import json
import numpy as np
import time
import pickle
from datetime import datetime, timezone
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sentence_transformers import SentenceTransformer
from typing import Dict, List, Optional
from collections import Counter
from database import colecao_mensagens, colecao_interacoes, colecao_tickets, colecao_feedback_ia
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

# === Diretório para modelos ML ===
MODELO_DIR = "./modelos_ia"
os.makedirs(MODELO_DIR, exist_ok=True)
MODELO_PATH = os.path.join(MODELO_DIR, "modelo_prioridade.pkl")
VECTORIZER_PATH = os.path.join(MODELO_DIR, "vectorizer.pkl")


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
# BUSCA RELEVANTE
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
# SISTEMA DE MACHINE LEARNING (APRENDIZADO)
# ================================================================

class ModeloAprendizado:
    """
    Sistema de ML que aprende com tickets classificados e correções
    """
    
    def __init__(self):
        self.modelo = None
        self.vectorizer = None
        self.prioridades_map = {
            'baixa': 0,
            'media': 1,
            'alta': 2,
            'critica': 3
        }
        self.prioridades_reverse = {v: k for k, v in self.prioridades_map.items()}
        self.carregado = False
        self.metadados = None
        
    def carregar_modelo(self) -> bool:
        """Carrega modelo já treinado"""
        try:
            if os.path.exists(MODELO_PATH) and os.path.exists(VECTORIZER_PATH):
                with open(MODELO_PATH, 'rb') as f:
                    self.modelo = pickle.load(f)
                with open(VECTORIZER_PATH, 'rb') as f:
                    self.vectorizer = pickle.load(f)
                
                # Carregar metadados
                metadados_path = os.path.join(MODELO_DIR, 'metadados.pkl')
                if os.path.exists(metadados_path):
                    with open(metadados_path, 'rb') as f:
                        self.metadados = pickle.load(f)
                
                self.carregado = True
                print("[ML] ✅ Modelo carregado!")
                return True
            else:
                print("[ML] ⚠️ Nenhum modelo encontrado. Execute: python retreinar_modelo.py")
                return False
        except Exception as e:
            print(f"[ML] ❌ Falha ao carregar: {e}")
            return False
    
    def preparar_dados_treino(self) -> tuple:
        """Busca tickets do banco para treinar"""
        print("[ML] 📊 Buscando dados de treino...")
        
        # 1. Tickets CORRIGIDOS (fonte mais confiável)
        tickets_corrigidos = list(colecao_tickets.find({
            "foi_corrigido": True,
            "prioridade_corrigida_atendente": {"$exists": True}
        }))
        
        # 2. Tickets RESOLVIDOS (sem correção = IA acertou)
        tickets_resolvidos = list(colecao_tickets.find({
            "status": {"$in": ["resolvido", "fechado"]},
            "foi_corrigido": {"$ne": True},
            "prioridade": {"$exists": True}
        }).limit(500))
        
        print(f"[ML]    Corrigidos: {len(tickets_corrigidos)}")
        print(f"[ML]    Resolvidos: {len(tickets_resolvidos)}")
        
        total = len(tickets_corrigidos) + len(tickets_resolvidos)
        
        if total < 20:
            print(f"[ML] ⚠️ Mínimo 20 tickets necessários (atual: {total})")
            return None, None, None
        
        textos = []
        categorias = []
        prioridades = []
        
        # Priorizar correções
        for ticket in tickets_corrigidos:
            texto = f"{ticket['titulo']} {ticket['descricao']}"
            textos.append(texto)
            categorias.append(ticket.get('categoria', 'outro'))
            prioridades.append(ticket['prioridade_corrigida_atendente'])
        
        for ticket in tickets_resolvidos:
            texto = f"{ticket['titulo']} {ticket['descricao']}"
            textos.append(texto)
            categorias.append(ticket.get('categoria', 'outro'))
            prioridades.append(ticket['prioridade'])
        
        # Distribuição
        dist = Counter(prioridades)
        print(f"[ML] 📈 Distribuição:")
        for prio in ['baixa', 'media', 'alta', 'critica']:
            count = dist.get(prio, 0)
            print(f"       {prio}: {count}")
        
        return textos, categorias, prioridades
    
    def treinar(self, force=False):
        """Treina o modelo"""
        print("\n" + "="*70)
        print("🧠 TREINANDO MODELO DE MACHINE LEARNING")
        print("="*70)
        
        if not force and os.path.exists(MODELO_PATH):
            print("\n⚠️  Modelo já existe.")
            return False
        
        textos, categorias, prioridades = self.preparar_dados_treino()
        
        if textos is None:
            return False
        
        # Converter para números
        y = np.array([self.prioridades_map[p] for p in prioridades])
        
        # Features
        print("\n[ML] 🔧 Criando features...")
        
        self.vectorizer = TfidfVectorizer(
            max_features=500,
            ngram_range=(1, 2),
            min_df=2
        )
        
        X_texto = self.vectorizer.fit_transform(textos)
        
        # One-hot para categoria
        categorias_unicas = list(set(categorias))
        X_cat = np.zeros((len(categorias), len(categorias_unicas)))
        for i, cat in enumerate(categorias):
            if cat in categorias_unicas:
                X_cat[i, categorias_unicas.index(cat)] = 1
        
        X = np.hstack([X_texto.toarray(), X_cat])
        
        print(f"[ML]    Shape: {X.shape}")
        
        # Treino/teste
        if len(textos) >= 40:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
        else:
            X_train, y_train = X, y
            X_test, y_test = X, y
        
        # Treinar
        print("\n[ML] 🎯 Treinando Random Forest...")
        
        self.modelo = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            random_state=42,
            class_weight='balanced'
        )
        
        self.modelo.fit(X_train, y_train)
        
        # Avaliar
        score_treino = self.modelo.score(X_train, y_train)
        score_teste = self.modelo.score(X_test, y_test)
        
        print(f"\n[ML] 📊 Resultados:")
        print(f"       Treino: {score_treino:.1%}")
        print(f"       Teste: {score_teste:.1%}")
        
        # Salvar
        print(f"\n[ML] 💾 Salvando modelo...")
        
        with open(MODELO_PATH, 'wb') as f:
            pickle.dump(self.modelo, f)
        
        with open(VECTORIZER_PATH, 'wb') as f:
            pickle.dump(self.vectorizer, f)
        
        metadados = {
            'treinado_em': datetime.now(timezone.utc).isoformat(),
            'num_exemplos': len(textos),
            'acuracia_treino': float(score_treino),
            'acuracia_teste': float(score_teste),
            'distribuicao': dict(Counter(prioridades)),
            'categorias_unicas': categorias_unicas
        }
        
        with open(os.path.join(MODELO_DIR, 'metadados.pkl'), 'wb') as f:
            pickle.dump(metadados, f)
        
        self.metadados = metadados
        self.carregado = True
        
        print(f"[ML] ✅ Modelo salvo!")
        print("="*70)
        
        return True
    
    def prever(self, titulo: str, descricao: str, categoria: str) -> Optional[Dict]:
        """Prediz prioridade"""
        if not self.carregado:
            if not self.carregar_modelo():
                return None
        
        try:
            texto = f"{titulo} {descricao}"
            X_texto = self.vectorizer.transform([texto])
            
            categorias_unicas = self.metadados['categorias_unicas']
            X_cat = np.zeros((1, len(categorias_unicas)))
            if categoria in categorias_unicas:
                X_cat[0, categorias_unicas.index(categoria)] = 1
            
            X = np.hstack([X_texto.toarray(), X_cat])
            
            prioridade_num = self.modelo.predict(X)[0]
            probabilidades = self.modelo.predict_proba(X)[0]
            
            prioridade = self.prioridades_reverse[prioridade_num]
            confianca = float(probabilidades[prioridade_num]) * 100
            
            urgencias = {'baixa': 2, 'media': 5, 'alta': 8, 'critica': 10}
            
            return {
                'prioridade': prioridade,
                'urgencia': urgencias[prioridade],
                'confianca': confianca,
                'metodo': 'modelo_ml',
                'probabilidades': {
                    self.prioridades_reverse[i]: float(prob)
                    for i, prob in enumerate(probabilidades)
                }
            }
            
        except Exception as e:
            print(f"[ML] ❌ Erro ao prever: {e}")
            return None
    
    def verificar_retreino(self) -> bool:
        """Verifica se precisa retreinar"""
        if not self.metadados:
            return False
        
        try:
            data_treino = datetime.fromisoformat(self.metadados['treinado_em'])
            
            novas_correcoes = colecao_tickets.count_documents({
                "foi_corrigido": True,
                "corrigido_em": {"$gt": data_treino}
            })
            
            if novas_correcoes >= 20:
                print(f"[ML] ⚠️ {novas_correcoes} novas correções - retreino recomendado!")
                return True
            
            return False
            
        except:
            return False


# Instância global
modelo_ml = ModeloAprendizado()


# ================================================================
# SISTEMA DE FEEDBACK (APRENDIZADO)
# ================================================================

def registrar_correcao_atendente(
    ticket_id: str,
    prioridade_corrigida: str,
    atendente_email: str,
    motivo: str = None
):
    """Registra correção de atendente"""
    from bson import ObjectId
    
    ticket = colecao_tickets.find_one({"_id": ObjectId(ticket_id)})
    
    if not ticket:
        print(f"[FEEDBACK] ❌ Ticket {ticket_id} não encontrado")
        return False
    
    prioridade_original = ticket.get('prioridade')
    
    if prioridade_original == prioridade_corrigida:
        print(f"[FEEDBACK] ℹ️ Prioridade já está correta")
        return False
    
    # Atualizar ticket
    colecao_tickets.update_one(
        {"_id": ObjectId(ticket_id)},
        {
            "$set": {
                "prioridade_original_ia": prioridade_original,
                "prioridade_corrigida_atendente": prioridade_corrigida,
                "prioridade": prioridade_corrigida,
                "foi_corrigido": True,
                "corrigido_por": atendente_email,
                "corrigido_em": datetime.now(timezone.utc),
                "motivo_correcao": motivo
            }
        }
    )
    
    # Registrar feedback
    feedback = {
        "ticket_id": ticket_id,
        "ticket_numero": ticket.get('numero_ticket'),
        "titulo": ticket.get('titulo'),
        "descricao": ticket.get('descricao'),
        "categoria": ticket.get('categoria'),
        "prioridade_ia": prioridade_original,
        "prioridade_correta": prioridade_corrigida,
        "atendente": atendente_email,
        "motivo": motivo,
        "metodo_usado": ticket.get('analise_ia', {}).get('metodo_usado'),
        "registrado_em": datetime.now(timezone.utc)
    }
    
    colecao_feedback_ia.insert_one(feedback)
    
    print(f"[FEEDBACK] ✅ Correção registrada:")
    print(f"           #{ticket.get('numero_ticket')}: {prioridade_original} → {prioridade_corrigida}")
    
    # Verificar se precisa retreinar
    if modelo_ml.verificar_retreino():
        print(f"[FEEDBACK] 🔄 Execute: python retreinar_modelo.py")
    
    return True


def obter_estatisticas_feedback():
    """Estatísticas de feedback"""
    total_correcoes = colecao_tickets.count_documents({"foi_corrigido": True})
    total_tickets = colecao_tickets.count_documents({})
    
    if total_tickets == 0:
        print("\n[FEEDBACK] ⚠️ Nenhum ticket no banco")
        return
    
    taxa_acerto = ((total_tickets - total_correcoes) / total_tickets) * 100
    
    print("\n" + "="*70)
    print("📊 ESTATÍSTICAS DE APRENDIZADO")
    print("="*70)
    print(f"\n✅ Taxa de acerto: {taxa_acerto:.1f}%")
    print(f"📊 Total: {total_tickets} tickets")
    print(f"🔧 Correções: {total_correcoes}")
    
    # Erros comuns
    erros = list(colecao_tickets.find({
        "foi_corrigido": True,
        "prioridade_original_ia": {"$exists": True}
    }).limit(10))
    
    if erros:
        print(f"\n🔄 Erros mais recentes:")
        transicoes = []
        for erro in erros:
            trans = f"{erro['prioridade_original_ia']} → {erro['prioridade_corrigida_atendente']}"
            transicoes.append(trans)
        
        counter = Counter(transicoes)
        for trans, count in counter.most_common(5):
            print(f"   {trans}: {count}x")


# ================================================================
# SISTEMA DE PRIORIZAÇÃO COM 4 CAMADAS (REGRAS + CACHE + ML + IA)
# ================================================================

class AnalisadorPrioridadeAvancado:
    """Sistema de 4 camadas com aprendizado"""
    
    # PALAVRAS-CHAVE CRÍTICAS
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
    
    # PALAVRAS ALTA
    PALAVRAS_ALTAS_ERRO = [
        'erro grave', 'erro crítico', 'bug grave', 'bug crítico',
        'falha grave', 'exception', 'crash'
    ]
    
    PALAVRAS_ALTAS_FUNCIONALIDADE = [
        'não salva', 'não gera', 'não processa', 'não emite',
        'não importa', 'não exporta'
    ]
    
    PALAVRAS_ALTAS_MULTIPLOS = [
        'todos os usuários', 'todos usuários', 'ninguém consegue',
        'departamento inteiro', 'equipe inteira', 'time inteiro'
    ]
    
    # PALAVRAS MÉDIA
    PALAVRAS_MEDIAS = [
        'problema', 'dificuldade', 'erro', 'falha',
        'lento', 'demora', 'travando às vezes'
    ]
    
    # PALAVRAS BAIXA
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
        """CAMADA 1: Regras determinísticas"""
        texto_completo = f"{titulo} {descricao}".lower()
        titulo_lower = titulo.lower()
        descricao_lower = descricao.lower()
        
        # CRÍTICO
        for palavra in AnalisadorPrioridadeAvancado.PALAVRAS_CRITICAS_SISTEMA_PARADO:
            if palavra in texto_completo:
                return {
                    'prioridade': 'critica',
                    'urgencia': 10,
                    'impacto': 'critico',
                    'confianca': 100,
                    'metodo': 'regra_critica_sistema',
                    'justificativa': f'Sistema parado: "{palavra}"',
                    'requer_atencao_imediata': True,
                    'tempo_estimado_resolucao': '15-30 minutos'
                }
        
        for palavra in AnalisadorPrioridadeAvancado.PALAVRAS_CRITICAS_DADOS:
            if palavra in texto_completo:
                return {
                    'prioridade': 'critica',
                    'urgencia': 10,
                    'impacto': 'critico',
                    'confianca': 100,
                    'metodo': 'regra_critica_dados',
                    'justificativa': f'Dados críticos: "{palavra}"',
                    'requer_atencao_imediata': True,
                    'tempo_estimado_resolucao': '30-60 minutos'
                }
        
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
        
        for palavra in AnalisadorPrioridadeAvancado.PALAVRAS_CRITICAS_SEGURANCA:
            if palavra in texto_completo:
                return {
                    'prioridade': 'critica',
                    'urgencia': 10,
                    'impacto': 'critico',
                    'confianca': 100,
                    'metodo': 'regra_critica_seguranca',
                    'justificativa': f'Segurança: "{palavra}"',
                    'requer_atencao_imediata': True,
                    'tempo_estimado_resolucao': '30-60 minutos'
                }
        
        # ALTA
        for palavra in AnalisadorPrioridadeAvancado.PALAVRAS_ALTAS_ERRO:
            if palavra in texto_completo:
                return {
                    'prioridade': 'alta',
                    'urgencia': 8,
                    'impacto': 'alto',
                    'confianca': 85,
                    'metodo': 'regra_alta_erro',
                    'justificativa': f'Erro grave: "{palavra}"',
                    'tempo_estimado_resolucao': '1-2 horas'
                }
        
        funcionalidade_alta = any(p in texto_completo for p in AnalisadorPrioridadeAvancado.PALAVRAS_ALTAS_FUNCIONALIDADE)
        if funcionalidade_alta:
            return {
                'prioridade': 'alta',
                'urgencia': 7,
                'impacto': 'alto',
                'confianca': 85,
                'metodo': 'regra_alta_funcionalidade',
                'justificativa': 'Funcionalidade importante quebrada',
                'tempo_estimado_resolucao': '2-4 horas'
            }
        
        for palavra in AnalisadorPrioridadeAvancado.PALAVRAS_ALTAS_MULTIPLOS:
            if palavra in texto_completo:
                return {
                    'prioridade': 'alta',
                    'urgencia': 8,
                    'impacto': 'alto',
                    'confianca': 90,
                    'metodo': 'regra_alta_multiplos',
                    'justificativa': f'Múltiplos usuários: "{palavra}"',
                    'tempo_estimado_resolucao': '1-2 horas'
                }
        
        # BUG
        if categoria and categoria.lower() == 'bug':
            if any(p in texto_completo for p in ['grave', 'crítico', 'sério', 'importante']):
                return {
                    'prioridade': 'alta',
                    'urgencia': 7,
                    'impacto': 'alto',
                    'confianca': 80,
                    'metodo': 'regra_bug_grave',
                    'justificativa': 'Bug grave',
                    'tempo_estimado_resolucao': '2-4 horas'
                }
            else:
                return {
                    'prioridade': 'media',
                    'urgencia': 5,
                    'impacto': 'medio',
                    'confianca': 75,
                    'metodo': 'regra_bug_medio',
                    'justificativa': 'Bug sem gravidade clara',
                    'tempo_estimado_resolucao': '4-8 horas'
                }
        
        # BAIXA (verificar ANTES de média)
        for palavra in AnalisadorPrioridadeAvancado.PALAVRAS_BAIXAS_DUVIDA:
            if palavra in titulo_lower or palavra in descricao_lower[:100]:
                return {
                    'prioridade': 'baixa',
                    'urgencia': 2,
                    'impacto': 'baixo',
                    'confianca': 85,
                    'metodo': 'regra_baixa_duvida',
                    'justificativa': 'Dúvida sobre uso',
                    'tempo_estimado_resolucao': '1-2 horas'
                }
        
        for palavra in AnalisadorPrioridadeAvancado.PALAVRAS_BAIXAS_SUGESTAO:
            if palavra in titulo_lower or palavra in descricao_lower[:100]:
                return {
                    'prioridade': 'baixa',
                    'urgencia': 2,
                    'impacto': 'baixo',
                    'confianca': 90,
                    'metodo': 'regra_baixa_sugestao',
                    'justificativa': 'Sugestão (não urgente)',
                    'tempo_estimado_resolucao': '24-48 horas'
                }
        
        if categoria and categoria.lower() in ['duvida', 'feature', 'outro']:
            return {
                'prioridade': 'baixa',
                'urgencia': 3,
                'impacto': 'baixo',
                'confianca': 80,
                'metodo': 'regra_categoria_baixa',
                'justificativa': f'Categoria "{categoria}" - baixa urgência',
                'tempo_estimado_resolucao': '4-24 horas'
            }
        
        # MÉDIA
        for palavra in AnalisadorPrioridadeAvancado.PALAVRAS_MEDIAS:
            if palavra in texto_completo:
                return {
                    'prioridade': 'media',
                    'urgencia': 5,
                    'impacto': 'medio',
                    'confianca': 70,
                    'metodo': 'regra_media',
                    'justificativa': f'Problema moderado: "{palavra}"',
                    'tempo_estimado_resolucao': '4-8 horas'
                }
        
        # CAIXA ALTA
        if len(titulo) > 5 and sum(1 for c in titulo if c.isupper()) > len(titulo) * 0.7:
            tem_critica = any(p in titulo_lower for p in ['parado', 'travado', 'caiu'])
            if tem_critica:
                return {
                    'prioridade': 'critica',
                    'urgencia': 9,
                    'impacto': 'critico',
                    'confianca': 90,
                    'metodo': 'regra_caixa_alta_critica',
                    'justificativa': 'CAIXA ALTA + palavra crítica',
                    'tempo_estimado_resolucao': '15-30 minutos'
                }
            else:
                return {
                    'prioridade': 'alta',
                    'urgencia': 7,
                    'impacto': 'alto',
                    'confianca': 60,
                    'metodo': 'regra_caixa_alta',
                    'justificativa': 'CAIXA ALTA = urgência',
                    'tempo_estimado_resolucao': '1-2 horas'
                }
        
        # EXCLAMAÇÕES
        if texto_completo.count('!') >= 3:
            return {
                'prioridade': 'alta',
                'urgencia': 7,
                'impacto': 'alto',
                'confianca': 55,
                'metodo': 'regra_exclamacoes',
                'justificativa': 'Múltiplas exclamações',
                'tempo_estimado_resolucao': '1-2 horas'
            }
        
        # PADRÃO
        return {
            'prioridade': 'media',
            'urgencia': 5,
            'impacto': 'medio',
            'confianca': 40,
            'metodo': 'padrao',
            'justificativa': 'Sem padrão claro',
            'tempo_estimado_resolucao': '4-8 horas'
        }
    
    @staticmethod
    def calcular_score(prioridade: str, urgencia: int, tempo_espera_minutos: float = 0) -> int:
        """Calcula score para fila"""
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
    """CAMADA 2: Cache de tickets similares"""
    try:
        texto_busca = f"{titulo} {descricao}"
        embedding_busca = modelo_embedding.encode([texto_busca])[0].reshape(1, -1)
        
        tickets = list(colecao_tickets.find({
            "embedding": {"$exists": True},
            "status": {"$in": ["resolvido", "fechado"]}
        }).limit(100))
        
        if not tickets:
            return []
        
        tickets_similares = []
        for ticket in tickets:
            if "embedding" not in ticket or not ticket["embedding"]:
                continue
                
            ticket_embedding = np.array(ticket["embedding"]).reshape(1, -1)
            similaridade = cosine_similarity(embedding_busca, ticket_embedding)[0][0]
            
            if similaridade > 0.70:
                tickets_similares.append({
                    "ticket": ticket,
                    "similaridade": float(similaridade)
                })
        
        tickets_similares.sort(key=lambda x: x["similaridade"], reverse=True)
        return tickets_similares[:limite]
        
    except Exception as e:
        print(f"[CACHE] ❌ Erro: {e}")
        return []


def analisar_ticket_com_ia(titulo: str, descricao: str, categoria: Optional[str] = None) -> Dict:
    """CAMADA 4: IA Gemini (último recurso)"""
    
    prompt = f"""
Você é especialista em triagem de tickets ERP.

**TICKET:**
Título: {titulo}
Descrição: {descricao}
Categoria: {categoria or "Não informada"}

**CRITÉRIOS:**
🔴 CRÍTICA: Sistema parado, dados perdidos, segurança comprometida
🟠 ALTA: Funcionalidade importante quebrada, múltiplos usuários afetados
🟡 MÉDIA: Problemas moderados, workaround disponível
🟢 BAIXA: Dúvidas, sugestões, problemas cosméticos

Retorne JSON:
{{
  "prioridade": "critica|alta|media|baixa",
  "urgencia": 1-10,
  "impacto": "critico|alto|medio|baixo",
  "justificativa": "por que essa prioridade",
  "tempo_estimado_resolucao": "ex: 1-2 horas"
}}
"""

    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        response = model.generate_content(prompt, generation_config={"temperature": 0.1})
        response_text = response.text.strip()
        
        if response_text.startswith("```"):
            response_text = response_text.replace("```json", "").replace("```", "").strip()
        
        analise = json.loads(response_text)
        
        # Validação
        texto_completo = f"{titulo} {descricao}".lower()
        palavras_criticas = ["parado", "travado", "não funciona", "caiu", "fora do ar"]
        
        if any(p in texto_completo for p in palavras_criticas):
            if analise.get("prioridade") not in ["critica", "alta"]:
                analise["prioridade"] = "critica"
                analise["urgencia"] = 10
        
        return analise
        
    except Exception as e:
        print(f"[IA] ❌ Erro: {e}")
        return {
            "prioridade": "media",
            "urgencia": 5,
            "impacto": "medio",
            "erro": str(e)
        }


def analisar_prioridade_hibrido(
    titulo: str,
    descricao: str,
    categoria: str,
    usar_ia: bool = True,
    usar_cache: bool = True,
    usar_ml: bool = True
) -> Dict:
    """
    🧠 SISTEMA COM 4 CAMADAS (+ APRENDIZADO):
    
    1. REGRAS (0-5ms) - Padrões fixos
    2. CACHE (10-50ms) - Tickets similares
    3. ML (50-100ms) - 🆕 APRENDE COM FEEDBACK!
    4. IA Gemini (1-3s) - Último recurso
    """
    
    print(f"\n[PRIORIZAÇÃO] Analisando...")
    tempo_inicio = time.time()
    
    # CAMADA 1: REGRAS
    analise_regras = AnalisadorPrioridadeAvancado.analisar_por_regras(titulo, descricao, categoria)
    print(f"  ✓ Regras: {analise_regras['prioridade'].upper()} ({analise_regras['confianca']}%)")
    
    if analise_regras['confianca'] >= 85:
        tempo_total = int((time.time() - tempo_inicio) * 1000)
        score = AnalisadorPrioridadeAvancado.calcular_score(
            analise_regras['prioridade'],
            analise_regras['urgencia']
        )
        return {
            **analise_regras,
            'score': score,
            'tempo_processamento_ms': tempo_total,
            'analise_ia': None
        }
    
    # CAMADA 2: CACHE
    if usar_cache:
        try:
            print(f"  🔍 Cache...")
            similares = buscar_tickets_similares(titulo, descricao, limite=3)
            
            if similares and similares[0]['similaridade'] > 0.90:
                ticket_similar = similares[0]['ticket']
                tempo_total = int((time.time() - tempo_inicio) * 1000)
                
                print(f"  ✓ Cache hit! ({tempo_total}ms)")
                
                prioridade = ticket_similar.get('prioridade', 'media')
                urgencia = ticket_similar.get('analise_ia', {}).get('urgencia', 5)
                score = AnalisadorPrioridadeAvancado.calcular_score(prioridade, urgencia)
                
                return {
                    'prioridade': prioridade,
                    'urgencia': urgencia,
                    'impacto': ticket_similar.get('analise_ia', {}).get('impacto', 'medio'),
                    'score': score,
                    'confianca': 95,
                    'metodo': 'cache_similar',
                    'justificativa': f"Similar a #{ticket_similar.get('numero_ticket', 'N/A')}",
                    'tempo_estimado_resolucao': ticket_similar.get('analise_ia', {}).get('tempo_estimado_resolucao', 'A definir'),
                    'tempo_processamento_ms': tempo_total,
                    'analise_ia': None
                }
        except Exception as e:
            print(f"  ⚠️ Cache: {e}")
    
    # CAMADA 3: MODELO ML (APRENDIZADO!) 🆕
    if usar_ml:
        try:
            print(f"  🤖 ML...")
            predicao = modelo_ml.prever(titulo, descricao, categoria)
            
            if predicao and predicao['confianca'] >= 70:
                tempo_total = int((time.time() - tempo_inicio) * 1000)
                
                print(f"  ✓ ML: {predicao['prioridade'].upper()} ({predicao['confianca']:.0f}%) em {tempo_total}ms")
                
                score = AnalisadorPrioridadeAvancado.calcular_score(
                    predicao['prioridade'],
                    predicao['urgencia']
                )
                
                return {
                    'prioridade': predicao['prioridade'],
                    'urgencia': predicao['urgencia'],
                    'impacto': {'baixa': 'baixo', 'media': 'medio', 'alta': 'alto', 'critica': 'critico'}[predicao['prioridade']],
                    'score': score,
                    'confianca': predicao['confianca'],
                    'metodo': 'modelo_ml_aprendizado',
                    'justificativa': f"ML treinado ({predicao['confianca']:.0f}% confiança)",
                    'tempo_estimado_resolucao': 'Baseado em histórico',
                    'tempo_processamento_ms': tempo_total,
                    'probabilidades_ml': predicao['probabilidades'],
                    'analise_ia': None
                }
        except Exception as e:
            print(f"  ⚠️ ML: {e}")
    
    # CAMADA 4: IA GEMINI
    if usar_ia:
        try:
            print(f"  🤖 IA Gemini...")
            analise_ia = analisar_ticket_com_ia(titulo, descricao, categoria)
            
            tempo_total = int((time.time() - tempo_inicio) * 1000)
            print(f"  ✓ IA: {tempo_total}ms")
            
            prioridade_final = analise_ia.get('prioridade', 'media')
            
            # Validação com regras
            if analise_regras['prioridade'] == 'critica' and prioridade_final not in ['critica', 'alta']:
                prioridade_final = 'critica'
                analise_ia['urgencia'] = 10
            
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
                'justificativa': analise_ia.get('justificativa', ''),
                'tempo_estimado_resolucao': analise_ia.get('tempo_estimado_resolucao', 'A definir'),
                'tempo_processamento_ms': tempo_total,
                'analise_ia': analise_ia
            }
        except Exception as e:
            print(f"  ❌ IA: {e}")
    
    # FALLBACK
    tempo_total = int((time.time() - tempo_inicio) * 1000)
    score = AnalisadorPrioridadeAvancado.calcular_score(
        analise_regras['prioridade'],
        analise_regras['urgencia']
    )
    
    return {
        **analise_regras,
        'score': score,
        'metodo': 'regras_fallback',
        'tempo_processamento_ms': tempo_total,
        'analise_ia': None
    }


# FUNÇÃO LEGACY (compatibilidade)
def calcular_prioridade_inteligente(titulo: str, descricao: str, categoria: str, usar_ia: bool = True, cliente_email: Optional[str] = None) -> Dict:
    """Compatibilidade com código antigo"""
    resultado = analisar_prioridade_hibrido(titulo, descricao, categoria, usar_ia=usar_ia)
    
    similares = buscar_tickets_similares(titulo, descricao, limite=3)
    resultado['tickets_similares'] = similares
    
    recomendacoes = []
    if resultado['prioridade'] in ['critica', 'alta']:
        recomendacoes.append("⚠️ Prioridade!")
    
    if similares:
        tempos = [s['ticket'].get('tempo_resolucao_minutos', 0) for s in similares if s['ticket'].get('tempo_resolucao_minutos')]
        if tempos:
            tempo_medio = sum(tempos) / len(tempos)
            recomendacoes.append(f"📊 ~{int(tempo_medio)} min (histórico)")
    
    if cliente_email:
        try:
            from database import colecao_usuarios
            usuario = colecao_usuarios.find_one({"email": cliente_email})
            if usuario and usuario.get("tipo_usuario") == "vip":
                resultado['score'] += 2000
                recomendacoes.append("⭐ Cliente VIP")
        except:
            pass
    
    resultado['recomendacoes'] = recomendacoes
    return resultado


def adicionar_embedding_ao_ticket(ticket_id: str, titulo: str, descricao: str):
    """Adiciona embedding ao ticket"""
    try:
        from bson import ObjectId
        texto = f"{titulo} {descricao}"
        embedding = modelo_embedding.encode([texto])[0].tolist()
        
        colecao_tickets.update_one(
            {"_id": ObjectId(ticket_id)},
            {"$set": {"embedding": embedding}}
        )
        
        print(f"[EMBEDDING] ✅ Adicionado ao ticket {ticket_id[:8]}...")
        
    except Exception as e:
        print(f"[EMBEDDING] ❌ Erro: {e}")


def gerar_resposta_automatica_ticket(ticket: Dict) -> Optional[str]:
    """Resposta automática baseada em similares"""
    similares = buscar_tickets_similares(ticket["titulo"], ticket["descricao"], limite=3)
    
    if not similares or similares[0]["similaridade"] < 0.85:
        return None
    
    ticket_similar = similares[0]["ticket"]
    mensagens = ticket_similar.get("mensagens", [])
    respostas = [m for m in mensagens if m.get("is_atendente", False)]
    
    if not respostas:
        return None
    
    prompt = f"""
Você é atendente de suporte.

Cliente: {ticket["titulo"]}
Descrição: {ticket["descricao"]}

Solução similar: {respostas[0]["conteudo"]}

Adapte a solução. Seja claro e profissional.
"""
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        response = model.generate_content(prompt, generation_config={"temperature": 0.3})
        
        resposta = response.text.strip()
        return f"{resposta}\n\n---\n_💡 Sugestão automática. Atendente revisará._"
        
    except Exception as e:
        print(f"[RESPOSTA AUTO] ❌ Erro: {e}")
        return None


print("[✓] Sistema carregado!")
print("    • Camada 1: Regras (0-5ms)")
print("    • Camada 2: Cache (10-50ms)")
print("    • Camada 3: ML Aprendizado (50-100ms) 🆕")
print("    • Camada 4: IA Gemini (1-3s)")
print("\n💡 Para treinar ML: python retreinar_modelo.py")