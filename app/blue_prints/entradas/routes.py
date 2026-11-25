from datetime import datetime, timezone

from bson.objectid import ObjectId
from flask import Blueprint, render_template, request, redirect, url_for, flash
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.database import get_mongo_db, get_redis_client
from app.preventas_servicio import PREFIJO, listar_preventas_abiertas

entradas_bp = Blueprint("entradas", __name__)

# ---------------------------------------------------------------------------
# Scripts Lua. Redis ejecuta cada script completo, sin que otro cliente se cuele
# a la mitad: por eso dos personas que piden la última entrada al mismo tiempo
# nunca pueden llevársela las dos.
# ---------------------------------------------------------------------------

# Descuenta una entrada solo si la preventa existe y todavía le quedan entradas.
# Devuelve: las entradas que quedan (>= 0), -1 si está agotada, -2 si venció.
# DECR conserva el TTL de la llave.
LUA_DESCONTAR = """
local valor = redis.call('GET', KEYS[1])
if not valor then return -2 end
if tonumber(valor) <= 0 then return -1 end
return redis.call('DECR', KEYS[1])
"""

# Devuelve una entrada a la preventa (si hubo que deshacer un descuento), pero solo si
# la llave todavía existe. Un INCR directo sobre una llave vencida la crearía de nuevo
# SIN tiempo de vida, y esa preventa quedaría abierta para siempre.
LUA_DEVOLVER = """
if redis.call('EXISTS', KEYS[1]) == 1 then return redis.call('INCR', KEYS[1]) end
return -2
"""

_indices_listos = False


def clave_preventa(id_evento):
    """Nombre de la llave de la preventa en Redis. Ejemplo: preventa:E001"""
    return f"{PREFIJO}{id_evento}"


def buscar_evento(db, id_evento):
    """Busca en el catálogo (MongoDB) el evento cuyo identificador, en texto, es id_evento.
    Acepta ids de texto ('E001'), numéricos (1) o el _id interno de Mongo."""
    filtros = [{"id": id_evento}]
    if id_evento.lstrip("-").isdigit():
        filtros.append({"id": int(id_evento)})
    if ObjectId.is_valid(id_evento):
        filtros.append({"_id": ObjectId(id_evento)})

    for filtro in filtros:
        evento = db.eventos.find_one(filtro)
        if evento is not None:
            return evento
    return None


def asegurar_indices(db):
    """
    Crea (una sola vez) los índices únicos de la colección 'entradas':
    - (cliente_clave, id_evento): un cliente solo puede tener una entrada por evento.
      Es la garantía final aunque dos solicitudes del mismo cliente lleguen a la vez.
    - codigo: el código de cada entrada es único.
    """
    global _indices_listos
    if _indices_listos:
        return
    db.entradas.create_index([("cliente_clave", 1), ("id_evento", 1)], unique=True, name="uniq_cliente_evento")
    db.entradas.create_index("codigo", unique=True, name="uniq_codigo")
    _indices_listos = True


def generar_codigo(db, id_evento):
    """
    Genera un código único y legible: <ID del evento>-<consecutivo>. Ejemplo: E001-0001.
    El consecutivo sale de un contador en MongoDB que se incrementa de forma atómica.
    """
    contador = db.contadores.find_one_and_update(
        {"_id": f"entradas:{id_evento}"},
        {"$inc": {"n": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return f"{id_evento}-{contador['n']:04d}"


def descontar_entrada(r, id_evento):
    return int(r.register_script(LUA_DESCONTAR)(keys=[clave_preventa(id_evento)]))


def devolver_entrada(r, id_evento):
    r.register_script(LUA_DEVOLVER)(keys=[clave_preventa(id_evento)])


@entradas_bp.route("/obtener", methods=["GET", "POST"])
def obtener_entrada():
    """
    Funcionalidad 4: obtener una entrada.
    El cliente se identifica con su nombre y elige una de las preventas abiertas.
    Se descuenta una entrada en Redis y la entrada queda registrada en MongoDB.
    """
    db = get_mongo_db()
    r = get_redis_client()

    if request.method == "POST":
        # Se normalizan los espacios: "  Ana   Torres " es el mismo cliente que "Ana Torres".
        nombre = " ".join(request.form.get("nombre_cliente", "").split())
        id_evento = request.form.get("id_evento", "").strip()

        def volver():
            # Se devuelve el nombre para que el formulario quede listo para el siguiente intento.
            return redirect(url_for("entradas.obtener_entrada", nombre=nombre))

        if not nombre:
            flash("Debe indicar el nombre del cliente.", "error")
            return volver()
        if not id_evento:
            flash("Debe seleccionar un evento de la lista de preventas abiertas.", "error")
            return volver()

        evento = buscar_evento(db, id_evento)
        if evento is None:
            flash("El evento seleccionado no existe en el catálogo.", "error")
            return volver()
        nombre_evento = evento.get("nombre", id_evento)

        # 1. Preventa vencida: su llave ya no existe en Redis.
        if not r.exists(clave_preventa(id_evento)):
            flash(f"La preventa de «{nombre_evento}» ya venció.", "error")
            return volver()

        asegurar_indices(db)

        # 2. Cliente repetido: ya tiene una entrada de este evento.
        #    (La comparación ignora mayúsculas: "ana" y "Ana" son la misma persona.)
        cliente_clave = nombre.casefold()
        if db.entradas.find_one({"cliente_clave": cliente_clave, "id_evento": id_evento}):
            flash("Cliente ya tiene una entrada de este evento.", "error")
            return volver()

        # 3. Descontar una entrada en Redis, de forma atómica.
        restantes = descontar_entrada(r, id_evento)
        if restantes == -2:
            flash(f"La preventa de «{nombre_evento}» ya venció.", "error")
            return volver()
        if restantes == -1:
            flash(f"La preventa de «{nombre_evento}» está agotada: ya no quedan entradas disponibles.", "error")
            return volver()

        # 4. Registrar la entrada en MongoDB. Si algo falla aquí, se devuelve la entrada
        #    a Redis para no perderla.
        try:
            codigo = generar_codigo(db, id_evento)
            db.entradas.insert_one({
                "codigo": codigo,
                "nombre_cliente": nombre,
                "cliente_clave": cliente_clave,
                "id_evento": id_evento,
                "nombre_evento": nombre_evento,
                "categoria": evento.get("categoria"),
                "fecha_hora": datetime.now(timezone.utc),
            })
        except DuplicateKeyError:
            # Dos solicitudes del mismo cliente llegaron a la vez: el índice único dejó pasar solo una.
            devolver_entrada(r, id_evento)
            flash("Cliente ya tiene una entrada de este evento.", "error")
            return volver()
        except Exception:
            devolver_entrada(r, id_evento)
            flash("No se pudo registrar la entrada. Intente de nuevo.", "error")
            return volver()

        plural = "entrada disponible" if restantes == 1 else "entradas disponibles"
        flash(
            f"{nombre} obtuvo una entrada para «{nombre_evento}». Código: {codigo}. "
            f"A la preventa le quedan {restantes} {plural}.",
            "success",
        )
        return volver()

    return render_template(
        "entradas/obtener.html",
        preventas=listar_preventas_abiertas(),
        nombre=request.args.get("nombre", ""),
    )


@entradas_bp.route("/consulta", methods=["GET"])
def consultar_entradas():
    """
    Funcionalidad 5: por categoría, el total de entradas obtenidas y la cantidad de
    clientes distintos. Un cliente con entradas de varios eventos de la misma categoría
    cuenta una sola vez en esa categoría ($addToSet no repite valores).
    """
    db = get_mongo_db()

    pipeline = [
        {"$group": {
            "_id": "$categoria",
            "total": {"$sum": 1},
            "clientes": {"$addToSet": "$cliente_clave"},
        }}
    ]
    por_categoria = {doc["_id"]: doc for doc in db.entradas.aggregate(pipeline)}

    # Se listan todas las categorías del catálogo, incluso las que aún no tienen entradas.
    categorias = set(db.eventos.distinct("categoria")) | set(por_categoria)

    filas = []
    for categoria in sorted(categorias, key=lambda c: str(c).casefold()):
        doc = por_categoria.get(categoria)
        filas.append({
            "categoria": categoria or "(sin categoría)",
            "total": doc["total"] if doc else 0,
            "clientes": len(doc["clientes"]) if doc else 0,
        })

    return render_template("entradas/consulta.html", filas=filas)
