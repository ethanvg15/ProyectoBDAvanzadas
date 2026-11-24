from app.database import get_mongo_db, get_redis_client
from app.utils import id_de_evento

PREFIJO = "preventa:"


def formatear_tiempo(segundos):
    """Convierte segundos a texto legible. Ej.: 750 -> '12 minutos 30 segundos'."""
    minutos, seg = divmod(int(segundos), 60)
    partes = []
    if minutos:
        partes.append(f"{minutos} minuto" + ("" if minutos == 1 else "s"))
    if seg or not partes:
        partes.append(f"{seg} segundo" + ("" if seg == 1 else "s"))
    return " ".join(partes)


def listar_preventas_abiertas():
    """
    Devuelve las preventas vigentes (no vencidas y con entradas disponibles).
    - Entradas disponibles y tiempo restante: se leen de Redis (valor y TTL de la llave).
    - Nombre del evento y categoría: se leen del catálogo en MongoDB.
    Función compartida: la usan la funcionalidad 3 (lista de preventas abiertas)
    y la funcionalidad 4 (lista de preventas para obtener una entrada).
    """
    r = get_redis_client()
    db = get_mongo_db()

    # 1. Leer de Redis todas las llaves de preventa, con su valor y su TTL
    llaves = list(r.scan_iter(match=f"{PREFIJO}*"))
    if not llaves:
        return []

    pipe = r.pipeline()
    for llave in llaves:
        pipe.get(llave)
        pipe.ttl(llave)
    resultados = pipe.execute()

    # 2. Catálogo de eventos indexado por su id
    catalogo = {id_de_evento(e): e for e in db.eventos.find({})}

    # 3. Armar la lista
    preventas = []
    for i, llave in enumerate(llaves):
        valor, ttl = resultados[2 * i], resultados[2 * i + 1]
        id_evento = llave[len(PREFIJO):]
        try:
            entradas = int(valor)
        except (TypeError, ValueError):
            continue  # la llave desapareció (venció) o tiene un valor inválido

        # TTL < 0: la llave venció o no tiene vencimiento; entradas <= 0: preventa agotada
        if ttl is None or ttl <= 0 or entradas <= 0:
            continue

        evento = catalogo.get(id_evento)
        if evento is None:
            continue  # preventa de un evento que ya no está en el catálogo

        preventas.append({
            "id_evento": id_evento,
            "nombre": evento.get("nombre", "(sin nombre)"),
            "categoria": evento.get("categoria", ""),
            "entradas_disponibles": entradas,
            "segundos_restantes": ttl,
            "tiempo_restante": formatear_tiempo(ttl),
        })

    preventas.sort(key=lambda p: p["nombre"])
    return preventas
