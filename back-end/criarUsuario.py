#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para Criação de Usuários do Sistema TekBot
Permite criar usuários Admin e Atendente
"""

import sys
import os
from datetime import datetime
from getpass import getpass
import hashlib

try:
    from pymongo import MongoClient
    from dotenv import load_dotenv
except ImportError:
    print("❌ Dependências não encontradas!")
    print("Execute: pip install pymongo python-dotenv")
    sys.exit(1)

# Carregar variáveis de ambiente
load_dotenv()

# Configurações
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DATABASE_NAME = os.getenv("DATABASE_NAME", "tekbot")

def conectar_mongodb():
    """Conecta ao MongoDB e retorna a coleção de usuários"""
    try:
        print("🔌 Conectando ao MongoDB...")
        client = MongoClient(MONGO_URI)
        db = client[DATABASE_NAME]
        
        # Testar conexão
        client.admin.command('ping')
        print("✅ Conexão estabelecida com sucesso!")
        
        return client, db, db.usuarios
    except Exception as e:
        print(f"❌ Erro ao conectar ao MongoDB: {e}")
        print("Verifique se o MongoDB está rodando e a URI está correta.")
        return None, None, None

def hash_senha(senha):
    """Gera hash da senha usando SHA-256"""
    return hashlib.sha256(senha.encode()).hexdigest()

def validar_email(email):
    """Valida formato básico do email"""
    if not email or "@" not in email or "." not in email.split("@")[1]:
        return False
    return True

def verificar_usuario_existe(colecao_usuarios, email):
    """Verifica se usuário já existe"""
    return colecao_usuarios.find_one({"email": email}) is not None

def listar_usuarios(colecao_usuarios, nivel=None):
    """Lista usuários do sistema"""
    filtro = {"nivel": nivel} if nivel else {}
    usuarios = list(colecao_usuarios.find(filtro))
    
    if not usuarios:
        print(f"\n📋 Nenhum usuário {nivel if nivel else ''} encontrado.")
        return
    
    print(f"\n📋 Usuários {nivel if nivel else 'cadastrados'}:")
    print("-" * 80)
    for i, user in enumerate(usuarios, 1):
        status = "✅ ATIVO" if user.get("ativo", True) else "❌ INATIVO"
        criado = user.get("criado_em", "N/A")
        print(f"{i}. {user['email']:<30} | Nível: {user['nivel']:<10} | {status}")
        if isinstance(criado, datetime):
            print(f"   Criado em: {criado.strftime('%d/%m/%Y %H:%M')}")
    print("-" * 80)

def criar_usuario(colecao_usuarios, nivel):
    """Cria um novo usuário"""
    print(f"\n{'=' * 60}")
    print(f"    CRIAÇÃO DE USUÁRIO {nivel.upper()}")
    print(f"{'=' * 60}")
    
    # Coletar email
    while True:
        email = input("\n📧 Email: ").strip().lower()
        
        if not email:
            print("❌ Email não pode estar vazio.")
            continue
        
        if not validar_email(email):
            print("❌ Formato de email inválido.")
            continue
        
        if verificar_usuario_existe(colecao_usuarios, email):
            print("❌ Este email já está cadastrado.")
            continue
        
        break
    
    # Coletar nome
    while True:
        nome = input("👤 Nome completo: ").strip()
        if nome:
            break
        print("❌ Nome não pode estar vazio.")
    
    # Coletar senha
    while True:
        senha = getpass("🔒 Senha (mínimo 8 caracteres): ")
        
        if len(senha) < 8:
            print("❌ Senha deve ter pelo menos 8 caracteres.")
            continue
        
        senha_confirma = getpass("🔒 Confirme a senha: ")
        
        if senha != senha_confirma:
            print("❌ Senhas não coincidem. Tente novamente.")
            continue
        
        break
    
    # Criar documento do usuário
    usuario = {
        "email": email,
        "nome": nome,
        "senha": hash_senha(senha),
        "nivel": nivel,
        "ativo": True,
        "criado_em": datetime.now(),
        "atualizado_em": datetime.now()
    }
    
    # Adicionar campos específicos por nível
    if nivel == "atendente":
        usuario["tickets_atribuidos"] = []
        usuario["tickets_resolvidos"] = 0
        usuario["avaliacao_media"] = 0.0
    elif nivel == "admin":
        usuario["permissoes_especiais"] = ["gerenciar_usuarios", "visualizar_relatorios", "configurar_sistema"]
    
    # Inserir no banco
    try:
        resultado = colecao_usuarios.insert_one(usuario)
        print(f"\n✅ Usuário {nivel} criado com sucesso!")
        print(f"   ID: {resultado.inserted_id}")
        print(f"   Email: {email}")
        print(f"   Nome: {nome}")
        return True
    except Exception as e:
        print(f"\n❌ Erro ao criar usuário: {e}")
        return False

def menu_principal():
    """Exibe menu principal"""
    print("\n" + "=" * 60)
    print("    SISTEMA DE GERENCIAMENTO DE USUÁRIOS - TEKBOT")
    print("=" * 60)
    print("\n1. Criar Administrador")
    print("2. Criar Atendente")
    print("3. Listar todos os usuários")
    print("4. Listar apenas Administradores")
    print("5. Listar apenas Atendentes")
    print("6. Sair")
    print("\n" + "-" * 60)
    
    while True:
        try:
            opcao = input("\nEscolha uma opção: ").strip()
            if opcao in ['1', '2', '3', '4', '5', '6']:
                return opcao
            print("❌ Opção inválida. Escolha entre 1 e 6.")
        except KeyboardInterrupt:
            print("\n\n👋 Operação cancelada pelo usuário.")
            return '6'

def main():
    """Função principal"""
    print("\n🤖 BEM-VINDO AO CONFIGURADOR DE USUÁRIOS DO TEKBOT")
    
    # Conectar ao MongoDB
    client, db, colecao_usuarios = conectar_mongodb()
    if not client:
        return
    
    try:
        while True:
            opcao = menu_principal()
            
            if opcao == '1':
                criar_usuario(colecao_usuarios, "admin")
            
            elif opcao == '2':
                criar_usuario(colecao_usuarios, "atendente")
            
            elif opcao == '3':
                listar_usuarios(colecao_usuarios)
            
            elif opcao == '4':
                listar_usuarios(colecao_usuarios, "admin")
            
            elif opcao == '5':
                listar_usuarios(colecao_usuarios, "atendente")
            
            elif opcao == '6':
                print("\n👋 Encerrando o sistema...")
                break
            
            input("\nPressione ENTER para continuar...")
    
    except KeyboardInterrupt:
        print("\n\n👋 Sistema encerrado pelo usuário.")
    
    finally:
        client.close()
        print("🔌 Conexão com MongoDB fechada.")
        print("✅ Sistema finalizado com sucesso!\n")

if __name__ == "__main__":
    main()