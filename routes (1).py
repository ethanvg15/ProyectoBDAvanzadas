from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.database import get_mongo_db, get_redis_client
from bson.objectid import ObjectId
import json
import uuid
eventos_bp = Blueprint("eventos", __name__)

@eventos_bp.route("/", methods=["GET"])
def index():
    """Redirige de la raíz al catálogo principal."""
    return redirect(url_for("eventos.ver_catalogo"))


@eventos_bp.route("/cargar", methods=["GET", "POST"])
def cargar_inicial():
    """
    Rubro 1: Carga Inicial de datos JSON a MongoDB.
    El nombre de esta función DEBE ser 'cargar_inicial' para hacer match con url_for('eventos.cargar_inicial').
    """
    if request.method == "POST":
        file = request.files.get("archivo_json")
        if not file or file.filename == "":
            flash("Debe seleccionar un archivo JSON válido.", "error")
            return redirect(request.url)

        try:
            db = get_mongo_db()
            contenido = json.load(file)

            if isinstance(contenido, list) and len(contenido) > 0:
                db.eventos.delete_many({})
                db.eventos.insert_many(contenido)
                flash(f"¡Éxito! Se cargaron {len(contenido)} eventos a MongoDB.", "success")
                return redirect(url_for("eventos.ver_catalogo"))
            else:
                flash("El archivo JSON debe contener una lista estructurada.", "error")

        except Exception as e:
            flash(f"Error al procesar el archivo: {str(e)}", "error")

        return redirect(request.url)

    return render_template("eventos/cargar.html")


@eventos_bp.route("/catalogo", methods=["GET"])
def ver_catalogo():
    """Rubro 2: Catálogo y preventa de eventos."""
    db = get_mongo_db()
    categoria_filtro = request.args.get("categoria", "")

    query = {}
    if categoria_filtro:
        query["categoria"] = categoria_filtro

    eventos = list(db.eventos.find(query))
    categorias = db.eventos.distinct("categoria")

    return render_template(
        "eventos/catalogo.html", 
        eventos=eventos, 
        categorias=categorias, 
        categoria_seleccionada=categoria_filtro
    )


@eventos_bp.route("/admin/preventa", methods=["GET", "POST"])
def configurar_preventa():
    db = get_mongo_db()
    redis_client = get_redis_client()

    if request.method == "POST":
        id_seleccionado = request.form.get("id_evento", "").strip()
        precio_preventa = float(request.form.get("precio"))
        cantidad_entradas = int(request.form.get("cantidad"))
        duracion_segundos = int(request.form.get("duracion_segundos"))

        # Construir filtro flexible (soporta id_evento string/int o ObjectId _id)
        filtros = [{"id_evento": id_seleccionado}]
        if id_seleccionado.isdigit():
            filtros.append({"id_evento": int(id_seleccionado)})
        if ObjectId.is_valid(id_seleccionado):
            filtros.append({"_id": ObjectId(id_seleccionado)})

        resultado = db.eventos.update_one(
            {"$or": filtros},
            {"$set": {
                "id_evento": id_seleccionado,
                "precio": precio_preventa,
                "entradas_disponibles": cantidad_entradas,
                "estado": "EN_PREVENTA"
            }}
        )

        if resultado.matched_count == 0:
            flash(f"No se encontró el evento '{id_seleccionado}' en la base de datos.", "error")
            return redirect(request.url)

        # Registrar ventana de preventa activa en Redis con TTL
        redis_client.setex(f"preventa_activa:{id_seleccionado}", duracion_segundos, "ACTIVA")

        flash(f"Preventa activada por {duracion_segundos} segundos para el evento {id_seleccionado}.", "success")
        return redirect(url_for("eventos.ver_catalogo"))

    eventos = list(db.eventos.find({}))
    return render_template("admin/configurar_preventa.html", eventos=eventos)
@eventos_bp.route("/reservar/<id_evento>", methods=["POST"])
def reservar_entrada(id_evento):
    """
    Fase 1 (Estado Activo / Bloqueo Temporal en Redis con TTL):
    Verifica el inventario real descontando reservas activas en RAM y bloquea el cupo.
    """
    db = get_mongo_db()
    redis_client = get_redis_client()

    cantidad_solicitada = int(request.form.get("cantidad", 1))
    if "cliente_id" not in session:
        session["cliente_id"] = str(uuid.uuid4())[:8]
    cliente_id = session["cliente_id"]

    # 1. Validar que la preventa siga activa en Redis
    if not redis_client.exists(f"preventa_activa:{id_evento}"):
        flash("La ventana de preventa para este evento ha expirado o no está activa.", "error")
        return redirect(url_for("eventos.ver_catalogo"))

    # 2. Consultar inventario persistente en MongoDB
    evento = db.eventos.find_one({"id_evento": id_evento})
    if not evento:
        flash("El evento seleccionado no existe.", "error")
        return redirect(url_for("eventos.ver_catalogo"))

    # 3. Calcular cupos retenidos en Redis por otros usuarios concurrentes
    llaves_reservas = redis_client.keys(f"reserva:{id_evento}:*")
    entradas_retenidas = sum(int(redis_client.get(k) or 0) for k in llaves_reservas)
    disponibles_reales = int(evento.get("entradas_disponibles", 0)) - entradas_retenidas

    if cantidad_solicitada > disponibles_reales:
        flash(f"Cupo insuficiente. Solo quedan {disponibles_reales} entradas disponibles.", "error")
        return redirect(url_for("eventos.ver_catalogo"))

    # 4. Crear bloqueo temporal en Redis con TTL de 120 segundos
    tiempo_ttl = 120
    llave_usuario = f"reserva:{id_evento}:{cliente_id}"
    redis_client.setex(llave_usuario, tiempo_ttl, cantidad_solicitada)

    flash(f"Reserva temporal activada por {tiempo_ttl} segundos.", "success")
    return redirect(url_for("eventos.checkout_reserva", id_evento=id_evento))


@eventos_bp.route("/checkout/<id_evento>", methods=["GET"])
def checkout_reserva(id_evento):
    """Muestra la ventana de confirmación mientras el TTL de Redis esté vigente."""
    db = get_mongo_db()
    redis_client = get_redis_client()
    cliente_id = session.get("cliente_id")

    llave_usuario = f"reserva:{id_evento}:{cliente_id}"
    ttl_restante = redis_client.ttl(llave_usuario)
    cantidad_reservada = redis_client.get(llave_usuario)

    if ttl_restante <= 0 or not cantidad_reservada:
        flash("Transacción abortada: Tu reserva temporal expiró y los cupos fueron liberados.", "error")
        return redirect(url_for("eventos.ver_catalogo"))

    evento = db.eventos.find_one({"id_evento": id_evento})
    return render_template(
        "eventos/checkout.html",
        evento=evento,
        cantidad=int(cantidad_reservada),
        ttl=ttl_restante
    )


@eventos_bp.route("/confirmar_compra/<id_evento>", methods=["POST"])
def confirmar_compra(id_evento):
    """
    Fase 2 (Estado Committed / Persistencia en MongoDB):
    Consolida la venta en disco y libera la llave temporal de Redis.
    """
    db = get_mongo_db()
    redis_client = get_redis_client()
    cliente_id = session.get("cliente_id")
    llave_usuario = f"reserva:{id_evento}:{cliente_id}"

    cantidad_str = redis_client.get(llave_usuario)
    if not cantidad_str:
        flash("Transacción abortada: El tiempo límite expiró antes de confirmar.", "error")
        return redirect(url_for("eventos.ver_catalogo"))

    cantidad_comprada = int(cantidad_str)
    evento = db.eventos.find_one({"id_evento": id_evento})

    # 1. Descontar inventario en MongoDB de forma atómica
    db.eventos.update_one(
        {"id_evento": id_evento},
        {"$inc": {"entradas_disponibles": -cantidad_comprada}}
    )

    # 2. Registrar comprobante en la colección 'ventas' (Durabilidad)
    db.ventas.insert_one({
        "id_venta": str(uuid.uuid4())[:12],
        "id_evento": id_evento,
        "nombre_evento": evento.get("nombre"),
        "cliente_id": cliente_id,
        "cantidad": cantidad_comprada,
        "total_pagado": cantidad_comprada * float(evento.get("precio", 0))
    })

    # 3. Liberar el bloqueo en Redis
    redis_client.delete(llave_usuario)

    flash("¡Compra confirmada (Committed) exitosamente!", "success")
    return redirect(url_for("eventos.ver_catalogo"))