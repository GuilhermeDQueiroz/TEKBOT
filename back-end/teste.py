import sys
sys.path.append('.')

from rag import analisar_prioridade_hibrido

testes = [
    ("Como cadastrar cliente?", "Gostaria de saber como faço", "duvida", "baixa"),
    ("Sistema está lento", "O sistema está demorando", "tecnico", "media"),
    ("Erro ao salvar", "Não consigo salvar os dados", "bug", "media"),
    ("Erro grave ao salvar", "Bug crítico que impede salvar", "bug", "alta"),
    ("Sistema parado", "O sistema está completamente travado", "tecnico", "critica"),
    ("SISTEMA PARADO!!!", "Nada funciona, sistema caiu", "tecnico", "critica"),
]

print("\n" + "="*70)
print("🧪 TESTE DE CLASSIFICAÇÃO")
print("="*70)

corretos = 0
for titulo, descricao, categoria, esperado in testes:
    resultado = analisar_prioridade_hibrido(titulo, descricao, categoria, usar_ia=False)
    obtido = resultado['prioridade']
    status = "✅" if obtido == esperado else "❌"
    
    print(f"\n{status} [{esperado.upper()}] {titulo}")
    print(f"   Obtido: {obtido.upper()} ({resultado['metodo']})")
    print(f"   Tempo: {resultado['tempo_processamento_ms']}ms")
    
    if obtido == esperado:
        corretos += 1

print(f"\n{'='*70}")
print(f"📊 Resultado: {corretos}/{len(testes)} corretos ({corretos/len(testes)*100:.0f}%)")