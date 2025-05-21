from pydantic import BaseModel, Field
from typing import List,Optional


class AuthRequest(BaseModel):
    cliente_id: str
    token_encriptado: str
    placa: Optional[str] = None

class TokenExterno(BaseModel):
    clienteExterno: str
    tokenConexion: str

class Usuario(BaseModel):
    nombre: str
    apellidos: str
    rol: str

class Unidad(BaseModel):
    id: str
    longitud: float
    latitud: float
    fecha: str # ISO 8601
    matricula: str

class Cliente(BaseModel):
    id: str
    nombre: str
    token_access_externo: List[TokenExterno]
    usuarios: List[Usuario] = Field(default_factory=list)
    unidades: List[Unidad] = Field(default_factory=list)