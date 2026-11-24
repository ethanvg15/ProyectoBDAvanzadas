from bson.errors import InvalidId
from bson.objectid import ObjectId
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.database import get_mongo_db, get_redis_client
from app.utils import id_de_evento
from app.preventas_servicio import listar_preventas_abiertas

preventas_bp = Blueprint("preventas", __name__)


def clave_preventa(id_evento):
    """Nombre de la llave en Redis. Ejemplo: preventa:E001"""
    return f"preventa:{id_evento}"


@preventas_bp.route("/abrir", methods=["GET", "POST"])
def abrir_preventa():
    """
    Funcionalidad 2: abrir la preventa de un evento.
    - El evento se elige del catálogo (MongoDB). El catálogo no se modifica.
    - La preventa vive solo en Redis: la llave guarda las entradas disponibles
      y su vencimiento lo controla el TTL de Redis (la duración llega en minutos).
    - No se permite abrir una preventa si el evento ya tiene una abierta.
    """
    db = get_mongo_db()
    r = get_redis_client()

    if request.method == "POST":
        # 1. Validar los datos del formulario
        try:
            entradas = int(request.form.get("entradas", ""))
            minutos = int(request.form.get("minutos", ""))
        except ValueError:
            flash("La cantidad de entradas y la duración deben ser números enteros.", "error")
            return redirect(url_for("preventas.abrir_preventa"))

        if entradas < 1 or minutos < 1:
            flash("La cantidad de entradas y la duración deben ser mayores que cero.", "error")
            return redirect(url_for("preventas.abrir_preventa"))

        # 2. Buscar el evento en el catálogo (MongoDB)
        try:
            evento = db.eventos.find_one({"_id": ObjectId(request.form.get("evento", ""))})
        except InvalidId:
            evento = None
        if evento is None:
            flash("Debe seleccionar un evento válido del catálogo.", "error")
            return redirect(url_for("preventas.abrir_preventa"))

        id_evento = id_de_evento(evento)
        llave = clave_preventa(id_evento)
        segundos = minutos * 60

        # 3. Crear la preventa en Redis con su TTL en UNA sola operación atómica.
        #    nx=True -> solo se crea si la llave NO existe (evita duplicar la preventa).
        creada = r.set(llave, entradas, nx=True, ex=segundos)

        # Una preventa con 0 entradas ya está agotada (cerrada): se puede reabrir.
        if not creada:
            actuales = r.get(llave)
            if actuales is not None and int(actuales) <= 0:
                r.delete(llave)
                creada = r.set(llave, entradas, nx=True, ex=segundos)

        if not creada:
            flash(f"El evento «{evento.get('nombre')}» ya tiene una preventa abierta.", "error")
            return redirect(url_for("preventas.abrir_preventa"))

        flash(
            f"Preventa abierta: «{evento.get('nombre')}» con {entradas} entradas "
            f"disponibles durante {minutos} minuto(s).",
            "success",
        )
        return redirect(url_for("preventas.abrir_preventa"))

    # GET: mostrar el formulario con los eventos del catálogo
    eventos = [
        {"_id": str(e["_id"]), "nombre": e.get("nombre", "(sin nombre)"), "categoria": e.get("categoria", "")}
        for e in db.eventos.find({})
    ]
    return render_template("preventas/abrir.html", eventos=eventos)


@preventas_bp.route("/activas", methods=["GET"])
def preventas_activas():
    """
    Funcionalidad 3: mostrar las preventas abiertas (vigentes).
    Entradas disponibles y tiempo restante salen de Redis; el nombre del evento
    y la categoría, del catálogo en MongoDB.
    """
    preventas = listar_preventas_abiertas()
    return render_template("preventas/activas.html", preventas=preventas)
