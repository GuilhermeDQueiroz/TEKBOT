import os
import torch
import numpy as np
from datetime import datetime, timezone
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
from database import colecao_mensagens
import google.generativeai as genai
from typing import List, Dict, Optional

# === Configuração de ambiente ===
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Configuração da API do Gemini
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
print("[INFO] Utilizando a API do Gemini (Google AI)...")

# === Classe para gerenciar contexto da conversa ===
class GerenciadorContexto:
    def __init__(self, max_historico: int = 10, max_tokens_contexto: int = 1500):
        self.historico_conversa: List[Dict] = []
        self.max_historico = max_historico
        self.max_tokens_contexto = max_tokens_contexto
        self.sessao_id = self.gerarSessaoId()
        
    def gerarSessaoId(self) -> str:
        """Gera um ID único para a sessão de conversa"""
        return f"sessao_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    def adicionarInteracao(self, pergunta: str, resposta: str, contexto_utilizado: List = None):
        """Adiciona uma nova interação ao histórico"""
        interacao = {
            "pergunta": pergunta,
            "resposta": resposta,
            "contexto_utilizado": contexto_utilizado or [],
            "timestamp": datetime.now(timezone.utc)
        }
        
        self.historico_conversa.append(interacao)
        
        # Manter apenas as últimas N interações
        if len(self.historico_conversa) > self.max_historico:
            self.historico_conversa.pop(0)
    
    def obterContextoConversa(self) -> str:
        """Obtém o contexto formatado da conversa atual"""
        if not self.historico_conversa:
            return ""
        
        contexto_texto = "HISTÓRICO DA CONVERSA ATUAL:\n"
        for i, interacao in enumerate(self.historico_conversa[-5:], 1):  # Últimas 5 interações
            contexto_texto += f"\n{i}. USUÁRIO: {interacao['pergunta']}\n"
            contexto_texto += f"   ASSISTENTE: {interacao['resposta']}\n"
        
        # Limitar tamanho do contexto
        if len(contexto_texto) > self.max_tokens_contexto:
            contexto_texto = contexto_texto[-self.max_tokens_contexto:]
        
        return contexto_texto
    
    def verificarContinuidade(self, nova_pergunta: str) -> bool:
        """Verifica se a pergunta atual é uma continuação da anterior"""
        if not self.historico_conversa:
            return False
            
        ultima_interacao = self.historico_conversa[-1]
        ultima_pergunta = ultima_interacao['pergunta'].lower()
        nova_pergunta_lower = nova_pergunta.lower()
        
        # Palavras-chave que indicam continuação
        palavras_continuacao = [
            'continue', 'continuar', 'mais', 'detalhe', 'detalhes', 'explique melhor',
            'como assim', 'e depois', 'próximo', 'passo', 'então', 'e se', 'mas'
        ]
        
        return any(palavra in nova_pergunta_lower for palavra in palavras_continuacao)
    
    def obterUltimaResposta(self) -> Optional[str]:
        """Obtém a última resposta dada pelo assistente"""
        if self.historico_conversa:
            return self.historico_conversa[-1]['resposta']
        return None
    
    def salvarSessao(self):
        """Salva o histórico da sessão no banco de dados"""
        try:
            sessao_data = {
                "tipo": "sessao_conversa",
                "sessao_id": self.sessao_id,
                "historico": self.historico_conversa,
                "data_inicio": self.historico_conversa[0]['timestamp'] if self.historico_conversa else datetime.now(timezone.utc),
                "data_fim": datetime.now(timezone.utc),
                "total_interacoes": len(self.historico_conversa)
            }
            colecao_mensagens.insert_one(sessao_data)
            print(f"[INFO] Sessão {self.sessao_id} salva com {len(self.historico_conversa)} interações.")
        except Exception as e:
            print(f"[ERRO] Falha ao salvar sessão: {e}")
    
    def carregarUltimaSessao(self, limite_horas: int = 24):
        """Carrega a última sessão do usuário se foi recente"""
        try:
            tempo_limite = datetime.now(timezone.utc).timestamp() - (limite_horas * 3600)
            
            ultima_sessao = colecao_mensagens.find_one(
                {
                    "tipo": "sessao_conversa",
                    "data_fim": {"$gte": datetime.fromtimestamp(tempo_limite, timezone.utc)}
                },
                sort=[("data_fim", -1)]
            )
            
            if ultima_sessao and ultima_sessao.get("historico"):
                self.historico_conversa = ultima_sessao["historico"]
                self.sessao_id = ultima_sessao["sessao_id"]
                print(f"[INFO] Sessão anterior carregada: {len(self.historico_conversa)} interações.")
                return True
            return False
        except Exception as e:
            print(f"[ERRO] Falha ao carregar sessão anterior: {e}")
            return False

# Instância global do gerenciador de contexto
contexto_manager = GerenciadorContexto()

# === Funções modificadas ===

def gerarRespostaComIa(contexto_relevante: List, pergunta: str, contexto_conversa: str = "") -> str:
    """Gera uma resposta usando a API do Gemini com base em contexto e histórico da conversa."""
    
    # Contexto da base de conhecimento
    contexto_base = ""
    if contexto_relevante:
        contexto_base = "\n".join(
            f"P: {doc.get('pergunta', '')}\nR: {doc.get('resposta', '')}"
            for doc in contexto_relevante
        )
    
    # Verificar se é uma continuação
    eh_continuacao = contexto_manager.verificarContinuidade(pergunta)
    ultima_resposta = contexto_manager.obterUltimaResposta()
    
    # Construir prompt baseado no tipo de pergunta
    if eh_continuacao and ultima_resposta:
        prompt = f"""
Você é um atendente especialista em sistema ERP.
O usuário está pedindo continuação ou mais detalhes sobre a resposta anterior.

{contexto_conversa}

ÚLTIMA RESPOSTA DADA:
{ultima_resposta}

NOVA PERGUNTA (continuação): {pergunta}

Continue ou detalhe a resposta anterior conforme solicitado:
"""
    else:
        prompt = f"""
Você é um atendente especialista em sistema ERP.
Use o histórico da conversa para manter contexto e coerência nas respostas.

{contexto_conversa}

CONHECIMENTO BASE RELEVANTE:
{contexto_base}

NOVA PERGUNTA: {pergunta}
Resposta:
"""
    
    try:
        # Seleciona o modelo do Gemini (gemini-1.5-flash é rápido e eficiente)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')

        # Configurações de geração para controlar a saída da IA
        generation_config = {
            "temperature": 0.3,
            "max_output_tokens": 512,
        }

        response = model.generate_content(
            prompt,
            generation_config=generation_config
        )

        return response.text.strip()

    except Exception as e:
        print(f"[ERRO] Erro ao chamar a API Gemini: {e}")
        return "Erro ao gerar resposta com a IA do Gemini."


def recuperarInfoRelevantes(pergunta: str) -> List[Dict]:
    """Recupera informações relevantes, considerando também o contexto da conversa"""
    try:
        # Buscar na base de conhecimento
        documentos = list(colecao_mensagens.find({"tipo": {"$ne": "interacao", "$ne": "sessao_conversa"}}))
        
        # Se for continuação, priorizar contexto da conversa
        if contexto_manager.verificarContinuidade(pergunta):
            return []  # Para continuações, não buscar nova base, usar apenas contexto da conversa
            
    except Exception as e:
        print(f"[ERRO] Acesso ao banco falhou: {e}")
        return []

    if not documentos:
        return []

    pergunta_embedding = modelo_embedding.encode([pergunta])[0].reshape(1, -1)
    documentos_com_similaridade = []

    for doc in documentos:
        pergunta_doc = doc.get("pergunta", "")
        if not pergunta_doc:
            continue

        if "embedding" in doc:
            doc_embedding = np.array(doc["embedding"]).reshape(1, -1)
        else:
            doc_embedding_np = modelo_embedding.encode([pergunta_doc])[0]
            doc_embedding = doc_embedding_np.reshape(1, -1)
            try:
                colecao_mensagens.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"embedding": doc_embedding_np.tolist()}}
                )
            except Exception as e:
                print(f"[WARN] Não foi possível salvar embedding: {e}")

        similaridade = cosine_similarity(pergunta_embedding, doc_embedding)[0][0]
        documentos_com_similaridade.append((doc, similaridade))

    documentos_com_similaridade.sort(key=lambda x: x[1], reverse=True)
    return [doc for doc, sim in documentos_com_similaridade[:5] if sim > 0.6]


def registrarInteracao(pergunta: str, resposta: str, contexto: List):
    """Registra a interação no banco e no contexto da conversa"""
    # Adicionar ao contexto da conversa
    contexto_manager.adicionarInteracao(pergunta, resposta, contexto)
    
    # Registrar no banco como antes
    interacao = {
        "tipo": "interacao",
        "pergunta": pergunta,
        "resposta": resposta,
        "contexto_utilizado": [{"_id": doc["_id"], "pergunta": doc.get("pergunta")} for doc in contexto if isinstance(doc, dict)],
        "sessao_id": contexto_manager.sessao_id,
        "data": datetime.now(timezone.utc)
    }
    try:
        colecao_mensagens.insert_one(interacao)
        print("[INFO] Interação salva no banco de dados.")
    except Exception as e:
        print(f"[ERRO] Falha ao salvar interação: {e}")


def treinarNovaPergunta(pergunta: str, resposta: str):
    """Simula aprendizado incremental armazenando a pergunta e resposta como novo dado de conhecimento."""
    try:
        embedding = modelo_embedding.encode([pergunta])[0].tolist()
        novo_conhecimento = {
            "tipo": "base_conhecimento",
            "pergunta": pergunta,
            "resposta": resposta,
            "embedding": embedding,
            "data": datetime.now(timezone.utc)
        }
        colecao_mensagens.insert_one(novo_conhecimento)
        print("[INFO] Nova pergunta/resposta registrada na base de conhecimento.")
    except Exception as e:
        print(f"[ERRO] Falha ao treinar nova pergunta: {e}")


# === Execução via terminal para testes ===
if __name__ == "__main__":
    print("\n[ASSISTENTE ERP - Tek-System IA com Gemini e Contexto Conversacional]")
    print("Pergunte sobre rotinas fiscais, NFe, SPED, SEFAZ.")
    print("Digite 'sair' para encerrar, 'aprender' para ensinar algo novo,")
    print("'historico' para ver histórico da conversa, ou 'nova_sessao' para começar nova conversa.\n")
    
    # Tentar carregar sessão anterior
    if contexto_manager.carregarUltimaSessao():
        print("[INFO] Conversa anterior carregada. Posso continuar de onde paramos.")
        print("Digite 'historico' para ver o que já conversamos.\n")

    while True:
        try:
            pergunta = input("Pergunta: ").strip()
            if not pergunta:
                continue
                
            if pergunta.lower() == "sair":
                contexto_manager.salvarSessao()
                print("Encerrando assistente. Conversa salva.")
                break
                
            if pergunta.lower() == "historico":
                print("\n" + "="*50)
                print(contexto_manager.obterContextoConversa())
                print("="*50 + "\n")
                continue
                
            if pergunta.lower() == "nova_sessao":
                contexto_manager.salvarSessao()
                contexto_manager = GerenciadorContexto()
                print("[INFO] Nova sessão iniciada.\n")
                continue
                
            if pergunta.lower().startswith("aprender"):
                nova_pergunta = input("Nova pergunta: ").strip()
                nova_resposta = input("Resposta correta: ").strip()
                treinarNovaPergunta(nova_pergunta, nova_resposta)
                continue

            # Obter contexto da conversa atual
            contexto_conversa = contexto_manager.obterContextoConversa()
            
            # Recuperar documentos relevantes
            documentos_relevantes = recuperarInfoRelevantes(pergunta)

            # Verificar se é resposta direta de alta similaridade
            if documentos_relevantes and not contexto_manager.verificarContinuidade(pergunta):
                pergunta_embedding = modelo_embedding.encode([pergunta]).reshape(1, -1)
                doc_top = documentos_relevantes[0]
                doc_embedding = modelo_embedding.encode([doc_top.get("pergunta", "")]).reshape(1, -1)
                similaridade = cosine_similarity(pergunta_embedding, doc_embedding)[0][0]
                
                if similaridade > 0.9:
                    resposta = doc_top.get("resposta", "")
                    print(f"\n[RESPOSTA (base)]: {resposta}\n")
                    registrarInteracao(pergunta, resposta, [doc_top])
                    continue

            # Gerar resposta com IA usando contexto
            resposta = gerarRespostaComIa(documentos_relevantes, pergunta, contexto_conversa)
            registrarInteracao(pergunta, resposta, documentos_relevantes)
            
            # Identificar tipo de resposta
            tipo_resposta = "[CONTINUAÇÃO]" if contexto_manager.verificarContinuidade(pergunta) else "[RESPOSTA (IA)]"
            print(f"\n{tipo_resposta}: {resposta}\n")

        except KeyboardInterrupt:
            contexto_manager.salvarSessao()
            print("\nEncerrando assistente. Conversa salva.")
            break
        except Exception as e:
            print(f"[ERRO]: {e}")