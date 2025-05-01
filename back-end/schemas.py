from pydantic import BaseModel

class UsuarioCriar(BaseModel):
    username: str
    email: str
    senha: str

class UsuarioResposta(BaseModel):
    username: str
    email: str

class Token(BaseModel):
    access_token: str
    token_type: str

class RequisicaoConsulta(BaseModel):
    consulta: str
