from fastapi import FastAPI, HTTPException, Query
from typing import List
from db import clientes_collection
from models import Unidad, AuthRequest
from utils import llenar_unidades_para_cliente

app = FastAPI(title="API de Unidades por Cliente", redoc_url="/documentacion",docs_url=None)


@app.post("/external/getUnits", response_model=List[Unidad])
def consultar_unidades(auth: AuthRequest):
    # Buscar cliente
    cliente = clientes_collection.find_one({"id": auth.cliente_id})
    if not cliente:
        raise HTTPException(status_code=404, detail="ID de cliente no encontrado")

    # Validar token
    tokens_validos = [token["tokenConexion"] for token in cliente.get("token_access_externo", [])]
    if auth.token_encriptado not in tokens_validos:
        raise HTTPException(status_code=401, detail="Token inválido")

    try:
        # Llenar unidades desde Wialon
        llenar_unidades_para_cliente(auth.cliente_id, "a3bb803c27770ea3a0082be2b77c328eE86E433926A9FF64D7223EFB32D698699962043D")
        cliente = clientes_collection.find_one({"id": auth.cliente_id})  # Recargar datos actualizados
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    unidades = cliente.get("unidades", [])

    # Si se proporciona una ID de unidad específica
    if auth.id:
        unidad = next((u for u in unidades if u["id"] == auth.id), None)
        if not unidad:
            raise HTTPException(status_code=404, detail="Unidad no encontrada")
        return [unidad]

    return unidades
