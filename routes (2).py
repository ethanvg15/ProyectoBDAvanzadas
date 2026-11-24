from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.database import get_redis_client, get_mongo_db

preventas_bp = Blueprint("preventas", __name__)

@preventas_bp.route("/abrir", methods=["GET", "POST"])
def abrir_preventa():
    db_mongo = get_mongo_db()
    r_redis = get_redis_client()

    if request.method == "POST":
        id_evento = request.form.get("id_evento")
        entradas = int(request.form.get("entradas", 0))
        duracion_minutos = int(request.form.get("duracion_minutos", 0))

        key_redis = f"preventa:{id_evento}"

        # Validar si ya existe una preventa activa para el mismo evento en Redis
        if r_redis.exists(key_redis):
            flash("El evento ya cuenta con una preventa activa.", "error")
            return redirect(request.url)

        # Convertir minutos a segundos para el TTL de Redis
        ttl_segundos = duracion_minutos * 60

        # Guardar en Redis mediante Hash o Estructura dedicada
        # Se establece la llave con el TTL correspondiente
        r_redis.hset(key_redis, mapping={"entradas_disponibles": entradas, "id_evento": id_evento})
        r_redis.expire(key_redis, ttl_segundos)

        flash("Preventa abierta y registrada en Redis con éxito.", "success")
        return redirect(url_for("preventas.preventas_activas"))

    # Obtener catálogo de MongoDB para el selector del formulario
    eventos = list(db_mongo.eventos.find({}))
    return render_template("preventas/abrir.html", eventos=eventos)


@preventas_bp.route("/activas", methods=["GET"])
def preventas_activas():
    r_redis = get_redis_client()
    db_mongo = get_mongo_db()

    # Buscar todas las llaves que coincidan con el patrón preventa:*
    keys = r_redis.keys("preventa:*")
    preventas = []

    for key in keys:
        datos = r_redis.hgetall(key)
        ttl_restante = r_redis.ttl(key) # Obtener TTL en segundos
        
        # Consultar detalles del evento en MongoDB
        evento = db_mongo.eventos.find_one({"id_evento": datos.get("id_evento")})
        
        if evento:
            preventas.append({
                "nombre_evento": evento.get("nombre"),
                "categoria": evento.get("categoria"),
                "entradas_disponibles": datos.get("entradas_disponibles"),
                "minutos_restantes": round(ttl_restante / 60, 2)
            })

    return render_template("preventas/activas.html", preventas=preventas)