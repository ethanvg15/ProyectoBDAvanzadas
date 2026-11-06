from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.database import get_redis_client, get_mongo_db
from datetime import datetime
import uuid

entradas_bp = Blueprint("entradas", __name__)

@entradas_bp.route("/obtener", methods=["GET", "POST"])
def obtener_entrada():
    r_redis = get_redis_client()
    db_mongo = get_mongo_db()

    if request.method == "POST":
        nombre_cliente = request.form.get("nombre_cliente").strip()
        id_evento = request.form.get("id_evento")

        # 1. Validar si el cliente ya tiene una entrada para este evento en MongoDB
        existente = db_mongo.entradas.find_one({"nombre_cliente": nombre_cliente, "id_evento": id_evento})
        if existente:
            flash("El cliente ya posee una entrada adjudicada para este evento.", "error")
            return redirect(request.url)

        key_redis = f"preventa:{id_evento}"

        # 2. Validar existencia y stock en Redis
        if not r_redis.exists(key_redis):
            flash("La preventa para este evento ha expirado o no existe.", "error")
            return redirect(request.url)

        entradas_disponibles = int(r_redis.hget(key_redis, "entradas_disponibles"))
        if entradas_disponibles <= 0:
            flash("No quedan entradas disponibles para esta preventa.", "error")
            return redirect(request.url)

        # 3. Decrementar stock de forma atómica en Redis
        r_redis.hincrby(key_redis, "entradas_disponibles", -1)

        # 4. Registrar la entrada obtenida en MongoDB
        evento = db_mongo.eventos.find_one({"id_evento": id_evento})
        codigo_unico = f"ENT-{uuid.uuid4().hex[:8].upper()}"

        documento_entrada = {
            "codigo": codigo_unico,
            "nombre_cliente": nombre_cliente,
            "id_evento": id_evento,
            "nombre_evento": evento.get("nombre"),
            "categoria": evento.get("categoria"),
            "fecha_adquisicion": datetime.now()
        }
        db_mongo.entradas.insert_one(documento_entrada)

        flash(f"Entrada adjudicada con éxito. Código asignado: {codigo_unico}", "success")
        return redirect(url_for("entradas.obtener_entrada"))

    return render_template("entradas/obtener.html")


@entradas_bp.route("/consulta", methods=["GET"])
def consulta_analitica():
    db_mongo = get_mongo_db()

    # Aggregation Pipeline para calcular total de entradas y clientes distintos por categoría
    pipeline = [
        {
            "$group": {
                "_id": "$categoria",
                "total_entradas": {"$sum": 1},
                "clientes_unicos": {"$addToSet": "$nombre_cliente"}
            }
        },
        {
            "$project": {
                "categoria": "$_id",
                "total_entradas": 1,
                "cantidad_clientes_distintos": {"$size": "$clientes_unicos"},
                "_id": 0
            }
        }
    ]

    resultados = list(db_mongo.entradas.aggregate(pipeline))
    return render_template("entradas/consulta.html", resultados=resultados)