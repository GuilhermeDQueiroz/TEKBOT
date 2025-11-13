"""
Torna um usuário existente em admin

Execute: python tornar_admin.py
"""

from database import colecao_usuarios

# Email do usuário que será admin
email = "contato.thiagofreitasp@gmail.com"

# Atualizar para admin
resultado = colecao_usuarios.update_one(
    {"email": email},
    {"$set": {"tipo_usuario": "admin"}}
)

if resultado.modified_count > 0:
    print(f"✅ Usuário {email} agora é ADMIN!")
    
    # Verificar
    usuario = colecao_usuarios.find_one({"email": email})
    print(f"   Tipo: {usuario.get('tipo_usuario')}")
else:
    print(f"❌ Usuário {email} não encontrado ou já era admin")