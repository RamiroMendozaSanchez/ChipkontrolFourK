import requests
from datetime import datetime, timedelta
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import unicodedata
from db import clientes_collection


# Cache simple en memoria: token -> {sid, expiracion}
_sid_cache = {}

# Tiempo de expiración Wialon: 5 minutos de inactividad (según docs)
SID_EXPIRACION_MINUTOS = 5

def normalize_text(text):
    return unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode().lower()


def obtener_sid(token: str) -> str:
    global _sid_cache
    ahora = datetime.utcnow()

    cache = _sid_cache.get(token)
    print(_sid_cache)

    if cache:
        expiracion: datetime = cache.get("expiracion")
        if expiracion and ahora < expiracion:
            # Sid válido, actualizar expiración y retornarlo
            cache["expiracion"] = ahora + timedelta(minutes=SID_EXPIRACION_MINUTOS)
            return cache["sid"]
    print(cache)
    # Sid expirado o no existe, hacer login
    url = "https://hst-api.wialon.us/wialon/ajax.html"
    params = {
        "svc": "token/login",
        "params": json.dumps({"token": token})
    }
    r = requests.get(url, params=params)
    r.raise_for_status()
    data = r.json()

    sid = data.get("eid") or data.get("sid")
    if not sid:
        raise ValueError("No se pudo obtener el sid con el token proporcionado")

    # Guardar en cache con nueva expiración
    _sid_cache[token] = {
        "sid": sid,
        "expiracion": ahora + timedelta(minutes=SID_EXPIRACION_MINUTOS)
    }

    return sid


def obtener_datos_unidad(sid: str, uid: int) -> dict | None:
    url_unidad = "https://hst-api.wialon.us/wialon/ajax.html"
    params_unidad = {
        "svc": "core/search_item",
        "params": {
            "id": uid,
            "flags": 4611686018427387903
        },
        "sid": sid
    }
    try:
        ru = requests.get(url_unidad, params={"params": json.dumps(params_unidad["params"]), "svc": "core/search_item", "sid": sid})
        ru.raise_for_status()
        data_u = ru.json()
        item = data_u.get("item")
        if not item or "pos" not in item:
            return None

        matricula = ""
        if "flds" in item and isinstance(item["flds"], dict):
            for value in item["flds"].values():
                nombre_campo = value.get("n", "")
                if normalize_text(nombre_campo) == "matricula":
                    matricula = value.get("v", "")
                    break

        return {
            "id": str(item["id"]),
            "longitud": item["pos"]["x"],
            "latitud": item["pos"]["y"],
            "fecha": datetime.utcfromtimestamp(item["pos"]["t"]).isoformat(),
            "matricula": matricula
        }
    except Exception:
        # Puedes agregar aquí logging para errores
        return None


def llenar_unidades_para_cliente(cliente_id: str, token: str, grupo_nombre: str = "TRANSPORTES CARLITOS") -> list[dict]:
    sid = obtener_sid(token)

    # Obtener IDs de unidades del grupo específico
    url_grupo = "https://hst-api.wialon.us/wialon/ajax.html"
    params_grupo = {
        "svc": "core/search_items",
        "params": {
            "spec": {
                "itemsType": "avl_unit_group",
                "propName": "sys_name",
                "propValueMask": grupo_nombre,
                "sortType": "sys_name",
                "propType": "property"
            },
            "force": 1,
            "flags": 1,
            "from": 0,
            "to": 0
        },
        "sid": sid
    }

    r = requests.get(url_grupo, params={"params": json.dumps(params_grupo["params"]), "svc": "core/search_items", "sid": sid})
    r.raise_for_status()
    data = r.json()

    grupos = data.get("items", [])
    if not grupos:
        raise ValueError(f"No se encontraron grupos con el nombre '{grupo_nombre}'.")

    unidades_ids = grupos[0].get("u", [])
    if not unidades_ids:
        raise ValueError("No se encontraron unidades en el grupo.")

    unidades = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futuros = {executor.submit(obtener_datos_unidad, sid, uid): uid for uid in unidades_ids}
        for futuro in as_completed(futuros):
            resultado = futuro.result()
            if resultado:
                unidades.append(resultado)

    if not unidades:
        raise ValueError("No se pudo obtener información de las unidades.")

    # Actualizar el cliente en MongoDB con las unidades obtenidas
    result = clientes_collection.update_one(
        {"id": cliente_id},
        {"$set": {"unidades": unidades}}
    )

    if result.matched_count == 0:
        raise ValueError("Cliente no encontrado.")

    return unidades
