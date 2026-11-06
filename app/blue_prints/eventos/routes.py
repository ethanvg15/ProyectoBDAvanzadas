from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.database import get_mongo_db
import json

# Blueprint oficial para el módulo de eventos
eventos_bp = Blueprint("eventos", __name__)

@eventos_bp.route("/", methods=["GET"])
def index():
    """
    Ruta raíz del módulo: Redirige automáticamente al catálogo principal.
    Resuelve el error 404 al entrar a http://localhost:5000/eventos/
    """
    return redirect(url_for("eventos.ver_catalogo"))


@eventos_bp.route("/cargar", methods=["GET", "POST"])
def cargar_inicial():
    """
    Rubro 1: Carga inicial de datos desde un archivo JSON a MongoDB (10 pts).
    Tras una carga exitosa, redirige automáticamente al flujo de Preventa/Catálogo.
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
                # Inserción masiva limpia en MongoDB
                db.eventos.delete_many({})
                db.eventos.insert_many(contenido)
                
                flash(f"¡Éxito! Se procesaron e insertaron {len(contenido)} eventos en MongoDB.", "success")
                
                # REDIRECCIÓN AUTOMÁTICA AL CATÁLOGO
                return redirect(url_for("eventos.ver_catalogo"))
            else:
                flash("El archivo JSON debe contener una lista válida de objetos.", "error")

        except Exception as e:
            flash(f"Error al procesar el archivo: {str(e)}", "error")

        return redirect(request.url)

    return render_template("eventos/cargar.html")


@eventos_bp.route("/catalogo", methods=["GET"])
def ver_catalogo():
    """
    Rubro 2: Consulta del catálogo de eventos en MongoDB con filtro por categoría.
    """
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