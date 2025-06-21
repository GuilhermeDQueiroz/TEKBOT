from pydantic import BaseModel

# Classe para criar um usuário
class UsuarioCriar(BaseModel):
    username: str
    email: str
    senha: str

# Classe para responder ao usuário (informações básicas)
class UsuarioResposta(BaseModel):
    username: str
    email: str

# Classe para retornar o token de autenticação
class Token(BaseModel):
    access_token: str
    token_type: str

# Classe para requisição de consulta no chatbot
class RequisicaoConsulta(BaseModel):
    consulta: str

# Classe para entrada de pergunta no chatbot
class PerguntaEntrada(BaseModel):
    pergunta: str

class MensagemEntrada(BaseModel):
    texto: str

