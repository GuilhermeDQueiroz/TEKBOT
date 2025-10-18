import sys
sys.path.append('.')

from datetime import datetime, timezone
from bson import ObjectId
from database import colecao_tickets, colecao_usuarios
from rag import analisar_prioridade_hibrido, adicionar_embedding_ao_ticket

# Criar usuário de teste
def criar_usuario():
    email = "teste_simples@sistema.com"
    if not colecao_usuarios.find_one({"email": email}):
        colecao_usuarios.insert_one({
            "nome": "Teste Simples",
            "email": email,
            "tipo_usuario": "cliente",
            "criado_em": datetime.now(timezone.utc)
        })
    return email

# Gerar número de ticket
def gerar_numero():
    ultimo = colecao_tickets.find_one(sort=[("numero_ticket", -1)])
    if ultimo and ultimo.get("numero_ticket"):
        num = int(ultimo["numero_ticket"].split("-")[-1])
        return f"TKT-{str(num + 1).zfill(6)}"
    return "TKT-000001"

# Testes
testes = [
    ("Como cadastrar cliente?", "Gostaria de saber como faço", "duvida", "baixa"),
    ("Sistema está lento", "O sistema está demorando", "tecnico", "media"),
    ("Erro ao salvar", "Não consigo salvar os dados", "bug", "media"),
    ("Erro grave ao salvar", "Bug crítico que impede salvar", "bug", "alta"),
    ("Sistema parado", "O sistema está completamente travado", "tecnico", "critica"),
    ("SISTEMA PARADO!!!", "Nada funciona, sistema caiu", "tecnico", "critica"),
]

print("\n" + "="*70)
print("🧪 TESTE DE CLASSIFICAÇÃO (GRAVANDO NO BANCO)")
print("="*70)

email_cliente = criar_usuario()
tickets_criados = []
corretos = 0

for titulo, descricao, categoria, esperado in testes:
    # Analisar prioridade
    resultado = analisar_prioridade_hibrido(
        titulo, 
        descricao, 
        categoria, 
        usar_ia=False,  # Apenas regras (rápido)
        usar_cache=True
    )
    
    obtido = resultado['prioridade']
    status = "✅" if obtido == esperado else "❌"
    
    # Criar ticket no banco
    numero = gerar_numero()
    ticket = {
        "numero_ticket": numero,
        "titulo": titulo,
        "descricao": descricao,
        "categoria": categoria,
        "prioridade": resultado['prioridade'],
        "status": "aberto",
        "score_prioridade": resultado['score'],
        "email_cliente": email_cliente,
        "analise_ia": {
            "urgencia": resultado['urgencia'],
            "impacto": resultado['impacto'],
            "justificativa": resultado['justificativa'],
            "metodo_usado": resultado['metodo'],
            "confianca": resultado['confianca'],
            "tempo_processamento_ms": resultado['tempo_processamento_ms']
        },
        "criado_em": datetime.now(timezone.utc),
        "atualizado_em": datetime.now(timezone.utc)
    }
    
    res = colecao_tickets.insert_one(ticket)
    ticket_id = str(res.inserted_id)
    tickets_criados.append(ticket_id)
    
    # Adicionar embedding
    adicionar_embedding_ao_ticket(ticket_id, titulo, descricao)
    
    # Exibir resultado
    print(f"\n{status} [{esperado.upper()}] {titulo}")
    print(f"   Obtido: {obtido.upper()} ({resultado['metodo']})")
    print(f"   Tempo: {resultado['tempo_processamento_ms']}ms")
    print(f"   Ticket: #{numero} (ID: {ticket_id[:8]}...)")
    
    if obtido == esperado:
        corretos += 1

print(f"\n{'='*70}")
print(f"📊 Resultado: {corretos}/{len(testes)} corretos ({corretos/len(testes)*100:.0f}%)")
print(f"💾 {len(tickets_criados)} tickets gravados no banco com embeddings")

# Verificar no banco
print(f"\n{'='*70}")
print("🔍 VERIFICANDO NO BANCO DE DADOS")
print(f"{'='*70}")

for ticket_id in tickets_criados:
    ticket = colecao_tickets.find_one({"_id": ObjectId(ticket_id)})
    if ticket:
        emb_status = "✅" if ticket.get('embedding') else "❌"
        print(f"  {emb_status} #{ticket['numero_ticket']}: {ticket['titulo'][:40]} - {ticket['prioridade'].upper()}")

# Limpar
print(f"\n{'='*70}")
resposta = input(f"\n🗑️  Deseja DELETAR os {len(tickets_criados)} tickets? (s/N): ")

if resposta.lower() == 's':
    for ticket_id in tickets_criados:
        colecao_tickets.delete_one({"_id": ObjectId(ticket_id)})
    print(f"✅ {len(tickets_criados)} tickets deletados")
else:
    print(f"✅ Tickets mantidos no banco")